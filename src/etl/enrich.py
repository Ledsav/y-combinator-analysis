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
