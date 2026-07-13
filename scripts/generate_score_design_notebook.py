"""
Generates notebooks/score_design.ipynb for Phase 7 calibration analysis.

Run: ./.venv/Scripts/python.exe scripts/generate_score_design_notebook.py

Regenerate this way (not by hand-editing the .ipynb) whenever a cell needs
to change, so the notebook stays reproducible from source.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "notebooks" / "score_design.ipynb"


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
        "# Phase 7 Score Design & Calibration\n"
        "\n"
        "Analysis-only notebook: imports the scoring logic from "
        "`src/etl/score.py` (no logic is duplicated here). Covers "
        "distribution, spot-checks, correlation with team size, a "
        "sensitivity pass, and manual top/bottom review, per "
        "`docs/superpowers/specs/2026-07-10-phase7-scoring-rubric-design.md`."
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
        "from src.etl.score import build_score_table\n"
        "\n"
        "features_df = pd.read_parquet(REPO_ROOT / \"data\" / \"processed\" / \"features\" / \"complexity_features.parquet\")\n"
        "scores_df = build_score_table(features_df)\n"
        "scores_df.shape"
    ),
    markdown_cell("## 1. Distribution"),
    code_cell(
        "scores_df[\"complexity_score\"].plot(kind=\"hist\", bins=30, title=\"Complexity Score Distribution\")"
    ),
    code_cell(
        "scores_df.plot(kind=\"scatter\", x=\"technical_score\", y=\"practical_score\", alpha=0.3, title=\"Technical vs Practical\")"
    ),
    markdown_cell(
        "## 2. Spot-check known companies\n"
        "\n"
        "`polymath-robotics` and `andromeda-surgical` are deep-tech/hard-science "
        "(expect high `technical_score`); `gusto` is regulated B2B fintech/payroll "
        "(expect high `practical_score`)."
    ),
    code_cell(
        "spot_check_slugs = [\"polymath-robotics\", \"andromeda-surgical\", \"gusto\"]\n"
        "scores_df[scores_df[\"slug\"].isin(spot_check_slugs)][\n"
        "    [\"slug\", \"name\", \"deep_tech_score\", \"description_score\", \"founder_background_score\",\n"
        "     \"regulated_score\", \"market_type_pts\", \"geo_ops_score\",\n"
        "     \"technical_score\", \"practical_score\", \"complexity_score\"]\n"
        "]"
    ),
    markdown_cell(
        "## 3. Correlation with team size\n"
        "\n"
        "Objectives doc target: `r > 0.2` with team size. `teamSize` is "
        "heavily right-skewed (median 7, max 8,600), so it's log1p-transformed "
        "before correlating."
    ),
    code_cell(
        "companies_df = pd.read_csv(REPO_ROOT / \"data\" / \"processed\" / \"step3_enriched\" / \"companies_enriched.csv\")\n"
        "merged = scores_df.merge(companies_df[[\"id\", \"teamSize\"]], on=\"id\", how=\"left\").dropna(subset=[\"teamSize\"])\n"
        "merged[\"log_team_size\"] = np.log1p(merged[\"teamSize\"])\n"
        "\n"
        "pearson_r = merged[\"complexity_score\"].corr(merged[\"log_team_size\"], method=\"pearson\")\n"
        "spearman_r = merged[\"complexity_score\"].corr(merged[\"log_team_size\"], method=\"spearman\")\n"
        "print(f\"Pearson r (complexity_score vs log1p(teamSize)): {pearson_r:.3f}\")\n"
        "print(f\"Spearman r: {spearman_r:.3f}\")\n"
        "print(f\"Target from objectives doc: r > 0.2\")"
    ),
    markdown_cell(
        "## 4. Distribution spread\n"
        "\n"
        "Objectives doc target: standard deviation ≥ 15 points (avoid clustering)."
    ),
    code_cell(
        "std = scores_df[\"complexity_score\"].std()\n"
        "print(f\"complexity_score std: {std:.2f} (target: >= 15)\")\n"
        "scores_df[\"complexity_score\"].describe()"
    ),
    markdown_cell(
        "## 5. Sensitivity analysis\n"
        "\n"
        "Perturb each cap by ±1 and each bucket's point budget by ±20%, "
        "recompute, and check Spearman rank correlation of the top-100-by-"
        "`complexity_score` between baseline and each perturbation. High "
        "correlation (close to 1.0) means the ranking is stable and not "
        "overly sensitive to the exact calibration constants chosen."
    ),
    code_cell(
        "from src.etl.score import (\n"
        "    compute_deep_tech_score, compute_description_score, compute_founder_background_score,\n"
        "    compute_regulated_score, compute_market_type_pts, compute_geo_ops_score,\n"
        ")\n"
        "\n"
        "def build_with_overrides(**overrides):\n"
        "    parts = [\n"
        "        compute_deep_tech_score(features_df, cap=overrides.get(\"deep_tech_cap\", 3), points=overrides.get(\"deep_tech_points\", 20)),\n"
        "        compute_description_score(features_df, cap=overrides.get(\"description_cap\", 3), points=overrides.get(\"description_points\", 15)),\n"
        "        compute_founder_background_score(features_df, cap=overrides.get(\"founder_cap\", 4), points=overrides.get(\"founder_points\", 15)),\n"
        "        compute_regulated_score(features_df, points=overrides.get(\"regulated_points\", 15)),\n"
        "        compute_market_type_pts(features_df, points_per_level=overrides.get(\"market_points_per_level\", 5)),\n"
        "        compute_geo_ops_score(features_df, intl_points=overrides.get(\"geo_ops_intl_points\", 10), ops_points=overrides.get(\"geo_ops_ops_points\", 10)),\n"
        "    ]\n"
        "    df = features_df[[\"id\"]].copy()\n"
        "    for part in parts:\n"
        "        df = df.merge(part, on=\"id\", how=\"left\")\n"
        "    df[\"complexity_score\"] = df.drop(columns=\"id\").sum(axis=1)\n"
        "    return df\n"
        "\n"
        "baseline_top100 = set(scores_df.nlargest(100, \"complexity_score\")[\"id\"])\n"
        "\n"
        "perturbations = {\n"
        "    \"deep_tech_cap-1\": {\"deep_tech_cap\": 2},\n"
        "    \"deep_tech_cap+1\": {\"deep_tech_cap\": 4},\n"
        "    \"deep_tech_points-20pct\": {\"deep_tech_points\": 16},\n"
        "    \"deep_tech_points+20pct\": {\"deep_tech_points\": 24},\n"
        "    \"regulated_points-20pct\": {\"regulated_points\": 12},\n"
        "    \"regulated_points+20pct\": {\"regulated_points\": 18},\n"
        "}\n"
        "\n"
        "for label, overrides in perturbations.items():\n"
        "    perturbed = build_with_overrides(**overrides)\n"
        "    perturbed_top100 = set(perturbed.nlargest(100, \"complexity_score\")[\"id\"])\n"
        "    overlap = len(baseline_top100 & perturbed_top100)\n"
        "    print(f\"{label}: {overlap}/100 companies remain in top 100\")"
    ),
    markdown_cell(
        "## 6. Manual review\n"
        "\n"
        "Objectives doc target: top/bottom 25 companies should make sense on "
        "manual inspection."
    ),
    code_cell(
        "scores_df.sort_values(\"complexity_score\", ascending=False)[[\"name\", \"batch\", \"complexity_score\"]].head(25)"
    ),
    code_cell(
        "scores_df.sort_values(\"complexity_score\", ascending=True)[[\"name\", \"batch\", \"complexity_score\"]].head(25)"
    ),
    markdown_cell(
        "## 7. Findings\n"
        "\n"
        "- Correlation with log(team size): Pearson r = 0.035, Spearman = 0.050 "
        "(target: > 0.2) — well below target\n"
        "- Distribution std: 10.11 (target: >= 15) — below target\n"
        "- Sensitivity: top-100 overlap ranged from 65-94/100 across perturbations\n"
        "- Manual review: the top 25 are dominated by biotech/deep-tech/hard-science "
        "companies (Atomic Alchemy, Abalone Bio, Atomwise, GEn1E Lifesciences, Rain "
        "Neuromorphics, Altay Therapeutics) plus a few regulated/complex outfits "
        "(Bunkerhill Health, Casetext), which matches intuition for `deep_tech_score` "
        "and `founder_background_score` driving the ranking; the bottom 25 are "
        "consumer-facing education/tutoring/bootcamp products (UPchieve, CodeCombat, "
        "CodeNow, Clever, Codingal, Study Edge) that plausibly score 0 across every "
        "bucket (not regulated, not deep-tech, single-market, no international/ops "
        "footprint) — both ends look sensible on inspection.\n"
        "\n"
        "No formula changes were made in Phase 7 based on these findings "
        "(see \"Open Question\" in the design spec) — if a target is missed "
        "significantly, that requires a follow-up brainstorming pass, not a "
        "silent patch here."
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
