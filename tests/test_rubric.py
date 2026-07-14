import pytest
import yaml

from src.etl.rubric import load_rubric, validate_rubric


def _valid_rubric():
    return {
        "version": "test",
        "buckets": [
            {
                "name": "deep_tech",
                "dimension": "technical",
                "raw_feature": "deep_tech_tag_count",
                "method": "linear_capped",
                "params": {"cap": 2, "points": 12},
            },
            {
                "name": "founder_background",
                "dimension": "technical",
                "combine": "weighted_sum",
                "combine_params": {"features": {"phd": 2, "research": 1}},
                "method": "linear_capped",
                "params": {"cap": 2, "points": 9},
            },
        ],
    }


def test_validate_rubric_accepts_valid_rubric():
    validate_rubric(_valid_rubric())  # should not raise


def test_validate_rubric_rejects_missing_buckets_key():
    with pytest.raises(ValueError, match="buckets"):
        validate_rubric({})


def test_validate_rubric_rejects_duplicate_bucket_names():
    rubric = _valid_rubric()
    rubric["buckets"][1]["name"] = "deep_tech"

    with pytest.raises(ValueError, match="Duplicate bucket name"):
        validate_rubric(rubric)


def test_validate_rubric_rejects_bucket_with_both_raw_feature_and_combine():
    rubric = _valid_rubric()
    rubric["buckets"][0]["combine"] = "weighted_sum"
    rubric["buckets"][0]["combine_params"] = {"features": {"x": 1}}

    with pytest.raises(ValueError, match="exactly one of"):
        validate_rubric(rubric)


def test_validate_rubric_rejects_bucket_with_neither_raw_feature_nor_combine():
    rubric = _valid_rubric()
    del rubric["buckets"][0]["raw_feature"]

    with pytest.raises(ValueError, match="exactly one of"):
        validate_rubric(rubric)


def test_validate_rubric_rejects_unknown_scaling_method():
    rubric = _valid_rubric()
    rubric["buckets"][0]["method"] = "logistic"

    with pytest.raises(ValueError, match="unknown scaling method"):
        validate_rubric(rubric)


def test_validate_rubric_rejects_unknown_combine_method():
    rubric = _valid_rubric()
    rubric["buckets"][1]["combine"] = "nonexistent"

    with pytest.raises(ValueError, match="unknown combine method"):
        validate_rubric(rubric)


def test_validate_rubric_rejects_params_missing_points():
    rubric = _valid_rubric()
    del rubric["buckets"][0]["params"]["points"]

    with pytest.raises(ValueError, match="points"):
        validate_rubric(rubric)


def test_load_rubric_reads_and_validates_yaml_file(tmp_path):
    rubric_path = tmp_path / "rubric.yaml"
    rubric_path.write_text(yaml.dump(_valid_rubric()), encoding="utf-8")

    rubric = load_rubric(rubric_path)

    assert rubric["version"] == "test"
    assert len(rubric["buckets"]) == 2


def test_load_rubric_raises_on_invalid_yaml_content(tmp_path):
    rubric_path = tmp_path / "bad.yaml"
    rubric_path.write_text("buckets: []", encoding="utf-8")

    with pytest.raises(ValueError, match="buckets"):
        load_rubric(rubric_path)
