# Phase 10 Visualization Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `scripts/generate_dashboard.py`, a generator producing `output/complexity_dashboard_v1.html` — a single self-contained, offline-capable HTML dashboard (Plotly.js bundled inline) with 6 interactive charts mirroring Phase 9's analysis plus a sortable/filterable/searchable company-explorer table, per `docs/superpowers/specs/2026-07-14-phase10-visualization-dashboard-design.md`.

**Architecture:** Small, independently-testable pure functions (data loading/joining, one builder per chart, a company-records/table-HTML builder) composed by two assembly functions — `build_dashboard_body()` (body-only HTML: styles, 6 chart divs, one inline Plotly bundle, the table) and `build_standalone_dashboard()` (wraps the body in a minimal `<html>` shell) — and a thin `main()` that wires them to real data paths and writes the file. All logic lives in one script file, following the project's existing `scripts/generate_*.py` generator convention; unlike Phase 9's pure-analysis notebook, this phase has real transform/assembly logic worth unit testing (precedent: `tests/test_run_complexity_pipeline.py` already unit-tests functions inside `scripts/run_complexity_pipeline.py`).

**Tech Stack:** Python stdlib (`json`, `math`, `pathlib`) + `pandas`, `pyarrow` (already dependencies) + `plotly` (**new** dependency, added in Task 1) + hand-written vanilla JS (no new JS library — Decision 4 in the spec).

## Global Constraints

- No server, no live recomputation — a static file, generated once, opened from disk (spec Decision 1).
- All assets bundled inline: the Plotly.js bundle is embedded via `plotly.offline.get_plotlyjs()` exactly **once** per file (not once per chart) — never a CDN `<script src=...>` (spec Decision 2).
- Charts and the company table are independent — no cross-filtering wiring between them in this phase (spec Decision 3).
- Company table is hand-rolled vanilla JS (sort/filter/search) — no jQuery, no DataTables.js or other table library (spec Decision 4).
- No pagination in the table — all 4,844 rows render as plain `<tr>` elements; filtering hides rows rather than re-rendering a paginated subset (spec Decision 5).
- `plotly` is added to `requirements.txt` (spec Decision 6).
- No unit tests exist for `main()`'s real-data run itself or for the generated JS's runtime behavior (JS can't be exercised by `pytest`) — acceptance for those two pieces is an automated structural-content check plus a manual visual pass, both in Task 6 (spec Decision 7). All other functions (data loading/joining, chart builders, table/body/standalone assembly) ARE unit tested with TDD, using small hand-built fixtures — this is stronger test coverage than Phase 9 had, since this phase has real transform logic Phase 9's pure-analysis notebook didn't.
- Any string interpolated into `innerHTML`-adjacent HTML must not create an XSS/breakage risk: company names are rendered into the table via `textContent`/DOM APIs, never raw string concatenation into `innerHTML`. The embedded JSON payload has `</` escaped to `<\/` so a company name or field value containing the literal substring `</script>` can never prematurely close the embedding `<script>` tag.
- Real-data verified values used throughout this plan (computed directly against the current `data/processed/` outputs, unchanged since Phase 9): `scores_df.shape == (4844, 14)`, `companies_df.shape == (4844, 12)`, company `id` sets between scores and companies match exactly (no left-join surprises), `corr_matrix.shape == (17, 17)`, 55 industries meet the `>= 20` threshold (same number as Phase 9's notebook), company `circuithub` (id 5) has industries `"Industrials, Manufacturing and Robotics"` and `teamSize 58.0`, company `sift` (id 102) has `teamSize` missing (must serialize as JSON `null`, not `NaN`), company `opencurriculum` (id 642) has no industry tags (must serialize `industries` as `""`, not `null`).

---

## Task 1: Data loading + industry aggregation + `plotly` dependency

**Files:**
- Create: `scripts/generate_dashboard.py`
- Create: `tests/test_generate_dashboard.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces:
  - `load_dashboard_data(scores_path: Path, features_path: Path, industries_path: Path, companies_path: Path) -> Dict[str, pd.DataFrame]` — keys `"scores"`, `"features"`, `"industries"`, `"companies"`
  - `aggregate_company_industries(scores_df: pd.DataFrame, industries_df: pd.DataFrame) -> pd.DataFrame` — columns `id`, `industries` (comma-joined string, `""` if none), one row per `scores_df` id
  - `explode_industries(scores_df: pd.DataFrame, industries_df: pd.DataFrame) -> pd.DataFrame` — left join, one row per company-industry tag pair
  - `batch_sort_key(batch: str) -> Tuple[int, int]` — `(year, season_order)`, Winter=0 before Summer=1

- [ ] **Step 1: Install `plotly` and add it to `requirements.txt`**

Run: `./.venv/Scripts/pip.exe install plotly`
Expected: installs `plotly` (and its `narwhals` dependency) successfully.

Add `plotly` as a new line at the end of `requirements.txt` (after `matplotlib`).

- [ ] **Step 2: Write the failing tests**

Create `tests/test_generate_dashboard.py`:

```python
import pandas as pd
import pytest

from scripts.generate_dashboard import (
    aggregate_company_industries,
    batch_sort_key,
    explode_industries,
    load_dashboard_data,
)


def test_load_dashboard_data_reads_all_four_sources(tmp_path):
    scores_path = tmp_path / "scores.csv"
    features_path = tmp_path / "features.parquet"
    industries_path = tmp_path / "industries.csv"
    companies_path = tmp_path / "companies.csv"

    pd.DataFrame({"id": [1], "slug": ["acme"], "complexity_score": [42.0]}).to_csv(
        scores_path, index=False
    )
    pd.DataFrame({"id": [1], "deep_tech_tag_count": [2]}).to_parquet(
        features_path, index=False
    )
    pd.DataFrame({"id": [1], "industry": ["Fintech"]}).to_csv(
        industries_path, index=False
    )
    pd.DataFrame({"id": [1], "teamSize": [5.0]}).to_csv(companies_path, index=False)

    data = load_dashboard_data(scores_path, features_path, industries_path, companies_path)

    assert set(data.keys()) == {"scores", "features", "industries", "companies"}
    assert data["scores"].loc[0, "complexity_score"] == 42.0
    assert data["features"].loc[0, "deep_tech_tag_count"] == 2
    assert data["industries"].loc[0, "industry"] == "Fintech"
    assert data["companies"].loc[0, "teamSize"] == 5.0


def test_aggregate_company_industries_joins_multiple_tags_and_fills_empty():
    scores_df = pd.DataFrame({"id": [1, 2, 3]})
    industries_df = pd.DataFrame(
        {
            "id": [1, 1, 2],
            "industry": ["Industrials", "Manufacturing and Robotics", "Consumer"],
        }
    )

    result = aggregate_company_industries(scores_df, industries_df).set_index("id")

    assert result.loc[1, "industries"] == "Industrials, Manufacturing and Robotics"
    assert result.loc[2, "industries"] == "Consumer"
    assert result.loc[3, "industries"] == ""


def test_explode_industries_produces_one_row_per_company_industry_pair():
    scores_df = pd.DataFrame({"id": [1, 2], "complexity_score": [10.0, 20.0]})
    industries_df = pd.DataFrame({"id": [1, 1, 2], "industry": ["A", "B", "C"]})

    result = explode_industries(scores_df, industries_df)

    assert len(result) == 3
    assert set(result[result["id"] == 1]["industry"]) == {"A", "B"}


def test_batch_sort_key_orders_winter_before_summer_within_year():
    assert batch_sort_key("W12") < batch_sort_key("S12")
    assert batch_sort_key("S11") < batch_sort_key("W12")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_generate_dashboard.py -v`
Expected: `ModuleNotFoundError: No module named 'scripts.generate_dashboard'`

- [ ] **Step 4: Implement `scripts/generate_dashboard.py` (data loading + industry helpers)**

Create `scripts/generate_dashboard.py`:

```python
"""
Generates output/complexity_dashboard_v1.html — a self-contained, offline
HTML dashboard for exploring data/processed/scores/complexity_index_v1.csv,
per docs/superpowers/specs/2026-07-14-phase10-visualization-dashboard-design.md.

Run: ./.venv/Scripts/python.exe scripts/generate_dashboard.py

This phase only visualizes the already-computed index; it does not
recompute or re-validate any scores.
"""

from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SCORES_PATH = REPO_ROOT / "data" / "processed" / "scores" / "complexity_index_v1.csv"
FEATURES_PATH = REPO_ROOT / "data" / "processed" / "features" / "complexity_features.parquet"
INDUSTRIES_PATH = REPO_ROOT / "data" / "processed" / "step3_enriched" / "industries_enriched.csv"
COMPANIES_PATH = REPO_ROOT / "data" / "processed" / "step3_enriched" / "companies_enriched.csv"
OUTPUT_PATH = REPO_ROOT / "output" / "complexity_dashboard_v1.html"


def load_dashboard_data(
    scores_path: Path, features_path: Path, industries_path: Path, companies_path: Path
) -> Dict[str, pd.DataFrame]:
    """Read the 4 data sources the dashboard needs."""
    return {
        "scores": pd.read_csv(scores_path),
        "features": pd.read_parquet(features_path),
        "industries": pd.read_csv(industries_path),
        "companies": pd.read_csv(companies_path),
    }


def aggregate_company_industries(
    scores_df: pd.DataFrame, industries_df: pd.DataFrame
) -> pd.DataFrame:
    """
    One row per company id (from scores_df, so companies with zero industry
    tags are still present), with a comma-joined `industries` string column
    ("" if the company has no industry tags).
    """
    grouped = (
        industries_df.groupby("id")["industry"]
        .apply(lambda s: ", ".join(s))
        .reset_index()
        .rename(columns={"industry": "industries"})
    )
    result = scores_df[["id"]].merge(grouped, on="id", how="left")
    result["industries"] = result["industries"].fillna("")
    return result


def explode_industries(scores_df: pd.DataFrame, industries_df: pd.DataFrame) -> pd.DataFrame:
    """One row per company-industry tag pair (a company with N tags appears N times)."""
    return scores_df.merge(industries_df, on="id", how="left")


def batch_sort_key(batch: str) -> Tuple[int, int]:
    """Chronological sort key: Winter before Summer within the same year."""
    year = int(batch[1:])
    season_order = 0 if batch[0] == "W" else 1
    return (year, season_order)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_generate_dashboard.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add scripts/generate_dashboard.py tests/test_generate_dashboard.py requirements.txt
git commit -m "feat: add Phase 10 dashboard data loading and industry aggregation"
```

---

## Task 2: Simple aggregate charts (distribution, scatter, batch, status)

**Files:**
- Modify: `scripts/generate_dashboard.py`
- Modify: `tests/test_generate_dashboard.py`

**Interfaces:**
- Consumes: `batch_sort_key` (Task 1)
- Produces:
  - `build_distribution_chart(scores_df: pd.DataFrame) -> go.Figure`
  - `build_scatter_chart(scores_df: pd.DataFrame) -> go.Figure`
  - `build_batch_chart(scores_df: pd.DataFrame) -> go.Figure`
  - `build_status_chart(scores_df: pd.DataFrame) -> go.Figure`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_generate_dashboard.py`:

```python
from scripts.generate_dashboard import (
    build_batch_chart,
    build_distribution_chart,
    build_scatter_chart,
    build_status_chart,
)


def test_build_distribution_chart_uses_complexity_score_as_x():
    scores_df = pd.DataFrame({"complexity_score": [10.0, 20.0, 30.0]})

    fig = build_distribution_chart(scores_df)

    assert list(fig.data[0].x) == [10.0, 20.0, 30.0]
    assert fig.layout.title.text == "Complexity Score Distribution"


def test_build_scatter_chart_plots_technical_vs_practical():
    scores_df = pd.DataFrame(
        {
            "technical_score": [10.0, 20.0],
            "practical_score": [5.0, 15.0],
            "name": ["Acme", "Beta"],
        }
    )

    fig = build_scatter_chart(scores_df)

    assert list(fig.data[0].x) == [10.0, 20.0]
    assert list(fig.data[0].y) == [5.0, 15.0]
    assert list(fig.data[0].text) == ["Acme", "Beta"]


def test_build_batch_chart_orders_batches_chronologically():
    scores_df = pd.DataFrame(
        {
            "batch": ["S12", "W12", "S11"],
            "complexity_score": [30.0, 20.0, 10.0],
        }
    )

    fig = build_batch_chart(scores_df)

    assert list(fig.data[0].x) == ["S11", "W12", "S12"]
    assert list(fig.data[0].y) == [10.0, 20.0, 30.0]


def test_build_status_chart_sorts_descending_by_mean_score():
    scores_df = pd.DataFrame(
        {
            "status": ["Active", "Active", "Inactive"],
            "complexity_score": [10.0, 30.0, 5.0],
        }
    )

    fig = build_status_chart(scores_df)

    assert list(fig.data[0].x) == ["Active", "Inactive"]
    assert list(fig.data[0].y) == [20.0, 5.0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_generate_dashboard.py -v`
Expected: `ImportError: cannot import name 'build_distribution_chart'`

- [ ] **Step 3: Implement the 4 chart builders**

Add to `scripts/generate_dashboard.py` (after `batch_sort_key`, add `import plotly.graph_objects as go` to the top imports alongside `import pandas as pd`):

```python
import plotly.graph_objects as go


def build_distribution_chart(scores_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure(data=[go.Histogram(x=scores_df["complexity_score"], nbinsx=30)])
    fig.update_layout(
        title="Complexity Score Distribution",
        xaxis_title="complexity_score",
        yaxis_title="count",
    )
    return fig


def build_scatter_chart(scores_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure(
        data=[
            go.Scatter(
                x=scores_df["technical_score"],
                y=scores_df["practical_score"],
                mode="markers",
                marker=dict(opacity=0.5),
                text=scores_df["name"],
                hovertemplate="%{text}<br>Technical: %{x}<br>Practical: %{y}<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        title="Technical vs Practical Complexity",
        xaxis_title="technical_score",
        yaxis_title="practical_score",
    )
    return fig


def build_batch_chart(scores_df: pd.DataFrame) -> go.Figure:
    batch_summary = scores_df.groupby("batch")["complexity_score"].mean().reset_index()
    batch_summary["sort_key"] = batch_summary["batch"].apply(batch_sort_key)
    batch_summary = batch_summary.sort_values("sort_key").drop(columns="sort_key")

    fig = go.Figure(
        data=[
            go.Scatter(
                x=batch_summary["batch"], y=batch_summary["complexity_score"], mode="lines+markers"
            )
        ]
    )
    fig.update_layout(
        title="Mean Complexity Score by Batch",
        xaxis_title="batch",
        yaxis_title="mean complexity_score",
    )
    return fig


def build_status_chart(scores_df: pd.DataFrame) -> go.Figure:
    status_summary = (
        scores_df.groupby("status")["complexity_score"]
        .mean()
        .sort_values(ascending=False)
        .reset_index()
    )
    fig = go.Figure(
        data=[go.Bar(x=status_summary["status"], y=status_summary["complexity_score"])]
    )
    fig.update_layout(
        title="Mean Complexity Score by Status",
        xaxis_title="status",
        yaxis_title="mean complexity_score",
    )
    return fig
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_generate_dashboard.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_dashboard.py tests/test_generate_dashboard.py
git commit -m "feat: add Phase 10 distribution, scatter, batch, and status charts"
```

---

## Task 3: Industry chart + correlation heatmap

**Files:**
- Modify: `scripts/generate_dashboard.py`
- Modify: `tests/test_generate_dashboard.py`

**Interfaces:**
- Consumes: `explode_industries` (Task 1)
- Produces:
  - `build_industry_chart(industry_exploded_df: pd.DataFrame, min_count: int = 20) -> go.Figure`
  - `build_correlation_matrix(scores_df: pd.DataFrame, features_df: pd.DataFrame, feature_cols: List[str]) -> pd.DataFrame`
  - `build_correlation_heatmap(corr_matrix: pd.DataFrame) -> go.Figure`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_generate_dashboard.py`:

```python
from scripts.generate_dashboard import (
    build_correlation_heatmap,
    build_correlation_matrix,
    build_industry_chart,
)


def test_build_industry_chart_filters_by_min_count_and_sorts_descending():
    industry_exploded_df = pd.DataFrame(
        {
            "industry": ["A", "A", "A", "B", "B", "C"],
            "complexity_score": [10.0, 20.0, 30.0, 5.0, 15.0, 100.0],
        }
    )

    fig = build_industry_chart(industry_exploded_df, min_count=2)

    # C has only 1 company (< min_count), excluded; A (mean 20) > B (mean 10)
    assert list(fig.data[0].y) == ["A", "B"]
    assert list(fig.data[0].x) == [20.0, 10.0]


def test_build_correlation_matrix_computes_expected_shape_and_values():
    scores_df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "deep_tech_score": [10.0, 20.0, 30.0],
            "technical_score": [10.0, 20.0, 30.0],
            "practical_score": [30.0, 20.0, 10.0],
            "description_score": [0.0, 0.0, 0.0],
            "founder_background_score": [0.0, 0.0, 0.0],
            "regulated_score": [0, 0, 0],
            "market_type_pts": [0, 0, 0],
            "geo_ops_score": [0.0, 0.0, 0.0],
            "complexity_score": [40.0, 40.0, 40.0],
        }
    )
    features_df = pd.DataFrame({"id": [1, 2, 3], "deep_tech_tag_count": [1, 2, 3]})

    corr = build_correlation_matrix(scores_df, features_df, feature_cols=["deep_tech_tag_count"])

    assert corr.shape == (10, 10)
    assert corr.loc["deep_tech_tag_count", "technical_score"] == pytest.approx(1.0)
    assert corr.loc["technical_score", "practical_score"] == pytest.approx(-1.0)


def test_build_correlation_heatmap_uses_matrix_values_and_labels():
    corr_matrix = pd.DataFrame({"a": [1.0, 0.5], "b": [0.5, 1.0]}, index=["a", "b"])

    fig = build_correlation_heatmap(corr_matrix)

    assert fig.data[0].z.tolist() == [[1.0, 0.5], [0.5, 1.0]]
    assert list(fig.data[0].x) == ["a", "b"]
    assert list(fig.data[0].y) == ["a", "b"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_generate_dashboard.py -v`
Expected: `ImportError: cannot import name 'build_industry_chart'`

- [ ] **Step 3: Implement the industry chart, correlation matrix, and heatmap**

Add to `scripts/generate_dashboard.py` (after `build_status_chart`):

```python
def build_industry_chart(industry_exploded_df: pd.DataFrame, min_count: int = 20) -> go.Figure:
    industry_summary = (
        industry_exploded_df.groupby("industry")["complexity_score"]
        .agg(["mean", "count"])
        .query("count >= @min_count")
        .sort_values("mean", ascending=False)
        .reset_index()
    )
    fig = go.Figure(
        data=[go.Bar(y=industry_summary["industry"], x=industry_summary["mean"], orientation="h")]
    )
    fig.update_layout(
        title=f"Mean Complexity Score by Industry (>= {min_count} companies)",
        xaxis_title="mean complexity_score",
        yaxis_title="industry",
        height=max(400, 20 * len(industry_summary)),
    )
    return fig


def build_correlation_matrix(
    scores_df: pd.DataFrame, features_df: pd.DataFrame, feature_cols: List[str]
) -> pd.DataFrame:
    merged = scores_df.merge(features_df[["id"] + feature_cols], on="id", how="left")
    corr_cols = feature_cols + [
        "deep_tech_score",
        "description_score",
        "founder_background_score",
        "regulated_score",
        "market_type_pts",
        "geo_ops_score",
        "technical_score",
        "practical_score",
        "complexity_score",
    ]
    return merged[corr_cols].corr()


def build_correlation_heatmap(corr_matrix: pd.DataFrame) -> go.Figure:
    fig = go.Figure(
        data=go.Heatmap(
            z=corr_matrix.values,
            x=corr_matrix.columns.tolist(),
            y=corr_matrix.columns.tolist(),
            colorscale="RdBu",
            zmid=0,
            zmin=-1,
            zmax=1,
        )
    )
    fig.update_layout(title="Correlation Heatmap")
    return fig
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_generate_dashboard.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_dashboard.py tests/test_generate_dashboard.py
git commit -m "feat: add Phase 10 industry chart and correlation heatmap"
```

---

## Task 4: Company table records + HTML/JS table builder

**Files:**
- Modify: `scripts/generate_dashboard.py`
- Modify: `tests/test_generate_dashboard.py`

**Interfaces:**
- Consumes: (none from earlier tasks directly — takes plain DataFrames)
- Produces:
  - `build_company_records(scores_df: pd.DataFrame, company_industries_df: pd.DataFrame, team_sizes_df: pd.DataFrame) -> List[dict]`
  - `build_table_html(records: List[dict]) -> str`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_generate_dashboard.py`:

```python
import json
import re

from scripts.generate_dashboard import build_company_records, build_table_html


def test_build_company_records_handles_missing_teamsize_and_empty_industries():
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
    company_industries_df = pd.DataFrame({"id": [1, 2], "industries": ["Fintech", ""]})
    team_sizes_df = pd.DataFrame({"id": [1, 2], "teamSize": [5.0, float("nan")]})

    records = build_company_records(scores_df, company_industries_df, team_sizes_df)

    assert len(records) == 2
    acme = next(r for r in records if r["slug"] == "acme")
    assert acme["teamSize"] == 5.0
    assert acme["industries"] == "Fintech"
    beta = next(r for r in records if r["slug"] == "beta")
    assert beta["teamSize"] is None
    assert beta["industries"] == ""


def test_build_company_records_produces_valid_json_with_none_not_nan():
    scores_df = pd.DataFrame(
        {
            "id": [1],
            "slug": ["acme"],
            "name": ["Acme"],
            "batch": ["W24"],
            "status": ["Active"],
            "technical_score": [10.0],
            "practical_score": [5.0],
            "complexity_score": [15.0],
        }
    )
    company_industries_df = pd.DataFrame({"id": [1], "industries": [""]})
    team_sizes_df = pd.DataFrame({"id": [1], "teamSize": [float("nan")]})

    records = build_company_records(scores_df, company_industries_df, team_sizes_df)
    json_str = json.dumps(records)

    # json.dumps emits a bare `NaN` token (not valid per strict JSON, and
    # rejected by a browser's JSON.parse) unless NaN was already replaced
    # with None before this call.
    assert "NaN" not in json_str
    parsed = json.loads(json_str)
    assert parsed[0]["teamSize"] is None


def test_build_table_html_embeds_escaped_json_and_expected_structure():
    records = [
        {
            "id": 1,
            "slug": "acme",
            "name": "Acme </script> Co",
            "batch": "W24",
            "status": "Active",
            "industries": "Fintech",
            "teamSize": 5.0,
            "technical_score": 10.0,
            "practical_score": 5.0,
            "complexity_score": 15.0,
        }
    ]

    html = build_table_html(records)

    assert '<table id="company-table">' in html
    assert 'data-key="complexity_score"' in html

    # Non-greedy match stops at the FIRST </script> it finds. If the name's
    # literal "</script>" substring weren't escaped, this would find that
    # instead of the real closing tag, truncating the payload early — this
    # test would then fail to json.loads() a complete, valid record.
    match = re.search(
        r'<script id="company-data" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match, "company-data script tag not found or was truncated early"
    payload = match.group(1)
    assert "</script>" not in payload
    parsed = json.loads(payload.replace("<\\/", "</"))
    assert parsed[0]["name"] == "Acme </script> Co"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_generate_dashboard.py -v`
Expected: `ImportError: cannot import name 'build_company_records'`

- [ ] **Step 3: Implement `build_company_records` and `build_table_html`**

Add `import json` and `import math` to the top imports of `scripts/generate_dashboard.py` (alongside the existing `from pathlib import Path`), then add to the end of the file:

```python
def build_company_records(
    scores_df: pd.DataFrame, company_industries_df: pd.DataFrame, team_sizes_df: pd.DataFrame
) -> List[dict]:
    """
    One dict per company, JSON-safe (NaN replaced with None — json.dumps'
    default NaN output is not valid JSON and a browser's JSON.parse rejects
    it).
    """
    merged = scores_df.merge(company_industries_df, on="id", how="left")
    merged = merged.merge(team_sizes_df[["id", "teamSize"]], on="id", how="left")
    columns = [
        "id",
        "slug",
        "name",
        "batch",
        "status",
        "industries",
        "teamSize",
        "technical_score",
        "practical_score",
        "complexity_score",
    ]
    records = merged[columns].to_dict(orient="records")
    for record in records:
        for key, value in record.items():
            if isinstance(value, float) and math.isnan(value):
                record[key] = None
    return records


TABLE_COLUMNS = [
    ("slug", "Slug"),
    ("name", "Name"),
    ("batch", "Batch"),
    ("status", "Status"),
    ("industries", "Industries"),
    ("teamSize", "Team Size"),
    ("technical_score", "Technical"),
    ("practical_score", "Practical"),
    ("complexity_score", "Complexity"),
]


def build_table_html(records: List[dict]) -> str:
    """
    A sortable/filterable/searchable company table: data embedded as a JSON
    payload, everything else hand-rolled vanilla JS (no table library).
    `</` is escaped to `<\\/` in the JSON payload so a field value containing
    the literal substring `</script>` cannot prematurely close the
    surrounding <script> tag.
    """
    json_payload = json.dumps(records).replace("</", "<\\/")
    header_cells = "".join(
        f'<th data-key="{key}">{label}</th>' for key, label in TABLE_COLUMNS
    )

    return f"""
<div class="table-controls">
  <input type="text" id="search-box" placeholder="Search by name...">
  <select id="batch-filter"><option value="">All Batches</option></select>
  <select id="status-filter"><option value="">All Statuses</option></select>
  <select id="industry-filter"><option value="">All Industries</option></select>
  <span id="company-count"></span>
</div>
<table id="company-table">
  <thead><tr>{header_cells}</tr></thead>
  <tbody id="company-table-body"></tbody>
</table>
<script id="company-data" type="application/json">{json_payload}</script>
<script>
(function () {{
  const records = JSON.parse(document.getElementById("company-data").textContent);
  let sortKey = "complexity_score";
  let sortAsc = false;

  const tbody = document.getElementById("company-table-body");
  const searchBox = document.getElementById("search-box");
  const batchFilter = document.getElementById("batch-filter");
  const statusFilter = document.getElementById("status-filter");
  const industryFilter = document.getElementById("industry-filter");
  const countLabel = document.getElementById("company-count");

  function uniqueSorted(values) {{
    return Array.from(new Set(values)).sort();
  }}

  function addOptions(select, values) {{
    values.forEach((v) => {{
      const opt = document.createElement("option");
      opt.value = v;
      opt.textContent = v;
      select.appendChild(opt);
    }});
  }}

  function populateFilters() {{
    addOptions(batchFilter, uniqueSorted(records.map((r) => r.batch)));
    addOptions(statusFilter, uniqueSorted(records.map((r) => r.status)));
    const allIndustries = new Set();
    records.forEach((r) => {{
      (r.industries || "").split(", ").forEach((ind) => {{
        if (ind) allIndustries.add(ind);
      }});
    }});
    addOptions(industryFilter, Array.from(allIndustries).sort());
  }}

  function currentFilters() {{
    return {{
      search: searchBox.value.trim().toLowerCase(),
      batch: batchFilter.value,
      status: statusFilter.value,
      industry: industryFilter.value,
    }};
  }}

  function matchesFilters(record, filters) {{
    if (filters.search && !record.name.toLowerCase().includes(filters.search)) {{
      return false;
    }}
    if (filters.batch && record.batch !== filters.batch) {{
      return false;
    }}
    if (filters.status && record.status !== filters.status) {{
      return false;
    }}
    if (filters.industry && !(record.industries || "").includes(filters.industry)) {{
      return false;
    }}
    return true;
  }}

  function makeCell(value) {{
    const td = document.createElement("td");
    td.textContent = value === null || value === undefined ? "" : value;
    return td;
  }}

  function render() {{
    const filters = currentFilters();
    const filtered = records.filter((r) => matchesFilters(r, filters));
    filtered.sort((a, b) => {{
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      if (av < bv) return sortAsc ? -1 : 1;
      if (av > bv) return sortAsc ? 1 : -1;
      return 0;
    }});

    const fragment = document.createDocumentFragment();
    filtered.forEach((r) => {{
      const tr = document.createElement("tr");
      tr.appendChild(makeCell(r.slug));
      tr.appendChild(makeCell(r.name));
      tr.appendChild(makeCell(r.batch));
      tr.appendChild(makeCell(r.status));
      tr.appendChild(makeCell(r.industries));
      tr.appendChild(makeCell(r.teamSize));
      tr.appendChild(makeCell(r.technical_score));
      tr.appendChild(makeCell(r.practical_score));
      tr.appendChild(makeCell(r.complexity_score));
      fragment.appendChild(tr);
    }});
    tbody.innerHTML = "";
    tbody.appendChild(fragment);

    countLabel.textContent = filtered.length + " of " + records.length + " companies";
  }}

  document.querySelectorAll("#company-table thead th").forEach((th) => {{
    th.style.cursor = "pointer";
    th.addEventListener("click", () => {{
      const key = th.getAttribute("data-key");
      if (sortKey === key) {{
        sortAsc = !sortAsc;
      }} else {{
        sortKey = key;
        sortAsc = true;
      }}
      render();
    }});
  }});

  [searchBox, batchFilter, statusFilter, industryFilter].forEach((el) => {{
    el.addEventListener("input", render);
  }});

  populateFilters();
  render();
}})();
</script>
"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_generate_dashboard.py -v`
Expected: 14 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_dashboard.py tests/test_generate_dashboard.py
git commit -m "feat: add Phase 10 company table records and HTML/JS table builder"
```

---

## Task 5: Dashboard body + standalone HTML assembly

**Files:**
- Modify: `scripts/generate_dashboard.py`
- Modify: `tests/test_generate_dashboard.py`

**Interfaces:**
- Consumes: `build_distribution_chart`, `build_scatter_chart`, `build_batch_chart`, `build_status_chart`, `build_industry_chart`, `build_correlation_heatmap` (Tasks 2-3)
- Produces:
  - `build_dashboard_body(scores_df: pd.DataFrame, industry_exploded_df: pd.DataFrame, corr_matrix: pd.DataFrame, table_html: str) -> str`
  - `build_standalone_dashboard(body: str, title: str = "YC Complexity Index Dashboard") -> str`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_generate_dashboard.py`:

```python
from scripts.generate_dashboard import build_dashboard_body, build_standalone_dashboard


def _sample_scores_df():
    return pd.DataFrame(
        {
            "id": [1, 2],
            "name": ["Acme", "Beta"],
            "batch": ["W24", "S23"],
            "status": ["Active", "Active"],
            "technical_score": [10.0, 5.0],
            "practical_score": [5.0, 10.0],
            "complexity_score": [15.0, 15.0],
        }
    )


def test_build_dashboard_body_contains_one_bundle_and_all_six_charts():
    scores_df = _sample_scores_df()
    industry_exploded_df = scores_df.assign(industry="Fintech")
    corr_matrix = pd.DataFrame({"a": [1.0, 0.5], "b": [0.5, 1.0]}, index=["a", "b"])
    table_html = '<table id="company-table"></table>'

    body = build_dashboard_body(scores_df, industry_exploded_df, corr_matrix, table_html)

    assert body.count("plotly.js v") == 1
    for div_id in [
        "chart-distribution",
        "chart-scatter",
        "chart-batch",
        "chart-status",
        "chart-industry",
        "chart-heatmap",
    ]:
        assert div_id in body
    assert "<html" not in body.lower()
    assert "<table id=\"company-table\"></table>" in body


def test_build_standalone_dashboard_wraps_body_exactly_once():
    body = "<div>hello</div>"

    html = build_standalone_dashboard(body)

    assert html.count("<html") == 1
    assert html.count("<head>") == 1
    assert html.count("<body>") == 1
    assert "<div>hello</div>" in html
    assert "<title>YC Complexity Index Dashboard</title>" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_generate_dashboard.py -v`
Expected: `ImportError: cannot import name 'build_dashboard_body'`

- [ ] **Step 3: Implement `build_dashboard_body` and `build_standalone_dashboard`**

Add `import plotly.offline as pyo` to the top imports of `scripts/generate_dashboard.py` (alongside `import plotly.graph_objects as go`), then add to the end of the file:

```python
STYLE = """
<style>
  body { font-family: sans-serif; margin: 2rem; }
  h1 { margin-bottom: 0.5rem; }
  .chart { margin-bottom: 2rem; }
  table { border-collapse: collapse; width: 100%; }
  th, td { border: 1px solid #ccc; padding: 4px 8px; text-align: left; }
  th { background: #f0f0f0; }
  .table-controls { margin-bottom: 1rem; }
  .table-controls input, .table-controls select { margin-right: 0.5rem; }
</style>
"""


def build_dashboard_body(
    scores_df: pd.DataFrame,
    industry_exploded_df: pd.DataFrame,
    corr_matrix: pd.DataFrame,
    table_html: str,
) -> str:
    """
    Body-only HTML (no <html>/<head>/<body> tags): one inline Plotly.js
    bundle (never duplicated per chart), 6 chart sections, and the company
    table.
    """
    chart_specs = [
        ("chart-distribution", "Score Distribution", build_distribution_chart(scores_df)),
        ("chart-scatter", "Technical vs Practical", build_scatter_chart(scores_df)),
        ("chart-batch", "Complexity by Batch", build_batch_chart(scores_df)),
        ("chart-status", "Complexity by Status", build_status_chart(scores_df)),
        ("chart-industry", "Complexity by Industry", build_industry_chart(industry_exploded_df)),
        ("chart-heatmap", "Correlation Heatmap", build_correlation_heatmap(corr_matrix)),
    ]

    chart_sections = "\n".join(
        f'<div class="chart"><h2>{title}</h2>'
        f'{fig.to_html(full_html=False, include_plotlyjs=False, div_id=div_id)}</div>'
        for div_id, title, fig in chart_specs
    )

    plotly_bundle = f"<script>{pyo.get_plotlyjs()}</script>"

    return (
        f"{STYLE}{plotly_bundle}"
        f"<h1>Y Combinator Complexity Index Dashboard</h1>"
        f"{chart_sections}"
        f"<h2>Company Explorer</h2>{table_html}"
    )


def build_standalone_dashboard(
    body: str, title: str = "YC Complexity Index Dashboard"
) -> str:
    """Wrap body-only HTML in a minimal standalone document."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
</head>
<body>
{body}
</body>
</html>
"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_generate_dashboard.py -v`
Expected: 16 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_dashboard.py tests/test_generate_dashboard.py
git commit -m "feat: add Phase 10 dashboard body and standalone HTML assembly"
```

---

## Task 6: CLI `main()`, real run, structural verification, and roadmap updates

**Files:**
- Modify: `scripts/generate_dashboard.py`
- Modify: `documentation/plan_complexity_metric/roadmap.md`
- Modify: `documentation/plan/roadmap_todo.md`
- Create (by running the script): `output/complexity_dashboard_v1.html`

**Interfaces:**
- Consumes: `load_dashboard_data`, `aggregate_company_industries`, `explode_industries`, `build_correlation_matrix`, `build_company_records`, `build_table_html`, `build_dashboard_body`, `build_standalone_dashboard` (Tasks 1-5)

- [ ] **Step 1: Implement `main()`**

Add to the end of `scripts/generate_dashboard.py`:

```python
def main() -> None:
    data = load_dashboard_data(SCORES_PATH, FEATURES_PATH, INDUSTRIES_PATH, COMPANIES_PATH)
    scores_df = data["scores"]
    features_df = data["features"]
    industries_df = data["industries"]
    companies_df = data["companies"]

    industry_exploded_df = explode_industries(scores_df, industries_df)
    company_industries_df = aggregate_company_industries(scores_df, industries_df)
    team_sizes_df = companies_df[["id", "teamSize"]]

    feature_cols = [
        c for c in features_df.columns if c not in ("id", "slug", "name", "batch", "status")
    ]
    corr_matrix = build_correlation_matrix(scores_df, features_df, feature_cols)

    records = build_company_records(scores_df, company_industries_df, team_sizes_df)
    table_html = build_table_html(records)

    body = build_dashboard_body(scores_df, industry_exploded_df, corr_matrix, table_html)
    standalone = build_standalone_dashboard(body)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(standalone, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the full test suite to confirm no regressions**

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: all tests pass (93 pre-existing + 16 from Tasks 1-5 = 109).

- [ ] **Step 3: Run the generator for real**

Run: `./.venv/Scripts/python.exe scripts/generate_dashboard.py`
Expected: exits 0, prints `Wrote <repo>/output/complexity_dashboard_v1.html`.

- [ ] **Step 4: Structural verification of the real output**

Run:
```bash
./.venv/Scripts/python.exe -c "
import json
import re
from pathlib import Path

html = Path('output/complexity_dashboard_v1.html').read_text(encoding='utf-8')

assert html.count('<html') == 1, 'expected exactly one <html tag'
assert html.count('plotly.js v') == 1, 'expected exactly one inline Plotly bundle'

for div_id in ['chart-distribution', 'chart-scatter', 'chart-batch', 'chart-status', 'chart-industry', 'chart-heatmap']:
    assert div_id in html, f'missing chart div {div_id}'

assert '<table id=\"company-table\">' in html

match = re.search(r'<script id=\"company-data\" type=\"application/json\">(.*?)</script>', html, re.DOTALL)
assert match, 'company-data script tag not found'
records = json.loads(match.group(1).replace('<\\\\/', '</'))
print('company record count:', len(records))
assert len(records) == 4844

acme_like = next(r for r in records if r['slug'] == 'circuithub')
print('circuithub record:', acme_like)
assert acme_like['industries'] == 'Industrials, Manufacturing and Robotics'
assert acme_like['teamSize'] == 58.0

sift = next(r for r in records if r['slug'] == 'sift')
assert sift['teamSize'] is None

opencurriculum = next(r for r in records if r['slug'] == 'opencurriculum')
assert opencurriculum['industries'] == ''

print('file size bytes:', len(html.encode('utf-8')))
print('ALL STRUCTURAL CHECKS PASSED')
"
```
Expected: prints `company record count: 4844`, the `circuithub` record with `industries: 'Industrials, Manufacturing and Robotics'` and `teamSize: 58.0`, confirms `sift`'s `teamSize` is `None` and `opencurriculum`'s `industries` is `''`, prints a file size around 6-6.5 MB (dominated by the ~4.85 MB inline Plotly bundle), and ends with `ALL STRUCTURAL CHECKS PASSED`.

- [ ] **Step 5: Manual visual verification (controller-only step, not part of automated tests)**

This step is performed by whoever is orchestrating implementation (the controller), not coded into the script or test suite — matching the design spec's Decision 7. Read `output/complexity_dashboard_v1.html`, extract everything between `<body>` and `</body>`, and publish it as a preview (e.g. via an Artifact-style tool that renders HTML) to visually confirm: all 6 charts render with real data (not blank), the company table renders with sortable headers, and the batch/status/industry filter dropdowns are populated. This is the equivalent of "start the dev server and use the feature in a browser" for a file:// artifact that has no dev server to start.

- [ ] **Step 6: Update `documentation/plan_complexity_metric/roadmap.md`**

Insert a new checklist item 10 (renumbering the existing item 10 "Documentation & reproducibility" to item 11), immediately after item 9's block:

```markdown
- [x] **10. Visualization dashboard**
  - [x] Interactive charts mirroring Phase 9's analysis (distribution, technical vs practical, batch, status, industry, correlation heatmap)
  - [x] Searchable/sortable/filterable company explorer table (4,844 companies)
  - [x] Self-contained, offline-capable single HTML file (Plotly.js bundled inline, no CDN, no server)
  - [x] Output: `output/complexity_dashboard_v1.html`

- [ ] **11. Documentation & reproducibility**
  - [ ] Update main README
  - [ ] Add pipeline usage instructions
  - [ ] Write minimal test suite
  - [ ] Version control all outputs
```

Remove the old, now-superseded item 10 block (the one this replaces — the one with the same 4 sub-bullets currently numbered 10, immediately following this new insertion).

Update the timeline table: add a new row after the "9. Validation" row:
```markdown
| 10. Visualization | 1 day | ✅ Complete |
| 11. Documentation | 1 day | 🔲 Not started |
```
(remove the old, now-renumbered "10. Documentation" row it replaces), and update the total-complete percentage to `~91% complete` (10 of 11 phases substantively done, with the Phase 9.5 rubric-revision decision still open as noted in Phase 9's roadmap entry).

Update "Next Immediate Actions":
```markdown
## Next Immediate Actions

**Current Focus:** Phase 11 - Documentation & Reproducibility (with the open Phase 9.5 rubric-revision decision from Phase 9 still unresolved)

**Next Steps:**
1. Decide on the deferred Phase 9.5 question (revise `score.py`'s weights/caps to address the confirmed team-size correlation and distribution-spread gaps) before or alongside Phase 11 — still not decided as of Phase 10.
2. Update the main `README.md` with a Complexity Index section, pipeline usage instructions (including how to run `scripts/generate_dashboard.py` and open `output/complexity_dashboard_v1.html`), a minimal test suite for anything still untested, and version-control notes for all outputs.
3. Output (Phase 11): updated `README.md` + usage docs.

**To continue:** Mark this task complete and proceed to Phase 11 (or the Phase 9.5 decision first).
```

- [ ] **Step 7: Update `documentation/plan/roadmap_todo.md`**

Add a new checklist item after item 9 (renumbering everything from the old item 10 onward by one):

```markdown
- [x] 9. Validate & analyze index
- [x] 10. Build visualization dashboard
- [ ] 11. Documentation & reproducibility
- [ ] 12. Deploy & monitor
- [ ] 13. Maintain interactive todo file
```

- [ ] **Step 8: Commit**

```bash
git add scripts/generate_dashboard.py output/complexity_dashboard_v1.html documentation/plan_complexity_metric/roadmap.md documentation/plan/roadmap_todo.md
git commit -m "feat: add Phase 10 CLI runner, real dashboard output, and roadmap updates"
```

---

## Self-Review Notes

- **Spec coverage:** Decision 1 (static, no server) — the whole architecture, no server code anywhere. Decision 2 (inline bundle, once) — Task 5's `build_dashboard_body` calls `pyo.get_plotlyjs()` exactly once, tested explicitly (`body.count("plotly.js v") == 1`). Decision 3 (no cross-filtering) — charts (Tasks 2-3) and the table (Task 4) never share JS state; verified by construction (separate functions, separate `<script>` blocks). Decision 4 (hand-rolled table, no library) — Task 4's `build_table_html` uses only vanilla JS, no new JS dependency. Decision 5 (no pagination) — Task 4's table renders all filtered rows via a `DocumentFragment`, no page-size logic; Task 6 Step 5 explicitly calls out this as the thing to watch during manual verification, per the spec's stated fallback-if-needed. Decision 6 (`plotly` dependency) — Task 1 Step 1. Decision 7 (verification without a browser tool) — Task 6 Steps 4 (automated structural check) and 5 (manual visual pass, explicitly not delegated to the test suite).
- **XSS/breakage safety (Global Constraints):** `build_table_html`'s JS renders every cell via `makeCell()`'s `td.textContent = ...`, never `innerHTML` string concatenation — verified by the absence of any `innerHTML = ... + record...` pattern in Task 4's implementation. The JSON payload's `</` → `<\/` escape is unit-tested directly (`test_build_table_html_embeds_escaped_json_and_expected_structure`, using a company name containing the literal string `</script>` as the fixture).
- **Type/naming consistency:** `scores_df`, `industry_exploded_df`, `company_industries_df`, `team_sizes_df`, `corr_matrix`, `records`, `table_html`, `body` — every later task's function signature uses the exact same parameter names and types as the producing task defined them (Task 1's `aggregate_company_industries`/`explode_industries` outputs feed Task 6's `main()` under the same names; Task 2-3's 6 chart-builder functions are called with the exact same argument DataFrames inside Task 5's `build_dashboard_body`).
- **No placeholders:** every code block is complete and was validated by prototyping the full pipeline against the real `data/processed/` files before this plan was written (see Global Constraints' "Real-data verified values" — `(4844, 14)`, `(4844, 12)`, `(17, 17)`, 55 industries, and the three named company fixtures were all confirmed by actually running the planned functions against real data, not estimated).
- **Known limitation:** Task 6 Step 5 (manual visual verification) cannot be executed by an implementer subagent the way the rest of this plan's steps can — it requires a tool (an HTML-preview/Artifact-style capability) that may only be available to whoever is orchestrating the overall implementation, not to a sandboxed coding subagent. This is flagged explicitly in the step itself rather than silently assumed away.
