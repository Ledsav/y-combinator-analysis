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
            f"(default: all steps except enrich). CAVEAT: 'features' always reads "
            f"its input from data/processed/step3_enriched/ (enrich's output "
            f"directory), never from step2_imputed/. Since 'all' excludes enrich, "
            f"a default run regenerates step1_cleaned/ and step2_imputed/ but then "
            f"'features' silently reads the stale, pre-existing step3_enriched/ "
            f"-- fresh clean/impute output does NOT propagate to the final "
            f"complexity_index CSV. To truly regenerate from raw data, "
            f"explicitly include enrich, e.g. --steps clean,impute,enrich,features,score."
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
    parser.add_argument(
        "--rubric-config",
        default=None,
        help=(
            "Path to a rubric YAML file overriding the score step's rubric "
            "(default: config/rubric_<output-version>.yaml)."
        ),
    )
    return parser


def parse_steps_arg(steps_arg: str) -> List[str]:
    return [s.strip() for s in steps_arg.split(",") if s.strip()]


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    steps = parse_steps_arg(args.steps)
    rubric_config_path = Path(args.rubric_config) if args.rubric_config else None

    try:
        run_pipeline(
            steps=steps,
            output_version=args.output_version,
            rubric_config_path=rubric_config_path,
        )
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1

    print("Pipeline completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
