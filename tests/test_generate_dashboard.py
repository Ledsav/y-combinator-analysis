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
