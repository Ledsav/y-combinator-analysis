import pytest

from src.etl.pipeline import DEFAULT_STEPS, STEP_ORDER, normalize_steps


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
