import pytest
import pandas as pd

from src.etl.score import (
    build_score_table,
    compute_deep_tech_score,
    compute_description_score,
    compute_founder_background_score,
    compute_geo_ops_score,
    compute_market_type_pts,
    compute_regulated_score,
    run_scoring_pipeline,
    validate_scores,
)


def test_compute_deep_tech_score_scales_linearly_up_to_cap():
    features_df = pd.DataFrame({"id": [1, 2, 3, 4], "deep_tech_tag_count": [0, 1, 3, 5]})

    result = compute_deep_tech_score(features_df, cap=3, points=20)

    scores = dict(zip(result["id"], result["deep_tech_score"]))
    assert scores[1] == 0
    assert scores[2] == pytest.approx(20 / 3)
    assert scores[3] == 20
    assert scores[4] == 20  # clipped above cap


def test_compute_deep_tech_score_returns_one_row_per_company():
    features_df = pd.DataFrame({"id": [1, 2], "deep_tech_tag_count": [0, 0]})

    result = compute_deep_tech_score(features_df)

    assert len(result) == 2
    assert set(result["id"]) == {1, 2}


def test_compute_description_score_scales_linearly_up_to_cap():
    features_df = pd.DataFrame({"id": [1, 2, 3], "description_tech_score": [0, 3, 10]})

    result = compute_description_score(features_df, cap=3, points=15)

    scores = dict(zip(result["id"], result["description_score"]))
    assert scores[1] == 0
    assert scores[2] == 15
    assert scores[3] == 15  # clipped above cap


def test_compute_founder_background_score_weights_phd_and_research():
    features_df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "founder_phd_count": [0, 1, 0],
            "research_company_experience": [0, 0, 4],
        }
    )

    result = compute_founder_background_score(features_df, phd_weight=2, cap=4, points=15)

    scores = dict(zip(result["id"], result["founder_background_score"]))
    assert scores[1] == 0
    assert scores[2] == pytest.approx(7.5)  # raw = 2*1 = 2 -> 2/4*15
    assert scores[3] == 15  # raw = 4, at cap


def test_compute_regulated_score_multiplies_binary_flag():
    features_df = pd.DataFrame({"id": [1, 2], "regulated_industry": [0, 1]})

    result = compute_regulated_score(features_df, points=15)

    scores = dict(zip(result["id"], result["regulated_score"]))
    assert scores == {1: 0, 2: 15}


def test_compute_market_type_pts_scales_ordinal():
    features_df = pd.DataFrame({"id": [1, 2, 3, 4], "market_type_score": [0, 1, 2, 3]})

    result = compute_market_type_pts(features_df, points_per_level=5)

    scores = dict(zip(result["id"], result["market_type_pts"]))
    assert scores == {1: 0, 2: 5, 3: 10, 4: 15}


def test_compute_geo_ops_score_sums_independently_capped_sub_scores():
    features_df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "international_operations": [0, 1, 5],
            "operational_intensity": [0, 2, 0],
        }
    )

    result = compute_geo_ops_score(
        features_df, intl_cap=2, ops_cap=2, intl_points=10, ops_points=10
    )

    scores = dict(zip(result["id"], result["geo_ops_score"]))
    assert scores[1] == 0
    assert scores[2] == 15  # intl: 1/2*10=5, ops: 2/2*10=10
    assert scores[3] == 10  # intl clipped: 2/2*10=10, ops: 0


def _minimal_score_inputs():
    return pd.DataFrame(
        {
            "id": [1, 2],
            "slug": ["acme", "beta"],
            "name": ["Acme", "Beta"],
            "batch": ["W24", "S23"],
            "status": ["Active", "Active"],
            "deep_tech_tag_count": [3, 0],
            "description_tech_score": [3, 0],
            "founder_phd_count": [1, 0],
            "research_company_experience": [2, 0],
            "regulated_industry": [1, 0],
            "market_type_score": [3, 0],
            "international_operations": [2, 0],
            "operational_intensity": [2, 0],
        }
    )


def test_build_score_table_has_one_row_per_company():
    features_df = _minimal_score_inputs()

    scores_df = build_score_table(features_df)

    assert len(scores_df) == 2
    assert set(scores_df["id"]) == {1, 2}


def test_build_score_table_computes_expected_values_for_acme_and_beta():
    features_df = _minimal_score_inputs()

    scores_df = build_score_table(features_df)

    acme = scores_df[scores_df["slug"] == "acme"].iloc[0]
    assert acme["technical_score"] == 50  # 20 + 15 + 15 (all buckets at cap)
    assert acme["practical_score"] == 50  # 15 + 15 + 20 (all buckets at cap)
    assert acme["complexity_score"] == 100

    beta = scores_df[scores_df["slug"] == "beta"].iloc[0]
    assert beta["technical_score"] == 0
    assert beta["practical_score"] == 0
    assert beta["complexity_score"] == 0


def test_validate_scores_passes_on_valid_table():
    features_df = _minimal_score_inputs()
    scores_df = build_score_table(features_df)

    validate_scores(features_df, scores_df)  # should not raise


def test_validate_scores_raises_on_row_count_mismatch():
    features_df = pd.DataFrame({"id": [1, 2]})
    scores_df = pd.DataFrame(
        {"id": [1], "technical_score": [10.0], "practical_score": [10.0], "complexity_score": [20.0]}
    )

    with pytest.raises(AssertionError, match="Row count"):
        validate_scores(features_df, scores_df)


def test_validate_scores_raises_on_out_of_range_score():
    features_df = pd.DataFrame({"id": [1]})
    scores_df = pd.DataFrame(
        {"id": [1], "technical_score": [60.0], "practical_score": [10.0], "complexity_score": [70.0]}
    )

    with pytest.raises(AssertionError, match="technical_score"):
        validate_scores(features_df, scores_df)


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
        validate_scores(features_df, scores_df)


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
        validate_scores(features_df, scores_df)


def test_validate_scores_raises_on_out_of_range_practical_score():
    features_df = pd.DataFrame({"id": [1]})
    scores_df = pd.DataFrame(
        {"id": [1], "technical_score": [10.0], "practical_score": [55.0], "complexity_score": [65.0]}
    )

    with pytest.raises(AssertionError, match="practical_score"):
        validate_scores(features_df, scores_df)


def test_validate_scores_raises_on_out_of_range_complexity_score():
    features_df = pd.DataFrame({"id": [1]})
    scores_df = pd.DataFrame(
        {"id": [1], "technical_score": [45.0], "practical_score": [45.0], "complexity_score": [110.0]}
    )

    with pytest.raises(AssertionError, match="complexity_score"):
        validate_scores(features_df, scores_df)


def test_run_scoring_pipeline_end_to_end(tmp_path):
    input_path = tmp_path / "complexity_features.parquet"
    output_path = tmp_path / "scores" / "complexity_index_v1.csv"

    features_df = _minimal_score_inputs()
    features_df.to_parquet(input_path, index=False)

    run_scoring_pipeline(input_path=input_path, output_path=output_path)

    scores_df = pd.read_csv(output_path)
    assert len(scores_df) == 2
    acme = scores_df[scores_df["slug"] == "acme"].iloc[0]
    assert acme["complexity_score"] == 100
    beta = scores_df[scores_df["slug"] == "beta"].iloc[0]
    assert beta["complexity_score"] == 0
