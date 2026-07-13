# Phase 8 ETL Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `src/etl/pipeline.py`, an orchestrator that sequences the existing Phase 3-7 step modules (`clean`, `impute`, `enrich`, `features`, `score`) into one run, plus a CLI entry point (`scripts/run_complexity_pipeline.py`) with `--steps` and `--output-version` flags, per `docs/superpowers/specs/2026-07-13-phase8-etl-pipeline-design.md`.

**Architecture:** A canonical step order (`STEP_ORDER`) with a fail-fast pre-flight check per step, dispatch through each step's existing `run_*_pipeline()` function, a uniform exception-based failure signal across all 5 steps, and an end-to-end validation pass on the final output. `enrich` is opt-in (excluded from `--steps all`). No new data-processing logic — this phase only sequences and validates.

**Tech Stack:** Python stdlib (`argparse`, `pathlib`) + `pandas` (already a dependency).

## Global Constraints

- `STEP_ORDER = ["clean", "impute", "enrich", "features", "score"]` — canonical order, used to sort/dedup any requested step list.
- `DEFAULT_STEPS = ["clean", "impute", "features", "score"]` — what `--steps all` (or no `--steps` flag) resolves to. `enrich` requires explicit inclusion (per spec Decision 1).
- `--output-version` only changes the final score CSV's filename: `data/processed/scores/complexity_index_{version}.csv`. Intermediate directories (`step1_cleaned/`, `step2_imputed/`, `step3_enriched/`, `features/`) are unversioned fixed paths (spec Decision 3).
- `run_cleaning_pipeline()` gains optional `input_dir`/`output_dir` params, defaulting to today's `RAW_DIR`/`CLEANED_DIR` — additive, no behavior change for existing callers (spec Decision 2).
- All 5 steps present one uniform failure signal to the orchestrator: an exception. `clean`'s `(success, message)` return is translated into `RuntimeError(message)` when `success` is `False`; the other 4 steps already raise `AssertionError` internally (spec Decision 4).
- Pre-flight check happens immediately before each step runs (not all upfront), so a step that ran earlier in the same invocation satisfies a later step's check. Missing input raises `FileNotFoundError` naming the path and, where applicable, which step produces it (spec Decision 5).
- `run_pipeline` takes an internal `data_root: Path | None = None` parameter, defaulting to the real project's `data/` directory. **This is not exposed via any CLI flag** — it exists solely so tests can redirect an entire pipeline run into `tmp_path` without touching real project data, the same way `run_scoring_pipeline`'s `input_path`/`output_path` already do for a single step.
- **Deviation from the spec's literal Decision 6 wording:** the spec says end-to-end validation compares row count against `data/raw/companies.csv`. In this environment, `data/raw/*.csv` is gitignored and genuinely absent from disk (verified: `git ls-files data/raw/` returns nothing, and `data/raw/` locally contains only `enrichment_cache/`). Hardcoding the check to a file that may not exist would make `validate_pipeline_output` crash on any partial run that doesn't include `clean` — which is the common case, since `clean` is only runnable when raw data is present. Instead, `validate_pipeline_output` compares against the **required input of the first step that actually ran** in the given invocation (whichever file that is — CSV or parquet). This preserves the spec's intent (catch cross-step row-loss bugs the per-step validators can't see) without assuming raw data exists. Flagged here for visibility since it changes an approved decision's specifics, not just its implementation.
- Existing step I/O conventions reused as-is: `clean`/`impute`/`enrich`/`features` all take `input_dir`/`output_dir`; `score` takes `input_path`/`output_path`. `pipeline.py` accounts for this naming difference per-step rather than forcing a uniform signature onto `score.py`.

---

## Task 1: `run_cleaning_pipeline` accepts `input_dir`/`output_dir`

**Files:**
- Modify: `src/etl/clean.py:366-441`
- Create: `tests/test_clean.py`

**Interfaces:**
- Produces: `run_cleaning_pipeline(input_dir: Path = None, output_dir: Path = None) -> Tuple[bool, str]` (same return type as today; new optional params only)

- [ ] **Step 1: Write the failing test**

Create `tests/test_clean.py`:

```python
import pandas as pd

from src.etl.clean import run_cleaning_pipeline


def test_run_cleaning_pipeline_respects_input_and_output_dir(tmp_path):
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "step1_cleaned"
    input_dir.mkdir()

    pd.DataFrame(
        {"id": [1], "batch": ["w24"], "status": ["Active"], "teamSize": [3]}
    ).to_csv(input_dir / "companies.csv", index=False)
    pd.DataFrame({"hnid": ["a"]}).to_csv(input_dir / "founders.csv", index=False)
    pd.DataFrame({"id": [1], "industry": ["Fintech"]}).to_csv(
        input_dir / "industries.csv", index=False
    )
    pd.DataFrame({"id": [1], "tag": ["AI"]}).to_csv(input_dir / "tags.csv", index=False)
    pd.DataFrame({"id": [1]}).to_csv(input_dir / "regions.csv", index=False)
    pd.DataFrame({"hnid": ["a"], "year": [2020]}).to_csv(
        input_dir / "schools.csv", index=False
    )
    pd.DataFrame({"hnid": ["a"], "company": ["Old Co"]}).to_csv(
        input_dir / "prior_companies.csv", index=False
    )
    pd.DataFrame({"id": [1], "badge": ["Top Company"]}).to_csv(
        input_dir / "badges.csv", index=False
    )

    success, message = run_cleaning_pipeline(input_dir=input_dir, output_dir=output_dir)

    assert success is True
    assert (output_dir / "companies_cleaned.csv").exists()
    cleaned = pd.read_csv(output_dir / "companies_cleaned.csv")
    assert cleaned.loc[0, "batch"] == "W24"


def test_run_cleaning_pipeline_defaults_still_work_with_no_args():
    # Uses the real RAW_DIR/CLEANED_DIR defaults — just confirms the
    # function signature still accepts a no-arg call after the change.
    import inspect

    from src.etl.clean import run_cleaning_pipeline as fn

    sig = inspect.signature(fn)
    assert list(sig.parameters) == ["input_dir", "output_dir"]
    assert sig.parameters["input_dir"].default is None
    assert sig.parameters["output_dir"].default is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_clean.py -v`
Expected: `TypeError: run_cleaning_pipeline() got an unexpected keyword argument 'input_dir'`

- [ ] **Step 3: Modify `run_cleaning_pipeline`**

In `src/etl/clean.py`, replace the `run_cleaning_pipeline` function (lines 366-427) with:

```python
def run_cleaning_pipeline(
    input_dir: Path = None, output_dir: Path = None
) -> Tuple[bool, str]:
    """
    Execute the complete data cleaning pipeline.

    Reads all raw CSVs, applies cleaning functions, validates, and saves.

    Args:
        input_dir: Path to raw CSVs directory. Defaults to RAW_DIR.
        output_dir: Path to write cleaned CSVs. Defaults to CLEANED_DIR.

    Returns:
        Tuple of (success: bool, message: str)
    """
    if input_dir is None:
        input_dir = RAW_DIR
    if output_dir is None:
        output_dir = CLEANED_DIR

    logger.info("Starting data cleaning pipeline...")

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Define cleaning functions for each file
    cleaning_functions = {
        "companies.csv": clean_companies,
        "founders.csv": clean_founders,
        "industries.csv": clean_industries,
        "tags.csv": clean_tags,
        "regions.csv": clean_regions,
        "schools.csv": clean_schools,
        "prior_companies.csv": clean_prior_companies,
        "badges.csv": clean_badges,
    }

    original_counts = {}
    cleaned_counts = {}

    try:
        # Process each file
        for filename, clean_func in cleaning_functions.items():
            input_path = input_dir / filename
            output_path = output_dir / filename.replace(".csv", "_cleaned.csv")

            logger.info(f"\nProcessing {filename}...")

            # Read raw data
            df_raw = pd.read_csv(input_path)
            original_counts[filename] = len(df_raw)

            # Clean data
            df_clean = clean_func(df_raw)
            cleaned_counts[filename] = len(df_clean)

            # Save cleaned data
            df_clean.to_csv(output_path, index=False)
            logger.info(f"Saved to {output_path}")

        # Validate results
        if validate_cleaning(original_counts, cleaned_counts):
            logger.info("\n✓ Data cleaning pipeline completed successfully!")
            return True, "All 8 CSV files cleaned and validated"
        else:
            logger.error("\n✗ Validation failed - row count mismatches detected")
            return False, "Validation failed"

    except Exception as e:
        logger.error(f"\n✗ Pipeline failed with error: {str(e)}")
        return False, str(e)
```

(The only functional change from the original: `RAW_DIR`/`CLEANED_DIR` module constants are now only used as defaults when `input_dir`/`output_dir` are `None`; the loop body uses the resolved local variables. The `output_path.relative_to(PROJECT_ROOT)` log call is replaced with plain `output_path` since a `tmp_path`-based `output_dir` in tests isn't under `PROJECT_ROOT` and `relative_to` would raise `ValueError`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_clean.py -v`
Expected: 2 passed

- [ ] **Step 5: Run the full test suite to confirm no regressions**

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: all existing tests still pass (66 before this task + 2 new)

- [ ] **Step 6: Commit**

```bash
git add src/etl/clean.py tests/test_clean.py
git commit -m "feat: add input_dir/output_dir params to run_cleaning_pipeline"
```

---

## Task 2: Step ordering (`STEP_ORDER`, `DEFAULT_STEPS`, `normalize_steps`)

**Files:**
- Create: `src/etl/pipeline.py`
- Create: `tests/test_pipeline.py`

**Interfaces:**
- Produces:
  - `STEP_ORDER: List[str]` = `["clean", "impute", "enrich", "features", "score"]`
  - `DEFAULT_STEPS: List[str]` = `["clean", "impute", "features", "score"]`
  - `normalize_steps(requested: Optional[List[str]]) -> List[str]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pipeline.py`:

```python
import pytest

from src.etl.pipeline import DEFAULT_STEPS, STEP_ORDER, normalize_steps


def test_normalize_steps_none_returns_default_steps():
    assert normalize_steps(None) == DEFAULT_STEPS


def test_normalize_steps_all_returns_default_steps_excluding_enrich():
    result = normalize_steps(["all"])
    assert result == DEFAULT_STEPS
    assert "enrich" not in result


def test_normalize_steps_deduplicates_and_orders_canonically():
    assert normalize_steps(["score", "clean", "score"]) == ["clean", "score"]


def test_normalize_steps_includes_enrich_when_explicitly_requested():
    result = normalize_steps(["clean", "enrich", "impute"])
    assert result == ["clean", "impute", "enrich"]


def test_normalize_steps_rejects_unknown_step_name():
    with pytest.raises(ValueError, match="scrape"):
        normalize_steps(["clean", "scrape"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -v`
Expected: `ModuleNotFoundError: No module named 'src.etl.pipeline'`

- [ ] **Step 3: Implement `src/etl/pipeline.py` (step ordering)**

Create `src/etl/pipeline.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/etl/pipeline.py tests/test_pipeline.py
git commit -m "feat: add Phase 8 pipeline step ordering"
```

---

## Task 3: Path resolution + prerequisite checks

**Files:**
- Modify: `src/etl/pipeline.py`
- Modify: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `PRODUCER_STEP` (Task 2)
- Produces:
  - `_default_paths(data_root: Path, output_version: str) -> Dict[str, dict]` — per step: `{"required_input": Path, "kwargs": dict}`
  - `check_step_prerequisite(step: str, required_input: Path) -> None` — raises `FileNotFoundError` if `required_input` doesn't exist

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pipeline.py`:

```python
from src.etl.pipeline import _default_paths, check_step_prerequisite


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


def test_default_paths_respects_output_version(tmp_path):
    paths = _default_paths(tmp_path, output_version="v2")
    assert paths["score"]["kwargs"]["output_path"].name == "complexity_index_v2.csv"


def test_default_paths_kwargs_use_each_steps_own_param_names(tmp_path):
    paths = _default_paths(tmp_path, output_version="v1")

    assert set(paths["clean"]["kwargs"]) == {"input_dir", "output_dir"}
    assert set(paths["impute"]["kwargs"]) == {"input_dir", "output_dir"}
    assert set(paths["enrich"]["kwargs"]) == {"input_dir", "output_dir"}
    assert set(paths["features"]["kwargs"]) == {"input_dir", "output_dir"}
    assert set(paths["score"]["kwargs"]) == {"input_path", "output_path"}


def test_check_step_prerequisite_passes_when_input_exists(tmp_path):
    required = tmp_path / "companies_cleaned.csv"
    required.write_text("id\n1\n")

    check_step_prerequisite("impute", required)  # should not raise


def test_check_step_prerequisite_raises_with_producer_hint(tmp_path):
    required = tmp_path / "missing.parquet"

    with pytest.raises(FileNotFoundError, match="run 'features' first"):
        check_step_prerequisite("score", required)


def test_check_step_prerequisite_raises_without_producer_hint_for_clean(tmp_path):
    required = tmp_path / "companies.csv"

    with pytest.raises(FileNotFoundError, match="ensure raw data is present"):
        check_step_prerequisite("clean", required)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -v`
Expected: `ImportError: cannot import name '_default_paths'`

- [ ] **Step 3: Implement `_default_paths` and `check_step_prerequisite`**

Add to `src/etl/pipeline.py` (after `normalize_steps`):

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
            },
        },
    }


def check_step_prerequisite(step: str, required_input: Path) -> None:
    """
    Raise FileNotFoundError with a clear message if a step's required input
    is missing from disk.

    Args:
        step: Step name (for the error message).
        required_input: Path that must exist before this step can run.
    """
    if required_input.exists():
        return

    producer = PRODUCER_STEP.get(step)
    if producer:
        raise FileNotFoundError(
            f"Cannot run '{step}': missing {required_input} — run '{producer}' first."
        )
    raise FileNotFoundError(
        f"Cannot run '{step}': missing {required_input} — "
        f"ensure raw data is present in data/raw/."
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add src/etl/pipeline.py tests/test_pipeline.py
git commit -m "feat: add Phase 8 path resolution and prerequisite checks"
```

---

## Task 4: `run_pipeline` orchestrator dispatch

**Files:**
- Modify: `src/etl/pipeline.py`
- Modify: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `normalize_steps`, `_default_paths`, `check_step_prerequisite` (Tasks 2-3); `run_cleaning_pipeline`, `run_imputation_pipeline`, `run_enrichment_pipeline`, `run_feature_engineering_pipeline`, `run_scoring_pipeline` (existing modules)
- Produces: `run_pipeline(steps: Optional[List[str]] = None, output_version: str = "v1", data_root: Optional[Path] = None) -> None`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pipeline.py`:

```python
from src.etl import pipeline
from src.etl.pipeline import run_pipeline


def test_run_pipeline_invokes_requested_steps_in_canonical_order(tmp_path, monkeypatch):
    calls = []

    monkeypatch.setattr(
        pipeline, "run_cleaning_pipeline", lambda **kwargs: (calls.append("clean"), (True, "ok"))[1]
    )
    monkeypatch.setattr(
        pipeline, "run_imputation_pipeline", lambda **kwargs: calls.append("impute")
    )
    monkeypatch.setattr(pipeline, "check_step_prerequisite", lambda step, path: None)

    run_pipeline(steps=["impute", "clean"], data_root=tmp_path)

    assert calls == ["clean", "impute"]


def test_run_pipeline_raises_runtime_error_when_clean_step_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "run_cleaning_pipeline", lambda **kwargs: (False, "boom"))
    monkeypatch.setattr(pipeline, "check_step_prerequisite", lambda step, path: None)

    with pytest.raises(RuntimeError, match="boom"):
        run_pipeline(steps=["clean"], data_root=tmp_path)


def test_run_pipeline_raises_file_not_found_when_prerequisite_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="run 'clean' first"):
        run_pipeline(steps=["impute"], data_root=tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -v`
Expected: `ImportError: cannot import name 'run_pipeline'`

- [ ] **Step 3: Implement `run_pipeline`**

Add these imports to the top of `src/etl/pipeline.py` (after the existing `import pandas as pd`):

```python
from src.etl.clean import run_cleaning_pipeline
from src.etl.enrich import run_enrichment_pipeline
from src.etl.features import run_feature_engineering_pipeline
from src.etl.impute import run_imputation_pipeline
from src.etl.score import run_scoring_pipeline
```

Add to the end of `src/etl/pipeline.py`:

```python
def _run_clean_step(kwargs: dict) -> None:
    success, message = run_cleaning_pipeline(**kwargs)
    if not success:
        raise RuntimeError(message)


STEP_RUNNERS = {
    "clean": _run_clean_step,
    "impute": lambda kwargs: run_imputation_pipeline(**kwargs),
    "enrich": lambda kwargs: run_enrichment_pipeline(**kwargs),
    "features": lambda kwargs: run_feature_engineering_pipeline(**kwargs),
    "score": lambda kwargs: run_scoring_pipeline(**kwargs),
}


def run_pipeline(
    steps: Optional[List[str]] = None,
    output_version: str = "v1",
    data_root: Optional[Path] = None,
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
    """
    resolved_steps = normalize_steps(steps)

    if data_root is None:
        data_root = Path(__file__).resolve().parents[2] / "data"

    paths = _default_paths(data_root, output_version)

    for step in resolved_steps:
        check_step_prerequisite(step, paths[step]["required_input"])
        print(f"\n{'#' * 60}")
        print(f"PIPELINE STEP: {step}")
        print(f"{'#' * 60}")
        STEP_RUNNERS[step](paths[step]["kwargs"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -v`
Expected: 14 passed

- [ ] **Step 5: Commit**

```bash
git add src/etl/pipeline.py tests/test_pipeline.py
git commit -m "feat: add Phase 8 pipeline orchestrator dispatch"
```

---

## Task 5: End-to-end validation + real integration test

**Files:**
- Modify: `src/etl/pipeline.py`
- Modify: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `run_pipeline` (Task 4)
- Produces: `validate_pipeline_output(output_path: Path, reference_input_path: Path) -> None`
- Modifies: `run_pipeline` to call `validate_pipeline_output` after all requested steps finish, when `"score"` was among them

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pipeline.py`:

```python
from src.etl.pipeline import validate_pipeline_output


def test_validate_pipeline_output_passes_on_valid_csv_reference(tmp_path):
    reference_path = tmp_path / "companies_cleaned.csv"
    output_path = tmp_path / "complexity_index_v1.csv"
    pd.DataFrame({"id": [1, 2]}).to_csv(reference_path, index=False)
    pd.DataFrame({"id": [1, 2], "complexity_score": [10.0, 90.0]}).to_csv(
        output_path, index=False
    )

    validate_pipeline_output(output_path, reference_path)  # should not raise


def test_validate_pipeline_output_passes_on_valid_parquet_reference(tmp_path):
    reference_path = tmp_path / "complexity_features.parquet"
    output_path = tmp_path / "complexity_index_v1.csv"
    pd.DataFrame({"id": [1, 2]}).to_parquet(reference_path, index=False)
    pd.DataFrame({"id": [1, 2], "complexity_score": [10.0, 90.0]}).to_csv(
        output_path, index=False
    )

    validate_pipeline_output(output_path, reference_path)  # should not raise


def test_validate_pipeline_output_raises_on_row_count_mismatch(tmp_path):
    reference_path = tmp_path / "companies_cleaned.csv"
    output_path = tmp_path / "complexity_index_v1.csv"
    pd.DataFrame({"id": [1, 2, 3]}).to_csv(reference_path, index=False)
    pd.DataFrame({"id": [1, 2], "complexity_score": [10.0, 90.0]}).to_csv(
        output_path, index=False
    )

    with pytest.raises(AssertionError, match="Row count mismatch"):
        validate_pipeline_output(output_path, reference_path)


def test_validate_pipeline_output_raises_on_out_of_range_score(tmp_path):
    reference_path = tmp_path / "companies_cleaned.csv"
    output_path = tmp_path / "complexity_index_v1.csv"
    pd.DataFrame({"id": [1]}).to_csv(reference_path, index=False)
    pd.DataFrame({"id": [1], "complexity_score": [150.0]}).to_csv(
        output_path, index=False
    )

    with pytest.raises(AssertionError, match="complexity_score"):
        validate_pipeline_output(output_path, reference_path)


def test_run_pipeline_end_to_end_features_and_score(tmp_path):
    data_root = tmp_path
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

    run_pipeline(steps=["features", "score"], output_version="v9", data_root=data_root)

    output_path = data_root / "processed" / "scores" / "complexity_index_v9.csv"
    assert output_path.exists()
    scores_df = pd.read_csv(output_path)
    assert len(scores_df) == 2
    acme = scores_df[scores_df["slug"] == "acme"].iloc[0]
    assert acme["complexity_score"] > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -v`
Expected: `ImportError: cannot import name 'validate_pipeline_output'`

- [ ] **Step 3: Implement `validate_pipeline_output` and wire it into `run_pipeline`**

Add to `src/etl/pipeline.py` (after `run_pipeline`... actually define it before `run_pipeline` so it's available when called — add it directly above the `run_pipeline` function definition):

```python
def validate_pipeline_output(output_path: Path, reference_input_path: Path) -> None:
    """
    End-to-end validation of the final score CSV, on top of each step's own
    internal validate_* checks. Compares row count against
    reference_input_path — the required input of the first step that
    actually ran in this invocation — to catch cross-step row-loss bugs
    that no single step's own validation would see.

    Args:
        output_path: Path to the written complexity_index_*.csv.
        reference_input_path: CSV or parquet file whose row count the
            output should match.
    """
    assert output_path.exists(), f"Pipeline output not found at {output_path}"

    scores_df = pd.read_csv(output_path)
    if reference_input_path.suffix == ".parquet":
        reference_df = pd.read_parquet(reference_input_path)
    else:
        reference_df = pd.read_csv(reference_input_path)

    assert len(scores_df) == len(reference_df), (
        f"Row count mismatch: {len(scores_df)} scores vs "
        f"{len(reference_df)} rows in {reference_input_path}"
    )
    assert scores_df["complexity_score"].notna().all(), "Null complexity_score values found!"
    assert scores_df["complexity_score"].between(0, 100).all(), (
        "complexity_score must be within [0, 100]!"
    )

    print(f"Pipeline validation passed: {len(scores_df)} companies scored")
```

Then modify `run_pipeline`'s body — replace:

```python
    for step in resolved_steps:
        check_step_prerequisite(step, paths[step]["required_input"])
        print(f"\n{'#' * 60}")
        print(f"PIPELINE STEP: {step}")
        print(f"{'#' * 60}")
        STEP_RUNNERS[step](paths[step]["kwargs"])
```

with:

```python
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
Expected: 19 passed

- [ ] **Step 5: Run the full test suite**

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add src/etl/pipeline.py tests/test_pipeline.py
git commit -m "feat: add Phase 8 end-to-end pipeline output validation"
```

---

## Task 6: CLI runner (`scripts/run_complexity_pipeline.py`)

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/run_complexity_pipeline.py`
- Create: `tests/test_run_complexity_pipeline.py`

**Interfaces:**
- Consumes: `run_pipeline`, `STEP_ORDER` (Tasks 2-5)
- Produces:
  - `build_arg_parser() -> argparse.ArgumentParser`
  - `parse_steps_arg(steps_arg: str) -> List[str]`
  - `main(argv=None) -> int`

- [ ] **Step 1: Write the failing tests**

Create `scripts/__init__.py` (empty file, makes `scripts/` importable as a package):

```python
```

Create `tests/test_run_complexity_pipeline.py`:

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


def test_build_arg_parser_accepts_overrides():
    parser = build_arg_parser()
    args = parser.parse_args(["--steps", "clean,impute", "--output-version", "v3"])
    assert args.steps == "clean,impute"
    assert args.output_version == "v3"


def test_main_calls_run_pipeline_with_parsed_args_and_returns_zero(monkeypatch):
    captured = {}

    def fake_run_pipeline(steps, output_version):
        captured["steps"] = steps
        captured["output_version"] = output_version

    monkeypatch.setattr(cli_module, "run_pipeline", fake_run_pipeline)

    exit_code = main(["--steps", "clean,impute", "--output-version", "v3"])

    assert exit_code == 0
    assert captured == {"steps": ["clean", "impute"], "output_version": "v3"}


def test_main_returns_one_and_prints_error_on_pipeline_failure(monkeypatch, capsys):
    def fake_run_pipeline(steps, output_version):
        raise FileNotFoundError("missing data/raw/companies.csv")

    monkeypatch.setattr(cli_module, "run_pipeline", fake_run_pipeline)

    exit_code = main(["--steps", "clean"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "FAILED" in captured.err
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_run_complexity_pipeline.py -v`
Expected: `ModuleNotFoundError: No module named 'scripts.run_complexity_pipeline'`

- [ ] **Step 3: Implement `scripts/run_complexity_pipeline.py`**

Create `scripts/run_complexity_pipeline.py`:

```python
#!/usr/bin/env python3
"""
CLI entry point for the Phase 8 ETL pipeline orchestrator.

Usage:
  python scripts/run_complexity_pipeline.py --steps all --output-version v1
  python scripts/run_complexity_pipeline.py --steps clean,impute,features,score
"""
import argparse
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.etl.pipeline import STEP_ORDER, run_pipeline


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Y Combinator complexity index ETL pipeline."
    )
    parser.add_argument(
        "--steps",
        default="all",
        help=(
            f"Comma-separated step names ({', '.join(STEP_ORDER)}), or 'all' "
            f"(default: all steps except enrich)."
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
    return parser


def parse_steps_arg(steps_arg: str) -> List[str]:
    return [s.strip() for s in steps_arg.split(",") if s.strip()]


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    steps = parse_steps_arg(args.steps)

    try:
        run_pipeline(steps=steps, output_version=args.output_version)
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1

    print("Pipeline completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_run_complexity_pipeline.py -v`
Expected: 6 passed

- [ ] **Step 5: Run the full test suite**

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add scripts/__init__.py scripts/run_complexity_pipeline.py tests/test_run_complexity_pipeline.py
git commit -m "feat: add Phase 8 CLI runner for the ETL pipeline"
```

---

## Task 7: Real run, sanity check, and roadmap updates

**Files:**
- Modify: `documentation/plan_complexity_metric/roadmap.md`
- Modify: `documentation/plan/roadmap_todo.md`
- Possibly regenerated (only if non-deterministic, which is not expected): `data/processed/step2_imputed/*`, `data/processed/features/complexity_features.parquet`, `data/processed/scores/complexity_index_v1.csv`

**Interfaces:**
- Consumes: `scripts/run_complexity_pipeline.py` (Task 6)

- [ ] **Step 1: Confirm the full test suite passes before the real run**

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: all tests pass (66 pre-existing + Task 1-6 additions)

- [ ] **Step 2: Verify the fail-fast prerequisite check for real**

`data/raw/*.csv` is not present in this environment (it's gitignored and was never fetched locally — confirmed via `git ls-files data/raw/` returning nothing). Run:

```bash
./.venv/Scripts/python.exe scripts/run_complexity_pipeline.py --steps all
echo "Exit code: $?"
```

Expected: exits 1, stderr contains `FAILED: Cannot run 'clean': missing ... data\raw\companies.csv — ensure raw data is present in data/raw/.` This demonstrates the pre-flight check firing correctly in a real scenario, not just in tests.

- [ ] **Step 3: Run the pipeline for real over the available data**

`data/processed/step1_cleaned/` already exists and is git-tracked, so `impute → features → score` can run for real without raw data:

```bash
./.venv/Scripts/python.exe scripts/run_complexity_pipeline.py --steps impute,features,score --output-version v1
echo "Exit code: $?"
```

Expected: exits 0, prints `PIPELINE STEP: impute`, `PIPELINE STEP: features`, `PIPELINE STEP: score`, then `Pipeline validation passed: 4844 companies scored` and `Pipeline completed successfully.`

- [ ] **Step 4: Sanity-check the regenerated output**

Run:
```bash
./.venv/Scripts/python.exe -c "
import pandas as pd
df = pd.read_csv('data/processed/scores/complexity_index_v1.csv')
print(df.shape)
print(df.isna().sum().sum(), 'total NaNs')
print(df['complexity_score'].between(0, 100).all(), 'all scores in range')
"
```

Confirm: `(4844, 14)`, `0 total NaNs`, `True`.

- [ ] **Step 5: Confirm regeneration is byte-for-byte deterministic**

Since Phase 8 wires existing, unchanged step logic together, re-running should reproduce identical output to what's already committed:

```bash
git status --porcelain data/processed/
git diff --stat data/processed/
```

Expected: no output (no changes) — proves the orchestrator faithfully reproduces each step's already-verified behavior. **If this shows a diff, stop and investigate before proceeding** (it would mean the orchestrator is calling a step differently than its own module's tests assume — do not commit changed data files without understanding why first).

- [ ] **Step 6: Update `documentation/plan_complexity_metric/roadmap.md`**

Change the checklist item 8 block:
```markdown
- [x] **8. ETL pipeline implementation**
  - [x] Create modular ETL scripts in `src/etl/`
  - [x] Build CLI runner with versioning
  - [x] Add automated validation checks
  - [x] Output: Complete pipeline + `complexity_index_v1.csv`
```

Update the timeline table row:
```markdown
| 8. Pipeline | 2 days | ✅ Complete |
```
and the total-complete percentage to `80% complete`.

Update "Next Immediate Actions":
```markdown
## Next Immediate Actions

**Current Focus:** Phase 9 - Validation & Analysis

**Next Steps:**
1. Build `notebooks/complexity_analysis.ipynb`: score distribution, technical vs practical scatter, complexity by batch/status/industry, correlation heatmap
2. Manual review of top/bottom outliers
3. Revisit the Phase 7 calibration gap (team-size correlation r=0.035 vs target >0.2; score spread σ=10.11 vs target ≥15) — this is the natural point to decide whether to fix it before treating the index as validated, since Phase 9 is the first phase that actually analyzes/uses the scores rather than just producing them
4. Output: `notebooks/complexity_analysis.ipynb`

**To continue:** Mark this task complete and proceed to implementation.
```

- [ ] **Step 7: Update `documentation/plan/roadmap_todo.md`**

```markdown
- [x] 8. Implement ETL pipeline
```

- [ ] **Step 8: Commit**

```bash
git add documentation/plan_complexity_metric/roadmap.md documentation/plan/roadmap_todo.md
git commit -m "docs: mark Phase 8 ETL pipeline complete, point roadmap at Phase 9"
```

If Step 5 showed no diff (expected), there is nothing further to commit for `data/processed/`. If it showed a diff, resolve that first (see Step 5) before this commit.

---

## Self-Review Notes

- **Spec coverage:** Decision 1 (enrich opt-in) — Task 2's `DEFAULT_STEPS`. Decision 2 (`clean` params) — Task 1. Decision 3 (output-version scope) — Task 3's `_default_paths`. Decision 4 (uniform failure signal) — Task 4's `_run_clean_step`/`STEP_RUNNERS`. Decision 5 (fail-fast pre-flight, step-by-step) — Task 3's `check_step_prerequisite` + Task 4's per-step check inside the loop. Decision 6 (end-to-end validation) — Task 5, with the `reference_input_path` deviation explained in Global Constraints. CLI `--steps`/`--output-version` flags — Task 6.
- **Type consistency:** `_default_paths` return shape (`{"required_input": Path, "kwargs": dict}`) is used identically across Tasks 3, 4, and 5. `STEP_RUNNERS` values all accept a single `kwargs: dict` positional argument, matching how `run_pipeline`'s loop calls them (`STEP_RUNNERS[step](paths[step]["kwargs"])`) — consistent from Task 4 through Task 7's real run.
- **No placeholders:** all steps contain complete, runnable code; no `<value>`-style fill-ins anywhere in this plan (unlike the Phase 7 plan's notebook-findings step, Phase 8 has no analysis step that depends on real output numbers).
- **Known limitation carried into Task 7:** `data/raw/*.csv` doesn't exist in this environment, so `--steps all` cannot be exercised against real data end-to-end here — only its fail-fast behavior can be. This is inherent to the environment, not a gap in the implementation; anyone with raw CSVs present can run `--steps all` normally.
