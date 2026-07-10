import json
import urllib.error

import pytest

from src.etl.enrich import extract_company_json, fetch_company_json


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


def test_fetch_company_json_retries_on_5xx_then_succeeds(monkeypatch):
    calls = []

    def fake_fetch_company_page(url):
        calls.append(url)
        if len(calls) < 2:
            raise urllib.error.HTTPError(url, 500, "Server Error", {}, None)
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


def test_fetch_company_json_does_not_retry_malformed_page(monkeypatch):
    calls = []

    def fake_fetch_company_page(url):
        calls.append(url)
        return "<html><body>no data-page here</body></html>"

    monkeypatch.setattr(
        "src.etl.enrich.fetch_company_page", fake_fetch_company_page
    )
    monkeypatch.setattr("src.etl.enrich.time.sleep", lambda s: None)

    with pytest.raises(ValueError):
        fetch_company_json("https://example.com/companies/x")

    assert len(calls) == 1


import math

from src.etl.enrich import build_founder_row, merge_company_fields, split_full_name


def test_split_full_name_splits_on_first_space():
    assert split_full_name("Patrick Collison") == ("Patrick", "Collison")


def test_split_full_name_handles_single_name():
    assert split_full_name("Madonna") == ("Madonna", "")


def test_split_full_name_handles_middle_names():
    assert split_full_name("Mary Jane Watson") == ("Mary", "Jane Watson")


def test_split_full_name_collapses_internal_whitespace():
    assert split_full_name("Patrick  Collison") == ("Patrick", "Collison")


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
        "longDescription": "Existing long description.",
        "teamSize": 5,
    }
    scraped = {
        "one_liner": "Scraped one liner.",
        "long_description": "Scraped description.",
        "team_size": 12,
    }

    updated, report_rows = merge_company_fields(company_row, scraped)

    assert updated["oneLiner"] == "Existing one liner."
    assert updated["longDescription"] == "Existing long description."
    assert updated["teamSize"] == 5
    assert report_rows == []


def test_merge_company_fields_reports_failure_when_scraped_value_missing():
    company_row = {"id": 1, "oneLiner": math.nan, "longDescription": "x", "teamSize": 5}
    scraped = {"one_liner": None}

    updated, report_rows = merge_company_fields(company_row, scraped)

    assert math.isnan(updated["oneLiner"]) or updated["oneLiner"] is None
    assert report_rows == [{"field": "oneLiner", "success": False}]


def test_merge_company_fields_reports_failure_when_scraped_value_is_nan():
    company_row = {"id": 1, "oneLiner": math.nan, "longDescription": "x", "teamSize": 5}
    scraped = {"one_liner": math.nan}

    updated, report_rows = merge_company_fields(company_row, scraped)

    assert math.isnan(updated["oneLiner"]) or updated["oneLiner"] is None
    assert report_rows == [{"field": "oneLiner", "success": False}]
