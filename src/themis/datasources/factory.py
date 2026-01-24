from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from themis.datasources.base import DataSource
from themis.datasources.files import FileDataSource
from themis.datasources.duckdb_source import from_duckdb_uri


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
        return from_duckdb_uri(input_str)

    raise ValueError(f"Unsupported input scheme: {scheme}")
