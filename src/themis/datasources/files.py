from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl

from themis.datasources.base import DataSource

# Script to encapsulate current behaviour (in cli.py)

@dataclass(frozen=True)
class FileDataSource(DataSource):
    path: Path

    def read(self) -> pl.DataFrame:
        if not self.path.exists():
            raise FileNotFoundError(f"Input not found: {self.path}")

        suffix = self.path.suffix.lower()
        if suffix == ".csv":
            return pl.read_csv(self.path)
        if suffix == ".parquet":
            return pl.read_parquet(self.path)

        raise ValueError(f"Unsupported file type: {suffix} (supported: .csv, .parquet)")
