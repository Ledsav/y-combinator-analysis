"""
Generates output/complexity_dashboard_v1.html — a self-contained, offline
HTML dashboard for exploring data/processed/scores/complexity_index_v1.csv,
per docs/superpowers/specs/2026-07-14-phase10-visualization-dashboard-design.md.

Run: ./.venv/Scripts/python.exe scripts/generate_dashboard.py

This phase only visualizes the already-computed index; it does not
recompute or re-validate any scores.
"""

from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SCORES_PATH = REPO_ROOT / "data" / "processed" / "scores" / "complexity_index_v1.csv"
FEATURES_PATH = REPO_ROOT / "data" / "processed" / "features" / "complexity_features.parquet"
INDUSTRIES_PATH = REPO_ROOT / "data" / "processed" / "step3_enriched" / "industries_enriched.csv"
COMPANIES_PATH = REPO_ROOT / "data" / "processed" / "step3_enriched" / "companies_enriched.csv"
OUTPUT_PATH = REPO_ROOT / "output" / "complexity_dashboard_v1.html"


def load_dashboard_data(
    scores_path: Path, features_path: Path, industries_path: Path, companies_path: Path
) -> Dict[str, pd.DataFrame]:
    """Read the 4 data sources the dashboard needs."""
    return {
        "scores": pd.read_csv(scores_path),
        "features": pd.read_parquet(features_path),
        "industries": pd.read_csv(industries_path),
        "companies": pd.read_csv(companies_path),
    }


def aggregate_company_industries(
    scores_df: pd.DataFrame, industries_df: pd.DataFrame
) -> pd.DataFrame:
    """
    One row per company id (from scores_df, so companies with zero industry
    tags are still present), with a comma-joined `industries` string column
    ("" if the company has no industry tags).
    """
    grouped = (
        industries_df.groupby("id")["industry"]
        .apply(lambda s: ", ".join(s))
        .reset_index()
        .rename(columns={"industry": "industries"})
    )
    result = scores_df[["id"]].merge(grouped, on="id", how="left")
    result["industries"] = result["industries"].fillna("")
    return result


def explode_industries(scores_df: pd.DataFrame, industries_df: pd.DataFrame) -> pd.DataFrame:
    """One row per company-industry tag pair (a company with N tags appears N times)."""
    return scores_df.merge(industries_df, on="id", how="left")


def batch_sort_key(batch: str) -> Tuple[int, int]:
    """Chronological sort key: Winter before Summer within the same year."""
    year = int(batch[1:])
    season_order = 0 if batch[0] == "W" else 1
    return (year, season_order)
