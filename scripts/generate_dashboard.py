"""
Generates output/complexity_dashboard_v1.html — a self-contained, offline
HTML dashboard for exploring data/processed/scores/complexity_index_v1.csv,
per docs/superpowers/specs/2026-07-14-phase10-visualization-dashboard-design.md.

Run: ./.venv/Scripts/python.exe scripts/generate_dashboard.py

This phase only visualizes the already-computed index; it does not
recompute or re-validate any scores.
"""

import json
import math
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import plotly.graph_objects as go

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
