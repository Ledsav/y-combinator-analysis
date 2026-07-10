import pandas as pd

from src.etl.features import (
    compute_deep_tech_tag_count,
    compute_international_operations,
    compute_market_type_score,
    compute_operational_intensity,
    compute_regulated_industry,
    count_countries_mentioned,
    normalize_country_names,
    score_description_tech,
)


def test_compute_deep_tech_tag_count_counts_matches_per_company():
    tags_df = pd.DataFrame(
        {
            "id": [1, 1, 1, 2, 3],
            "tag": ["Artificial Intelligence", "SaaS", "Robotics", "B2B", "Biotech"],
        }
    )
    deep_tech_tags = {"Artificial Intelligence", "Robotics", "Biotech"}

    result = compute_deep_tech_tag_count(tags_df, deep_tech_tags=deep_tech_tags)

    counts = dict(zip(result["id"], result["deep_tech_tag_count"]))
    assert counts == {1: 2, 3: 1}


def test_compute_deep_tech_tag_count_excludes_companies_with_no_matches():
    tags_df = pd.DataFrame({"id": [1], "tag": ["SaaS"]})

    result = compute_deep_tech_tag_count(tags_df, deep_tech_tags={"AI"})

    assert result.empty


def test_compute_regulated_industry_flags_matching_companies():
    tags_df = pd.DataFrame({"id": [1, 2], "tag": ["Fintech", "SaaS"]})
    industries_df = pd.DataFrame({"id": [3], "industry": ["Healthcare"]})

    result = compute_regulated_industry(
        tags_df, industries_df, regulated_labels={"Fintech", "Healthcare"}
    )

    matched_ids = set(result["id"])
    assert matched_ids == {1, 3}
    assert (result["regulated_industry"] == 1).all()


def test_compute_market_type_score_takes_highest_matching_type():
    tags_df = pd.DataFrame(
        {"id": [1, 1, 2, 3], "tag": ["B2B", "Marketplace", "Marketplace", "Consumer"]}
    )
    industries_df = pd.DataFrame({"id": [4], "industry": ["Other"]})

    result = compute_market_type_score(
        tags_df,
        industries_df,
        b2b_labels={"B2B"},
        marketplace_labels={"Marketplace"},
        b2c_labels={"Consumer"},
    )

    scores = dict(zip(result["id"], result["market_type_score"]))
    assert scores == {1: 3, 2: 2, 3: 1}


def test_compute_operational_intensity_counts_distinct_label_matches():
    tags_df = pd.DataFrame(
        {"id": [1, 1, 1, 2], "tag": ["Logistics", "Logistics", "Hardware", "SaaS"]}
    )
    industries_df = pd.DataFrame({"id": [1], "industry": ["Manufacturing"]})

    result = compute_operational_intensity(
        tags_df,
        industries_df,
        operational_labels={"Logistics", "Hardware", "Manufacturing"},
    )

    counts = dict(zip(result["id"], result["operational_intensity"]))
    assert counts == {1: 3}  # Logistics, Hardware, Manufacturing (duplicate Logistics row deduped)


def test_score_description_tech_counts_keyword_matches():
    text = "Our proprietary machine learning algorithm uses a novel neural network."
    patterns = [
        r"\bproprietary\b", r"\bmachine learning\b", r"\balgorithms?\b",
        r"\bnovel\b", r"\bneural networks?\b",
    ]

    score = score_description_tech(text, keyword_patterns=patterns)

    assert score == 5


def test_score_description_tech_returns_zero_for_missing_text():
    assert score_description_tech(None) == 0
    assert score_description_tech(float("nan")) == 0
    assert score_description_tech("") == 0


def test_normalize_country_names_maps_and_dedupes():
    result = normalize_country_names(
        ["United States of America", "India", "Remote", "India", None]
    )
    assert result == ["India", "United States"]


def test_count_countries_mentioned_counts_distinct_whole_word_matches():
    text = "We started in India and expanded to Kenya, then to Indiana."
    countries = ["India", "Kenya", "Nigeria"]

    count = count_countries_mentioned(text, countries)

    assert count == 2  # India and Kenya; "Indiana" must not match "India"


def test_count_countries_mentioned_returns_zero_for_missing_text():
    assert count_countries_mentioned(None, ["India"]) == 0


def test_compute_international_operations_counts_per_company():
    companies_df = pd.DataFrame(
        {
            "id": [1, 2],
            "longDescription": [
                "We operate in India and Kenya.",
                "A local bakery in Ohio.",
            ],
        }
    )
    regions_df = pd.DataFrame(
        {"id": [10, 11, 12], "country": ["United States of America", "India", "Kenya"]}
    )

    result = compute_international_operations(companies_df, regions_df)

    counts = dict(zip(result["id"], result["international_operations"]))
    assert counts == {1: 2, 2: 0}
