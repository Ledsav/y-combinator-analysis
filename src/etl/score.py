"""
Scoring Module for Y Combinator Analysis
Phase 7: Convert Phase 6 raw complexity features into a 0-100 Complexity Index.

Strategy (see docs/superpowers/specs/2026-07-10-phase7-scoring-rubric-design.md):
- Each raw feature (or combination of features) is scaled via capped linear
  scaling: linear from 0 up to a cap, then clipped, then scaled to fill a
  fixed point budget. Caps come from the observed p95-p99 feature
  distribution, not the absolute max, so rare outliers don't waste the
  scale on a handful of companies.
- Technical (0-50): deep-tech tags (0-20) + description NLP score (0-15) +
  founder background (0-15, combining PhD count and research-institution
  experience since founder_phd_count alone is near-zero-variance).
- Practical (0-50): regulated industry (0-15) + market type (0-15) +
  geography & operations (0-20, combining international_operations and
  operational_intensity since there is no distinct "GTM complexity" signal
  in the Phase 6 feature set).
- All caps/weights/points are overridable default parameters, per the
  Phase 6 convention, so tests exercise the scaling logic independent of
  the exact curated values.
"""

from pathlib import Path

import pandas as pd


def compute_deep_tech_score(
    features_df: pd.DataFrame, cap: int = 3, points: float = 20
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
    features_df: pd.DataFrame, cap: int = 3, points: float = 15
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
    cap: float = 4,
    points: float = 15,
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
    features_df: pd.DataFrame, points: float = 15
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
    features_df: pd.DataFrame, points_per_level: float = 5
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
    intl_cap: int = 2,
    ops_cap: int = 2,
    intl_points: float = 10,
    ops_points: float = 10,
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
