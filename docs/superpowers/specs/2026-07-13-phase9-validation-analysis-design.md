# Phase 9 Validation & Analysis — Design

**Status:** Approved
**Date:** 2026-07-13
**Roadmap:** `documentation/plan_complexity_metric/roadmap.md`, checklist item 9 ("Validation & analysis")

## Context

Phase 8 (`src/etl/pipeline.py` + `scripts/run_complexity_pipeline.py`) produced the reproducible ETL orchestrator and regenerated `data/processed/scores/complexity_index_v1.csv` (4,844 companies, 14 columns: `id, slug, name, batch, status`, 6 bucket scores, `technical_score`, `practical_score`, `complexity_score`).

Phase 7's calibration notebook (`notebooks/score_design.ipynb`) already ran a preliminary correlation/distribution/outlier check and found the index misses two of the objectives doc's own success criteria by a wide margin:
- Correlation with log(team size): Pearson r = 0.035, Spearman r = 0.050 (target: r > 0.2)
- Distribution std: 10.11 (target: ≥ 15)
- Manual top/bottom-25 review looked intuitively sensible (biotech/deep-tech dominates the top, consumer/education the bottom)

Per Phase 7's spec, this gap was flagged but deliberately not fixed — "a follow-up brainstorming pass to revise the caps/weights is needed before this index is treated as validated." The roadmap named Phase 9 as "the natural point to decide whether to fix it."

## Decisions

1. **Scope: analyze only, decide after.** Phase 9 builds the validation notebook per the roadmap's original checklist (distribution, correlation, batch/status/industry breakdown, outlier review) and explicitly re-surfaces the calibration gap with fresh Phase-9-derived numbers in its Findings section. It does **not** redesign `score.py`'s weights/caps in this pass. If the fresh numbers confirm the gap, revising the rubric is a distinct follow-up brainstorming pass with its own spec (a "Phase 7.5" or "Phase 9.5"), not bundled into this one.
2. **Re-run team-size correlation and outlier review fresh**, rather than citing Phase 7's `score_design.ipynb` numbers. `complexity_analysis.ipynb` is self-contained and is the single authoritative validation artifact for the index — a reader shouldn't need to cross-reference the Phase 7 calibration notebook to see the full picture.
3. **Industry grouping: explode on industry.** `industries_enriched.csv` has 8,838 rows for 4,844 companies (most companies carry multiple industry tags). For the "complexity by industry" breakdown, each company contributes its `complexity_score` to every industry group it's tagged with (matches how Phase 6 already treats multi-tag fields elsewhere in the pipeline). No "primary industry" simplification.
4. **No new `src/` module.** Unlike Phase 7 (where `score.py` was pulled forward because Phase 8 needed to orchestrate it), Phase 9 has no downstream pipeline step that consumes its logic — it's terminal analysis. All logic lives in the notebook; nothing here needs to be reusable or unit-tested as a module.
5. **Verification bar:** since there's no unit-testable logic, the acceptance check is that the notebook executes top-to-bottom without error (`jupyter nbconvert --execute` or equivalent), the same bar Phase 7's `score_design.ipynb` met.
6. **Minimum sample size for industry breakdown:** industries with very few tagged companies produce noisy single-company "averages." The industry bar chart filters to industries with at least 20 tagged companies (chosen from the real distribution — `B2B` at 2,325 down to long-tail industries with single-digit counts; 20 is a reasonable floor that still keeps ~15-20 industries visible without single-company noise, per the `industry.value_counts()` check done during brainstorming).

## Data Sources & Joins

- `data/processed/scores/complexity_index_v1.csv` — base table (scores, batch, status).
- `data/processed/step3_enriched/companies_enriched.csv` — `teamSize`, joined on `id`; log1p-transformed before correlation (heavily right-skewed: median 7, max 8,600 — same transform Phase 7 used).
- `data/processed/step3_enriched/industries_enriched.csv` — `id, industry`, joined on `id` with an explode (left join keeps companies with no industry tag, if any, out of the industry breakdown but not out of other sections).
- `data/processed/features/complexity_features.parquet` — the 8 raw features, joined on `id`, needed for the full correlation heatmap (raw features + bucket scores + totals).

## Notebook Structure (`notebooks/complexity_analysis.ipynb`)

1. **Setup & load** — read `complexity_index_v1.csv`, join `teamSize` (companies_enriched), join exploded industry tags, join raw features (complexity_features.parquet). No scoring logic duplicated — analysis only, same convention as `score_design.ipynb`.
2. **Score distribution** — histograms of `complexity_score`, `technical_score`, `practical_score`; `describe()` and std vs. the σ≥15 target.
3. **Technical vs. Practical scatter** — scatter plot of `technical_score` vs. `practical_score`, noting their own correlation.
4. **Complexity by batch** — mean/median `complexity_score` per batch, plotted in chronological order (batches sorted S05→W24 by year/season, not alphabetically).
5. **Complexity by status** — mean `complexity_score` by `status` (Active/Inactive/Acquired/Public). Explicitly answers "are public companies more complex than average?" with a caveat that Public has only 19 companies (small-sample noise risk called out in the write-up).
6. **Complexity by industry** — exploded groupby mean/count per industry, bar chart filtered to industries with ≥20 tagged companies (Decision 6).
7. **Correlation heatmap** — matrix across all 8 raw features, 6 bucket scores, and `technical_score`/`practical_score`/`complexity_score`.
8. **Team-size correlation** — fresh Pearson/Spearman of `complexity_score` vs. log1p(teamSize), independently re-derived (Decision 2).
9. **Validation questions** — using the exploded industry join: do companies tagged `Healthcare`/biotech-adjacent industries skew high on `technical_score`? Do companies tagged `Fintech` skew high on `practical_score`/`regulated_score`? Reported as group means compared to the overall mean.
10. **Manual review of outliers** — fresh top-25/bottom-25 by `complexity_score`, printed with their bucket breakdown, eyeballed against the objectives doc's "pass manual review" criterion.
11. **Findings** — written summary covering every section above, explicitly re-stating the Phase 7 calibration gap in light of this phase's fresh numbers (confirmed, worsened, or improved), and stating plainly that a rubric revision — if warranted — is a separate follow-up brainstorming pass with its own spec, out of scope here.

## Output

- `notebooks/complexity_analysis.ipynb`, executed with outputs saved (not a template — same convention as `score_design.ipynb`).
- Roadmap checklist item 9 marked complete; roadmap's "Known gap" note under item 7 updated to reference Phase 9's fresh confirmation/numbers; "Next Immediate Actions" updated to point at Phase 10 (Documentation & reproducibility) — or, if Phase 9's findings warrant it, an inserted Phase 9.5 (rubric revision) ahead of Phase 10. That decision itself is made at the end of Phase 9 implementation based on the actual fresh numbers, not prejudged here.

## Out of Scope

- Any change to `src/etl/score.py`'s weights, caps, or formula (that's the potential Phase 9.5/7.5 follow-up).
- A "primary industry" per-company simplification (rejected — see Decision 3).
- New reusable `src/` analysis functions (notebook-only — see Decision 4).
- Re-fixing `founder_phd_count`'s near-zero variance (still a Phase 6 concern, unchanged from Phase 7's spec).
