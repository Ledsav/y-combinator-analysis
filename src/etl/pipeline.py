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
