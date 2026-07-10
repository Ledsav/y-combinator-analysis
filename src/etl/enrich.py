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
from pathlib import Path
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
    parts = full_name.split()
    if len(parts) == 0:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


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
        success = not pd.isna(value) and value != ""
        if success:
            updated[local_field] = value
        report_rows.append({"field": local_field, "success": success})
    return updated, report_rows


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
    targeted_field_flags = [
        ("oneLiner", "missing_oneliner"),
        ("longDescription", "missing_description"),
        ("teamSize", "missing_teamsize"),
    ]
    for i, target in enumerate(target_list):
        company_id = target.id
        slug = target.slug
        url = target.yc_url
        print(f"  ({i + 1}/{len(target_list)}) {slug} ...")

        try:
            scraped = fetch_fn(url)

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
        except Exception as e:
            print(f"    FAILED: {e}")
            for local_field, flag_name in targeted_field_flags:
                if bool(getattr(target, flag_name)):
                    report_rows.append(
                        {
                            "company_id": company_id,
                            "company_slug": slug,
                            "field": local_field,
                            "method": "yc_page_scrape",
                            "success": False,
                            "source_url": url,
                        }
                    )
            if bool(target.missing_founders):
                report_rows.append(
                    {
                        "company_id": company_id,
                        "company_slug": slug,
                        "field": "founders",
                        "method": "yc_page_scrape",
                        "success": False,
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
        companies_df["_new_founder_count"].fillna(0).astype(int)
    )
    companies_df.drop(columns=["company_slug", "_new_founder_count"], inplace=True)

    companies_df.to_csv(output_dir / "companies_enriched.csv", index=False)
    print(f"  [OK] {output_dir / 'companies_enriched.csv'}")
    founders_df.to_csv(output_dir / "founders_enriched.csv", index=False)
    print(f"  [OK] {output_dir / 'founders_enriched.csv'}")

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
        print(f"  [OK] {dst}")

    report_df = pd.DataFrame(report_rows)
    report_df.to_csv(output_dir / "enrichment_report.csv", index=False)
    print(f"  [OK] {output_dir / 'enrichment_report.csv'}")

    print("\n" + "=" * 60)
    print("PHASE 5 COMPLETE")
    print("=" * 60)
    print(f"Companies attempted: {len(target_list)}")
    if len(report_df):
        print(f"Fields successfully filled: {report_df['success'].sum()}/{len(report_df)}")


if __name__ == "__main__":
    run_enrichment_pipeline()
