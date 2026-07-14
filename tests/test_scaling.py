import pandas as pd
import pytest

from src.etl.scaling import SCALING_METHODS, linear_capped


def test_linear_capped_scales_linearly_up_to_cap():
    raw = pd.Series([0, 1, 3, 5])

    result = linear_capped(raw, cap=3, points=20)

    assert result[0] == 0
    assert result[1] == pytest.approx(20 / 3)
    assert result[2] == 20
    assert result[3] == 20  # clipped above cap


def test_linear_capped_registered_under_its_name():
    assert SCALING_METHODS["linear_capped"] is linear_capped
