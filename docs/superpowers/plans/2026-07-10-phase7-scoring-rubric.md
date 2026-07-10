# Phase 7 Scoring Rubric Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `src/etl/score.py`, a Phase 7 scoring module that converts the 8 raw features in `data/processed/features/complexity_features.parquet` into a 0-100 Complexity Index (Technical 0-50 + Practical 0-50) via capped linear scaling, and a companion `notebooks/score_design.ipynb` for calibration analysis.

**Architecture:** Pure, independently-testable `compute_*_score` functions (one per point bucket, cap/weight as overridable default parameters) — mirroring `src/etl/features.py` — merged by an orchestrator (`build_score_table`); a `validate_scores` assertion function; a pipeline entry point (`run_scoring_pipeline`) writing `data/processed/scores/complexity_index_v1.csv`; and a calibration notebook built via a small reproducible generator script (no scoring logic duplicated in the notebook — it only imports and analyzes `src/etl/score.py`).

**Tech Stack:** Python stdlib (`json`, `pathlib`) + `pandas` (already a dependency, no new dependencies needed).

## Global Constraints

- This is scoring only — no new feature extraction. All inputs come from the existing `data/processed/features/complexity_features.parquet` columns: `id, slug, name, batch, status, deep_tech_tag_count, description_tech_score, founder_phd_count, research_company_experience, regulated_industry, market_type_score, international_operations, operational_intensity`.
- Formula (from `docs/superpowers/specs/2026-07-10-phase7-scoring-rubric-design.md`):
  - `deep_tech_score = min(deep_tech_tag_count, 3) / 3 * 20`
  - `description_score = min(description_tech_score, 3) / 3 * 15`
  - `founder_background_score = min(2*founder_phd_count + research_company_experience, 4) / 4 * 15`
  - `technical_score = deep_tech_score + description_score + founder_background_score` (0-50)
  - `regulated_score = regulated_industry * 15`
  - `market_type_pts = market_type_score * 5`
  - `geo_ops_score = min(international_operations, 2)/2*10 + min(operational_intensity, 2)/2*10`
  - `practical_score = regulated_score + market_type_pts + geo_ops_score` (0-50)
  - `complexity_score = technical_score + practical_score` (0-100)
- Every `compute_*_score` function returns a row for **every** input company (never filtered/absent), unlike Phase 6's "absent = 0" convention — a score of 0 is a real value, not a missing one.
- `technical_score`, `practical_score`, `complexity_score` are rounded to 1 decimal place in the final table. Sub-bucket scores (`deep_tech_score`, etc.) are left unrounded.
- No missing values anywhere in the output — every company gets a score.
- Output CSV path: `data/processed/scores/complexity_index_v1.csv` (per the roadmap's existing date/version-stamping convention — `v1` here, not a date, matching the roadmap's own example `complexity_index_v1.csv`).

---

## Task 1: Test setup + technical score functions

**Files:**
- Create: `tests/test_score.py`
- Create: `src/etl/score.py`

**Interfaces:**
- Produces:
  - `compute_deep_tech_score(features_df: pd.DataFrame, cap: int = 3, points: float = 20) -> pd.DataFrame` — columns `['id', 'deep_tech_score']`, one row per input row
  - `compute_description_score(features_df: pd.DataFrame, cap: int = 3, points: float = 15) -> pd.DataFrame` — columns `['id', 'description_score']`, one row per input row
  - `compute_founder_background_score(features_df: pd.DataFrame, phd_weight: float = 2, cap: float = 4, points: float = 15) -> pd.DataFrame` — columns `['id', 'founder_background_score']`, one row per input row

- [ ] **Step 1: Write the failing tests**

Create `tests/test_score.py`:

```python
import pytest
import pandas as pd

from src.etl.score import (
    compute_deep_tech_score,
    compute_description_score,
    compute_founder_background_score,
)


def test_compute_deep_tech_score_scales_linearly_up_to_cap():
    features_df = pd.DataFrame({"id": [1, 2, 3, 4], "deep_tech_tag_count": [0, 1, 3, 5]})

    result = compute_deep_tech_score(features_df, cap=3, points=20)

    scores = dict(zip(result["id"], result["deep_tech_score"]))
    assert scores[1] == 0
    assert scores[2] == pytest.approx(20 / 3)
    assert scores[3] == 20
    assert scores[4] == 20  # clipped above cap


def test_compute_deep_tech_score_returns_one_row_per_company():
    features_df = pd.DataFrame({"id": [1, 2], "deep_tech_tag_count": [0, 0]})

    result = compute_deep_tech_score(features_df)

    assert len(result) == 2
    assert set(result["id"]) == {1, 2}


def test_compute_description_score_scales_linearly_up_to_cap():
    features_df = pd.DataFrame({"id": [1, 2, 3], "description_tech_score": [0, 3, 10]})

    result = compute_description_score(features_df, cap=3, points=15)

    scores = dict(zip(result["id"], result["description_score"]))
    assert scores[1] == 0
    assert scores[2] == 15
    assert scores[3] == 15  # clipped above cap


def test_compute_founder_background_score_weights_phd_and_research():
    features_df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "founder_phd_count": [0, 1, 0],
            "research_company_experience": [0, 0, 4],
        }
    )

    result = compute_founder_background_score(features_df, phd_weight=2, cap=4, points=15)

    scores = dict(zip(result["id"], result["founder_background_score"]))
    assert scores[1] == 0
    assert scores[2] == pytest.approx(7.5)  # raw = 2*1 = 2 -> 2/4*15
    assert scores[3] == 15  # raw = 4, at cap
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_score.py -v`
Expected: `ModuleNotFoundError: No module named 'src.etl.score'`

- [ ] **Step 3: Implement `src/etl/score.py` (technical score functions)**

Create `src/etl/score.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_score.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add tests/test_score.py src/etl/score.py
git commit -m "feat: add Phase 7 technical score functions"
```

---

## Task 2: Practical score functions

**Files:**
- Modify: `src/etl/score.py`
- Modify: `tests/test_score.py`

**Interfaces:**
- Produces:
  - `compute_regulated_score(features_df: pd.DataFrame, points: float = 15) -> pd.DataFrame` — columns `['id', 'regulated_score']`, one row per input row
  - `compute_market_type_pts(features_df: pd.DataFrame, points_per_level: float = 5) -> pd.DataFrame` — columns `['id', 'market_type_pts']`, one row per input row
  - `compute_geo_ops_score(features_df: pd.DataFrame, intl_cap: int = 2, ops_cap: int = 2, intl_points: float = 10, ops_points: float = 10) -> pd.DataFrame` — columns `['id', 'geo_ops_score']`, one row per input row

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_score.py`:

```python
from src.etl.score import (
    compute_geo_ops_score,
    compute_market_type_pts,
    compute_regulated_score,
)


def test_compute_regulated_score_multiplies_binary_flag():
    features_df = pd.DataFrame({"id": [1, 2], "regulated_industry": [0, 1]})

    result = compute_regulated_score(features_df, points=15)

    scores = dict(zip(result["id"], result["regulated_score"]))
    assert scores == {1: 0, 2: 15}


def test_compute_market_type_pts_scales_ordinal():
    features_df = pd.DataFrame({"id": [1, 2, 3, 4], "market_type_score": [0, 1, 2, 3]})

    result = compute_market_type_pts(features_df, points_per_level=5)

    scores = dict(zip(result["id"], result["market_type_pts"]))
    assert scores == {1: 0, 2: 5, 3: 10, 4: 15}


def test_compute_geo_ops_score_sums_independently_capped_sub_scores():
    features_df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "international_operations": [0, 1, 5],
            "operational_intensity": [0, 2, 0],
        }
    )

    result = compute_geo_ops_score(
        features_df, intl_cap=2, ops_cap=2, intl_points=10, ops_points=10
    )

    scores = dict(zip(result["id"], result["geo_ops_score"]))
    assert scores[1] == 0
    assert scores[2] == 15  # intl: 1/2*10=5, ops: 2/2*10=10
    assert scores[3] == 10  # intl clipped: 2/2*10=10, ops: 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_score.py -v`
Expected: `ImportError: cannot import name 'compute_regulated_score'`

- [ ] **Step 3: Implement the practical score functions**

Add to `src/etl/score.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_score.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/etl/score.py tests/test_score.py
git commit -m "feat: add Phase 7 practical score functions"
```

---

## Task 3: Score table orchestrator + validation

**Files:**
- Modify: `src/etl/score.py`
- Modify: `tests/test_score.py`

**Interfaces:**
- Consumes: all `compute_*_score` functions from Tasks 1-2
- Produces:
  - `SCORE_COLUMNS: List[str]` (module constant, the 6 sub-bucket score column names)
  - `build_score_table(features_df: pd.DataFrame) -> pd.DataFrame` — columns `['id', 'slug', 'name', 'batch', 'status'] + SCORE_COLUMNS + ['technical_score', 'practical_score', 'complexity_score']`, one row per company in `features_df`
  - `validate_scores(features_df: pd.DataFrame, scores_df: pd.DataFrame) -> None` — raises `AssertionError` on row-count/id-set mismatch, missing values, or out-of-range scores; prints a success message otherwise

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_score.py`:

```python
from src.etl.score import build_score_table, validate_scores


def _minimal_score_inputs():
    return pd.DataFrame(
        {
            "id": [1, 2],
            "slug": ["acme", "beta"],
            "name": ["Acme", "Beta"],
            "batch": ["W24", "S23"],
            "status": ["Active", "Active"],
            "deep_tech_tag_count": [3, 0],
            "description_tech_score": [3, 0],
            "founder_phd_count": [1, 0],
            "research_company_experience": [2, 0],
            "regulated_industry": [1, 0],
            "market_type_score": [3, 0],
            "international_operations": [2, 0],
            "operational_intensity": [2, 0],
        }
    )


def test_build_score_table_has_one_row_per_company():
    features_df = _minimal_score_inputs()

    scores_df = build_score_table(features_df)

    assert len(scores_df) == 2
    assert set(scores_df["id"]) == {1, 2}


def test_build_score_table_computes_expected_values_for_acme_and_beta():
    features_df = _minimal_score_inputs()

    scores_df = build_score_table(features_df)

    acme = scores_df[scores_df["slug"] == "acme"].iloc[0]
    assert acme["technical_score"] == 50  # 20 + 15 + 15 (all buckets at cap)
    assert acme["practical_score"] == 50  # 15 + 15 + 20 (all buckets at cap)
    assert acme["complexity_score"] == 100

    beta = scores_df[scores_df["slug"] == "beta"].iloc[0]
    assert beta["technical_score"] == 0
    assert beta["practical_score"] == 0
    assert beta["complexity_score"] == 0


def test_validate_scores_passes_on_valid_table():
    features_df = _minimal_score_inputs()
    scores_df = build_score_table(features_df)

    validate_scores(features_df, scores_df)  # should not raise


def test_validate_scores_raises_on_row_count_mismatch():
    features_df = pd.DataFrame({"id": [1, 2]})
    scores_df = pd.DataFrame(
        {"id": [1], "technical_score": [10.0], "practical_score": [10.0], "complexity_score": [20.0]}
    )

    with pytest.raises(AssertionError, match="Row count"):
        validate_scores(features_df, scores_df)


def test_validate_scores_raises_on_out_of_range_score():
    features_df = pd.DataFrame({"id": [1]})
    scores_df = pd.DataFrame(
        {"id": [1], "technical_score": [60.0], "practical_score": [10.0], "complexity_score": [70.0]}
    )

    with pytest.raises(AssertionError, match="technical_score"):
        validate_scores(features_df, scores_df)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_score.py -v`
Expected: `ImportError: cannot import name 'build_score_table'`

- [ ] **Step 3: Implement `build_score_table` and `validate_scores`**

Add to `src/etl/score.py`:

```python
from typing import List

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

    assert scores_df["technical_score"].between(0, 50).all(), (
        "technical_score must be within [0, 50]!"
    )
    assert scores_df["practical_score"].between(0, 50).all(), (
        "practical_score must be within [0, 50]!"
    )
    assert scores_df["complexity_score"].between(0, 100).all(), (
        "complexity_score must be within [0, 100]!"
    )

    print("Validation passed: No scoring corruption detected")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_score.py -v`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add src/etl/score.py tests/test_score.py
git commit -m "feat: add Phase 7 score table orchestrator and validation"
```

---

## Task 4: Pipeline orchestrator + real run + roadmap updates

**Files:**
- Modify: `src/etl/score.py`
- Modify: `tests/test_score.py`
- Modify: `documentation/plan_complexity_metric/roadmap.md`
- Modify: `documentation/plan/roadmap_todo.md`
- Create (generated by running the pipeline, not hand-written): `data/processed/scores/complexity_index_v1.csv`

**Interfaces:**
- Consumes: `build_score_table`, `validate_scores` (Task 3)
- Produces: `run_scoring_pipeline(input_path: Path = None, output_path: Path = None) -> None`

- [ ] **Step 1: Write the failing integration test**

Append to `tests/test_score.py`:

```python
from src.etl.score import run_scoring_pipeline


def test_run_scoring_pipeline_end_to_end(tmp_path):
    input_path = tmp_path / "complexity_features.parquet"
    output_path = tmp_path / "scores" / "complexity_index_v1.csv"

    features_df = _minimal_score_inputs()
    features_df.to_parquet(input_path, index=False)

    run_scoring_pipeline(input_path=input_path, output_path=output_path)

    scores_df = pd.read_csv(output_path)
    assert len(scores_df) == 2
    acme = scores_df[scores_df["slug"] == "acme"].iloc[0]
    assert acme["complexity_score"] == 100
    beta = scores_df[scores_df["slug"] == "beta"].iloc[0]
    assert beta["complexity_score"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_score.py -v`
Expected: `ImportError: cannot import name 'run_scoring_pipeline'`

- [ ] **Step 3: Implement `run_scoring_pipeline`**

Add to `src/etl/score.py`:

```python
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
    print(f"  ✓ {output_path}")

    print("\n" + "=" * 60)
    print("PHASE 7 COMPLETE")
    print("=" * 60)
    print(f"Companies: {len(scores_df)}")
    print(scores_df[["technical_score", "practical_score", "complexity_score"]].describe())


if __name__ == "__main__":
    run_scoring_pipeline()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_score.py -v`
Expected: 14 passed

- [ ] **Step 5: Commit**

```bash
git add src/etl/score.py tests/test_score.py
git commit -m "feat: add Phase 7 scoring pipeline orchestrator"
```

- [ ] **Step 6: Run the full test suite once more before the real run**

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: all tests pass (Phase 5 `test_enrich.py` + Phase 6 `test_features.py` + Phase 7 `test_score.py`)

- [ ] **Step 7: Run the pipeline for real**

Run: `./.venv/Scripts/python.exe -m src.etl.score`

Expected: Console output showing `PHASE 7: SCORING RUBRIC`, then `PHASE 7 COMPLETE` with a `describe()` table for all 4,844 companies.

- [ ] **Step 8: Sanity-check the output**

Run:
```bash
./.venv/Scripts/python.exe -c "
import pandas as pd
df = pd.read_csv('data/processed/scores/complexity_index_v1.csv')
print(df.shape)
print(df.isna().sum())
print(df[['technical_score','practical_score','complexity_score']].describe())
print(df.sort_values('complexity_score', ascending=False)[['name','technical_score','practical_score','complexity_score']].head(10))
"
```

Confirm: 4,844 rows, zero NaNs, `technical_score` within [0,50], `practical_score` within [0,50], `complexity_score` within [0,100], and the top-scoring companies by name are recognizably complex (deep-tech + regulated/B2B).

- [ ] **Step 9: Update `documentation/plan_complexity_metric/roadmap.md`**

Change the checklist item 7 block:
```markdown
- [x] **7. Scoring rubric design**
  - [x] Design interpretable weighted rubric
  - [x] Calibrate weights with example companies
  - [x] Run sensitivity analysis
  - [x] Output: `notebooks/score_design.ipynb`
```

Update the timeline table row:
```markdown
| 7. Scoring | 1-2 days | ✅ Complete |
```
and the total-complete percentage to `70% complete`.

Update "Next Immediate Actions":
```markdown
## Next Immediate Actions

**Current Focus:** Phase 8 - ETL Pipeline Implementation

**Next Steps:**
1. Create modular ETL scripts in `src/etl/` (clean.py, impute.py, enrich.py, features.py, score.py already exist — this phase wires them into one orchestrator)
2. Build a CLI runner (`scripts/run_complexity_pipeline.py`) with `--steps` and `--output-version` flags per the roadmap's Phase 8 spec
3. Add automated validation checks across the full pipeline run
4. Output: Complete pipeline + `complexity_index_v1.csv` regenerated end-to-end from raw data

**To continue:** Mark this task complete and proceed to implementation.
```

- [ ] **Step 10: Update `documentation/plan/roadmap_todo.md`**

```markdown
- [x] 7. Design scoring rubric
```

- [ ] **Step 11: Commit**

```bash
git add documentation/plan_complexity_metric/roadmap.md documentation/plan/roadmap_todo.md
git add data/processed/scores/complexity_index_v1.csv
git commit -m "feat: complete Phase 7 scoring - generate complexity index for all companies"
```

---

## Task 5: Calibration notebook (`notebooks/score_design.ipynb`)

**Files:**
- Create: `scripts/generate_score_design_notebook.py`
- Create (generated by running the script, not hand-written): `notebooks/score_design.ipynb`

**Interfaces:**
- Consumes: `src.etl.score` (`build_score_table`), `data/processed/features/complexity_features.parquet`, `data/processed/step3_enriched/companies_enriched.csv` (for `teamSize`)
- Produces: `notebooks/score_design.ipynb` — a Jupyter notebook with no scoring logic of its own (only analysis/plots), generated reproducibly by a script (no `nbformat` dependency needed — `.ipynb` is plain JSON)

- [ ] **Step 1: Write the notebook generator script**

Create `scripts/generate_score_design_notebook.py`:

```python
"""
Generates notebooks/score_design.ipynb for Phase 7 calibration analysis.

Run: ./.venv/Scripts/python.exe scripts/generate_score_design_notebook.py

Regenerate this way (not by hand-editing the .ipynb) whenever a cell needs
to change, so the notebook stays reproducible from source.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "notebooks" / "score_design.ipynb"


def markdown_cell(text: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": text.splitlines(keepends=True),
    }


def code_cell(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text.splitlines(keepends=True),
    }


CELLS = [
    markdown_cell(
        "# Phase 7 Score Design & Calibration\n"
        "\n"
        "Analysis-only notebook: imports the scoring logic from "
        "`src/etl/score.py` (no logic is duplicated here). Covers "
        "distribution, spot-checks, correlation with team size, a "
        "sensitivity pass, and manual top/bottom review, per "
        "`docs/superpowers/specs/2026-07-10-phase7-scoring-rubric-design.md`."
    ),
    code_cell(
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "import numpy as np\n"
        "import pandas as pd\n"
        "\n"
        "REPO_ROOT = Path.cwd().parent if Path.cwd().name == \"notebooks\" else Path.cwd()\n"
        "sys.path.insert(0, str(REPO_ROOT))\n"
        "\n"
        "from src.etl.score import build_score_table\n"
        "\n"
        "features_df = pd.read_parquet(REPO_ROOT / \"data\" / \"processed\" / \"features\" / \"complexity_features.parquet\")\n"
        "scores_df = build_score_table(features_df)\n"
        "scores_df.shape"
    ),
    markdown_cell("## 1. Distribution"),
    code_cell(
        "scores_df[\"complexity_score\"].plot(kind=\"hist\", bins=30, title=\"Complexity Score Distribution\")"
    ),
    code_cell(
        "scores_df.plot(kind=\"scatter\", x=\"technical_score\", y=\"practical_score\", alpha=0.3, title=\"Technical vs Practical\")"
    ),
    markdown_cell(
        "## 2. Spot-check known companies\n"
        "\n"
        "`polymath-robotics` and `andromeda-surgical` are deep-tech/hard-science "
        "(expect high `technical_score`); `gusto` is regulated B2B fintech/payroll "
        "(expect high `practical_score`)."
    ),
    code_cell(
        "spot_check_slugs = [\"polymath-robotics\", \"andromeda-surgical\", \"gusto\"]\n"
        "scores_df[scores_df[\"slug\"].isin(spot_check_slugs)][\n"
        "    [\"slug\", \"name\", \"deep_tech_score\", \"description_score\", \"founder_background_score\",\n"
        "     \"regulated_score\", \"market_type_pts\", \"geo_ops_score\",\n"
        "     \"technical_score\", \"practical_score\", \"complexity_score\"]\n"
        "]"
    ),
    markdown_cell(
        "## 3. Correlation with team size\n"
        "\n"
        "Objectives doc target: `r > 0.2` with team size. `teamSize` is "
        "heavily right-skewed (median 7, max 8,600), so it's log1p-transformed "
        "before correlating."
    ),
    code_cell(
        "companies_df = pd.read_csv(REPO_ROOT / \"data\" / \"processed\" / \"step3_enriched\" / \"companies_enriched.csv\")\n"
        "merged = scores_df.merge(companies_df[[\"id\", \"teamSize\"]], on=\"id\", how=\"left\").dropna(subset=[\"teamSize\"])\n"
        "merged[\"log_team_size\"] = np.log1p(merged[\"teamSize\"])\n"
        "\n"
        "pearson_r = merged[\"complexity_score\"].corr(merged[\"log_team_size\"], method=\"pearson\")\n"
        "spearman_r = merged[\"complexity_score\"].corr(merged[\"log_team_size\"], method=\"spearman\")\n"
        "print(f\"Pearson r (complexity_score vs log1p(teamSize)): {pearson_r:.3f}\")\n"
        "print(f\"Spearman r: {spearman_r:.3f}\")\n"
        "print(f\"Target from objectives doc: r > 0.2\")"
    ),
    markdown_cell(
        "## 4. Distribution spread\n"
        "\n"
        "Objectives doc target: standard deviation ≥ 15 points (avoid clustering)."
    ),
    code_cell(
        "std = scores_df[\"complexity_score\"].std()\n"
        "print(f\"complexity_score std: {std:.2f} (target: >= 15)\")\n"
        "scores_df[\"complexity_score\"].describe()"
    ),
    markdown_cell(
        "## 5. Sensitivity analysis\n"
        "\n"
        "Perturb each cap by ±1 and each bucket's point budget by ±20%, "
        "recompute, and check Spearman rank correlation of the top-100-by-"
        "`complexity_score` between baseline and each perturbation. High "
        "correlation (close to 1.0) means the ranking is stable and not "
        "overly sensitive to the exact calibration constants chosen."
    ),
    code_cell(
        "from src.etl.score import (\n"
        "    compute_deep_tech_score, compute_description_score, compute_founder_background_score,\n"
        "    compute_regulated_score, compute_market_type_pts, compute_geo_ops_score,\n"
        ")\n"
        "\n"
        "def build_with_overrides(**overrides):\n"
        "    parts = [\n"
        "        compute_deep_tech_score(features_df, cap=overrides.get(\"deep_tech_cap\", 3), points=overrides.get(\"deep_tech_points\", 20)),\n"
        "        compute_description_score(features_df, cap=overrides.get(\"description_cap\", 3), points=overrides.get(\"description_points\", 15)),\n"
        "        compute_founder_background_score(features_df, cap=overrides.get(\"founder_cap\", 4), points=overrides.get(\"founder_points\", 15)),\n"
        "        compute_regulated_score(features_df, points=overrides.get(\"regulated_points\", 15)),\n"
        "        compute_market_type_pts(features_df, points_per_level=overrides.get(\"market_points_per_level\", 5)),\n"
        "        compute_geo_ops_score(features_df, intl_points=overrides.get(\"geo_ops_intl_points\", 10), ops_points=overrides.get(\"geo_ops_ops_points\", 10)),\n"
        "    ]\n"
        "    df = features_df[[\"id\"]].copy()\n"
        "    for part in parts:\n"
        "        df = df.merge(part, on=\"id\", how=\"left\")\n"
        "    df[\"complexity_score\"] = df.drop(columns=\"id\").sum(axis=1)\n"
        "    return df\n"
        "\n"
        "baseline_top100 = set(scores_df.nlargest(100, \"complexity_score\")[\"id\"])\n"
        "\n"
        "perturbations = {\n"
        "    \"deep_tech_cap-1\": {\"deep_tech_cap\": 2},\n"
        "    \"deep_tech_cap+1\": {\"deep_tech_cap\": 4},\n"
        "    \"deep_tech_points-20pct\": {\"deep_tech_points\": 16},\n"
        "    \"deep_tech_points+20pct\": {\"deep_tech_points\": 24},\n"
        "    \"regulated_points-20pct\": {\"regulated_points\": 12},\n"
        "    \"regulated_points+20pct\": {\"regulated_points\": 18},\n"
        "}\n"
        "\n"
        "for label, overrides in perturbations.items():\n"
        "    perturbed = build_with_overrides(**overrides)\n"
        "    perturbed_top100 = set(perturbed.nlargest(100, \"complexity_score\")[\"id\"])\n"
        "    overlap = len(baseline_top100 & perturbed_top100)\n"
        "    print(f\"{label}: {overlap}/100 companies remain in top 100\")"
    ),
    markdown_cell(
        "## 6. Manual review\n"
        "\n"
        "Objectives doc target: top/bottom 50 companies should make sense on "
        "manual inspection."
    ),
    code_cell(
        "scores_df.sort_values(\"complexity_score\", ascending=False)[[\"name\", \"batch\", \"complexity_score\"]].head(25)"
    ),
    code_cell(
        "scores_df.sort_values(\"complexity_score\", ascending=True)[[\"name\", \"batch\", \"complexity_score\"]].head(25)"
    ),
]


def build_notebook() -> dict:
    return {
        "cells": CELLS,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(build_notebook(), f, indent=1)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the generator**

Run: `./.venv/Scripts/python.exe scripts/generate_score_design_notebook.py`
Expected: `Wrote <repo>/notebooks/score_design.ipynb`

- [ ] **Step 3: Verify the notebook is valid JSON and executes top-to-bottom**

Run:
```bash
./.venv/Scripts/python.exe -c "
import json
with open('notebooks/score_design.ipynb', encoding='utf-8') as f:
    nb = json.load(f)
print(f'{len(nb[\"cells\"])} cells, nbformat {nb[\"nbformat\"]}.{nb[\"nbformat_minor\"]}')
"
```

Then execute it end-to-end (requires `jupyter` / `nbconvert` — if not installed, run `./.venv/Scripts/pip.exe install jupyter nbconvert` first, and add `jupyter` and `nbconvert` to `requirements.txt`):

```bash
./.venv/Scripts/python.exe -m jupyter nbconvert --to notebook --execute --inplace notebooks/score_design.ipynb
```

Expected: exits 0, no exceptions. Open `notebooks/score_design.ipynb` afterward and confirm each cell has output (histogram renders, spot-check table shows the 3 named companies, correlation/std numbers print, sensitivity overlaps print, top/bottom 25 tables print).

- [ ] **Step 4: Record the calibration findings as a note in the notebook**

Based on the executed output from Step 3, add one more markdown cell to the end of `CELLS` in `scripts/generate_score_design_notebook.py` summarizing the actual results (fill in the real numbers observed — do not leave placeholder text):

```python
    markdown_cell(
        "## 7. Findings\n"
        "\n"
        "- Correlation with log(team size): Pearson r = <value>, Spearman = <value> "
        "(target: > 0.2)\n"
        "- Distribution std: <value> (target: >= 15)\n"
        "- Sensitivity: top-100 overlap ranged from <min>-<max>/100 across perturbations\n"
        "- Manual review: <one or two sentences on whether the top/bottom 25 make sense>\n"
        "\n"
        "No formula changes were made in Phase 7 based on these findings "
        "(see \"Open Question\" in the design spec) — if a target is missed "
        "significantly, that requires a follow-up brainstorming pass, not a "
        "silent patch here."
    ),
```

Re-run Steps 2-3 to regenerate and re-execute the notebook with the findings cell included.

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_score_design_notebook.py notebooks/score_design.ipynb
git commit -m "feat: add Phase 7 score design calibration notebook"
```

---

## Self-Review Notes

- **Spec coverage:** capped linear scaling (Decision 1) — Tasks 1-2; `founder_phd_count` folded into founder background (Decision 2) — Task 1's `compute_founder_background_score`; practical budget merged into 3 buckets (Decision 3) — Task 2's `compute_geo_ops_score`; `src/etl/score.py` built with TDD (Decision 4) — Tasks 1-4; calibration notebook (spec's "Calibration Notebook" section, all 7 sub-sections) — Task 5.
- **Type consistency:** all `compute_*_score` functions return frames keyed by `id` (unlike Phase 6's mix of `id`/`company_slug` keys — Phase 7 only reads from `complexity_features.parquet`, which is already keyed by `id`), so `build_score_table`'s `merge(..., on="id", how="left")` is used uniformly across every sub-score, consistent between Task 3's implementation and Task 4's integration test.
- **No placeholders:** all steps contain complete, runnable code. The one exception is Task 5 Step 4's `<value>` placeholders, which is intentional — it directs the engineer to fill in real numbers observed from actually running the notebook in Step 3, not to leave the placeholder text in the final committed notebook.
- **Rounding:** `technical_score`/`practical_score`/`complexity_score` are rounded to 1 decimal in `build_score_table` (Task 3); sub-bucket scores are left unrounded, matching the spec.
