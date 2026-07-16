# Complexity Index: Objectives & Success Metrics

**Document Version:** 1.0  
**Date:** 2026-01-24  
**Status:** Complete (all 11 phases — see `documentation/plan_complexity_metric/roadmap.md`)

---

## 1. Objective Definition

### Primary Objective
Create a **Complexity Index** that quantifies the difficulty and ambition of Y Combinator startups across two dimensions:
1. **Technical Complexity** - difficulty of the technology/product being built
2. **Practical Complexity** - difficulty of market execution and operational challenges

### Purpose & Use Cases

The Complexity Index will serve as:

1. **Predictive Feature**: Input variable for ML models predicting startup success/failure
2. **Segmentation Tool**: Group companies into complexity cohorts for comparative analysis
3. **Research Instrument**: Investigate correlation between complexity and outcomes (success rate, funding, growth)
4. **Portfolio Analysis**: Understand YC's investment thesis evolution over time

### Scope

- **Input Data**: 8 raw CSV files from `data/raw/` (4,844 companies, 8,465 founders)
- **Output**: Per-company complexity scores (0-100 scale) with component breakdowns
- **Coverage Target**: ≥95% of companies with valid scores
- **Time Horizon**: All YC batches (2005-2024)

---

## 2. Complexity Components

### 2.1 Technical Complexity (Weight: 30%, revised from 50% in Phase 9.5)

**Definition**: Difficulty of building the core technology/product

**Indicators**:
- **Deep Tech Tags**: AI, Machine Learning, Biotech, Robotics, Quantum, Hardware, Space Tech
- **R&D Intensity**: NLP signals from `longDescription` (research, patents, novel algorithms)
- **Technical Talent**: Founders with PhD backgrounds or prior experience at research-heavy companies
- **Hard Science Industries**: Healthcare, Hard Tech, Industrial, Manufacturing

**Scoring Logic**:
- Base score from tag/industry classification (0-40 points)
- NLP-based description analysis (+0-30 points)
- Founder pedigree multiplier (+0-30 points)

### 2.2 Practical/Market Complexity (Weight: 70%, revised from 50% in Phase 9.5)

**Definition**: Difficulty of go-to-market, operations, and scaling

**Indicators**:
- **Regulatory Burden**: Fintech, Healthcare, Insurance, Legal, Government sectors
- **Market Structure**: B2B (long sales cycles), B2C (high CAC), Marketplace (chicken-egg)
- **Geographic Challenges**: Operating in emerging markets or multiple countries
- **Operational Intensity**: Real-world operations (logistics, hardware, manufacturing)

**Scoring Logic**:
- Regulatory/compliance sectors (+0-25 points)
- Market type complexity (+0-25 points)
- Geographic/operational factors (+0-25 points)
- Customer acquisition difficulty (+0-25 points)

---

## 3. Success Metrics

### 3.1 Data Quality Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Coverage** | ≥95% companies scored | % of companies with non-null complexity score |
| **Completeness** | ≥90% feature coverage | % of features successfully extracted per company |
| **Data Freshness** | 2024 batch included | Latest batch in scored dataset |

### 3.2 Validity Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Face Validity** | Manual review pass | Expert review of top/bottom 50 companies |
| **Construct Validity** | Expected correlations | Technical complexity correlates with deep-tech tags |
| **Distribution** | Normal-ish curve | Avoid bimodal or heavily skewed distributions |
| **Variance** | Relaxed in Phase 9.5 | Standard deviation ≥15 points was the original target; diagnostics showed this is unreachable while keeping the score bounded 0-100 and both technical and practical dimensions meaningfully represented (a defensible rebalance tops out around σ≈12; only a near-elimination of the technical dimension reaches σ≥15). Phase 9.5's revised rubric achieves σ=11.95 (up from 10.11) — a real, verified improvement, target formally relaxed rather than met. See `docs/superpowers/specs/2026-07-14-phase9.5-rubric-revision-design.md`. |

### 3.3 Sanity Check Correlations

Expected relationships (to validate scoring):

| Variable | Expected Correlation | Rationale |
|----------|---------------------|-----------|
| `teamSize` (for Active companies) | Relaxed in Phase 9.5 | r>0.2 was the original target. Diagnostics found no single one of the 8 underlying features correlates with log(team size) above r=0.193, several technical-side features correlate *negatively*, and even a 100%-practical reweight only reaches r=0.128 — no achievable feature combination clears r>0.2. Phase 9.5's rubric reaches r=0.103 (up from 0.035) as a side effect of the spread-focused rebalance, target formally relaxed rather than met. See `docs/superpowers/specs/2026-07-14-phase9.5-rubric-revision-design.md`. |
| `status` = "Public" | Higher complexity | Public (mean 29.0, n=19) and Active (29.1) score similarly, both above Acquired (23.9) and Inactive (22.3) — directionally right on Public, but n=19 is too small to lean on. |
| `topCompany` badge / success (strict) | Positive correlation with complexity | **Not met.** Point-biserial r = -0.003 (n=91, 1.9% of companies) — essentially zero. Complexity does not predict YC's own top-performer flag. See notebook §10. |
| `status` in {Acquired, Public} / success (broad) | Positive correlation with complexity | **Not met.** Point-biserial r = -0.105 (n=598, 12.4%) — weakly *negative*. Companies reaching this outcome score 24.0 on average vs. 27.8 for the rest. Confounded by batch vintage (older batches score lower on complexity and have had more time to reach Acquired/Public) and by `Acquired` mixing strong exits with acquihires; not controlled for here. See notebook §10 and `documentation/dataset/dataset_overview.md`. |
| Biotech/Healthcare industry | High technical score | Known deep-tech domains |
| Fintech/Healthcare industry | High practical score | Heavily regulated sectors |
| YC batch vintage | ? | Test if complexity thesis changed over time |

### 3.4 Reproducibility Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Script Success Rate** | 100% | ETL pipeline runs without errors on fresh data |
| **Deterministic Output** | 100% match | Same input → same output across runs |
| **Documentation Coverage** | All steps documented | README + inline comments explain logic |
| **Version Control** | Git tracked | All code, configs, and outputs versioned |

---

## 4. Analysis Plan

### 4.1 Exploratory Analysis
- Score distribution by batch, status, industry
- Correlation matrix: complexity vs key variables
- Identify outliers and edge cases

### 4.2 Validation Analysis
- Top 20 most/least complex companies (manual review)
- Stratified sampling for qualitative validation
- Compare technical vs practical complexity (scatterplot)

### 4.3 Insights & Applications
- Success rate by complexity quartile
- Complexity evolution over YC batches
- Industry complexity benchmarks
- Founder background impact on complexity choice

---

## 5. External Research Comparison

The success correlation (section 3.3) and the confound-controlled model in
`notebooks/complexity_analysis.ipynb` (section 11) were checked against published research on
the same questions, to see whether the results land on familiar ground or contradict it.

**Elite-school founder pedigree not predicting success.** This is the strongest match. A 2026
arXiv paper studying founder backgrounds within Y Combinator itself, "Founder Backgrounds and
Startup Funding: Evidence from Y Combinator," found that founder credentials, including
top-school attendance, explain only 0.6% to 3.5% of variance in funding outcomes, with a
top-school coefficient that is not statistically significant (p > 0.10). Their explanation
matches ours: YC's own admissions process already filters for founder quality, so within that
filtered population, pedigree has little predictive power left. Broader literature agrees more
generally, describing the founder education to outcome link as "scant" or "weak/inconsistent,"
despite clear investor bias toward pedigree at the funding stage.

**Batch vintage dominating the outcome.** This is the best established pattern in the
comparison set. Venture capital research treats fund vintage year as one of the single most
important factors in fund performance, with roughly 80% of returns concentrated in 22% to 30%
of vintages, driven by how much time a cohort has had to mature and the market conditions it
was deployed into. Our `batch_year` coefficient dominating the regression is the same
phenomenon at the company level.

**Team size correlating with success.** Corroborated, but with a live methodological debate
attached. Some research finds a positive team-size-to-success relationship, while other work
frames this as survivorship bias: only the hiring sprees of eventual winners get remembered,
while the far larger set of companies that hired aggressively and failed do not. Startup
Genome's widely cited finding that premature scaling, including hiring too fast, is behind 70%
to 74% of startup failures points in the same direction. Our regression is cross-sectional and
cannot separate cause from effect here either.

**Complexity not predicting success.** No directly comparable published metric exists, since
the Complexity Index is custom to this project. Two adjacent findings are still relevant. Y
Combinator's own public philosophy, described by Paul Graham and CEO Michael Seibel, treats
idea difficulty as close to unmeasurable at the earliest stage and instead names founder
execution, formidability, communication, and motivation as the real predictors. Separately,
deep-tech and biotech companies, the highest-complexity segment in this dataset, are well
documented to take structurally longer to reach IPO or acquisition than software companies.
That means a same-batch, point-in-time Acquired/Public snapshot could still understate outcomes
for complex companies even after the `batch_year` control. This is a real, untested limitation
of the current model, not a resolved question.

**Sources**
- [Founder Backgrounds and Startup Funding: Evidence from Y Combinator](https://arxiv.org/html/2512.13755v1)
- [Does more education lead to better startup funding outcomes?](https://www.tandfonline.com/doi/full/10.1080/23322039.2024.2354281)
- [VC's Pedigree Bias: Data Reveals Funding Inequality](https://www.betaboom.com/magazine/article/pedigree-bias-venture-capital)
- [The Vintage Year Power Law, StepStone Group](https://www.stepstonegroup.com/news-insights/the-vintage-year-power-law/)
- [Why Fund Vintage Matters and How Timing Shapes Venture Outcomes](https://www.fbventures.vc/post/why-vintage-year-matters-in-venture-capital)
- [Founding Teams and Startup Performance, NBER working paper](https://www.nber.org/system/files/working_papers/w28417/revisions/w28417.rev0.pdf)
- [Graduating the Old Guard: survivorship bias in startup hiring](https://thepiegrower.medium.com/graduating-the-old-guard-will-more-startups-succeed-without-their-survivorship-bias-6ebad632d6f5)
- [A Deep Dive Into the Anatomy of Premature Scaling, Startup Genome](https://startupgenome.com/insights/a-deep-dive-into-the-anatomy-of-premature-scaling)
- [What We Look for in Founders, Paul Graham](https://www.paulgraham.com/founders.html)
- [What Makes Great Founders Stand Out?, Y Combinator](https://www.ycombinator.com/library/64-what-makes-great-founders-stand-out)
- [Deep Tech Venture Capital: Key Strategies and Evaluations](https://growthequityinterviewguide.com/venture-capital/sector-focused-venture-capital/deep-tech-venture-capital)

---

## 6. Risks & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Missing descriptions (6.9%) | Medium | High | Impute from tags/industry; flag for enrichment |
| Subjective scoring | High | Medium | Use rule-based approach first; document weights |
| Industry misclassification | Medium | Medium | Multi-tag support; manual review edge cases |
| Batch effects (early vs recent) | Low | High | Normalize or stratify by batch |
| Score inflation/deflation | Medium | Medium | Calibrate against known examples |

---

## 7. Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| **Planning** (Step 1) | 1 day | This document ✓ |
| **Inventory** (Step 2) | 0.5 day | Data dictionary ✓ |
| **Cleaning** (Step 3) | 2 days | Cleaned CSVs |
| **Imputation** (Step 4) | 1 day | Imputed dataset |
| **Feature Engineering** (Step 6) | 3 days | Feature table |
| **Scoring** (Step 7) | 2 days | Complexity index v1 |
| **Validation** (Step 9) | 1 day | Analysis notebook |
| **Total** | ~10 days | Full pipeline |

---

## 8. Open Questions

1. **Scoring Approach**: Linear weights vs logistic mapping vs percentile ranks?
2. **Normalization**: Normalize within batch or across all companies?
3. **Tag Conflicts**: How to handle companies with both "low-tech" and "high-tech" tags?
4. **Temporal Bias**: Should recent companies (less data) be scored differently?
5. **Enrichment Scope**: How many missing descriptions should we attempt to scrape?

**Decision Log**: Track key decisions in `documentation/plan/decisions.md`

---

## 9. Project Status

**See the main roadmap for full task tracking**: `documentation/plan_complexity_metric/roadmap.md`

**Completed:** all 11 phases — data cleaning, imputation, enrichment, feature engineering, scoring rubric (including the Phase 9.5 revision to a 30/70 technical/practical split), the ETL pipeline, validation & analysis, the visualization dashboard, and this documentation pass.

**Current output:** `data/processed/scores/complexity_index_v2.csv` (current default) and `complexity_index_v1.csv` (historical Phase 7 baseline), analyzed in `notebooks/complexity_analysis.ipynb` and `output/complexity_dashboard_v2.html`.
