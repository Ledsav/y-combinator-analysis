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
    markdown_cell(
        "## 1. Score Distribution\n"
        "\n"
        "Objectives doc target: standard deviation ≥ 15 points (avoid clustering)."
    ),
    code_cell(
        "merged[[\"complexity_score\", \"technical_score\", \"practical_score\"]].hist(bins=30, figsize=(12, 4), layout=(1, 3))"
    ),
    code_cell(
        "std = merged[\"complexity_score\"].std()\n"
        "print(f\"complexity_score std: {std:.2f} (target: >= 15)\")\n"
        "merged[\"complexity_score\"].describe()"
    ),
    markdown_cell(
        "## 2. Technical vs Practical\n"
        "\n"
        "Checks whether the two 0-50 sub-scores move together or measure "
        "independent dimensions of complexity, as the rubric intends."
    ),
    code_cell(
        "merged.plot(kind=\"scatter\", x=\"technical_score\", y=\"practical_score\", alpha=0.3, title=\"Technical vs Practical\")\n"
        "tp_corr = merged[\"technical_score\"].corr(merged[\"practical_score\"])\n"
        "print(f\"Correlation between technical_score and practical_score: {tp_corr:.3f}\")"
    ),
    markdown_cell(
        "## 3. Complexity by Batch\n"
        "\n"
        "Mean/median `complexity_score` per batch, ordered chronologically "
        "(Winter before Summer within the same year), not alphabetically."
    ),
    code_cell(
        "def batch_sort_key(batch: str) -> tuple:\n"
        "    year = int(batch[1:])\n"
        "    season_order = 0 if batch[0] == \"W\" else 1\n"
        "    return (year, season_order)\n"
        "\n"
        "batch_summary = merged.groupby(\"batch\")[\"complexity_score\"].agg([\"mean\", \"median\", \"count\"]).reset_index()\n"
        "batch_summary[\"sort_key\"] = batch_summary[\"batch\"].apply(batch_sort_key)\n"
        "batch_summary = batch_summary.sort_values(\"sort_key\").drop(columns=\"sort_key\")\n"
        "\n"
        "batch_summary.plot(\n"
        "    x=\"batch\", y=\"mean\", kind=\"line\", marker=\"o\", figsize=(14, 4),\n"
        "    title=\"Mean Complexity Score by Batch (chronological)\", rot=90,\n"
        ")\n"
        "batch_summary"
    ),
    markdown_cell(
        "## 4. Complexity by Status\n"
        "\n"
        "Validation question: are Public companies more complex than average?"
    ),
    code_cell(
        "status_summary = merged.groupby(\"status\")[\"complexity_score\"].agg([\"mean\", \"median\", \"count\"]).sort_values(\"mean\", ascending=False)\n"
        "overall_mean = merged[\"complexity_score\"].mean()\n"
        "print(f\"Overall mean complexity_score: {overall_mean:.2f}\")\n"
        "status_summary"
    ),
    markdown_cell(
        "## 5. Complexity by Industry\n"
        "\n"
        "Each company contributes its `complexity_score` to every industry it's "
        "tagged with (explode, not a single primary industry). Filtered to "
        "industries with >= 20 tagged companies to avoid noisy single-company "
        "averages."
    ),
    code_cell(
        "industry_summary = (\n"
        "    industry_merged.groupby(\"industry\")[\"complexity_score\"]\n"
        "    .agg([\"mean\", \"count\"])\n"
        "    .query(\"count >= 20\")\n"
        "    .sort_values(\"mean\", ascending=False)\n"
        ")\n"
        "industry_summary.plot(\n"
        "    kind=\"barh\", y=\"mean\", figsize=(8, 10),\n"
        "    title=\"Mean Complexity Score by Industry (>=20 companies)\", legend=False,\n"
        ")\n"
        "industry_summary"
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
