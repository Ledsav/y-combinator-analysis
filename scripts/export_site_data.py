"""
Phase 13: exports the already-computed complexity index into the small,
pre-aggregated JSON files site/index.html, site/dashboard.html, and
site/pipeline.html fetch at runtime. Performs no scoring or recomputation
-- pure read-and-reshape, following the same NaN-to-null pattern as
scripts/generate_dashboard.py's build_company_records.

Run: ./.venv/Scripts/python.exe scripts/export_site_data.py
"""

import datetime
import json
import math
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from scripts.generate_dashboard import aggregate_company_industries, batch_sort_key
from src.etl.rubric import load_rubric

REPO_ROOT = Path(__file__).resolve().parents[1]
SCORES_PATH = REPO_ROOT / "data" / "processed" / "scores" / "complexity_index_v2.csv"
INDUSTRIES_PATH = REPO_ROOT / "data" / "processed" / "step3_enriched" / "industries_enriched.csv"
COMPANIES_PATH = REPO_ROOT / "data" / "processed" / "step3_enriched" / "companies_enriched.csv"
RUBRIC_PATH = REPO_ROOT / "config" / "rubric_v2.yaml"
SITE_DATA_DIR = REPO_ROOT / "site" / "data"

INDUSTRY_MIN_COUNT = 20


def _clean_json(value: Any) -> Any:
    """Replace float NaN with None -- json.dumps' bare NaN token is not
    valid JSON and a browser's JSON.parse rejects it."""
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def build_company_records(
    scores_df: pd.DataFrame, company_industries_df: pd.DataFrame, team_sizes_df: pd.DataFrame
) -> List[dict]:
    """One dict per company: id, slug, name, batch, status, industries_list,
    teamSize, technical_score, practical_score, complexity_score. JSON-safe."""
    merged = scores_df.merge(company_industries_df, on="id", how="left")
    merged = merged.merge(team_sizes_df[["id", "teamSize"]], on="id", how="left")
    columns = [
        "id",
        "slug",
        "name",
        "batch",
        "status",
        "industries_list",
        "teamSize",
        "technical_score",
        "practical_score",
        "complexity_score",
    ]
    records = merged[columns].to_dict(orient="records")
    for record in records:
        for key, value in record.items():
            record[key] = _clean_json(value)
    return records
