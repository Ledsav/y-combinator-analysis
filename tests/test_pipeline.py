import pandas as pd
import pytest

from src.etl.pipeline import DEFAULT_STEPS, STEP_ORDER, normalize_steps
from src.etl.pipeline import _default_paths, check_step_prerequisite


def test_normalize_steps_none_returns_default_steps():
    assert normalize_steps(None) == DEFAULT_STEPS


def test_normalize_steps_all_returns_default_steps_excluding_enrich():
    result = normalize_steps(["all"])
    assert result == DEFAULT_STEPS
    assert "enrich" not in result


def test_normalize_steps_deduplicates_and_orders_canonically():
    assert normalize_steps(["score", "clean", "score"]) == ["clean", "score"]


def test_normalize_steps_includes_enrich_when_explicitly_requested():
    result = normalize_steps(["clean", "enrich", "impute"])
    assert result == ["clean", "impute", "enrich"]


def test_normalize_steps_rejects_unknown_step_name():
    with pytest.raises(ValueError, match="scrape"):
        normalize_steps(["clean", "scrape"])


def test_default_paths_computes_expected_required_inputs(tmp_path):
    paths = _default_paths(tmp_path, output_version="v1")

    assert paths["clean"]["required_input"] == tmp_path / "raw" / "companies.csv"
    assert (
        paths["impute"]["required_input"]
        == tmp_path / "processed" / "step1_cleaned" / "companies_cleaned.csv"
    )
    assert (
        paths["enrich"]["required_input"]
        == tmp_path / "processed" / "step2_imputed" / "companies_imputed.csv"
    )
    assert (
        paths["features"]["required_input"]
        == tmp_path / "processed" / "step3_enriched" / "companies_enriched.csv"
    )
    assert (
        paths["score"]["required_input"]
        == tmp_path / "processed" / "features" / "complexity_features.parquet"
    )
    assert (
        paths["score"]["kwargs"]["output_path"]
        == tmp_path / "processed" / "scores" / "complexity_index_v1.csv"
    )
    rubric_path = paths["score"]["kwargs"]["rubric_config_path"]
    assert rubric_path.name == "rubric_v1.yaml"
    assert rubric_path.parent.name == "config"


def test_default_paths_respects_output_version(tmp_path):
    paths = _default_paths(tmp_path, output_version="v2")
    assert paths["score"]["kwargs"]["output_path"].name == "complexity_index_v2.csv"


def test_default_paths_kwargs_use_each_steps_own_param_names(tmp_path):
    paths = _default_paths(tmp_path, output_version="v1")

    assert set(paths["clean"]["kwargs"]) == {"input_dir", "output_dir"}
    assert set(paths["impute"]["kwargs"]) == {"input_dir", "output_dir"}
    assert set(paths["enrich"]["kwargs"]) == {"input_dir", "output_dir"}
    assert set(paths["features"]["kwargs"]) == {"input_dir", "output_dir"}
    assert set(paths["score"]["kwargs"]) == {"input_path", "output_path", "rubric_config_path"}


def test_check_step_prerequisite_passes_when_input_exists(tmp_path):
    required = tmp_path / "companies_cleaned.csv"
    required.write_text("id\n1\n")

    check_step_prerequisite("impute", required)  # should not raise


def test_check_step_prerequisite_raises_with_producer_hint(tmp_path):
    required = tmp_path / "missing.parquet"

    with pytest.raises(FileNotFoundError, match="run 'features' first"):
        check_step_prerequisite("score", required)


def test_check_step_prerequisite_raises_without_producer_hint_for_clean(tmp_path):
    required = tmp_path / "companies.csv"

    with pytest.raises(FileNotFoundError, match="ensure raw data is present"):
        check_step_prerequisite("clean", required)


from src.etl import pipeline
from src.etl.pipeline import run_pipeline


def test_run_pipeline_invokes_requested_steps_in_canonical_order(tmp_path, monkeypatch):
    calls = []

    monkeypatch.setattr(
        pipeline, "run_cleaning_pipeline", lambda **kwargs: (calls.append("clean"), (True, "ok"))[1]
    )
    monkeypatch.setattr(
        pipeline, "run_imputation_pipeline", lambda **kwargs: calls.append("impute")
    )
    monkeypatch.setattr(pipeline, "check_step_prerequisite", lambda step, path: None)

    run_pipeline(steps=["impute", "clean"], data_root=tmp_path)

    assert calls == ["clean", "impute"]


def test_run_pipeline_raises_runtime_error_when_clean_step_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "run_cleaning_pipeline", lambda **kwargs: (False, "boom"))
    monkeypatch.setattr(pipeline, "check_step_prerequisite", lambda step, path: None)

    with pytest.raises(RuntimeError, match="boom"):
        run_pipeline(steps=["clean"], data_root=tmp_path)


def test_run_pipeline_raises_file_not_found_when_prerequisite_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="run 'clean' first"):
        run_pipeline(steps=["impute"], data_root=tmp_path)


from src.etl.pipeline import validate_pipeline_output


def test_validate_pipeline_output_passes_on_valid_csv_reference(tmp_path):
    reference_path = tmp_path / "companies_cleaned.csv"
    output_path = tmp_path / "complexity_index_v1.csv"
    pd.DataFrame({"id": [1, 2]}).to_csv(reference_path, index=False)
    pd.DataFrame({"id": [1, 2], "complexity_score": [10.0, 90.0]}).to_csv(
        output_path, index=False
    )

    validate_pipeline_output(output_path, reference_path)  # should not raise


def test_validate_pipeline_output_passes_on_valid_parquet_reference(tmp_path):
    reference_path = tmp_path / "complexity_features.parquet"
    output_path = tmp_path / "complexity_index_v1.csv"
    pd.DataFrame({"id": [1, 2]}).to_parquet(reference_path, index=False)
    pd.DataFrame({"id": [1, 2], "complexity_score": [10.0, 90.0]}).to_csv(
        output_path, index=False
    )

    validate_pipeline_output(output_path, reference_path)  # should not raise


def test_validate_pipeline_output_raises_on_row_count_mismatch(tmp_path):
    reference_path = tmp_path / "companies_cleaned.csv"
    output_path = tmp_path / "complexity_index_v1.csv"
    pd.DataFrame({"id": [1, 2, 3]}).to_csv(reference_path, index=False)
    pd.DataFrame({"id": [1, 2], "complexity_score": [10.0, 90.0]}).to_csv(
        output_path, index=False
    )

    with pytest.raises(AssertionError, match="Row count mismatch"):
        validate_pipeline_output(output_path, reference_path)


def test_validate_pipeline_output_raises_on_out_of_range_score(tmp_path):
    reference_path = tmp_path / "companies_cleaned.csv"
    output_path = tmp_path / "complexity_index_v1.csv"
    pd.DataFrame({"id": [1]}).to_csv(reference_path, index=False)
    pd.DataFrame({"id": [1], "complexity_score": [150.0]}).to_csv(
        output_path, index=False
    )

    with pytest.raises(AssertionError, match="complexity_score"):
        validate_pipeline_output(output_path, reference_path)


def test_run_pipeline_end_to_end_features_and_score(tmp_path):
    data_root = tmp_path / "data"
    raw_dir = data_root / "raw"
    step3_dir = data_root / "processed" / "step3_enriched"
    raw_dir.mkdir(parents=True)
    step3_dir.mkdir(parents=True)

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
    regions = pd.DataFrame(
        {"id": [1, 2], "country": ["United States of America", "India"]}
    )
    founders = pd.DataFrame({"hnid": ["a"], "company_slug": ["acme"]})
    schools = pd.DataFrame({"hnid": ["a"], "field_of_study": ["Doctor Of Philosophy"]})
    prior_companies = pd.DataFrame({"hnid": [], "company": []})

    companies.to_csv(step3_dir / "companies_enriched.csv", index=False)
    tags.to_csv(step3_dir / "tags_enriched.csv", index=False)
    industries.to_csv(step3_dir / "industries_enriched.csv", index=False)
    regions.to_csv(step3_dir / "regions_enriched.csv", index=False)
    founders.to_csv(step3_dir / "founders_enriched.csv", index=False)
    schools.to_csv(step3_dir / "schools_enriched.csv", index=False)
    prior_companies.to_csv(step3_dir / "prior_companies_enriched.csv", index=False)

    rubric_config_path = tmp_path / "rubric.yaml"
    rubric_config_path.write_text(
        """
version: test
buckets:
  - name: deep_tech
    dimension: technical
    raw_feature: deep_tech_tag_count
    method: linear_capped
    params: {cap: 2, points: 30}
  - name: regulated
    dimension: practical
    raw_feature: regulated_industry
    method: linear_capped
    params: {cap: 1, points: 70}
""",
        encoding="utf-8",
    )

    run_pipeline(
        steps=["features", "score"],
        output_version="v9",
        data_root=data_root,
        rubric_config_path=rubric_config_path,
    )

    output_path = data_root / "processed" / "scores" / "complexity_index_v9.csv"
    assert output_path.exists()
    scores_df = pd.read_csv(output_path)
    assert len(scores_df) == 2
    acme = scores_df[scores_df["slug"] == "acme"].iloc[0]
    assert acme["complexity_score"] > 0
