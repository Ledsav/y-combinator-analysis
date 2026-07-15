"""
Phase 8: ETL Pipeline Orchestrator for Y Combinator Analysis

Sequences the existing Phase 3-7 step modules (clean, impute, enrich,
features, score) into one run, per
docs/superpowers/specs/2026-07-13-phase8-etl-pipeline-design.md.

No new data-processing logic lives here — this module only orders steps,
resolves their I/O paths, checks prerequisites, and validates the final
output end-to-end.
"""

from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from src.etl.clean import run_cleaning_pipeline
from src.etl.enrich import run_enrichment_pipeline
from src.etl.features import run_feature_engineering_pipeline
from src.etl.impute import run_imputation_pipeline
from src.etl.score import run_scoring_pipeline

STEP_ORDER: List[str] = ["clean", "impute", "enrich", "features", "score"]
DEFAULT_STEPS: List[str] = ["clean", "impute", "features", "score"]

PRODUCER_STEP: Dict[str, str] = {
    "impute": "clean",
    "enrich": "impute",
    "features": "enrich",
    "score": "features",
}


def normalize_steps(requested: Optional[List[str]]) -> List[str]:
    """
    Validate and canonically order a requested step list.

    Args:
        requested: List of step names, or None / ["all"] for DEFAULT_STEPS.

    Returns:
        Requested steps in STEP_ORDER order, deduplicated.
    """
    if requested is None or list(requested) == ["all"]:
        return list(DEFAULT_STEPS)

    unknown = set(requested) - set(STEP_ORDER)
    if unknown:
        raise ValueError(
            f"Unknown step(s): {sorted(unknown)}. Valid steps: {STEP_ORDER}"
        )

    requested_set = set(requested)
    return [step for step in STEP_ORDER if step in requested_set]


def _default_paths(data_root: Path, output_version: str) -> Dict[str, dict]:
    """
    Compute each step's required input (for prerequisite checks) and the
    kwargs to pass to its run_*_pipeline() function.

    Args:
        data_root: Root data directory (real project data/ or a tmp_path
            for tests).
        output_version: Version suffix for the final score CSV filename.

    Returns:
        Dict keyed by step name, each value {"required_input": Path,
        "kwargs": dict} where kwargs matches that step's own
        run_*_pipeline() parameter names.
    """
    raw_dir = data_root / "raw"
    processed_dir = data_root / "processed"
    step1_dir = processed_dir / "step1_cleaned"
    step2_dir = processed_dir / "step2_imputed"
    step3_dir = processed_dir / "step3_enriched"
    features_dir = processed_dir / "features"
    scores_dir = processed_dir / "scores"
    features_path = features_dir / "complexity_features.parquet"
    default_rubric_path = data_root.parent / "config" / f"rubric_{output_version}.yaml"

    return {
        "clean": {
            "required_input": raw_dir / "companies.csv",
            "kwargs": {"input_dir": raw_dir, "output_dir": step1_dir},
        },
        "impute": {
            "required_input": step1_dir / "companies_cleaned.csv",
            "kwargs": {"input_dir": step1_dir, "output_dir": step2_dir},
        },
        "enrich": {
            "required_input": step2_dir / "companies_imputed.csv",
            "kwargs": {"input_dir": step2_dir, "output_dir": step3_dir},
        },
        "features": {
            "required_input": step3_dir / "companies_enriched.csv",
            "kwargs": {"input_dir": step3_dir, "output_dir": features_dir},
        },
        "score": {
            "required_input": features_path,
            "kwargs": {
                "input_path": features_path,
                "output_path": scores_dir / f"complexity_index_{output_version}.csv",
                "rubric_config_path": default_rubric_path,
            },
        },
    }


def check_step_prerequisite(step: str, required_input: Path) -> None:
    """
    Raise FileNotFoundError with a clear message if a step's required input
    is missing from disk.

    Args:
        step: Step name (for the error message).
        required_input: Path that must exist before this step can run.
    """
    if required_input.exists():
        return

    producer = PRODUCER_STEP.get(step)
    if producer:
        raise FileNotFoundError(
            f"Cannot run '{step}': missing {required_input} — run '{producer}' first."
        )
    raise FileNotFoundError(
        f"Cannot run '{step}': missing {required_input} — "
        f"ensure raw data is present in data/raw/."
    )


def _run_clean_step(kwargs: dict) -> None:
    success, message = run_cleaning_pipeline(**kwargs)
    if not success:
        raise RuntimeError(message)


STEP_RUNNERS = {
    "clean": _run_clean_step,
    "impute": lambda kwargs: run_imputation_pipeline(**kwargs),
    "enrich": lambda kwargs: run_enrichment_pipeline(**kwargs),
    "features": lambda kwargs: run_feature_engineering_pipeline(**kwargs),
    "score": lambda kwargs: run_scoring_pipeline(**kwargs),
}


def validate_pipeline_output(output_path: Path, reference_input_path: Path) -> None:
    """
    End-to-end validation of the final score CSV, on top of each step's own
    internal validate_* checks. Compares row count against
    reference_input_path — the required input of the first step that
    actually ran in this invocation — to catch cross-step row-loss bugs
    that no single step's own validation would see.

    Args:
        output_path: Path to the written complexity_index_*.csv.
        reference_input_path: CSV or parquet file whose row count the
            output should match.
    """
    assert output_path.exists(), f"Pipeline output not found at {output_path}"

    scores_df = pd.read_csv(output_path)
    if reference_input_path.suffix == ".parquet":
        reference_df = pd.read_parquet(reference_input_path)
    else:
        reference_df = pd.read_csv(reference_input_path)

    assert len(scores_df) == len(reference_df), (
        f"Row count mismatch: {len(scores_df)} scores vs "
        f"{len(reference_df)} rows in {reference_input_path}"
    )
    assert scores_df["complexity_score"].notna().all(), "Null complexity_score values found!"
    assert scores_df["complexity_score"].between(0, 100).all(), (
        "complexity_score must be within [0, 100]!"
    )

    print(f"Pipeline validation passed: {len(scores_df)} companies scored")


def run_pipeline(
    steps: Optional[List[str]] = None,
    output_version: str = "v1",
    data_root: Optional[Path] = None,
    rubric_config_path: Optional[Path] = None,
) -> None:
    """
    Run the requested ETL steps in canonical order.

    Args:
        steps: Step names to run, or None/["all"] for DEFAULT_STEPS
            (clean, impute, features, score — enrich is opt-in).
        output_version: Version suffix for the final score CSV filename.
        data_root: Root data directory. Defaults to the real project's
            data/ directory; overridden in tests to isolate I/O. Not
            exposed via the CLI.
        rubric_config_path: Explicit override for the score step's rubric
            config file. Defaults to <repo_root>/config/rubric_<output_version>.yaml
            (derived from data_root's parent) when not given. Exposed via
            the CLI's --rubric-config flag.
    """
    resolved_steps = normalize_steps(steps)

    if data_root is None:
        data_root = Path(__file__).resolve().parents[2] / "data"

    paths = _default_paths(data_root, output_version)
    if rubric_config_path is not None:
        paths["score"]["kwargs"]["rubric_config_path"] = rubric_config_path

    for step in resolved_steps:
        check_step_prerequisite(step, paths[step]["required_input"])
        print(f"\n{'#' * 60}")
        print(f"PIPELINE STEP: {step}")
        print(f"{'#' * 60}")
        STEP_RUNNERS[step](paths[step]["kwargs"])

    if "score" in resolved_steps:
        first_step = resolved_steps[0]
        validate_pipeline_output(
            output_path=paths["score"]["kwargs"]["output_path"],
            reference_input_path=paths[first_step]["required_input"],
        )
