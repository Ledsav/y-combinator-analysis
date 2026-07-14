"""
Phase 12: Combine-method registry — merges one or more raw feature columns
into a single pd.Series before a scaling method (src/etl/scaling.py)
scores it. Kept separate from scaling.py because "how raw signals merge"
and "how a merged value maps to points" are different concerns.
"""

from typing import Callable, Dict

import pandas as pd


def identity(features_df: pd.DataFrame, raw_feature: str) -> pd.Series:
    """Pass a single raw feature column through unchanged."""
    return features_df[raw_feature]


def weighted_sum(features_df: pd.DataFrame, features: Dict[str, float]) -> pd.Series:
    """
    Combine multiple raw feature columns into one weighted sum.

    Args:
        features_df: Feature table containing every column named in `features`.
        features: Maps column name -> weight applied before summing.

    Returns:
        pd.Series: sum of `features_df[col] * weight` for each entry in `features`.
    """
    total = None
    for col, weight in features.items():
        term = features_df[col] * weight
        total = term if total is None else total + term
    return total


COMBINE_METHODS: Dict[str, Callable] = {
    "identity": identity,
    "weighted_sum": weighted_sum,
}
