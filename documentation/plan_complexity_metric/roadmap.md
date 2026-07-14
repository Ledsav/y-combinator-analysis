# Y Combinator Complexity Index - Project Roadmap

**Version:** 1.0  
**Last Updated:** 2026-01-24  
**Status:** In Progress

---

## Project Overview

**Goal:** Create a reproducible Complexity Index for Y Combinator companies that quantifies startup difficulty across technical and practical dimensions.

**Data Source:** 8 CSV files in `data/raw/` (4,844 companies, 8,465 founders)

**Output:** Per-company complexity scores (0-100 scale) with:
- Technical Complexity component (0-50)
- Practical/Market Complexity component (0-50)
- Combined index and detailed breakdowns

---

## Objectives & Success Metrics

### What the Index Measures

**Technical Complexity (50%)**: Difficulty of building the core technology
- Deep tech indicators: AI, Biotech, Robotics, Hardware
- R&D intensity from descriptions
- Technical founder backgrounds (PhDs, research labs)
- Hard science industries

**Practical Complexity (50%)**: Difficulty of market execution
- Regulatory burden (Fintech, Healthcare)
- Market structure (B2B, B2C, Marketplace)
- Geographic challenges
- Operational intensity

### Success Criteria

| Metric | Target | Purpose |
|--------|--------|---------|
| **Coverage** | ≥95% of companies | Ensure broad applicability |
| **Reproducibility** | 100% deterministic | Same input = same output |
| **Validity** | Pass manual review | Top/bottom 50 companies make sense |
| **Correlation** | r>0.2 with team size | Complex ventures need bigger teams |
| **Distribution** | σ ≥15 points | Good variance, avoid clustering |

---

## Interactive Checklist

**Instructions:** Edit checkboxes below to track progress, or use `python scripts/todo_cli.py toggle <N>`

- [x] **1. Define objectives & metrics**
  - [x] Document complexity components
  - [x] Define success metrics & validation approach
  - [x] Create objectives document

- [x] **2. Inventory raw datasets**
  - [x] Analyze all 8 CSV files
  - [x] Generate data dictionary with schemas
  - [x] Document missingness patterns

- [x] **3. Data cleaning & normalization**
  - [x] Normalize company identifiers
  - [x] Standardize text fields (oneLiner, longDescription)
  - [x] Parse categorical fields (status, batch, region)
  - [x] Output: `data/processed/step1_cleaned/`

- [x] **4. Missing data completion**
  - [x] Identify critical missing fields
  - [x] Implement heuristic imputation rules
  - [x] Flag companies needing enrichment
  - [x] Output: `data/processed/step2_imputed/` + report

- [x] **5. Data enrichment (optional)**
  - [x] Define enrichment strategy & scope
  - [x] Implement web scraping (rate-limited)
  - [x] Store raw enrichment logs
  - [x] Output: `data/processed/step3_enriched/`

- [x] **6. Feature engineering**
  - [x] Extract technical complexity features
  - [x] Extract practical complexity features
  - [x] Combine with founder/school/prior company data
  - [x] Output: `data/processed/features/complexity_features.parquet`

- [x] **7. Scoring rubric design**
  - [x] Design interpretable weighted rubric
  - [x] Calibrate weights with example companies
  - [x] Run sensitivity analysis
  - [x] Output: `notebooks/score_design.ipynb`
  - **Known gap:** the mechanism (module, pipeline, output schema) is complete and correct, but calibration missed two objectives-doc success criteria by a wide margin: correlation with team size (Pearson r=0.035, Spearman r=0.050 vs. target r>0.2) and score-distribution spread (std=10.11 vs. target ≥15) — see `notebooks/score_design.ipynb` section 7 ("Findings") for the full numbers. Per `docs/superpowers/specs/2026-07-10-phase7-scoring-rubric-design.md`'s "Open Question," no formula changes were made to chase these targets; a follow-up brainstorming pass to revise the caps/weights is needed before this index is treated as validated for downstream use (e.g. as an ML feature or segmentation input in later phases).

- [x] **8. ETL pipeline implementation**
  - [x] Create modular ETL scripts in `src/etl/`
  - [x] Build CLI runner with versioning
  - [x] Add automated validation checks
  - [x] Output: Complete pipeline + `complexity_index_v1.csv`
  - **Known gap:** `DEFAULT_STEPS` in `src/etl/pipeline.py` (what `--steps all` resolves to) deliberately excludes `enrich`, but `run_feature_engineering_pipeline` in `src/etl/features.py` always reads its input from `data/processed/step3_enriched/` — `enrich`'s output directory, not `impute`'s (`step2_imputed/`). So a default `--steps all` run regenerates `step1_cleaned/` and `step2_imputed/` but then `features` reads the untouched, pre-existing `step3_enriched/`, meaning fresh clean/impute output never reaches the final `complexity_index` CSV unless `enrich` is explicitly included in `--steps`. No behavior change was made; this is documented only (see the `--steps` help text in `scripts/run_complexity_pipeline.py`).

- [x] **9. Validation & analysis**
  - [x] Score distribution analysis
  - [x] Correlation checks (team size, status)
  - [x] Manual review top/bottom companies
  - [x] Output: `notebooks/complexity_analysis.ipynb`
  - **Confirmed gap:** re-derived fresh (not copied from Phase 7), the team-size correlation (Pearson r=0.035, Spearman r=0.050 vs target r>0.2) and distribution spread (std=10.11 vs target ≥15) gaps identified in Phase 7 are unchanged — see `notebooks/complexity_analysis.ipynb` section 10 ("Findings"). New findings: technical/practical sub-scores are uncorrelated (r=-0.049, as intended); complexity rises markedly by batch over time (undiagnosed cause); Public/Active companies score similarly and both above Acquired/Inactive; industry and validation-question checks (Healthcare→technical, Fintech→practical/regulated) all match intuition. A rubric-revision follow-up (tentatively "Phase 9.5") is recommended before treating the index as fully validated, but is out of scope for this phase.

- [x] **10. Visualization dashboard**
  - [x] Interactive charts mirroring Phase 9's analysis (distribution, technical vs practical, batch, status, industry, correlation heatmap)
  - [x] Searchable/sortable/filterable company explorer table (4,844 companies)
  - [x] Self-contained, offline-capable single HTML file (Plotly.js bundled inline, no CDN, no server)
  - [x] Output: `output/complexity_dashboard_v1.html`

- [ ] **11. Documentation & reproducibility**
  - [ ] Update main README
  - [ ] Add pipeline usage instructions
  - [ ] Write minimal test suite
  - [ ] Version control all outputs

---

## Detailed Phase Descriptions

### Phase 1-2: Planning & Inventory ✅ COMPLETE

**Deliverables:**
- ✅ `objectives_and_metrics.md` - Full objectives document
- ✅ `data_dictionary.md` - Complete schema analysis

**Key Findings:**
- 4,844 companies across 39 YC batches (S05-W24)
- 6.9% missing longDescription, 3.1% missing oneLiner
- 381 companies without founder data
- 57 unique industries, 12,971 tag assignments

### Phase 3: Data Cleaning & Normalization ✅ COMPLETE

**Deliverables:**
- ✅ `src/etl/clean.py` - Cleaning module with 8 cleaning functions
- ✅ `data/processed/step1_cleaned/` - All 8 cleaned CSV files

**Implementation:**
- Created modular cleaning functions for each dataset
- Standardized text fields (stripped whitespace, handled nulls)
- Normalized company `id` as integer primary key
- Preserved batch format (already uppercase: S05, W06, etc.)
- Validated row count preservation across all files
- All 130,561 rows preserved across 8 files

**Tasks:**
1. ✓ Normalize company identifiers (use `id` as primary key)
2. ✓ Standardize text: strip whitespace, handle nulls
3. ✓ Parse `teamSize` as numeric (preserve NaN)
4. ✓ Normalize `batch` format (already uppercase)
5. ✓ Standardize `status` categories

**Output Structure:**
```
data/processed/step1_cleaned/
├── companies_cleaned.csv
├── founders_cleaned.csv
├── industries_cleaned.csv
├── tags_cleaned.csv
├── regions_cleaned.csv
├── schools_cleaned.csv
├── prior_companies_cleaned.csv
└── badges_cleaned.csv
```

### Phase 4: Missing Data Completion

**Imputation Strategy:**
- **oneLiner**: Extract first sentence from `longDescription`
- **longDescription**: Use tags + industry to generate placeholder
- **teamSize**: Flag as "unknown" (don't impute 0)
- **region/country**: Cross-reference with founder locations if available

**Output:**
- Imputed CSVs in `step2_imputed/`
- `imputation_report.csv` with (company_id, field, method)

### Phase 5: Data Enrichment (Optional)

**Scope Decision Points:**
- Budget/time available for scraping
- Quality threshold for proceeding without enrichment
- Priority: focus on high-value companies (Active status, recent batches)

**Approach:**
- Web scraping from company websites (robots.txt compliant)
- Rate limiting: max 10 requests/minute
- Store raw HTML/JSON for reproducibility

### Phase 6: Feature Engineering

**Technical Complexity Features:**
```python
- deep_tech_tag_count: # of AI/ML/Biotech/Hardware tags
- description_tech_score: NLP score from longDescription
- founder_phd_count: # founders with PhDs
- research_company_experience: prior work at universities/labs
```

**Practical Complexity Features:**
```python
- regulated_industry: binary (Fintech/Healthcare/Insurance)
- market_type_score: B2B=3, Marketplace=2, B2C=1
- international_operations: # of countries mentioned
- operational_intensity: logistics/hardware/manufacturing tags
```

### Phase 7: Scoring Rubric

**Initial Approach:** Linear weighted sum

```
Technical Score (0-50):
  - Deep tech tags: 0-20 points
  - Description NLP: 0-15 points
  - Founder background: 0-15 points

Practical Score (0-50):
  - Regulated industry: 0-15 points
  - Market type: 0-15 points
  - Geography/operations: 0-10 points
  - GTM complexity: 0-10 points

Total Complexity = Technical + Practical
```

**Calibration Examples:**
- **Low (0-30)**: Simple SaaS, consumer apps
- **Medium (31-60)**: B2B enterprise, regulated fintech
- **High (61-100)**: Biotech, space tech, hard robotics

### Phase 8: Pipeline Engineering

**Architecture:**
```
src/etl/
├── __init__.py
├── clean.py          # Step 3
├── impute.py         # Step 4
├── enrich.py         # Step 5 (optional)
├── features.py       # Step 6
├── score.py          # Step 7
└── pipeline.py       # Orchestrator

scripts/
└── run_complexity_pipeline.py  # CLI entry point
```

**CLI Usage:**
```bash
python scripts/run_complexity_pipeline.py --steps all --output-version v1
python scripts/run_complexity_pipeline.py --steps clean,impute,features,score
```

### Phase 9: Validation & Analysis

**Analysis Checklist:**
1. Score distribution histogram
2. Technical vs Practical scatter plot
3. Complexity by batch/status/industry
4. Correlation heatmap
5. Manual review of outliers

**Validation Questions:**
- Do biotech companies score high on technical?
- Do fintech companies score high on practical?
- Are public companies more complex than average?
- Does complexity correlate with team size?

### Phase 10: Documentation

**Updates Required:**
- Main `README.md` - add Complexity Index section
- Pipeline usage guide
- Data versioning conventions
- Known limitations & future work

---

## Timeline & Estimates

| Phase | Duration | Status |
|-------|----------|--------|
| 1-2. Planning & Inventory | 1-2 days | ✅ Complete |
| 3. Cleaning | 2 days | ✅ Complete |
| 4. Imputation | 1 day | ✅ Complete |
| 5. Enrichment | 2-7 days | ✅ Complete (scoped to score>=80) |
| 6. Features | 2-3 days | ✅ Complete |
| 7. Scoring | 1-2 days | ✅ Complete |
| 8. Pipeline | 2 days | ✅ Complete |
| 9. Validation | 1 day | ✅ Complete |
| 10. Visualization | 1 day | ✅ Complete |
| 11. Documentation | 1 day | 🔲 Not started |
| **Total** | **10-15 days** | **~91% complete** |

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Missing descriptions (6.9%) | Medium | High | Impute from tags; proceed without for some |
| Subjective scoring | High | Medium | Rule-based weights; document rationale |
| Batch effects | Low | High | Normalize by batch if needed |
| Tag inconsistency | Medium | Medium | Multi-tag support; manual corrections |
| Enrichment failures | Low | Medium | Make enrichment optional; graceful degradation |

---

## Open Questions & Decisions

1. **Scoring normalization**: Normalize within batch or across all companies?
   - **Decision**: Start with global normalization, analyze batch effects later

2. **Enrichment scope**: How many companies to enrich?
   - **Decision**: TBD based on Phase 4 results

3. **NLP approach**: Simple keyword matching or embeddings?
   - **Decision**: Start simple (keyword), upgrade if needed

4. **Version control**: How to version complexity scores?
   - **Decision**: Date-stamped CSVs + git tags (e.g., `complexity_index_v1_2026-01-24.csv`)

---

## Related Documentation

- 📊 **Data Dictionary**: `documentation/dataset/data_dictionary.md`
- 📋 **Objectives & Metrics**: `documentation/plan_complexity_metric/objectives_and_metrics.md`
- 📁 **Dataset Overview**: `documentation/dataset/dataset_overview.md`

---

## Next Immediate Actions

**Current Focus:** Phase 11 - Documentation & Reproducibility (with the open Phase 9.5 rubric-revision decision from Phase 9 still unresolved)

**Next Steps:**
1. Decide on the deferred Phase 9.5 question (revise `score.py`'s weights/caps to address the confirmed team-size correlation and distribution-spread gaps) before or alongside Phase 11 — still not decided as of Phase 10.
2. Update the main `README.md` with a Complexity Index section, pipeline usage instructions (including how to run `scripts/generate_dashboard.py` and open `output/complexity_dashboard_v1.html`), a minimal test suite for anything still untested, and version-control notes for all outputs.
3. Output (Phase 11): updated `README.md` + usage docs.

**To continue:** Mark this task complete and proceed to Phase 11 (or the Phase 9.5 decision first).
