# Phase 11 Documentation & Reproducibility — Design

**Status:** Approved
**Date:** 2026-07-14
**Roadmap:** `documentation/plan_complexity_metric/roadmap.md`, checklist item 11 ("Documentation & reproducibility") — the final phase.

## Context

By the end of Phase 9.5, the project has a complete, tested, versioned pipeline (`src/etl/`), two analysis artifacts (`notebooks/complexity_analysis.ipynb`, `output/complexity_dashboard_v2.html`), and thorough phase-by-phase documentation (`documentation/plan_complexity_metric/roadmap.md`, `objectives_and_metrics.md`, and per-phase spec docs under `docs/superpowers/specs/`). What's missing is a single entry point: `README.md` is still the generic project-scaffold template from before any of this work started — it never mentions the Complexity Index, has no pipeline usage instructions, and its "Project Structure" tree doesn't reflect the real repository.

Two other checklist items were investigated before writing this spec and found already substantially satisfied or newly gapped:
- **"Version control all outputs"**: already done. `git ls-files` confirms `data/processed/scores/complexity_index_v1.csv`, `complexity_index_v2.csv`, `output/complexity_dashboard_v1.html`, `complexity_dashboard_v2.html`, and all intermediate `data/processed/` directories are tracked. No action needed.
- **"Write minimal test suite"**: mostly already done (`tests/test_clean.py`, `test_enrich.py`, `test_features.py`, `test_score.py`, `test_pipeline.py`, `test_run_complexity_pipeline.py`, `test_generate_dashboard.py` — 114 tests total), but `src/etl/impute.py` (a core pipeline module with 6 real functions, used in production exactly like its already-tested siblings) has zero dedicated unit tests — only indirect, mocked coverage via `test_pipeline.py`'s orchestration tests. This is a real, closeable gap.

## Decisions

1. **README.md gets a full rewrite** of its content (not a small addition) — replacing the generic template with a Complexity-Index-specific document. Structure: Project Overview, Quickstart (setup + pipeline/notebook/dashboard commands), Data Versioning, Project Structure (updated to the real tree), Known Limitations & Future Work, Testing, and links to the deeper docs (`roadmap.md`, `objectives_and_metrics.md`, spec docs) rather than duplicating their content.
2. **Depth: substantial overview, not a bare pointer.** A newcomer should be able to get oriented and run the full pipeline/notebook/dashboard from the README alone, without needing to read every phase's spec doc first — but the README defers to `objectives_and_metrics.md` and the roadmap for exhaustive detail (formula internals, full success-metric tables, phase-by-phase history) rather than re-explaining them.
3. **Close the `impute.py` test gap.** New file `tests/test_impute.py`, matching the established style/depth of `tests/test_clean.py` and `tests/test_score.py` (one or two tests per function covering main behavior plus edge cases, hand-built small fixture DataFrames, not the real 4,844-row dataset). No changes to `impute.py`'s logic — this is coverage-only, consistent with the phase's "documentation & reproducibility" framing (a codebase without tests for one of its core modules isn't fully reproducible/verifiable).
4. **Known Limitations section content** (real, already-documented facts, consolidated for a newcomer, not re-derived): team-size correlation r=0.103 and score-distribution spread σ=11.95, both still short of the objectives doc's original (now-relaxed) targets even after the Phase 9.5 revision, with the diagnostic rationale linked; the Phase 8 known gap where `--steps all`'s default step selection doesn't reach `features` through fresh `impute` output unless `enrich` is explicitly included; the pre-existing NaN `slug` values (ids 382, 599, 1189) noted since Phase 6.
5. **Data Versioning section content**: `complexity_index_v1.csv` = Phase 7's original 50/50 technical/practical calibration (historical, preserved, not the current default); `complexity_index_v2.csv` = Phase 9.5's revised 30/70 calibration (current default, what the notebook and dashboard now analyze); how to produce a new version via `scripts/run_complexity_pipeline.py --output-version vN`; the same versioning convention applies to `output/complexity_dashboard_vN.html` (regenerated manually per version, not auto-versioned by the CLI).

## Architecture

No new architecture — this phase touches documentation and one new test file, no changes to any production module's logic.

```
README.md                    — full rewrite (Decisions 1-2, 4-5)
tests/test_impute.py         — new file (Decision 3), covers:
  extract_first_sentence         — NaN/non-string, empty, short-abbreviation
                                    fallback, normal sentence, no-terminator cases
  impute_oneliner_from_description — imputes when longDescription present,
                                    leaves existing oneLiner untouched
  add_founder_count              — correct aggregation, zero-fill for no-founder companies
  create_enrichment_priorities   — status/batch/missing-field scoring, sort order
  validate_imputation            — passes on valid input; raises on row-count
                                    change, overwritten oneLiner, negative founder_count
  run_imputation_pipeline        — tmp_path integration test, same pattern as
                                    tests/test_clean.py's pipeline test
documentation/plan_complexity_metric/roadmap.md — mark Phase 11 complete
```

## Testing

- `tests/test_impute.py`'s own tests ARE the testing deliverable for this phase — no meta-tests needed.
- Acceptance: full project test suite (114 existing + new `test_impute.py` tests) passes.
- README changes have no automated test (it's prose) — acceptance is a manual read-through confirming the documented commands are real and correct (verified by actually running them during implementation, not just written from memory).

## Out of Scope

- Any change to `impute.py`'s actual logic — coverage-only, per Decision 3.
- Re-litigating or re-tuning the Phase 9.5 rubric — the Known Limitations section documents the current state, it doesn't reopen the decision.
- Adding tests for `scripts/analyze_raw_data.py` or `scripts/todo_cli.py` — these are exploratory/tooling utilities outside the core reproducible pipeline, not in the roadmap's stated scope for this phase.
- A CHANGELOG or release-notes file — not requested, not part of the roadmap's stated Phase 11 checklist.
