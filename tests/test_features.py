import pandas as pd
import pytest

from src.etl.features import (
    FEATURE_COLUMNS,
    build_feature_table,
    compute_deep_tech_tag_count,
    compute_founder_phd_count,
    compute_international_operations,
    compute_market_type_score,
    compute_operational_intensity,
    compute_regulated_industry,
    compute_research_company_experience,
    count_countries_mentioned,
    normalize_country_names,
    score_description_tech,
    validate_features,
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


def test_compute_founder_phd_count_counts_distinct_founders_with_phd():
    founders_df = pd.DataFrame(
        {
            "hnid": ["a", "b", "c", "d"],
            "company_slug": ["acme", "acme", "beta", "beta"],
        }
    )
    schools_df = pd.DataFrame(
        {
            "hnid": ["a", "a", "b", "c"],
            "field_of_study": [
                "Doctor Of Philosophy", "Computer Science", "Economics", "Phd",
            ],
        }
    )

    result = compute_founder_phd_count(founders_df, schools_df)

    counts = dict(zip(result["company_slug"], result["founder_phd_count"]))
    assert counts == {"acme": 1, "beta": 1}


def test_compute_founder_phd_count_deduplicates_multiple_phd_school_rows():
    founders_df = pd.DataFrame({"hnid": ["a"], "company_slug": ["acme"]})
    schools_df = pd.DataFrame(
        {"hnid": ["a", "a"], "field_of_study": ["Doctor Of Philosophy", "Ph.D."]}
    )

    result = compute_founder_phd_count(founders_df, schools_df)

    counts = dict(zip(result["company_slug"], result["founder_phd_count"]))
    assert counts == {"acme": 1}


def test_compute_research_company_experience_counts_distinct_founders():
    founders_df = pd.DataFrame(
        {"hnid": ["a", "b", "c"], "company_slug": ["acme", "acme", "beta"]}
    )
    prior_companies_df = pd.DataFrame(
        {
            "hnid": ["a", "b", "c"],
            "company": ["MIT Media Lab", "Acme Corp", "Stanford University"],
        }
    )

    result = compute_research_company_experience(founders_df, prior_companies_df)

    counts = dict(zip(result["company_slug"], result["research_company_experience"]))
    assert counts == {"acme": 1, "beta": 1}


def test_compute_founder_phd_count_uses_overridable_pattern():
    founders_df = pd.DataFrame({"hnid": ["a", "b"], "company_slug": ["acme", "acme"]})
    schools_df = pd.DataFrame(
        {"hnid": ["a", "b"], "field_of_study": ["Custom Doctorate", "Computer Science"]}
    )

    result = compute_founder_phd_count(
        founders_df, schools_df, phd_pattern=r"\bcustom doctorate\b"
    )

    counts = dict(zip(result["company_slug"], result["founder_phd_count"]))
    assert counts == {"acme": 1}


def test_compute_research_company_experience_uses_overridable_pattern():
    # "Widget Corp" / "Acme Ltd" deliberately avoid every keyword in the real
    # RESEARCH_PATTERN (university, institute, laboratory, lab, research,
    # nasa, jpl, cern) so this test only passes if the override is actually
    # used -- it would fail if research_pattern were silently ignored in
    # favor of the production default.
    founders_df = pd.DataFrame({"hnid": ["a", "b"], "company_slug": ["acme", "acme"]})
    prior_companies_df = pd.DataFrame(
        {"hnid": ["a", "b"], "company": ["Widget Corp", "Acme Ltd"]}
    )

    result = compute_research_company_experience(
        founders_df, prior_companies_df, research_pattern=r"\bwidget corp\b"
    )

    counts = dict(zip(result["company_slug"], result["research_company_experience"]))
    assert counts == {"acme": 1}


def _minimal_inputs():
    companies_df = pd.DataFrame(
        {
            "id": [1, 2],
            "slug": ["acme", "beta"],
            "name": ["Acme", "Beta"],
            "batch": ["W24", "S23"],
            "status": ["Active", "Active"],
            "longDescription": [
                "Acme builds a proprietary machine learning platform for India and Kenya.",
                "Beta is a local bakery.",
            ],
        }
    )
    tags_df = pd.DataFrame(
        {"id": [1, 1, 2], "tag": ["Artificial Intelligence", "B2B", "SaaS"]}
    )
    industries_df = pd.DataFrame({"id": [1], "industry": ["Fintech"]})
    regions_df = pd.DataFrame(
        {"id": [1, 2], "country": ["India", "United States of America"]}
    )
    founders_df = pd.DataFrame(
        {"hnid": ["a", "b"], "company_slug": ["acme", "beta"]}
    )
    schools_df = pd.DataFrame(
        {"hnid": ["a"], "field_of_study": ["Doctor Of Philosophy"]}
    )
    prior_companies_df = pd.DataFrame({"hnid": ["b"], "company": ["Acme Corp"]})
    return (
        companies_df, tags_df, industries_df, regions_df,
        founders_df, schools_df, prior_companies_df,
    )


def test_build_feature_table_has_one_row_per_company_and_no_missing_values():
    inputs = _minimal_inputs()

    features_df = build_feature_table(*inputs)

    assert len(features_df) == 2
    assert set(features_df["id"]) == {1, 2}
    feature_cols = [
        "deep_tech_tag_count", "description_tech_score", "founder_phd_count",
        "research_company_experience", "regulated_industry", "market_type_score",
        "international_operations", "operational_intensity",
    ]
    for col in feature_cols:
        assert features_df[col].notna().all()


def test_build_feature_table_computes_expected_values_for_acme():
    inputs = _minimal_inputs()

    features_df = build_feature_table(*inputs)

    acme = features_df[features_df["slug"] == "acme"].iloc[0]
    assert acme["deep_tech_tag_count"] == 1  # Artificial Intelligence
    assert acme["market_type_score"] == 3  # B2B
    assert acme["regulated_industry"] == 1  # Fintech
    assert acme["founder_phd_count"] == 1  # founder 'a' has a PhD
    assert acme["international_operations"] == 1  # "India" mentioned

    beta = features_df[features_df["slug"] == "beta"].iloc[0]
    assert beta["deep_tech_tag_count"] == 0
    assert beta["research_company_experience"] == 0  # "Acme Corp" isn't a research institution


def test_build_feature_table_returns_columns_in_spec_order():
    inputs = _minimal_inputs()

    features_df = build_feature_table(*inputs)

    expected_columns = ["id", "slug", "name", "batch", "status"] + FEATURE_COLUMNS
    assert list(features_df.columns) == expected_columns


def test_validate_features_passes_on_valid_table():
    inputs = _minimal_inputs()
    companies_df = inputs[0]
    features_df = build_feature_table(*inputs)

    validate_features(companies_df, features_df)  # should not raise


def test_validate_features_raises_on_row_count_mismatch():
    companies_df = pd.DataFrame({"id": [1, 2]})
    features_df = pd.DataFrame(
        {
            "id": [1],
            "deep_tech_tag_count": [0], "description_tech_score": [0],
            "founder_phd_count": [0], "research_company_experience": [0],
            "regulated_industry": [0], "market_type_score": [0],
            "international_operations": [0], "operational_intensity": [0],
        }
    )

    with pytest.raises(AssertionError, match="Row count"):
        validate_features(companies_df, features_df)


def test_validate_features_raises_on_missing_feature_values():
    companies_df = pd.DataFrame({"id": [1]})
    features_df = pd.DataFrame(
        {
            "id": [1],
            "deep_tech_tag_count": [None], "description_tech_score": [0],
            "founder_phd_count": [0], "research_company_experience": [0],
            "regulated_industry": [0], "market_type_score": [0],
            "international_operations": [0], "operational_intensity": [0],
        }
    )

    with pytest.raises(AssertionError, match="deep_tech_tag_count"):
        validate_features(companies_df, features_df)


from src.etl.features import run_feature_engineering_pipeline


def test_run_feature_engineering_pipeline_end_to_end(tmp_path):
    input_dir = tmp_path / "step3_enriched"
    output_dir = tmp_path / "features"
    input_dir.mkdir()

    companies = pd.DataFrame(
        [
            {
                "id": 1, "slug": "acme", "name": "Acme", "batch": "W24",
                "status": "Active",
                "longDescription": "Acme builds a proprietary machine learning platform.",
            },
            {
                "id": 2, "slug": "beta", "name": "Beta", "batch": "S23",
                "status": "Active", "longDescription": "Beta is a local bakery.",
            },
        ]
    )
    tags = pd.DataFrame({"id": [1], "tag": ["Artificial Intelligence"]})
    industries = pd.DataFrame({"id": [1], "industry": ["Fintech"]})
    regions = pd.DataFrame({"id": [1, 2], "country": ["United States of America", "India"]})
    founders = pd.DataFrame({"hnid": ["a"], "company_slug": ["acme"]})
    schools = pd.DataFrame({"hnid": ["a"], "field_of_study": ["Doctor Of Philosophy"]})
    prior_companies = pd.DataFrame({"hnid": [], "company": []})

    companies.to_csv(input_dir / "companies_enriched.csv", index=False)
    tags.to_csv(input_dir / "tags_enriched.csv", index=False)
    industries.to_csv(input_dir / "industries_enriched.csv", index=False)
    regions.to_csv(input_dir / "regions_enriched.csv", index=False)
    founders.to_csv(input_dir / "founders_enriched.csv", index=False)
    schools.to_csv(input_dir / "schools_enriched.csv", index=False)
    prior_companies.to_csv(input_dir / "prior_companies_enriched.csv", index=False)

    run_feature_engineering_pipeline(input_dir=input_dir, output_dir=output_dir)

    features_df = pd.read_parquet(output_dir / "complexity_features.parquet")
    assert len(features_df) == 2
    acme = features_df[features_df["slug"] == "acme"].iloc[0]
    assert acme["deep_tech_tag_count"] == 1
    assert acme["regulated_industry"] == 1
    assert acme["founder_phd_count"] == 1
