# Phase 12: Config-Driven Scoring Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `src/etl/score.py`'s six hardcoded bucket functions with a generic, rubric-config-driven scoring engine so scaling methods (today: only linear-capped) become pluggable without touching the engine, per `docs/superpowers/specs/2026-07-14-phase12-config-driven-scoring-engine-design.md`.

**Architecture:** A rubric YAML (`config/rubric_v1.yaml`, `config/rubric_v2.yaml`) declares a list of scoring buckets, each with a raw feature (or a `combine` of several), a scaling `method`, and that method's params. `src/etl/scaling.py` and `src/etl/combine.py` are small registries of pluggable functions; `src/etl/rubric.py` loads/validates a rubric; `src/etl/score.py` becomes a generic engine that applies whatever buckets the rubric declares and sums them by `dimension`.

**Tech Stack:** Python 3.12+, pandas, pyyaml (new dependency), pytest.

## Global Constraints

- Every scaling method must return values bounded `[0, points]` for its given `points` param — this is the contract `validate_scores` relies on to derive bounds from the rubric instead of hardcoding them.
- `technical_score`, `practical_score`, `complexity_score` totals produced by the new engine against `config/rubric_v2.yaml` must exactly match the currently-committed `data/processed/scores/complexity_index_v2.csv` (row for row) — this is the load-bearing regression check (Task 6).
- Bucket-level output columns are dynamic: one `<bucket_name>_score` column per rubric bucket. `geo_ops_score` (today's combined column) is replaced by two independent columns, `international_operations_score` and `operational_intensity_score` — this is an intentional schema change, not a bug.
- Scaling/combine method selection is code-level (via the rubric YAML), not a runtime CLI flag — the CLI only selects *which rubric file* to use (`--rubric-config`), not individual bucket methods.
- Config format is YAML (`pyyaml`), chosen specifically to preserve inline comments explaining each cap/points rationale.
- One rubric config file per output version: `config/rubric_v1.yaml`, `config/rubric_v2.yaml`.

---

## Task 1: `src/etl/scaling.py` — scaling-method registry

**Files:**
- Create: `src/etl/scaling.py`
- Test: `tests/test_scaling.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `linear_capped(raw: pd.Series, cap: float, points: float) -> pd.Series`, `SCALING_METHODS: Dict[str, Callable]`. Consumed by Task 3 (`rubric.py`, to validate method names) and Task 5 (`score.py`'s engine).

- [ ] **Step 1: Add `pyyaml` to `requirements.txt`**

Append a new line to `requirements.txt`:

```
pandas
numpy
pytest
pyarrow
jupyter
nbconvert
scipy
matplotlib
plotly
pyyaml
```

- [ ] **Step 2: Install it**

Run: `./.venv/Scripts/python.exe -m pip install pyyaml`
Expected: successful install (or "already satisfied").

- [ ] **Step 3: Write the failing test**

Create `tests/test_scaling.py`:

```python
import pandas as pd
import pytest

from src.etl.scaling import SCALING_METHODS, linear_capped


def test_linear_capped_scales_linearly_up_to_cap():
    raw = pd.Series([0, 1, 3, 5])

    result = linear_capped(raw, cap=3, points=20)

    assert result[0] == 0
    assert result[1] == pytest.approx(20 / 3)
    assert result[2] == 20
    assert result[3] == 20  # clipped above cap


def test_linear_capped_registered_under_its_name():
    assert SCALING_METHODS["linear_capped"] is linear_capped
```

- [ ] **Step 4: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_scaling.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.etl.scaling'`

- [ ] **Step 5: Write the implementation**

Create `src/etl/scaling.py`:

```python
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
```

- [ ] **Step 6: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_scaling.py -v`
Expected: PASS (2 passed)

- [ ] **Step 7: Commit**

```bash
git add requirements.txt src/etl/scaling.py tests/test_scaling.py
git commit -m "feat: add scaling-method registry for config-driven scoring engine"
```

---

## Task 2: `src/etl/combine.py` — combine-method registry

**Files:**
- Create: `src/etl/combine.py`
- Test: `tests/test_combine.py`

**Interfaces:**
- Produces: `identity(features_df, raw_feature) -> pd.Series`, `weighted_sum(features_df, features: Dict[str, float]) -> pd.Series`, `COMBINE_METHODS: Dict[str, Callable]`. Consumed by Task 3 (`rubric.py`) and Task 5 (`score.py`'s engine).

- [ ] **Step 1: Write the failing test**

Create `tests/test_combine.py`:

```python
import pandas as pd

from src.etl.combine import COMBINE_METHODS, identity, weighted_sum


def test_identity_passes_through_single_column():
    features_df = pd.DataFrame({"x": [1, 2, 3]})

    result = identity(features_df, raw_feature="x")

    assert list(result) == [1, 2, 3]


def test_weighted_sum_combines_columns_with_weights():
    features_df = pd.DataFrame({"phd": [0, 1, 0], "research": [0, 0, 4]})

    result = weighted_sum(features_df, features={"phd": 2, "research": 1})

    assert list(result) == [0, 2, 4]


def test_combine_methods_registered_under_their_names():
    assert COMBINE_METHODS["identity"] is identity
    assert COMBINE_METHODS["weighted_sum"] is weighted_sum
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_combine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.etl.combine'`

- [ ] **Step 3: Write the implementation**

Create `src/etl/combine.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_combine.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/etl/combine.py tests/test_combine.py
git commit -m "feat: add combine-method registry for config-driven scoring engine"
```

---

## Task 3: `src/etl/rubric.py` — rubric config loading & validation

**Files:**
- Create: `src/etl/rubric.py`
- Test: `tests/test_rubric.py`

**Interfaces:**
- Consumes: `SCALING_METHODS` from `src/etl/scaling.py` (Task 1), `COMBINE_METHODS` from `src/etl/combine.py` (Task 2).
- Produces: `validate_rubric(rubric: dict) -> None` (raises `ValueError`), `load_rubric(path: Path) -> dict`. Consumed by Task 4 (config test fixtures) and Task 5 (`score.py`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_rubric.py`:

```python
import pytest
import yaml

from src.etl.rubric import load_rubric, validate_rubric


def _valid_rubric():
    return {
        "version": "test",
        "buckets": [
            {
                "name": "deep_tech",
                "dimension": "technical",
                "raw_feature": "deep_tech_tag_count",
                "method": "linear_capped",
                "params": {"cap": 2, "points": 12},
            },
            {
                "name": "founder_background",
                "dimension": "technical",
                "combine": "weighted_sum",
                "combine_params": {"features": {"phd": 2, "research": 1}},
                "method": "linear_capped",
                "params": {"cap": 2, "points": 9},
            },
        ],
    }


def test_validate_rubric_accepts_valid_rubric():
    validate_rubric(_valid_rubric())  # should not raise


def test_validate_rubric_rejects_missing_buckets_key():
    with pytest.raises(ValueError, match="buckets"):
        validate_rubric({})


def test_validate_rubric_rejects_duplicate_bucket_names():
    rubric = _valid_rubric()
    rubric["buckets"][1]["name"] = "deep_tech"

    with pytest.raises(ValueError, match="Duplicate bucket name"):
        validate_rubric(rubric)


def test_validate_rubric_rejects_bucket_with_both_raw_feature_and_combine():
    rubric = _valid_rubric()
    rubric["buckets"][0]["combine"] = "weighted_sum"
    rubric["buckets"][0]["combine_params"] = {"features": {"x": 1}}

    with pytest.raises(ValueError, match="exactly one of"):
        validate_rubric(rubric)


def test_validate_rubric_rejects_bucket_with_neither_raw_feature_nor_combine():
    rubric = _valid_rubric()
    del rubric["buckets"][0]["raw_feature"]

    with pytest.raises(ValueError, match="exactly one of"):
        validate_rubric(rubric)


def test_validate_rubric_rejects_unknown_scaling_method():
    rubric = _valid_rubric()
    rubric["buckets"][0]["method"] = "logistic"

    with pytest.raises(ValueError, match="unknown scaling method"):
        validate_rubric(rubric)


def test_validate_rubric_rejects_unknown_combine_method():
    rubric = _valid_rubric()
    rubric["buckets"][1]["combine"] = "nonexistent"

    with pytest.raises(ValueError, match="unknown combine method"):
        validate_rubric(rubric)


def test_validate_rubric_rejects_params_missing_points():
    rubric = _valid_rubric()
    del rubric["buckets"][0]["params"]["points"]

    with pytest.raises(ValueError, match="points"):
        validate_rubric(rubric)


def test_load_rubric_reads_and_validates_yaml_file(tmp_path):
    rubric_path = tmp_path / "rubric.yaml"
    rubric_path.write_text(yaml.dump(_valid_rubric()), encoding="utf-8")

    rubric = load_rubric(rubric_path)

    assert rubric["version"] == "test"
    assert len(rubric["buckets"]) == 2


def test_load_rubric_raises_on_invalid_yaml_content(tmp_path):
    rubric_path = tmp_path / "bad.yaml"
    rubric_path.write_text("buckets: []", encoding="utf-8")

    with pytest.raises(ValueError, match="buckets"):
        load_rubric(rubric_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_rubric.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.etl.rubric'`

- [ ] **Step 3: Write the implementation**

Create `src/etl/rubric.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_rubric.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: Commit**

```bash
git add src/etl/rubric.py tests/test_rubric.py
git commit -m "feat: add rubric config loading and validation"
```

---

## Task 4: `config/rubric_v1.yaml` and `config/rubric_v2.yaml`

**Files:**
- Create: `config/rubric_v1.yaml`
- Create: `config/rubric_v2.yaml`
- Modify: `tests/test_rubric.py` (append)

**Interfaces:**
- Consumes: `load_rubric` from Task 3.
- Produces: two real rubric files at `config/rubric_v1.yaml` (Phase 7's 50/50 split, points: technical 20+15+15=50, practical 15+15+10+10=50) and `config/rubric_v2.yaml` (Phase 9.5's 30/70 split, points: technical 12+9+9=30, practical 21+21+14+14=70). Consumed by Task 5's regression path, Task 6, and Task 7's pipeline wiring.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_rubric.py`:

```python
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def _dimension_points(rubric):
    totals = {}
    for bucket in rubric["buckets"]:
        totals[bucket["dimension"]] = totals.get(bucket["dimension"], 0) + bucket["params"]["points"]
    return totals


def test_rubric_v2_loads_and_sums_to_30_70():
    rubric = load_rubric(CONFIG_DIR / "rubric_v2.yaml")

    totals = _dimension_points(rubric)
    assert totals["technical"] == 30
    assert totals["practical"] == 70


def test_rubric_v1_loads_and_sums_to_50_50():
    rubric = load_rubric(CONFIG_DIR / "rubric_v1.yaml")

    totals = _dimension_points(rubric)
    assert totals["technical"] == 50
    assert totals["practical"] == 50
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_rubric.py -v -k "rubric_v"`
Expected: FAIL — `config/rubric_v2.yaml` and `config/rubric_v1.yaml` don't exist yet.

- [ ] **Step 3: Create `config/rubric_v2.yaml`** (Phase 9.5's current 30/70 rubric — exact values from `src/etl/score.py`'s current defaults)

```yaml
version: v2
description: "Phase 9.5 rubric -- 30/70 technical/practical split"
buckets:
  - name: deep_tech
    dimension: technical
    raw_feature: deep_tech_tag_count
    method: linear_capped
    params:
      cap: 2 # 2+ tags = maximally deep-tech
      points: 12

  - name: description
    dimension: technical
    raw_feature: description_tech_score
    method: linear_capped
    params:
      cap: 2
      points: 9

  - name: founder_background
    dimension: technical
    combine: weighted_sum
    combine_params:
      features:
        founder_phd_count: 2 # PhD is a rarer, stronger signal than research experience
        research_company_experience: 1
    method: linear_capped
    params:
      cap: 2
      points: 9

  - name: regulated
    dimension: practical
    raw_feature: regulated_industry
    method: linear_capped
    params:
      cap: 1 # binary flag: 0 or points
      points: 21

  - name: market_type
    dimension: practical
    raw_feature: market_type_score
    method: linear_capped
    params:
      cap: 3 # ordinal 0-3, already bounded
      points: 21

  - name: international_operations
    dimension: practical
    raw_feature: international_operations
    method: linear_capped
    params:
      cap: 1
      points: 14

  - name: operational_intensity
    dimension: practical
    raw_feature: operational_intensity
    method: linear_capped
    params:
      cap: 1
      points: 14
```

- [ ] **Step 4: Create `config/rubric_v1.yaml`** (Phase 7's original 50/50 rubric — exact values from `docs/superpowers/specs/2026-07-10-phase7-scoring-rubric-design.md`, preserved for provenance of the frozen `complexity_index_v1.csv`)

```yaml
version: v1
description: "Phase 7 original rubric -- 50/50 technical/practical split (historical baseline, preserved for provenance of complexity_index_v1.csv; not the current default)"
buckets:
  - name: deep_tech
    dimension: technical
    raw_feature: deep_tech_tag_count
    method: linear_capped
    params:
      cap: 3
      points: 20

  - name: description
    dimension: technical
    raw_feature: description_tech_score
    method: linear_capped
    params:
      cap: 3
      points: 15

  - name: founder_background
    dimension: technical
    combine: weighted_sum
    combine_params:
      features:
        founder_phd_count: 2
        research_company_experience: 1
    method: linear_capped
    params:
      cap: 4
      points: 15

  - name: regulated
    dimension: practical
    raw_feature: regulated_industry
    method: linear_capped
    params:
      cap: 1
      points: 15

  - name: market_type
    dimension: practical
    raw_feature: market_type_score
    method: linear_capped
    params:
      cap: 3
      points: 15

  - name: international_operations
    dimension: practical
    raw_feature: international_operations
    method: linear_capped
    params:
      cap: 2
      points: 10

  - name: operational_intensity
    dimension: practical
    raw_feature: operational_intensity
    method: linear_capped
    params:
      cap: 2
      points: 10
```

- [ ] **Step 5: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_rubric.py -v`
Expected: PASS (11 passed)

- [ ] **Step 6: Commit**

```bash
git add config/rubric_v1.yaml config/rubric_v2.yaml tests/test_rubric.py
git commit -m "feat: add rubric_v1.yaml and rubric_v2.yaml config files"
```

---

## Task 5: Rewrite `src/etl/score.py` as a rubric-driven engine

**Files:**
- Modify: `src/etl/score.py` (full rewrite)
- Modify: `tests/test_score.py` (full rewrite)

**Interfaces:**
- Consumes: `SCALING_METHODS` (Task 1), `COMBINE_METHODS` (Task 2), `load_rubric` (Task 3).
- Produces: `build_score_table(features_df, rubric) -> pd.DataFrame`, `validate_scores(features_df, scores_df, rubric) -> None`, `run_scoring_pipeline(input_path=None, output_path=None, rubric_config_path=None) -> None`. Consumed by Task 6 (regression test) and Task 7 (`pipeline.py`).
- **Note:** the old `compute_deep_tech_score`, `compute_description_score`, `compute_founder_background_score`, `compute_regulated_score`, `compute_market_type_pts`, `compute_geo_ops_score`, and `SCORE_COLUMNS` are removed entirely — no other module imports them (verified: only `tests/test_score.py` imports them, which this task also rewrites).

- [ ] **Step 1: Write the failing tests**

Replace the entire contents of `tests/test_score.py`:

```python
import pandas as pd
import pytest
import yaml

from src.etl.score import build_score_table, run_scoring_pipeline, validate_scores


def _minimal_rubric():
    return {
        "version": "test",
        "buckets": [
            {
                "name": "deep_tech",
                "dimension": "technical",
                "raw_feature": "deep_tech_tag_count",
                "method": "linear_capped",
                "params": {"cap": 2, "points": 12},
            },
            {
                "name": "founder_background",
                "dimension": "technical",
                "combine": "weighted_sum",
                "combine_params": {
                    "features": {"founder_phd_count": 2, "research_company_experience": 1}
                },
                "method": "linear_capped",
                "params": {"cap": 2, "points": 18},
            },
            {
                "name": "regulated",
                "dimension": "practical",
                "raw_feature": "regulated_industry",
                "method": "linear_capped",
                "params": {"cap": 1, "points": 70},
            },
        ],
    }


def _minimal_score_inputs():
    return pd.DataFrame(
        {
            "id": [1, 2],
            "slug": ["acme", "beta"],
            "name": ["Acme", "Beta"],
            "batch": ["W24", "S23"],
            "status": ["Active", "Active"],
            "deep_tech_tag_count": [3, 0],
            "founder_phd_count": [1, 0],
            "research_company_experience": [2, 0],
            "regulated_industry": [1, 0],
        }
    )


def test_build_score_table_has_one_row_per_company():
    features_df = _minimal_score_inputs()

    scores_df = build_score_table(features_df, _minimal_rubric())

    assert len(scores_df) == 2
    assert set(scores_df["id"]) == {1, 2}


def test_build_score_table_creates_one_column_per_bucket():
    features_df = _minimal_score_inputs()

    scores_df = build_score_table(features_df, _minimal_rubric())

    for col in ["deep_tech_score", "founder_background_score", "regulated_score"]:
        assert col in scores_df.columns


def test_build_score_table_computes_expected_values_for_acme_and_beta():
    features_df = _minimal_score_inputs()

    scores_df = build_score_table(features_df, _minimal_rubric())

    acme = scores_df[scores_df["slug"] == "acme"].iloc[0]
    assert acme["deep_tech_score"] == 12  # raw=3 clipped to cap=2 -> 2/2*12
    assert acme["founder_background_score"] == 18  # raw=2*1+2=4 clipped to cap=2 -> 18
    assert acme["regulated_score"] == 70
    assert acme["technical_score"] == 30  # 12 + 18
    assert acme["practical_score"] == 70
    assert acme["complexity_score"] == 100

    beta = scores_df[scores_df["slug"] == "beta"].iloc[0]
    assert beta["technical_score"] == 0
    assert beta["practical_score"] == 0
    assert beta["complexity_score"] == 0


def test_build_score_table_splits_geo_ops_into_two_independent_buckets():
    """
    Regression guard for the Phase 12 schema change: geo_ops_score no
    longer exists as one combined column -- international_operations and
    operational_intensity are ordinary independent buckets that both roll
    into practical_score.
    """
    features_df = pd.DataFrame(
        {
            "id": [1],
            "slug": ["acme"],
            "name": ["Acme"],
            "batch": ["W24"],
            "status": ["Active"],
            "international_operations": [5],
            "operational_intensity": [5],
        }
    )
    rubric = {
        "version": "test",
        "buckets": [
            {
                "name": "international_operations",
                "dimension": "practical",
                "raw_feature": "international_operations",
                "method": "linear_capped",
                "params": {"cap": 1, "points": 14},
            },
            {
                "name": "operational_intensity",
                "dimension": "practical",
                "raw_feature": "operational_intensity",
                "method": "linear_capped",
                "params": {"cap": 1, "points": 14},
            },
        ],
    }

    scores_df = build_score_table(features_df, rubric)

    assert "geo_ops_score" not in scores_df.columns
    assert scores_df.loc[0, "international_operations_score"] == 14
    assert scores_df.loc[0, "operational_intensity_score"] == 14
    assert scores_df.loc[0, "practical_score"] == 28


def test_validate_scores_passes_on_valid_table():
    features_df = _minimal_score_inputs()
    rubric = _minimal_rubric()
    scores_df = build_score_table(features_df, rubric)

    validate_scores(features_df, scores_df, rubric)  # should not raise


def test_validate_scores_raises_on_row_count_mismatch():
    features_df = pd.DataFrame({"id": [1, 2]})
    scores_df = pd.DataFrame(
        {"id": [1], "technical_score": [10.0], "practical_score": [10.0], "complexity_score": [20.0]}
    )

    with pytest.raises(AssertionError, match="Row count"):
        validate_scores(features_df, scores_df, _minimal_rubric())


def test_validate_scores_raises_on_id_set_mismatch():
    features_df = pd.DataFrame({"id": [1, 2]})
    scores_df = pd.DataFrame(
        {
            "id": [1, 3],
            "technical_score": [10.0, 10.0],
            "practical_score": [10.0, 10.0],
            "complexity_score": [20.0, 20.0],
        }
    )

    with pytest.raises(AssertionError, match="id set"):
        validate_scores(features_df, scores_df, _minimal_rubric())


def test_validate_scores_raises_on_missing_values():
    features_df = pd.DataFrame({"id": [1, 2]})
    scores_df = pd.DataFrame(
        {
            "id": [1, 2],
            "technical_score": [10.0, None],
            "practical_score": [10.0, 10.0],
            "complexity_score": [20.0, None],
        }
    )

    with pytest.raises(AssertionError, match="Missing values"):
        validate_scores(features_df, scores_df, _minimal_rubric())


def test_validate_scores_raises_on_out_of_range_technical_score():
    features_df = pd.DataFrame({"id": [1]})
    scores_df = pd.DataFrame(
        {"id": [1], "technical_score": [60.0], "practical_score": [10.0], "complexity_score": [70.0]}
    )

    # _minimal_rubric's technical budget = 12 + 18 = 30
    with pytest.raises(AssertionError, match="technical_score"):
        validate_scores(features_df, scores_df, _minimal_rubric())


def test_validate_scores_raises_on_out_of_range_practical_score():
    features_df = pd.DataFrame({"id": [1]})
    scores_df = pd.DataFrame(
        {"id": [1], "technical_score": [10.0], "practical_score": [75.0], "complexity_score": [85.0]}
    )

    # _minimal_rubric's practical budget = 70
    with pytest.raises(AssertionError, match="practical_score"):
        validate_scores(features_df, scores_df, _minimal_rubric())


def test_validate_scores_raises_on_out_of_range_complexity_score():
    features_df = pd.DataFrame({"id": [1]})
    scores_df = pd.DataFrame(
        {"id": [1], "technical_score": [25.0], "practical_score": [45.0], "complexity_score": [110.0]}
    )

    # _minimal_rubric's total budget = 30 + 70 = 100
    with pytest.raises(AssertionError, match="complexity_score"):
        validate_scores(features_df, scores_df, _minimal_rubric())


def test_run_scoring_pipeline_end_to_end(tmp_path):
    input_path = tmp_path / "complexity_features.parquet"
    output_path = tmp_path / "scores" / "complexity_index_test.csv"
    rubric_config_path = tmp_path / "rubric.yaml"

    features_df = _minimal_score_inputs()
    features_df.to_parquet(input_path, index=False)
    rubric_config_path.write_text(yaml.dump(_minimal_rubric()), encoding="utf-8")

    run_scoring_pipeline(
        input_path=input_path, output_path=output_path, rubric_config_path=rubric_config_path
    )

    scores_df = pd.read_csv(output_path)
    assert len(scores_df) == 2
    acme = scores_df[scores_df["slug"] == "acme"].iloc[0]
    assert acme["complexity_score"] == 100
    beta = scores_df[scores_df["slug"] == "beta"].iloc[0]
    assert beta["complexity_score"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_score.py -v`
Expected: FAIL — `build_score_table`/`validate_scores`/`run_scoring_pipeline` still have the old signatures (no `rubric` parameter).

- [ ] **Step 3: Replace the entire contents of `src/etl/score.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_score.py -v`
Expected: PASS (14 passed)

- [ ] **Step 5: Commit**

```bash
git add src/etl/score.py tests/test_score.py
git commit -m "refactor: rewrite score.py as a rubric-driven scoring engine"
```

---

## Task 6: Regression test — new engine reproduces the pre-Phase-12 v2 totals exactly

**Files:**
- Create: `tests/fixtures/complexity_index_v2_totals_snapshot.csv`
- Create: `tests/test_score_v2_regression.py`

**Interfaces:**
- Consumes: `load_rubric` (Task 3), `build_score_table` (Task 5), `config/rubric_v2.yaml` (Task 4), the real `data/processed/features/complexity_features.parquet` and the currently-committed `data/processed/scores/complexity_index_v2.csv` (both confirmed present on disk).

- [ ] **Step 1: Create the regression fixture from the current, pre-Phase-12 `complexity_index_v2.csv`**

This snapshot is the pinned ground truth this test compares against forever — it must be created now, before Task 11 overwrites the real `complexity_index_v2.csv` with new-engine output.

Run:

```bash
./.venv/Scripts/python.exe -c "
import pandas as pd
df = pd.read_csv('data/processed/scores/complexity_index_v2.csv')
df[['id', 'technical_score', 'practical_score', 'complexity_score']].to_csv(
    'tests/fixtures/complexity_index_v2_totals_snapshot.csv', index=False
)
print(f'Wrote {len(df)} rows')
"
```

Expected output: `Wrote 4844 rows` (or whatever the current real row count is).

- [ ] **Step 2: Write the failing test**

Create `tests/test_score_v2_regression.py`:

```python
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
```

- [ ] **Step 3: Run test and verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_score_v2_regression.py -v`
Expected: PASS (1 passed). If it fails, do not proceed to later tasks — a mismatch here means the engine rewrite changed real scoring behavior, which contradicts the design's core requirement. Debug `build_score_table`/`config/rubric_v2.yaml` against the exact formulas in Task 4's Step 3 before continuing.

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/complexity_index_v2_totals_snapshot.csv tests/test_score_v2_regression.py
git commit -m "test: add regression guard proving new engine matches pre-Phase-12 v2 totals"
```

---

## Task 7: Wire the rubric into `src/etl/pipeline.py`

**Files:**
- Modify: `src/etl/pipeline.py`
- Modify: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `run_scoring_pipeline(input_path, output_path, rubric_config_path)` (Task 5's new signature).
- Produces: `run_pipeline(steps, output_version, data_root, rubric_config_path)` — new optional `rubric_config_path` parameter. Consumed by Task 8 (CLI).

- [ ] **Step 1: Write the failing tests**

In `tests/test_pipeline.py`, replace `test_default_paths_computes_expected_required_inputs`:

```python
def test_default_paths_computes_expected_required_inputs(tmp_path):
    paths = _default_paths(tmp_path, output_version="v1")

    assert paths["clean"]["required_input"] == tmp_path / "raw" / "companies.csv"
    assert (
        paths["impute"]["required_input"]
        == tmp_path / "processed" / "step1_cleaned" / "companies_cleaned.csv"
    )
    assert (
        paths["enrich"]["required_input"]
        == tmp_path / "processed" / "step2_imputed" / "companies_imputed.csv"
    )
    assert (
        paths["features"]["required_input"]
        == tmp_path / "processed" / "step3_enriched" / "companies_enriched.csv"
    )
    assert (
        paths["score"]["required_input"]
        == tmp_path / "processed" / "features" / "complexity_features.parquet"
    )
    assert (
        paths["score"]["kwargs"]["output_path"]
        == tmp_path / "processed" / "scores" / "complexity_index_v1.csv"
    )
    rubric_path = paths["score"]["kwargs"]["rubric_config_path"]
    assert rubric_path.name == "rubric_v1.yaml"
    assert rubric_path.parent.name == "config"
```

Replace `test_default_paths_kwargs_use_each_steps_own_param_names`:

```python
def test_default_paths_kwargs_use_each_steps_own_param_names(tmp_path):
    paths = _default_paths(tmp_path, output_version="v1")

    assert set(paths["clean"]["kwargs"]) == {"input_dir", "output_dir"}
    assert set(paths["impute"]["kwargs"]) == {"input_dir", "output_dir"}
    assert set(paths["enrich"]["kwargs"]) == {"input_dir", "output_dir"}
    assert set(paths["features"]["kwargs"]) == {"input_dir", "output_dir"}
    assert set(paths["score"]["kwargs"]) == {"input_path", "output_path", "rubric_config_path"}
```

Replace `test_run_pipeline_end_to_end_features_and_score` (adds explicit `rubric_config_path` override so the test stays isolated to `tmp_path`, matching how the CLI's `--rubric-config` override works):

```python
def test_run_pipeline_end_to_end_features_and_score(tmp_path):
    data_root = tmp_path / "data"
    raw_dir = data_root / "raw"
    step3_dir = data_root / "processed" / "step3_enriched"
    raw_dir.mkdir(parents=True)
    step3_dir.mkdir(parents=True)

    companies = pd.DataFrame(
        [
            {
                "id": 1, "slug": "acme", "name": "Acme", "batch": "W24",
                "status": "Active",
                "longDescription": "Acme builds a proprietary machine learning platform.",
            },
            {
                "id": 2, "slug": "beta", "name": "Beta", "batch": "S23",
                "status": "Active", "longDescription": "Beta is a local bakery.",
            },
        ]
    )
    tags = pd.DataFrame({"id": [1], "tag": ["Artificial Intelligence"]})
    industries = pd.DataFrame({"id": [1], "industry": ["Fintech"]})
    regions = pd.DataFrame(
        {"id": [1, 2], "country": ["United States of America", "India"]}
    )
    founders = pd.DataFrame({"hnid": ["a"], "company_slug": ["acme"]})
    schools = pd.DataFrame({"hnid": ["a"], "field_of_study": ["Doctor Of Philosophy"]})
    prior_companies = pd.DataFrame({"hnid": [], "company": []})

    companies.to_csv(step3_dir / "companies_enriched.csv", index=False)
    tags.to_csv(step3_dir / "tags_enriched.csv", index=False)
    industries.to_csv(step3_dir / "industries_enriched.csv", index=False)
    regions.to_csv(step3_dir / "regions_enriched.csv", index=False)
    founders.to_csv(step3_dir / "founders_enriched.csv", index=False)
    schools.to_csv(step3_dir / "schools_enriched.csv", index=False)
    prior_companies.to_csv(step3_dir / "prior_companies_enriched.csv", index=False)

    rubric_config_path = tmp_path / "rubric.yaml"
    rubric_config_path.write_text(
        """
version: test
buckets:
  - name: deep_tech
    dimension: technical
    raw_feature: deep_tech_tag_count
    method: linear_capped
    params: {cap: 2, points: 30}
  - name: regulated
    dimension: practical
    raw_feature: regulated_industry
    method: linear_capped
    params: {cap: 1, points: 70}
""",
        encoding="utf-8",
    )

    run_pipeline(
        steps=["features", "score"],
        output_version="v9",
        data_root=data_root,
        rubric_config_path=rubric_config_path,
    )

    output_path = data_root / "processed" / "scores" / "complexity_index_v9.csv"
    assert output_path.exists()
    scores_df = pd.read_csv(output_path)
    assert len(scores_df) == 2
    acme = scores_df[scores_df["slug"] == "acme"].iloc[0]
    assert acme["complexity_score"] > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -v`
Expected: FAIL — `_default_paths`'s returned score kwargs don't yet include `rubric_config_path`, and `run_pipeline` doesn't yet accept a `rubric_config_path` argument.

- [ ] **Step 3: Modify `src/etl/pipeline.py`**

Replace the `_default_paths` function body's `score` entry (the function itself, in full):

```python
def _default_paths(data_root: Path, output_version: str) -> Dict[str, dict]:
    """
    Compute each step's required input (for prerequisite checks) and the
    kwargs to pass to its run_*_pipeline() function.

    Args:
        data_root: Root data directory (real project data/ or a tmp_path
            for tests).
        output_version: Version suffix for the final score CSV filename.

    Returns:
        Dict keyed by step name, each value {"required_input": Path,
        "kwargs": dict} where kwargs matches that step's own
        run_*_pipeline() parameter names.
    """
    raw_dir = data_root / "raw"
    processed_dir = data_root / "processed"
    step1_dir = processed_dir / "step1_cleaned"
    step2_dir = processed_dir / "step2_imputed"
    step3_dir = processed_dir / "step3_enriched"
    features_dir = processed_dir / "features"
    scores_dir = processed_dir / "scores"
    features_path = features_dir / "complexity_features.parquet"
    default_rubric_path = data_root.parent / "config" / f"rubric_{output_version}.yaml"

    return {
        "clean": {
            "required_input": raw_dir / "companies.csv",
            "kwargs": {"input_dir": raw_dir, "output_dir": step1_dir},
        },
        "impute": {
            "required_input": step1_dir / "companies_cleaned.csv",
            "kwargs": {"input_dir": step1_dir, "output_dir": step2_dir},
        },
        "enrich": {
            "required_input": step2_dir / "companies_imputed.csv",
            "kwargs": {"input_dir": step2_dir, "output_dir": step3_dir},
        },
        "features": {
            "required_input": step3_dir / "companies_enriched.csv",
            "kwargs": {"input_dir": step3_dir, "output_dir": features_dir},
        },
        "score": {
            "required_input": features_path,
            "kwargs": {
                "input_path": features_path,
                "output_path": scores_dir / f"complexity_index_{output_version}.csv",
                "rubric_config_path": default_rubric_path,
            },
        },
    }
```

Replace the `run_pipeline` function in full:

```python
def run_pipeline(
    steps: Optional[List[str]] = None,
    output_version: str = "v1",
    data_root: Optional[Path] = None,
    rubric_config_path: Optional[Path] = None,
) -> None:
    """
    Run the requested ETL steps in canonical order.

    Args:
        steps: Step names to run, or None/["all"] for DEFAULT_STEPS
            (clean, impute, features, score — enrich is opt-in).
        output_version: Version suffix for the final score CSV filename.
        data_root: Root data directory. Defaults to the real project's
            data/ directory; overridden in tests to isolate I/O. Not
            exposed via the CLI.
        rubric_config_path: Explicit override for the score step's rubric
            config file. Defaults to <repo_root>/config/rubric_<output_version>.yaml
            (derived from data_root's parent) when not given. Exposed via
            the CLI's --rubric-config flag.
    """
    resolved_steps = normalize_steps(steps)

    if data_root is None:
        data_root = Path(__file__).resolve().parents[2] / "data"

    paths = _default_paths(data_root, output_version)
    if rubric_config_path is not None:
        paths["score"]["kwargs"]["rubric_config_path"] = rubric_config_path

    for step in resolved_steps:
        check_step_prerequisite(step, paths[step]["required_input"])
        print(f"\n{'#' * 60}")
        print(f"PIPELINE STEP: {step}")
        print(f"{'#' * 60}")
        STEP_RUNNERS[step](paths[step]["kwargs"])

    if "score" in resolved_steps:
        first_step = resolved_steps[0]
        validate_pipeline_output(
            output_path=paths["score"]["kwargs"]["output_path"],
            reference_input_path=paths[first_step]["required_input"],
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Commit**

```bash
git add src/etl/pipeline.py tests/test_pipeline.py
git commit -m "feat: wire rubric config path through the ETL pipeline orchestrator"
```

---

## Task 8: `--rubric-config` CLI flag

**Files:**
- Modify: `scripts/run_complexity_pipeline.py`
- Modify: `tests/test_run_complexity_pipeline.py`

**Interfaces:**
- Consumes: `run_pipeline(steps, output_version, rubric_config_path)` (Task 7).

- [ ] **Step 1: Write the failing tests**

Replace `tests/test_run_complexity_pipeline.py` in full:

```python
from scripts import run_complexity_pipeline as cli_module
from scripts.run_complexity_pipeline import build_arg_parser, main, parse_steps_arg


def test_parse_steps_arg_splits_and_strips_comma_list():
    assert parse_steps_arg("clean, impute,score") == ["clean", "impute", "score"]


def test_parse_steps_arg_handles_all():
    assert parse_steps_arg("all") == ["all"]


def test_build_arg_parser_defaults():
    parser = build_arg_parser()
    args = parser.parse_args([])
    assert args.steps == "all"
    assert args.output_version == "v1"
    assert args.rubric_config is None


def test_build_arg_parser_accepts_overrides():
    parser = build_arg_parser()
    args = parser.parse_args(
        [
            "--steps", "clean,impute",
            "--output-version", "v3",
            "--rubric-config", "config/custom.yaml",
        ]
    )
    assert args.steps == "clean,impute"
    assert args.output_version == "v3"
    assert args.rubric_config == "config/custom.yaml"


def test_main_calls_run_pipeline_with_parsed_args_and_returns_zero(monkeypatch):
    captured = {}

    def fake_run_pipeline(steps, output_version, rubric_config_path):
        captured["steps"] = steps
        captured["output_version"] = output_version
        captured["rubric_config_path"] = rubric_config_path

    monkeypatch.setattr(cli_module, "run_pipeline", fake_run_pipeline)

    exit_code = main(["--steps", "clean,impute", "--output-version", "v3"])

    assert exit_code == 0
    assert captured == {
        "steps": ["clean", "impute"],
        "output_version": "v3",
        "rubric_config_path": None,
    }


def test_main_passes_rubric_config_path_as_a_path(monkeypatch):
    captured = {}

    def fake_run_pipeline(steps, output_version, rubric_config_path):
        captured["rubric_config_path"] = rubric_config_path

    monkeypatch.setattr(cli_module, "run_pipeline", fake_run_pipeline)

    main(["--steps", "score", "--rubric-config", "config/custom.yaml"])

    assert captured["rubric_config_path"] == Path("config/custom.yaml")


def test_main_returns_one_and_prints_error_on_pipeline_failure(monkeypatch, capsys):
    def fake_run_pipeline(steps, output_version, rubric_config_path):
        raise FileNotFoundError("missing data/raw/companies.csv")

    monkeypatch.setattr(cli_module, "run_pipeline", fake_run_pipeline)

    exit_code = main(["--steps", "clean"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "FAILED" in captured.err
```

Add the missing `from pathlib import Path` import at the top of the file (needed by the new `test_main_passes_rubric_config_path_as_a_path` test):

```python
from pathlib import Path

from scripts import run_complexity_pipeline as cli_module
from scripts.run_complexity_pipeline import build_arg_parser, main, parse_steps_arg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_run_complexity_pipeline.py -v`
Expected: FAIL — `args.rubric_config` doesn't exist yet, and `main`'s `fake_run_pipeline` stub now expects a `rubric_config_path` kwarg that `main` doesn't pass.

- [ ] **Step 3: Modify `scripts/run_complexity_pipeline.py`**

Replace `build_arg_parser`:

```python
def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Y Combinator complexity index ETL pipeline."
    )
    parser.add_argument(
        "--steps",
        default="all",
        help=(
            f"Comma-separated step names ({', '.join(STEP_ORDER)}), or 'all' "
            f"(default: all steps except enrich). CAVEAT: 'features' always reads "
            f"its input from data/processed/step3_enriched/ (enrich's output "
            f"directory), never from step2_imputed/. Since 'all' excludes enrich, "
            f"a default run regenerates step1_cleaned/ and step2_imputed/ but then "
            f"'features' silently reads the stale, pre-existing step3_enriched/ "
            f"-- fresh clean/impute output does NOT propagate to the final "
            f"complexity_index CSV. To truly regenerate from raw data, "
            f"explicitly include enrich, e.g. --steps clean,impute,enrich,features,score."
        ),
    )
    parser.add_argument(
        "--output-version",
        default="v1",
        help=(
            "Version suffix for the final complexity_index_<version>.csv "
            "filename (default: v1)."
        ),
    )
    parser.add_argument(
        "--rubric-config",
        default=None,
        help=(
            "Path to a rubric YAML file overriding the score step's rubric "
            "(default: config/rubric_<output-version>.yaml)."
        ),
    )
    return parser
```

Replace `main`:

```python
def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    steps = parse_steps_arg(args.steps)
    rubric_config_path = Path(args.rubric_config) if args.rubric_config else None

    try:
        run_pipeline(
            steps=steps,
            output_version=args.output_version,
            rubric_config_path=rubric_config_path,
        )
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1

    print("Pipeline completed successfully.")
    return 0
```

(`Path` is already imported at the top of this file — no new import needed here.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_run_complexity_pipeline.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/run_complexity_pipeline.py tests/test_run_complexity_pipeline.py
git commit -m "feat: add --rubric-config CLI flag"
```

---

## Task 9: Dynamic bucket-score columns in `scripts/generate_dashboard.py`

**Files:**
- Modify: `scripts/generate_dashboard.py:172-187` (`build_correlation_matrix`)
- Modify: `tests/test_generate_dashboard.py`

**Interfaces:**
- No signature change to `build_correlation_matrix(scores_df, features_df, feature_cols)` — only its internal column discovery changes from a hardcoded list to introspecting `scores_df.columns`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_generate_dashboard.py`, replace `test_build_correlation_matrix_computes_expected_shape_and_values`:

```python
def test_build_correlation_matrix_computes_expected_shape_and_values():
    scores_df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "deep_tech_score": [10.0, 20.0, 30.0],
            "technical_score": [10.0, 20.0, 30.0],
            "practical_score": [30.0, 20.0, 10.0],
            "description_score": [0.0, 0.0, 0.0],
            "founder_background_score": [0.0, 0.0, 0.0],
            "regulated_score": [0.0, 0.0, 0.0],
            "market_type_score": [0.0, 0.0, 0.0],
            "international_operations_score": [0.0, 0.0, 0.0],
            "operational_intensity_score": [0.0, 0.0, 0.0],
            "complexity_score": [40.0, 40.0, 40.0],
        }
    )
    features_df = pd.DataFrame({"id": [1, 2, 3], "deep_tech_tag_count": [1, 2, 3]})

    corr = build_correlation_matrix(scores_df, features_df, feature_cols=["deep_tech_tag_count"])

    # 1 feature col + 7 bucket-score cols + technical/practical/complexity = 11
    assert corr.shape == (11, 11)
    assert corr.loc["deep_tech_tag_count", "technical_score"] == pytest.approx(1.0)
    assert corr.loc["technical_score", "practical_score"] == pytest.approx(-1.0)
```

Add a new test directly after it, in the same file:

```python
def test_build_correlation_matrix_discovers_bucket_score_columns_dynamically():
    """
    Proves build_correlation_matrix no longer hardcodes bucket column
    names -- any rubric bucket's <name>_score column is picked up
    automatically, which is the whole point of Phase 12's config-driven
    engine producing a dynamic schema.
    """
    scores_df = pd.DataFrame(
        {
            "id": [1, 2],
            "some_new_bucket_score": [10.0, 20.0],
            "technical_score": [10.0, 20.0],
            "practical_score": [5.0, 15.0],
            "complexity_score": [15.0, 35.0],
        }
    )
    features_df = pd.DataFrame({"id": [1, 2], "x": [1, 2]})

    corr = build_correlation_matrix(scores_df, features_df, feature_cols=["x"])

    assert "some_new_bucket_score" in corr.columns
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_generate_dashboard.py -v -k correlation_matrix`
Expected: FAIL — current `build_correlation_matrix` still uses the hardcoded 6-column list (`market_type_pts`, `geo_ops_score` not present in the new fixtures; `some_new_bucket_score` not discovered).

- [ ] **Step 3: Modify `scripts/generate_dashboard.py`**

Replace `build_correlation_matrix` (lines 172-187):

```python
def build_correlation_matrix(
    scores_df: pd.DataFrame, features_df: pd.DataFrame, feature_cols: List[str]
) -> pd.DataFrame:
    """
    Correlation matrix across the given raw features, every rubric
    bucket's <name>_score column (discovered dynamically from scores_df,
    not hardcoded -- see Phase 12), and the 3 top-level scores.
    """
    bucket_score_cols = [
        c
        for c in scores_df.columns
        if c.endswith("_score")
        and c not in ("technical_score", "practical_score", "complexity_score")
    ]
    merged = scores_df.merge(features_df[["id"] + feature_cols], on="id", how="left")
    corr_cols = feature_cols + bucket_score_cols + [
        "technical_score",
        "practical_score",
        "complexity_score",
    ]
    return merged[corr_cols].corr()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_generate_dashboard.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_dashboard.py tests/test_generate_dashboard.py
git commit -m "feat: discover bucket-score columns dynamically in dashboard correlation matrix"
```

---

## Task 10: Dynamic bucket-score columns in `scripts/generate_complexity_analysis_notebook.py`

**Files:**
- Modify: `scripts/generate_complexity_analysis_notebook.py`

**Interfaces:**
- None (script-embedded notebook-cell source strings only; verified by regeneration + execution in Task 11, not by a dedicated unit test — this generator produces notebook JSON, its correctness is proven by running the resulting notebook end-to-end).

- [ ] **Step 1: Add a `bucket_score_cols` line to the setup cell**

In the setup `code_cell` (starts around line 49), immediately after the line that loads `scores_df`, insert a new line computing `bucket_score_cols` once for reuse by later cells. The setup cell currently reads:

```python
        "scores_df = pd.read_csv(REPO_ROOT / \"data\" / \"processed\" / \"scores\" / \"complexity_index_v2.csv\")\n"
        "features_df = pd.read_parquet(REPO_ROOT / \"data\" / \"processed\" / \"features\" / \"complexity_features.parquet\")\n"
```

Change it to:

```python
        "scores_df = pd.read_csv(REPO_ROOT / \"data\" / \"processed\" / \"scores\" / \"complexity_index_v2.csv\")\n"
        "bucket_score_cols = [c for c in scores_df.columns if c.endswith(\"_score\") and c not in (\"technical_score\", \"practical_score\", \"complexity_score\")]\n"
        "features_df = pd.read_parquet(REPO_ROOT / \"data\" / \"processed\" / \"features\" / \"complexity_features.parquet\")\n"
```

- [ ] **Step 2: Replace the hardcoded `corr_cols` cell**

The cell around line 158-177 currently builds:

```python
        "corr_cols = feature_cols + [\n"
        "    \"deep_tech_score\", \"description_score\", \"founder_background_score\",\n"
        "    \"regulated_score\", \"market_type_pts\", \"geo_ops_score\",\n"
        "    \"technical_score\", \"practical_score\", \"complexity_score\",\n"
        "]\n"
```

Replace those 5 lines with:

```python
        "corr_cols = feature_cols + bucket_score_cols + [\n"
        "    \"technical_score\", \"practical_score\", \"complexity_score\",\n"
        "]\n"
```

Also update the markdown cell immediately before it (around line 152-157), which currently reads:

```python
    markdown_cell(
        "## 6. Correlation Heatmap\n"
        "\n"
        "Correlation matrix across all 8 raw features (`complexity_features.parquet`), "
        "the 6 rubric bucket scores, and the 3 top-level scores."
    ),
```

Change `"the 6 rubric bucket scores, "` to `"the rubric's bucket scores, "` (the bucket count is no longer fixed at 6):

```python
    markdown_cell(
        "## 6. Correlation Heatmap\n"
        "\n"
        "Correlation matrix across all 8 raw features (`complexity_features.parquet`), "
        "the rubric's bucket scores, and the 3 top-level scores."
    ),
```

- [ ] **Step 3: Replace the hardcoded `bucket_cols` cell**

The cell around line 224-233 currently builds:

```python
    code_cell(
        "bucket_cols = [\n"
        "    \"slug\", \"name\", \"batch\", \"status\",\n"
        "    \"deep_tech_score\", \"description_score\", \"founder_background_score\",\n"
        "    \"regulated_score\", \"market_type_pts\", \"geo_ops_score\",\n"
        "    \"technical_score\", \"practical_score\", \"complexity_score\",\n"
        "]\n"
        "top_25 = merged.sort_values(\"complexity_score\", ascending=False)[bucket_cols].head(25)\n"
        "top_25"
    ),
```

Replace with:

```python
    code_cell(
        "bucket_cols = [\"slug\", \"name\", \"batch\", \"status\"] + bucket_score_cols + [\n"
        "    \"technical_score\", \"practical_score\", \"complexity_score\",\n"
        "]\n"
        "top_25 = merged.sort_values(\"complexity_score\", ascending=False)[bucket_cols].head(25)\n"
        "top_25"
    ),
```

- [ ] **Step 4: Verify no hardcoded legacy bucket names remain in the file**

Run: `grep -n "geo_ops_score\|market_type_pts\|founder_background_score" scripts/generate_complexity_analysis_notebook.py`
Expected: no matches (empty output). If any remain, they're in prose/markdown describing historical findings, not executable `corr_cols`/`bucket_cols` lists — leave those (they're historical commentary, not code that breaks).

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_complexity_analysis_notebook.py
git commit -m "feat: discover bucket-score columns dynamically in notebook generator"
```

---

## Task 11: Regenerate real artifacts and verify the full suite

**Files:**
- Modify: `data/processed/scores/complexity_index_v2.csv` (regenerated, new schema)
- Modify: `notebooks/complexity_analysis.ipynb` (regenerated)
- Modify: `output/complexity_dashboard_v2.html` (regenerated)

**Interfaces:** None — this task runs the already-implemented pipeline against real data and commits the results.

- [ ] **Step 1: Regenerate `complexity_index_v2.csv` using the new engine**

Run: `./.venv/Scripts/python.exe scripts/run_complexity_pipeline.py --steps score --output-version v2`
Expected: `Pipeline completed successfully.` printed at the end; `data/processed/scores/complexity_index_v2.csv` now has `international_operations_score` and `operational_intensity_score` columns instead of `geo_ops_score`.

- [ ] **Step 2: Spot-check the regenerated CSV's totals still match the regression snapshot**

Run:

```bash
./.venv/Scripts/python.exe -c "
import pandas as pd
new = pd.read_csv('data/processed/scores/complexity_index_v2.csv').set_index('id').sort_index()
snap = pd.read_csv('tests/fixtures/complexity_index_v2_totals_snapshot.csv').set_index('id').sort_index()
for col in ['technical_score', 'practical_score', 'complexity_score']:
    assert (new[col] == snap[col]).all(), f'{col} mismatch'
print('OK: regenerated v2.csv totals match the pre-Phase-12 snapshot')
"
```

Expected: `OK: regenerated v2.csv totals match the pre-Phase-12 snapshot`

- [ ] **Step 3: Regenerate the analysis notebook**

Run:

```bash
./.venv/Scripts/python.exe scripts/generate_complexity_analysis_notebook.py
./.venv/Scripts/python.exe -m jupyter nbconvert --to notebook --execute --inplace notebooks/complexity_analysis.ipynb
```

Expected: both commands exit 0; no exceptions in the executed notebook (nbconvert fails loudly with a non-zero exit code and a traceback if any cell raises).

- [ ] **Step 4: Regenerate the dashboard**

Run: `./.venv/Scripts/python.exe scripts/generate_dashboard.py`
Expected: `Wrote <repo_root>/output/complexity_dashboard_v2.html`

- [ ] **Step 5: Run the full test suite**

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: all tests pass, 0 failures.

- [ ] **Step 6: Commit the regenerated artifacts and any remaining changes**

```bash
git add data/processed/scores/complexity_index_v2.csv notebooks/complexity_analysis.ipynb output/complexity_dashboard_v2.html
git commit -m "chore: regenerate v2 score CSV, notebook, and dashboard with the config-driven engine"
```

---

## Post-plan note

This plan does not update `README.md` or `documentation/plan_complexity_metric/roadmap.md` — both describe the *current* rubric/architecture in prose and would need a follow-up documentation pass once this lands, but that's a separate, explicitly out-of-scope concern per the design spec's "Out of scope" section (it only covers the engine, config, and direct consumers).
