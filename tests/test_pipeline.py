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


def test_default_paths_respects_output_version(tmp_path):
    paths = _default_paths(tmp_path, output_version="v2")
    assert paths["score"]["kwargs"]["output_path"].name == "complexity_index_v2.csv"


def test_default_paths_kwargs_use_each_steps_own_param_names(tmp_path):
    paths = _default_paths(tmp_path, output_version="v1")

    assert set(paths["clean"]["kwargs"]) == {"input_dir", "output_dir"}
    assert set(paths["impute"]["kwargs"]) == {"input_dir", "output_dir"}
    assert set(paths["enrich"]["kwargs"]) == {"input_dir", "output_dir"}
    assert set(paths["features"]["kwargs"]) == {"input_dir", "output_dir"}
    assert set(paths["score"]["kwargs"]) == {"input_path", "output_path"}


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
