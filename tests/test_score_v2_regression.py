"""
Phase 12 regression guard: proves the config-driven engine reproduces the
exact totals of the pre-Phase-12 score.py output for the real dataset,
pinned via tests/fixtures/complexity_index_v2_totals_snapshot.csv (a
snapshot of complexity_index_v2.csv taken immediately before Phase 12
regenerated it with the new engine). This is the load-bearing check that
the refactor preserves behavior -- see
docs/superpowers/specs/2026-07-14-phase12-config-driven-scoring-engine-design.md
section 4, item 3.
"""

from pathlib import Path

import pandas as pd

from src.etl.rubric import load_rubric
from src.etl.score import build_score_table

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURES_PATH = REPO_ROOT / "data" / "processed" / "features" / "complexity_features.parquet"
SNAPSHOT_PATH = REPO_ROOT / "tests" / "fixtures" / "complexity_index_v2_totals_snapshot.csv"
RUBRIC_V2_PATH = REPO_ROOT / "config" / "rubric_v2.yaml"


def test_new_engine_reproduces_pre_phase12_v2_totals_exactly():
    features_df = pd.read_parquet(FEATURES_PATH)
    rubric = load_rubric(RUBRIC_V2_PATH)

    new_scores = build_score_table(features_df, rubric).set_index("id").sort_index()
    snapshot = pd.read_csv(SNAPSHOT_PATH).set_index("id").sort_index()

    for col in ["technical_score", "practical_score", "complexity_score"]:
        pd.testing.assert_series_equal(new_scores[col], snapshot[col], check_names=False)
