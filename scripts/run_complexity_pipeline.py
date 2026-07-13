#!/usr/bin/env python3
"""
CLI entry point for the Phase 8 ETL pipeline orchestrator.

Usage:
  python scripts/run_complexity_pipeline.py --steps all --output-version v1
  python scripts/run_complexity_pipeline.py --steps clean,impute,features,score
"""
import argparse
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.etl.pipeline import STEP_ORDER, run_pipeline


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Y Combinator complexity index ETL pipeline."
    )
    parser.add_argument(
        "--steps",
        default="all",
        help=(
            f"Comma-separated step names ({', '.join(STEP_ORDER)}), or 'all' "
            f"(default: all steps except enrich)."
        ),
    )
    parser.add_argument(
        "--output-version",
        default="v1",
        help=(
            "Version suffix for the final complexity_index_<version>.csv "
            "filename (default: v1)."
        ),
    )
    return parser


def parse_steps_arg(steps_arg: str) -> List[str]:
    return [s.strip() for s in steps_arg.split(",") if s.strip()]


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    steps = parse_steps_arg(args.steps)

    try:
        run_pipeline(steps=steps, output_version=args.output_version)
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1

    print("Pipeline completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
