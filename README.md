# Y Combinator Complexity Index

A reproducible pipeline that scores 4,844 Y Combinator companies on a 0-100 **Complexity Index**, combining Technical difficulty (building the core technology) and Practical/Market difficulty (executing in the market) into one comparable metric per company.

## What This Measures

Each company gets three scores:
- **`technical_score`** (0-30) — deep-tech tags, R&D-vocabulary in the company description, founder background (PhDs, prior research-institution experience)
- **`practical_score`** (0-70) — regulated industry, market type (B2B/B2C/marketplace), geography & operations
- **`complexity_score`** (0-100) — the sum of the two

The 30/70 split (not 50/50) is a deliberate revision made in Phase 9.5, after diagnostics found that most YC companies carry no deep-tech signal at all — a 50-point technical budget was mostly wasted on zeros for about half the dataset. See [Data Versioning](#data-versioning) and [Known Limitations](#known-limitations--future-work) below, and `documentation/plan_complexity_metric/objectives_and_metrics.md` for the full scoring methodology and success-metric definitions.

## Quickstart

### Prerequisites
- Python 3.12 or higher
- pip (Python package manager)

### Installation

```bash
git clone <repository-url>
cd y-combinator-analysis
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
```

### Run the pipeline

The full pipeline (clean → impute → enrich → features → score) is orchestrated by one CLI:

```bash
# Run everything (enrich is opt-in — see the --steps help text for why)
./.venv/Scripts/python.exe scripts/run_complexity_pipeline.py --steps all --output-version v3

# Or just recompute scores from existing features (fastest — skips scraping/cleaning)
./.venv/Scripts/python.exe scripts/run_complexity_pipeline.py --steps impute,features,score --output-version v3
```

This writes `data/processed/scores/complexity_index_v3.csv`. See [Data Versioning](#data-versioning) for what version number to use.

### Regenerate the analysis notebook

```bash
./.venv/Scripts/python.exe scripts/generate_complexity_analysis_notebook.py
./.venv/Scripts/python.exe -m jupyter nbconvert --to notebook --execute --inplace notebooks/complexity_analysis.ipynb
```

Produces `notebooks/complexity_analysis.ipynb` — score distribution, batch/status/industry breakdowns, a correlation heatmap, team-size correlation, and manual outlier review.

### Regenerate the dashboard

```bash
./.venv/Scripts/python.exe scripts/generate_dashboard.py
```

Produces `output/complexity_dashboard_v2.html` — a single self-contained, offline HTML file (no server needed). Open it directly in a browser. Includes an "About This Index" section, key findings, 6 interactive charts, and a searchable/filterable table of all 4,844 companies.

## Data Versioning

- **`complexity_index_v1.csv`** — the original Phase 7 calibration (50/50 technical/practical split). Preserved as the historical baseline; not the current default.
- **`complexity_index_v2.csv`** — the current default, from the Phase 9.5 rubric revision (30/70 split). This is what `notebooks/complexity_analysis.ipynb` and `output/complexity_dashboard_v2.html` currently analyze.
- To produce a new version, pass `--output-version vN` to `scripts/run_complexity_pipeline.py`. Nothing else is auto-versioned — if you generate a new score version, manually re-point and re-run `scripts/generate_complexity_analysis_notebook.py` / `scripts/generate_dashboard.py` against it if you want updated analysis artifacts (see each script's `SCORES_PATH` constant).

## Project Structure

```
y-combinator-analysis/
├── data/
│   ├── raw/                    # Raw YC CSVs (gitignored, not included)
│   └── processed/
│       ├── step1_cleaned/      # Phase 3 output
│       ├── step2_imputed/      # Phase 4 output
│       ├── step3_enriched/     # Phase 5 output (optional enrichment)
│       ├── features/           # Phase 6 output (complexity_features.parquet)
│       └── scores/             # Phase 7/9.5 output (complexity_index_v1.csv, v2.csv)
├── src/etl/                    # Pipeline modules: clean, impute, enrich, features, score, pipeline
├── scripts/                    # CLI entry points and notebook/dashboard generators
├── notebooks/                  # Jupyter analysis notebooks
├── output/                     # Generated dashboard HTML
├── tests/                      # pytest test suite (129 tests)
├── documentation/plan_complexity_metric/  # Roadmap, objectives & success metrics
├── docs/superpowers/specs/     # Per-phase design specs (full decision history)
└── requirements.txt
```

## Known Limitations & Future Work

- **Team-size correlation is weak.** Even after the Phase 9.5 revision, `complexity_score` correlates with log(team size) at only r=0.103 (Pearson) — up from r=0.035 pre-revision, but still far short of the objectives doc's original r>0.2 target. Diagnostics found no combination of the current 8 features reaches r>0.2; several technical-side features are even *negatively* correlated with team size in this dataset. This target has been formally relaxed rather than further chased — see `docs/superpowers/specs/2026-07-14-phase9.5-rubric-revision-design.md`.
- **Score distribution is narrower than originally targeted.** σ=11.95 after Phase 9.5 (up from σ=10.11), still short of the original σ≥15 target. About half of all companies have zero deep-tech signal (no tags, no R&D-vocabulary keywords, no founder-background indicators) — real "no signal" mass in the data, not a tuning failure. Also formally relaxed rather than further chased.
- **`--steps all` has a known ordering gap** (Phase 8): `DEFAULT_STEPS` excludes `enrich`, but `features` always reads from `enrich`'s output directory (`step3_enriched/`), not `impute`'s. A default `--steps all` run regenerates fresh `impute` output that never reaches the final index unless `enrich` is explicitly included in `--steps`. See `scripts/run_complexity_pipeline.py --help` for the full explanation.
- **A handful of pre-existing NaN `slug` values** (company ids 382, 599, 1189) have been present since Phase 6 — unrelated to scoring, doesn't affect any score column.
- **Possible future work:** investigate the batch-over-time complexity trend observed in Phase 9 (rising from ~19 in the earliest batches to ~34 in the most recent, cause undiagnosed); add features beyond the current 8 that might better predict team size if that correlation is ever revisited.

## Testing

```bash
./.venv/Scripts/python.exe -m pytest -v
```

129 tests covering every `src/etl/` module (clean, impute, enrich, features, score, pipeline) and the dashboard/notebook generator scripts.

## Further Reading

- `documentation/plan_complexity_metric/roadmap.md` — full phase-by-phase project history and status
- `documentation/plan_complexity_metric/objectives_and_metrics.md` — complete scoring methodology, success-metric definitions, and rationale
- `docs/superpowers/specs/` — one design spec per phase, with full decision rationale (including diagnostic investigations behind the Phase 9.5 rubric revision)

## License

This project is for educational and research purposes.
