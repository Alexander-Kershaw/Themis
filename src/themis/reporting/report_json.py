from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict

import polars as pl

from themis.validate.results import ValidationRun


def write_json_report(
    run: ValidationRun,
    df_clean: pl.DataFrame,
    df_quarantine: pl.DataFrame,
    out_dir: Path,
    *,
    run_id: str,
    sample_fail_rows: int = 20,
) -> Path:
    """
    ------------------------------------------------------------------------------------------
    Writes a machine-readable JSON validation report.

    Parameters
    ------------------------------------------------------------------------------------------
    run:
        Validation run metadata (rule results, dataset name, etc.)
    df_clean:
        Rows that passed all ERROR-level rules.
    df_quarantine:
        Rows that failed one or more ERROR-level rules as defined by reasons vector logic.
    out_dir:
        Output directory for the validation run.
    run_id:
        UTC timestamp used to keep JSON/MD reports aligned for the same run.
    sample_fail_rows:
        Number of quarantined rows to include as examples in the report.
    
    ------------------------------------------------------------------------------------------
    """
    dataset = run.dataset_name

    reports_dir = out_dir / "reports" / dataset
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Basic column stats for non-numeric columns uses .describe()
    if df_clean.height > 0:
        stats = df_clean.select(pl.all()).describe().to_dict(as_series=False)
    else:
        stats = {}

    # Sample quarantined rows 
    if df_quarantine.height > 0:
        sample_bad = df_quarantine.head(sample_fail_rows).to_dict(as_series=False)
    else:
        sample_bad = {}

    payload: Dict[str, Any] = {
        "run_id": run_id,
        "dataset_name": dataset,
        "total_rows": run.total_rows,
        "clean_rows": df_clean.height,
        "quarantine_rows": df_quarantine.height,
        "error_failed": run.error_failed,
        "rule_results": [asdict(r) for r in run.rule_results],
        "sample_quarantine_rows": sample_bad,
        "clean_column_stats": stats,
    }

    path = reports_dir / f"{run_id}.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path
