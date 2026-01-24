from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse, unquote

import duckdb
import polars as pl

from themis.datasources.base import DataSource


@dataclass(frozen=True)
class DuckDBDataSource(DataSource):
    db_path: str
    query: str

    def read(self) -> pl.DataFrame:
        con = duckdb.connect(self.db_path)
        try:
            rel = con.execute(self.query)
            # DuckDB export direct to polars
            return rel.pl()
        finally:
            con.close()


def from_duckdb_uri(uri: str) -> DuckDBDataSource:

    # Parse duckdb:// URI.
    parsed = urlparse(uri)
    if (parsed.scheme or "").lower() != "duckdb":
        raise ValueError("Not a duckdb URI")

    # Build db_path:
    # parsed.path includes a leading "/" (e.g. "/:memory:" or "/relative.db")
    raw_path = parsed.path or ""
    if raw_path.startswith("/"):
        raw_path = raw_path[1:]

    db_path = unquote(raw_path) if raw_path else ":memory:"
    if db_path == "":
        db_path = ":memory:"

    qs = parse_qs(parsed.query)
    query_vals = qs.get("query", [])
    if not query_vals or not query_vals[0].strip():
        raise ValueError("duckdb input requires ?query=...")

    query = unquote(query_vals[0])
    return DuckDBDataSource(db_path=db_path, query=query)
