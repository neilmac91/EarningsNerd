"""ops/excerpts/provenance_count.py: the excerpt builders counted from retained logs, counts only (E28).

The reader takes each UTC day of a bounded window from Cloud Logging and counts the `Excerpt provenance` lines by
source and builder era, the fetches over the size cap and the accessions fetched with no provenance line. These
tests hold it to its header: both payload shapes read; a day it could not read whole is a floor, never zero; a
day before the oldest retained entry reads as gone; and the receipt names no accession, filing, URL or text.
"""
import importlib.util
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[3] / "ops" / "excerpts" / "provenance_count.py"


@pytest.fixture(scope="module")
def count():
    spec = importlib.util.spec_from_file_location("ops_excerpt_provenance_count", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


NATIVE = "0000320193-25-000073"
REGEX = "0001099590-26-000006"
BOTH = "0001628280-26-054342"
FETCHED_ONLY = "000114036126015366"


def provenance_line(source, accession, *, json_payload=True, stamp="2026-10-10T12:00:00Z"):
    record = {"schema_version": 1, "accession": accession, "source": source, "excerpt_chars": 10,
              "excerpt_sha256": "a" * 64, "supplied_sections": [], "coverage_status": "observed_partial"}
    text = "Excerpt provenance: " + json.dumps(record, sort_keys=True)
    if json_payload:
        return {"timestamp": stamp, "jsonPayload": {"message": text, "level": "INFO"}}
    return {"timestamp": stamp, "textPayload": f"[{stamp}] INFO     [-] app.services - {text}"}


def fetch_lines(filing_id, accession_digits, length, stamp="2026-10-10T12:00:00Z"):
    url = f"https://www.sec.gov/Archives/edgar/data/1140361/{accession_digits}/doc.htm"
    return [
        {"timestamp": stamp, "jsonPayload": {"message": f"[stream:{filing_id}] Starting SEC fetch for URL: {url}"}},
        {"timestamp": stamp, "jsonPayload": {"message": f"[stream:{filing_id}] SEC fetch completed. Text length: {length}"}},
    ]


def test_the_window_is_cut_into_utc_days_bounded_and_past(count):
    assert count.days("2026-10-04T09:29:00Z", "2026-10-06T00:00:00Z") == [
        ("2026-10-04T09:29:00Z", "2026-10-05T00:00:00Z"), ("2026-10-05T00:00:00Z", "2026-10-06T00:00:00Z")]
    future = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for start, end in (("2026-10-06T00:00:00Z", "2026-10-04T00:00:00Z"), ("2026-10-01T00:00:00Z", future),
                       ("2026-08-01T00:00:00Z", "2026-10-01T00:00:00Z"), ("2026-10-01", "2026-10-02T00:00:00Z")):
        with pytest.raises(ValueError):
            count.days(start, end)


def test_the_filter_reads_both_payload_shapes_in_the_services_scope(count):
    text = count.day_filter("2026-10-10T00:00:00Z", "2026-10-11T00:00:00Z")
    for line in ("Excerpt provenance:", "SEC fetch completed. Text length:", "Starting SEC fetch for URL:"):
        assert f'textPayload:"{line}"' in text and f'jsonPayload.message:"{line}"' in text
    assert '"earningsnerd-backend" OR "earningsnerd-task-worker"' in text and 'resource.type="cloud_run_job"' in text
    assert 'timestamp>="2026-10-10T00:00:00Z" AND timestamp<"2026-10-11T00:00:00Z"' in text


def test_counts_each_source_era_cap_and_fetch_without_provenance_and_names_none(count):
    day = {"start": "2026-10-10T00:00:00Z", "state": "complete", "entries": [
        provenance_line("edgartools", NATIVE, stamp="2026-10-02T08:00:00Z"),
        provenance_line("regex_fallback", REGEX, json_payload=False, stamp="2026-10-06T03:00:00Z"),
        provenance_line("regex_fallback", REGEX, stamp="2026-10-10T03:00:00Z"),  # the same accession again
        provenance_line("edgartools", BOTH, stamp="2026-10-03T00:00:00Z"),
        provenance_line("regex_fallback", BOTH, stamp="2026-10-09T00:00:00Z"),
        provenance_line("legacy_cached_excerpt", NATIVE, stamp="2026-10-12T00:00:00Z"),
        {"timestamp": "2026-10-10T00:00:00Z", "jsonPayload": {"message": "Excerpt provenance: {not json"}},
        *fetch_lines(41, FETCHED_ONLY, 16_000_001),
        *fetch_lines(42, NATIVE.replace("-", ""), 900_000),
    ]}
    report = count.tally([day])
    assert report["days"] == [{"day": "2026-10-10", "state": "complete", "fetches": 2, "over_size_cap_filings": 1,
                               "lines": {"edgartools": 2, "legacy_cached_excerpt": 1, "regex_fallback": 3,
                                         "unreadable": 1},
                               "accessions": {"edgartools": 2, "legacy_cached_excerpt": 1, "regex_fallback": 2}}]
    eras = report["accessions_by_source_and_era"]
    assert eras["edgartools"] == {"before": 2, "onset": 0, "window": 0, "after": 0}
    assert eras["regex_fallback"] == {"before": 0, "onset": 1, "window": 2, "after": 0}
    assert eras["legacy_cached_excerpt"]["window"] == 1
    assert report["accessions_native_and_regex"] == 1
    # The onset CI could not bound: the first regex line after the last native report, a timestamp alone.
    assert report["first_regex_fallback_after_last_native_report"] == "2026-10-06T03:00:00Z"
    assert report["accessions_fetched_without_provenance"] == 1
    printed = json.dumps(report)
    for name in (NATIVE, REGEX, BOTH, FETCHED_ONLY, NATIVE.replace("-", ""), "stream:41", "sec.gov"):
        assert name not in printed
    assert not re.search(r"\d{10}-\d{2}-\d{6}|\d{18}", printed)


class FakeApi:
    """The capacity readout's Api shape: request() for one page, pages() for a paged read."""

    def __init__(self, oldest, days):
        self.oldest, self.days, self.filters = oldest, days, []

    def request(self, url, params, post=False):
        assert params["pageSize"] == 1 and params["orderBy"] == "timestamp asc"
        if self.oldest == "denied":
            return None, "http_403"
        return {"entries": [{"timestamp": self.oldest}] if self.oldest else []}, None

    def pages(self, url, params, key, *, post=False):
        self.filters.append(params["filter"])
        day = re.search(r'timestamp>="([^"]+)"', params["filter"]).group(1)[:10]
        return self.days.get(day, {"state": "complete", "items": []})


def test_a_day_gone_from_the_logs_reads_as_gone_and_a_short_read_as_a_floor(count):
    api = FakeApi("2026-10-05T06:00:00Z", {
        "2026-10-06": {"state": "partial", "error": "page_limit", "items": [provenance_line("regex_fallback", REGEX)]},
        "2026-10-07": {"state": "unavailable", "error": "http_503", "items": []},
    })
    report = count.collect(api, "earnings-nerd", "2026-10-04T00:00:00Z", "2026-10-08T00:00:00Z")
    assert [(day["day"], day["state"], day.get("error")) for day in report["days"]] == [
        ("2026-10-04", "expired_or_absent", None),
        ("2026-10-05", "partly_expired", None),
        ("2026-10-06", "partial", "page_limit"),
        ("2026-10-07", "unavailable", "http_503"),
    ]
    assert len(api.filters) == 3  # the gone day is not read
    assert report["earliest_retained"] == {"state": "complete", "timestamp": "2026-10-05T06:00:00Z"}
    assert "floor" in report["counts_basis"]


def test_an_unreadable_retention_probe_marks_nothing_gone_and_nothing_retained_marks_everything(count):
    report = count.collect(FakeApi("denied", {}), "earnings-nerd", "2026-10-04T00:00:00Z", "2026-10-06T00:00:00Z")
    assert report["earliest_retained"] == {"state": "unavailable", "error": "http_403", "timestamp": None}
    assert {day["state"] for day in report["days"]} == {"complete"}
    report = count.collect(FakeApi(None, {}), "earnings-nerd", "2026-10-04T00:00:00Z", "2026-10-06T00:00:00Z")
    assert {day["state"] for day in report["days"]} == {"expired_or_absent"}


def test_the_project_and_the_window_are_checked_before_any_read(count):
    with pytest.raises(ValueError):
        count.collect(FakeApi(None, {}), "bad project", "2026-10-04T00:00:00Z", "2026-10-06T00:00:00Z")
    assert count.main(["--start", "2026-10-04T00:00:00Z", "--end", "2026-10-06T00:00:00Z", "--validate-only"]) == 0
