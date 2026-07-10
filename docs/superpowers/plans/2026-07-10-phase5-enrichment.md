# Phase 5 Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `src/etl/enrich.py`, a Phase 5 enrichment module that scrapes YC's own company pages for the 21 highest-priority companies (`enrichment_score >= 80`) to fill missing `oneLiner`, `longDescription`, `teamSize`, and founder data, then writes `data/processed/step3_enriched/`.

**Architecture:** Pure parsing/merging functions (unit-testable without network access) + a thin network-fetch layer (`urllib.request`) + an orchestrator (`run_enrichment_pipeline`) that wires them together, following the existing `src/etl/impute.py` pattern (module-level functions, `if __name__ == "__main__"` entry point, print-based progress logging, `validate_*` assertion function before writing outputs).

**Tech Stack:** Python stdlib (`urllib.request`, `html.parser`, `json`, `time`) + `pandas` (already a dependency). New dev dependency: `pytest` (project currently has no test suite or test runner).

## Global Constraints

- Never overwrite a non-null existing value when merging scraped data — only fill fields that are currently missing (spec: "Merge scraped values ... only where the field was originally missing").
- Rate limit: 6 seconds between requests (10 req/min), per `documentation/plan_complexity_metric/phase5_enrichment_design.md`.
- Request timeout: 15s. Retry up to 2 times on timeout/5xx only — never retry 404 or other 4xx (permanent failures).
- Scrape target: `enrichment_score >= 80` from `data/processed/step2_imputed/enrichment_priorities.csv` (parameterized via `score_threshold`, default `80` — not hardcoded to the current 21-company count).
- Raw scraped JSON cached per company to `data/raw/enrichment_cache/<slug>.json` (already gitignored via `data/raw/*.json`).
- Outputs written to `data/processed/step3_enriched/` (already gitignored via `data/processed/*.csv`).
- No new runtime dependencies beyond `pandas` (already present) — the scraper itself uses stdlib only.

---

## Task 1: Project test setup + `data-page` JSON extraction

**Files:**
- Create: `conftest.py` (project root)
- Create: `tests/__init__.py` (empty)
- Create: `tests/test_enrich.py`
- Create: `src/etl/enrich.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `extract_company_json(html_text: str) -> dict` — raises `ValueError` on missing/malformed data.

- [ ] **Step 1: Add pytest to the venv and requirements.txt**

Run: `./.venv/Scripts/pip.exe install pytest`

Then edit `requirements.txt` to:
```
pandas
numpy
pytest
```

- [ ] **Step 2: Create `conftest.py` at the project root**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
```

This guarantees `from src.etl.enrich import ...` resolves regardless of how pytest is invoked, since `src/` is a package (`src/__init__.py` already exists).

- [ ] **Step 3: Create empty `tests/__init__.py`**

Empty file — makes `tests` a package so pytest's rootdir insertion behaves consistently.

- [ ] **Step 4: Write the failing test for `extract_company_json`**

Create `tests/test_enrich.py`:

```python
import json

import pytest

from src.etl.enrich import extract_company_json


SAMPLE_PAGE_TEMPLATE = """
<html><body>
<div id="app" data-page="{data_page}"></div>
</body></html>
"""


def _wrap_data_page(company: dict) -> str:
    payload = json.dumps({"props": {"company": company}})
    escaped = (
        payload.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return SAMPLE_PAGE_TEMPLATE.format(data_page=escaped)


def test_extract_company_json_returns_company_dict():
    company = {
        "id": 240,
        "slug": "stripe",
        "one_liner": "Economic infrastructure for the internet.",
        "long_description": "Stripe builds economic infrastructure.",
        "team_size": 7000,
        "founders": [{"full_name": "Patrick Collison", "title": "Founder/CEO"}],
    }
    html_text = _wrap_data_page(company)

    result = extract_company_json(html_text)

    assert result == company


def test_extract_company_json_raises_when_no_data_page_attribute():
    with pytest.raises(ValueError, match="No data-page attribute found"):
        extract_company_json("<html><body>no data here</body></html>")


def test_extract_company_json_raises_on_malformed_json():
    html_text = '<div data-page="{not valid json"></div>'
    with pytest.raises(ValueError, match="Malformed data-page JSON"):
        extract_company_json(html_text)


def test_extract_company_json_raises_when_props_company_missing():
    html_text = '<div data-page="{&quot;props&quot;:{}}"></div>'
    with pytest.raises(ValueError, match="missing props.company"):
        extract_company_json(html_text)
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_enrich.py -v`
Expected: `ModuleNotFoundError: No module named 'src.etl.enrich'` (module doesn't exist yet) or collection error.

- [ ] **Step 6: Implement `extract_company_json` in `src/etl/enrich.py`**

```python
"""
Data Enrichment Module for Y Combinator Analysis
Phase 5: Scrape YC company pages for the highest-priority companies with
missing critical fields (oneLiner, longDescription, teamSize, founders).

Strategy:
- Fetch each target company's YC page (ycombinator.com/companies/<slug>)
- Parse the embedded Inertia.js `data-page` JSON blob (no HTML scraping heuristics)
- Fill only currently-missing fields (oneLiner, longDescription, teamSize)
- Append founder rows for companies missing founder data
- Cache raw scraped JSON per company for reproducibility
"""

import json
from html.parser import HTMLParser
from typing import Dict, Optional


class _DataPageParser(HTMLParser):
    """Extracts the `data-page` attribute value from the first matching tag."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.data_page: Optional[str] = None

    def handle_starttag(self, tag, attrs):
        if self.data_page is not None:
            return
        attr_dict = dict(attrs)
        if "data-page" in attr_dict:
            self.data_page = attr_dict["data-page"]


def extract_company_json(html_text: str) -> Dict:
    """
    Parse the Inertia.js `data-page` JSON blob out of a YC company page's HTML
    and return the `props.company` dict.

    Args:
        html_text: Raw HTML of a ycombinator.com/companies/<slug> page.

    Returns:
        The `props.company` dict (one_liner, long_description, team_size,
        founders, tags, etc.)

    Raises:
        ValueError: if no data-page attribute is found, the JSON is malformed,
            or props.company is missing.
    """
    parser = _DataPageParser()
    parser.feed(html_text)
    if parser.data_page is None:
        raise ValueError("No data-page attribute found in HTML")
    try:
        data = json.loads(parser.data_page)
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed data-page JSON: {e}") from e
    try:
        return data["props"]["company"]
    except (KeyError, TypeError) as e:
        raise ValueError("data-page JSON missing props.company") from e
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_enrich.py -v`
Expected: 4 passed

- [ ] **Step 8: Commit**

```bash
git add conftest.py tests/__init__.py tests/test_enrich.py src/etl/enrich.py requirements.txt
git commit -m "feat: add data-page JSON extraction for YC company pages"
```

---

## Task 2: Network fetch with rate-limit-friendly retry

**Files:**
- Modify: `src/etl/enrich.py`
- Modify: `tests/test_enrich.py`

**Interfaces:**
- Consumes: `extract_company_json(html_text: str) -> dict` (Task 1)
- Produces:
  - `fetch_company_page(url: str) -> str`
  - `fetch_company_json(url: str, max_retries: int = MAX_RETRIES) -> dict` — raises `RuntimeError` if all attempts fail
  - Constants: `RATE_LIMIT_SECONDS = 6.0`, `REQUEST_TIMEOUT = 15`, `MAX_RETRIES = 2`, `USER_AGENT`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_enrich.py`:

```python
import urllib.error

from src.etl.enrich import fetch_company_json


def test_fetch_company_json_retries_on_timeout_then_succeeds(monkeypatch):
    calls = []

    def fake_fetch_company_page(url):
        calls.append(url)
        if len(calls) < 2:
            raise TimeoutError("timed out")
        return "<div data-page='{}'></div>".replace(
            "{}", '{&quot;props&quot;:{&quot;company&quot;:{&quot;slug&quot;:&quot;x&quot;}}}'
        )

    monkeypatch.setattr(
        "src.etl.enrich.fetch_company_page", fake_fetch_company_page
    )
    monkeypatch.setattr("src.etl.enrich.time.sleep", lambda s: None)

    result = fetch_company_json("https://example.com/companies/x")

    assert result == {"slug": "x"}
    assert len(calls) == 2


def test_fetch_company_json_does_not_retry_404(monkeypatch):
    calls = []

    def fake_fetch_company_page(url):
        calls.append(url)
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    monkeypatch.setattr(
        "src.etl.enrich.fetch_company_page", fake_fetch_company_page
    )
    monkeypatch.setattr("src.etl.enrich.time.sleep", lambda s: None)

    with pytest.raises(RuntimeError):
        fetch_company_json("https://example.com/companies/missing")

    assert len(calls) == 1


def test_fetch_company_json_gives_up_after_max_retries(monkeypatch):
    calls = []

    def fake_fetch_company_page(url):
        calls.append(url)
        raise TimeoutError("timed out")

    monkeypatch.setattr(
        "src.etl.enrich.fetch_company_page", fake_fetch_company_page
    )
    monkeypatch.setattr("src.etl.enrich.time.sleep", lambda s: None)

    with pytest.raises(RuntimeError):
        fetch_company_json("https://example.com/companies/x", max_retries=2)

    assert len(calls) == 3  # initial attempt + 2 retries
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_enrich.py -v`
Expected: `ImportError: cannot import name 'fetch_company_json'`

- [ ] **Step 3: Implement the fetch layer**

Add to `src/etl/enrich.py` (after the imports, add `time`, `urllib.error`, `urllib.request`; after `extract_company_json`, add):

```python
import time
import urllib.error
import urllib.request

RATE_LIMIT_SECONDS = 6.0  # 10 requests/minute
REQUEST_TIMEOUT = 15
MAX_RETRIES = 2
USER_AGENT = "Mozilla/5.0 (compatible; YC-Complexity-Research/1.0)"


def fetch_company_page(url: str) -> str:
    """Fetch raw HTML for a YC company page."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
        return response.read().decode("utf-8", errors="ignore")


def fetch_company_json(url: str, max_retries: int = MAX_RETRIES) -> Dict:
    """
    Fetch and parse a YC company page's JSON data, retrying on transient
    errors (timeout, 5xx). Does not retry on 404 or other 4xx errors.

    Args:
        url: Full YC company page URL.
        max_retries: Number of retries after the first attempt.

    Returns:
        The parsed `props.company` dict.

    Raises:
        RuntimeError: if all attempts fail, wrapping the last exception.
    """
    last_error: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            html_text = fetch_company_page(url)
            return extract_company_json(html_text)
        except urllib.error.HTTPError as e:
            last_error = e
            if e.code < 500:
                break  # permanent failure (404, etc.) - don't retry
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            last_error = e
        if attempt < max_retries:
            time.sleep(1)
    raise RuntimeError(f"Failed to fetch {url}: {last_error}") from last_error
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_enrich.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/etl/enrich.py tests/test_enrich.py
git commit -m "feat: add rate-limit-aware fetch with retry for YC pages"
```

---

## Task 3: Field merging and founder-row building

**Files:**
- Modify: `src/etl/enrich.py`
- Modify: `tests/test_enrich.py`

**Interfaces:**
- Produces:
  - `split_full_name(full_name: str) -> Tuple[str, str]`
  - `build_founder_row(scraped_founder: dict, company_slug: str) -> dict` — keys: `first_name, last_name, hnid, avatar_thumb, current_company, current_title, company_slug, top_company`
  - `merge_company_fields(company_row: dict, scraped: dict) -> Tuple[dict, List[dict]]` — report rows have keys `field, success`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_enrich.py`:

```python
import math

from src.etl.enrich import build_founder_row, merge_company_fields, split_full_name


def test_split_full_name_splits_on_first_space():
    assert split_full_name("Patrick Collison") == ("Patrick", "Collison")


def test_split_full_name_handles_single_name():
    assert split_full_name("Madonna") == ("Madonna", "")


def test_split_full_name_handles_middle_names():
    assert split_full_name("Mary Jane Watson") == ("Mary", "Jane Watson")


def test_build_founder_row_maps_scraped_fields():
    scraped_founder = {
        "full_name": "Patrick Collison",
        "title": "Founder/CEO",
        "avatar_thumb_url": "https://example.com/avatar.jpg",
    }

    row = build_founder_row(scraped_founder, "stripe")

    assert row == {
        "first_name": "Patrick",
        "last_name": "Collison",
        "hnid": None,
        "avatar_thumb": "https://example.com/avatar.jpg",
        "current_company": None,
        "current_title": "Founder/CEO",
        "company_slug": "stripe",
        "top_company": False,
    }


def test_merge_company_fields_fills_missing_fields_only():
    company_row = {
        "id": 1,
        "oneLiner": math.nan,
        "longDescription": math.nan,
        "teamSize": math.nan,
    }
    scraped = {
        "one_liner": "A one liner.",
        "long_description": "A longer description.",
        "team_size": 12,
    }

    updated, report_rows = merge_company_fields(company_row, scraped)

    assert updated["oneLiner"] == "A one liner."
    assert updated["longDescription"] == "A longer description."
    assert updated["teamSize"] == 12
    assert {r["field"]: r["success"] for r in report_rows} == {
        "oneLiner": True,
        "longDescription": True,
        "teamSize": True,
    }


def test_merge_company_fields_never_overwrites_existing_value():
    company_row = {
        "id": 1,
        "oneLiner": "Existing one liner.",
        "longDescription": math.nan,
        "teamSize": 5,
    }
    scraped = {
        "one_liner": "Scraped one liner.",
        "long_description": "Scraped description.",
        "team_size": 12,
    }

    updated, report_rows = merge_company_fields(company_row, scraped)

    assert updated["oneLiner"] == "Existing one liner."
    assert updated["teamSize"] == 5
    assert updated["longDescription"] == "Scraped description."
    fields_reported = {r["field"] for r in report_rows}
    assert fields_reported == {"longDescription"}


def test_merge_company_fields_reports_failure_when_scraped_value_missing():
    company_row = {"id": 1, "oneLiner": math.nan, "longDescription": "x", "teamSize": 5}
    scraped = {"one_liner": None}

    updated, report_rows = merge_company_fields(company_row, scraped)

    assert math.isnan(updated["oneLiner"]) or updated["oneLiner"] is None
    assert report_rows == [{"field": "oneLiner", "success": False}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_enrich.py -v`
Expected: `ImportError: cannot import name 'split_full_name'`

- [ ] **Step 3: Implement the merge functions**

Add to `src/etl/enrich.py` (add `Tuple, List` to the `typing` import, add `pandas as pd` import):

```python
from typing import Dict, List, Optional, Tuple

import pandas as pd
```

```python
def split_full_name(full_name: str) -> Tuple[str, str]:
    """Split a scraped founder's full name into (first_name, last_name) on the first space."""
    parts = full_name.strip().split(" ", 1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def build_founder_row(scraped_founder: Dict, company_slug: str) -> Dict:
    """Build a founders_enriched.csv row from a scraped founder dict."""
    first_name, last_name = split_full_name(scraped_founder.get("full_name", ""))
    return {
        "first_name": first_name,
        "last_name": last_name,
        "hnid": None,
        "avatar_thumb": scraped_founder.get("avatar_thumb_url"),
        "current_company": None,
        "current_title": scraped_founder.get("title"),
        "company_slug": company_slug,
        "top_company": False,
    }


def merge_company_fields(company_row: Dict, scraped: Dict) -> Tuple[Dict, List[Dict]]:
    """
    Fill missing oneLiner/longDescription/teamSize on a company row from
    scraped data. Never overwrites a non-null existing value.

    Args:
        company_row: A single company's data as a dict (e.g. from a
            DataFrame row's .to_dict()).
        scraped: The `props.company` dict from `extract_company_json`.

    Returns:
        (updated_row, report_rows) where report_rows is a list of
        {"field": str, "success": bool} for each field that was missing
        and attempted.
    """
    updated = dict(company_row)
    report_rows = []
    field_map = [
        ("oneLiner", "one_liner"),
        ("longDescription", "long_description"),
        ("teamSize", "team_size"),
    ]
    for local_field, scraped_field in field_map:
        if not pd.isna(updated.get(local_field)):
            continue
        value = scraped.get(scraped_field)
        success = value is not None and value != ""
        if success:
            updated[local_field] = value
        report_rows.append({"field": local_field, "success": success})
    return updated, report_rows
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_enrich.py -v`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add src/etl/enrich.py tests/test_enrich.py
git commit -m "feat: add field-merge and founder-row builder for enrichment"
```

---

## Task 4: Validation function

**Files:**
- Modify: `src/etl/enrich.py`
- Modify: `tests/test_enrich.py`

**Interfaces:**
- Consumes: nothing new
- Produces: `validate_enrichment(original_df: pd.DataFrame, enriched_df: pd.DataFrame) -> None` — raises `AssertionError` on row-count mismatch or overwritten existing value; prints a success message otherwise.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_enrich.py`:

```python
import pandas as pd
import pytest

from src.etl.enrich import validate_enrichment


def test_validate_enrichment_passes_when_only_missing_fields_filled():
    original = pd.DataFrame(
        {
            "id": [1, 2],
            "oneLiner": ["Existing", None],
            "longDescription": [None, "Existing desc"],
            "teamSize": [5.0, float("nan")],
        }
    )
    enriched = pd.DataFrame(
        {
            "id": [1, 2],
            "oneLiner": ["Existing", "Filled in"],
            "longDescription": ["Filled in desc", "Existing desc"],
            "teamSize": [5.0, 10.0],
        }
    )

    validate_enrichment(original, enriched)  # should not raise


def test_validate_enrichment_raises_on_row_count_mismatch():
    original = pd.DataFrame({"id": [1, 2], "oneLiner": ["a", "b"],
                              "longDescription": ["a", "b"], "teamSize": [1.0, 2.0]})
    enriched = pd.DataFrame({"id": [1], "oneLiner": ["a"],
                              "longDescription": ["a"], "teamSize": [1.0]})

    with pytest.raises(AssertionError, match="Row count"):
        validate_enrichment(original, enriched)


def test_validate_enrichment_raises_when_existing_value_overwritten():
    original = pd.DataFrame({"id": [1], "oneLiner": ["Existing"],
                              "longDescription": ["Existing"], "teamSize": [5.0]})
    enriched = pd.DataFrame({"id": [1], "oneLiner": ["Changed!"],
                              "longDescription": ["Existing"], "teamSize": [5.0]})

    with pytest.raises(AssertionError, match="oneLiner"):
        validate_enrichment(original, enriched)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_enrich.py -v`
Expected: `ImportError: cannot import name 'validate_enrichment'`

- [ ] **Step 3: Implement `validate_enrichment`**

Add to `src/etl/enrich.py`:

```python
def validate_enrichment(original_df: pd.DataFrame, enriched_df: pd.DataFrame) -> None:
    """
    Validate that enrichment didn't corrupt data.

    Args:
        original_df: companies_imputed.csv loaded as a DataFrame, before enrichment.
        enriched_df: The enriched companies DataFrame, same row order.
    """
    assert len(original_df) == len(enriched_df), "Row count changed during enrichment!"

    for field in ("oneLiner", "longDescription", "teamSize"):
        had_value = original_df[field].notna().reset_index(drop=True)
        original_values = original_df[field].reset_index(drop=True)
        enriched_values = enriched_df[field].reset_index(drop=True)
        assert (
            original_values[had_value] == enriched_values[had_value]
        ).all(), f"Existing {field} values were modified!"

    print("Validation passed: No data corruption detected")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_enrich.py -v`
Expected: 16 passed

- [ ] **Step 5: Commit**

```bash
git add src/etl/enrich.py tests/test_enrich.py
git commit -m "feat: add enrichment validation function"
```

---

## Task 5: Pipeline orchestrator

**Files:**
- Modify: `src/etl/enrich.py`
- Modify: `tests/test_enrich.py`

**Interfaces:**
- Consumes: `fetch_company_json`, `merge_company_fields`, `build_founder_row`, `validate_enrichment` (Tasks 1-4)
- Produces: `run_enrichment_pipeline(input_dir=None, output_dir=None, cache_dir=None, score_threshold=80, fetch_fn=fetch_company_json, sleep_fn=time.sleep) -> None`

- [ ] **Step 1: Write the failing integration test**

Append to `tests/test_enrich.py`:

```python
import json as json_module

from src.etl.enrich import run_enrichment_pipeline


def test_run_enrichment_pipeline_end_to_end(tmp_path):
    input_dir = tmp_path / "step2_imputed"
    output_dir = tmp_path / "step3_enriched"
    cache_dir = tmp_path / "enrichment_cache"
    input_dir.mkdir()

    companies = pd.DataFrame(
        [
            {
                "id": 1,
                "slug": "acme",
                "name": "Acme",
                "oneLiner": None,
                "longDescription": None,
                "teamSize": float("nan"),
                "founder_count": 0,
            },
            {
                "id": 2,
                "slug": "beta",
                "name": "Beta",
                "oneLiner": "Already has one",
                "longDescription": "Already has a description",
                "teamSize": 3.0,
                "founder_count": 1,
            },
        ]
    )
    founders = pd.DataFrame(
        [{"first_name": "Bea", "last_name": "Founder", "hnid": "1", "avatar_thumb": None,
          "current_company": None, "current_title": None, "company_slug": "beta",
          "top_company": False}]
    )
    priorities = pd.DataFrame(
        [
            {"id": 1, "slug": "acme", "name": "Acme", "enrichment_score": 90,
             "missing_oneliner": True, "missing_description": True,
             "missing_founders": True, "missing_teamsize": True,
             "yc_url": "https://www.ycombinator.com/companies/acme"},
            {"id": 2, "slug": "beta", "name": "Beta", "enrichment_score": 20,
             "missing_oneliner": False, "missing_description": False,
             "missing_founders": False, "missing_teamsize": False,
             "yc_url": "https://www.ycombinator.com/companies/beta"},
        ]
    )
    companies.to_csv(input_dir / "companies_imputed.csv", index=False)
    founders.to_csv(input_dir / "founders_imputed.csv", index=False)
    priorities.to_csv(input_dir / "enrichment_priorities.csv", index=False)
    for name in ["industries", "tags", "schools", "prior_companies", "regions", "badges"]:
        pd.DataFrame({"company_slug": []}).to_csv(
            input_dir / f"{name}_imputed.csv", index=False
        )

    def fake_fetch(url):
        assert "acme" in url
        return {
            "one_liner": "Acme makes everything.",
            "long_description": "Acme is a company that makes everything you need.",
            "team_size": 42,
            "founders": [{"full_name": "Ada Founder", "title": "CEO",
                          "avatar_thumb_url": "https://example.com/a.jpg"}],
        }

    sleep_calls = []

    run_enrichment_pipeline(
        input_dir=input_dir,
        output_dir=output_dir,
        cache_dir=cache_dir,
        score_threshold=80,
        fetch_fn=fake_fetch,
        sleep_fn=sleep_calls.append,
    )

    enriched_companies = pd.read_csv(output_dir / "companies_enriched.csv")
    acme = enriched_companies[enriched_companies["slug"] == "acme"].iloc[0]
    assert acme["oneLiner"] == "Acme makes everything."
    assert acme["teamSize"] == 42
    assert acme["founder_count"] == 1

    beta = enriched_companies[enriched_companies["slug"] == "beta"].iloc[0]
    assert beta["oneLiner"] == "Already has one"  # untouched, below threshold

    enriched_founders = pd.read_csv(output_dir / "founders_enriched.csv")
    assert "Ada" in enriched_founders["first_name"].values

    report = pd.read_csv(output_dir / "enrichment_report.csv")
    assert (report["company_slug"] == "acme").all()
    assert report["success"].all()

    cache_file = cache_dir / "acme.json"
    assert cache_file.exists()
    cached = json_module.loads(cache_file.read_text(encoding="utf-8"))
    assert cached["team_size"] == 42

    assert sleep_calls == []  # only one target company - no inter-request sleep needed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_enrich.py -v`
Expected: `ImportError: cannot import name 'run_enrichment_pipeline'`

- [ ] **Step 3: Implement `run_enrichment_pipeline`**

Add to `src/etl/enrich.py` (add `from pathlib import Path` to imports):

```python
from pathlib import Path


def run_enrichment_pipeline(
    input_dir: Path = None,
    output_dir: Path = None,
    cache_dir: Path = None,
    score_threshold: int = 80,
    fetch_fn=fetch_company_json,
    sleep_fn=time.sleep,
) -> None:
    """
    Main enrichment pipeline orchestrator.

    Args:
        input_dir: Path to step2_imputed/ directory.
        output_dir: Path to step3_enriched/ directory.
        cache_dir: Path to the raw scraped-JSON cache directory.
        score_threshold: Minimum enrichment_score to target for scraping.
        fetch_fn: Injectable fetch function (url) -> company dict, defaults
            to the real network fetcher. Overridden in tests.
        sleep_fn: Injectable sleep function, defaults to time.sleep.
            Overridden in tests to avoid real waits.
    """
    if input_dir is None:
        input_dir = (
            Path(__file__).resolve().parents[2] / "data" / "processed" / "step2_imputed"
        )
    if output_dir is None:
        output_dir = (
            Path(__file__).resolve().parents[2] / "data" / "processed" / "step3_enriched"
        )
    if cache_dir is None:
        cache_dir = Path(__file__).resolve().parents[2] / "data" / "raw" / "enrichment_cache"

    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("PHASE 5: DATA ENRICHMENT")
    print("=" * 60)

    print("\n[1/5] Loading imputed data...")
    companies_df = pd.read_csv(input_dir / "companies_imputed.csv")
    founders_df = pd.read_csv(input_dir / "founders_imputed.csv")
    priorities_df = pd.read_csv(input_dir / "enrichment_priorities.csv")
    original_companies = companies_df.copy()

    targets = priorities_df[priorities_df["enrichment_score"] >= score_threshold]
    print(f"Targeting {len(targets)} companies with enrichment_score >= {score_threshold}")

    companies_df = companies_df.set_index("id", drop=False)

    report_rows = []
    new_founder_rows = []

    print("\n[2/5] Scraping target companies...")
    target_list = list(targets.itertuples())
    for i, target in enumerate(target_list):
        company_id = target.id
        slug = target.slug
        url = target.yc_url
        print(f"  ({i + 1}/{len(target_list)}) {slug} ...")

        try:
            scraped = fetch_fn(url)
        except Exception as e:
            print(f"    FAILED: {e}")
            for field in ("oneLiner", "longDescription", "teamSize", "founders"):
                report_rows.append(
                    {
                        "company_id": company_id,
                        "company_slug": slug,
                        "field": field,
                        "method": "yc_page_scrape",
                        "success": False,
                        "source_url": url,
                    }
                )
            if i < len(target_list) - 1:
                sleep_fn(RATE_LIMIT_SECONDS)
            continue

        cache_path = cache_dir / f"{slug}.json"
        cache_path.write_text(json.dumps(scraped, indent=2), encoding="utf-8")

        company_row = companies_df.loc[company_id].to_dict()
        updated_row, field_reports = merge_company_fields(company_row, scraped)
        for r in field_reports:
            report_rows.append(
                {
                    "company_id": company_id,
                    "company_slug": slug,
                    "field": r["field"],
                    "method": "yc_page_scrape",
                    "success": r["success"],
                    "source_url": url,
                }
            )
        for col, val in updated_row.items():
            companies_df.loc[company_id, col] = val

        if bool(target.missing_founders):
            scraped_founders = scraped.get("founders") or []
            for f in scraped_founders:
                new_founder_rows.append(build_founder_row(f, slug))
            report_rows.append(
                {
                    "company_id": company_id,
                    "company_slug": slug,
                    "field": "founders",
                    "method": "yc_page_scrape",
                    "success": len(scraped_founders) > 0,
                    "source_url": url,
                }
            )

        if i < len(target_list) - 1:
            sleep_fn(RATE_LIMIT_SECONDS)

    companies_df = companies_df.reset_index(drop=True)

    print("\n[3/5] Validating enrichment...")
    validate_enrichment(original_companies, companies_df)

    print("\n[4/5] Merging founders and writing outputs...")
    if new_founder_rows:
        founders_df = pd.concat(
            [founders_df, pd.DataFrame(new_founder_rows)], ignore_index=True
        )

    founder_counts = (
        founders_df.groupby("company_slug").size().reset_index(name="_new_founder_count")
    )
    companies_df = companies_df.merge(
        founder_counts, left_on="slug", right_on="company_slug", how="left"
    )
    companies_df["founder_count"] = (
        companies_df["_new_founder_count"]
        .fillna(companies_df["founder_count"])
        .astype(int)
    )
    companies_df.drop(columns=["company_slug", "_new_founder_count"], inplace=True)

    companies_df.to_csv(output_dir / "companies_enriched.csv", index=False)
    print(f"  ✓ {output_dir / 'companies_enriched.csv'}")
    founders_df.to_csv(output_dir / "founders_enriched.csv", index=False)
    print(f"  ✓ {output_dir / 'founders_enriched.csv'}")

    for filename in [
        "industries_imputed.csv",
        "tags_imputed.csv",
        "schools_imputed.csv",
        "prior_companies_imputed.csv",
        "regions_imputed.csv",
        "badges_imputed.csv",
    ]:
        src = input_dir / filename
        dst = output_dir / filename.replace("_imputed", "_enriched")
        pd.read_csv(src).to_csv(dst, index=False)
        print(f"  ✓ {dst}")

    report_df = pd.DataFrame(report_rows)
    report_df.to_csv(output_dir / "enrichment_report.csv", index=False)
    print(f"  ✓ {output_dir / 'enrichment_report.csv'}")

    print("\n" + "=" * 60)
    print("PHASE 5 COMPLETE")
    print("=" * 60)
    print(f"Companies attempted: {len(target_list)}")
    if len(report_df):
        print(f"Fields successfully filled: {report_df['success'].sum()}/{len(report_df)}")


if __name__ == "__main__":
    run_enrichment_pipeline()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_enrich.py -v`
Expected: 17 passed

- [ ] **Step 5: Commit**

```bash
git add src/etl/enrich.py tests/test_enrich.py
git commit -m "feat: add Phase 5 enrichment pipeline orchestrator"
```

---

## Task 6: Real run against the 21 target companies + roadmap updates

**Files:**
- Modify: `documentation/plan_complexity_metric/roadmap.md`
- Modify: `documentation/plan/roadmap_todo.md`
- Create (generated by running the pipeline, not hand-written): `data/processed/step3_enriched/*.csv`, `data/raw/enrichment_cache/*.json`

**Interfaces:**
- Consumes: `run_enrichment_pipeline()` (Task 5), run with real network access (no `fetch_fn`/`sleep_fn` override).

- [ ] **Step 1: Run the full test suite once more before the real run**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_enrich.py -v`
Expected: 17 passed

- [ ] **Step 2: Run the pipeline for real**

Run: `./.venv/Scripts/python.exe -m src.etl.enrich`

Expected: Console output showing `PHASE 5: DATA ENRICHMENT`, 21 companies processed one by one with ~6s between requests (~2 minutes total), ending with `PHASE 5 COMPLETE` and a success/total field count.

- [ ] **Step 3: Inspect the enrichment report**

Run: `./.venv/Scripts/python.exe -c "import pandas as pd; df = pd.read_csv('data/processed/step3_enriched/enrichment_report.csv'); print(df['success'].value_counts()); print(df[~df['success']])"`

Confirm the failure count is small and inspect which companies/fields failed (dead slug, no founders listed on the page, etc. are all acceptable outcomes — just verify nothing crashed silently).

- [ ] **Step 4: Spot-check 2-3 companies against the live page**

Pick 2-3 slugs from `data/processed/step3_enriched/companies_enriched.csv` where `oneLiner`/`longDescription` were filled, open `https://www.ycombinator.com/companies/<slug>` and confirm the filled values match what's shown on the page.

- [ ] **Step 5: Confirm the raw cache was written**

Run: `./.venv/Scripts/python.exe -c "import pathlib; print(list(pathlib.Path('data/raw/enrichment_cache').glob('*.json'))[:5])"`

Expected: a list of `.json` file paths, one per successfully scraped company.

- [ ] **Step 6: Update `documentation/plan_complexity_metric/roadmap.md`**

Change the checklist item 5 block:
```markdown
- [x] **5. Data enrichment (optional)**
  - [x] Define enrichment strategy & scope
  - [x] Implement web scraping (rate-limited)
  - [x] Store raw enrichment logs
  - [x] Output: `data/processed/step3_enriched/`
```

Update the timeline table row:
```markdown
| 5. Enrichment | 2-7 days | ✅ Complete (scoped to score>=80) |
```
and the total-complete percentage to `50% complete`.

Update "Next Immediate Actions":
```markdown
## Next Immediate Actions

**Current Focus:** Phase 6 - Feature Engineering

**Next Steps:**
1. Extract technical/practical complexity features per the Phase 6 spec above, using `data/processed/step3_enriched/` as input
2. Output to `data/processed/features/complexity_features.parquet`
3. Update checklist item #6 accordingly

**To continue:** Mark this task complete and proceed to implementation.
```

- [ ] **Step 7: Update `documentation/plan/roadmap_todo.md`**

```markdown
- [x] 5. Scraping & enrichment
```

- [ ] **Step 8: Commit**

```bash
git add documentation/plan_complexity_metric/roadmap.md documentation/plan/roadmap_todo.md documentation/plan_complexity_metric/phase5_enrichment_design.md docs/superpowers/plans/2026-07-10-phase5-enrichment.md
git add data/processed/step3_enriched/*.csv
git commit -m "feat: complete Phase 5 - scrape 21 highest-priority companies"
```

Note: `data/raw/enrichment_cache/*.json` is gitignored (matches `data/raw/*.json`) and intentionally not committed — it's a local reproducibility cache, not versioned data.

---

## Self-Review Notes

- **Spec coverage:** rate limit (Task 2/5), retry policy (Task 2), robots.txt-compliant target (single-page fetch, no query-string URLs used anywhere), never-overwrite rule (Task 3, tested), raw JSON caching (Task 5), founders merge (Task 3/5), report log (Task 5), validation (Task 4), manual spot-check (Task 6) — all covered.
- **Type consistency:** `fetch_fn` signature `(url: str) -> dict` matches between `fetch_company_json` (Task 2) and its use/override in `run_enrichment_pipeline` (Task 5) and the integration test (Task 5). `merge_company_fields` return shape `(dict, List[{"field", "success"}])` is consistent between Task 3's definition and Task 5's consumption.
- **No placeholders:** all steps contain complete, runnable code.
