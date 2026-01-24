from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from themis.datasources.base import DataSource
from themis.datasources.files import FileDataSource


def make_datasource(input_str: str) -> DataSource:
    """
    -------------------------------------------------------------------------------------------
    Builds a datasource from an input string.

    Supported inputs:
    - file paths (CSV/Parquet)
    - duckdb://... (added in Milestone A2)
    -------------------------------------------------------------------------------------------
    """
    parsed = urlparse(input_str)
    scheme = (parsed.scheme or "").lower()

    if scheme in ("", "file"):
        p = Path(input_str.replace("file://", ""))
        return FileDataSource(p)

    if scheme == "duckdb":
        # placeholder
        raise ValueError("DuckDB datasource not implemented yet")

    raise ValueError(f"Unsupported input scheme: {scheme}")
