# Phase 11 Documentation & Reproducibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the `src/etl/impute.py` test-coverage gap, rewrite `README.md` from its generic template into a real Complexity-Index-specific document (overview, quickstart, versioning, known limitations, testing), and mark Phase 11 complete in the roadmap — the final phase of the project, per `docs/superpowers/specs/2026-07-14-phase11-documentation-design.md`.

**Architecture:** No production logic changes anywhere. One new test file covering an already-in-production module (`impute.py`), one full-content rewrite of a pure-prose file (`README.md`), one roadmap doc update. No new dependencies, no new scripts.

**Tech Stack:** `pytest`, `pandas` (test file only) — everything else is Markdown.

## Global Constraints

- `src/etl/impute.py`'s actual logic is never modified — `tests/test_impute.py` is coverage-only.
- Every command documented in the README must be verified to actually work during implementation (run it for real), not transcribed from memory.
- Real, already-verified numbers used throughout this plan: team-size correlation r=0.103, distribution spread σ=11.95 (both from Phase 9.5, both still short of the objectives doc's original — now relaxed — targets of r>0.2 and σ≥15); pre-existing NaN `slug` values at company ids 382, 599, 1189 (documented since Phase 6); Phase 8's known gap where `--steps all` doesn't propagate fresh `impute` output through to the final index unless `enrich` is explicitly included in `--steps`.
- Real verified `extract_first_sentence` behavior (Global Constraints for Task 1 — computed by running the actual function against real inputs before this plan was written): `extract_first_sentence(float("nan"))` → `""`; `extract_first_sentence("")` → `""`; `extract_first_sentence("   ")` → `""`; `extract_first_sentence("We build tools for developers. Second sentence here.")` → `"We build tools for developers."`; `extract_first_sentence("Acme Inc. builds widgets for the widget industry.")` → `"Acme Inc"` (the ≤10-char "Acme Inc." abbreviation match falls through to the `re.split` fallback, which discards the trailing period); `extract_first_sentence("Hi.")` → `"Hi."` (the split fallback finds no match since there's no trailing whitespace after the period, so the original string passes through unchanged); a 100+-character string with no `.`/`!`/`?` anywhere returns exactly the first 100 characters, stripped.
- Real verified `add_founder_count`/`impute_oneliner_from_description`/`create_enrichment_priorities`/`validate_imputation` behavior on hand-built fixtures — see each function's task steps below for the exact fixtures and exact expected outputs, all independently run and confirmed before this plan was written.

---

## Task 1: `tests/test_impute.py`

**Files:**
- Create: `tests/test_impute.py`

**Interfaces:**
- Consumes: `src/etl/impute.py`'s existing, unmodified functions — `extract_first_sentence(text: str) -> str`, `impute_oneliner_from_description(companies_df) -> Tuple[pd.DataFrame, List[Dict]]`, `add_founder_count(companies_df, founders_df) -> Tuple[pd.DataFrame, List[Dict]]`, `create_enrichment_priorities(companies_df) -> pd.DataFrame`, `validate_imputation(original_df, imputed_df) -> None`, `run_imputation_pipeline(input_dir=None, output_dir=None) -> None`.

- [ ] **Step 1: Write the full test file**

Create `tests/test_impute.py`:

```python
import pandas as pd
import pytest

from src.etl.impute import (
    add_founder_count,
    create_enrichment_priorities,
    extract_first_sentence,
    impute_oneliner_from_description,
    run_imputation_pipeline,
    validate_imputation,
)


def test_extract_first_sentence_handles_nan_and_non_string():
    assert extract_first_sentence(float("nan")) == ""
    assert extract_first_sentence(None) == ""


def test_extract_first_sentence_handles_empty_and_whitespace():
    assert extract_first_sentence("") == ""
    assert extract_first_sentence("   ") == ""


def test_extract_first_sentence_extracts_normal_sentence():
    text = "We build tools for developers. Second sentence here."
    assert extract_first_sentence(text) == "We build tools for developers."


def test_extract_first_sentence_falls_back_on_short_abbreviation_match():
    # "Acme Inc." is only 9 chars (<=10), so the primary regex match is
    # rejected as a likely abbreviation and the function falls back to
    # splitting on ". " (which discards the period).
    text = "Acme Inc. builds widgets for the widget industry."
    assert extract_first_sentence(text) == "Acme Inc"


def test_extract_first_sentence_returns_whole_short_string_with_no_fallback_split():
    # "Hi." has no trailing whitespace after its period (end of string), so
    # re.split(r"[.!?]\s+", ...) finds no match and returns the original
    # string unchanged.
    assert extract_first_sentence("Hi.") == "Hi."


def test_extract_first_sentence_truncates_at_100_chars_with_no_terminator():
    text = "word " * 30  # 150 chars, no '.', '!', or '?' anywhere
    result = extract_first_sentence(text)
    assert result == text[:100].strip()
    assert len(result) <= 100


def test_impute_oneliner_from_description_imputes_when_description_present():
    companies_df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "slug": ["acme", "beta", "gamma"],
            "oneLiner": ["Existing oneliner", None, None],
            "longDescription": [
                "Acme desc.",
                "Beta builds tools for devs. More text.",
                None,
            ],
        }
    )

    result_df, log = impute_oneliner_from_description(companies_df)

    # Existing oneLiner untouched
    assert result_df.loc[0, "oneLiner"] == "Existing oneliner"
    # Missing oneLiner + present longDescription -> imputed
    assert result_df.loc[1, "oneLiner"] == "Beta builds tools for devs."
    # Missing oneLiner + missing longDescription -> left alone, not even attempted
    assert pd.isna(result_df.loc[2, "oneLiner"])

    assert len(log) == 1
    assert log[0]["company_slug"] == "beta"
    assert log[0]["success"] is True
    assert log[0]["imputed_value"] == "Beta builds tools for devs."


def test_add_founder_count_aggregates_and_zero_fills():
    companies_df = pd.DataFrame({"id": [1, 2, 3], "slug": ["acme", "beta", "gamma"]})
    founders_df = pd.DataFrame({"company_slug": ["acme", "acme", "beta"]})

    result_df, log = add_founder_count(companies_df, founders_df)

    counts = dict(zip(result_df["slug"], result_df["founder_count"]))
    assert counts == {"acme": 2, "beta": 1, "gamma": 0}
    assert result_df["founder_count"].dtype.kind == "i"  # int, not float

    assert len(log) == 1
    assert log[0]["company_slug"] == "gamma"
    assert log[0]["success"] is False


def test_create_enrichment_priorities_scores_and_sorts_descending():
    companies_df = pd.DataFrame(
        {
            "id": [1, 2],
            "slug": ["acme", "beta"],
            "name": ["Acme", "Beta"],
            "status": ["Active", "Inactive"],
            "batch": ["W24", "W10"],
            "oneLiner": [None, "Has oneliner"],
            "longDescription": ["Has desc.", "Has desc."],
            "founder_count": [0, 2],
            "teamSize": [None, 5.0],
        }
    )

    priorities = create_enrichment_priorities(companies_df)

    acme = priorities[priorities["slug"] == "acme"].iloc[0]
    beta = priorities[priorities["slug"] == "beta"].iloc[0]
    # Acme: Active(30) + batch_year 2024>=2020(20) + missing_oneliner(15) + missing_founders(10) = 75
    assert acme["enrichment_score"] == 75
    assert acme["batch_year"] == 2024
    assert acme["missing_oneliner"] == True
    # Beta: Inactive(0) + batch_year 2010, (2010-2000)*1=10 + no missing fields = 10
    assert beta["enrichment_score"] == 10
    assert beta["batch_year"] == 2010

    # Sorted descending by enrichment_score
    assert priorities.iloc[0]["slug"] == "acme"
    assert priorities.iloc[1]["slug"] == "beta"

    assert "yc_url" in priorities.columns
    assert priorities[priorities["slug"] == "acme"]["yc_url"].iloc[0] == (
        "https://www.ycombinator.com/companies/acme"
    )


def test_validate_imputation_passes_on_valid_input():
    companies_df = pd.DataFrame(
        {"id": [1], "oneLiner": ["Existing"], "founder_count": [2]}
    )

    validate_imputation(companies_df, companies_df.copy())  # should not raise


def test_validate_imputation_raises_on_row_count_change():
    original_df = pd.DataFrame(
        {"id": [1, 2], "oneLiner": [None, None], "founder_count": [0, 0]}
    )
    imputed_df = pd.DataFrame({"id": [1], "oneLiner": [None], "founder_count": [0]})

    with pytest.raises(AssertionError, match="Row count"):
        validate_imputation(original_df, imputed_df)


def test_validate_imputation_raises_on_overwritten_oneliner():
    original_df = pd.DataFrame(
        {"id": [1], "oneLiner": ["Existing"], "founder_count": [0]}
    )
    imputed_df = pd.DataFrame(
        {"id": [1], "oneLiner": ["Changed!"], "founder_count": [0]}
    )

    with pytest.raises(AssertionError, match="oneLiners were modified"):
        validate_imputation(original_df, imputed_df)


def test_validate_imputation_raises_on_negative_founder_count():
    original_df = pd.DataFrame(
        {"id": [1], "oneLiner": [None], "founder_count": [0]}
    )
    imputed_df = pd.DataFrame(
        {"id": [1], "oneLiner": [None], "founder_count": [-1]}
    )

    with pytest.raises(AssertionError, match="Negative founder counts"):
        validate_imputation(original_df, imputed_df)


def test_run_imputation_pipeline_respects_input_and_output_dir(tmp_path):
    input_dir = tmp_path / "step1_cleaned"
    output_dir = tmp_path / "step2_imputed"
    input_dir.mkdir()

    pd.DataFrame(
        {
            "id": [1, 2],
            "slug": ["acme", "beta"],
            "name": ["Acme", "Beta"],
            "status": ["Active", "Active"],
            "batch": ["W24", "S23"],
            "teamSize": [5, 3],
            "oneLiner": [None, "Existing"],
            "longDescription": ["Acme builds widgets. More text.", "Beta desc."],
        }
    ).to_csv(input_dir / "companies_cleaned.csv", index=False)
    pd.DataFrame({"company_slug": ["acme"]}).to_csv(
        input_dir / "founders_cleaned.csv", index=False
    )
    for filename in [
        "industries_cleaned.csv",
        "tags_cleaned.csv",
        "schools_cleaned.csv",
        "prior_companies_cleaned.csv",
        "regions_cleaned.csv",
        "badges_cleaned.csv",
    ]:
        pd.DataFrame({"id": [1]}).to_csv(input_dir / filename, index=False)

    run_imputation_pipeline(input_dir=input_dir, output_dir=output_dir)

    assert (output_dir / "companies_imputed.csv").exists()
    assert (output_dir / "imputation_report.csv").exists()
    assert (output_dir / "enrichment_priorities.csv").exists()

    imputed = pd.read_csv(output_dir / "companies_imputed.csv")
    assert len(imputed) == 2
    acme = imputed[imputed["slug"] == "acme"].iloc[0]
    assert acme["oneLiner"] == "Acme builds widgets."
    assert acme["founder_count"] == 1


def test_run_imputation_pipeline_defaults_still_work_with_no_args():
    # Uses the real project-relative input_dir/output_dir defaults — just
    # confirms the function signature still accepts a no-arg call.
    import inspect

    sig = inspect.signature(run_imputation_pipeline)
    assert list(sig.parameters) == ["input_dir", "output_dir"]
    assert sig.parameters["input_dir"].default is None
    assert sig.parameters["output_dir"].default is None
```

- [ ] **Step 2: Run the new test file**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_impute.py -v`
Expected: 15 passed.

- [ ] **Step 3: Run the full test suite to confirm no regressions**

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: all tests pass (114 pre-existing + 15 new = 129).

- [ ] **Step 4: Commit**

```bash
git add tests/test_impute.py
git commit -m "test: add unit test coverage for src/etl/impute.py"
```

---

## Task 2: README.md rewrite

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: real, already-verified facts about the project (Global Constraints), and every command in this task must be run for real during implementation to confirm it works exactly as documented.

- [ ] **Step 1: Verify every command before documenting it**

Run each of these for real and confirm they work as expected (do not skip this — the whole point of this task is a README a newcomer can trust):

```bash
./.venv/Scripts/python.exe -m pytest -v
./.venv/Scripts/python.exe scripts/run_complexity_pipeline.py --steps impute,features,score --output-version v3
./.venv/Scripts/python.exe scripts/generate_complexity_analysis_notebook.py
./.venv/Scripts/python.exe scripts/generate_dashboard.py
```

The third command (`--output-version v3`) is a throwaway verification run — after confirming it works, delete the file it created so no stray `complexity_index_v3.csv` gets committed:

```bash
rm data/processed/scores/complexity_index_v3.csv
git status --porcelain data/processed/scores/
```
Expected after the `rm` + `git status`: no output (the throwaway v3 file was never staged, so removing it leaves nothing to clean up). If `git status` shows anything, stop and investigate before proceeding — do not commit a stray v3 file.

The fourth command (`generate_dashboard.py`) regenerates the real, already-committed `output/complexity_dashboard_v2.html` in place — this is expected and fine (same content, since `complexity_index_v2.csv` hasn't changed), but confirm via `git status --porcelain output/` that it shows either no change or an identical-content overwrite, not something unexpected.

- [ ] **Step 2: Write the new README.md**

Replace the entire contents of `README.md` with:

```markdown
# Y Combinator Complexity Index

A reproducible pipeline that scores 4,844 Y Combinator companies on a 0-100 **Complexity Index**, combining Technical difficulty (building the core technology) and Practical/Market difficulty (executing in the market) into one comparable metric per company.

## What This Measures

Each company gets three scores:
- **`technical_score`** (0-30) — deep-tech tags, R&D-vocabulary in the company description, founder background (PhDs, prior research-institution experience)
- **`practical_score`** (0-70) — regulated industry, market type (B2B/B2C/marketplace), geography & operations
- **`complexity_score`** (0-100) — the sum of the two

The 30/70 split (not 50/50) is a deliberate revision made in Phase 9.5, after diagnostics found that most YC companies carry no deep-tech signal at all — a 50-point technical budget was mostly wasted on zeros for about half the dataset. See [Data Versioning](#data-versioning) and [Known Limitations](#known-limitations--future-work) below, and `documentation/plan_complexity_metric/objectives_and_metrics.md` for the full scoring methodology and success-metric definitions.

## Quickstart

### Prerequisites
- Python 3.12 or higher
- pip (Python package manager)

### Installation

```bash
git clone <repository-url>
cd y-combinator-analysis
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
```

### Run the pipeline

The full pipeline (clean → impute → enrich → features → score) is orchestrated by one CLI:

```bash
# Run everything (enrich is opt-in — see the --steps help text for why)
./.venv/Scripts/python.exe scripts/run_complexity_pipeline.py --steps all --output-version v3

# Or just recompute scores from existing features (fastest — skips scraping/cleaning)
./.venv/Scripts/python.exe scripts/run_complexity_pipeline.py --steps impute,features,score --output-version v3
```

This writes `data/processed/scores/complexity_index_v3.csv`. See [Data Versioning](#data-versioning) for what version number to use.

### Regenerate the analysis notebook

```bash
./.venv/Scripts/python.exe scripts/generate_complexity_analysis_notebook.py
./.venv/Scripts/python.exe -m jupyter nbconvert --to notebook --execute --inplace notebooks/complexity_analysis.ipynb
```

Produces `notebooks/complexity_analysis.ipynb` — score distribution, batch/status/industry breakdowns, a correlation heatmap, team-size correlation, and manual outlier review.

### Regenerate the dashboard

```bash
./.venv/Scripts/python.exe scripts/generate_dashboard.py
```

Produces `output/complexity_dashboard_v2.html` — a single self-contained, offline HTML file (no server needed). Open it directly in a browser. Includes an "About This Index" section, key findings, 6 interactive charts, and a searchable/filterable table of all 4,844 companies.

## Data Versioning

- **`complexity_index_v1.csv`** — the original Phase 7 calibration (50/50 technical/practical split). Preserved as the historical baseline; not the current default.
- **`complexity_index_v2.csv`** — the current default, from the Phase 9.5 rubric revision (30/70 split). This is what `notebooks/complexity_analysis.ipynb` and `output/complexity_dashboard_v2.html` currently analyze.
- To produce a new version, pass `--output-version vN` to `scripts/run_complexity_pipeline.py`. Nothing else is auto-versioned — if you generate a new score version, manually re-point and re-run `scripts/generate_complexity_analysis_notebook.py` / `scripts/generate_dashboard.py` against it if you want updated analysis artifacts (see each script's `SCORES_PATH` constant).

## Project Structure

```
y-combinator-analysis/
├── data/
│   ├── raw/                    # Raw YC CSVs (gitignored, not included)
│   └── processed/
│       ├── step1_cleaned/      # Phase 3 output
│       ├── step2_imputed/      # Phase 4 output
│       ├── step3_enriched/     # Phase 5 output (optional enrichment)
│       ├── features/           # Phase 6 output (complexity_features.parquet)
│       └── scores/             # Phase 7/9.5 output (complexity_index_v1.csv, v2.csv)
├── src/etl/                    # Pipeline modules: clean, impute, enrich, features, score, pipeline
├── scripts/                    # CLI entry points and notebook/dashboard generators
├── notebooks/                  # Jupyter analysis notebooks
├── output/                     # Generated dashboard HTML
├── tests/                      # pytest test suite (129 tests)
├── documentation/plan_complexity_metric/  # Roadmap, objectives & success metrics
├── docs/superpowers/specs/     # Per-phase design specs (full decision history)
└── requirements.txt
```

## Known Limitations & Future Work

- **Team-size correlation is weak.** Even after the Phase 9.5 revision, `complexity_score` correlates with log(team size) at only r=0.103 (Pearson) — up from r=0.035 pre-revision, but still far short of the objectives doc's original r>0.2 target. Diagnostics found no combination of the current 8 features reaches r>0.2; several technical-side features are even *negatively* correlated with team size in this dataset. This target has been formally relaxed rather than further chased — see `docs/superpowers/specs/2026-07-14-phase9.5-rubric-revision-design.md`.
- **Score distribution is narrower than originally targeted.** σ=11.95 after Phase 9.5 (up from σ=10.11), still short of the original σ≥15 target. About half of all companies have zero deep-tech signal (no tags, no R&D-vocabulary keywords, no founder-background indicators) — real "no signal" mass in the data, not a tuning failure. Also formally relaxed rather than further chased.
- **`--steps all` has a known ordering gap** (Phase 8): `DEFAULT_STEPS` excludes `enrich`, but `features` always reads from `enrich`'s output directory (`step3_enriched/`), not `impute`'s. A default `--steps all` run regenerates fresh `impute` output that never reaches the final index unless `enrich` is explicitly included in `--steps`. See `scripts/run_complexity_pipeline.py --help` for the full explanation.
- **A handful of pre-existing NaN `slug` values** (company ids 382, 599, 1189) have been present since Phase 6 — unrelated to scoring, doesn't affect any score column.
- **Possible future work:** investigate the batch-over-time complexity trend observed in Phase 9 (rising from ~19 in the earliest batches to ~34 in the most recent, cause undiagnosed); add features beyond the current 8 that might better predict team size if that correlation is ever revisited.

## Testing

```bash
./.venv/Scripts/python.exe -m pytest -v
```

129 tests covering every `src/etl/` module (clean, impute, enrich, features, score, pipeline) and the dashboard/notebook generator scripts.

## Further Reading

- `documentation/plan_complexity_metric/roadmap.md` — full phase-by-phase project history and status
- `documentation/plan_complexity_metric/objectives_and_metrics.md` — complete scoring methodology, success-metric definitions, and rationale
- `docs/superpowers/specs/` — one design spec per phase, with full decision rationale (including diagnostic investigations behind the Phase 9.5 rubric revision)

## License

This project is for educational and research purposes.
```

- [ ] **Step 3: Confirm the README renders sensibly**

Run: `./.venv/Scripts/python.exe -c "print(open('README.md', encoding='utf-8').read()[:200])"`
Expected: prints the start of the new README content without encoding errors (confirms the file was written with valid UTF-8, including the `→`/`—` characters used in the text).

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README for the Complexity Index project"
```

---

## Task 3: Roadmap update and final verification

**Files:**
- Modify: `documentation/plan_complexity_metric/roadmap.md`

**Interfaces:**
- Consumes: Tasks 1-2's completed work.

- [ ] **Step 1: Mark the Phase 11 checklist item complete**

Find this exact block in `documentation/plan_complexity_metric/roadmap.md`:

```markdown
- [ ] **11. Documentation & reproducibility**
  - [ ] Update main README
  - [ ] Add pipeline usage instructions
  - [ ] Write minimal test suite
  - [ ] Version control all outputs
```

Replace with:

```markdown
- [x] **11. Documentation & reproducibility**
  - [x] Update main README
  - [x] Add pipeline usage instructions
  - [x] Write minimal test suite (added `tests/test_impute.py`, closing the one real coverage gap found)
  - [x] Version control all outputs (already complete — verified `data/processed/` and `output/` are fully tracked, including both v1/v2 score files and dashboards)
```

- [ ] **Step 2: Update the "Detailed Phase Descriptions" section**

Find this exact block:

```markdown
### Phase 11: Documentation

**Updates Required:**
- Main `README.md` - add Complexity Index section
- Pipeline usage guide (including how to run `scripts/generate_dashboard.py`)
- Data versioning conventions
- Known limitations & future work
```

Replace with:

```markdown
### Phase 11: Documentation ✅ COMPLETE

**Deliverables:**
- Rewritten `README.md` — Complexity Index overview, quickstart, data versioning, project structure, known limitations, testing
- `tests/test_impute.py` — closed the one real test-coverage gap (15 new tests, `src/etl/impute.py`'s 6 functions were previously only indirectly covered via mocked pipeline-orchestration tests)
- Confirmed "version control all outputs" was already satisfied (no action needed)

**Why:** `README.md` was still the generic project-scaffold template from before any Complexity Index work started. This phase gives the project a real entry point and closes the project's only remaining test-coverage gap.
```

- [ ] **Step 3: Update the timeline table**

Find:
```markdown
| 11. Documentation | 1 day | 🔲 Not started |
| **Total** | **11-16 days** | **~92% complete** |
```

Replace with:
```markdown
| 11. Documentation | 1 day | ✅ Complete |
| **Total** | **11-16 days** | **100% complete** |
```

- [ ] **Step 4: Update "Next Immediate Actions"**

Find:
```markdown
## Next Immediate Actions

**Current Focus:** Phase 11 - Documentation & Reproducibility (the deferred Phase 9.5 decision is now resolved)

**Next Steps:**
1. Update the main `README.md` with a Complexity Index section, pipeline usage instructions (including how to run `scripts/generate_dashboard.py`, which now defaults to v2, and open `output/complexity_dashboard_v2.html`), a minimal test suite for anything still untested, and version-control notes for all outputs (including the v1/v2 distinction).
2. Output (Phase 11): updated `README.md` + usage docs.

**To continue:** Mark this task complete and proceed to Phase 11.
```

Replace with:
```markdown
## Next Immediate Actions

**Status:** All 11 phases complete. The Complexity Index pipeline, validation analysis, visualization dashboard, and documentation are all done, tested, and versioned.

**Possible future work (not scheduled):**
- Investigate the batch-over-time complexity trend (rising from ~19 in the earliest batches to ~34 in the most recent) — cause undiagnosed.
- Revisit the team-size correlation and score-spread targets if new features become available that might close the gap without gutting the technical dimension.
- Fix the Phase 8 `--steps all` / `enrich` ordering gap if it becomes a real friction point (currently just documented).
```

- [ ] **Step 5: Run the full test suite one final time**

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: all 129 tests pass.

- [ ] **Step 6: Commit**

```bash
git add documentation/plan_complexity_metric/roadmap.md
git commit -m "docs: mark Phase 11 documentation complete, project 100% done"
```

---

## Self-Review Notes

- **Spec coverage:** Decision 1-2 (README rewrite, substantial depth) — Task 2. Decision 3 (impute.py test gap) — Task 1. Decision 4 (Known Limitations content) — Task 2's README section, using the real Phase 9.5/Phase 8/Phase 6 facts verbatim. Decision 5 (Data Versioning content) — Task 2's README section.
- **Type/naming consistency:** `tests/test_impute.py`'s function names and fixture shapes match `impute.py`'s actual signatures exactly (verified by running each function against the plan's exact fixtures before this plan was written — see Global Constraints). The README's documented commands match the actual CLI flags and script paths used throughout Phases 8-10 (`--steps`, `--output-version`, `scripts/generate_complexity_analysis_notebook.py`, `scripts/generate_dashboard.py`).
- **No placeholders:** every test assertion and every README fact is a real, independently-verified value — no `<value>` fill-ins. The one place this plan requires an in-the-moment action (Task 2 Step 1's command verification) is explicit about being a verification step with a real cleanup requirement (deleting the throwaway v3 file), not silently left undone.
- **Known limitation carried forward:** this plan does not touch `scripts/analyze_raw_data.py` or `scripts/todo_cli.py` (explicitly out of scope per the spec) — if either ever needs tests, that's a separate, smaller task, not silently folded in here.
