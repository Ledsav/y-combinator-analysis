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


def build_distribution_bins(scores_df: pd.DataFrame, bin_count: int = 30) -> List[dict]:
    """Histogram bins over complexity_score: [{start, end, count}, ...]."""
    binned = pd.cut(scores_df["complexity_score"], bins=bin_count, include_lowest=True)
    bin_counts = binned.value_counts(sort=False)
    return [
        {"start": round(interval.left, 2), "end": round(interval.right, 2), "count": int(count)}
        for interval, count in bin_counts.items()
    ]


def build_mean_by_batch(scores_df: pd.DataFrame) -> List[dict]:
    """Chronologically ordered [{batch, mean_complexity}, ...]."""
    summary = scores_df.groupby("batch")["complexity_score"].mean().reset_index()
    summary["sort_key"] = summary["batch"].apply(batch_sort_key)
    summary = summary.sort_values("sort_key").drop(columns="sort_key")
    return [
        {"batch": row.batch, "mean_complexity": round(row.complexity_score, 2)}
        for row in summary.itertuples()
    ]


def build_mean_by_status(scores_df: pd.DataFrame) -> List[dict]:
    """Descending [{status, mean_complexity}, ...]."""
    summary = (
        scores_df.groupby("status")["complexity_score"]
        .mean()
        .sort_values(ascending=False)
        .reset_index()
    )
    return [
        {"status": row.status, "mean_complexity": round(row.complexity_score, 2)}
        for row in summary.itertuples()
    ]


def build_industry_ranking(
    industry_exploded_df: pd.DataFrame, min_count: int = INDUSTRY_MIN_COUNT, top_n: int = 5
) -> Dict[str, List[dict]]:
    """Top-N and bottom-N industries by mean complexity_score, among those
    with >= min_count companies. {"top": [...], "bottom": [...]}."""
    summary = (
        industry_exploded_df.groupby("industry")["complexity_score"]
        .agg(["mean", "count"])
        .query("count >= @min_count")
        .sort_values("mean", ascending=False)
        .reset_index()
    )
    records = [
        {"industry": row.industry, "mean_complexity": round(row.mean, 2), "count": int(row.count)}
        for row in summary.itertuples()
    ]
    bottom = list(reversed(records[-top_n:])) if records else []
    return {"top": records[:top_n], "bottom": bottom}


def build_correlation_matrix(scores_df: pd.DataFrame) -> Dict[str, Any]:
    """Trimmed correlation matrix: bucket-score columns (any column ending
    in _score other than the 3 totals) followed by the 3 totals.
    {"columns": [...], "values": [[...], ...]}."""
    totals = ["technical_score", "practical_score", "complexity_score"]
    score_cols = [c for c in scores_df.columns if c.endswith("_score")]
    bucket_cols = [c for c in score_cols if c not in totals]
    ordered_cols = bucket_cols + totals
    corr = scores_df[ordered_cols].corr().round(3)
    return {"columns": ordered_cols, "values": corr.values.tolist()}
