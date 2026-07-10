# Phase 5: Data Enrichment — Design

**Date:** 2026-07-10
**Status:** Approved
**Scope:** Companies with `enrichment_score >= 80` in `data/processed/step2_imputed/enrichment_priorities.csv` (21 companies as of this writing)

---

## Context

The roadmap (`roadmap.md`) marks Phase 5 (web scraping enrichment) as optional, with scope left as an open decision ("TBD based on Phase 4 results"). Phase 4's output (`enrichment_priorities.csv`) ranks all 4,844 companies by an `enrichment_score` (0-100) reflecting status, batch recency, and which critical fields (`oneLiner`, `longDescription`, founders, `teamSize`) are missing.

Decision: scrape only the highest-priority tier (`enrichment_score >= 80`, 21 companies) rather than the full medium+ tier (3,554 companies, ~6 hours at the roadmap's 10 req/min rate limit). This validates the enrichment approach end-to-end on the companies where it matters most, without a long-running scrape job.

Investigation confirmed YC's individual company pages (`ycombinator.com/companies/<slug>`, no query string) are:
- Allowed by `robots.txt` (only `/companies?*` with query params is disallowed)
- Server-rendered with a clean embedded JSON blob (Inertia.js `data-page` attribute) containing `one_liner`, `long_description`, `team_size`, `founders[]` (`full_name`, `title`, `avatar_thumb_url`), `tags`, `location`, etc.
- Parseable with the Python stdlib alone (`urllib.request` + `html.parser.HTMLParser` + `json`) — no new dependencies required.

## Architecture

New module: `src/etl/enrich.py`, following the existing pattern in `src/etl/clean.py` and `src/etl/impute.py` (small pure functions + a `run_enrichment_pipeline()` orchestrator, runnable via `if __name__ == "__main__"`).

## Data Flow

1. Load `data/processed/step2_imputed/enrichment_priorities.csv` and `companies_imputed.csv`; filter priorities to `enrichment_score >= 80`.
2. For each target company, GET its `yc_url`:
   - Throttle to 10 req/min (sleep 6s between requests)
   - 15s request timeout, up to 2 retries on transient failure (timeout/5xx)
   - Extract the `data-page` attribute via `HTMLParser`, `json.loads` it, read `data['props']['company']`
3. Cache the parsed company JSON blob per company to `data/raw/enrichment_cache/<slug>.json` (gitignored — matches the existing `data/raw/*.json` gitignore pattern; this is the "raw enrichment log" the roadmap calls for)
4. Merge scraped values into a copy of `companies_imputed.csv`, **only filling fields that are currently null/missing** — never overwrite existing data (same conservative rule as `impute.py`):
   - `oneLiner` ← `one_liner` (only if missing)
   - `longDescription` ← `long_description` (only if missing)
   - `teamSize` ← `team_size` (only if missing)
   - Write result to `data/processed/step3_enriched/companies_enriched.csv`
5. For companies with `missing_founders == True`, append rows to a copy of `founders_imputed.csv`:
   - `full_name` split into `first_name`/`last_name` (split on first whitespace)
   - `title` → `current_title`
   - `avatar_thumb_url` → `avatar_thumb`
   - `company_slug` set to the company's slug
   - `hnid`, `current_company`, `top_company` left null/`False` (not available from this source)
   - Write result to `data/processed/step3_enriched/founders_enriched.csv`
   - Recompute `founder_count` on the enriched companies table for affected rows
6. Copy through the remaining unchanged step2 files into `step3_enriched/` (same copy-through pattern `impute.py` uses for files it doesn't touch).
7. Write `data/processed/step3_enriched/enrichment_report.csv` logging one row per (company, field) attempt: `company_id, company_slug, field, method="yc_page_scrape", success, source_url`.

## Error Handling

- HTTP error (404, non-200), timeout after retries, or malformed/missing `data-page` JSON → log as a failed row in `enrichment_report.csv` for that company (all fields), skip to the next company. Never abort the batch over one failure.
- No retries on 404 (permanent); retries only on timeout/5xx (transient).

## Validation

- Row-count preservation on `companies_enriched.csv` vs `companies_imputed.csv` (same assertion style as `validate_imputation` in `impute.py`).
- Assert no previously non-null `oneLiner`/`longDescription`/`teamSize` value was changed.
- Print a summary: companies attempted, succeeded, failed, fields filled.

## Testing / Verification

Manual run against the 21 target companies:
- Check `enrichment_report.csv` success count
- Spot-check 2-3 companies' `companies_enriched.csv` rows against the live YC page
- Confirm gitignored raw cache files were written under `data/raw/enrichment_cache/`

## Out of Scope

- The remaining ~3,533 medium-priority companies (can be re-run later by widening the `enrichment_score` filter — the pipeline is not hardcoded to 21, just to the `>= 80` threshold, so scope can change via a parameter later without a redesign).
- Any field not present in the YC page JSON (e.g., deeper R&D/patent signals) — that remains Phase 6's job via NLP on `longDescription`.
