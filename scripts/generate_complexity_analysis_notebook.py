"""
Generates notebooks/complexity_analysis.ipynb for Phase 9 validation & analysis.

Run: ./.venv/Scripts/python.exe scripts/generate_complexity_analysis_notebook.py

Regenerate this way (not by hand-editing the .ipynb) whenever a cell needs
to change, so the notebook stays reproducible from source.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "notebooks" / "complexity_analysis.ipynb"


def markdown_cell(text: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": text.splitlines(keepends=True),
    }


def code_cell(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text.splitlines(keepends=True),
    }


CELLS = [
    markdown_cell(
        "# Phase 9 Validation & Analysis\n"
        "\n"
        "Authoritative validation notebook for `data/processed/scores/complexity_index_v1.csv` "
        "(self-contained — re-derives team-size correlation and manual outlier review fresh "
        "rather than citing `notebooks/score_design.ipynb`). Covers score distribution, "
        "technical-vs-practical relationship, complexity by batch/status/industry, a full "
        "correlation heatmap, team-size correlation, targeted validation questions, manual "
        "outlier review, and findings, per "
        "`docs/superpowers/specs/2026-07-13-phase9-validation-analysis-design.md`."
    ),
    code_cell(
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "import numpy as np\n"
        "import pandas as pd\n"
        "\n"
        "REPO_ROOT = Path.cwd().parent if Path.cwd().name == \"notebooks\" else Path.cwd()\n"
        "sys.path.insert(0, str(REPO_ROOT))\n"
        "\n"
        "scores_df = pd.read_csv(REPO_ROOT / \"data\" / \"processed\" / \"scores\" / \"complexity_index_v1.csv\")\n"
        "features_df = pd.read_parquet(REPO_ROOT / \"data\" / \"processed\" / \"features\" / \"complexity_features.parquet\")\n"
        "companies_df = pd.read_csv(REPO_ROOT / \"data\" / \"processed\" / \"step3_enriched\" / \"companies_enriched.csv\")\n"
        "industries_df = pd.read_csv(REPO_ROOT / \"data\" / \"processed\" / \"step3_enriched\" / \"industries_enriched.csv\")\n"
        "\n"
        "merged = scores_df.merge(companies_df[[\"id\", \"teamSize\"]], on=\"id\", how=\"left\")\n"
        "merged[\"log_team_size\"] = np.log1p(merged[\"teamSize\"])\n"
        "\n"
        "feature_cols = [c for c in features_df.columns if c not in (\"id\", \"slug\", \"name\", \"batch\", \"status\")]\n"
        "merged = merged.merge(features_df[[\"id\"] + feature_cols], on=\"id\", how=\"left\")\n"
        "\n"
        "industry_merged = scores_df.merge(industries_df, on=\"id\", how=\"left\")\n"
        "\n"
        "merged.shape, industry_merged.shape"
    ),
]


def build_notebook() -> dict:
    return {
        "cells": CELLS,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(build_notebook(), f, indent=1)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
