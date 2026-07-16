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
        "Authoritative validation notebook for `data/processed/scores/complexity_index_v2.csv` "
        "(Phase 9.5 rubric: 30/70 technical/practical split — see "
        "`docs/superpowers/specs/2026-07-14-phase9.5-rubric-revision-design.md`) "
        "(self-contained — re-derives team-size correlation and manual outlier review fresh "
        "rather than citing `notebooks/score_design.ipynb`). Covers score distribution, "
        "technical-vs-practical relationship, complexity by batch/status/industry, a full "
        "correlation heatmap, team-size correlation, targeted validation questions, manual "
        "outlier review, success correlation (topCompany badge and Acquired/Public status), "
        "a confound-controlled logistic regression of success on complexity/team size/batch "
        "vintage/founder pedigree, and findings, per "
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
        "scores_df = pd.read_csv(REPO_ROOT / \"data\" / \"processed\" / \"scores\" / \"complexity_index_v2.csv\")\n"
        "bucket_score_cols = [c for c in scores_df.columns if c.endswith(\"_score\") and c not in (\"technical_score\", \"practical_score\", \"complexity_score\")]\n"
        "features_df = pd.read_parquet(REPO_ROOT / \"data\" / \"processed\" / \"features\" / \"complexity_features.parquet\")\n"
        "companies_df = pd.read_csv(REPO_ROOT / \"data\" / \"processed\" / \"step3_enriched\" / \"companies_enriched.csv\")\n"
        "industries_df = pd.read_csv(REPO_ROOT / \"data\" / \"processed\" / \"step3_enriched\" / \"industries_enriched.csv\")\n"
        "badges_df = pd.read_csv(REPO_ROOT / \"data\" / \"processed\" / \"step3_enriched\" / \"badges_enriched.csv\")\n"
        "founders_df = pd.read_csv(REPO_ROOT / \"data\" / \"processed\" / \"step3_enriched\" / \"founders_enriched.csv\")\n"
        "schools_df = pd.read_csv(REPO_ROOT / \"data\" / \"processed\" / \"step3_enriched\" / \"schools_enriched.csv\")\n"
        "\n"
        "merged = scores_df.merge(companies_df[[\"id\", \"teamSize\"]], on=\"id\", how=\"left\")\n"
        "merged[\"log_team_size\"] = np.log1p(merged[\"teamSize\"])\n"
        "\n"
        "feature_cols = [c for c in features_df.columns if c not in (\"id\", \"slug\", \"name\", \"batch\", \"status\") and c not in scores_df.columns]\n"
        "merged = merged.merge(features_df[[\"id\"] + feature_cols], on=\"id\", how=\"left\")\n"
        "\n"
        "top_company_ids = set(badges_df.loc[badges_df[\"badge\"] == \"topCompany\", \"id\"])\n"
        "merged[\"is_top_company\"] = merged[\"id\"].isin(top_company_ids).astype(float)\n"
        "merged[\"is_acquired_or_public\"] = merged[\"status\"].isin([\"Acquired\", \"Public\"]).astype(float)\n"
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
    markdown_cell(
        "## 6. Correlation Heatmap\n"
        "\n"
        "Correlation matrix across all 8 raw features (`complexity_features.parquet`), "
        "the rubric's bucket scores, and the 3 top-level scores."
    ),
    code_cell(
        "import matplotlib.pyplot as plt\n"
        "\n"
        "corr_cols = feature_cols + bucket_score_cols + [\n"
        "    \"technical_score\", \"practical_score\", \"complexity_score\",\n"
        "]\n"
        "corr_matrix = merged[corr_cols].corr()\n"
        "\n"
        "fig, ax = plt.subplots(figsize=(10, 8))\n"
        "im = ax.imshow(corr_matrix, cmap=\"coolwarm\", vmin=-1, vmax=1)\n"
        "ax.set_xticks(range(len(corr_cols)))\n"
        "ax.set_xticklabels(corr_cols, rotation=90)\n"
        "ax.set_yticks(range(len(corr_cols)))\n"
        "ax.set_yticklabels(corr_cols)\n"
        "fig.colorbar(im, ax=ax)\n"
        "ax.set_title(\"Correlation Heatmap: Raw Features, Bucket Scores, Totals\")\n"
        "fig.tight_layout()"
    ),
    markdown_cell(
        "## 7. Team-Size Correlation\n"
        "\n"
        "Objectives doc target: `r > 0.2` with team size. `teamSize` is heavily "
        "right-skewed (median 7, max 8,600), so it's log1p-transformed before "
        "correlating. Re-derived fresh here (not copied from "
        "`notebooks/score_design.ipynb`) so this notebook is self-contained."
    ),
    code_cell(
        "team_size_valid = merged.dropna(subset=[\"teamSize\"])\n"
        "pearson_r = team_size_valid[\"complexity_score\"].corr(team_size_valid[\"log_team_size\"], method=\"pearson\")\n"
        "spearman_r = team_size_valid[\"complexity_score\"].corr(team_size_valid[\"log_team_size\"], method=\"spearman\")\n"
        "print(f\"Pearson r (complexity_score vs log1p(teamSize)): {pearson_r:.3f}\")\n"
        "print(f\"Spearman r: {spearman_r:.3f}\")\n"
        "print(\"Target from objectives doc: r > 0.2\")\n"
        "print(f\"n = {len(team_size_valid)} companies with known teamSize\")"
    ),
    markdown_cell(
        "## 8. Validation Questions\n"
        "\n"
        "Do Healthcare-tagged companies skew high on `technical_score`? Do "
        "Fintech-tagged companies skew high on `practical_score`/`regulated_score`? "
        "(No distinct \"Biotech\" industry tag exists in this dataset — "
        "`Healthcare` is the closest proxy for deep-tech/hard-science regulation.)"
    ),
    code_cell(
        "def industry_group_mean(industry_name: str, score_col: str) -> tuple:\n"
        "    tagged = industry_merged[industry_merged[\"industry\"] == industry_name][score_col]\n"
        "    overall = industry_merged[score_col].mean()\n"
        "    return tagged.mean(), overall, len(tagged)\n"
        "\n"
        "for industry_name, score_col in [\n"
        "    (\"Healthcare\", \"technical_score\"),\n"
        "    (\"Fintech\", \"practical_score\"),\n"
        "    (\"Fintech\", \"regulated_score\"),\n"
        "]:\n"
        "    group_mean, overall_mean_val, n = industry_group_mean(industry_name, score_col)\n"
        "    print(f\"{industry_name} mean {score_col}: {group_mean:.2f} (n={n}) vs overall mean: {overall_mean_val:.2f}\")"
    ),
    markdown_cell(
        "## 9. Manual Review of Outliers\n"
        "\n"
        "Objectives doc target: top/bottom 25 companies should make sense on "
        "manual inspection. Re-derived fresh here (not copied from "
        "`notebooks/score_design.ipynb`)."
    ),
    code_cell(
        "bucket_cols = [\"slug\", \"name\", \"batch\", \"status\"] + bucket_score_cols + [\n"
        "    \"technical_score\", \"practical_score\", \"complexity_score\",\n"
        "]\n"
        "top_25 = merged.sort_values(\"complexity_score\", ascending=False)[bucket_cols].head(25)\n"
        "top_25"
    ),
    code_cell(
        "bottom_25 = merged.sort_values(\"complexity_score\", ascending=True)[bucket_cols].head(25)\n"
        "bottom_25"
    ),
    markdown_cell(
        "## 10. Success Correlation\n"
        "\n"
        "Does complexity predict startup success? Two outcome proxies, per "
        "`documentation/dataset/dataset_overview.md`:\n"
        "- **Strict**: the `topCompany` badge (1.9% of companies) -- YC's own top-performer flag.\n"
        "- **Broad**: `status` in `{Acquired, Public}` (12.4%) -- reached a liquidity/scale outcome.\n"
        "\n"
        "Both are 0/1 flags, so `.corr()` against `complexity_score` is exactly the "
        "point-biserial correlation. Neither definition was part of the original rubric "
        "design or its calibration targets -- this is a fresh validation question, not "
        "a target the scoring was tuned against."
    ),
    code_cell(
        "for flag_col, label in [(\"is_top_company\", \"topCompany (strict)\"), (\"is_acquired_or_public\", \"Acquired/Public (broad)\")]:\n"
        "    n = int(merged[flag_col].sum())\n"
        "    rate = merged[flag_col].mean()\n"
        "    r_complexity = merged[\"complexity_score\"].corr(merged[flag_col])\n"
        "    r_technical = merged[\"technical_score\"].corr(merged[flag_col])\n"
        "    r_practical = merged[\"practical_score\"].corr(merged[flag_col])\n"
        "    print(f\"{label}: n={n} ({rate:.1%})\")\n"
        "    print(f\"  r(complexity_score) = {r_complexity:.3f}\")\n"
        "    print(f\"  r(technical_score)  = {r_technical:.3f}\")\n"
        "    print(f\"  r(practical_score)  = {r_practical:.3f}\")"
    ),
    code_cell(
        "success_group_means = pd.concat(\n"
        "    {\n"
        "        \"topCompany (strict)\": merged.groupby(\"is_top_company\")[\"complexity_score\"].agg([\"mean\", \"median\", \"count\"]),\n"
        "        \"Acquired/Public (broad)\": merged.groupby(\"is_acquired_or_public\")[\"complexity_score\"].agg([\"mean\", \"median\", \"count\"]),\n"
        "    },\n"
        "    names=[\"definition\", \"is_success\"],\n"
        ")\n"
        "success_group_means"
    ),
    markdown_cell(
        "## 11. Confound-Controlled Success Model (with a founder angle)\n"
        "\n"
        "The broad success correlation above (r=-0.105) is suspect: older batches score "
        "*lower* on `complexity_score` (finding in §3) and have had *more time* to reach "
        "Acquired/Public, so batch vintage alone could produce a spurious negative "
        "correlation. A logistic regression on `is_acquired_or_public` isolates "
        "`complexity_score`'s effect after controlling for `batch_year` and `log_team_size` "
        "(team growth is `dataset_overview.md`'s own strongest observed success signal). "
        "Two founder-pedigree covariates are added as a fresh angle, neither of which was "
        "part of the original rubric calibration:\n"
        "- `research_company_experience`: already a raw rubric feature (founder worked at a "
        "research-heavy prior company).\n"
        "- `has_elite_school_founder` (new here): any founder attended Stanford, MIT, "
        "Harvard, or UC Berkeley, per `schools_enriched.csv`."
    ),
    code_cell(
        "import statsmodels.api as sm\n"
        "\n"
        "elite_pattern = \"Stanford|Massachusetts Institute of Technology|\\\\bMIT\\\\b|Harvard|University of California, Berkeley\"\n"
        "elite_hnids = set(schools_df.loc[schools_df[\"school\"].str.contains(elite_pattern, case=False, na=False, regex=True), \"hnid\"])\n"
        "founders_df[\"is_elite_school\"] = founders_df[\"hnid\"].isin(elite_hnids)\n"
        "elite_by_company = founders_df.groupby(\"company_slug\")[\"is_elite_school\"].any().reset_index(name=\"has_elite_school_founder\")\n"
        "\n"
        "merged = merged.merge(elite_by_company, left_on=\"slug\", right_on=\"company_slug\", how=\"left\")\n"
        "merged[\"has_elite_school_founder\"] = merged[\"has_elite_school_founder\"].fillna(False).astype(float)\n"
        "merged[\"batch_year\"] = merged[\"batch\"].str[1:].astype(int)\n"
        "\n"
        "print(f\"Elite-school founder rate: {merged['has_elite_school_founder'].mean():.1%} (n={int(merged['has_elite_school_founder'].sum())})\")\n"
        "print(f\"Bivariate r(is_acquired_or_public, has_elite_school_founder) = {merged['is_acquired_or_public'].corr(merged['has_elite_school_founder']):.3f}\")"
    ),
    code_cell(
        "reg_cols = [\"complexity_score\", \"log_team_size\", \"batch_year\", \"has_elite_school_founder\", \"research_company_experience\"]\n"
        "reg_df = merged.dropna(subset=reg_cols)\n"
        "print(f\"n = {len(reg_df)} of {len(merged)} companies (dropped for missing teamSize)\")\n"
        "\n"
        "X = sm.add_constant(reg_df[reg_cols])\n"
        "y = reg_df[\"is_acquired_or_public\"]\n"
        "logit_model = sm.Logit(y, X).fit(disp=0)\n"
        "logit_model.summary()"
    ),
    code_cell(
        "import numpy as np\n"
        "print(\"Odds ratios (exp(coef)):\")\n"
        "np.exp(logit_model.params).round(3)"
    ),
    markdown_cell(
        "## 12. Findings\n"
        "\n"
        "**Phase 9.5 rubric revision (re-derived here on `complexity_index_v2.csv`):**\n"
        "- The technical/practical split was revised from 50/50 to 30/70 (technical 0-30, "
        "practical 0-70), with tighter per-bucket caps, per "
        "`docs/superpowers/specs/2026-07-14-phase9.5-rubric-revision-design.md`. Diagnostics "
        "showed the original targets (team-size r>0.2, distribution σ≥15) are unreachable via "
        "reweighting alone while keeping the score bounded 0-100 and both dimensions "
        "meaningfully represented — both targets were formally relaxed, not silently dropped.\n"
        "- Correlation with log(team size): Pearson r = 0.103, Spearman r = 0.102 (target: "
        "relaxed from > 0.2) — real improvement over v1's r=0.035, still not a strong "
        "relationship.\n"
        "- Distribution std: 11.95 (target: relaxed from >= 15) — real improvement over v1's "
        "10.11 (+18%), still below the original aspiration.\n"
        "\n"
        "**Findings from v2 (compare against Phase 9's v1 findings, reproduced fresh here on "
        "the new rubric):**\n"
        "- Technical vs Practical: correlation = -0.051 — still essentially uncorrelated, "
        "same conclusion as v1: the two sub-scores measure independent dimensions.\n"
        "- Complexity by batch: still rises over time, from ~19 in the earliest batches "
        "(S05-S09) to ~34 in the most recent (S22-S24) — same shape as v1's trend, rescaled "
        "to the new 0-100 range.\n"
        "- Complexity by status: Active (mean 29.1, n=3441) and Public (mean 29.0, n=19) "
        "score similarly and both above Acquired (23.9) and Inactive (22.3) — same ordering "
        "as v1, confirmed on the new rubric.\n"
        "- Complexity by industry: the top of the ranking shifted noticeably under the "
        "practical-heavy rebalance — `Legal` (49.4), `Finance and Accounting` (46.6), and "
        "`Supply Chain and Logistics` (42.7) now lead, ahead of `Drug Discovery and Delivery` "
        "(40.5, v1's top industry). The bottom is largely unchanged: `Education` (8.5), "
        "`Social` (10.9), `Content` (11.8), `Gaming` (13.3), `Virtual and Augmented Reality` "
        "(13.1), `Apparel and Cosmetics` (14.2).\n"
        "- Validation questions confirmed: Healthcare-tagged companies still score ~2x the "
        "overall mean on `technical_score` (9.20 vs 4.90); Fintech-tagged companies score "
        "higher on `practical_score` (27.94 vs 22.53) and universally receive the full "
        "`regulated_score` bonus (21.00 vs an overall mean of 6.68).\n"
        "- **New effect of the 30/70 rebalance**: since the practical budget alone (70 points) "
        "now exceeds v1's entire observed maximum (63.8), companies with zero technical "
        "signal can reach very high complexity scores purely on practical complexity — "
        "several companies with `technical_score`=0.0 (e.g. Bulk MRO Industrial Supply, "
        "TrackChain, Nuvocargo, Uwi, DimOrder) now reach `complexity_score`=70.0, placing "
        "them in the top 25. This is a direct, expected consequence of the rebalance, not an "
        "anomaly — worth noting for anyone comparing v1 and v2 rankings directly.\n"
        "- Manual review: top scorer is now `BeGo` (85.0, technical=15.0/practical=70.0, "
        "was also v1's top scorer at 63.8). Bottom 25 unchanged in character — all "
        "`complexity_score`=0.0, consumer/education products (e.g. `CodeCombat`, `CodeNow`, "
        "`Clever`, `Study Edge`, `Avocademy`).\n"
        "- **Success correlation (new)**: complexity does not predict either outcome proxy. "
        "`topCompany` badge: r=-0.003 (essentially zero, n=91). Broader `Acquired`/`Public` "
        "status: r=-0.105 (weakly *negative*, n=598) — companies that reach that outcome "
        "score 24.0 on average vs. 27.8 for the rest. Neither sub-score (technical r=-0.070, "
        "practical r=-0.078 for the broad definition) rescues this. This is a real, if "
        "unflattering, result for objectives doc use-case #3 (\"research instrument ... "
        "correlation between complexity and outcomes\") — the index does not function as a "
        "success predictor.\n"
        "- **Confound-controlled model (new)**: the -0.105 bivariate correlation turns out to "
        "be exactly the batch-vintage confound suspected above — in a logistic regression of "
        "`is_acquired_or_public` on `complexity_score` + `log_team_size` + `batch_year` + two "
        "founder-pedigree covariates, `complexity_score`'s coefficient is not significant "
        "(p=0.36, odds ratio 0.996 — i.e. no effect in either direction) once vintage and "
        "team growth are controlled for. `batch_year` dominates (odds ratio 0.79 per year "
        "more recent, p<0.001, purely mechanical: less time to exit) and `log_team_size` is "
        "the only other real signal (odds ratio 1.10, p=0.001). The founder-pedigree angle "
        "comes up empty too: neither `has_elite_school_founder` (Stanford/MIT/Harvard/"
        "Berkeley, p=0.93) nor `research_company_experience` (p=0.65) predicts success once "
        "controlled — a naive elite-school bivariate correlation (r=0.035) exists but "
        "vanishes after controlling, so it was itself a vintage/team-size artifact, not a "
        "real pedigree effect. Net: once you strip out \"how long has this company had to "
        "exit\" and \"how big did the team get\", nothing else measured in this dataset — "
        "complexity or founder background — moves the needle on success.\n"
        "\n"
        "**Conclusion:** the Phase 9.5 rubric revision produces a real, verified improvement "
        "on both previously-missed calibration targets without abandoning the balanced "
        "technical+practical design or the 0-100 bound — but neither target is fully met, and "
        "the objectives doc now records both as formally relaxed with the diagnostic "
        "rationale, rather than carrying them forward as an open gap indefinitely. The index "
        "passes manual review, produces intuitive industry/status/batch patterns, and is now "
        "treated as the current default (`v2`) — `v1` remains available as the historical "
        "baseline."
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
