import pandas as pd

from src.etl.combine import COMBINE_METHODS, identity, weighted_sum


def test_identity_passes_through_single_column():
    features_df = pd.DataFrame({"x": [1, 2, 3]})

    result = identity(features_df, raw_feature="x")

    assert list(result) == [1, 2, 3]


def test_weighted_sum_combines_columns_with_weights():
    features_df = pd.DataFrame({"phd": [0, 1, 0], "research": [0, 0, 4]})

    result = weighted_sum(features_df, features={"phd": 2, "research": 1})

    assert list(result) == [0, 2, 4]


def test_combine_methods_registered_under_their_names():
    assert COMBINE_METHODS["identity"] is identity
    assert COMBINE_METHODS["weighted_sum"] is weighted_sum
