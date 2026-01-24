from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import polars as pl

from themis.validate.results import ValidationRun

"""

------------------------------------------------------------------------------------------
Generate a timestamped run_id and creates an output directory for reports

The JSON payload contains the report summary:

- counts
- rule results
- sample of the failing rows
- some basic summary stats for the clean dataset
------------------------------------------------------------------------------------------

"""

def _utc_run_id() -> str:
    # Timestamp run_id (so its sortable)
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_json_report(
    run: ValidationRun,
    df_clean: pl.DataFrame,
    df_quarantine: pl.DataFrame,
    out_dir: Path,
    *,
    sample_fail_rows: int = 20,
) -> Path:
    run_id = _utc_run_id()
    dataset = run.dataset_name

    reports_dir = out_dir / "reports" / dataset
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Basic column stats
    # describe() is sufficient for a basic summary for non-numeric cols
    stats = df_clean.select(pl.all()).describe().to_dict(as_series=False) if df_clean.height > 0 else {}

    # Sample of rows that failed contract rules
    sample_bad = df_quarantine.head(sample_fail_rows).to_dict(as_series=False) if df_quarantine.height > 0 else {}

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
