# Phase 7 Scoring Rubric — Design

**Status:** Approved
**Date:** 2026-07-10
**Roadmap:** `documentation/plan_complexity_metric/roadmap.md`, checklist item 7 ("Scoring rubric design")

## Context

Phase 6 (`src/etl/features.py`) produced `data/processed/features/complexity_features.parquet`: one row per company (4,844 rows) with 8 raw complexity signals — 4 technical, 4 practical. All are raw counts, 0/1 flags, or small ordinals (no `NaN`s).

Phase 7 converts those 8 raw features into a single 0-100 Complexity Index, split into a Technical component (0-50) and a Practical component (0-50), per `documentation/plan_complexity_metric/objectives_and_metrics.md`.

### Actual feature distributions (from the real Phase 6 output)

| Feature | p90 | p95 | p99 | max | Notes |
|---|---|---|---|---|---|
| `deep_tech_tag_count` | 2 | 2 | 4 | 5 | |
| `description_tech_score` | 1 | 1 | 3 | 10 | long tail, one outlier at 10 |
| `founder_phd_count` | 0 | 0 | 0 | 1 | **near-dead**: nonzero for only 3/4,844 companies |
| `research_company_experience` | 1 | 2 | 2 | 4 | |
| `regulated_industry` | 1 | 1 | 1 | 1 | binary, 32% of companies = 1 |
| `market_type_score` | 3 | 3 | 3 | 3 | ordinal 0-3, already clean |
| `international_operations` | 0 | 1 | 2 | 7 | mostly 0 (93%) |
| `operational_intensity` | 2 | 2 | 3 | 5 | |

`founder_phd_count`'s near-zero variance is a known Phase 6 limitation (the `PHD_PATTERN` regex rarely matches literal `field_of_study` text in the schools data). Fixing the regex is out of scope for Phase 7 — it's a Phase 6 concern. Phase 7 instead folds it into a combined founder-background bucket so its point budget isn't wasted on a near-constant column (see below).

## Decisions

1. **Scaling method:** capped linear scaling. Each raw feature (or combination) is linearly scaled from 0 to a cap, then multiplied to fill its point budget. Values above the cap clip at the budget max. Caps are chosen from the p95-p99 distribution above, not the absolute max, so rare outliers don't waste the scale on a handful of companies.
2. **`founder_phd_count` handling:** merged with `research_company_experience` into one "founder background" bucket (0-15 pts) rather than kept as its own 0-15 bucket, since it alone carries almost no signal.
3. **Practical budget shape:** the original roadmap sketch proposed 4 practical sub-scores (Regulated 15, Market type 15, Geography/ops 10, GTM complexity 10), but Phase 6 only produced 4 practical features with no distinct "GTM complexity" signal. Rather than force an artificial 4th bucket, `international_operations` and `operational_intensity` are combined into one "Geography & Operations" bucket (0-20 pts), each contributing up to half.
4. **Deliverable:** a tested Python module (`src/etl/score.py`), built with TDD in the same style as `src/etl/features.py` (pure `compute_*` functions with overridable defaults, an orchestrator, a `validate_*` function, and a pipeline entry point) — not just a notebook. This diverges from the original roadmap text (which listed `notebooks/score_design.ipynb` as the sole Phase 7 output and deferred `src/etl/score.py` to Phase 8), in order to stay consistent with how Phases 5-6 were actually built and to avoid Phase 8 having to port notebook logic into a module from scratch. The notebook still gets built, but only for calibration/analysis — no scoring logic lives in it.

## Scoring Formula

All inputs come from `complexity_features.parquet` columns.

### Technical (0-50)

```
deep_tech_score            = min(deep_tech_tag_count, 3) / 3 * 20
description_score          = min(description_tech_score, 3) / 3 * 15
founder_background_score   = min(2*founder_phd_count + research_company_experience, 4) / 4 * 15

technical_score = deep_tech_score + description_score + founder_background_score
```

### Practical (0-50)

```
regulated_score  = regulated_industry * 15                          # binary: 0 or 15
market_type_pts  = market_type_score * 5                            # 0-3 -> 0/5/10/15
geo_ops_score    = min(international_operations, 2) / 2 * 10
                  + min(operational_intensity, 2) / 2 * 10

practical_score = regulated_score + market_type_pts + geo_ops_score
```

### Total

```
complexity_score = technical_score + practical_score   # 0-100, rounded to 1 decimal
```

All caps/weights are module-level constants passed as overridable default parameters to each `compute_*_score` function, matching the Phase 6 convention (tests exercise the scaling *logic* independent of the exact curated cap values).

## Architecture

```
src/etl/score.py
├── compute_deep_tech_score(features_df, cap=3, points=20) -> pd.DataFrame  # ['id', 'deep_tech_score']
├── compute_description_score(features_df, cap=3, points=15) -> pd.DataFrame
├── compute_founder_background_score(features_df, phd_weight=2, cap=4, points=15) -> pd.DataFrame
├── compute_regulated_score(features_df, points=15) -> pd.DataFrame
├── compute_market_type_pts(features_df, points_per_level=5) -> pd.DataFrame
├── compute_geo_ops_score(features_df, intl_cap=2, ops_cap=2, intl_points=10, ops_points=10) -> pd.DataFrame
├── build_score_table(features_df) -> pd.DataFrame
│     # columns: id, slug, name, batch, status,
│     #          deep_tech_score, description_score, founder_background_score,
│     #          regulated_score, market_type_pts, geo_ops_score,
│     #          technical_score, practical_score, complexity_score
├── validate_scores(features_df, scores_df) -> None
│     # row count / id set match; no NaNs; technical_score in [0,50];
│     # practical_score in [0,50]; complexity_score in [0,100]
└── run_scoring_pipeline(input_path=None, output_path=None) -> None
      # reads complexity_features.parquet, writes
      # data/processed/scores/complexity_index_v1.csv
```

Each `compute_*_score` function is pure: it takes the small subset of `features_df` columns it needs and returns a `(id, <bucket>_score)` frame for every input row (no filtering — unlike Phase 6's "absent = 0" convention, since every company always gets a score, even if 0). `build_score_table` merges them all on `id` and sums into the three top-level scores.

## Testing

- One unit test per `compute_*_score` function, covering: a zero-input case, a below-cap case, an at-cap case, and an above-cap case (clipping behavior) — small hand-built fixture frames, not the real feature table.
- `build_score_table` test: hand-built 2-3 row fixture with known expected `technical_score`/`practical_score`/`complexity_score` (arithmetic worked out by hand in the test, similar to Phase 6's `test_build_feature_table_computes_expected_values_for_acme`).
- `validate_scores` tests: passes on a valid table; raises on row-count mismatch; raises on an out-of-range score.
- Integration test for `run_scoring_pipeline`: writes a small fixture parquet to a tmp dir, runs the pipeline, reads back the CSV, checks shape and a couple of known values.

## Calibration Notebook (`notebooks/score_design.ipynb`)

Analysis only — imports `src/etl/score.py`, no scoring logic duplicated. Sections:

1. Run `build_score_table` on the real `complexity_features.parquet`.
2. Distribution: histogram of `complexity_score`, `technical_score` vs `practical_score` scatter.
3. Spot-check: pull a handful of well-known biotech/hardware companies (expect high `technical_score`) and fintech/insurance companies (expect high `regulated_score`/`practical_score`) by name and print their bucket breakdown.
4. Correlation check: merge in `teamSize` from `companies_enriched.csv` (log1p-transform first — heavily right-skewed, max 8,600 vs median 7), compute Pearson/Spearman correlation with `complexity_score` against the objectives doc's `r>0.2` target.
5. Distribution spread check against the objectives doc's `σ≥15` target.
6. Sensitivity pass: perturb each cap by ±1 and each bucket's point budget by ±20%, recompute scores, report Spearman rank correlation of the top-100-by-`complexity_score` between baseline and each perturbation (stability check, not a full grid search).
7. Manual review: print top 25 / bottom 25 companies by `complexity_score` for eyeballing against the objectives doc's "pass manual review" criterion.

Findings from steps 4-7 are recorded as notes in the notebook; no code changes are made based on them within Phase 7 (that would be a rubric-revision cycle, out of scope unless the numbers are badly off — see Open Question below).

## Output

- `data/processed/scores/complexity_index_v1.csv` — columns: `id, slug, name, batch, status, deep_tech_score, description_score, founder_background_score, regulated_score, market_type_pts, geo_ops_score, technical_score, practical_score, complexity_score`. Versioned filename per the roadmap's existing decision ("date-stamped CSVs + git tags").
- `notebooks/score_design.ipynb`.
- Roadmap checklist item 7 marked complete; "Next Immediate Actions" updated to point at Phase 8 (ETL pipeline / CLI wiring — `score.py` already exists at that point, so Phase 8 is orchestration only).

## Open Question

If the calibration notebook's correlation/distribution checks come back badly out of spec (e.g., `r` with team size near 0, or σ well under 15), this spec does not prescribe a fallback — that would require a follow-up brainstorming pass to revise the formula. This is called out explicitly rather than silently patched during implementation.

## Out of Scope

- Fixing `founder_phd_count`'s underlying regex/matching (Phase 6 concern).
- Wiring `score.py` into a CLI/orchestrator pipeline alongside `clean.py`/`impute.py`/`enrich.py`/`features.py` (Phase 8).
- Batch-relative or percentile-based normalization (rejected in favor of capped linear scaling — see Decisions).
