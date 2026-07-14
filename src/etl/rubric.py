"""
Phase 12: Rubric config loading & validation for the scoring engine
(src/etl/score.py). A rubric YAML (config/rubric_v1.yaml,
config/rubric_v2.yaml, ...) declares the list of scoring buckets that
src.etl.score.build_score_table consumes — see
docs/superpowers/specs/2026-07-14-phase12-config-driven-scoring-engine-design.md.
"""

from pathlib import Path
from typing import Any, Dict

import yaml

from src.etl.combine import COMBINE_METHODS
from src.etl.scaling import SCALING_METHODS


def validate_rubric(rubric: Dict[str, Any]) -> None:
    """
    Validate a parsed rubric dict before it reaches build_score_table.

    Args:
        rubric: Parsed rubric (must have a "buckets" list).

    Raises:
        ValueError: on any structural problem, identifying the offending
            bucket by name (or index, if unnamed).
    """
    buckets = rubric.get("buckets")
    if not buckets:
        raise ValueError("Rubric has no 'buckets' list")

    seen_names = set()
    for i, bucket in enumerate(buckets):
        label = bucket.get("name", f"#{i}")

        name = bucket.get("name")
        if not name:
            raise ValueError(f"Bucket {label} is missing required key 'name'")
        if name in seen_names:
            raise ValueError(f"Duplicate bucket name '{name}'")
        seen_names.add(name)

        if not bucket.get("dimension"):
            raise ValueError(f"Bucket '{name}' is missing required key 'dimension'")

        has_raw_feature = "raw_feature" in bucket
        has_combine = "combine" in bucket
        if has_raw_feature == has_combine:
            raise ValueError(
                f"Bucket '{name}' must set exactly one of 'raw_feature' or 'combine'"
            )
        if has_combine and bucket["combine"] not in COMBINE_METHODS:
            raise ValueError(
                f"Bucket '{name}' references unknown combine method '{bucket['combine']}'"
            )

        method = bucket.get("method")
        if method not in SCALING_METHODS:
            raise ValueError(f"Bucket '{name}' references unknown scaling method '{method}'")

        params = bucket.get("params")
        if not params or "points" not in params:
            raise ValueError(f"Bucket '{name}' params must include 'points'")


def load_rubric(path: Path) -> Dict[str, Any]:
    """
    Load and validate a rubric YAML file.

    Args:
        path: Path to a rubric YAML file (e.g. config/rubric_v2.yaml).

    Returns:
        The parsed, validated rubric dict.
    """
    with open(path, "r", encoding="utf-8") as f:
        rubric = yaml.safe_load(f)
    validate_rubric(rubric)
    return rubric
