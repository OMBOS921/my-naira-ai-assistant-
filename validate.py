#!/usr/bin/env python3
"""
Validation Agent — development-only QA subsystem for Naira.

Usage:
    python validate.py                     # Run all validations
    python validate.py --quick             # Unit + Integration only
    python validate.py --coverage          # Includes coverage measurement
    python validate.py --leak              # Includes leak detection
    python validate.py --performance       # Includes performance profiling
    python validate.py --async-inspect     # Async static analysis only
    python validate.py --history           # Show validation history
    python validate.py --report            # Show last report
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from backend.validation import ValidationManager

_LOG = logging.getLogger("naira.validate")


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
    logging.getLogger("naira").setLevel(logging.INFO)
    for noisy in ("httpx", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


async def _run_validation(args: argparse.Namespace) -> int:
    mgr = ValidationManager(
        run_async_inspection=args.async_inspect or args.all,
        run_leak_detection=args.leak or args.all,
        run_performance=args.performance or args.all,
        run_coverage=args.coverage or args.all,
        run_regression=not args.quick,
    )
    report = await mgr.run_all()
    print()
    print(mgr.generate_report())
    return 0 if report.all_passed else 1


def _show_history() -> None:
    from backend.validation import ValidationHistory

    hist = ValidationHistory()
    runs = hist.get_recent_runs(20)
    if not runs:
        print("No validation history found.")
        return
    print(f"{'Run ID':<14} {'Status':<8} {'Passed':<8} {'Failed':<8} {'Duration':<10} {'Coverage':<8}")
    print("-" * 60)
    for r in runs:
        status = "PASS" if r["total_failed"] == 0 else "FAIL"
        cov = f"{r['coverage_pct']:.1f}%" if r.get("coverage_pct") else "N/A"
        print(
            f"{r['run_id']:<14} {status:<8} {r['total_passed']:<8} "
            f"{r['total_failed']:<8} {r['total_duration_s']:<10.1f} {cov:<8}"
        )
    hist.close()


def main() -> None:
    _setup_logging()
    parser = argparse.ArgumentParser(
        description="Naira Validation Agent (development only)"
    )
    parser.add_argument("--quick", action="store_true", help="Unit + Integration only")
    parser.add_argument("--coverage", action="store_true", help="Include coverage measurement")
    parser.add_argument("--leak", action="store_true", help="Include leak detection")
    parser.add_argument("--performance", action="store_true", help="Include performance profiling")
    parser.add_argument("--async-inspect", action="store_true", help="Async static analysis only")
    parser.add_argument("--history", action="store_true", help="Show validation history")
    parser.add_argument("--report", action="store_true", help="Show last report")
    parser.add_argument("--all", action="store_true", help="Run all checks including coverage, leak, performance")

    args = parser.parse_args()

    if args.history:
        _show_history()
        return

    if args.report:
        hist = ValidationManager().history
        runs = hist.get_recent_runs(1)
        if runs:
            print(f"Last run: {runs[0]}")
        else:
            print("No runs yet.")
        return

    exit_code = asyncio.run(_run_validation(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
