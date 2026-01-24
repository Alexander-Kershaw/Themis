from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

"""
-----------------------------------------------------------------------------------------------
Infering data contracts from datafram:
-----------------------------------------------------------------------------------------------

Data contract content is infered from an input dataset:

- dataset_name infered from file name

- primary_key (kept empty unless it is confidently infered)

- columns: infered dtype from polars dytypes, suggested required values (marked by 
a null threshold), min/max range (based on the data), allowed values, regex suggestions

- rules: non_null suggested for required rows

- severity: some sensible defaults (regex: warn, error for other elements)

-----------------------------------------------------------------------------------------------

Notes:

- Default null threshold for required columns = 0.0, therefore only columns with zero nulls
are considered required.

- allowed_values only when cardinality is small AND the column is sufficiently unique.

- Only obvious regex implementaion (4 uppercase letters).

- Primary keys are not guessed, if they are not obvious then its left empty.
-----------------------------------------------------------------------------------------------
"""

def _infer_dataset_name(path: Path) -> str:
    # filename without any extension
    return path.stem


def _polars_dtype_to_contract(dtype: pl.DataType) -> str:
    # A conservative dtype to contract definition
    if dtype == pl.Boolean:
        return "bool"
    if dtype in (pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64):
        return "int"
    if dtype in (pl.Float32, pl.Float64):
        return "float"
    if dtype in (pl.Date, pl.Datetime, pl.Time):
        return "datetime"
    return "string"


def _looks_like_datetime(s: pl.Series, min_parse_rate: float = 0.9, sample_n: int = 200) -> bool:

    if s.len() == 0:
        return False

    ss = s.drop_nulls()
    if ss.len() == 0:
        return False

    ss = ss.head(sample_n).cast(pl.Utf8)

    # parse timestamps; unparseable become null when strict=False
    parsed = ss.str.strptime(pl.Datetime, strict=False)

    ok = int(parsed.is_not_null().sum())
    rate = ok / float(ss.len())
    return rate >= min_parse_rate


def _maybe_regex_for_string(s: pl.Series) -> Optional[str]:

    try:
        vals = s.drop_nulls().cast(pl.Utf8)
    except Exception:
        return None
    if vals.len() == 0:
        return None

    # sample to avoid scanning huge columns
    sample = vals.head(200)

    # all match uppercase 4 letters
    ok = sample.str.contains(r"^[A-Z]{4}$").all()
    return r"^[A-Z]{4}$" if bool(ok) else None


def _should_be_required(null_frac: float, threshold: float) -> bool:
    # If <= threshold null fraction, call it required.
    return null_frac <= threshold


def infer_contract_from_df(
    df: pl.DataFrame,
    *,
    dataset_name: str,
    required_null_frac_threshold: float = 0.0,
    allowed_values_max_cardinality: int = 20,
    allowed_values_max_frac: float = 0.05,
    range_mode: str = "p01p99",  # "p01p99" | "minmax" | "none"
    suggest_allowed_values: bool = True,
    suggest_regex: bool = True,
    max_regex_sample: int = 200,
) -> Dict[str, Any]:
    
    total = df.height if df.height > 0 else 1

    columns: List[Dict[str, Any]] = []
    not_null_cols: List[str] = []

    for name, dtype in zip(df.columns, df.dtypes):
        s = df[name]

        nulls = int(s.null_count())
        null_frac = nulls / total

        dtype_str = _polars_dtype_to_contract(dtype)

        # Polars might see datetime as string, so try parsing to datetime
        if dtype_str == "string":
            try:
                if _looks_like_datetime(s):
                    dtype_str = "datetime"
            except Exception:
                pass

        c: Dict[str, Any] = {
            "name": name,
            "dtype": dtype_str,
        }

        required = _should_be_required(null_frac, required_null_frac_threshold)
        c["required"] = bool(required)

        if required:
            not_null_cols.append(name)

        # Range suggestions for numeric columns
        if c["dtype"] in {"int", "float"} and range_mode != "none":
            sn = s.drop_nulls()
            if sn.len() > 0:
                try:
                    if range_mode == "minmax":
                        c["min"] = float(sn.min())
                        c["max"] = float(sn.max())
                    
                    # Adaptive range infereance (small data -> wider quantiles, larger data -> more constricted quantiles)
                    elif range_mode == "p01p99":
                        n = sn.len()

                        # Tiny datasets: quantiles are too coarse so using trimmed bounds instead.
                        if n < 20:
                            vals = sorted([float(x) for x in sn.to_list()])
                            # trim one value from each tail
                            k = 1
                            if n > 2 * k:
                                c["suggested_min"] = float(vals[k])
                                c["suggested_max"] = float(vals[-k - 1])
                            else:
                                c["suggested_min"] = float(min(vals))
                                c["suggested_max"] = float(max(vals))

                        # Smallish datasets -> use wider quantiles
                        elif n < 100:
                            lo = sn.quantile(0.10, interpolation="linear")
                            hi = sn.quantile(0.90, interpolation="linear")
                            c["suggested_min"] = float(lo)
                            c["suggested_max"] = float(hi)

                        # Larger datasets -> robust quantiles
                        else:
                            lo = sn.quantile(0.01, interpolation="linear")
                            hi = sn.quantile(0.99, interpolation="linear")
                            c["suggested_min"] = float(lo)
                            c["suggested_max"] = float(hi)

                        pass
                except Exception:
                    pass


        # allowed_values suggestions 
        if suggest_allowed_values:
            # Avoid huge enumeration (only if cardinality is small)
            try:
                nunique = int(s.n_unique())
            except Exception:
                nunique = 0

            if 0 < nunique <= allowed_values_max_cardinality:
                # If the column is sufficiently low cardinality, suggest allowed values
                if (nunique / total) <= allowed_values_max_frac:
                    vals = s.drop_nulls().unique().to_list()
                    # Make sure they're YAML-friendly scalars
                    c["allowed_values"] = [v for v in vals]

        # regex suggestions
        if suggest_regex and c["dtype"] == "string":
            ss = s.drop_nulls()
            if ss.len() > 0:
                # sample
                ss = ss.head(max_regex_sample)
                rx = _maybe_regex_for_string(ss)
                if rx:
                    c["regex"] = rx

        columns.append(c)

    contract: Dict[str, Any] = {
        "dataset_name": dataset_name,
        "primary_key": [],
        "columns": columns,
        "rules": {
            "not_null": not_null_cols,
        },
        "severity": {
            "schema_required_columns": "error",
            "not_null": "error",
            "uniqueness": "error",
            "ranges": "error",
            "allowed_values": "error",
            "regex": "warn",
        },
    }

    return contract


def infer_contract_from_path(
    path: Path,
    *,
    required_null_frac_threshold: float = 0.0,
    **kwargs: Any,
) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Input not found: {path}")

    if path.suffix.lower() == ".csv":
        df = pl.read_csv(path)
    elif path.suffix.lower() == ".parquet":
        df = pl.read_parquet(path)
    else:
        raise ValueError("sample-contract supports .csv and .parquet")

    dataset_name = _infer_dataset_name(path)
    return infer_contract_from_df(
        df,
        dataset_name=dataset_name,
        required_null_frac_threshold=required_null_frac_threshold,
        **kwargs,
    )
