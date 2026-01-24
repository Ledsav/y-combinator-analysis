# AI Agent Instructions - Y Combinator Analysis Project

## Project Mission
Build a **Complexity Index** to quantify Y Combinator startup difficulty across technical (building the product) and practical (market execution) dimensions. The goal is a reproducible, interpretable scoring system for 4,844 companies.

## Architecture Overview

**Data Pipeline Flow:**
```
data/raw/*.csv (8 files)
  → scripts/analyze_raw_data.py (inventory)
  → src/etl/clean.py (planned: normalization)
  → src/etl/impute.py (planned: fill missing data)
  → src/etl/features.py (planned: extract complexity signals)
  → src/etl/score.py (planned: compute 0-100 complexity score)
  → data/processed/complexity_index_v1.csv
```

**Key Components:**
- `data/raw/`: 8 CSVs with companies, founders, industries, tags, schools, prior_companies, regions, badges
- `data/processed/`: Versioned outputs at each pipeline stage (step1_cleaned/, step2_imputed/, etc.)
- `scripts/`: Standalone utilities (data analysis, todo management)
- `src/etl/`: Core ETL pipeline modules (not yet created)
- `notebooks/`: Jupyter notebooks for exploration and validation
- `documentation/`: Structured docs with single source of truth

## Critical Conventions

### 1. Documentation Structure (CENTRALIZED)
- **Single roadmap**: `documentation/plan_complexity_metric/ROADMAP.md` contains ALL task tracking, phases, and deliverables
- **No duplicate checklists**: Objectives doc points to ROADMAP, not vice versa
- **Folder structure**:
  - `documentation/plan_complexity_metric/` - roadmap, objectives, metrics
  - `documentation/dataset/` - data dictionary, dataset overview

### 2. Task Tracking
- Edit checkboxes directly in `ROADMAP.md` OR use: `python scripts/todo_cli.py toggle <N>`
- CLI reads/writes to `ROADMAP.md` (not a separate todo file)
- 10 phases defined, currently at Phase 2 complete (planning + inventory done)

### 3. Data Versioning Pattern
Each pipeline stage outputs to `data/processed/stepN_<stage>/`:
- `step1_cleaned/` - normalized identifiers, standardized text
- `step2_imputed/` - heuristic gap-filling + enrichment flags
- `step3_enriched/` - optional web scraping results
- `features/` - engineered complexity features (parquet format)
- Final: `complexity_index_v1.csv` with per-company scores

### 4. Python Environment
- Uses `.venv` virtual environment (Windows-focused project)
- Run Python via: `C:/Users/megaa/OneDrive/Desktop/projects/y-combinator-analysis/.venv/Scripts/python.exe`
- Dependencies: pandas, numpy (minimal for now)
- Version: Python 3.12+

### 5. ETL Module Structure (Planned)
```python
src/etl/
├── __init__.py
├── clean.py      # Normalize IDs, standardize text, parse numerics
├── impute.py     # oneLiner from longDescription, flag nulls
├── enrich.py     # Optional web scraping (rate-limited)
├── features.py   # Extract technical/practical signals
├── score.py      # Apply weighted rubric (0-100 scale)
└── pipeline.py   # Orchestrate all steps
```

## Key Workflows

### Generate Data Dictionary
```bash
python scripts/analyze_raw_data.py > documentation/dataset/data_dictionary.md
```
- Outputs markdown tables with schema, null %, sample values for all CSVs
- Run after any raw data changes

### Progress Tracking Workflow (CRITICAL)

**After completing ANY task or sub-task:**

1. **Update ROADMAP.md immediately:**
   ```bash
   # Option 1: Use CLI
   python scripts/todo_cli.py toggle <N>
   
   # Option 2: Edit directly
   # Change [ ] to [x] in documentation/plan_complexity_metric/ROADMAP.md
   ```

2. **Update "Current Status" section in THIS file (.github/copilot-instructions.md):**
   - Change phase status: `🔲 Not started` → `🔄 In progress` → `✅ Complete`
   - Update "Next:" to point to the actual next phase
   - If Phase 3+ is complete, update the entire "Current Status" section

3. **Document implementation patterns (when code is added):**
   - If you create new modules (e.g., `src/etl/clean.py`), update "ETL Module Structure" section
   - If you establish new conventions, add them to "Project-Specific Patterns"
   - If pipeline behavior changes, update "Data Pipeline Flow" diagram

4. **Update ROADMAP.md phase descriptions:**
   - When starting a phase, mark the main checkbox as `[x]` and sub-tasks as `[ ]`
   - As you complete sub-tasks, check them off immediately
   - Add notes about decisions made in the "Open Questions & Decisions" section

**Example workflow for Phase 3:**
```bash
# 1. Start Phase 3
python scripts/todo_cli.py toggle 3  # Marks "Data cleaning & normalization" in progress

# 2. Create src/etl/clean.py
# ... implement cleaning logic ...

# 3. Update copilot-instructions.md:
#    - Change "ETL Module Structure (Planned)" to "ETL Module Structure"
#    - Add actual function signatures and patterns used

# 4. Complete Phase 3
#    - Mark all sub-tasks complete in ROADMAP.md
#    - Update "Current Status" in copilot-instructions.md to "Phase 3 Complete"

# 5. Commit with clear message
git add .
git commit -m "Phase 3 complete: Data cleaning pipeline with validation"
```

**Manual Task Tracking:**
```bash
python scripts/todo_cli.py list              # View all tasks
python scripts/todo_cli.py toggle 3          # Toggle task #3
python scripts/todo_cli.py set 3 done        # Mark complete
```

### Complexity Scoring Logic (Future)
**Technical Complexity (0-50):**
- Deep tech tags (AI, Biotech, Robotics): 0-20 pts
- NLP from `longDescription`: 0-15 pts
- Founder PhDs / research background: 0-15 pts

**Practical Complexity (0-50):**
- Regulated industries (Fintech, Healthcare): 0-15 pts
- Market type (B2B=3, Marketplace=2, B2C=1): 0-15 pts
- Geographic/operational factors: 0-10 pts
- GTM complexity: 0-10 pts

## Data Schema Essentials

**companies.csv** (4,844 rows):
- Primary key: `id`
- Text fields: `name`, `slug`, `oneLiner` (3.1% null), `longDescription` (6.9% null)
- Categories: `status` (Active/Acquired/Inactive/Public), `batch` (S05-W24)
- Numeric: `teamSize` (1.6% null)

**founders.csv** (8,465 rows):
- Links to companies via `company_slug`
- 381 companies have NO founder data
- 74% missing `current_title`

**Relationships:**
- `industries.csv`: many-to-many (company_id → industry)
- `tags.csv`: many-to-many (company_id → tag)
- `schools.csv`: many-to-many (founder_hnid → school)
- `prior_companies.csv`: many-to-many (founder_hnid → company)

## Project-Specific Patterns

### Path Handling
Always use `Path(__file__).resolve().parents[N]` for robust cross-file references:
```python
from pathlib import Path
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
```

### Missing Data Philosophy
- **Don't impute zeros** for teamSize (use NaN or "unknown" flag)
- **Heuristic imputation only** for text fields (oneLiner from first sentence of longDescription)
- **Flag for enrichment** rather than drop incomplete records (goal: ≥95% coverage)

### Scoring Interpretability
- Start with **linear weighted sums** (not ML models)
- Document all weights and rationale in `notebooks/score_design.ipynb`
- Validate with manual review of top/bottom 50 companies
- Target: normal-ish distribution with σ ≥15 on 0-100 scale

### Reproducibility Requirements
- All outputs must be deterministic (same input → same output)
- Version outputs by date: `complexity_index_v1_2026-01-24.csv`
- Store enrichment logs separately (API responses, scraped HTML)
- Git-ignore large processed files but track schemas

## What NOT to Do

❌ Create duplicate roadmaps or todo lists (ROADMAP.md is the single source)  
❌ Impute missing values without documenting the method  
❌ Use ML scoring until the rule-based baseline is validated  
❌ Scrape websites without rate limiting (max 10 req/min)  
❌ Modify raw CSVs (always output to `data/processed/`)  
❌ Create notebooks without corresponding validation in ROADMAP Phase 9  
❌ **Complete tasks without updating ROADMAP.md checkboxes immediately**  
❌ **Add new code patterns without updating copilot-instructions.md**  
❌ **Change architecture without updating the "Data Pipeline Flow" diagram**

## Integration Points

**External APIs (Planned, Optional):**
- Clearbit / LinkedIn for missing founder data
- Company websites for missing descriptions
- Always respect robots.txt, store raw responses, make enrichment OPTIONAL

**Output Consumers:**
- Analysis notebooks (Phase 9 validation)
- ML models (complexity as predictive feature)
- Clustering / segmentation analysis

## Current Status (Phase 2 Complete)

✅ Objectives & metrics defined  
✅ Data dictionary generated (8 CSVs analyzed)  
🔲 Next: Data cleaning & normalization (Phase 3)

**When implementing Phase 3:**
1. Create `src/etl/clean.py` with functions for each CSV
2. Handle company `id` as canonical primary key (not name/slug)
3. Standardize batch format: `S05`, `W06` (uppercase, zero-padded)
4. Output 8 cleaned CSVs to `data/processed/step1_cleaned/`
5. Add validation: row count matches, no duplicate IDs, schema preserved
6. **Update ROADMAP.md**: Mark Phase 3 checkbox as `[x]` and all sub-tasks
7. **Update this file**: Change Phase 3 status from 🔲 to ✅, update "Next:" to Phase 4

## Keeping Documentation in Sync

**This file (.github/copilot-instructions.md) should be updated when:**
- ✅ New modules are created in `src/etl/` (update "ETL Module Structure")
- ✅ Pipeline architecture changes (update "Data Pipeline Flow")
- ✅ New conventions are established (add to "Project-Specific Patterns")
- ✅ Phases are completed (update "Current Status")
- ✅ Critical decisions are made (add to "Questions to Ask" or document the answer)

**ROADMAP.md should be updated when:**
- ✅ Any task or sub-task is started or completed (checkbox toggling)
- ✅ Deliverables are produced (note the actual output path/file)
- ✅ Timeline estimates change
- ✅ New risks are identified

**Synchronization checklist after major work:**
1. ROADMAP.md checkboxes reflect actual completion
2. copilot-instructions.md "Current Status" matches ROADMAP
3. Module structure diagrams match `src/` directory
4. Data flow diagrams match actual pipeline outputs
5. Git commit includes both ROADMAP.md and copilot-instructions.md if both changed

## Questions to Ask

Before implementing features, validate these decisions:
- Should complexity scores be normalized by YC batch (early vs recent)?
- Enrichment scope: all companies or just Active/recent batches?
- NLP approach: keyword matching vs embeddings for description analysis?
- How to handle multi-tag conflicts (e.g., company has both SaaS and Deep Tech)?
