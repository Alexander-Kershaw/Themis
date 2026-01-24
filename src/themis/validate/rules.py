from __future__ import annotations

from typing import Any, Dict, List, Tuple

import polars as pl
from themis.validate.results import RuleResult
from themis.contracts.normalize import columns_by_name

"""
------------------------------------------------------------------------------------------------

Rules (row-level checks):

- Each helper function returns a RuleResult summary and a fail_mask (row boolean mask)

------------------------------------------------------------------------------------------------
"""

def _severity(contract: Dict[str, Any], rule_name: str, default: str = "error") -> str:
    sev = (contract.get("severity") or {}).get(rule_name, default)
    sev = str(sev).lower()
    return sev if sev in {"error", "warn"} else default


def _empty_mask(n: int) -> pl.Series:
    return pl.Series([False] * n)


def check_ranges(df: pl.DataFrame, contract: Dict[str, Any]) -> Tuple[RuleResult, pl.Series]:
    # Contract can define min/max at column level
    meta = columns_by_name(contract)
    n = df.height
    if n == 0:
        return RuleResult("ranges", _severity(contract, "ranges"), True, {"failed_rows": 0}), _empty_mask(0)

    mask = pl.lit(False)
    active_cols: List[str] = []

    for name, spec in meta.items():
        if name not in df.columns:
            continue
        min_v = spec.get("min", None)
        max_v = spec.get("max", None)
        if min_v is None and max_v is None:
            continue

        active_cols.append(name)
        col = pl.col(name)
        m = pl.lit(False)
        if min_v is not None:
            m = m | (col < pl.lit(min_v))
        if max_v is not None:
            m = m | (col > pl.lit(max_v))
        mask = mask | m

    if not active_cols:
        rr = RuleResult("ranges", _severity(contract, "ranges"), True, {"columns": [], "failed_rows": 0})
        return rr, _empty_mask(n)

    fail_mask = df.select(mask.alias("_fail"))["_fail"]
    failed_rows = int(fail_mask.sum())
    rr = RuleResult("ranges", _severity(contract, "ranges"), failed_rows == 0, {"columns": active_cols, "failed_rows": failed_rows})
    return rr, fail_mask


def check_allowed_values(df: pl.DataFrame, contract: Dict[str, Any]) -> Tuple[RuleResult, pl.Series]:
    # Contract column-level (check dataframe against contract allowed values)
    meta = columns_by_name(contract)
    n = df.height
    mask = pl.lit(False)
    active_cols: List[str] = []

    for name, spec in meta.items():
        if name not in df.columns:
            continue
        allowed = spec.get("allowed_values", None)
        if not allowed:
            continue
        active_cols.append(name)
        mask = mask | (~pl.col(name).is_in(list(allowed)) & pl.col(name).is_not_null())

    if not active_cols:
        rr = RuleResult("allowed_values", _severity(contract, "allowed_values"), True, {"columns": [], "failed_rows": 0})
        return rr, _empty_mask(n)

    fail_mask = df.select(mask.alias("_fail"))["_fail"]
    failed_rows = int(fail_mask.sum())
    rr = RuleResult("allowed_values", _severity(contract, "allowed_values"), failed_rows == 0, {"columns": active_cols, "failed_rows": failed_rows})
    return rr, fail_mask


def check_regex(df: pl.DataFrame, contract: Dict[str, Any]) -> Tuple[RuleResult, pl.Series]:
    # Contract column-level checking contract regex rules
    meta = columns_by_name(contract)
    n = df.height
    mask = pl.lit(False)
    active_cols: List[str] = []

    for name, spec in meta.items():
        if name not in df.columns:
            continue
        pattern = spec.get("regex", None)
        if not pattern:
            continue
        active_cols.append(name)
        # Fails if not matching regex AND not null
        mask = mask | (
            pl.col(name).is_not_null()
            & (~pl.col(name).cast(pl.Utf8).str.contains(pattern))
        )

    if not active_cols:
        rr = RuleResult("regex", _severity(contract, "regex"), True, {"columns": [], "failed_rows": 0})
        return rr, _empty_mask(n)

    fail_mask = df.select(mask.alias("_fail"))["_fail"]
    failed_rows = int(fail_mask.sum())
    rr = RuleResult("regex", _severity(contract, "regex"), failed_rows == 0, {"columns": active_cols, "failed_rows": failed_rows})
    return rr, fail_mask
