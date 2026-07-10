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
