from __future__ import annotations

from abc import ABC, abstractmethod
import polars as pl

"""
Expanding engine-agnostic capabilities of Themis to duckDB

Here I define the arbitrary contract for any backend, this abstraction
allows the validator to be impartial to where data has come from (duckdb, csv, parquest)

"""

class DataSource(ABC):
    @abstractmethod
    def read(self) -> pl.DataFrame:
        raise NotImplementedError
