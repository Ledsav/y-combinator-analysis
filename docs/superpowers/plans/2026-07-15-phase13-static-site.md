# Phase 13: Static Site (Landing, Dashboard, Pipeline) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 3-page static site (landing, redesigned dashboard, ETL/scoring-engine pipeline diagrams) hosted on GitHub Pages, reading only from pre-exported JSON derived from the already-computed `complexity_index_v2.csv`.

**Architecture:** One Python data-export script reshapes existing pipeline outputs into `site/data/*.json`. Three hand-authored static HTML pages share one CSS file (`site/assets/style.css`) and D3-based chart helpers (`site/assets/charts.js`). No framework, no bundler, no build step. A GitHub Actions workflow publishes `site/` to GitHub Pages.

**Tech Stack:** Python 3.12 + pandas (data export only), vanilla HTML/CSS/JS, D3.js v7 (via CDN `<script>` tag), Google Fonts CDN (Fraunces, IBM Plex Sans, IBM Plex Mono), GitHub Actions (`actions/deploy-pages`).

## Global Constraints

- Design tokens (from spec §3): `--color-paper: #FBFAF6`, `--color-ink: #1B1B18`, `--color-ink-muted: #5C594F`, `--color-technical: #2B4C7E`, `--color-practical: #C08A2E`. No third accent color.
- Fonts: Fraunces (display/headlines only), IBM Plex Sans (body), IBM Plex Mono (all numerals/data/labels).
- No changes to `src/etl/`, `scripts/generate_dashboard.py`, `scripts/generate_complexity_analysis_notebook.py`, or `output/complexity_dashboard_v1.html`/`v2.html` — those stay exactly as they are.
- No scoring recomputation — `scripts/export_site_data.py` only reads `data/processed/scores/complexity_index_v2.csv` (already computed) and reshapes it.
- Copy rule (site-wide): describe current values and current rationale only. No phase numbers, no "revised from," no before/after framing anywhere in page copy.
- The signature split-bar element (denim technical segment + gold practical segment + Plex Mono total) appears in: nav mark, landing stat tiles, dashboard KPI tiles, every company-explorer row, and the pipeline page's scoring-engine diagram.
- Palette must pass `dataviz`'s `scripts/validate_palette.js` (light mode) before the site is considered done (Task 8).
- All copy follows frontend-design's writing guidance: active voice, plain terms, no filler.

---

## Task 1: Data export script (`scripts/export_site_data.py`)

**Files:**
- Create: `scripts/export_site_data.py`
- Test: `tests/test_export_site_data.py`

**Interfaces:**
- Consumes: `scripts.generate_dashboard.aggregate_company_industries(scores_df, industries_df) -> pd.DataFrame` (existing, columns `id`, `industries_list`, `industries`), `scripts.generate_dashboard.batch_sort_key(batch: str) -> Tuple[int, int]` (existing), `src.etl.rubric.load_rubric(path: Path) -> dict` (existing, returns `{"buckets": [...]}`).
- Produces: `build_company_records(scores_df, company_industries_df, team_sizes_df) -> List[dict]`, `build_distribution_bins(scores_df, bin_count=30) -> List[dict]`, `build_mean_by_batch(scores_df) -> List[dict]`, `build_mean_by_status(scores_df) -> List[dict]`, `build_industry_ranking(industry_exploded_df, min_count=20, top_n=5) -> Dict[str, List[dict]]`, `build_correlation_matrix(scores_df) -> Dict[str, Any]`, `build_summary(scores_df, industry_exploded_df, generated_at) -> Dict[str, Any]`, `build_pipeline_config(rubric) -> Dict[str, Any]`, `write_json(path, data) -> None`. These are what Task 8's `main()` invocation and any future consumer rely on by exact name.

Known real schema (verified against the actual files, not assumed): `data/processed/scores/complexity_index_v2.csv` columns are `id,slug,name,batch,status,deep_tech_score,description_score,founder_background_score,regulated_score,market_type_score,international_operations_score,operational_intensity_score,technical_score,practical_score,complexity_score`. `data/processed/step3_enriched/industries_enriched.csv` columns are `id,industry`. `data/processed/step3_enriched/companies_enriched.csv` columns include `id,teamSize` (among others).

- [ ] **Step 1: Write failing tests for `build_company_records`**

Create `tests/test_export_site_data.py`:

```python
import json
import math

import pandas as pd
import pytest

from scripts.export_site_data import (
    build_company_records,
    build_correlation_matrix,
    build_distribution_bins,
    build_industry_ranking,
    build_mean_by_batch,
    build_mean_by_status,
    build_pipeline_config,
    build_summary,
    write_json,
)


def test_build_company_records_produces_json_safe_records_with_industries_list():
    scores_df = pd.DataFrame(
        {
            "id": [1, 2],
            "slug": ["acme", "beta"],
            "name": ["Acme", "Beta"],
            "batch": ["W24", "S23"],
            "status": ["Active", "Active"],
            "technical_score": [10.0, 20.0],
            "practical_score": [5.0, 15.0],
            "complexity_score": [15.0, 35.0],
        }
    )
    company_industries_df = pd.DataFrame(
        {
            "id": [1, 2],
            "industries": ["Fintech", ""],
            "industries_list": [["Fintech"], []],
        }
    )
    team_sizes_df = pd.DataFrame({"id": [1, 2], "teamSize": [5.0, float("nan")]})

    records = build_company_records(scores_df, company_industries_df, team_sizes_df)

    assert len(records) == 2
    acme = next(r for r in records if r["slug"] == "acme")
    assert acme["industries_list"] == ["Fintech"]
    assert acme["teamSize"] == 5.0
    beta = next(r for r in records if r["slug"] == "beta")
    assert beta["teamSize"] is None
    assert "NaN" not in json.dumps(records)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_export_site_data.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.export_site_data'`

- [ ] **Step 3: Implement `build_company_records` and its module skeleton**

Create `scripts/export_site_data.py`:

```python
"""
Phase 13: exports the already-computed complexity index into the small,
pre-aggregated JSON files site/index.html, site/dashboard.html, and
site/pipeline.html fetch at runtime. Performs no scoring or recomputation
-- pure read-and-reshape, following the same NaN-to-null pattern as
scripts/generate_dashboard.py's build_company_records.

Run: ./.venv/Scripts/python.exe scripts/export_site_data.py
"""

import datetime
import json
import math
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from scripts.generate_dashboard import aggregate_company_industries, batch_sort_key
from src.etl.rubric import load_rubric

REPO_ROOT = Path(__file__).resolve().parents[1]
SCORES_PATH = REPO_ROOT / "data" / "processed" / "scores" / "complexity_index_v2.csv"
INDUSTRIES_PATH = REPO_ROOT / "data" / "processed" / "step3_enriched" / "industries_enriched.csv"
COMPANIES_PATH = REPO_ROOT / "data" / "processed" / "step3_enriched" / "companies_enriched.csv"
RUBRIC_PATH = REPO_ROOT / "config" / "rubric_v2.yaml"
SITE_DATA_DIR = REPO_ROOT / "site" / "data"

INDUSTRY_MIN_COUNT = 20


def _clean_json(value: Any) -> Any:
    """Replace float NaN with None -- json.dumps' bare NaN token is not
    valid JSON and a browser's JSON.parse rejects it."""
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def build_company_records(
    scores_df: pd.DataFrame, company_industries_df: pd.DataFrame, team_sizes_df: pd.DataFrame
) -> List[dict]:
    """One dict per company: id, slug, name, batch, status, industries_list,
    teamSize, technical_score, practical_score, complexity_score. JSON-safe."""
    merged = scores_df.merge(company_industries_df, on="id", how="left")
    merged = merged.merge(team_sizes_df[["id", "teamSize"]], on="id", how="left")
    columns = [
        "id",
        "slug",
        "name",
        "batch",
        "status",
        "industries_list",
        "teamSize",
        "technical_score",
        "practical_score",
        "complexity_score",
    ]
    records = merged[columns].to_dict(orient="records")
    for record in records:
        for key, value in record.items():
            record[key] = _clean_json(value)
    return records
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_export_site_data.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add scripts/export_site_data.py tests/test_export_site_data.py
git commit -m "feat: add build_company_records for site data export"
```

- [ ] **Step 6: Write failing tests for the aggregation functions**

Append to `tests/test_export_site_data.py`:

```python
def test_build_distribution_bins_counts_all_rows_across_bins():
    scores_df = pd.DataFrame({"complexity_score": [0.0, 10.0, 20.0, 30.0, 100.0]})

    bins = build_distribution_bins(scores_df, bin_count=10)

    assert sum(b["count"] for b in bins) == 5
    assert all({"start", "end", "count"} <= set(b.keys()) for b in bins)


def test_build_mean_by_batch_orders_chronologically():
    scores_df = pd.DataFrame(
        {"batch": ["S12", "W12", "S11"], "complexity_score": [30.0, 20.0, 10.0]}
    )

    result = build_mean_by_batch(scores_df)

    assert [r["batch"] for r in result] == ["S11", "W12", "S12"]
    assert [r["mean_complexity"] for r in result] == [10.0, 20.0, 30.0]


def test_build_mean_by_status_sorts_descending():
    scores_df = pd.DataFrame(
        {"status": ["Active", "Active", "Inactive"], "complexity_score": [10.0, 30.0, 5.0]}
    )

    result = build_mean_by_status(scores_df)

    assert [r["status"] for r in result] == ["Active", "Inactive"]
    assert [r["mean_complexity"] for r in result] == [20.0, 5.0]


def test_build_industry_ranking_returns_top_and_bottom_above_min_count():
    industry_exploded_df = pd.DataFrame(
        {
            "industry": ["A", "A", "A", "B", "B", "B", "C"],
            "complexity_score": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 999.0],
        }
    )

    result = build_industry_ranking(industry_exploded_df, min_count=3, top_n=1)

    # C has only 1 company (< min_count=3), excluded even though it scores highest
    assert result["top"] == [{"industry": "B", "mean_complexity": 50.0, "count": 3}]
    assert result["bottom"] == [{"industry": "A", "mean_complexity": 20.0, "count": 3}]


def test_build_correlation_matrix_orders_bucket_columns_before_totals():
    scores_df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "deep_tech_score": [10.0, 20.0, 30.0],
            "technical_score": [10.0, 20.0, 30.0],
            "practical_score": [30.0, 20.0, 10.0],
            "complexity_score": [40.0, 40.0, 40.0],
        }
    )

    result = build_correlation_matrix(scores_df)

    assert result["columns"] == [
        "deep_tech_score",
        "technical_score",
        "practical_score",
        "complexity_score",
    ]
    assert len(result["values"]) == 4
    assert result["values"][0][1] == pytest.approx(1.0)
```

- [ ] **Step 7: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_export_site_data.py -v`
Expected: FAIL with `ImportError` (functions not yet defined)

- [ ] **Step 8: Implement the aggregation functions**

Append to `scripts/export_site_data.py`:

```python
def build_distribution_bins(scores_df: pd.DataFrame, bin_count: int = 30) -> List[dict]:
    """Histogram bins over complexity_score: [{start, end, count}, ...]."""
    binned = pd.cut(scores_df["complexity_score"], bins=bin_count, include_lowest=True)
    bin_counts = binned.value_counts(sort=False)
    return [
        {"start": round(interval.left, 2), "end": round(interval.right, 2), "count": int(count)}
        for interval, count in bin_counts.items()
    ]


def build_mean_by_batch(scores_df: pd.DataFrame) -> List[dict]:
    """Chronologically ordered [{batch, mean_complexity}, ...]."""
    summary = scores_df.groupby("batch")["complexity_score"].mean().reset_index()
    summary["sort_key"] = summary["batch"].apply(batch_sort_key)
    summary = summary.sort_values("sort_key").drop(columns="sort_key")
    return [
        {"batch": row.batch, "mean_complexity": round(row.complexity_score, 2)}
        for row in summary.itertuples()
    ]


def build_mean_by_status(scores_df: pd.DataFrame) -> List[dict]:
    """Descending [{status, mean_complexity}, ...]."""
    summary = (
        scores_df.groupby("status")["complexity_score"]
        .mean()
        .sort_values(ascending=False)
        .reset_index()
    )
    return [
        {"status": row.status, "mean_complexity": round(row.complexity_score, 2)}
        for row in summary.itertuples()
    ]


def build_industry_ranking(
    industry_exploded_df: pd.DataFrame, min_count: int = INDUSTRY_MIN_COUNT, top_n: int = 5
) -> Dict[str, List[dict]]:
    """Top-N and bottom-N industries by mean complexity_score, among those
    with >= min_count companies. {"top": [...], "bottom": [...]}."""
    summary = (
        industry_exploded_df.groupby("industry")["complexity_score"]
        .agg(["mean", "count"])
        .query("count >= @min_count")
        .sort_values("mean", ascending=False)
        .reset_index()
    )
    records = [
        {"industry": row.industry, "mean_complexity": round(row.mean, 2), "count": int(row.count)}
        for row in summary.itertuples()
    ]
    bottom = list(reversed(records[-top_n:])) if records else []
    return {"top": records[:top_n], "bottom": bottom}


def build_correlation_matrix(scores_df: pd.DataFrame) -> Dict[str, Any]:
    """Trimmed correlation matrix: bucket-score columns (any column ending
    in _score other than the 3 totals) followed by the 3 totals.
    {"columns": [...], "values": [[...], ...]}."""
    totals = ["technical_score", "practical_score", "complexity_score"]
    score_cols = [c for c in scores_df.columns if c.endswith("_score")]
    bucket_cols = [c for c in score_cols if c not in totals]
    ordered_cols = bucket_cols + totals
    corr = scores_df[ordered_cols].corr().round(3)
    return {"columns": ordered_cols, "values": corr.values.tolist()}
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_export_site_data.py -v`
Expected: PASS (6 tests)

- [ ] **Step 10: Commit**

```bash
git add scripts/export_site_data.py tests/test_export_site_data.py
git commit -m "feat: add distribution/batch/status/industry/correlation aggregation for site export"
```

- [ ] **Step 11: Write failing tests for `build_summary` and `build_pipeline_config`**

Append to `tests/test_export_site_data.py`:

```python
def test_build_summary_includes_headline_stats_and_top_industry():
    scores_df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "batch": ["W24", "W24", "S23"],
            "status": ["Active", "Active", "Inactive"],
            "deep_tech_score": [5.0, 10.0, 0.0],
            "technical_score": [10.0, 20.0, 5.0],
            "practical_score": [10.0, 10.0, 5.0],
            "complexity_score": [20.0, 30.0, 10.0],
        }
    )
    industry_exploded_df = scores_df.assign(industry="Fintech")

    summary = build_summary(scores_df, industry_exploded_df, generated_at="2026-07-15")

    assert summary["generated_at"] == "2026-07-15"
    assert summary["company_count"] == 3
    assert summary["median_complexity"] == 20.0
    assert summary["top_industry"]["industry"] == "Fintech"
    assert "distribution_bins" in summary
    assert "mean_by_batch" in summary
    assert "correlation_matrix" in summary


def test_build_pipeline_config_maps_rubric_buckets_and_fixed_etl_steps():
    rubric = {
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
                "combine_params": {"features": {"founder_phd_count": 2}},
                "method": "linear_capped",
                "params": {"cap": 2, "points": 9},
            },
        ]
    }

    config = build_pipeline_config(rubric)

    assert [s["name"] for s in config["steps"]] == [
        "clean",
        "impute",
        "enrich",
        "features",
        "score",
    ]
    enrich_step = next(s for s in config["steps"] if s["name"] == "enrich")
    assert enrich_step["optional"] is True
    assert len(config["buckets"]) == 2
    assert config["buckets"][0]["raw_feature"] == "deep_tech_tag_count"
    assert config["buckets"][1]["combine"] == "weighted_sum"


def test_write_json_produces_parseable_file_with_no_nan_tokens(tmp_path):
    path = tmp_path / "out.json"

    write_json(path, {"a": 1, "b": None})

    parsed = json.loads(path.read_text(encoding="utf-8"))
    assert parsed == {"a": 1, "b": None}
```

- [ ] **Step 12: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_export_site_data.py -v`
Expected: FAIL with `ImportError` (`build_summary`, `build_pipeline_config`, `write_json` not yet defined)

- [ ] **Step 13: Implement `build_summary`, `ETL_STEPS`, `build_pipeline_config`, `write_json`, and `main`**

Append to `scripts/export_site_data.py`:

```python
def build_summary(
    scores_df: pd.DataFrame, industry_exploded_df: pd.DataFrame, generated_at: str
) -> Dict[str, Any]:
    """Everything the landing hero stats and dashboard charts need,
    pre-aggregated so the browser never re-derives them from 4,844 rows."""
    industry_ranking = build_industry_ranking(industry_exploded_df)
    top_industry = industry_ranking["top"][0]
    tp_corr = round(scores_df["technical_score"].corr(scores_df["practical_score"]), 3)
    return {
        "generated_at": generated_at,
        "company_count": int(len(scores_df)),
        "median_complexity": round(scores_df["complexity_score"].median(), 2),
        "sigma_complexity": round(scores_df["complexity_score"].std(), 2),
        "min_complexity": round(scores_df["complexity_score"].min(), 2),
        "max_complexity": round(scores_df["complexity_score"].max(), 2),
        "technical_practical_correlation": tp_corr,
        "top_industry": top_industry,
        "distribution_bins": build_distribution_bins(scores_df),
        "mean_by_batch": build_mean_by_batch(scores_df),
        "mean_by_status": build_mean_by_status(scores_df),
        "industry_ranking": industry_ranking,
        "correlation_matrix": build_correlation_matrix(scores_df),
    }


ETL_STEPS: List[Dict[str, Any]] = [
    {
        "name": "clean",
        "module": "src/etl/clean.py",
        "input_dir": "data/raw/",
        "output_dir": "data/processed/step1_cleaned/",
        "optional": False,
    },
    {
        "name": "impute",
        "module": "src/etl/impute.py",
        "input_dir": "data/processed/step1_cleaned/",
        "output_dir": "data/processed/step2_imputed/",
        "optional": False,
    },
    {
        "name": "enrich",
        "module": "src/etl/enrich.py",
        "input_dir": "data/processed/step2_imputed/",
        "output_dir": "data/processed/step3_enriched/",
        "optional": True,
    },
    {
        "name": "features",
        "module": "src/etl/features.py",
        "input_dir": "data/processed/step3_enriched/",
        "output_dir": "data/processed/features/",
        "optional": False,
    },
    {
        "name": "score",
        "module": "src/etl/score.py",
        "input_dir": "data/processed/features/",
        "output_dir": "data/processed/scores/",
        "optional": False,
    },
]


def build_pipeline_config(rubric: Dict[str, Any]) -> Dict[str, Any]:
    """Structured description of the 5 ETL steps and the rubric's buckets,
    for the pipeline page's diagram labels."""
    buckets = [
        {
            "name": bucket["name"],
            "dimension": bucket["dimension"],
            "raw_feature": bucket.get("raw_feature"),
            "combine": bucket.get("combine"),
            "combine_params": bucket.get("combine_params"),
            "method": bucket["method"],
            "params": bucket["params"],
        }
        for bucket in rubric["buckets"]
    ]
    return {"steps": ETL_STEPS, "buckets": buckets}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> None:
    scores_df = pd.read_csv(SCORES_PATH)
    industries_df = pd.read_csv(INDUSTRIES_PATH)
    companies_df = pd.read_csv(COMPANIES_PATH)
    rubric = load_rubric(RUBRIC_PATH)

    company_industries_df = aggregate_company_industries(scores_df, industries_df)
    industry_exploded_df = scores_df.merge(industries_df, on="id", how="left")
    team_sizes_df = companies_df[["id", "teamSize"]]
    generated_at = datetime.date.today().isoformat()

    write_json(
        SITE_DATA_DIR / "companies.json",
        build_company_records(scores_df, company_industries_df, team_sizes_df),
    )
    write_json(
        SITE_DATA_DIR / "summary.json",
        build_summary(scores_df, industry_exploded_df, generated_at),
    )
    write_json(SITE_DATA_DIR / "pipeline.json", build_pipeline_config(rubric))

    print(f"Wrote site data to {SITE_DATA_DIR}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 14: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_export_site_data.py -v`
Expected: PASS (9 tests total)

- [ ] **Step 15: Commit**

```bash
git add scripts/export_site_data.py tests/test_export_site_data.py
git commit -m "feat: add build_summary, build_pipeline_config, and main() to site data export"
```

---

## Task 2: Design system (`site/assets/style.css`, `site/assets/nav.js`) and nav shell

**Files:**
- Create: `site/assets/style.css`
- Create: `site/assets/nav.js`
- Create: `site/index.html` (nav shell only — Task 3 fills in the body)

**Interfaces:**
- Produces: CSS custom properties `--color-paper`, `--color-ink`, `--color-ink-muted`, `--color-technical`, `--color-practical`, `--color-surface`, `--color-rule`, `--radius-card`, `--space-1..6`, `--max-width`, and component classes `.site-nav`, `.split-bar`/`.split-bar__track`/`.split-bar__technical`/`.split-bar__practical`/`.split-bar__total`, `.stat-tile-row`/`.stat-tile`, `.card-row`/`.ticket-card`, `.chart-section`/`.chart-tooltip`/`.chart-legend`, `.explorer-table`, `.pipeline-flow`/`.pipeline-stage-card`/`.bucket-card`/`.callout-box`, `.site-footer` — every later page task (3, 5, 6) uses these class names verbatim; do not rename any of them mid-plan.
- Fonts loaded via Google Fonts CDN `<link>` (Fraunces, IBM Plex Sans, IBM Plex Mono) in each page's `<head>` — simpler than self-hosting woff2 files with no build step to manage them, and GitHub Pages already requires network access so there's no offline constraint to preserve.
- `nav.js` renders the nav header itself (not just active-link state) into a `<div id="site-nav"></div>` mount point each page provides — single source of truth for the nav markup instead of duplicating it verbatim across 3 HTML files. Tasks 4, 5, and 6's pages each include `<div id="site-nav"></div>` where the header goes, not inline `<header>` markup.

- [ ] **Step 1: Create `site/assets/style.css`**

```css
/* Phase 13 design system -- "Field Report" direction. Tokens mirror the
   scoring model itself: technical (denim) + practical (gold) are the only
   two hues in the palette, no third "brand" accent. */

:root {
  --color-paper: #FBFAF6;
  --color-surface: #F1EFE6;
  --color-ink: #1B1B18;
  --color-ink-muted: #5C594F;
  --color-rule: #DEDACB;
  --color-technical: #2B4C7E;
  --color-technical-soft: #DCE4EE;
  --color-practical: #C08A2E;
  --color-practical-soft: #F2E4C8;

  --font-display: "Fraunces", Georgia, serif;
  --font-body: "IBM Plex Sans", -apple-system, sans-serif;
  --font-mono: "IBM Plex Mono", "Courier New", monospace;

  --space-1: 4px;
  --space-2: 8px;
  --space-3: 16px;
  --space-4: 24px;
  --space-5: 40px;
  --space-6: 64px;

  --radius-card: 10px;
  --max-width: 1120px;
}

* { box-sizing: border-box; }

html { -webkit-font-smoothing: antialiased; }

body {
  margin: 0;
  background: var(--color-paper);
  color: var(--color-ink);
  font-family: var(--font-body);
  font-size: 16px;
  line-height: 1.55;
}

h1, h2, h3 {
  font-family: var(--font-display);
  font-weight: 600;
  line-height: 1.15;
  margin: 0 0 var(--space-3);
}

h1 { font-size: clamp(2.2rem, 4vw, 3.4rem); }
h2 { font-size: clamp(1.5rem, 2.4vw, 2rem); }
h3 { font-size: 1.15rem; }

p { margin: 0 0 var(--space-3); color: var(--color-ink); }

a { color: var(--color-technical); text-decoration: none; }
a:hover { text-decoration: underline; }

.mono { font-family: var(--font-mono); }

.eyebrow {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
}

.wrap {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: 0 var(--space-4);
}

/* -- Nav -------------------------------------------------------------- */

.site-nav {
  border-bottom: 1px solid var(--color-rule);
  background: var(--color-paper);
  position: sticky;
  top: 0;
  z-index: 10;
}

.site-nav .wrap {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
}

.site-nav__mark {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--color-ink);
}

.site-nav__links {
  display: flex;
  gap: var(--space-4);
  list-style: none;
  margin: 0;
  padding: 0;
}

.site-nav__links a {
  color: var(--color-ink-muted);
  font-family: var(--font-mono);
  font-size: 0.85rem;
  letter-spacing: 0.02em;
}

.site-nav__links a[aria-current="page"] {
  color: var(--color-ink);
  border-bottom: 2px solid var(--color-technical);
  padding-bottom: 2px;
}

/* -- Split-bar signature element --------------------------------------- */

.split-bar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.split-bar__track {
  flex: 1 1 auto;
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
  display: flex;
  background: var(--color-surface);
  min-width: 60px;
}

.split-bar__technical { background: var(--color-technical); height: 100%; }
.split-bar__practical { background: var(--color-practical); height: 100%; }

.split-bar__total {
  font-family: var(--font-mono);
  font-weight: 600;
  font-size: 0.9rem;
  white-space: nowrap;
}

/* -- Stat tiles ---------------------------------------------------------- */

.stat-tile-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--space-3);
  margin: var(--space-5) 0;
}

.stat-tile {
  background: var(--color-surface);
  border-radius: var(--radius-card);
  padding: var(--space-4);
}

.stat-tile .eyebrow { margin-bottom: var(--space-2); }

.stat-tile__value {
  font-family: var(--font-mono);
  font-size: 2rem;
  font-weight: 600;
}

.stat-tile__caption {
  color: var(--color-ink-muted);
  font-size: 0.9rem;
  margin-top: var(--space-1);
}

/* -- Cards (nav cards / ticket stubs) ------------------------------------ */

.card-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--space-4);
  margin: var(--space-5) 0;
}

.ticket-card {
  display: block;
  background: var(--color-paper);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-card);
  padding: var(--space-4);
  transition: border-color 0.15s ease;
}

.ticket-card:hover { border-color: var(--color-technical); text-decoration: none; }
.ticket-card h3 { margin-bottom: var(--space-2); }
.ticket-card p { color: var(--color-ink-muted); margin: 0; }

/* -- Chart sections -------------------------------------------------------- */

.chart-section { margin: var(--space-6) 0; }

.chart-section__insight {
  font-family: var(--font-display);
  font-size: 1.2rem;
  max-width: 640px;
  margin-bottom: var(--space-3);
}

.chart-tooltip {
  position: absolute;
  pointer-events: none;
  background: var(--color-ink);
  color: var(--color-paper);
  font-family: var(--font-mono);
  font-size: 0.8rem;
  padding: var(--space-2) var(--space-3);
  border-radius: 6px;
  opacity: 0;
  transition: opacity 0.1s ease;
  max-width: 240px;
  z-index: 20;
}

.chart-legend {
  display: flex;
  gap: var(--space-4);
  font-family: var(--font-mono);
  font-size: 0.8rem;
  margin-bottom: var(--space-2);
}

.chart-legend__item { display: flex; align-items: center; gap: var(--space-1); }

.chart-legend__swatch {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  display: inline-block;
}

/* -- Explorer table -------------------------------------------------------- */

.table-controls { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-bottom: var(--space-3); }

.table-controls input, .table-controls select {
  font-family: var(--font-body);
  border: 1px solid var(--color-rule);
  border-radius: 6px;
  padding: var(--space-2);
}

table.explorer-table { width: 100%; border-collapse: collapse; }

.explorer-table th, .explorer-table td {
  text-align: left;
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--color-rule);
  font-size: 0.9rem;
}

.explorer-table th {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-ink-muted);
  cursor: pointer;
}

/* -- Pipeline diagrams ------------------------------------------------------ */

.pipeline-flow { display: flex; align-items: stretch; gap: var(--space-2); overflow-x: auto; padding: var(--space-3) 0; }

.pipeline-stage-card {
  flex: 0 0 200px;
  background: var(--color-surface);
  border-radius: var(--radius-card);
  padding: var(--space-3);
}

.pipeline-stage-card--optional { border: 1px dashed var(--color-ink-muted); background: transparent; }

.pipeline-stage-card__name {
  font-family: var(--font-mono);
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.85rem;
}

.pipeline-stage-card__tag {
  display: inline-block;
  margin-top: var(--space-1);
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--color-ink-muted);
}

.pipeline-arrow { flex: 0 0 24px; align-self: center; color: var(--color-ink-muted); font-size: 1.2rem; }

.bucket-card {
  background: var(--color-surface);
  border-radius: var(--radius-card);
  padding: var(--space-3);
  margin-bottom: var(--space-2);
  font-size: 0.85rem;
}

.bucket-card__name { font-family: var(--font-mono); font-weight: 600; }

.callout-box {
  background: var(--color-technical-soft);
  border-left: 4px solid var(--color-technical);
  border-radius: 6px;
  padding: var(--space-3) var(--space-4);
  margin: var(--space-4) 0;
}

.callout-box h3 { margin-bottom: var(--space-2); }
.callout-box ol { margin: 0; padding-left: 1.2em; }

/* -- Footer ------------------------------------------------------------------ */

.site-footer {
  border-top: 1px solid var(--color-rule);
  margin-top: var(--space-6);
  padding: var(--space-4) 0;
  color: var(--color-ink-muted);
  font-size: 0.85rem;
}

/* -- Responsive --------------------------------------------------------------- */

@media (max-width: 640px) {
  .site-nav__links { gap: var(--space-3); }
  .site-nav .wrap { flex-direction: column; height: auto; padding: var(--space-2) var(--space-4); gap: var(--space-2); }
}

/* -- Accessibility ------------------------------------------------------------- */

:focus-visible { outline: 2px solid var(--color-technical); outline-offset: 2px; }

@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; animation: none !important; }
}
```

- [ ] **Step 2: Create `site/assets/nav.js`**

```js
// Single source of truth for the nav header: builds the markup and
// injects it into each page's <div id="site-nav"></div> mount point,
// with the current page's link marked aria-current. Avoids duplicating
// the header HTML verbatim across all 3 pages.
(function () {
  const NAV_LINKS = [
    { href: "index.html", label: "Overview" },
    { href: "dashboard.html", label: "Dashboard" },
    { href: "pipeline.html", label: "Pipeline" },
  ];

  function renderNav() {
    const mount = document.getElementById("site-nav");
    if (!mount) return;
    const path = window.location.pathname.split("/").pop() || "index.html";

    const links = NAV_LINKS.map((link) => {
      const current = link.href === path ? ' aria-current="page"' : "";
      return `<li><a href="${link.href}"${current}>${link.label}</a></li>`;
    }).join("");

    mount.outerHTML = `
<header class="site-nav">
  <div class="wrap">
    <a class="site-nav__mark" href="index.html">
      <svg width="20" height="14" viewBox="0 0 20 14" aria-hidden="true">
        <rect x="0" y="4" width="12" height="6" fill="#2B4C7E" />
        <rect x="12" y="4" width="8" height="6" fill="#C08A2E" />
      </svg>
      YC Complexity Index
    </a>
    <nav>
      <ul class="site-nav__links">${links}</ul>
    </nav>
  </div>
</header>`;
  }

  renderNav();
})();
```

- [ ] **Step 3: Create `site/index.html` as a nav-only shell**

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Y Combinator Complexity Index</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<div id="site-nav"></div>
<main class="wrap"></main>
<script src="assets/nav.js"></script>
</body>
</html>
```

- [ ] **Step 4: Verify in browser**

Run: `powershell -Command "Start-Process 'site/index.html'"` (or open the file directly in a browser)
Expected: nav bar renders (injected by `nav.js` into `#site-nav`) with the split-bar mark icon, "Overview" is underlined/highlighted as the active link (denim underline), the three fonts are visibly distinct (Plex Sans/Mono should already look right in the nav text), and the page background is the pale paper tone (`#FBFAF6`), not white.

- [ ] **Step 5: Commit**

```bash
git add site/assets/style.css site/assets/nav.js site/index.html
git commit -m "feat: add Phase 13 site design system (tokens, nav, split-bar) and nav shell"
```

---

## Task 3: D3 chart helpers (`site/assets/charts.js`)

**Files:**
- Create: `site/assets/charts.js`

**Interfaces:**
- Consumes: global `d3` (loaded via `<script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>` in each page's `<head>`, before `charts.js`), and the `.chart-tooltip`/`.split-bar*` CSS classes from Task 2's `style.css`.
- Produces (all attached as top-level functions in the page's global scope, since there's no module bundler): `renderSplitBar(container, technical, practical, opts) -> HTMLElement`, `renderHistogram(container, bins, opts) -> void`, `renderScatter(container, points, opts) -> void`, `renderRankedBars(container, records, opts) -> void`, `renderLineChart(container, series, opts) -> void`, `renderBarCompare(container, records, opts) -> void`, `renderHeatmap(container, columns, values, opts) -> void`. Task 4 (landing) uses `renderSplitBar` and `renderScatter`. Task 5 (dashboard) uses all seven.

- [ ] **Step 1: Create `site/assets/charts.js`**

```js
// Hand-built D3 chart helpers for the Phase 13 site. Each render*
// function takes a DOM container and data already shaped by
// scripts/export_site_data.py, and draws an SVG chart with a hover
// tooltip. Color always follows the two-hue model: technical = denim,
// practical = gold -- never a third "brand" accent.

const CHART_COLORS = {
  technical: "#2B4C7E",
  practical: "#C08A2E",
  ink: "#1B1B18",
  inkMuted: "#5C594F",
  surface: "#F1EFE6",
};

function makeTooltip(container) {
  return d3.select(container).append("div").attr("class", "chart-tooltip");
}

function showTooltip(tooltip, event, html, rect) {
  tooltip.style("opacity", 1).html(html)
    .style("left", event.clientX - rect.left + 12 + "px")
    .style("top", event.clientY - rect.top - 12 + "px");
}

function hideTooltip(tooltip) {
  tooltip.style("opacity", 0);
}

/* -- Split-bar signature element ---------------------------------------- */

function renderSplitBar(container, technical, practical, opts) {
  opts = opts || {};
  const maxScale = opts.maxScale || 100;
  const total = technical + practical;
  const wrap = d3.select(container).append("div").attr("class", "split-bar");
  const track = wrap.append("div").attr("class", "split-bar__track");
  track.append("div").attr("class", "split-bar__technical")
    .style("width", (technical / maxScale * 100) + "%");
  track.append("div").attr("class", "split-bar__practical")
    .style("width", (practical / maxScale * 100) + "%");
  wrap.append("span").attr("class", "split-bar__total mono").text(total.toFixed(1));
  return wrap.node();
}

/* -- Score distribution: histogram + median/p90 lines + complexity bands - */

function renderHistogram(container, bins, opts) {
  opts = opts || {};
  const width = container.clientWidth;
  const height = opts.height || 320;
  const margin = { top: 20, right: 20, bottom: 32, left: 36 };
  const svg = d3.select(container).append("svg").attr("width", width).attr("height", height);

  const x = d3.scaleLinear()
    .domain([bins[0].start, bins[bins.length - 1].end])
    .range([margin.left, width - margin.right]);
  const y = d3.scaleLinear()
    .domain([0, d3.max(bins, d => d.count)]).nice()
    .range([height - margin.bottom, margin.top]);

  const tooltip = makeTooltip(container);
  const rect = container.getBoundingClientRect();

  svg.selectAll(".bar").data(bins).join("rect")
    .attr("x", d => x(d.start) + 1)
    .attr("width", d => Math.max(0, x(d.end) - x(d.start) - 2))
    .attr("y", d => y(d.count))
    .attr("height", d => y(0) - y(d.count))
    .attr("rx", 2)
    .attr("fill", CHART_COLORS.technical)
    .on("mousemove", (event, d) => showTooltip(tooltip, event,
      `${d.start}&ndash;${d.end}: <strong>${d.count}</strong> companies`, rect))
    .on("mouseleave", () => hideTooltip(tooltip));

  [{ value: opts.median, label: "median", dash: null },
   { value: opts.p90, label: "p90", dash: "4,3" }].forEach((ref, i) => {
    if (ref.value == null) return;
    svg.append("line")
      .attr("x1", x(ref.value)).attr("x2", x(ref.value))
      .attr("y1", margin.top).attr("y2", height - margin.bottom)
      .attr("stroke", i === 0 ? CHART_COLORS.ink : CHART_COLORS.inkMuted)
      .attr("stroke-width", i === 0 ? 2 : 1.5)
      .attr("stroke-dasharray", ref.dash);
    svg.append("text")
      .attr("x", x(ref.value) + 6).attr("y", margin.top + 12 + i * 16)
      .attr("class", "mono").attr("font-size", "11px")
      .text(`${ref.label} ${ref.value}`);
  });

  svg.append("g").attr("transform", `translate(0,${height - margin.bottom})`)
    .call(d3.axisBottom(x).ticks(6))
    .call(g => g.selectAll("text").attr("class", "mono").attr("font-size", "11px"));
  svg.append("g").attr("transform", `translate(${margin.left},0)`)
    .call(d3.axisLeft(y).ticks(4))
    .call(g => g.select(".domain").remove())
    .call(g => g.selectAll("text").attr("class", "mono").attr("font-size", "11px"));
}

/* -- Technical vs Practical scatter -------------------------------------- */

function renderScatter(container, points, opts) {
  opts = opts || {};
  const width = container.clientWidth;
  const height = opts.height || 360;
  const margin = { top: 20, right: 20, bottom: 36, left: 36 };
  const svg = d3.select(container).append("svg").attr("width", width).attr("height", height);

  const x = d3.scaleLinear().domain([0, d3.max(points, d => d.x) || 1]).nice()
    .range([margin.left, width - margin.right]);
  const y = d3.scaleLinear().domain([0, d3.max(points, d => d.y) || 1]).nice()
    .range([height - margin.bottom, margin.top]);

  const tooltip = makeTooltip(container);
  const rect = container.getBoundingClientRect();

  svg.selectAll(".dot").data(points).join("circle")
    .attr("cx", d => x(d.x)).attr("cy", d => y(d.y))
    .attr("r", 4)
    .attr("fill", CHART_COLORS.technical)
    .attr("fill-opacity", 0.45)
    .on("mousemove", (event, d) => showTooltip(tooltip, event,
      `<strong>${d.name}</strong><br>Technical: ${d.x}<br>Practical: ${d.y}`, rect))
    .on("mouseleave", () => hideTooltip(tooltip));

  svg.append("g").attr("transform", `translate(0,${height - margin.bottom})`)
    .call(d3.axisBottom(x).ticks(5))
    .call(g => g.selectAll("text").attr("class", "mono").attr("font-size", "11px"));
  svg.append("g").attr("transform", `translate(${margin.left},0)`)
    .call(d3.axisLeft(y).ticks(5))
    .call(g => g.select(".domain").remove())
    .call(g => g.selectAll("text").attr("class", "mono").attr("font-size", "11px"));

  svg.append("text").attr("x", width - margin.right).attr("y", margin.top)
    .attr("text-anchor", "end").attr("class", "mono").attr("font-size", "11px")
    .attr("fill", CHART_COLORS.inkMuted).text("technical →");
  svg.append("text").attr("x", margin.left).attr("y", margin.top - 4)
    .attr("class", "mono").attr("font-size", "11px")
    .attr("fill", CHART_COLORS.inkMuted).text("↑ practical");

  if (opts.medianX != null && opts.medianY != null) {
    svg.append("line")
      .attr("x1", x(opts.medianX)).attr("x2", x(opts.medianX))
      .attr("y1", margin.top).attr("y2", height - margin.bottom)
      .attr("stroke", CHART_COLORS.inkMuted).attr("stroke-width", 1)
      .attr("stroke-dasharray", "3,3").attr("opacity", 0.5);
    svg.append("line")
      .attr("y1", y(opts.medianY)).attr("y2", y(opts.medianY))
      .attr("x1", margin.left).attr("x2", width - margin.right)
      .attr("stroke", CHART_COLORS.inkMuted).attr("stroke-width", 1)
      .attr("stroke-dasharray", "3,3").attr("opacity", 0.5);
    svg.append("text")
      .attr("x", width - margin.right - 4).attr("y", margin.top + 14)
      .attr("text-anchor", "end").attr("class", "mono").attr("font-size", "10px")
      .attr("fill", CHART_COLORS.inkMuted).text("high on both");
    svg.append("text")
      .attr("x", margin.left + 4).attr("y", height - margin.bottom - 6)
      .attr("class", "mono").attr("font-size", "10px")
      .attr("fill", CHART_COLORS.inkMuted).text("low on both");
  }

  if (opts.annotation) {
    svg.append("text")
      .attr("x", margin.left).attr("y", 14)
      .attr("class", "mono").attr("font-size", "11px")
      .attr("fill", CHART_COLORS.inkMuted).text(opts.annotation);
  }
}

/* -- Ranked bars (industry top/bottom) ------------------------------------ */

function renderRankedBars(container, records, opts) {
  opts = opts || {};
  const width = container.clientWidth;
  const barHeight = 28;
  const height = records.length * barHeight + 20;
  const margin = { top: 10, right: 60, bottom: 10, left: 180 };
  const svg = d3.select(container).append("svg").attr("width", width).attr("height", height);

  const x = d3.scaleLinear().domain([0, d3.max(records, d => d.mean_complexity)]).nice()
    .range([margin.left, width - margin.right]);
  const y = d3.scaleBand().domain(records.map(d => d.industry))
    .range([margin.top, height - margin.bottom]).padding(0.3);

  const tooltip = makeTooltip(container);
  const rect = container.getBoundingClientRect();

  svg.selectAll(".bar").data(records).join("rect")
    .attr("x", x(0)).attr("y", d => y(d.industry))
    .attr("width", d => x(d.mean_complexity) - x(0))
    .attr("height", y.bandwidth())
    .attr("rx", 3)
    .attr("fill", CHART_COLORS.ink)
    .attr("fill-opacity", (d, i) => 0.9 - i * 0.08)
    .on("mousemove", (event, d) => showTooltip(tooltip, event,
      `<strong>${d.industry}</strong><br>${d.mean_complexity} avg, ${d.count} companies`, rect))
    .on("mouseleave", () => hideTooltip(tooltip));

  svg.selectAll(".label").data(records).join("text")
    .attr("x", margin.left - 8).attr("y", d => y(d.industry) + y.bandwidth() / 2 + 4)
    .attr("text-anchor", "end").attr("font-size", "12px").text(d => d.industry);

  svg.selectAll(".value").data(records).join("text")
    .attr("x", d => x(d.mean_complexity) + 6).attr("y", d => y(d.industry) + y.bandwidth() / 2 + 4)
    .attr("class", "mono").attr("font-size", "12px").attr("fill", CHART_COLORS.inkMuted)
    .text(d => d.mean_complexity);
}

/* -- Complexity by batch (line, with an annotation callout) --------------- */

function renderLineChart(container, series, opts) {
  opts = opts || {};
  const width = container.clientWidth;
  const height = opts.height || 300;
  const margin = { top: 30, right: 20, bottom: 32, left: 36 };
  const svg = d3.select(container).append("svg").attr("width", width).attr("height", height);

  const x = d3.scalePoint().domain(series.map(d => d.batch))
    .range([margin.left, width - margin.right]);
  const y = d3.scaleLinear().domain([0, d3.max(series, d => d.mean_complexity)]).nice()
    .range([height - margin.bottom, margin.top]);

  const line = d3.line().x(d => x(d.batch)).y(d => y(d.mean_complexity));
  svg.append("path").datum(series).attr("d", line)
    .attr("fill", "none").attr("stroke", CHART_COLORS.technical).attr("stroke-width", 2);

  const tooltip = makeTooltip(container);
  const rect = container.getBoundingClientRect();

  svg.selectAll(".dot").data(series).join("circle")
    .attr("cx", d => x(d.batch)).attr("cy", d => y(d.mean_complexity)).attr("r", 4)
    .attr("fill", CHART_COLORS.technical)
    .on("mousemove", (event, d) => showTooltip(tooltip, event,
      `<strong>${d.batch}</strong><br>${d.mean_complexity} avg complexity`, rect))
    .on("mouseleave", () => hideTooltip(tooltip));

  const tickEvery = Math.ceil(series.length / 12);
  svg.append("g").attr("transform", `translate(0,${height - margin.bottom})`)
    .call(d3.axisBottom(x).tickValues(series.map(d => d.batch).filter((_, i) => i % tickEvery === 0)))
    .call(g => g.selectAll("text").attr("class", "mono").attr("font-size", "10px"));
  svg.append("g").attr("transform", `translate(${margin.left},0)`)
    .call(d3.axisLeft(y).ticks(4))
    .call(g => g.select(".domain").remove())
    .call(g => g.selectAll("text").attr("class", "mono").attr("font-size", "11px"));

  if (opts.annotation) {
    svg.append("text").attr("x", margin.left).attr("y", 14)
      .attr("class", "mono").attr("font-size", "11px").attr("fill", CHART_COLORS.inkMuted)
      .text(opts.annotation);
  }
}

/* -- Complexity by status (compact bar comparison) ------------------------- */

function renderBarCompare(container, records, opts) {
  opts = opts || {};
  const width = container.clientWidth;
  const height = opts.height || 220;
  const margin = { top: 20, right: 20, bottom: 32, left: 36 };
  const svg = d3.select(container).append("svg").attr("width", width).attr("height", height);

  const x = d3.scaleBand().domain(records.map(d => d.status))
    .range([margin.left, width - margin.right]).padding(0.35);
  const y = d3.scaleLinear().domain([0, d3.max(records, d => d.mean_complexity)]).nice()
    .range([height - margin.bottom, margin.top]);

  svg.selectAll(".bar").data(records).join("rect")
    .attr("x", d => x(d.status)).attr("width", x.bandwidth())
    .attr("y", d => y(d.mean_complexity)).attr("height", d => y(0) - y(d.mean_complexity))
    .attr("rx", 3).attr("fill", CHART_COLORS.ink).attr("fill-opacity", 0.85);

  svg.selectAll(".value").data(records).join("text")
    .attr("x", d => x(d.status) + x.bandwidth() / 2).attr("y", d => y(d.mean_complexity) - 6)
    .attr("text-anchor", "middle").attr("class", "mono").attr("font-size", "12px")
    .text(d => d.mean_complexity);

  svg.append("g").attr("transform", `translate(0,${height - margin.bottom})`)
    .call(d3.axisBottom(x))
    .call(g => g.selectAll("text").attr("font-size", "12px"));
}

/* -- Correlation heatmap: diverging technical<->practical, + table view --- */

function renderHeatmap(container, columns, values, opts) {
  opts = opts || {};
  const width = container.clientWidth;
  const cell = Math.min(48, (width - 160) / columns.length);
  const margin = { top: 120, right: 20, bottom: 20, left: 140 };
  const height = margin.top + cell * columns.length + margin.bottom;
  const svg = d3.select(container).append("svg").attr("width", width).attr("height", height);

  const color = d3.scaleLinear()
    .domain([-1, 0, 1])
    .range([CHART_COLORS.practical, CHART_COLORS.surface, CHART_COLORS.technical]);

  const tooltip = makeTooltip(container);
  const rect = container.getBoundingClientRect();

  columns.forEach((rowLabel, i) => {
    columns.forEach((colLabel, j) => {
      const v = values[i][j];
      svg.append("rect")
        .attr("x", margin.left + j * cell).attr("y", margin.top + i * cell)
        .attr("width", cell - 2).attr("height", cell - 2)
        .attr("fill", color(v))
        .on("mousemove", (event) => showTooltip(tooltip, event,
          `<strong>${rowLabel} × ${colLabel}</strong><br>r = ${v}`, rect))
        .on("mouseleave", () => hideTooltip(tooltip));
      if (Math.abs(v) >= 0.4 && rowLabel !== colLabel) {
        svg.append("text")
          .attr("x", margin.left + j * cell + cell / 2).attr("y", margin.top + i * cell + cell / 2 + 4)
          .attr("text-anchor", "middle").attr("class", "mono").attr("font-size", "10px")
          .text(v.toFixed(2));
      }
    });
  });

  columns.forEach((label, i) => {
    svg.append("text")
      .attr("x", margin.left - 6).attr("y", margin.top + i * cell + cell / 2 + 4)
      .attr("text-anchor", "end").attr("font-size", "10px").text(label.replace("_score", ""));
    svg.append("text")
      .attr("transform", `translate(${margin.left + i * cell + cell / 2},${margin.top - 6}) rotate(-45)`)
      .attr("text-anchor", "start").attr("font-size", "10px").text(label.replace("_score", ""));
  });

  if (opts.tableToggleContainer) {
    const btn = d3.select(opts.tableToggleContainer).append("button").text("Show as table");
    let showingTable = false;
    btn.on("click", () => {
      showingTable = !showingTable;
      svg.style("display", showingTable ? "none" : "block");
      d3.select(container).select("table").remove();
      if (showingTable) {
        const table = d3.select(container).append("table").attr("class", "explorer-table");
        const thead = table.append("thead").append("tr");
        thead.append("th").text("");
        columns.forEach(c => thead.append("th").text(c.replace("_score", "")));
        const tbody = table.append("tbody");
        columns.forEach((rowLabel, i) => {
          const tr = tbody.append("tr");
          tr.append("td").text(rowLabel.replace("_score", ""));
          values[i].forEach(v => tr.append("td").attr("class", "mono").text(v.toFixed(2)));
        });
      }
      btn.text(showingTable ? "Show as chart" : "Show as table");
    });
  }
}
```

- [ ] **Step 2: Verify with a scratch HTML page**

Create a temporary `site/_chart-check.html` (not committed) that loads D3 + `charts.js` and calls `renderHistogram` with sample bins, `renderScatter` with sample points, and `renderSplitBar` with `(18, 42)`. Open it in a browser and confirm: bars/dots render in denim, the split-bar shows two proportional segments summing visually to the total, hovering a bar/dot shows a tooltip near the cursor. Delete `site/_chart-check.html` once confirmed (it was scratch-only, not part of the shipped site).

- [ ] **Step 3: Commit**

```bash
git add site/assets/charts.js
git commit -m "feat: add D3 chart helpers for the Phase 13 site"
```

---

## Task 4: Landing page content (`site/index.html`, `site/assets/landing.js`)

**Files:**
- Modify: `site/index.html` (replace the `<main class="wrap"></main>` placeholder from Task 2)
- Create: `site/assets/landing.js`

**Interfaces:**
- Consumes: `renderScatter(container, points, opts)` from Task 3's `charts.js`; `site/data/summary.json` fields `company_count`, `median_complexity`, `technical_practical_correlation`, `top_industry` (`{industry, mean_complexity, count}`), `generated_at`; `site/data/companies.json` records with `technical_score`/`practical_score`/`name` (from Task 1).
- Produces: nothing consumed by later tasks — this is a leaf page.

Copy states current values and rationale only — no phase numbers, no before/after framing.

- [ ] **Step 1: Replace the `<main>` placeholder in `site/index.html`**

Replace `<main class="wrap"></main>` with:

```html
<main>
  <section class="wrap" style="padding-top: var(--space-6);">
    <p class="eyebrow">A reproducible startup complexity index</p>
    <h1>How hard is it, actually, to build a Y Combinator company?</h1>
    <p style="max-width: 640px; font-size: 1.1rem; color: var(--color-ink-muted);">
      Every company in the dataset gets two scores — one for the technology, one for the
      market — that combine into a single 0&ndash;100 Complexity Index.
    </p>

    <div class="stat-tile-row">
      <div class="stat-tile">
        <p class="eyebrow">Companies scored</p>
        <p class="stat-tile__value" id="stat-count">&mdash;</p>
      </div>
      <div class="stat-tile">
        <p class="eyebrow">Median complexity</p>
        <p class="stat-tile__value" id="stat-median">&mdash;</p>
        <p class="stat-tile__caption">0&ndash;100 scale</p>
      </div>
      <div class="stat-tile">
        <p class="eyebrow">Technical vs. practical</p>
        <p class="stat-tile__value" id="stat-correlation">&mdash;</p>
        <p class="stat-tile__caption">independent dimensions</p>
      </div>
      <div class="stat-tile">
        <p class="eyebrow">Highest-scoring industry</p>
        <p class="stat-tile__value" id="stat-top-industry-name">&mdash;</p>
        <p class="stat-tile__caption" id="stat-top-industry-value"></p>
      </div>
    </div>
  </section>

  <section class="wrap" style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-5); align-items: start;">
    <div>
      <h2>Two kinds of hard</h2>
      <p>
        Practical execution &mdash; regulation, market structure, geography, operations &mdash;
        carries more of the score than raw technical difficulty, because it accounts for more
        of what actually varies between companies. Most Y Combinator companies aren&rsquo;t
        deep-tech; regulatory and market complexity is where the real spread in difficulty
        shows up.
      </p>
      <p>
        The two dimensions are almost entirely independent of each other &mdash; building hard
        technology and operating in a hard market are, empirically, two different problems,
        not two names for the same one.
      </p>
    </div>
    <div id="teaser-scatter" style="position: relative;"></div>
  </section>

  <section class="wrap">
    <div class="card-row">
      <a class="ticket-card" href="dashboard.html">
        <p class="eyebrow">01</p>
        <h3>Explore the Dashboard</h3>
        <p>See the score distribution, how technical and practical complexity relate, which
        industries top the index, and search all companies.</p>
      </a>
      <a class="ticket-card" href="pipeline.html">
        <p class="eyebrow">02</p>
        <h3>See How It's Built</h3>
        <p>A rubric of scoring buckets, combined and summed by a config-driven engine &mdash;
        walk through exactly how a raw signal becomes a score.</p>
      </a>
    </div>
  </section>

  <footer class="site-footer">
    <div class="wrap">
      <a href="https://github.com/Ledsav/y-combinator-analysis">Source on GitHub</a>
      &middot; data generated <span id="generated-at" class="mono"></span>
    </div>
  </footer>
</main>
```

- [ ] **Step 2: Add script tags before `</body>` in `site/index.html`**

Replace:
```html
<script src="assets/nav.js"></script>
</body>
```
with:
```html
<script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
<script src="assets/nav.js"></script>
<script src="assets/charts.js"></script>
<script src="assets/landing.js"></script>
</body>
```

- [ ] **Step 3: Create `site/assets/landing.js`**

```js
async function loadLanding() {
  const [summary, companies] = await Promise.all([
    fetch("data/summary.json").then((r) => r.json()),
    fetch("data/companies.json").then((r) => r.json()),
  ]);

  document.getElementById("stat-count").textContent = summary.company_count.toLocaleString();
  document.getElementById("stat-median").textContent = summary.median_complexity;
  document.getElementById("stat-correlation").textContent =
    "r = " + summary.technical_practical_correlation;
  document.getElementById("stat-top-industry-name").textContent = summary.top_industry.industry;
  document.getElementById("stat-top-industry-value").textContent =
    summary.top_industry.mean_complexity + " avg";
  document.getElementById("generated-at").textContent = summary.generated_at;

  const sample = companies
    .filter((_, i) => i % 16 === 0)
    .map((c) => ({ x: c.technical_score, y: c.practical_score, name: c.name }));
  renderScatter(document.getElementById("teaser-scatter"), sample, { height: 280 });
}

loadLanding();
```

- [ ] **Step 4: Verify in browser**

Requires the real `site/data/*.json` files to exist — run `./.venv/Scripts/python.exe scripts/export_site_data.py` first if they don't (Task 8 also runs this for real, but landing needs it now to verify visually). Open `site/index.html` and confirm: all 4 stat tiles show real numbers (not `—`), the scatter preview renders denim dots, both nav cards are clickable and hover-highlight, the footer date matches today.

- [ ] **Step 5: Commit**

```bash
git add site/index.html site/assets/landing.js
git commit -m "feat: build the Phase 13 landing page"
```

---

## Task 5: Dashboard page (`site/dashboard.html`, `site/assets/dashboard.js`)

**Files:**
- Create: `site/dashboard.html`
- Create: `site/assets/dashboard.js`

**Interfaces:**
- Consumes: all seven `render*` functions from Task 3's `charts.js`; `site/data/summary.json` (`company_count`, `median_complexity`, `sigma_complexity`, `top_industry`, `distribution_bins`, `mean_by_batch`, `mean_by_status`, `industry_ranking.{top,bottom}`, `correlation_matrix.{columns,values}`); `site/data/companies.json` full records (from Task 1).
- Produces: nothing consumed by later tasks — leaf page.

- [ ] **Step 1: Create `site/dashboard.html`**

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dashboard — Y Combinator Complexity Index</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<div id="site-nav"></div>
<main>
  <section class="wrap" style="padding-top: var(--space-6);">
    <p class="eyebrow">Dashboard</p>
    <h1>Complexity Index Dashboard</h1>
    <p style="max-width: 640px; color: var(--color-ink-muted);">
      Y Combinator companies, scored 0&ndash;100 on Technical and Practical complexity.
    </p>
    <div class="stat-tile-row">
      <div class="stat-tile">
        <p class="eyebrow">Companies scored</p>
        <p class="stat-tile__value" id="kpi-count">&mdash;</p>
      </div>
      <div class="stat-tile">
        <p class="eyebrow">Median complexity</p>
        <p class="stat-tile__value" id="kpi-median">&mdash;</p>
      </div>
      <div class="stat-tile">
        <p class="eyebrow">Spread (&sigma;)</p>
        <p class="stat-tile__value" id="kpi-sigma">&mdash;</p>
      </div>
      <div class="stat-tile">
        <p class="eyebrow">Top industry</p>
        <p class="stat-tile__value" id="kpi-top-industry-name">&mdash;</p>
        <p class="stat-tile__caption" id="kpi-top-industry-value"></p>
      </div>
    </div>
  </section>

  <section class="wrap chart-section">
    <h2>Score distribution</h2>
    <p class="chart-section__insight">Most companies land in the moderate band &mdash; plain
    regulation or market complexity, not deep technology.</p>
    <div id="chart-distribution" style="position: relative;"></div>
  </section>

  <section class="wrap chart-section">
    <h2>Technical vs. Practical</h2>
    <p class="chart-section__insight">The two dimensions are independent &mdash; a company can
    score high on one, low on the other, or both.</p>
    <div id="chart-scatter" style="position: relative;"></div>
  </section>

  <section class="wrap chart-section">
    <h2>Complexity by industry</h2>
    <p class="chart-section__insight">Regulated and operations-heavy industries dominate the
    top of the index; consumer/content industries sit at the bottom.</p>
    <div id="chart-industry" style="position: relative;"></div>
  </section>

  <section class="wrap chart-section">
    <h2>Complexity by batch</h2>
    <p class="chart-section__insight">Average complexity has risen across batches, from the
    earliest cohorts to the most recent.</p>
    <div id="chart-batch" style="position: relative;"></div>
  </section>

  <section class="wrap chart-section">
    <h2>Complexity by status</h2>
    <p class="chart-section__insight">Active and Public companies score similarly, both above
    Acquired and Inactive.</p>
    <div id="chart-status" style="position: relative;"></div>
  </section>

  <section class="wrap chart-section">
    <h2>How the pieces relate</h2>
    <p class="chart-section__insight">Correlation across every scoring bucket and the two
    dimension totals they roll up into.</p>
    <div id="chart-heatmap-toggle"></div>
    <div id="chart-heatmap" style="position: relative;"></div>
  </section>

  <section class="wrap chart-section">
    <h2>Company Explorer</h2>
    <div class="table-controls">
      <input type="text" id="explorer-search" placeholder="Search by name...">
      <select id="explorer-batch"><option value="">All batches</option></select>
      <select id="explorer-status"><option value="">All statuses</option></select>
      <span id="explorer-count" class="mono"></span>
    </div>
    <table class="explorer-table" id="explorer-table">
      <thead>
        <tr>
          <th data-key="name">Name</th>
          <th data-key="batch">Batch</th>
          <th data-key="status">Status</th>
          <th>Industries</th>
          <th data-key="complexity_score">Score (technical / practical)</th>
        </tr>
      </thead>
      <tbody id="explorer-body"></tbody>
    </table>
  </section>

  <footer class="site-footer">
    <div class="wrap"><a href="index.html">&larr; Back to overview</a></div>
  </footer>
</main>
<script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
<script src="assets/nav.js"></script>
<script src="assets/charts.js"></script>
<script src="assets/dashboard.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create `site/assets/dashboard.js`**

```js
async function loadDashboard() {
  const [summary, companies] = await Promise.all([
    fetch("data/summary.json").then((r) => r.json()),
    fetch("data/companies.json").then((r) => r.json()),
  ]);

  document.getElementById("kpi-count").textContent = summary.company_count.toLocaleString();
  document.getElementById("kpi-median").textContent = summary.median_complexity;
  document.getElementById("kpi-sigma").textContent = summary.sigma_complexity;
  document.getElementById("kpi-top-industry-name").textContent = summary.top_industry.industry;
  document.getElementById("kpi-top-industry-value").textContent =
    summary.top_industry.mean_complexity + " avg";

  const sorted = companies.map((c) => c.complexity_score).sort((a, b) => a - b);
  const p90 = sorted[Math.floor(sorted.length * 0.9)];
  renderHistogram(document.getElementById("chart-distribution"), summary.distribution_bins, {
    median: summary.median_complexity,
    p90: Math.round(p90 * 10) / 10,
  });

  const technicalValues = companies.map((c) => c.technical_score).sort((a, b) => a - b);
  const practicalValues = companies.map((c) => c.practical_score).sort((a, b) => a - b);
  renderScatter(
    document.getElementById("chart-scatter"),
    companies.map((c) => ({ x: c.technical_score, y: c.practical_score, name: c.name })),
    {
      medianX: technicalValues[Math.floor(technicalValues.length / 2)],
      medianY: practicalValues[Math.floor(practicalValues.length / 2)],
      annotation: "r = " + summary.technical_practical_correlation + " — nearly uncorrelated",
    }
  );

  renderRankedBars(
    document.getElementById("chart-industry"),
    summary.industry_ranking.top.concat(summary.industry_ranking.bottom)
  );

  renderLineChart(document.getElementById("chart-batch"), summary.mean_by_batch, {
    annotation: "Complexity has risen across batches, earliest to most recent.",
  });

  renderBarCompare(document.getElementById("chart-status"), summary.mean_by_status);

  renderHeatmap(
    document.getElementById("chart-heatmap"),
    summary.correlation_matrix.columns,
    summary.correlation_matrix.values,
    { tableToggleContainer: document.getElementById("chart-heatmap-toggle") }
  );

  initExplorer(companies);
}

function initExplorer(records) {
  let sortKey = "complexity_score";
  let sortAsc = false;
  const tbody = document.getElementById("explorer-body");
  const searchBox = document.getElementById("explorer-search");
  const batchFilter = document.getElementById("explorer-batch");
  const statusFilter = document.getElementById("explorer-status");
  const countLabel = document.getElementById("explorer-count");

  function unique(values) {
    return Array.from(new Set(values)).sort();
  }
  function addOptions(select, values) {
    values.forEach((v) => {
      const opt = document.createElement("option");
      opt.value = v;
      opt.textContent = v;
      select.appendChild(opt);
    });
  }
  addOptions(batchFilter, unique(records.map((r) => r.batch)));
  addOptions(statusFilter, unique(records.map((r) => r.status)));

  function currentFilters() {
    return {
      search: searchBox.value.trim().toLowerCase(),
      batch: batchFilter.value,
      status: statusFilter.value,
    };
  }
  function matches(r, f) {
    if (f.search && !r.name.toLowerCase().includes(f.search)) return false;
    if (f.batch && r.batch !== f.batch) return false;
    if (f.status && r.status !== f.status) return false;
    return true;
  }

  function render() {
    const f = currentFilters();
    const filtered = records.filter((r) => matches(r, f));
    filtered.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av == null) return 1;
      if (bv == null) return -1;
      if (av < bv) return sortAsc ? -1 : 1;
      if (av > bv) return sortAsc ? 1 : -1;
      return 0;
    });

    const fragment = document.createDocumentFragment();
    filtered.forEach((r) => {
      const tr = document.createElement("tr");
      const nameCell = document.createElement("td");
      nameCell.textContent = r.name;
      const batchCell = document.createElement("td");
      batchCell.textContent = r.batch;
      const statusCell = document.createElement("td");
      statusCell.textContent = r.status;
      const industriesCell = document.createElement("td");
      industriesCell.textContent = (r.industries_list || []).join(", ");
      const scoreCell = document.createElement("td");
      renderSplitBar(scoreCell, r.technical_score, r.practical_score);
      tr.append(nameCell, batchCell, statusCell, industriesCell, scoreCell);
      fragment.appendChild(tr);
    });
    tbody.innerHTML = "";
    tbody.appendChild(fragment);
    countLabel.textContent = filtered.length + " of " + records.length + " companies";
  }

  document.querySelectorAll("#explorer-table thead th[data-key]").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.getAttribute("data-key");
      if (sortKey === key) {
        sortAsc = !sortAsc;
      } else {
        sortKey = key;
        sortAsc = true;
      }
      render();
    });
  });
  [searchBox, batchFilter, statusFilter].forEach((el) => el.addEventListener("input", render));
  render();
}

loadDashboard();
```

- [ ] **Step 3: Verify in browser**

Ensure `site/data/*.json` exist (run `./.venv/Scripts/python.exe scripts/export_site_data.py` if not). Open `site/dashboard.html` and confirm: 4 KPI tiles show real numbers, all 6 chart sections render (histogram with median/p90 lines, scatter, ranked industry bars, batch line with annotation, status bars, heatmap with a working "Show as table" toggle), and the Company Explorer table populates, search/filter/sort all work, and each row's score column renders a split-bar (not 3 separate numbers).

- [ ] **Step 4: Commit**

```bash
git add site/dashboard.html site/assets/dashboard.js
git commit -m "feat: build the Phase 13 dashboard page"
```

---

## Task 6: Pipeline page (`site/pipeline.html`, `site/assets/pipeline-diagram.js`)

**Files:**
- Create: `site/pipeline.html`
- Create: `site/assets/pipeline-diagram.js`
- Modify: `site/assets/style.css` (append `.scoring-engine*` layout rules)

**Interfaces:**
- Consumes: `renderSplitBar` from Task 3's `charts.js`; `site/data/pipeline.json` fields `steps` (`{name, module, input_dir, output_dir, optional}`) and `buckets` (`{name, dimension, raw_feature, combine, combine_params, method, params}`) from Task 1.
- Produces: `renderEtlFlow(container, steps) -> void`, `renderScoringEngine(container, buckets) -> void` — leaf functions, nothing later depends on them.

All copy states current implementation facts only — no before/after or hardcoded-vs-config comparisons.

- [ ] **Step 1: Append scoring-engine layout CSS to `site/assets/style.css`**

Add at the end of the file (after the accessibility block from Task 2):

```css
/* -- Scoring engine diagram (pipeline page) --------------------------------- */

.scoring-engine {
  display: grid;
  grid-template-columns: 2fr auto 1fr auto 1fr;
  gap: var(--space-3);
  align-items: start;
  overflow-x: auto;
  padding: var(--space-3) 0;
}

.scoring-engine__buckets, .scoring-engine__totals, .scoring-engine__total {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 160px;
}

.scoring-engine__arrow {
  align-self: center;
  color: var(--color-ink-muted);
  font-size: 1.2rem;
}
```

- [ ] **Step 2: Create `site/assets/pipeline-diagram.js`**

```js
function renderEtlFlow(container, steps) {
  const wrap = d3.select(container).append("div").attr("class", "pipeline-flow");
  steps.forEach((step, i) => {
    const card = wrap
      .append("div")
      .attr("class", "pipeline-stage-card" + (step.optional ? " pipeline-stage-card--optional" : ""));
    card.append("div").attr("class", "pipeline-stage-card__name").text(step.name);
    card.append("div").attr("class", "mono").style("font-size", "0.7rem").text(step.module);
    card
      .append("div")
      .attr("class", "mono")
      .style("font-size", "0.7rem")
      .style("color", "var(--color-ink-muted)")
      .text("→ " + step.output_dir);
    if (step.optional) {
      card.append("span").attr("class", "pipeline-stage-card__tag").text("off by default");
    }
    if (i < steps.length - 1) {
      wrap.append("div").attr("class", "pipeline-arrow").text("→");
    }
  });
}

function renderScoringEngine(container, buckets) {
  const dimensions = {};
  buckets.forEach((b) => {
    dimensions[b.dimension] = (dimensions[b.dimension] || 0) + b.params.points;
  });

  const wrap = d3.select(container).append("div").attr("class", "scoring-engine");
  const bucketsCol = wrap.append("div").attr("class", "scoring-engine__buckets");
  buckets.forEach((b) => {
    const card = bucketsCol.append("div").attr("class", "bucket-card");
    card.append("div").attr("class", "bucket-card__name").text(b.name);
    const source = b.raw_feature ? b.raw_feature : "combine: " + b.combine;
    card.append("div").attr("class", "mono").style("font-size", "0.75rem").text(source);
    card
      .append("div")
      .attr("class", "mono")
      .style("font-size", "0.75rem")
      .style("color", "var(--color-ink-muted)")
      .text(b.method + " → " + b.params.points + " pts");
  });

  wrap.append("div").attr("class", "scoring-engine__arrow").text("→");

  const totalsCol = wrap.append("div").attr("class", "scoring-engine__totals");
  Object.entries(dimensions).forEach(([dim, points]) => {
    const card = totalsCol.append("div").attr("class", "bucket-card");
    card.append("div").attr("class", "bucket-card__name").text(dim + "_score");
    card
      .append("div")
      .attr("class", "mono")
      .style("font-size", "0.75rem")
      .text(points + " pt budget");
  });

  wrap.append("div").attr("class", "scoring-engine__arrow").text("→");

  const total = Object.values(dimensions).reduce((a, b) => a + b, 0);
  const complexityCol = wrap.append("div").attr("class", "scoring-engine__total");
  complexityCol.append("div").attr("class", "bucket-card__name").text("complexity_score");
  renderSplitBar(complexityCol.node(), dimensions.technical || 0, dimensions.practical || 0, {
    maxScale: total,
  });
}

async function loadPipeline() {
  const pipeline = await fetch("data/pipeline.json").then((r) => r.json());
  renderEtlFlow(document.getElementById("diagram-etl-flow"), pipeline.steps);
  renderScoringEngine(document.getElementById("diagram-scoring-engine"), pipeline.buckets);
}

loadPipeline();
```

- [ ] **Step 3: Create `site/pipeline.html`**

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pipeline — Y Combinator Complexity Index</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<div id="site-nav"></div>
<main>
  <section class="wrap" style="padding-top: var(--space-6);">
    <p class="eyebrow">Pipeline</p>
    <h1>How the number is computed</h1>
    <p style="max-width: 640px; color: var(--color-ink-muted);">
      Five steps turn raw company data into a score. The last step, scoring, reads its
      rubric from a config file rather than from code.
    </p>
  </section>

  <section class="wrap">
    <h2>The ETL pipeline</h2>
    <div id="diagram-etl-flow"></div>
    <p style="color: var(--color-ink-muted); font-size: 0.9rem;">
      <code class="mono">enrich</code> is opt-in: it must be explicitly requested for the
      <code class="mono">features</code> step to see freshly enriched data, since
      <code class="mono">features</code> always reads from <code class="mono">enrich</code>'s
      output directory.
    </p>
  </section>

  <section class="wrap">
    <p>
      The <code class="mono">score</code> step is config-driven: its rubric &mdash; which
      signals count, how they're combined, how they're scaled, and how many points each is
      worth &mdash; lives in a YAML file the engine reads, not in code.
    </p>
  </section>

  <section class="wrap">
    <h2>The scoring engine</h2>
    <div id="diagram-scoring-engine"></div>
  </section>

  <section class="wrap">
    <div class="callout-box">
      <h3>Adding a new scoring method</h3>
      <ol>
        <li>Write a function taking a raw <code class="mono">pd.Series</code> plus its own
        parameters (must include <code class="mono">points</code>), returning a
        <code class="mono">pd.Series</code> bounded <code class="mono">[0, points]</code>.</li>
        <li>Register it in <code class="mono">src/etl/scaling.py</code>'s
        <code class="mono">SCALING_METHODS</code> dict.</li>
        <li>Reference it from a bucket's <code class="mono">method:</code> field in a rubric
        YAML.</li>
        <li>Add a unit test for the function itself.</li>
      </ol>
      <p style="margin: var(--space-2) 0 0;">No changes to <code class="mono">score.py</code>,
      <code class="mono">pipeline.py</code>, <code class="mono">rubric.py</code>, or any other
      bucket's config.</p>
    </div>
  </section>

  <section class="wrap">
    <h2>Why YAML</h2>
    <p>
      The rubric lives in <code class="mono">config/rubric_v2.yaml</code>, not in code. Each
      bucket's cap and points value carries an inline comment explaining its rationale &mdash;
      the <code class="mono">deep_tech</code> bucket's <code class="mono">cap: 2</code> comment
      reads &ldquo;2+ tags = maximally deep-tech,&rdquo; for example. That context stays
      attached to the number it explains.
    </p>
  </section>

  <section class="wrap">
    <h2>Known limitations</h2>
    <ul>
      <li><strong>enrich must be requested explicitly.</strong> The pipeline orchestrator's
      default step list excludes it, but <code class="mono">features</code> always reads its
      output directory.</li>
      <li><strong>Team-size correlation is weak.</strong> <code class="mono">complexity_score</code>
      correlates with log(team size) at r&asymp;0.10 &mdash; roughly half the dataset carries
      no deep-tech signal at all, which caps how strongly team size can track the score.</li>
    </ul>
  </section>

  <footer class="site-footer">
    <div class="wrap"><a href="index.html">&larr; Back to overview</a></div>
  </footer>
</main>
<script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
<script src="assets/nav.js"></script>
<script src="assets/charts.js"></script>
<script src="assets/pipeline-diagram.js"></script>
</body>
</html>
```

- [ ] **Step 4: Verify in browser**

Ensure `site/data/pipeline.json` exists (run `./.venv/Scripts/python.exe scripts/export_site_data.py` if not). Open `site/pipeline.html` and confirm: the ETL flow diagram shows 5 connected stage cards with `enrich` visually dashed and tagged "off by default"; the scoring engine diagram shows all 7 buckets on the left, 2 dimension totals in the middle, and a `complexity_score` split-bar on the right sized to the 30/70 point budget; the callout box and both narrative sections render.

- [ ] **Step 5: Commit**

```bash
git add site/pipeline.html site/assets/pipeline-diagram.js site/assets/style.css
git commit -m "feat: build the Phase 13 pipeline page and its two diagrams"
```

---

## Task 7: GitHub Pages deploy workflow

**Files:**
- Create: `.github/workflows/deploy-pages.yml`

**Interfaces:**
- Consumes: nothing from earlier tasks — deploys the `site/` directory as-is.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Create `.github/workflows/deploy-pages.yml`**

```yaml
name: Deploy site to GitHub Pages

on:
  push:
    branches: [master]
    paths:
      - "site/**"
      - ".github/workflows/deploy-pages.yml"
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Upload site artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: site
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/deploy-pages.yml
git commit -m "feat: add GitHub Actions workflow to deploy site/ to GitHub Pages"
```

- [ ] **Step 3: Push and enable Pages (manual, one-time)**

Push the branch containing this workflow to `origin`. Then, in the GitHub repo's Settings → Pages, set **Source** to **GitHub Actions** (this is a repo-settings change only a repo admin can make via the GitHub UI — not something a script can do). After that's set, any future push to `master` touching `site/**` triggers a deploy; the Actions tab shows the run and the resulting `https://ledsav.github.io/y-combinator-analysis/` URL.

---

## Task 8: Final data export, palette validation, and full-site verification

**Files:**
- Create: `site/data/companies.json`, `site/data/summary.json`, `site/data/pipeline.json` (generated, not hand-written)

**Interfaces:**
- Consumes: `scripts/export_site_data.py`'s `main()` from Task 1; the `dataviz` skill's `scripts/validate_palette.js`.
- Produces: the final committed data snapshot the deployed site serves.

- [ ] **Step 1: Generate the real site data**

Run: `./.venv/Scripts/python.exe scripts/export_site_data.py`
Expected: `Wrote site data to <repo>/site/data`, and `site/data/companies.json`, `summary.json`, `pipeline.json` exist and are non-empty.

- [ ] **Step 2: Run the full existing test suite to confirm nothing else broke**

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: all tests pass, including the new `tests/test_export_site_data.py` tests from Task 1 (139 total: the existing 129 plus the 9 new ones).

- [ ] **Step 3: Validate the palette**

Invoke the `dataviz` skill if it isn't already active in this session, to get its current base directory. Then run its validator against the site's two categorical hues:

Run: `node <dataviz-skill-base-dir>/scripts/validate_palette.js "#2B4C7E,#C08A2E" --mode light`
Expected: PASS on lightness band, chroma floor, CVD separation (target ΔE ≥ 8), and the normal-vision floor. If anything FAILs, adjust the two hex values in `site/assets/style.css`'s `--color-technical`/`--color-practical` (and re-run this check) until it passes — do not ship a failing pair. Also re-run against the correlation heatmap's 3-stop diverging scale (`"#C08A2E,#F1EFE6,#2B4C7E"`) to confirm the diverging pair is legible.

- [ ] **Step 4: Manual full-site verification**

Open `site/index.html`, `site/dashboard.html`, and `site/pipeline.html` in a browser and confirm, per the `verify` skill's golden-path approach:
- Nav links move correctly between all 3 pages, with the current page highlighted (denim underline) on each.
- Resize to a mobile width (~375px): nav stacks vertically, stat tiles wrap to a single column, charts don't overflow horizontally.
- Tab through the page with the keyboard: focus outlines are visible on nav links, table headers, and buttons.
- On the dashboard, the Company Explorer search/filter/sort all update the table live, and every score cell renders a split-bar (not raw numbers).
- On the pipeline page, both diagrams render with real data (not empty containers) and the `enrich` stage card is visually distinct (dashed border, "off by default" tag).
- Open the browser devtools console on each page and confirm there are no JS errors.

- [ ] **Step 5: Commit the generated site data**

```bash
git add site/data/companies.json site/data/summary.json site/data/pipeline.json
git commit -m "chore: generate site data snapshot for the Phase 13 static site"
```

---

