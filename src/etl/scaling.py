"""
Phase 12: Scaling-method registry for the config-driven scoring engine.

Each scaling method takes a raw pd.Series (already combined, if the
bucket combines multiple raw features via src/etl/combine.py) and returns
a pd.Series scaled into [0, points]. This bound is a hard contract:
src/etl/score.py's validate_scores() derives its technical/practical/
complexity_score bounds by summing each bucket's configured `points`, so
a method that doesn't honor [0, points] will only be caught by those
assertions, not by anything structural.
"""

from typing import Callable, Dict

import pandas as pd


def linear_capped(raw: pd.Series, cap: float, points: float) -> pd.Series:
    """
    Scale linearly from 0 up to `cap`, then clip, then scale to fill a
    0-`points` budget. Values above `cap` clip at `points`.

    Args:
        raw: Raw feature values (already combined, if applicable).
        cap: Raw value at which the bucket maxes out.
        points: Point budget this bucket scales into.

    Returns:
        pd.Series of values in [0, points].
    """
    return raw.clip(upper=cap) / cap * points


SCALING_METHODS: Dict[str, Callable] = {
    "linear_capped": linear_capped,
}
