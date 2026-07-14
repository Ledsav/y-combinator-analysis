import pandas as pd
import pytest
import yaml

from src.etl.score import build_score_table, run_scoring_pipeline, validate_scores


def _minimal_rubric():
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
                "combine_params": {
                    "features": {"founder_phd_count": 2, "research_company_experience": 1}
                },
                "method": "linear_capped",
                "params": {"cap": 2, "points": 18},
            },
            {
                "name": "regulated",
                "dimension": "practical",
                "raw_feature": "regulated_industry",
                "method": "linear_capped",
                "params": {"cap": 1, "points": 70},
            },
        ],
    }


def _minimal_score_inputs():
    return pd.DataFrame(
        {
            "id": [1, 2],
            "slug": ["acme", "beta"],
            "name": ["Acme", "Beta"],
            "batch": ["W24", "S23"],
            "status": ["Active", "Active"],
            "deep_tech_tag_count": [3, 0],
            "founder_phd_count": [1, 0],
            "research_company_experience": [2, 0],
            "regulated_industry": [1, 0],
        }
    )


def test_build_score_table_has_one_row_per_company():
    features_df = _minimal_score_inputs()

    scores_df = build_score_table(features_df, _minimal_rubric())

    assert len(scores_df) == 2
    assert set(scores_df["id"]) == {1, 2}


def test_build_score_table_creates_one_column_per_bucket():
    features_df = _minimal_score_inputs()

    scores_df = build_score_table(features_df, _minimal_rubric())

    for col in ["deep_tech_score", "founder_background_score", "regulated_score"]:
        assert col in scores_df.columns


def test_build_score_table_computes_expected_values_for_acme_and_beta():
    features_df = _minimal_score_inputs()

    scores_df = build_score_table(features_df, _minimal_rubric())

    acme = scores_df[scores_df["slug"] == "acme"].iloc[0]
    assert acme["deep_tech_score"] == 12  # raw=3 clipped to cap=2 -> 2/2*12
    assert acme["founder_background_score"] == 18  # raw=2*1+2=4 clipped to cap=2 -> 18
    assert acme["regulated_score"] == 70
    assert acme["technical_score"] == 30  # 12 + 18
    assert acme["practical_score"] == 70
    assert acme["complexity_score"] == 100

    beta = scores_df[scores_df["slug"] == "beta"].iloc[0]
    assert beta["technical_score"] == 0
    assert beta["practical_score"] == 0
    assert beta["complexity_score"] == 0


def test_build_score_table_splits_geo_ops_into_two_independent_buckets():
    """
    Regression guard for the Phase 12 schema change: geo_ops_score no
    longer exists as one combined column -- international_operations and
    operational_intensity are ordinary independent buckets that both roll
    into practical_score.
    """
    features_df = pd.DataFrame(
        {
            "id": [1],
            "slug": ["acme"],
            "name": ["Acme"],
            "batch": ["W24"],
            "status": ["Active"],
            "international_operations": [5],
            "operational_intensity": [5],
        }
    )
    rubric = {
        "version": "test",
        "buckets": [
            {
                "name": "international_operations",
                "dimension": "practical",
                "raw_feature": "international_operations",
                "method": "linear_capped",
                "params": {"cap": 1, "points": 14},
            },
            {
                "name": "operational_intensity",
                "dimension": "practical",
                "raw_feature": "operational_intensity",
                "method": "linear_capped",
                "params": {"cap": 1, "points": 14},
            },
        ],
    }

    scores_df = build_score_table(features_df, rubric)

    assert "geo_ops_score" not in scores_df.columns
    assert scores_df.loc[0, "international_operations_score"] == 14
    assert scores_df.loc[0, "operational_intensity_score"] == 14
    assert scores_df.loc[0, "practical_score"] == 28


def test_validate_scores_passes_on_valid_table():
    features_df = _minimal_score_inputs()
    rubric = _minimal_rubric()
    scores_df = build_score_table(features_df, rubric)

    validate_scores(features_df, scores_df, rubric)  # should not raise


def test_validate_scores_raises_on_row_count_mismatch():
    features_df = pd.DataFrame({"id": [1, 2]})
    scores_df = pd.DataFrame(
        {"id": [1], "technical_score": [10.0], "practical_score": [10.0], "complexity_score": [20.0]}
    )

    with pytest.raises(AssertionError, match="Row count"):
        validate_scores(features_df, scores_df, _minimal_rubric())


def test_validate_scores_raises_on_id_set_mismatch():
    features_df = pd.DataFrame({"id": [1, 2]})
    scores_df = pd.DataFrame(
        {
            "id": [1, 3],
            "technical_score": [10.0, 10.0],
            "practical_score": [10.0, 10.0],
            "complexity_score": [20.0, 20.0],
        }
    )

    with pytest.raises(AssertionError, match="id set"):
        validate_scores(features_df, scores_df, _minimal_rubric())


def test_validate_scores_raises_on_missing_values():
    features_df = pd.DataFrame({"id": [1, 2]})
    scores_df = pd.DataFrame(
        {
            "id": [1, 2],
            "technical_score": [10.0, None],
            "practical_score": [10.0, 10.0],
            "complexity_score": [20.0, None],
        }
    )

    with pytest.raises(AssertionError, match="Missing values"):
        validate_scores(features_df, scores_df, _minimal_rubric())


def test_validate_scores_raises_on_out_of_range_technical_score():
    features_df = pd.DataFrame({"id": [1]})
    scores_df = pd.DataFrame(
        {"id": [1], "technical_score": [60.0], "practical_score": [10.0], "complexity_score": [70.0]}
    )

    # _minimal_rubric's technical budget = 12 + 18 = 30
    with pytest.raises(AssertionError, match="technical_score"):
        validate_scores(features_df, scores_df, _minimal_rubric())


def test_validate_scores_raises_on_out_of_range_practical_score():
    features_df = pd.DataFrame({"id": [1]})
    scores_df = pd.DataFrame(
        {"id": [1], "technical_score": [10.0], "practical_score": [75.0], "complexity_score": [85.0]}
    )

    # _minimal_rubric's practical budget = 70
    with pytest.raises(AssertionError, match="practical_score"):
        validate_scores(features_df, scores_df, _minimal_rubric())


def test_validate_scores_raises_on_out_of_range_complexity_score():
    features_df = pd.DataFrame({"id": [1]})
    scores_df = pd.DataFrame(
        {"id": [1], "technical_score": [25.0], "practical_score": [45.0], "complexity_score": [110.0]}
    )

    # _minimal_rubric's total budget = 30 + 70 = 100
    with pytest.raises(AssertionError, match="complexity_score"):
        validate_scores(features_df, scores_df, _minimal_rubric())


def test_run_scoring_pipeline_end_to_end(tmp_path):
    input_path = tmp_path / "complexity_features.parquet"
    output_path = tmp_path / "scores" / "complexity_index_test.csv"
    rubric_config_path = tmp_path / "rubric.yaml"

    features_df = _minimal_score_inputs()
    features_df.to_parquet(input_path, index=False)
    rubric_config_path.write_text(yaml.dump(_minimal_rubric()), encoding="utf-8")

    run_scoring_pipeline(
        input_path=input_path, output_path=output_path, rubric_config_path=rubric_config_path
    )

    scores_df = pd.read_csv(output_path)
    assert len(scores_df) == 2
    acme = scores_df[scores_df["slug"] == "acme"].iloc[0]
    assert acme["complexity_score"] == 100
    beta = scores_df[scores_df["slug"] == "beta"].iloc[0]
    assert beta["complexity_score"] == 0
