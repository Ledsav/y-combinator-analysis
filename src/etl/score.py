"""
Scoring Module for Y Combinator Analysis.
Phase 12: config-driven scoring engine -- builds a per-company score table
from a rubric config (config/rubric_v1.yaml, config/rubric_v2.yaml, ...)
instead of a hardcoded set of bucket functions. See
docs/superpowers/specs/2026-07-14-phase12-config-driven-scoring-engine-design.md
for the full architecture, and
docs/superpowers/specs/2026-07-10-phase7-scoring-rubric-design.md /
docs/superpowers/specs/2026-07-14-phase9.5-rubric-revision-design.md for
the original rubric design history now expressed as data in config/.

Each rubric bucket declares a raw feature (or a `combine` of several, via
src/etl/combine.py) and a scaling `method` (src/etl/scaling.py) that maps
the raw value into a [0, points] budget. build_score_table applies every
bucket, writes one <bucket_name>_score column per bucket, and sums bucket
scores by `dimension` into <dimension>_score totals (today: technical_score,
practical_score) plus complexity_score (the sum of all dimension totals).
"""

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from src.etl.combine import COMBINE_METHODS
from src.etl.rubric import load_rubric
from src.etl.scaling import SCALING_METHODS


def _resolve_raw(features_df: pd.DataFrame, bucket: Dict[str, Any]) -> pd.Series:
    """Resolve a bucket's raw (pre-scaling) value from features_df."""
    if "raw_feature" in bucket:
        return features_df[bucket["raw_feature"]]
    combine_fn = COMBINE_METHODS[bucket["combine"]]
    return combine_fn(features_df, **bucket["combine_params"])


def build_score_table(features_df: pd.DataFrame, rubric: Dict[str, Any]) -> pd.DataFrame:
    """
    Build the full per-company score table from a rubric config: compute
    each bucket's score independently, then sum bucket scores by
    `dimension` into dimension totals and complexity_score.

    Args:
        features_df: Phase 6 feature table (id, slug, name, batch, status,
            plus raw feature columns referenced by the rubric).
        rubric: A validated rubric dict (see src/etl/rubric.load_rubric).

    Returns:
        DataFrame with columns ['id', 'slug', 'name', 'batch', 'status'] +
        one '<bucket_name>_score' column per bucket + one '<dimension>_score'
        column per distinct dimension + 'complexity_score'.
    """
    scores = features_df[["id", "slug", "name", "batch", "status"]].copy()
    dimension_cols: Dict[str, List[str]] = {}

    for bucket in rubric["buckets"]:
        raw = _resolve_raw(features_df, bucket)
        method_fn = SCALING_METHODS[bucket["method"]]
        col = f"{bucket['name']}_score"
        scores[col] = method_fn(raw, **bucket["params"])
        dimension_cols.setdefault(bucket["dimension"], []).append(col)

    dimension_totals = []
    for dimension, cols in dimension_cols.items():
        total_col = f"{dimension}_score"
        scores[total_col] = scores[cols].sum(axis=1).round(1)
        dimension_totals.append(total_col)

    scores["complexity_score"] = scores[dimension_totals].sum(axis=1).round(1)

    return scores


def validate_scores(
    features_df: pd.DataFrame, scores_df: pd.DataFrame, rubric: Dict[str, Any]
) -> None:
    """
    Validate the score table before writing output. Bounds are derived
    from the rubric's per-bucket `points` budgets, not hardcoded, so a
    rubric that reallocates points stays self-consistent automatically.

    Args:
        features_df: The source feature table.
        scores_df: The built score table.
        rubric: The rubric used to build scores_df.
    """
    assert len(features_df) == len(scores_df), "Row count changed during scoring!"
    assert set(features_df["id"]) == set(scores_df["id"]), "Company id set changed!"

    dimension_budgets: Dict[str, float] = {}
    for bucket in rubric["buckets"]:
        dimension_budgets[bucket["dimension"]] = (
            dimension_budgets.get(bucket["dimension"], 0) + bucket["params"]["points"]
        )

    score_cols = [f"{dimension}_score" for dimension in dimension_budgets] + ["complexity_score"]
    for col in score_cols:
        assert scores_df[col].notna().all(), f"Missing values found in {col}!"

    for dimension, budget in dimension_budgets.items():
        col = f"{dimension}_score"
        assert scores_df[col].between(0, budget).all(), f"{col} must be within [0, {budget}]!"

    total_budget = sum(dimension_budgets.values())
    assert scores_df["complexity_score"].between(0, total_budget).all(), (
        f"complexity_score must be within [0, {total_budget}]!"
    )

    print("Validation passed: No scoring corruption detected")


def run_scoring_pipeline(
    input_path: Path = None,
    output_path: Path = None,
    rubric_config_path: Path = None,
) -> None:
    """
    Main scoring pipeline orchestrator.

    Args:
        input_path: Path to complexity_features.parquet.
        output_path: Path to write the complexity index CSV.
        rubric_config_path: Path to a rubric YAML (see src/etl/rubric.py).
            Defaults to config/rubric_v2.yaml -- the current rubric this
            module produces by default, never rubric_v1.yaml, which must
            stay the immutable historical Phase 7 baseline. Callers who
            need a specific version should pass rubric_config_path
            explicitly (scripts/run_complexity_pipeline.py always does,
            via --output-version / --rubric-config).
    """
    repo_root = Path(__file__).resolve().parents[2]

    if input_path is None:
        input_path = repo_root / "data" / "processed" / "features" / "complexity_features.parquet"
    if output_path is None:
        output_path = repo_root / "data" / "processed" / "scores" / "complexity_index_v2.csv"
    if rubric_config_path is None:
        rubric_config_path = repo_root / "config" / "rubric_v2.yaml"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("SCORING RUBRIC (Phase 12: config-driven)")
    print("=" * 60)

    print(f"\n[1/4] Loading rubric config from {rubric_config_path}...")
    rubric = load_rubric(rubric_config_path)

    print("\n[2/4] Loading feature table...")
    features_df = pd.read_parquet(input_path)

    print("\n[3/4] Building score table...")
    scores_df = build_score_table(features_df, rubric)

    print("\n[4/4] Validating and saving scores...")
    validate_scores(features_df, scores_df, rubric)
    scores_df.to_csv(output_path, index=False)
    print(f"  [OK] {output_path}")

    print("\n" + "=" * 60)
    print("SCORING COMPLETE")
    print("=" * 60)
    print(f"Companies: {len(scores_df)}")
    dimension_score_cols = sorted({f"{b['dimension']}_score" for b in rubric["buckets"]})
    print(scores_df[dimension_score_cols + ["complexity_score"]].describe())


if __name__ == "__main__":
    run_scoring_pipeline()
