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
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple

import pandas as pd


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
        company = data["props"]["company"]
    except (KeyError, TypeError) as e:
        raise ValueError("data-page JSON missing props.company") from e
    if not isinstance(company, dict):
        raise ValueError("props.company is not an object")
    return company


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
    network errors (timeout, 5xx). Does not retry on 404/other 4xx errors,
    nor on malformed/missing page JSON (extract_company_json's ValueError),
    since those are permanent failures that a retry won't fix.

    Args:
        url: Full YC company page URL.
        max_retries: Number of retries after the first attempt.

    Returns:
        The parsed `props.company` dict.

    Raises:
        RuntimeError: if all fetch attempts fail, wrapping the last exception.
        ValueError: propagated immediately if the fetched page's JSON is
            malformed or missing expected fields (not retried).
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
        except (urllib.error.URLError, TimeoutError) as e:
            last_error = e
        if attempt < max_retries:
            time.sleep(1)
    raise RuntimeError(f"Failed to fetch {url}: {last_error}") from last_error


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
