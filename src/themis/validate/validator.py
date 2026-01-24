from __future__ import annotations

from typing import Any, Dict, List, Tuple

import polars as pl

from themis.contracts.normalize import required_columns
from themis.validate.results import RuleResult, ValidationRun
from themis.validate.rules import check_ranges, check_allowed_values, check_regex


def _severity(contract: Dict[str, Any], rule_name: str, default: str = "error") -> str:
    sev = (contract.get("severity") or {}).get(rule_name, default)
    sev = str(sev).lower()
    return sev if sev in {"error", "warn"} else default


def check_schema_required_columns(df: pl.DataFrame, contract: Dict[str, Any]) -> RuleResult:
    req = required_columns(contract)
    missing = [c for c in req if c not in df.columns]
    passed = len(missing) == 0
    return RuleResult(
        rule="schema_required_columns",
        severity=_severity(contract, "schema_required_columns", default="error"),
        passed=passed,
        details={"required": req, "missing": missing},
    )


def check_not_null(df: pl.DataFrame, contract: Dict[str, Any]) -> Tuple[RuleResult, pl.Series]:
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

    fail_mask = df.select(mask.alias("_fail"))["_fail"]
    failed_rows = int(fail_mask.sum())

    result = RuleResult(
        rule="not_null",
        severity=_severity(contract, "not_null", default="error"),
        passed=(failed_rows == 0),
        details={"columns": cols, "failed_rows": failed_rows},
    )
    return result, fail_mask


def check_uniqueness_pk(df: pl.DataFrame, contract: Dict[str, Any]) -> Tuple[RuleResult, pl.Series]:
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


def _append_reason_strings(base: pl.Series, fail_mask: pl.Series, reason: str) -> pl.Series:
    n = len(base)
    return pl.Series([
        (base[i] + (f"|{reason}" if base[i] else reason)) if bool(fail_mask[i]) else base[i]
        for i in range(n)
    ])


"""
------------------------------------------------------------------------------------------------
validate uses a reasons vector, checking schema, not_null, uniqueness rules, and row based rules
(ranges, allowed values, regex). 

reasons vector goes through each check appending rule failure reasoning, and warn reasoning

quarantine logic: rows with a reason string length >0 are quarantined (since they must
include at least one scheme, not_null, or uniqueness rule violation)

Quarantine depends on ERROR not WARN (WARN doesn't warrant quarantine)

Clean rows and quarantined rows are split by their classification (clean or quarantine) by
an error mask

ValidationRun is built
------------------------------------------------------------------------------------------------
"""

def validate(df: pl.DataFrame, contract: Dict[str, Any]) -> tuple[ValidationRun, pl.DataFrame, pl.DataFrame]:
    dataset_name = str(contract["dataset_name"])
    total = df.height
    rule_results: List[RuleResult] = []

    err_reasons = pl.Series([""] * total)
    warn_reasons = pl.Series([""] * total)

    # 1) Schema
    r_schema = check_schema_required_columns(df, contract)
    rule_results.append(r_schema)

    if not r_schema.passed and r_schema.severity == "error":
        err_reasons = pl.Series(["missing_required_columns"] * total)
        df_out = df.with_columns(
            pl.lit(err_reasons).alias("__themis_error_reasons__"),
            pl.lit(warn_reasons).alias("__themis_warn_reasons__"),
        )
        run = ValidationRun(
            dataset_name=dataset_name,
            total_rows=total,
            error_failed=True,
            rule_results=rule_results,
        )
        return run, df_out.head(0), df_out

    # 2) not_null
    r_nn, nn_fail = check_not_null(df, contract)
    rule_results.append(r_nn)
    if nn_fail.any():
        if r_nn.severity == "error":
            err_reasons = _append_reason_strings(err_reasons, nn_fail, "not_null")
        else:
            warn_reasons = _append_reason_strings(warn_reasons, nn_fail, "not_null")

    # 3) uniqueness
    r_uniq, uq_fail = check_uniqueness_pk(df, contract)
    rule_results.append(r_uniq)
    if uq_fail.any():
        if r_uniq.severity == "error":
            err_reasons = _append_reason_strings(err_reasons, uq_fail, "uniqueness")
        else:
            warn_reasons = _append_reason_strings(warn_reasons, uq_fail, "uniqueness")

    # 4) ranges
    r_rng, rng_fail = check_ranges(df, contract)
    rule_results.append(r_rng)
    if rng_fail.any():
        if r_rng.severity == "error":
            err_reasons = _append_reason_strings(err_reasons, rng_fail, "ranges")
        else:
            warn_reasons = _append_reason_strings(warn_reasons, rng_fail, "ranges")

    # 5) allowed_values
    r_av, av_fail = check_allowed_values(df, contract)
    rule_results.append(r_av)
    if av_fail.any():
        if r_av.severity == "error":
            err_reasons = _append_reason_strings(err_reasons, av_fail, "allowed_values")
        else:
            warn_reasons = _append_reason_strings(warn_reasons, av_fail, "allowed_values")

    # 6) regex
    r_rx, rx_fail = check_regex(df, contract)
    rule_results.append(r_rx)
    if rx_fail.any():
        if r_rx.severity == "error":
            err_reasons = _append_reason_strings(err_reasons, rx_fail, "regex")
        else:
            warn_reasons = _append_reason_strings(warn_reasons, rx_fail, "regex")

    df_out = df.with_columns(
        pl.lit(err_reasons).alias("__themis_error_reasons__"),
        pl.lit(warn_reasons).alias("__themis_warn_reasons__"),
    )

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