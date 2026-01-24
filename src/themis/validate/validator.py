from __future__ import annotations

from typing import Any, Dict, List, Tuple

import polars as pl

from themis.validate.results import RuleResult, ValidationRun

# Read severity from YAML: if missing fall to default
# later allow WARN rules for annotation but NOT quarantine
def _severity(contract: Dict[str, Any], rule_name: str, default: str = "error") -> str:
    sev = (contract.get("severity") or {}).get(rule_name, default)
    sev = str(sev).lower()
    if sev not in {"error", "warn"}:
        return default
    return sev

# Lists required columns from the data contract
def _required_columns(contract: Dict[str, Any]) -> List[str]:
    cols = contract.get("columns") or []
    required = []
    for c in cols:
        if c.get("required") is True:
            required.append(c["name"])
    return required

# Check required columns exist in the dataframe
def check_schema_required_columns(
    df: pl.DataFrame, contract: Dict[str, Any]
) -> RuleResult:
    required = _required_columns(contract)
    missing = [c for c in required if c not in df.columns]
    passed = len(missing) == 0
    return RuleResult(
        rule="schema_required_columns",
        severity=_severity(contract, "schema_required_columns", default="error"),
        passed=passed,
        details={"required": required, "missing": missing},
    )

# Check not_null contract rule

"""
------------------------------------------------------------------------------------------

RuleResult: checks adherence to not_null rule defined in contract

fail_mask: boolean mask (for each row) where True => failure of not_null rule

------------------------------------------------------------------------------------------
"""
def check_not_null(
    df: pl.DataFrame, contract: Dict[str, Any]
) -> Tuple[RuleResult, pl.Series]:
    cols = (contract.get("rules") or {}).get("not_null", []) or []
    cols = [c for c in cols if c in df.columns]

    if not cols:
        result = RuleResult(
            rule="not_null",
            severity=_severity(contract, "not_null", default="error"),
            passed=True,
            details={"columns": [], "failed_rows": 0},
        )
        return result, pl.Series([False] * df.height)

    mask = pl.lit(False)
    for c in cols:
        mask = mask | pl.col(c).is_null()

    fail_mask_df = df.select(mask.alias("_fail"))
    fail_mask = fail_mask_df["_fail"]
    failed_rows = int(fail_mask.sum())

    result = RuleResult(
        rule="not_null",
        severity=_severity(contract, "not_null", default="error"),
        passed=(failed_rows == 0),
        details={"columns": cols, "failed_rows": failed_rows},
    )
    return result, fail_mask

# Check primary key uniqueness

"""
------------------------------------------------------------------------------------------

count over the primary keys in each row, if count > 1, then that row belongs
to a duplicate primary key group

RuleResult: Summary of duplicate rows

fail_mask: shows which rows are duplicates

------------------------------------------------------------------------------------------
"""
def check_uniqueness_pk(
    df: pl.DataFrame, contract: Dict[str, Any]
) -> Tuple[RuleResult, pl.Series]:
    pk = contract.get("primary_key") or []
    if isinstance(pk, str):
        pk = [pk]
    pk = [c for c in pk if c in df.columns]

    if not pk:
        result = RuleResult(
            rule="uniqueness",
            severity=_severity(contract, "uniqueness", default="error"),
            passed=True,
            details={"pk": [], "duplicate_rows": 0},
        )
        return result, pl.Series([False] * df.height)

    # mark duplicates using a group count
    tmp = df.with_row_index("__row__").with_columns(
        pl.len().over(pk).alias("__pk_count__")
    )
    fail_mask = (tmp["__pk_count__"] > 1)
    dup_rows = int(fail_mask.sum())

    result = RuleResult(
        rule="uniqueness",
        severity=_severity(contract, "uniqueness", default="error"),
        passed=(dup_rows == 0),
        details={"pk": pk, "duplicate_rows": dup_rows},
    )
    return result, fail_mask

"""
------------------------------------------------------------------------------------------------
validate uses a reasons vector, checking schema, not_null, and uniqueness rules. 

reasons vector goes through each check appending rule failure reasoning

Schema error => quarantine everything (severe rule failure since missing required columns)
otherwise, reason vector is empty and everything is clean

not_null and uniqueness rules are ERROR level, the failure reasoning is appended to the
reason vector

error reasons are added to the dataframe

quarantine logic: rows with a reason string length >0 are quarantined (since they must
include at least one scheme, not_null, or uniqueness rule violation)

Clean rows and quarantined rows are split by their classification (clean or quarantine) by
an error mask

ValidationRun is built
------------------------------------------------------------------------------------------------
"""

def validate(df: pl.DataFrame, contract: Dict[str, Any]) -> tuple[ValidationRun, pl.DataFrame, pl.DataFrame]:
    dataset_name = str(contract["dataset_name"])
    total = df.height
    rule_results: List[RuleResult] = []

    # Start with "no error reasons"
    reasons = pl.Series([""] * total)

    # Schema: required columns must exist
    r_schema = check_schema_required_columns(df, contract)
    rule_results.append(r_schema)

    if not r_schema.passed and r_schema.severity == "error":
        # schema error: no safe row-level quarantine split possible, so quarantine everything
        reasons = pl.Series(["missing_required_columns"] * total)
        df2 = df.with_columns(pl.lit(reasons).alias("__themis_error_reasons__"))
        run = ValidationRun(
            dataset_name=dataset_name,
            total_rows=total,
            error_failed=True,
            rule_results=rule_results,
        )
        # clean empty, quarantine all
        return run, df2.head(0), df2

    # not_null
    r_nn, nn_fail = check_not_null(df, contract)
    rule_results.append(r_nn)
    if r_nn.severity == "error" and nn_fail.any():
        reasons = pl.Series([
            (reasons[i] + ("|not_null" if reasons[i] else "not_null")) if bool(nn_fail[i]) else reasons[i]
            for i in range(total)
        ])

    # uniqueness
    r_uniq, uq_fail = check_uniqueness_pk(df, contract)
    rule_results.append(r_uniq)
    if r_uniq.severity == "error" and uq_fail.any():
        reasons = pl.Series([
            (reasons[i] + ("|uniqueness" if reasons[i] else "uniqueness")) if bool(uq_fail[i]) else reasons[i]
            for i in range(total)
        ])

    df_out = df.with_columns(pl.lit(reasons).alias("__themis_error_reasons__"))
    error_mask = df_out["__themis_error_reasons__"].str.len_chars() > 0

    df_quarantine = df_out.filter(error_mask)
    df_clean = df_out.filter(~error_mask)

    error_failed = df_quarantine.height > 0
    run = ValidationRun(
        dataset_name=dataset_name,
        total_rows=total,
        error_failed=error_failed,
        rule_results=rule_results,
    )
    return run, df_clean, df_quarantine
