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


def test_extract_company_json_raises_when_props_company_is_not_a_dict():
    html_text = '<div data-page="{&quot;props&quot;:{&quot;company&quot;:null}}"></div>'
    with pytest.raises(ValueError):
        extract_company_json(html_text)
