"""ops/excerpts/provenance_count.py: the excerpt builders counted from retained logs, counts only (E28).

The reader takes each UTC day of a bounded window from Cloud Logging and counts the `Excerpt provenance` lines by
class, over E28 (b)'s window and the whole read, with each size-cap firing joined to its own run. These tests hold
it to its header with the API's real answer shapes (an empty result is `{}`, a slow search may answer with a token
alone): retention fails closed, never as a complete day of zeros, whether or not the bucket can be read; the
window's figures come from the window alone; the client keeps closed error classes; and the receipt names no
accession, filing, URL or exact time.
"""
import http.server
import importlib.util
import json
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[3] / "ops" / "excerpts" / "provenance_count.py"
NOW = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
START, END = datetime(2026, 10, 1, tzinfo=timezone.utc), datetime(2026, 10, 28, tzinfo=timezone.utc)


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


PROVENANCE_LOGGER = "app.services.summary_generation_service"
FETCH_LOGGER = "app.services.summary_pipeline"
CAP_LOGGER = "app.services.edgar.xbrl_service"


def line(logger, text, stamp, *, json_payload=True, resource="cloud_run_revision"):
    # Formatted as production formats it: the API service and the task worker through logging_service's JSON
    # formatter, a Cloud Run job through basicConfig's default text format (Cloud Run parses a JSON line into
    # jsonPayload and keeps a text line as textPayload).
    import logging

    from app.services.logging_service import StructuredLogFormatter

    record = logging.getLogger(logger).makeRecord(logger, logging.INFO, __file__, 0, text, None, None)
    if json_payload:
        return {"timestamp": stamp, "resource": {"type": resource},
                "jsonPayload": json.loads(StructuredLogFormatter().format(record))}
    return {"timestamp": stamp, "resource": {"type": "cloud_run_job" if resource == "cloud_run_revision" else resource},
            "textPayload": logging.Formatter(logging.BASIC_FORMAT).format(record)}


def provenance_line(source, accession, stamp, *, json_payload=True, **schema_two):
    record = {"schema_version": 2 if schema_two else 1, "accession": accession, "source": source,
              "excerpt_chars": 10, "excerpt_sha256": "a" * 64, "supplied_sections": [], **schema_two}
    return line(PROVENANCE_LOGGER, "Excerpt provenance: " + json.dumps(record, sort_keys=True), stamp,
                json_payload=json_payload)


def fetch_lines(filing_id, accession, length, stamp):
    url = f"https://www.sec.gov/Archives/edgar/data/1140361/{accession.replace('-', '')}/doc.htm"
    return [line(FETCH_LOGGER, f"[stream:{filing_id}] Starting SEC fetch for URL: {url}", stamp),
            line(FETCH_LOGGER, f"[stream:{filing_id}] SEC fetch completed. Text length: {length}", stamp)]


def cap_line(length, form, stamp):
    return line(CAP_LOGGER, f"Section parse skipped: {length:,}-char {form} document is over the size cap", stamp)


def day(start, entries, state="complete"):
    return {"start": datetime.fromisoformat(start).replace(tzinfo=timezone.utc), "state": state, "entries": entries}


class FakeLogging:
    """Logging's answers by request: the bucket (a GET), the one-entry retention probe, and each day's pages
    (one answer, or a list of answers page by page)."""

    def __init__(self, *, bucket=None, probe=({},), days=None):
        self.bucket, self.probe, self.days, self.calls = bucket, list(probe), days or {}, []

    def call(self, url, body=None):
        self.calls.append(body["filter"] if body else url)
        if body is None:
            return (self.bucket, None) if self.bucket else (None, "http_403")
        # The probe and the day reads alike read the app's own streams, never the audit logs _Required keeps.
        assert ' AND logName:("run.googleapis.com%2Fstdout" OR "run.googleapis.com%2Fstderr")' in body["filter"]
        if body["pageSize"] == 1:
            answer = self.probe.pop(0) if self.probe else {}
        else:
            first = re.search(r'timestamp>="([^"]+)"', body["filter"]).group(1)[:10]
            answer = self.days.get(first, {})
            if isinstance(answer, list):
                answer = answer.pop(0) if answer else {}
        return (None, answer) if isinstance(answer, str) else (answer, None)


def states(report):
    return [(d["day"], d["state"]) for d in report["days"]]


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
    for line in ("Excerpt provenance:", "SEC fetch completed. Text length:", "Starting SEC fetch for URL:",
                 "Section parse skipped:"):
        assert f'textPayload:"{line}"' in text and f'jsonPayload.message:"{line}"' in text
    assert '"earningsnerd-backend" OR "earningsnerd-task-worker"' in text and 'resource.type="cloud_run_job"' in text
    assert 'timestamp>="2026-10-10T00:00:00Z" AND timestamp<"2026-10-11T00:00:00Z"' in text


def test_a_mark_belongs_to_the_era_it_opens_to_the_microsecond(count):
    for _name, mark in count.MARKS[1:]:
        at = count.parse_timestamp(mark)
        assert count.era(at) != count.era(at - timedelta(microseconds=1))
    assert count.era(count.parse_timestamp("2026-10-04T09:28:59.999999999Z")) == "before"
    assert count.era(count.parse_timestamp("2026-10-04T09:29:00Z")) == "onset"
    assert count.parse_timestamp("2026-10-04T11:29:00+02:00") == datetime(2026, 10, 4, 9, 29, tzinfo=timezone.utc)
    assert count.parse_timestamp("yesterday") is None


def test_counts_each_class_window_reason_and_form_and_names_none(count):
    entries = [
        provenance_line("edgartools", NATIVE, "2026-10-02T08:00:00Z"),
        provenance_line("edgartools", BOTH, "2026-10-05T07:41:12.5Z"),  # native still worked after the last report
        provenance_line("edgartools", NATIVE, "2026-10-16T04:10:00Z"),  # at #1350's deploy: outside the window
        provenance_line("regex_fallback", REGEX, "2026-10-04T09:35:00Z", json_payload=False),  # a 6-K, say
        provenance_line("regex_fallback", REGEX, "2026-10-10T03:00:00Z"),  # the same accession again
        provenance_line("regex_fallback", BOTH, "2026-10-09T00:00:00Z", outcome="fallback",
                        fallback_reason="sections_not_supplied", filing_type="10-Q"),
        provenance_line("regex_fallback", CAPPED, "2026-10-20T00:00:01Z", outcome="fallback",
                        fallback_reason="sections_not_supplied", filing_type="10-K"),  # after the window
        provenance_line("regex_fallback", FETCHED_ONLY.replace("0101", "0102"), "2026-10-12T00:00:00Z",
                        outcome="unavailable", fallback_reason="sections_not_supplied", filing_type="6-K"),
        provenance_line("legacy_cached_excerpt", NATIVE, "2026-10-12T00:00:00Z"),
        provenance_line("somewhere_new", NATIVE, "2026-10-12T00:00:00Z"),
        line(PROVENANCE_LOGGER, "Excerpt provenance: {not json", "2026-10-10T00:00:00Z"),
        line(FETCH_LOGGER, "[stream:9] Starting SEC fetch for URL: x", "2026-10-10T00:00:00Z"),
    ]
    report = count.tally([day("2026-10-10T00:00:00", entries)], START, END)
    [only] = report["days"]
    assert only["lines"] == {"edgartools": 3, "legacy_cached_excerpt": 1, "other": 1, "regex_fallback": 4,
                             "unavailable": 1, "unreadable": 1}
    assert only["unmatched"] == 1
    window = report["e28_window"]
    assert window["accessions"]["regex_fallback"] == 2 and window["accessions"]["edgartools"] == 1
    assert window["accessions"]["unavailable"] == 1
    # The window's reasons and forms come from the window's lines alone: the 20 October line is outside it, and
    # counts over the whole read.
    assert window["schema_two"] == {
        "by_fallback_reason": {"regex_fallback": {"sections_not_supplied": 1}, "unavailable": {"sections_not_supplied": 1}},
        "by_form": {"regex_fallback": {"10-Q": 1}, "unavailable": {"6-K": 1}}}
    assert report["schema_two"] == {
        "by_fallback_reason": {"regex_fallback": {"sections_not_supplied": 2}, "unavailable": {"sections_not_supplied": 1}},
        "by_form": {"regex_fallback": {"10-K": 1, "10-Q": 1}, "unavailable": {"6-K": 1}}}
    # The onset's bound is the last native line inside the window, to its minute: not the one at the deploy mark.
    assert report["last_native_line_in_e28_window"] == "2026-10-05T07:41Z"
    assert report["accessions_by_era"]["regex_fallback"] == {"before": 0, "onset": 1, "window": 2, "after": 1}
    assert report["accessions_native_and_regex"] == 1


def test_each_size_cap_firing_joins_its_own_run_and_nothing_else(count):
    entries = [
        # A 403-era regex excerpt on a large filing: fetched over the cap before #1347, never a cap fallback.
        *fetch_lines(40, CAPPED, 20_000_000, "2026-10-08T00:00:00Z"),
        provenance_line("regex_fallback", CAPPED, "2026-10-08T00:00:01Z"),
        # The same filing after #1347, its excerpt stored: fetched over the cap, no parse, no cap fallback.
        *fetch_lines(41, CAPPED, 20_000_000, "2026-10-20T00:00:00Z"),
        provenance_line("legacy_cached_excerpt", CAPPED, "2026-10-20T00:00:01Z"),
        # A filing the cap sends to regex: its skip line's length is its own fetch's.
        *fetch_lines(42, FETCHED_ONLY, 17_000_000, "2026-10-21T00:00:00Z"),
        cap_line(17_000_000, "10-K", "2026-10-21T00:00:01Z"),
        provenance_line("regex_fallback", FETCHED_ONLY, "2026-10-21T00:00:02Z"),
        # Exactly the cap is not over it; a skip line no fetch explains stays unjoined.
        *fetch_lines(43, NATIVE, 16_000_000, "2026-10-21T01:00:00Z"),
        cap_line(18_000_000, "20-F", "2026-10-21T02:00:00Z"),
        # Two accessions fetched at one length: the skip line cannot say whose, so it stays unjoined.
        *fetch_lines(44, REGEX, 19_000_000, "2026-10-22T00:00:00Z"),
        *fetch_lines(45, BOTH, 19_000_000, "2026-10-22T00:00:00Z"),
        cap_line(19_000_000, "10-Q", "2026-10-22T00:00:01Z"),
        # A fetch whose run logged no start line names no accession: its skip line stays unjoined too.
        line(FETCH_LOGGER, "[stream:46] SEC fetch completed. Text length: 21000000", "2026-10-23T00:00:00Z"),
        cap_line(21_000_000, "10-K/A", "2026-10-23T00:00:01Z"),
        # One fetch of a length named, another of the same length not: whose run the skip line is stays unknown.
        *fetch_lines(47, "0000950170-26-000777", 22_000_000, "2026-10-24T00:00:00Z"),
        line(FETCH_LOGGER, "[stream:48] SEC fetch completed. Text length: 22000000", "2026-10-24T00:00:00Z"),
        cap_line(22_000_000, "10-Q", "2026-10-24T00:00:01Z"),
    ]
    report = count.tally([day("2026-10-08T00:00:00", entries)], START, END)
    assert report["size_cap"] == {"cap_merged": "2026-10-16T17:50:25Z",
                                  "over_cap_accessions_by_era": {"before": 0, "onset": 0, "window": 1, "after": 5},
                                  "native_over_cap_accessions_by_era": {"before": 0, "onset": 0, "window": 0, "after": 0},
                                  "native_over_cap_accessions_outside_403": 0,
                                  "over_cap_accessions_since_cap_merged": 5, "over_cap_fetches_unnamed": 2,
                                  "size_cap_fallbacks": {"10-K": 1, "10-K/A": 1, "10-Q": 2, "20-F": 1},
                                  "size_cap_fallback_accessions": 1, "size_cap_fallbacks_unjoined": 4}
    assert report["days"][0]["over_size_cap_fetches"] == 8


def test_only_each_lines_own_logger_counts_and_hostile_text_stays_closed(count):
    # A search query another logger records can hold the same words; deep nesting is no crash; keys stay closed.
    spoof = "Excerpt provenance: " + json.dumps({"accession": REGEX, "source": "regex_fallback"})
    entries = [
        line("app.routers.companies", f"Company search failed for {spoof}", "2026-10-10T00:00:00Z"),
        line("app.routers.companies", spoof, "2026-10-10T00:00:00Z"),
        line(PROVENANCE_LOGGER, "Excerpt provenance: " + "[" * 5000, "2026-10-10T00:00:00Z"),
        line(PROVENANCE_LOGGER, "Logged: Excerpt provenance: {}", "2026-10-10T00:00:00Z"),
        line(CAP_LOGGER, "[stream:1] SEC fetch completed. Text length: 99000000", "2026-10-10T00:00:00Z"),
        line(FETCH_LOGGER, "Section parse skipped: 99,000,000-char 10-K document is over the size cap",
             "2026-10-10T00:00:00Z"),
        provenance_line("regex_fallback", NATIVE, "2026-10-10T00:00:00Z", outcome="fallback",
                        fallback_reason="<script>alert(1)</script>", filing_type="10-k"),
        provenance_line("regex_fallback", BOTH, "2026-10-10T00:00:00Z", outcome="fallback",
                        fallback_reason="native_excerpt_thin", filing_type="S-1"),
        {**line(PROVENANCE_LOGGER, "x", "z"), "timestamp": "2026-02-30T00:00:00Z"},  # an impossible date: no crash
        # A job's text from another logger, a text line from the service (it writes JSON), JSON naming no logger,
        # and a start line from another logger, which must feed no fetch or join.
        line("app.routers.companies", spoof, "2026-10-10T00:00:00Z", json_payload=False),
        {**line(PROVENANCE_LOGGER, spoof, "2026-10-10T00:00:00Z", json_payload=False),
         "resource": {"type": "cloud_run_revision"}},
        {"timestamp": "2026-10-10T00:00:00Z", "resource": {"type": "cloud_run_revision"}, "jsonPayload": {"message": spoof}},
        line("app.routers.companies", "[stream:7] Starting SEC fetch for URL: https://www.sec.gov/Archives/edgar/data/"
             f"1/{CAPPED.replace('-', '')}/d.htm", "2026-10-10T00:00:00Z"),
    ]
    report = count.tally([day("2026-10-10T00:00:00", entries)], START, END)
    [only] = report["days"]
    assert only["lines"] == {"regex_fallback": 2, "unreadable": 1}
    assert (only["fetches"], only["unmatched"], only["size_cap_fallbacks"]) == (0, 10, {})
    assert report["accessions_fetched_without_provenance"] == 0
    assert report["accessions"]["regex_fallback"] == 2
    assert report["schema_two"] == {"by_fallback_reason": {"regex_fallback": {"native_excerpt_thin": 1, "other": 1}},
                                    "by_form": {"regex_fallback": {"10-K": 1, "other": 1}}}
    assert "script" not in json.dumps(report)
    for text in ("2026-02-30T00:00:00Z", "2026-10-04T09:29:00+99:00", "2026-13-01T00:00:00Z",
                 "0001-01-01T00:00:00+05:00", "9999-12-31T23:59:59-05:00"):
        assert count.parse_timestamp(text) is None


def test_the_cap_counts_filings_once_by_era_and_the_native_ones_e28_a_sizes(count):
    entries = [
        # Built natively before the onset, over the cap: an excerpt the cap would now send to regex.
        *fetch_lines(50, NATIVE, 18_000_000, "2026-10-01T00:00:00Z"),
        provenance_line("edgartools", NATIVE, "2026-10-01T00:00:01Z"),
        *fetch_lines(51, NATIVE, 18_000_000, "2026-10-02T00:00:00Z"),  # the same filing again: counted once
        provenance_line("legacy_cached_excerpt", NATIVE, "2026-10-02T00:00:01Z"),
        # Fetched over the cap after the deploy, reusing its stored excerpt: a ceiling's, not a native one's.
        *fetch_lines(52, REGEX, 18_500_000, "2026-10-16T05:00:00Z"),
        provenance_line("legacy_cached_excerpt", REGEX, "2026-10-16T05:00:01Z"),
        # Built natively after the deploy, before the cap's merge; and one fetched at the merge's own second.
        *fetch_lines(53, BOTH, 19_500_000, "2026-10-16T06:00:00Z"),
        provenance_line("edgartools", BOTH, "2026-10-16T06:00:01Z"),
        *fetch_lines(54, CAPPED, 20_500_000, "2026-10-16T17:50:25Z"),
    ]
    size_cap = count.tally([day("2026-10-01T00:00:00", entries)], START, END)["size_cap"]
    assert size_cap["over_cap_accessions_by_era"] == {"before": 1, "onset": 0, "window": 0, "after": 3}
    assert size_cap["native_over_cap_accessions_by_era"] == {"before": 1, "onset": 0, "window": 0, "after": 1}
    assert size_cap["native_over_cap_accessions_outside_403"] == 2
    assert size_cap["over_cap_accessions_since_cap_merged"] == 1
    # Built natively over the cap before the onset and again after the deploy: one accession, counted once; and a
    # native build in one era never makes another era's over-cap fetch native.
    entries += [*fetch_lines(55, NATIVE, 18_000_000, "2026-10-17T00:00:00Z"),
                provenance_line("edgartools", NATIVE, "2026-10-17T00:00:01Z"),
                *fetch_lines(56, REGEX, 18_500_000, "2026-10-01T05:00:00Z")]
    size_cap = count.tally([day("2026-10-01T00:00:00", entries)], START, END)["size_cap"]
    assert size_cap["native_over_cap_accessions_by_era"] == {"before": 1, "onset": 0, "window": 0, "after": 2}
    assert size_cap["native_over_cap_accessions_outside_403"] == 2


def test_a_cut_day_leaves_fetches_without_provenance_unknown(count):
    fetched = fetch_lines(41, CAPPED, 10, "2026-10-10T00:00:00Z")
    assert count.tally([day("2026-10-10T00:00:00", fetched)], START, END)["accessions_fetched_without_provenance"] == 1
    assert count.tally([day("2026-10-10T00:00:00", fetched, state="partial")], START,
                       END)["accessions_fetched_without_provenance"] is None


def test_the_window_says_whether_the_read_held_it_whole(count):
    whole = [day(f"2026-10-{n:02d}T00:00:00", []) for n in range(4, 17)]
    assert count.tally(whole, START, END)["e28_window"]["covered"] is True
    late = datetime(2026, 10, 6, tzinfo=timezone.utc)
    assert count.tally(whole[2:], late, END)["e28_window"]["covered"] is False
    early_end = datetime(2026, 10, 15, tzinfo=timezone.utc)
    assert count.tally(whole[:-2], START, early_end)["e28_window"]["covered"] is False
    # The onset's day and the deploy's day are the window's too.
    for index in (0, 5, len(whole) - 1):
        cut = [dict(d) for d in whole]
        cut[index]["state"] = "partial"
        assert count.tally(cut, START, END)["e28_window"]["covered"] is False, index


def test_the_later_of_the_buckets_boundary_and_the_oldest_entry_dates_what_is_gone(count):
    # Retention of 30 days on 28 October: the 28th of September is the first day kept, in part.
    api = FakeLogging(bucket={"retentionDays": 30}, probe=({"entries": [{"timestamp": "2026-09-01T00:00:00Z"}]},),
                      days={"2026-09-28": {"entries": [provenance_line("edgartools", NATIVE, "2026-09-28T20:00:00Z")]},
                            "2026-09-29": [{"nextPageToken": "t1", "entries": []}, {"nextPageToken": "t1"}]})
    report = count.collect(api, "earnings-nerd", "2026-09-26T00:00:00Z", "2026-09-30T00:00:00Z", now=NOW)
    assert states(report) == [("2026-09-26", "expired_or_absent"), ("2026-09-27", "expired_or_absent"),
                              ("2026-09-28", "partly_expired_or_absent"), ("2026-09-29", "partial")]
    assert report["retention"]["gone_before"] == "2026-09-28T12:00Z"
    assert report["days"][3]["error"] == "invalid_pagination"
    # Retention raised after the lines went: the bucket says 90 days, the oldest entry says 6 October.
    api = FakeLogging(bucket={"retentionDays": 90}, probe=({"entries": [{"timestamp": "2026-10-06T03:00:00Z"}]},))
    report = count.collect(api, "earnings-nerd", "2026-10-04T00:00:00Z", "2026-10-08T00:00:00Z", now=NOW)
    assert states(report) == [("2026-10-04", "expired_or_absent"), ("2026-10-05", "expired_or_absent"),
                              ("2026-10-06", "partly_expired_or_absent"), ("2026-10-07", "complete")]


def test_an_empty_probe_means_nothing_is_kept_unless_the_bucket_says_otherwise(count):
    # entries:list leaves out an empty list: `{}` is "nothing at or after the start", every day gone.
    api = FakeLogging(probe=({},))
    report = count.collect(api, "earnings-nerd", "2026-10-04T00:00:00Z", "2026-10-06T00:00:00Z", now=NOW)
    assert {d["state"] for d in report["days"]} == {"expired_or_absent"}
    assert report["retention"]["oldest_retained"] == {"state": "complete", "timestamp": None}
    # A bucket that keeps the window puts the probe's own filter in doubt: the days are read, and unverified.
    api = FakeLogging(bucket={"retentionDays": 3650}, probe=({},))
    report = count.collect(api, "earnings-nerd", "2026-10-04T00:00:00Z", "2026-10-06T00:00:00Z", now=NOW)
    assert {d["state"] for d in report["days"]} == {"retention_unverified"}
    assert sum("Excerpt provenance" in call for call in api.calls) == 2
    # A bucket that keeps part of the window: what it no longer keeps is gone, the rest read and unverified.
    api = FakeLogging(bucket={"retentionDays": 30}, probe=({},))
    report = count.collect(api, "earnings-nerd", "2026-09-27T00:00:00Z", "2026-09-30T00:00:00Z", now=NOW)
    assert states(report) == [("2026-09-27", "expired_or_absent"), ("2026-09-28", "partly_expired_or_absent"),
                              ("2026-09-29", "retention_unverified")]


def test_a_slow_or_failed_probe_leaves_every_day_to_the_first_line_unverified(count):
    for bucket in (None, {"retentionDays": 3650}):
        for probe in (({"nextPageToken": "a"},) * 5, ("http_503",), ({"entries": {"not": "a list"}},)):
            api = FakeLogging(bucket=bucket, probe=probe, days={
                "2026-10-05": {"entries": [provenance_line("regex_fallback", REGEX, "2026-10-05T15:00:00Z")]}})
            report = count.collect(api, "earnings-nerd", "2026-10-04T00:00:00Z", "2026-10-07T00:00:00Z", now=NOW)
            assert states(report) == [("2026-10-04", "retention_unverified"), ("2026-10-05", "retention_unverified"),
                                      ("2026-10-06", "complete")], (bucket, probe)
            assert report["retention"]["oldest_retained"]["state"] in ("unknown", "unavailable")


def test_a_quiet_start_is_no_expiry_and_a_late_one_is(count):
    for oldest, first_state in (("2026-10-04T00:00:02.4Z", "complete"),
                                ("2026-10-04T06:00:00Z", "partly_expired_or_absent")):
        api = FakeLogging(probe=({"entries": [{"timestamp": oldest}]},))
        report = count.collect(api, "earnings-nerd", "2026-10-04T00:00:00Z", "2026-10-05T00:00:00Z", now=NOW)
        assert report["days"][0]["state"] == first_state


def test_a_read_cut_by_an_error_or_the_time_budget_is_a_floor(count):
    api = FakeLogging(probe=({"entries": [{"timestamp": "2026-10-04T00:00:01Z"}]},),
                      days={"2026-10-04": [{"nextPageToken": "t1", "entries": [provenance_line(
                          "regex_fallback", REGEX, "2026-10-04T10:00:00Z")]}, "http_429"]})
    report = count.collect(api, "earnings-nerd", "2026-10-04T00:00:00Z", "2026-10-06T00:00:00Z", now=NOW)
    assert [(d["state"], d.get("error")) for d in report["days"]] == [("partial", "http_429"), ("complete", None)]
    api = FakeLogging(probe=({"entries": [{"timestamp": "2026-10-04T00:00:01Z"}]},))
    report = count.collect(api, "earnings-nerd", "2026-10-04T00:00:00Z", "2026-10-06T00:00:00Z", now=NOW, budget=-1)
    assert {(d["state"], d.get("error")) for d in report["days"]} == {("unavailable", "time_budget")}


def test_the_receipt_names_no_accession_filing_url_or_exact_time(count):
    entries = [provenance_line("edgartools", NATIVE, "2026-10-05T07:41:12.123Z"),
               *fetch_lines(424242, CAPPED, 16_500_000, "2026-10-20T00:00:00Z"),
               cap_line(16_500_000, "10-K", "2026-10-20T00:00:00.5Z"),
               provenance_line("regex_fallback", CAPPED, "2026-10-20T00:00:01Z")]
    api = FakeLogging(bucket={"retentionDays": 3650}, probe=({"entries": [{"timestamp": "2026-10-01T00:00:03Z"}]},),
                      days={"2026-10-05": {"entries": entries[:1]}, "2026-10-20": {"entries": entries[1:]}})
    report = count.collect(api, "earnings-nerd", "2026-10-01T00:00:00Z", "2026-10-28T00:00:00Z", now=NOW)
    printed = json.dumps(report)
    for name in (NATIVE, CAPPED, NATIVE.replace("-", ""), CAPPED.replace("-", ""), "424242", "sec.gov", "07:41:12",
                 "16,500,000"):
        assert name not in printed
    assert not re.search(r"\d{10}-\d{2}-\d{6}|\d{18}", printed)
    assert report["size_cap"]["size_cap_fallback_accessions"] == 1


class _Handler(http.server.BaseHTTPRequestHandler):
    answers: dict = {}

    def do_POST(self):  # noqa: N802
        self._answer()

    def do_GET(self):  # noqa: N802
        self._answer()

    def _answer(self):
        status, body = self.answers[self.path]
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


def test_the_client_keeps_closed_classes_and_paces_its_requests(count, monkeypatch):
    _Handler.answers = {"/empty": (200, b"  "), "/object": (200, b'{"entries": []}'), "/list": (200, b"[]"),
                        "/denied": (403, b'{"error": "PRIVATE principal@example.invalid"}'),
                        "/broken": (200, b'{"entries": ')}
    server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    slept = []
    monkeypatch.setattr(count.time, "sleep", slept.append)
    try:
        client = count.Logging("token", pace=5.0)
        base = f"http://127.0.0.1:{server.server_port}"
        answers = [client.call(base + path, {"pageSize": 1} if path != "/denied" else None)
                   for path in ("/empty", "/object", "/list", "/denied", "/broken")]
    finally:
        server.shutdown()
    # Logging answers an empty result with `{}`, never with no body: an empty body is no answer.
    assert answers == [(None, "invalid_response"), ({"entries": []}, None), (None, "invalid_response"),
                       (None, "http_403"), (None, "transport_or_decode_error")]
    assert "principal" not in json.dumps(answers)
    assert len(slept) == 4 and all(0 < wait <= 5.0 for wait in slept)


def test_a_malformed_answer_is_a_closed_class_never_a_crash(count, monkeypatch):
    # A bad status line, a body cut short and runaway nesting each raise past urllib's own errors; the run must
    # still write its receipt, so each is a closed class.
    import socketserver

    raw = {"/status": b"GARBAGE\r\n\r\n",
           "/cut": b"HTTP/1.1 200 OK\r\nContent-Length: 4096\r\n\r\n{}",
           "/short": b"HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\n{\"entries\"",
           "/deep": b"HTTP/1.1 200 OK\r\nContent-Length: 200000\r\n\r\n" + b"[" * 100000 + b"]" * 100000}

    class Raw(socketserver.StreamRequestHandler):
        def handle(self):
            path = self.rfile.readline().split()[1].decode()
            while self.rfile.readline() not in (b"\r\n", b""):
                pass
            self.wfile.write(raw[path])

    server = socketserver.TCPServer(("127.0.0.1", 0), Raw)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(count.time, "sleep", lambda _seconds: None)
    try:
        client = count.Logging("token", pace=0)
        base = f"http://127.0.0.1:{server.server_address[1]}"
        answers = [client.call(base + path) for path in raw]
    finally:
        server.shutdown()
        server.server_close()
    assert answers == [(None, "transport_or_decode_error")] * 4


def test_the_project_and_the_window_are_checked_before_any_read(count):
    with pytest.raises(ValueError):
        count.collect(FakeLogging(), "bad project", "2026-10-04T00:00:00Z", "2026-10-06T00:00:00Z", now=NOW)
    assert count.main(["--start", "2026-10-04T00:00:00Z", "--end", "2026-10-06T00:00:00Z", "--validate-only"]) == 0


def test_main_writes_the_receipt_and_prints_only_where(count, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(count.subprocess, "check_output",
                        lambda command, **_: "earnings-nerd\n" if "project" in command else "token\n")
    monkeypatch.setattr(count, "Logging", lambda token: FakeLogging(
        bucket={"retentionDays": 3650}, probe=({"entries": [{"timestamp": "2026-10-04T00:00:01Z"}]},)))
    output = tmp_path / "receipt.json"
    assert count.main(["--start", "2026-10-04T00:00:00Z", "--end", "2026-10-05T00:00:00Z",
                       "--output", str(output)]) == 0
    receipt = json.loads(output.read_text())
    assert receipt["days"][0]["state"] == "complete"
    printed = capsys.readouterr().out
    assert str(output) in printed and "{" not in printed
    assert oct(output.stat().st_mode & 0o777) == "0o600"
