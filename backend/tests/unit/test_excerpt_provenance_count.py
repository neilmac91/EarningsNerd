"""ops/excerpts/provenance_count.py: the excerpt builders counted from retained logs, counts only (E28).

The reader takes each UTC day of a bounded window from Cloud Logging and counts the `Excerpt provenance` lines by
class, over E28 (b)'s window and the whole read, with the fetches over the size cap joined to what their runs
logged. These tests hold it to its header with the API's real answer shapes (an empty result is `{}`, a slow
search may answer with a token alone): retention fails closed, never as a complete day of zeros; schema 2's
unavailable builds and fallback reasons are their own; a regex line bounds no onset; and the receipt names no
accession, filing, URL or exact time.
"""
import importlib.util
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[3] / "ops" / "excerpts" / "provenance_count.py"
NOW = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def count():
    spec = importlib.util.spec_from_file_location("ops_excerpt_provenance_count", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


NATIVE = "0000320193-25-000073"
REGEX = "0001099590-26-000006"
BOTH = "0001628280-26-054342"
CAPPED = "0001140361-26-015366"
FETCHED_ONLY = "0000950170-26-000101"


def provenance_line(source, accession, stamp, *, json_payload=True, **schema_two):
    record = {"schema_version": 2 if schema_two else 1, "accession": accession, "source": source,
              "excerpt_chars": 10, "excerpt_sha256": "a" * 64, "supplied_sections": [], **schema_two}
    text = "Excerpt provenance: " + json.dumps(record, sort_keys=True)
    if json_payload:
        return {"timestamp": stamp, "jsonPayload": {"message": text, "level": "INFO"}}
    return {"timestamp": stamp, "textPayload": f"[{stamp}] INFO     [-] app.services - {text}"}


def fetch_lines(filing_id, accession, length, stamp):
    url = f"https://www.sec.gov/Archives/edgar/data/1140361/{accession.replace('-', '')}/doc.htm"
    return [
        {"timestamp": stamp, "jsonPayload": {"message": f"[stream:{filing_id}] Starting SEC fetch for URL: {url}"}},
        {"timestamp": stamp, "jsonPayload": {"message": f"[stream:{filing_id}] SEC fetch completed. Text length: {length}"}},
    ]


def day(start, entries, state="complete"):
    return {"start": datetime.fromisoformat(start).replace(tzinfo=timezone.utc), "state": state, "entries": entries}


class FakeLogging:
    """Logging's answers by request: the bucket (a GET), the one-entry retention probe, and each day's pages."""

    def __init__(self, *, bucket=None, probe=({},), days=None):
        self.bucket, self.probe, self.days, self.calls = bucket, list(probe), days or {}, []

    def call(self, url, body=None):
        self.calls.append(body["filter"] if body else url)
        if body is None:
            return (self.bucket, None) if self.bucket else (None, "http_403")
        if body["pageSize"] == 1:
            answer = self.probe.pop(0) if self.probe else {}
            return (None, answer) if isinstance(answer, str) else (answer, None)
        first = re.search(r'timestamp>="([^"]+)"', body["filter"]).group(1)[:10]
        answer = self.days.get(first, {})
        return (None, answer) if isinstance(answer, str) else (answer, None)


def test_the_window_is_cut_into_utc_days_bounded_and_past(count):
    assert [(a.isoformat(), b.isoformat()) for a, b in count.days("2026-10-04T09:29:00Z", "2026-10-06T00:00:00Z")] == [
        ("2026-10-04T09:29:00+00:00", "2026-10-05T00:00:00+00:00"),
        ("2026-10-05T00:00:00+00:00", "2026-10-06T00:00:00+00:00")]
    future = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for start, end in (("2026-10-06T00:00:00Z", "2026-10-04T00:00:00Z"), ("2026-10-01T00:00:00Z", future),
                       ("2026-08-01T00:00:00Z", "2026-10-01T00:00:00Z"), ("2026-10-01", "2026-10-02T00:00:00Z")):
        with pytest.raises(ValueError):
            count.days(start, end)


def test_the_filter_reads_both_payload_shapes_in_the_services_scope(count):
    start, end = datetime(2026, 10, 10, tzinfo=timezone.utc), datetime(2026, 10, 11, tzinfo=timezone.utc)
    text = count.day_filter(start, end)
    for line in ("Excerpt provenance:", "SEC fetch completed. Text length:", "Starting SEC fetch for URL:"):
        assert f'textPayload:"{line}"' in text and f'jsonPayload.message:"{line}"' in text
    assert '"earningsnerd-backend" OR "earningsnerd-task-worker"' in text and 'resource.type="cloud_run_job"' in text
    assert 'timestamp>="2026-10-10T00:00:00Z" AND timestamp<"2026-10-11T00:00:00Z"' in text


def test_a_timestamp_reads_to_the_microsecond_so_a_mark_falls_where_it_should(count):
    moment = count.parse_timestamp("2026-10-04T09:28:59.999999999Z")
    assert count.era(moment) == "before"
    assert count.era(count.parse_timestamp("2026-10-04T09:29:00.000001Z")) == "onset"
    assert count.parse_timestamp("2026-10-04T11:29:00+02:00") == datetime(2026, 10, 4, 9, 29, tzinfo=timezone.utc)
    assert count.parse_timestamp("yesterday") is None


def test_counts_each_class_window_reason_and_cap_and_names_none(count):
    entries = [
        provenance_line("edgartools", NATIVE, "2026-10-02T08:00:00Z"),
        provenance_line("edgartools", BOTH, "2026-10-05T07:41:12.5Z"),  # native still worked after the last report
        provenance_line("regex_fallback", REGEX, "2026-10-04T09:35:00Z", json_payload=False),  # a 6-K, say
        provenance_line("regex_fallback", REGEX, "2026-10-10T03:00:00Z"),  # the same accession again
        provenance_line("regex_fallback", BOTH, "2026-10-09T00:00:00Z", outcome="fallback",
                        fallback_reason="sections_not_supplied"),
        provenance_line("regex_fallback", FETCHED_ONLY.replace("0101", "0102"), "2026-10-12T00:00:00Z",
                        outcome="unavailable", fallback_reason="sections_not_supplied"),
        provenance_line("legacy_cached_excerpt", NATIVE, "2026-10-12T00:00:00Z"),
        provenance_line("somewhere_new", NATIVE, "2026-10-12T00:00:00Z"),
        {"timestamp": "2026-10-10T00:00:00Z", "jsonPayload": {"message": "Excerpt provenance: {not json"}},
        {"timestamp": "2026-10-10T00:00:00Z", "jsonPayload": {"message": "[stream:9] Starting SEC fetch for URL: x"}},
        *fetch_lines(41, CAPPED, 16_000_001, "2026-10-20T00:00:00Z"),
        provenance_line("regex_fallback", CAPPED, "2026-10-20T00:00:01Z"),
        *fetch_lines(42, NATIVE, 900_000, "2026-10-12T00:00:00Z"),
        *fetch_lines(43, FETCHED_ONLY, 17_000_000, "2026-10-21T00:00:00Z"),
    ]
    report = count.tally([day("2026-10-10T00:00:00", entries)])
    [only] = report["days"]
    assert only["lines"] == {"edgartools": 2, "legacy_cached_excerpt": 1, "other": 1, "regex_fallback": 4,
                             "unavailable": 1, "unreadable": 1}
    assert (only["fetches"], only["over_size_cap_fetches"], only["unmatched"]) == (3, 2, 1)
    window = report["e28_window"]
    assert window["accessions"]["regex_fallback"] == 2 and window["accessions"]["edgartools"] == 1
    assert window["accessions"]["unavailable"] == 1
    assert window["accessions_by_fallback_reason"] == {"regex_fallback": {"sections_not_supplied": 1},
                                                      "unavailable": {"sections_not_supplied": 1}}
    # The onset's bound is the last native line in the window, to its minute; a regex line bounds nothing.
    assert report["last_native_line_in_e28_window"] == "2026-10-05T07:41Z"
    assert report["accessions_by_era"]["regex_fallback"] == {"before": 0, "onset": 1, "window": 2, "after": 1}
    assert report["accessions_native_and_regex"] == 1
    assert report["size_cap"] == {"over_cap_filings_unnamed": 0, "over_cap_accessions": 2, "size_cap_fallback": 1,
                                  "stored_excerpt_reused": 0, "native": 0, "none_logged": 1}
    assert report["accessions_fetched_without_provenance"] == 1


def test_a_cut_day_leaves_fetches_without_provenance_unknown(count):
    report = count.tally([day("2026-10-10T00:00:00", fetch_lines(41, CAPPED, 10, "2026-10-10T00:00:00Z"),
                              state="partial")])
    assert report["accessions_fetched_without_provenance"] is None


def test_the_buckets_retention_dates_what_is_gone(count):
    # Retention of 30 days on 28 October: the 28th of September is the first day kept, in part.
    api = FakeLogging(bucket={"retentionDays": 30},
                      days={"2026-09-28": {"entries": [provenance_line("edgartools", NATIVE, "2026-09-28T20:00:00Z")]},
                            "2026-09-29": {"nextPageToken": "t1", "entries": []}, })
    report = count.collect(api, "earnings-nerd", "2026-09-26T00:00:00Z", "2026-09-30T00:00:00Z", now=NOW)
    assert [(d["day"], d["state"]) for d in report["days"]] == [
        ("2026-09-26", "expired"), ("2026-09-27", "expired"), ("2026-09-28", "partly_expired"),
        ("2026-09-29", "partial")]
    assert report["retention"]["bucket"] == {"state": "complete", "days": 30}
    assert report["retention"]["boundary"] == "2026-09-28T12:00Z"
    day_reads = [call for call in api.calls if "Excerpt provenance" in call]  # the probe and the bucket aside
    assert [re.search(r'timestamp>="([^"]{10})', call).group(1) for call in day_reads] == [
        "2026-09-28", "2026-09-29", "2026-09-29"]  # the 29th's token repeats: a second page, then partial
    assert report["days"][3]["error"] == "invalid_pagination"


def test_without_the_bucket_an_empty_answer_means_nothing_is_kept_not_a_quiet_window(count):
    # entries:list leaves out an empty list: `{}` is "nothing at or after the start", every day gone.
    report = count.collect(FakeLogging(probe=({},)), "earnings-nerd", "2026-10-04T00:00:00Z",
                           "2026-10-06T00:00:00Z", now=NOW)
    assert {d["state"] for d in report["days"]} == {"expired_or_absent"}
    assert report["retention"]["oldest_retained"] == {"state": "complete", "timestamp": None}


def test_without_the_bucket_a_slow_or_failed_probe_never_reads_an_empty_day_as_complete(count):
    for probe in (({"nextPageToken": "a"},) * 5, ("http_503",)):
        api = FakeLogging(probe=probe, days={
            "2026-10-04": {"entries": [provenance_line("regex_fallback", REGEX, "2026-10-04T10:00:00Z")]}})
        report = count.collect(api, "earnings-nerd", "2026-10-04T00:00:00Z", "2026-10-06T00:00:00Z", now=NOW)
        assert [(d["day"], d["state"]) for d in report["days"]] == [
            ("2026-10-04", "complete"), ("2026-10-05", "retention_unverified")]
        assert report["retention"]["oldest_retained"]["state"] in ("unknown", "unavailable")


def test_without_the_bucket_a_quiet_start_is_no_expiry_and_a_late_one_is(count):
    for oldest, first_state in (("2026-10-04T00:00:02.4Z", "complete"),
                                ("2026-10-04T06:00:00Z", "partly_expired_or_absent")):
        api = FakeLogging(probe=({"entries": [{"timestamp": oldest}]},))
        report = count.collect(api, "earnings-nerd", "2026-10-04T00:00:00Z", "2026-10-05T00:00:00Z", now=NOW)
        assert report["days"][0]["state"] == first_state


def test_the_receipt_names_no_accession_filing_url_or_exact_time(count):
    entries = [provenance_line("edgartools", NATIVE, "2026-10-05T07:41:12.123Z"),
               *fetch_lines(424242, CAPPED, 16_500_000, "2026-10-20T00:00:00Z"),
               provenance_line("regex_fallback", CAPPED, "2026-10-20T00:00:01Z")]
    api = FakeLogging(bucket={"retentionDays": 3650}, days={"2026-10-05": {"entries": entries[:1]},
                                                            "2026-10-20": {"entries": entries[1:]}})
    report = count.collect(api, "earnings-nerd", "2026-10-01T00:00:00Z", "2026-10-28T00:00:00Z", now=NOW)
    printed = json.dumps(report)
    for name in (NATIVE, CAPPED, NATIVE.replace("-", ""), CAPPED.replace("-", ""), "424242", "sec.gov", "07:41:12"):
        assert name not in printed
    assert not re.search(r"\d{10}-\d{2}-\d{6}|\d{18}", printed)
    assert report["size_cap"]["size_cap_fallback"] == 1


def test_the_project_and_the_window_are_checked_before_any_read(count):
    with pytest.raises(ValueError):
        count.collect(FakeLogging(), "bad project", "2026-10-04T00:00:00Z", "2026-10-06T00:00:00Z", now=NOW)
    assert count.main(["--start", "2026-10-04T00:00:00Z", "--end", "2026-10-06T00:00:00Z", "--validate-only"]) == 0


def test_main_writes_the_receipt_it_prints(count, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(count.subprocess, "check_output",
                        lambda command, **_: "earnings-nerd\n" if "project" in command else "token\n")
    monkeypatch.setattr(count, "Logging", lambda token: FakeLogging(bucket={"retentionDays": 3650}))
    output = tmp_path / "receipt.json"
    assert count.main(["--start", "2026-10-04T00:00:00Z", "--end", "2026-10-05T00:00:00Z",
                       "--output", str(output)]) == 0
    assert json.loads(output.read_text()) == json.loads(capsys.readouterr().out)
    assert oct(output.stat().st_mode & 0o777) == "0o600"
