from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

"""
--------------------------------------------------------------------------------------------------------
Dtype checks and coercion
--------------------------------------------------------------------------------------------------------

dtypes.py serves to check data type missingness and compatibility, with type coersion to 
cast to expected dtype.

--------------------------------------------------------------------------------------------------------
For each column:

- if missing dtype -> records an issue ("missing:)"
- if the dtype is compatible -> record as "ok"
- else, coerce datatype (--coerce-dtypes):
        - attempts to cast into expected dtype
        - if the coercion works, label as "coerced"
        - if not, recorded as "mismatch"

- dtype_mode controls whether mismatches fail the run:
        - off: ignore dtype entirely
        - warm: report only
        - error: fail run if any mismatch or missing dtypes
--------------------------------------------------------------------------------------------------------        
"""

@dataclass(frozen=True)
class DTypeIssue:
    column: str
    expected: str
    actual: str
    action: str  # "ok" | "coerced" | "mismatch" | "missing"
    note: str = ""

# Using polars dtypes
def _expected_to_polars(expected: str) -> Optional[pl.DataType]:
    e = (expected or "").lower()
    if e == "string":
        return pl.Utf8
    if e == "int":
        return pl.Int64
    if e == "float":
        return pl.Float64
    if e == "bool":
        return pl.Boolean
    if e == "datetime":
        return pl.Datetime
    return None


def _is_compatible(actual: pl.DataType, expected: str) -> bool:
    e = (expected or "").lower()

    if e == "string":
        return actual == pl.Utf8

    if e == "int":
        return actual in (
            pl.Int8, pl.Int16, pl.Int32, pl.Int64,
            pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
        )

    if e == "float":
        # ints are compatible for float expectations
        (
            pl.Float32, pl.Float64,
            pl.Int8, pl.Int16, pl.Int32, pl.Int64,
            pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
        )

    if e == "bool":
        return actual == pl.Boolean

    if e == "datetime":
        return actual in (pl.Date, pl.Datetime)

    return True  # dont block unknown expected type


def _coerce_series(s: pl.Series, expected: str) -> pl.Series:
    e = (expected or "").lower()

    """
    NOTE: coersion is a best effort in matching a dtype, but should not
            throw for bad values. So, a strict=False is used where possible to
            turn a failure into nulls
    """

    if e == "string":
        return s.cast(pl.Utf8, strict=False)

    if e == "int":
        return s.cast(pl.Int64, strict=False)

    if e == "float":
        return s.cast(pl.Float64, strict=False)

    if e == "bool":
        if s.dtype == pl.Boolean:
            return s
        return s.cast(pl.Boolean, strict=False)

    if e == "datetime":
        if s.dtype in (pl.Date, pl.Datetime):
            return s.cast(pl.Datetime, strict=False)

        if s.dtype == pl.Utf8:
            return s.str.strptime(pl.Datetime, strict=False)

        return s.cast(pl.Datetime, strict=False)

    return s


def apply_dtype_policy(
    df: pl.DataFrame,
    contract: Dict[str, Any],
    *,
    dtype_mode: str = "off",      # "off" | "warn" | "error"
    coerce: bool = False,
) -> Tuple[pl.DataFrame, List[DTypeIssue], bool]:
    """
    Returns: (df_out, issues, dtype_failed)

    dtype_failed: schema dtype validation considered failed (at error severity)
    depending on dtype_mode
    """
    mode = (dtype_mode or "off").lower()
    if mode not in {"off", "warn", "error"}:
        raise ValueError("dtype_mode must be one of: off, warn, error")

    cols_spec = contract.get("columns", []) or []
    issues: List[DTypeIssue] = []
    df_out = df

    # If dtype checking is off do nothing
    if mode == "off":
        return df_out, issues, False

    # Build expected types for columns that have dtype defined
    expected_map: Dict[str, str] = {}
    for c in cols_spec:
        name = c.get("name")
        expected = c.get("dtype")
        if name and expected:
            expected_map[str(name)] = str(expected)

    # Check each expected dtype
    for col, expected in expected_map.items():
        if col not in df_out.columns:
            issues.append(DTypeIssue(column=col, expected=expected, actual="(missing)", action="missing"))
            continue

        actual_dtype = df_out[col].dtype
        actual_str = str(actual_dtype)

        # check expected and actual dtype compatibility
        if _is_compatible(actual_dtype, expected):
            issues.append(DTypeIssue(column=col, expected=expected, actual=actual_str, action="ok"))
            continue

        # coercion if enabled
        if coerce:
            try:
                coerced = _coerce_series(df_out[col], expected)
                # Replace the column
                df_out = df_out.with_columns(coerced.alias(col))
                new_dtype = df_out[col].dtype

                if _is_compatible(new_dtype, expected):
                    issues.append(DTypeIssue(column=col, expected=expected, actual=actual_str, action="coerced", note=str(new_dtype)))
                    continue
            except Exception as e:
                issues.append(DTypeIssue(column=col, expected=expected, actual=actual_str, action="mismatch", note=str(e)))
                continue

        issues.append(DTypeIssue(column=col, expected=expected, actual=actual_str, action="mismatch"))

    # If mode == warn: run won't fail but builds
    # If mode == error: fail if any mismatch/missing exists.
    dtype_failed = False
    if mode == "error":
        dtype_failed = any(i.action in {"mismatch", "missing"} for i in issues)

    return df_out, issues, dtype_failed
