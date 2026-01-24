from __future__ import annotations

from pathlib import Path
import polars as pl

"""
-------------------------------------------------------------------------------------------

write_outputs creates the necessary output folders, writing both clean and quarantined
datasets as parquet, standardising format for downstream pipelines

-------------------------------------------------------------------------------------------
"""

def write_outputs(df_clean: pl.DataFrame, df_quarantine: pl.DataFrame, out_dir: Path) -> None:
    clean_dir = out_dir / "clean"
    quar_dir = out_dir / "quarantine"
    clean_dir.mkdir(parents=True, exist_ok=True)
    quar_dir.mkdir(parents=True, exist_ok=True)

    df_clean.write_parquet(clean_dir / "data.parquet")
    df_quarantine.write_parquet(quar_dir / "data.parquet")
