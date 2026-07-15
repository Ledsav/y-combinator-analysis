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
            "regulated_score": [0.0, 0.0, 0.0],
            "market_type_score": [0.0, 0.0, 0.0],
            "international_operations_score": [0.0, 0.0, 0.0],
            "operational_intensity_score": [0.0, 0.0, 0.0],
            "complexity_score": [40.0, 40.0, 40.0],
        }
    )
    features_df = pd.DataFrame({"id": [1, 2, 3], "deep_tech_tag_count": [1, 2, 3]})

    corr = build_correlation_matrix(scores_df, features_df, feature_cols=["deep_tech_tag_count"])

    # 1 feature col + 7 bucket-score cols + technical/practical/complexity = 11
    assert corr.shape == (11, 11)
    assert corr.loc["deep_tech_tag_count", "technical_score"] == pytest.approx(1.0)
    assert corr.loc["technical_score", "practical_score"] == pytest.approx(-1.0)


def test_build_correlation_matrix_discovers_bucket_score_columns_dynamically():
    """
    Proves build_correlation_matrix no longer hardcodes bucket column
    names -- any rubric bucket's <name>_score column is picked up
    automatically, which is the whole point of Phase 12's config-driven
    engine producing a dynamic schema.
    """
    scores_df = pd.DataFrame(
        {
            "id": [1, 2],
            "some_new_bucket_score": [10.0, 20.0],
            "technical_score": [10.0, 20.0],
            "practical_score": [5.0, 15.0],
            "complexity_score": [15.0, 35.0],
        }
    )
    features_df = pd.DataFrame({"id": [1, 2], "x": [1, 2]})

    corr = build_correlation_matrix(scores_df, features_df, feature_cols=["x"])

    assert "some_new_bucket_score" in corr.columns


def test_build_correlation_heatmap_uses_matrix_values_and_labels():
    corr_matrix = pd.DataFrame({"a": [1.0, 0.5], "b": [0.5, 1.0]}, index=["a", "b"])

    fig = build_correlation_heatmap(corr_matrix)

    assert fig.data[0].z.tolist() == [[1.0, 0.5], [0.5, 1.0]]
    assert list(fig.data[0].x) == ["a", "b"]
    assert list(fig.data[0].y) == ["a", "b"]


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
    assert acme["teamSize"] == 5.0
    assert acme["industries"] == "Fintech"
    assert acme["industries_list"] == ["Fintech"]
    beta = next(r for r in records if r["slug"] == "beta")
    assert beta["teamSize"] is None
    assert beta["industries"] == ""
    assert beta["industries_list"] == []


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
    company_industries_df = pd.DataFrame(
        {"id": [1], "industries": [""], "industries_list": [[]]}
    )
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


def test_build_findings_summary_contains_expected_section_and_key_stats():
    from scripts.generate_dashboard import build_findings_summary

    summary = build_findings_summary()

    assert '<section class="findings">' in summary
    assert "Key Findings" in summary
    assert "Drug Discovery and Delivery" in summary
    assert "Known limitation" in summary


def test_build_dashboard_body_includes_about_and_findings_before_charts():
    scores_df = _sample_scores_df()
    industry_exploded_df = scores_df.assign(industry="Fintech")
    corr_matrix = pd.DataFrame({"a": [1.0, 0.5], "b": [0.5, 1.0]}, index=["a", "b"])
    table_html = '<table id="company-table"></table>'

    body = build_dashboard_body(scores_df, industry_exploded_df, corr_matrix, table_html)

    assert '<section class="about">' in body
    assert '<section class="findings">' in body
    assert body.index('<section class="about">') < body.index('<section class="findings">')
    assert body.index('<section class="findings">') < body.index("chart-distribution")


def test_build_standalone_dashboard_wraps_body_exactly_once():
    body = "<div>hello</div>"

    html = build_standalone_dashboard(body)

    assert html.count("<html") == 1
    assert html.count("<head>") == 1
    assert html.count("<body>") == 1
    assert "<div>hello</div>" in html
    assert "<title>YC Complexity Index Dashboard</title>" in html


def test_aggregate_company_industries_preserves_names_containing_the_join_delimiter():
    scores_df = pd.DataFrame({"id": [1]})
    industries_df = pd.DataFrame(
        {"id": [1, 1], "industry": ["Engineering, Product and Design", "Consumer"]}
    )

    result = aggregate_company_industries(scores_df, industries_df).set_index("id")

    assert result.loc[1, "industries_list"] == ["Engineering, Product and Design", "Consumer"]
    assert result.loc[1, "industries"] == "Engineering, Product and Design, Consumer"


def test_build_table_html_embeds_industries_list_for_exact_filter_matching():
    records = [
        {
            "id": 1,
            "slug": "acme",
            "name": "Acme",
            "batch": "W24",
            "status": "Active",
            "industries": "Consumer Finance",
            "industries_list": ["Consumer Finance"],
            "teamSize": 5.0,
            "technical_score": 10.0,
            "practical_score": 5.0,
            "complexity_score": 15.0,
        }
    ]

    html = build_table_html(records)

    match = re.search(
        r'<script id="company-data" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match, "company-data script tag not found"
    payload = json.loads(match.group(1).replace("<\\/", "</"))
    assert payload[0]["industries_list"] == ["Consumer Finance"]


def test_build_about_section_contains_expected_content():
    from scripts.generate_dashboard import build_about_section

    about = build_about_section()

    assert '<section class="about">' in about
    assert "About This Index" in about
    assert "30" in about and "70" in about
    assert "team size" in about.lower()
