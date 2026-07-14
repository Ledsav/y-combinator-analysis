# Complexity Index: Objectives & Success Metrics

**Document Version:** 1.0  
**Date:** 2026-01-24  
**Status:** Planning Phase

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
| `status` = "Public" | Higher complexity | Hardest companies that succeed go big |
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

## 8. Project Status

**See the main roadmap for task tracking**: `documentation/plan_complexity_metric/ROADMAP.md`

**Completed:**
- ✅ Objectives & metrics definition
- ✅ Data inventory & dictionary

**Next:** Data cleaning & normalization (Phase 3)
