import json
import math

import pandas as pd
import pytest

from scripts.export_site_data import build_company_records


def test_build_company_records_produces_json_safe_records_with_industries_list():
    scores_df = pd.DataFrame(
        {
            "id": [1, 2],
            "slug": ["acme", "beta"],
            "name": ["Acme", "Beta"],
            "batch": ["W24", "S23"],
            "status": ["Active", "Active"],
            "technical_score": [10.0, 20.0],
            "practical_score": [5.0, 15.0],
            "complexity_score": [15.0, 35.0],
        }
    )
    company_industries_df = pd.DataFrame(
        {
            "id": [1, 2],
            "industries": ["Fintech", ""],
            "industries_list": [["Fintech"], []],
        }
    )
    team_sizes_df = pd.DataFrame({"id": [1, 2], "teamSize": [5.0, float("nan")]})

    records = build_company_records(scores_df, company_industries_df, team_sizes_df)

    assert len(records) == 2
    acme = next(r for r in records if r["slug"] == "acme")
    assert acme["industries_list"] == ["Fintech"]
    assert acme["teamSize"] == 5.0
    beta = next(r for r in records if r["slug"] == "beta")
    assert beta["teamSize"] is None
    assert "NaN" not in json.dumps(records)
