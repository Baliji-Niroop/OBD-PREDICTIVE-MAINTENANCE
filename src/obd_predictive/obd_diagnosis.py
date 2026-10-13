"""Command-line entry point for the OBD-II predictive maintenance dashboard."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import sys

import pandas as pd

from .obd_analysis import analyze_log, build_report
from .obd_dashboard import render_dashboard


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze OBD-II CSV logs and create a health dashboard and plain-language report."
    )
    parser.add_argument("csv_files", nargs="+", type=Path, help="CSV log paths, supplied oldest first")
    parser.add_argument("--interval-days", type=float, help="Days between sequential logs; enables dated trend projections")
    project_root = Path(__file__).resolve().parents[2]
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_root / "output",
        help=f"Output folder (default: {project_root / 'output'})",
    )
    args = parser.parse_args()
    if args.interval_days is not None and (not math.isfinite(args.interval_days) or args.interval_days <= 0):
        parser.error("--interval-days must be a finite number greater than zero.")
    return args


def main() -> int:
    args = parse_args()
    logs = []
    failures = []
    for path in args.csv_files:
        if not path.is_file():
            failures.append(f"{path}: file does not exist or is not a file")
            continue
        try:
            log = analyze_log(path)
        except (OSError, UnicodeError, pd.errors.ParserError, ValueError) as error:
            failures.append(f"{path}: {error}")
            continue
        logs.append(log)
    if not logs:
        print("Error: no input CSV could be analyzed.", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "report.txt"
    dashboard_path = args.output_dir / "dashboard.png"
    report_path.write_text(build_report(logs, failures, args.interval_days), encoding="utf-8")
    render_dashboard(logs[-1], dashboard_path)
    print(f"Analyzed {len(logs)} log(s); latest: {logs[-1].path}")
    for failure in failures:
        print(f"Skipped input: {failure}", file=sys.stderr)
    print(f"Report: {report_path.resolve()}")
    print(f"Dashboard: {dashboard_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
