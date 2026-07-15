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
