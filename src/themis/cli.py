from __future__ import annotations

import argparse
import sys
from pathlib import Path

import polars as pl

from themis.contracts.loader import load_contract
from themis.validate.validator import validate
from themis.quarantine.sink import write_outputs
from themis.reporting.report_json import write_json_report
from themis.reporting.report_md import write_markdown_report
from themis.contracts.infer_contract import infer_contract_from_path
from themis.contracts.contract_writer import write_contract_yaml
from datetime import datetime, timezone
from pathlib import Path


# Read input file (check if file exists, is csv/parquet, or unsupported format)
def _read_input(path: Path) -> pl.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Input not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pl.read_csv(path)
    if suffix == ".parquet":
        return pl.read_parquet(path)

    raise ValueError(f"Unsupported input format: {suffix} (expected .csv or .parquet)")

# 
def cmd_validate(args: argparse.Namespace) -> int:
    contract_path = Path(args.contract)
    input_path = Path(args.input)
    out_dir = Path(args.out)

    out_dir.mkdir(parents=True, exist_ok=True)

    contract = load_contract(contract_path)
    df = _read_input(input_path)

    run, df_clean, df_quarantine = validate(df, contract)
    write_outputs(df_clean, df_quarantine, out_dir)

    # Timestamp to align md and JSON reports for same run
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # Write JSON report
    report_path = write_json_report(run, df_clean, df_quarantine, out_dir, run_id=run_id)
    print(f"JSON report: {report_path}")

    # Write markdown report
    md_path = write_markdown_report(run, df_clean, df_quarantine, out_dir, run_id=run_id)
    print(f"MD report: {md_path}")

    summary = (
        f"Dataset: {run.dataset_name}\n"
        f"Total: {run.total_rows}\n"
        f"Clean: {df_clean.height}\n"
        f"Quarantine: {df_quarantine.height}\n"
        f"Error failed: {run.error_failed}\n"
    )
    (out_dir / "run_summary.txt").write_text(summary, encoding="utf-8")
    print(summary)

    # 2 if quaratine has rows else 0 (clean)
    return 2 if run.error_failed else 0

def cmd_sample_contract(args: argparse.Namespace) -> int:

    in_path = Path(args.from_data)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    contract = infer_contract_from_path(
        in_path,
        required_null_frac_threshold=float(args.required_null_threshold),
        range_mode=str(args.range_mode),
    )

    out_path = out_dir / f"{contract['dataset_name']}.yml"
    write_contract_yaml(contract, out_path)

    print(f"Generated contract: {out_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="themis", description="Themis: data contracts and quality gates")
    sub = p.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="Validate input data against a contract")
    v.add_argument("--contract", required=True, help="Path to contract YAML")
    v.add_argument("--input", required=True, help="Path to input CSV/Parquet")
    v.add_argument("--out", required=True, help="Output directory")
    v.set_defaults(func=cmd_validate)

    sc = sub.add_parser("sample-contract", help="Generate a starter contract YAML from data")
    sc.add_argument("--from-data", required=True, help="Path to input CSV/Parquet")
    sc.add_argument("--out", required=True, help="Output directory for generated contract")
    sc.add_argument("--required-null-threshold", type=float, default=0.0, help="Null fraction threshold for required columns (default: 0.0)")
    sc.add_argument("--range-mode", choices=["p01p99", "minmax", "none"], default="p01p99", help="How to suggest numeric ranges: p01p99 (default), minmax, or none")
    sc.set_defaults(func=cmd_sample_contract)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        rc = args.func(args)
        raise SystemExit(rc)
    except SystemExit:
        raise
    except Exception as e:
        print(f"[themis] runtime error: {e}", file=sys.stderr)
        raise SystemExit(1)
