import pytest
import pandas as pd

from src.etl.score import (
    compute_deep_tech_score,
    compute_description_score,
    compute_founder_background_score,
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


from src.etl.score import (
    compute_geo_ops_score,
    compute_market_type_pts,
    compute_regulated_score,
)


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
