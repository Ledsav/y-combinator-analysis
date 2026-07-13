# Phase 8 ETL Pipeline — Design

**Status:** Approved
**Date:** 2026-07-13
**Roadmap:** `documentation/plan_complexity_metric/roadmap.md`, checklist item 8 ("ETL pipeline implementation")

## Context

Phases 3-7 each produced a self-contained step module in `src/etl/` (`clean.py`, `impute.py`, `enrich.py`, `features.py`, `score.py`), every one already exposing a `run_*_pipeline()` orchestrator function and reading/writing a fixed on-disk location:

```
data/raw/ → step1_cleaned/ → step2_imputed/ → step3_enriched/ → features/complexity_features.parquet → scores/complexity_index_v1.csv
```

Phase 8 does not add new data-processing logic. It wires these five existing, independently-tested functions into one orchestrator and a CLI entry point, per the roadmap's Phase 8 sketch (`documentation/plan_complexity_metric/roadmap.md` lines 229-250).

Phase 7 shipped with a documented calibration gap (see roadmap checklist item 7's "Known gap" note and `docs/superpowers/specs/2026-07-10-phase7-scoring-rubric-design.md`'s "Open Question") — team-size correlation and score spread both missed their objectives-doc targets. That gap blocks treating the index as *validated* for downstream analytical use, but Phase 8 doesn't consume score values analytically; it only sequences the existing pipeline. It is explicitly out of scope for Phase 8 to touch scoring logic or attempt recalibration — that remains a separate follow-up brainstorming pass before Phase 9 (Validation & Analysis).

### Existing step interfaces (as of Phase 7)

| Step | Function | Params | Failure signal |
|---|---|---|---|
| clean | `run_cleaning_pipeline()` | none (hardcoded `RAW_DIR`/`CLEANED_DIR`) | returns `(False, msg)` |
| impute | `run_imputation_pipeline(input_dir=None, output_dir=None)` | optional overrides | raises `AssertionError` (via `validate_imputation`) |
| enrich | `run_enrichment_pipeline(input_dir=None, output_dir=None, cache_dir=None, score_threshold=80, fetch_fn=..., sleep_fn=...)` | optional overrides + injectable network/sleep | raises `AssertionError` (via `validate_enrichment`) |
| features | `run_feature_engineering_pipeline(input_dir=None, output_dir=None)` | optional overrides | raises `AssertionError` (via `validate_features`) |
| score | `run_scoring_pipeline(input_path=None, output_path=None)` | optional overrides | raises `AssertionError` (via `validate_scores`) |

`clean` is the outlier on both axes (no params, tuple-return instead of raising). Phase 8 fixes the params gap (see Decision 2) and normalizes the failure signal at the orchestrator boundary (see Decision 4), without touching the other four modules.

## Decisions

1. **`enrich` is opt-in, not part of `--steps all`.** It performs live, rate-limited network scraping against an already-populated cache (`data/raw/enrichment_cache/`) that `features.py` already reads from. `all` = `clean, impute, features, score`. Running `enrich` requires explicitly listing it: `--steps clean,impute,enrich,features,score`.

2. **`run_cleaning_pipeline()` gains `input_dir`/`output_dir` params**, defaulting to today's `RAW_DIR`/`CLEANED_DIR` module constants. Purely additive — no behavior change for existing callers (including any current tests). This brings `clean` in line with the other 4 steps' signatures and makes the orchestrator's `clean` step testable via `tmp_path` the same way as the rest.

3. **`--output-version` only affects the final score CSV's filename** (`complexity_index_{version}.csv` under `data/processed/scores/`). Intermediate directories (`step1_cleaned/`, `step2_imputed/`, `step3_enriched/`, `features/`) remain unversioned fixed paths — they are not meant to be multi-version artifacts, only the published index is.

4. **Uniform failure signal via exceptions.** The orchestrator wraps `clean`'s `(success, message)` return and raises `RuntimeError(message)` when `success` is `False`, so all 5 steps present one failure path (an exception) to the CLI. No exceptions are caught inside `run_pipeline` — they propagate to the CLI's top-level handler.

5. **Fail-fast pre-flight check per step, checked immediately before that step runs.** Before invoking a step's `run_*_pipeline()`, the orchestrator checks that step's required input file/dir exists on disk. This is checked step-by-step in canonical order (not all upfront) so that a prerequisite step run earlier in the *same* invocation correctly satisfies a later step's check. On failure: `FileNotFoundError` naming the missing path and which step produces it, e.g. `"Cannot run 'score': missing data/processed/features/complexity_features.parquet — run 'features' first."`

6. **End-to-end validation runs only when `score` is among the executed steps.** `validate_pipeline_output(output_path, raw_companies_path)` checks: output file exists; row count equals `data/raw/companies.csv` row count; no nulls in `complexity_score`; `complexity_score` within `[0, 100]`. This supplements (not replaces) each step's existing internal `validate_*` call — it catches cross-step integration issues (e.g. a step silently writing to the wrong path) that per-step validation can't see.

## Architecture

```
src/etl/pipeline.py
├── STEP_ORDER = ["clean", "impute", "enrich", "features", "score"]   # canonical order
├── DEFAULT_STEPS = ["clean", "impute", "features", "score"]          # "all" excludes enrich
├── normalize_steps(requested: list[str]) -> list[str]
│     # validates each name against STEP_ORDER (raises ValueError on unknown name),
│     # dedups, returns in canonical order
├── check_step_prerequisite(step: str) -> None
│     # raises FileNotFoundError with a clear message if step's required input is missing
├── run_pipeline(steps: list[str] | None = None, output_version: str = "v1") -> None
│     # steps=None -> DEFAULT_STEPS. For each step in canonical order:
│     #   1. check_step_prerequisite(step)
│     #   2. invoke its run_*_pipeline() (clean's (bool, str) -> RuntimeError on failure)
│     # If "score" ran: rename/target output to complexity_index_{output_version}.csv,
│     # then call validate_pipeline_output(...)
└── validate_pipeline_output(output_path: Path, raw_companies_path: Path) -> None

scripts/run_complexity_pipeline.py
      # argparse:
      #   --steps STEPS      comma-separated step names, or "all" (default: "all")
      #   --output-version V default: "v1"
      # parses --steps into a list, calls src.etl.pipeline.run_pipeline(steps, output_version)
      # catches any exception -> prints it -> sys.exit(1); success -> exit 0
```

`run_pipeline` passes `output_version` through to `run_scoring_pipeline`'s `output_path` param (only when `score` is in the requested steps) rather than `pipeline.py` renaming a file after the fact — `score.py`'s own path-construction logic is reused, not duplicated.

## Testing

- `normalize_steps`: dedup/reordering; rejects unknown step names; confirms `"all"`/`None` resolves to `DEFAULT_STEPS` (excludes `enrich`); confirms explicit `enrich` inclusion works.
- `check_step_prerequisite`: raises `FileNotFoundError` with the expected message when a step's input is missing; no-op when present. One case per step.
- `run_cleaning_pipeline` param test: passing `input_dir`/`output_dir` to a `tmp_path` fixture produces output in the given `output_dir` instead of the real `CLEANED_DIR` (existing no-arg call still defaults correctly — regression check).
- Clean-step failure translation: `run_pipeline` raises `RuntimeError` with the original message when `run_cleaning_pipeline` returns `(False, "some message")` (via monkeypatch).
- `validate_pipeline_output`: passes on a valid fixture CSV; raises on row-count mismatch, out-of-range score, or null `complexity_score`.
- Integration test for `run_pipeline`: hand-built fixture files at each stage under `tmp_path` (small raw CSVs, or starting mid-chain with a features parquet), run a subset of steps (e.g. `["features", "score"]`), assert final CSV shape/values and that `output_version` is reflected in the filename — mirrors the existing `test_run_scoring_pipeline_end_to_end` pattern (`tests/test_score.py:225`).
- CLI test (`scripts/run_complexity_pipeline.py`): argparse parsing of `--steps` (comma list, `"all"`, invalid name → non-zero exit with error message) and `--output-version`; exercised via `subprocess` or by importing the script's `main()`/arg-parsing function directly.

## Output

- `src/etl/pipeline.py` (new)
- `scripts/run_complexity_pipeline.py` (new)
- `tests/test_pipeline.py` (new)
- `src/etl/clean.py`: `run_cleaning_pipeline()` gains optional `input_dir`/`output_dir` params (additive)
- Roadmap checklist item 8 marked complete; "Next Immediate Actions" updated to point at Phase 9 (Validation & Analysis).

## Out of Scope

- Any change to scoring logic, caps, or weights in `score.py` (Phase 7 calibration gap remains open — separate follow-up per that spec's "Open Question").
- Versioning intermediate step directories (`step1_cleaned/`, etc.) — only the final score CSV is versioned (Decision 3).
- Parallel/async step execution — steps run sequentially; no current need for concurrency.
- Automatic re-running of `enrich` as part of routine pipeline runs (Decision 1).
