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


import pandas as pd

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


from src.etl.enrich import RATE_LIMIT_SECONDS


def _write_enrichment_inputs(input_dir, companies_df, founders_df, priorities_df):
    input_dir.mkdir(parents=True, exist_ok=True)
    companies_df.to_csv(input_dir / "companies_imputed.csv", index=False)
    founders_df.to_csv(input_dir / "founders_imputed.csv", index=False)
    priorities_df.to_csv(input_dir / "enrichment_priorities.csv", index=False)
    for name in ["industries", "tags", "schools", "prior_companies", "regions", "badges"]:
        pd.DataFrame({"company_slug": []}).to_csv(
            input_dir / f"{name}_imputed.csv", index=False
        )


def test_run_enrichment_pipeline_sleeps_between_but_not_after_multiple_targets(tmp_path):
    input_dir = tmp_path / "step2_imputed"
    output_dir = tmp_path / "step3_enriched"
    cache_dir = tmp_path / "enrichment_cache"

    companies = pd.DataFrame(
        [
            {"id": 1, "slug": "eps", "name": "Eps", "oneLiner": None,
             "longDescription": None, "teamSize": float("nan"), "founder_count": 0},
            {"id": 2, "slug": "zeta", "name": "Zeta", "oneLiner": None,
             "longDescription": None, "teamSize": float("nan"), "founder_count": 0},
        ]
    )
    founders = pd.DataFrame(
        columns=["first_name", "last_name", "hnid", "avatar_thumb",
                 "current_company", "current_title", "company_slug", "top_company"]
    )
    priorities = pd.DataFrame(
        [
            {"id": 1, "slug": "eps", "name": "Eps", "enrichment_score": 90,
             "missing_oneliner": True, "missing_description": True,
             "missing_founders": True, "missing_teamsize": True,
             "yc_url": "https://www.ycombinator.com/companies/eps"},
            {"id": 2, "slug": "zeta", "name": "Zeta", "enrichment_score": 85,
             "missing_oneliner": True, "missing_description": True,
             "missing_founders": True, "missing_teamsize": True,
             "yc_url": "https://www.ycombinator.com/companies/zeta"},
        ]
    )
    _write_enrichment_inputs(input_dir, companies, founders, priorities)

    def fake_fetch(url):
        return {
            "one_liner": "A one liner.",
            "long_description": "A longer description.",
            "team_size": 5,
            "founders": [],
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

    # 2 targets -> exactly 1 inter-request sleep, never a trailing sleep after the last one.
    assert sleep_calls == [RATE_LIMIT_SECONDS]


def test_run_enrichment_pipeline_fetch_failure_does_not_abort_batch(tmp_path):
    input_dir = tmp_path / "step2_imputed"
    output_dir = tmp_path / "step3_enriched"
    cache_dir = tmp_path / "enrichment_cache"

    companies = pd.DataFrame(
        [
            {
                "id": 1,
                "slug": "gamma",
                "name": "Gamma",
                "oneLiner": "Existing one liner",
                "longDescription": "Existing description",
                "teamSize": 5.0,
                "founder_count": 0,
            },
            {
                "id": 2,
                "slug": "delta",
                "name": "Delta",
                "oneLiner": None,
                "longDescription": None,
                "teamSize": float("nan"),
                "founder_count": 0,
            },
        ]
    )
    founders = pd.DataFrame(
        columns=["first_name", "last_name", "hnid", "avatar_thumb",
                 "current_company", "current_title", "company_slug", "top_company"]
    )
    priorities = pd.DataFrame(
        [
            # gamma is targeted ONLY because it's missing founders - all other fields
            # are already filled, so a fetch failure should log just one failed row.
            {"id": 1, "slug": "gamma", "name": "Gamma", "enrichment_score": 95,
             "missing_oneliner": False, "missing_description": False,
             "missing_founders": True, "missing_teamsize": False,
             "yc_url": "https://www.ycombinator.com/companies/gamma"},
            {"id": 2, "slug": "delta", "name": "Delta", "enrichment_score": 85,
             "missing_oneliner": True, "missing_description": True,
             "missing_founders": True, "missing_teamsize": True,
             "yc_url": "https://www.ycombinator.com/companies/delta"},
        ]
    )
    _write_enrichment_inputs(input_dir, companies, founders, priorities)

    def fake_fetch(url):
        if "gamma" in url:
            raise RuntimeError("simulated network failure")
        return {
            "one_liner": "Delta does things.",
            "long_description": "Delta is a company for things.",
            "team_size": 10,
            "founders": [{"full_name": "Dana Founder", "title": "CEO",
                          "avatar_thumb_url": None}],
        }

    run_enrichment_pipeline(
        input_dir=input_dir,
        output_dir=output_dir,
        cache_dir=cache_dir,
        score_threshold=80,
        fetch_fn=fake_fetch,
        sleep_fn=lambda s: None,
    )

    # Pipeline completed and wrote all outputs rather than crashing mid-batch.
    assert (output_dir / "companies_enriched.csv").exists()
    assert (output_dir / "founders_enriched.csv").exists()
    assert (output_dir / "enrichment_report.csv").exists()

    enriched_companies = pd.read_csv(output_dir / "companies_enriched.csv")

    # gamma: fetch failed, so nothing changed and founder_count stays 0.
    gamma = enriched_companies[enriched_companies["slug"] == "gamma"].iloc[0]
    assert gamma["oneLiner"] == "Existing one liner"
    assert gamma["longDescription"] == "Existing description"
    assert gamma["teamSize"] == 5.0
    assert gamma["founder_count"] == 0

    # delta: the batch continued past gamma's failure and delta was fully enriched.
    delta = enriched_companies[enriched_companies["slug"] == "delta"].iloc[0]
    assert delta["oneLiner"] == "Delta does things."
    assert delta["longDescription"] == "Delta is a company for things."
    assert delta["teamSize"] == 10
    assert delta["founder_count"] == 1

    report = pd.read_csv(output_dir / "enrichment_report.csv")

    # gamma was only ever targeted for "founders" - the failure-path report must not
    # invent failed rows for oneLiner/longDescription/teamSize, which were never missing.
    gamma_rows = report[report["company_slug"] == "gamma"]
    assert len(gamma_rows) == 1
    assert gamma_rows.iloc[0]["field"] == "founders"
    assert gamma_rows.iloc[0]["success"] == False

    delta_rows = report[report["company_slug"] == "delta"]
    assert len(delta_rows) == 4
    assert delta_rows["success"].all()


def test_run_enrichment_pipeline_resets_stale_founder_count_with_no_matching_rows(tmp_path):
    input_dir = tmp_path / "step2_imputed"
    output_dir = tmp_path / "step3_enriched"
    cache_dir = tmp_path / "enrichment_cache"

    companies = pd.DataFrame(
        [
            {
                "id": 1,
                "slug": "stale",
                "name": "Stale Co",
                "oneLiner": "Has one",
                "longDescription": "Has description",
                "teamSize": 8.0,
                "founder_count": 5,  # stale value, no backing rows in founders_imputed.csv
            },
            {
                "id": 2,
                "slug": "eta",
                "name": "Eta",
                "oneLiner": None,
                "longDescription": None,
                "teamSize": float("nan"),
                "founder_count": 0,
            },
        ]
    )
    # No rows for "stale" (or anyone) - "stale" has zero matching founder rows.
    founders = pd.DataFrame(
        columns=["first_name", "last_name", "hnid", "avatar_thumb",
                 "current_company", "current_title", "company_slug", "top_company"]
    )
    priorities = pd.DataFrame(
        [
            # "stale" is below threshold and never scraped, but its founder_count must
            # still be recomputed from founders_df (source of truth) on every run,
            # not merely carried forward as-is.
            {"id": 1, "slug": "stale", "name": "Stale Co", "enrichment_score": 10,
             "missing_oneliner": False, "missing_description": False,
             "missing_founders": False, "missing_teamsize": False,
             "yc_url": "https://www.ycombinator.com/companies/stale"},
            {"id": 2, "slug": "eta", "name": "Eta", "enrichment_score": 90,
             "missing_oneliner": True, "missing_description": True,
             "missing_founders": True, "missing_teamsize": True,
             "yc_url": "https://www.ycombinator.com/companies/eta"},
        ]
    )
    _write_enrichment_inputs(input_dir, companies, founders, priorities)

    def fake_fetch(url):
        assert "eta" in url
        return {
            "one_liner": "Eta does things.",
            "long_description": "Eta is a company for things.",
            "team_size": 6,
            "founders": [{"full_name": "Erin Founder", "title": "CEO",
                          "avatar_thumb_url": None}],
        }

    run_enrichment_pipeline(
        input_dir=input_dir,
        output_dir=output_dir,
        cache_dir=cache_dir,
        score_threshold=80,
        fetch_fn=fake_fetch,
        sleep_fn=lambda s: None,
    )

    enriched_companies = pd.read_csv(output_dir / "companies_enriched.csv")

    # The buggy `.fillna(companies_df["founder_count"])` formula would have kept this
    # at 5 (its stale input value). The fixed `.fillna(0)` formula correctly recomputes
    # it from founders_df, where "stale" has zero matching rows, so it must come out 0.
    stale = enriched_companies[enriched_companies["slug"] == "stale"].iloc[0]
    assert stale["founder_count"] == 0

    eta = enriched_companies[enriched_companies["slug"] == "eta"].iloc[0]
    assert eta["founder_count"] == 1
