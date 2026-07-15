"""
Generates output/complexity_dashboard_v2.html — a self-contained, offline
HTML dashboard for exploring data/processed/scores/complexity_index_v2.csv,
per docs/superpowers/specs/2026-07-14-phase10-visualization-dashboard-design.md
(original dashboard architecture) and
docs/superpowers/specs/2026-07-14-phase9.5-rubric-revision-design.md
(v2 rubric + retargeting to v2, plus the About This Index section).

Run: ./.venv/Scripts/python.exe scripts/generate_dashboard.py

This script only visualizes the already-computed index; it does not
recompute or re-validate any scores.
"""

import json
import math
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import plotly.graph_objects as go
import plotly.offline as pyo

REPO_ROOT = Path(__file__).resolve().parents[1]
SCORES_PATH = REPO_ROOT / "data" / "processed" / "scores" / "complexity_index_v2.csv"
FEATURES_PATH = REPO_ROOT / "data" / "processed" / "features" / "complexity_features.parquet"
INDUSTRIES_PATH = REPO_ROOT / "data" / "processed" / "step3_enriched" / "industries_enriched.csv"
COMPANIES_PATH = REPO_ROOT / "data" / "processed" / "step3_enriched" / "companies_enriched.csv"
OUTPUT_PATH = REPO_ROOT / "output" / "complexity_dashboard_v2.html"


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
    tags are still present), with a comma-joined `industries` display string
    ("" if none) and an `industries_list` column (a Python list of the
    individual industry tags, [] if none) derived directly from the
    untouched multi-row industries_df — not by splitting the joined string,
    since some real industry names contain the literal ", " delimiter
    (e.g. "Engineering, Product and Design") and splitting on it would
    shatter them into bogus fragments.
    """
    grouped = (
        industries_df.groupby("id")["industry"]
        .agg(list)
        .reset_index()
        .rename(columns={"industry": "industries_list"})
    )
    result = scores_df[["id"]].merge(grouped, on="id", how="left")
    result["industries_list"] = result["industries_list"].apply(
        lambda v: v if isinstance(v, list) else []
    )
    result["industries"] = result["industries_list"].apply(lambda v: ", ".join(v))
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
        "industries_list",
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
      (r.industries_list || []).forEach((ind) => {{
        allIndustries.add(ind);
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
    if (filters.industry && !(record.industries_list || []).includes(filters.industry)) {{
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


STYLE = """
<style>
  body { font-family: sans-serif; margin: 2rem; }
  h1 { margin-bottom: 0.5rem; }
  .about, .findings { background: #f7f7f7; border: 1px solid #ddd; border-radius: 4px; padding: 1rem 1.5rem; margin-bottom: 2rem; }
  .about h2, .findings h2 { margin-top: 0; }
  .about p { margin: 0.5rem 0; }
  .findings li { margin-bottom: 0.5rem; }
  .chart { margin-bottom: 2rem; }
  table { border-collapse: collapse; width: 100%; }
  th, td { border: 1px solid #ccc; padding: 4px 8px; text-align: left; }
  th { background: #f0f0f0; }
  .table-controls { margin-bottom: 1rem; }
  .table-controls input, .table-controls select { margin-right: 0.5rem; }
</style>
"""


def build_about_section() -> str:
    """
    Explains what the score measures, how it's computed, and how to read
    it — placed before Key Findings so a first-time visitor has the
    context needed to interpret the charts and table that follow.
    """
    return """
<section class="about">
<h2>About This Index</h2>
<p><strong>What it measures:</strong> a 0-100 Complexity Index combining Technical difficulty (building the core technology) and Practical/Market difficulty (executing in the market) for each Y Combinator company.</p>
<p><strong>How it's built:</strong> capped linear scaling &mdash; each raw signal (deep-tech tags, regulatory status, market type, etc.) is scaled from 0 up to a cap, then clipped. Caps come from the 95th&ndash;99th percentile of real observed values, so rare outliers don't dominate the scale.</p>
<p><strong>The weighting (Phase 9.5 revision):</strong> Technical component 0&ndash;30 points (deep-tech tags, R&amp;D-vocabulary in descriptions, founder background), Practical component 0&ndash;70 points (regulated industry, market type, geography &amp; operations). This shifted from an original 50/50 split because practical signals cover far more of the company base &mdash; most YC companies aren't deep-tech, so a 50-point technical budget was mostly wasted on zeros for about half the dataset.</p>
<p><strong>Key assumptions:</strong> deep-tech signal comes from tags and description keywords, not a hands-on technical audit; "regulated" is industry-based, not a legal determination; team size wasn't found to reliably predict complexity in this dataset, so it isn't part of the formula.</p>
<p><strong>How to read a score:</strong> roughly, <strong>0&ndash;20 = minimal</strong> complexity (plain consumer/SaaS, no regulation or deep-tech signal), <strong>20&ndash;40 = moderate</strong> (the bulk of companies &mdash; some regulation or market complexity; the median score is 25.5), <strong>40+ = high</strong> (roughly the top 10% &mdash; deep-tech and/or heavily regulated, p90 is 42).</p>
<p><strong>Known limitations:</strong> this index does not correlate strongly with team size (r=0.10), and the score distribution remains narrower than originally targeted (std=11.95 vs an original aspiration of &ge;15). Both are explained by real "no signal" mass in about half the dataset &mdash; most companies simply have zero deep-tech indicators &mdash; not a tuning failure. See the project roadmap for the full diagnostic writeup.</p>
</section>
"""


def build_findings_summary() -> str:
    """
    A scannable "Key Findings" summary placed after About This Index and
    before the charts, adapting the notebook's Phase 9.5 analysis into
    dashboard-appropriate bullets. All numbers are the same verified
    figures re-derived on complexity_index_v2.csv.
    """
    return """
<section class="findings">
<h2>Key Findings</h2>
<ul>
<li><strong>Regulated and operations-heavy industries now dominate the top of the index</strong> &mdash; Legal (49.4), Finance and Accounting (46.6), and Supply Chain and Logistics (42.7) lead, ahead of Drug Discovery and Delivery (40.5). Consumer/content industries remain at the bottom &mdash; Education (8.5), Social (10.9), Content (11.8).</li>
<li><strong>Complexity has risen steadily across YC batches</strong> &mdash; from ~19 in the earliest batches (S05&ndash;S09) to ~34 in the most recent (S22&ndash;S24), the same upward shape observed before this rubric revision.</li>
<li><strong>Technical and practical complexity are independent dimensions</strong> (correlation &asymp; -0.05), confirming the rubric measures two distinct kinds of difficulty rather than one thing twice.</li>
<li><strong>Industry tags behave as expected</strong> &mdash; Healthcare-tagged companies score ~1.9x the overall average on technical complexity; Fintech-tagged companies score higher on practical complexity and universally receive the full regulated-industry bonus.</li>
<li><strong>Active and Public companies score similarly</strong> (~29 both), each above Acquired (23.9) and Inactive (22.3).</li>
<li><strong>A company can now reach a high score on practical complexity alone</strong> &mdash; since the practical budget (70 points) exceeds the entire previous version's observed maximum, several companies with zero technical signal (e.g. logistics and supply-chain operators) now rank in the top 25. This is an expected effect of shifting weight toward the practical dimension, not an anomaly.</li>
<li><strong>Known limitation:</strong> two quantitative calibration targets &mdash; correlation with team size and score distribution spread &mdash; were revisited in this rubric revision. Both improved meaningfully (r: 0.035&rarr;0.103, &sigma;: 10.11&rarr;11.95) but remain short of their original targets, which have been formally relaxed rather than further chased (see About This Index above).</li>
</ul>
</section>
"""


def build_dashboard_body(
    scores_df: pd.DataFrame,
    industry_exploded_df: pd.DataFrame,
    corr_matrix: pd.DataFrame,
    table_html: str,
) -> str:
    """
    Body-only HTML (no <html>/<head>/<body> tags): one inline Plotly.js
    bundle (never duplicated per chart), a key-findings summary, 6 chart
    sections, and the company table.
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
    about_section = build_about_section()
    findings_summary = build_findings_summary()

    return (
        f"{STYLE}{plotly_bundle}"
        f"<h1>Y Combinator Complexity Index Dashboard</h1>"
        f"{about_section}"
        f"{findings_summary}"
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
