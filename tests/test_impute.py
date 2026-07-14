import pandas as pd
import pytest

from src.etl.impute import (
    add_founder_count,
    create_enrichment_priorities,
    extract_first_sentence,
    impute_oneliner_from_description,
    run_imputation_pipeline,
    validate_imputation,
)


def test_extract_first_sentence_handles_nan_and_non_string():
    assert extract_first_sentence(float("nan")) == ""
    assert extract_first_sentence(None) == ""


def test_extract_first_sentence_handles_empty_and_whitespace():
    assert extract_first_sentence("") == ""
    assert extract_first_sentence("   ") == ""


def test_extract_first_sentence_extracts_normal_sentence():
    text = "We build tools for developers. Second sentence here."
    assert extract_first_sentence(text) == "We build tools for developers."


def test_extract_first_sentence_falls_back_on_short_abbreviation_match():
    # "Acme Inc." is only 9 chars (<=10), so the primary regex match is
    # rejected as a likely abbreviation and the function falls back to
    # splitting on ". " (which discards the period).
    text = "Acme Inc. builds widgets for the widget industry."
    assert extract_first_sentence(text) == "Acme Inc"


def test_extract_first_sentence_returns_whole_short_string_with_no_fallback_split():
    # "Hi." has no trailing whitespace after its period (end of string), so
    # re.split(r"[.!?]\s+", ...) finds no match and returns the original
    # string unchanged.
    assert extract_first_sentence("Hi.") == "Hi."


def test_extract_first_sentence_truncates_at_100_chars_with_no_terminator():
    text = "word " * 30  # 150 chars, no '.', '!', or '?' anywhere
    result = extract_first_sentence(text)
    assert result == text[:100].strip()
    assert len(result) <= 100


def test_impute_oneliner_from_description_imputes_when_description_present():
    companies_df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "slug": ["acme", "beta", "gamma"],
            "oneLiner": ["Existing oneliner", None, None],
            "longDescription": [
                "Acme desc.",
                "Beta builds tools for devs. More text.",
                None,
            ],
        }
    )

    result_df, log = impute_oneliner_from_description(companies_df)

    # Existing oneLiner untouched
    assert result_df.loc[0, "oneLiner"] == "Existing oneliner"
    # Missing oneLiner + present longDescription -> imputed
    assert result_df.loc[1, "oneLiner"] == "Beta builds tools for devs."
    # Missing oneLiner + missing longDescription -> left alone, not even attempted
    assert pd.isna(result_df.loc[2, "oneLiner"])

    assert len(log) == 1
    assert log[0]["company_slug"] == "beta"
    assert log[0]["success"] is True
    assert log[0]["imputed_value"] == "Beta builds tools for devs."


def test_add_founder_count_aggregates_and_zero_fills():
    companies_df = pd.DataFrame({"id": [1, 2, 3], "slug": ["acme", "beta", "gamma"]})
    founders_df = pd.DataFrame({"company_slug": ["acme", "acme", "beta"]})

    result_df, log = add_founder_count(companies_df, founders_df)

    counts = dict(zip(result_df["slug"], result_df["founder_count"]))
    assert counts == {"acme": 2, "beta": 1, "gamma": 0}
    assert result_df["founder_count"].dtype.kind == "i"  # int, not float

    assert len(log) == 1
    assert log[0]["company_slug"] == "gamma"
    assert log[0]["success"] is False


def test_create_enrichment_priorities_scores_and_sorts_descending():
    companies_df = pd.DataFrame(
        {
            "id": [1, 2],
            "slug": ["acme", "beta"],
            "name": ["Acme", "Beta"],
            "status": ["Active", "Inactive"],
            "batch": ["W24", "W10"],
            "oneLiner": [None, "Has oneliner"],
            "longDescription": ["Has desc.", "Has desc."],
            "founder_count": [0, 2],
            "teamSize": [None, 5.0],
        }
    )

    priorities = create_enrichment_priorities(companies_df)

    acme = priorities[priorities["slug"] == "acme"].iloc[0]
    beta = priorities[priorities["slug"] == "beta"].iloc[0]
    # Acme: Active(30) + batch_year 2024>=2020(20) + missing_oneliner(15) + missing_founders(10) = 75
    assert acme["enrichment_score"] == 75
    assert acme["batch_year"] == 2024
    assert acme["missing_oneliner"] == True
    # Beta: Inactive(0) + batch_year 2010, (2010-2000)*1=10 + no missing fields = 10
    assert beta["enrichment_score"] == 10
    assert beta["batch_year"] == 2010

    # Sorted descending by enrichment_score
    assert priorities.iloc[0]["slug"] == "acme"
    assert priorities.iloc[1]["slug"] == "beta"

    assert "yc_url" in priorities.columns
    assert priorities[priorities["slug"] == "acme"]["yc_url"].iloc[0] == (
        "https://www.ycombinator.com/companies/acme"
    )


def test_validate_imputation_passes_on_valid_input():
    companies_df = pd.DataFrame(
        {"id": [1], "oneLiner": ["Existing"], "founder_count": [2]}
    )

    validate_imputation(companies_df, companies_df.copy())  # should not raise


def test_validate_imputation_raises_on_row_count_change():
    original_df = pd.DataFrame(
        {"id": [1, 2], "oneLiner": [None, None], "founder_count": [0, 0]}
    )
    imputed_df = pd.DataFrame({"id": [1], "oneLiner": [None], "founder_count": [0]})

    with pytest.raises(AssertionError, match="Row count"):
        validate_imputation(original_df, imputed_df)


def test_validate_imputation_raises_on_overwritten_oneliner():
    original_df = pd.DataFrame(
        {"id": [1], "oneLiner": ["Existing"], "founder_count": [0]}
    )
    imputed_df = pd.DataFrame(
        {"id": [1], "oneLiner": ["Changed!"], "founder_count": [0]}
    )

    with pytest.raises(AssertionError, match="oneLiners were modified"):
        validate_imputation(original_df, imputed_df)


def test_validate_imputation_raises_on_negative_founder_count():
    original_df = pd.DataFrame(
        {"id": [1], "oneLiner": [None], "founder_count": [0]}
    )
    imputed_df = pd.DataFrame(
        {"id": [1], "oneLiner": [None], "founder_count": [-1]}
    )

    with pytest.raises(AssertionError, match="Negative founder counts"):
        validate_imputation(original_df, imputed_df)


def test_run_imputation_pipeline_respects_input_and_output_dir(tmp_path):
    input_dir = tmp_path / "step1_cleaned"
    output_dir = tmp_path / "step2_imputed"
    input_dir.mkdir()

    pd.DataFrame(
        {
            "id": [1, 2],
            "slug": ["acme", "beta"],
            "name": ["Acme", "Beta"],
            "status": ["Active", "Active"],
            "batch": ["W24", "S23"],
            "teamSize": [5, 3],
            "oneLiner": [None, "Existing"],
            "longDescription": ["Acme builds widgets. More text.", "Beta desc."],
        }
    ).to_csv(input_dir / "companies_cleaned.csv", index=False)
    pd.DataFrame({"company_slug": ["acme"]}).to_csv(
        input_dir / "founders_cleaned.csv", index=False
    )
    for filename in [
        "industries_cleaned.csv",
        "tags_cleaned.csv",
        "schools_cleaned.csv",
        "prior_companies_cleaned.csv",
        "regions_cleaned.csv",
        "badges_cleaned.csv",
    ]:
        pd.DataFrame({"id": [1]}).to_csv(input_dir / filename, index=False)

    run_imputation_pipeline(input_dir=input_dir, output_dir=output_dir)

    assert (output_dir / "companies_imputed.csv").exists()
    assert (output_dir / "imputation_report.csv").exists()
    assert (output_dir / "enrichment_priorities.csv").exists()

    imputed = pd.read_csv(output_dir / "companies_imputed.csv")
    assert len(imputed) == 2
    acme = imputed[imputed["slug"] == "acme"].iloc[0]
    assert acme["oneLiner"] == "Acme builds widgets."
    assert acme["founder_count"] == 1


def test_run_imputation_pipeline_defaults_still_work_with_no_args():
    # Uses the real project-relative input_dir/output_dir defaults — just
    # confirms the function signature still accepts a no-arg call.
    import inspect

    sig = inspect.signature(run_imputation_pipeline)
    assert list(sig.parameters) == ["input_dir", "output_dir"]
    assert sig.parameters["input_dir"].default is None
    assert sig.parameters["output_dir"].default is None
