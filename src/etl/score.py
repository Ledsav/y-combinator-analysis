"""
Scoring Module for Y Combinator Analysis
Phase 7: Convert Phase 6 raw complexity features into a 0-100 Complexity Index.
Phase 9.5: Weights revised from 50/50 to 30/70 technical/practical — see
docs/superpowers/specs/2026-07-14-phase9.5-rubric-revision-design.md.

Strategy (see docs/superpowers/specs/2026-07-10-phase7-scoring-rubric-design.md
for the original architecture, docs/superpowers/specs/2026-07-14-phase9.5-rubric-revision-design.md
for the Phase 9.5 weight revision):
- Each raw feature (or combination of features) is scaled via capped linear
  scaling: linear from 0 up to a cap, then clipped, then scaled to fill a
  fixed point budget. Caps come from the observed p95-p99 feature
  distribution, not the absolute max, so rare outliers don't waste the
  scale on a handful of companies.
- Technical (0-30): deep-tech tags (0-12) + description NLP score (0-9) +
  founder background (0-9, combining PhD count and research-institution
  experience since founder_phd_count alone is near-zero-variance).
- Practical (0-70): regulated industry (0-21) + market type (0-21) +
  geography & operations (0-28, combining international_operations and
  operational_intensity since there is no distinct "GTM complexity" signal
  in the Phase 6 feature set).
- The 30/70 split (was 50/50 through Phase 9) was revised in Phase 9.5:
  diagnostics showed the objectives doc's r>0.2 team-size-correlation and
  sigma>=15 spread targets were unreachable via reweighting alone while
  keeping technical and practical both meaningfully represented and the
  score bounded 0-100 — see the Phase 9.5 spec for the full investigation.
  This split is a real, verified improvement (sigma 10.11->11.95, r
  0.035->0.103) with both targets formally relaxed rather than fully met.
- All caps/weights/points are overridable default parameters, per the
  Phase 6 convention, so tests exercise the scaling logic independent of
  the exact curated values.
"""

from pathlib import Path
from typing import List

import pandas as pd


def compute_deep_tech_score(
    features_df: pd.DataFrame, cap: int = 2, points: float = 12
) -> pd.DataFrame:
    """
    Scale deep_tech_tag_count linearly to a 0-`points` budget, capped at
    `cap` tags (3+ tags = maximally deep-tech).

    Args:
        features_df: Feature table with an 'id' and 'deep_tech_tag_count' column.
        cap: Tag count at which the score maxes out.
        points: Point budget for this bucket.

    Returns:
        DataFrame with columns ['id', 'deep_tech_score'], one row per input row.
    """
    result = features_df[["id"]].copy()
    result["deep_tech_score"] = (
        features_df["deep_tech_tag_count"].clip(upper=cap) / cap * points
    )
    return result


def compute_description_score(
    features_df: pd.DataFrame, cap: int = 2, points: float = 9
) -> pd.DataFrame:
    """
    Scale description_tech_score (R&D-vocabulary keyword count) linearly to
    a 0-`points` budget, capped at `cap`.

    Args:
        features_df: Feature table with an 'id' and 'description_tech_score' column.
        cap: Score at which the bucket maxes out.
        points: Point budget for this bucket.

    Returns:
        DataFrame with columns ['id', 'description_score'], one row per input row.
    """
    result = features_df[["id"]].copy()
    result["description_score"] = (
        features_df["description_tech_score"].clip(upper=cap) / cap * points
    )
    return result


def compute_founder_background_score(
    features_df: pd.DataFrame,
    phd_weight: float = 2,
    cap: float = 2,
    points: float = 9,
) -> pd.DataFrame:
    """
    Combine founder_phd_count and research_company_experience into one
    founder-background signal (founder_phd_count alone is near-zero-variance
    in the real data, so its point budget would otherwise be wasted), scaled
    linearly to a 0-`points` budget capped at `cap`.

    Args:
        features_df: Feature table with 'id', 'founder_phd_count', and
            'research_company_experience' columns.
        phd_weight: Weight applied to founder_phd_count before summing with
            research_company_experience (PhD is a rarer, stronger signal).
        cap: Combined raw value at which the bucket maxes out.
        points: Point budget for this bucket.

    Returns:
        DataFrame with columns ['id', 'founder_background_score'], one row
        per input row.
    """
    result = features_df[["id"]].copy()
    raw = (
        phd_weight * features_df["founder_phd_count"]
        + features_df["research_company_experience"]
    )
    result["founder_background_score"] = raw.clip(upper=cap) / cap * points
    return result


def compute_regulated_score(
    features_df: pd.DataFrame, points: float = 21
) -> pd.DataFrame:
    """
    Score the regulated_industry binary flag as 0 or `points`.

    Args:
        features_df: Feature table with an 'id' and 'regulated_industry' column.
        points: Points awarded when regulated_industry == 1.

    Returns:
        DataFrame with columns ['id', 'regulated_score'], one row per input row.
    """
    result = features_df[["id"]].copy()
    result["regulated_score"] = features_df["regulated_industry"] * points
    return result


def compute_market_type_pts(
    features_df: pd.DataFrame, points_per_level: float = 7
) -> pd.DataFrame:
    """
    Score market_type_score (0-3 ordinal) linearly, `points_per_level` per level.

    Args:
        features_df: Feature table with an 'id' and 'market_type_score' column.
        points_per_level: Points awarded per market_type_score level.

    Returns:
        DataFrame with columns ['id', 'market_type_pts'], one row per input row.
    """
    result = features_df[["id"]].copy()
    result["market_type_pts"] = features_df["market_type_score"] * points_per_level
    return result


def compute_geo_ops_score(
    features_df: pd.DataFrame,
    intl_cap: int = 1,
    ops_cap: int = 1,
    intl_points: float = 14,
    ops_points: float = 14,
) -> pd.DataFrame:
    """
    Combine international_operations and operational_intensity into one
    geography-and-operations signal (no distinct "GTM complexity" feature
    exists in Phase 6's output). Each sub-feature is independently capped
    and linearly scaled to half of the bucket, then summed, so one
    dominant sub-feature can't drown out the other.

    Args:
        features_df: Feature table with 'id', 'international_operations',
            and 'operational_intensity' columns.
        intl_cap, ops_cap: Caps for each sub-feature.
        intl_points, ops_points: Point budgets for each sub-feature.

    Returns:
        DataFrame with columns ['id', 'geo_ops_score'], one row per input row.
    """
    result = features_df[["id"]].copy()
    intl_part = (
        features_df["international_operations"].clip(upper=intl_cap) / intl_cap * intl_points
    )
    ops_part = (
        features_df["operational_intensity"].clip(upper=ops_cap) / ops_cap * ops_points
    )
    result["geo_ops_score"] = intl_part + ops_part
    return result


SCORE_COLUMNS: List[str] = [
    "deep_tech_score",
    "description_score",
    "founder_background_score",
    "regulated_score",
    "market_type_pts",
    "geo_ops_score",
]


def build_score_table(features_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build the full per-company Phase 7 score table: compute each sub-bucket
    score independently, merge them onto the company identity columns, and
    sum into technical_score (0-50), practical_score (0-50), and
    complexity_score (0-100).

    Args:
        features_df: Phase 6 feature table (id, slug, name, batch, status,
            plus the 8 raw feature columns).

    Returns:
        DataFrame with columns ['id', 'slug', 'name', 'batch', 'status'] +
        SCORE_COLUMNS + ['technical_score', 'practical_score',
        'complexity_score'], one row per company in features_df.
    """
    scores = features_df[["id", "slug", "name", "batch", "status"]].copy()

    deep_tech = compute_deep_tech_score(features_df)
    description = compute_description_score(features_df)
    founder_bg = compute_founder_background_score(features_df)
    regulated = compute_regulated_score(features_df)
    market_type = compute_market_type_pts(features_df)
    geo_ops = compute_geo_ops_score(features_df)

    for part in (deep_tech, description, founder_bg, regulated, market_type, geo_ops):
        scores = scores.merge(part, on="id", how="left")

    scores["technical_score"] = (
        scores["deep_tech_score"] + scores["description_score"] + scores["founder_background_score"]
    ).round(1)
    scores["practical_score"] = (
        scores["regulated_score"] + scores["market_type_pts"] + scores["geo_ops_score"]
    ).round(1)
    scores["complexity_score"] = (scores["technical_score"] + scores["practical_score"]).round(1)

    return scores


def validate_scores(features_df: pd.DataFrame, scores_df: pd.DataFrame) -> None:
    """
    Validate the score table before writing output.

    Args:
        features_df: The source feature table.
        scores_df: The built score table.
    """
    assert len(features_df) == len(scores_df), "Row count changed during scoring!"
    assert set(features_df["id"]) == set(scores_df["id"]), "Company id set changed!"

    for col in ["technical_score", "practical_score", "complexity_score"]:
        assert scores_df[col].notna().all(), f"Missing values found in {col}!"

    # Bounds below must stay in sync with the technical/practical point
    # budgets set by compute_deep_tech_score/compute_description_score/
    # compute_founder_background_score (technical, sums to 30) and
    # compute_regulated_score/compute_market_type_pts/compute_geo_ops_score
    # (practical, sums to 70) — see the Phase 9.5 rubric revision spec.
    assert scores_df["technical_score"].between(0, 30).all(), (
        "technical_score must be within [0, 30]!"
    )
    assert scores_df["practical_score"].between(0, 70).all(), (
        "practical_score must be within [0, 70]!"
    )
    assert scores_df["complexity_score"].between(0, 100).all(), (
        "complexity_score must be within [0, 100]!"
    )

    print("Validation passed: No scoring corruption detected")


def run_scoring_pipeline(input_path: Path = None, output_path: Path = None) -> None:
    """
    Main scoring pipeline orchestrator.

    Args:
        input_path: Path to complexity_features.parquet.
        output_path: Path to write the complexity index CSV.
    """
    if input_path is None:
        input_path = (
            Path(__file__).resolve().parents[2]
            / "data" / "processed" / "features" / "complexity_features.parquet"
        )
    if output_path is None:
        output_path = (
            Path(__file__).resolve().parents[2]
            / "data" / "processed" / "scores" / "complexity_index_v1.csv"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("PHASE 7: SCORING RUBRIC")
    print("=" * 60)

    print("\n[1/3] Loading feature table...")
    features_df = pd.read_parquet(input_path)

    print("\n[2/3] Building score table...")
    scores_df = build_score_table(features_df)

    print("\n[3/3] Validating and saving scores...")
    validate_scores(features_df, scores_df)
    scores_df.to_csv(output_path, index=False)
    print(f"  [OK] {output_path}")

    print("\n" + "=" * 60)
    print("PHASE 7 COMPLETE")
    print("=" * 60)
    print(f"Companies: {len(scores_df)}")
    print(scores_df[["technical_score", "practical_score", "complexity_score"]].describe())


if __name__ == "__main__":
    run_scoring_pipeline()
