from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import polars as pl

from themis.validate.results import ValidationRun

"""
-----------------------------------------------------------------------------------------------
This script generates a markdown file with:

- a run header (counts, error_failed)
- a rules table derived form contract
- sample of the quarantined rows
- basic stats using .describe() on the clean dataset

-----------------------------------------------------------------------------------------------
"""

def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _md_table(headers: List[str], rows: List[List[str]]) -> str:
    out = []
    out.append("| " + " | ".join(headers) + " |")
    out.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def write_markdown_report(
    run: ValidationRun,
    df_clean: pl.DataFrame,
    df_quarantine: pl.DataFrame,
    out_dir: Path,
    *,
    run_id: str | None = None,
    sample_fail_rows: int = 20,
) -> Path:
    run_id = run_id or _utc_run_id()
    dataset = run.dataset_name

    reports_dir = out_dir / "reports" / dataset
    reports_dir.mkdir(parents=True, exist_ok=True)

    total = run.total_rows
    clean_n = df_clean.height
    quar_n = df_quarantine.height

    # Rule results table
    rule_rows: List[List[str]] = []
    for rr in run.rule_results:
        rule_rows.append([
            rr.rule,
            rr.severity,
            "PASS" if rr.passed else "FAIL",
            str(rr.details),
        ])

    rules_table = _md_table(
        ["rule", "severity", "status", "details"],
        rule_rows
    )

    # Sample of failing rows 
    sample_md = ""
    if quar_n > 0:
        # Only using a small set of columns to avoid a wide markdown
        cols = df_quarantine.columns
        show_cols = cols[: min(len(cols), 8)]
        sample = df_quarantine.select(show_cols).head(sample_fail_rows)

        # Turn into markdown table
        sample_rows: List[List[str]] = []
        d = sample.to_dict(as_series=False)
        for i in range(sample.height):
            sample_rows.append([str(d[c][i]) for c in show_cols])

        sample_md = "\n\n### Sample quarantined rows (top {})\n\n{}".format(
            sample_fail_rows, _md_table(show_cols, sample_rows)
        )
    else:
        sample_md = "\n\n### Sample quarantined rows\n\nNone"

    # Simple column summary for clean
    stats_md = "\n\n### Clean dataset column summary\n\n"
    if clean_n == 0:
        stats_md += "No clean rows.\n"
    else:
        desc = df_clean.describe()
        # first 12 columns max for readibility
        show = desc.select(desc.columns[: min(len(desc.columns), 12)])
        # Represent as markdown table
        d = show.to_dict(as_series=False)
        headers = list(d.keys())
        rows = []
        for i in range(show.height):
            rows.append([str(d[h][i]) for h in headers])
        stats_md += _md_table(headers, rows)

    md = f"""# Themis Validation Report

- dataset: **{dataset}**
- run_id: **{run_id}**
- total_rows: **{total}**
- clean_rows: **{clean_n}**
- quarantine_rows: **{quar_n}**
- error_failed: **{run.error_failed}**

## Rule results

{rules_table}
{sample_md}
{stats_md}
"""

    path = reports_dir / f"{run_id}.md"
    path.write_text(md, encoding="utf-8")
    return path
