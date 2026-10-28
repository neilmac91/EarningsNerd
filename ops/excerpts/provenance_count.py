"""Count the summary excerpts' builders from retained logs (E28 (a)/(b); read-only, counts only).

The `Excerpt provenance: {json}` line (summary_generation_service.get_or_cache_excerpt) is the only record of
which builder wrote an excerpt: `source` `edgartools` (native sections), `regex_fallback`, or
`legacy_cached_excerpt` (a stored excerpt reused), with the filing's `accession`. Schema 2 (E80-C1) adds
`outcome` (`unavailable`: no excerpt was built), `fallback_reason` and `filing_type`; a schema-1 line names no
form. The summary stream's `[stream:<filing id>] Starting SEC fetch for URL: <url>` line names the accession it
fetched and its `SEC fetch completed. Text length: N` line the document's length. Since #1347 the section parse
logs `Section parse skipped: N-char <form> document is over the size cap` when the cap
(edgar/xbrl_sections.py `_MAX_SECTION_HTML_CHARS`) fires: the parse reads that same fetched text and runs only
for a filing with no stored excerpt (or a forced rebuild), so each such line is one size-cap fallback, joined to
its run's accession by the length its fetch line logged (a length two accessions share stays unjoined).

For each UTC day of the window this reads those lines from Cloud Logging (the API service, the task worker and
the Cloud Run jobs) and counts:
- per day: lines and distinct accessions by class (a source, `unavailable`, `other`, or `unreadable`), fetches,
  fetches over the size cap, and size-cap fallbacks by form;
- over E28 (b)'s window (from the last native eval report to #1350's deploy) and over the whole read: distinct
  accessions by class, and, from schema-2 lines only, regex and unavailable ones by fallback_reason and every
  class by form (an amendment apart from its form; anything but 10-K, 10-Q and 20-F as `other`); `covered` says
  whether the read held the whole window;
- the last native line inside E28 (b)'s window, rounded down to its minute: native sections stopped after it,
  so it bounds the onset CI could not. A regex line bounds nothing: a 6-K, a thin native assembly, a parse
  timeout or the size cap falls back on any day;
- the size cap: distinct accessions fetched over it by era and since #1347's merge (E28 (a): the count over the
  eras native sections worked, before the onset and after #1350's deploy, sizes what the cap changes), size-cap
  fallbacks (the skip lines) by form, and the distinct accessions they join to;
- the accessions fetched with no provenance line, only when no day was cut (else null).

Retention fails closed. The `_Default` bucket's `retentionDays`, where the identity may read it, and a bounded
probe for the oldest stdout or stderr entry the scope still holds (the streams the lines are written to, never
the audit logs `_Required` keeps for 400 days) each date what is gone, and the later of the two wins (a
retention raised after lines expired keeps them gone). An empty probe (`{}`) means nothing is held. A day wholly
before that date reads `expired_or_absent`, the day it falls in `partly_expired_or_absent`; an oldest entry
within an hour of the window's start is a quiet start, not expiry. When the probe cannot say, every day up to
and including the first day that holds a line reads `retention_unverified`, never `complete` with 0. A day whose
pages ran out reads `partial`, one that could not be read `unavailable` with a closed class; a read that runs out
of its time budget (25 minutes, inside the 30 the Ops step allows) marks the days it did not reach `unavailable`
(`time_budget`).

The receipt holds counts and minute-rounded timestamps only: no accession, filing id, URL, message text or
principal. It is written to --output; stdout says where. Standard library only (the Ops runner's python3);
requests are paced under Logging's read quota.

Local usage:
  python3 ops/excerpts/provenance_count.py --start 2026-10-01T00:00:00Z --end 2026-10-28T00:00:00Z \
      --output excerpt-cohort/logged.json
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

REGION = "us-west1"
SERVICES = ("earningsnerd-backend", "earningsnerd-task-worker")
ENTRIES = "https://logging.googleapis.com/v2/entries:list"
MAX_DAYS = 45
MAX_PAGES_PER_DAY = 40  # 40 x 1,000 entries; a day that needs more is partial
PAGE_SIZE = 1000
MAX_RESPONSE = 32 * 1024 * 1024
PROBE_PAGES = 5  # a slow search may answer a page with a token alone
QUIET_START = timedelta(hours=1)  # an oldest entry this soon after the window opens is no expiry
PACE_SECONDS = 1.1  # Logging allows 60 entries.list requests a minute per project
BUDGET_SECONDS = 25 * 60  # inside the 30 minutes the Ops step allows, so the receipt is always written
SIZE_CAP = 16_000_000  # edgar/xbrl_sections.py _MAX_SECTION_HTML_CHARS since #1347
CAP_MERGED = "2026-10-16T17:50:25Z"  # #1347 (a9738b38); its deploy followed, unrecorded
CAP_FORMS = ("10-K", "10-Q", "20-F")  # the forms the section parse reads
APP_STREAMS = 'logName:("run.googleapis.com%2Fstdout" OR "run.googleapis.com%2Fstderr")'
_KEY = re.compile(r"[a-z_]{1,40}")
# The builder eras (tasks/todo.md E28; tasks/review-evidence/e28-native-sections-2026-10-15/README.md): the last
# native eval report, the first all-regex one, #1350's deploy. E28 (b)'s window runs from the first to the last.
MARKS = (
    ("before", None),
    ("onset", "2026-10-04T09:29:00Z"),
    ("window", "2026-10-07T19:06:00Z"),
    ("after", "2026-10-16T04:10:00Z"),
)
PROVENANCE = "Excerpt provenance: "
FETCHED = re.compile(r"\[stream:(\d+)\] SEC fetch completed\. Text length: (\d+)")
STARTED = re.compile(r"\[stream:(\d+)\] Starting SEC fetch for URL: \S*/Archives/edgar/data/\d+/(\d{18})/")
CAPPED = re.compile(r"Section parse skipped: ([\d,]+)-char (\S+) document is over the size cap")
SOURCES = ("edgartools", "regex_fallback", "legacy_cached_excerpt")
CLASSES = (*SOURCES, "unavailable", "other", "unreadable")
_TIMESTAMP = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:\d{2})")


class Logging:
    """Cloud Logging over HTTPS with a bearer token: one request at a time, paced, and only a closed error class
    on failure (an HTTP status, or transport/decode/size), never a response body."""

    def __init__(self, token: str, pace: float = PACE_SECONDS):
        self.token, self.pace, self._last = token, pace, 0.0

    def call(self, url: str, body: dict | None = None):
        wait = self._last + self.pace - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        data = json.dumps(body).encode() if body is not None else None
        request = Request(url, data=data, headers={"Authorization": "Bearer " + self.token,
                                                   "Content-Type": "application/json"})
        try:
            # Code-owned HTTPS endpoints only; nothing from the workflow's input forms a URL.
            with urlopen(request, timeout=30) as response:  # nosec B310
                raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                return None, "response_size_limit"
            payload = json.loads(raw) if raw.strip() else {}
            return (payload, None) if isinstance(payload, dict) else (None, "invalid_response")
        except HTTPError as exc:
            return None, f"http_{exc.code}"
        except (URLError, TimeoutError, OSError, ValueError, http.client.HTTPException, RecursionError):
            return None, "transport_or_decode_error"


def _instant(text: str) -> datetime:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", text or ""):
        raise ValueError("timestamps are UTC, YYYY-MM-DDTHH:MM:SSZ")
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_timestamp(text) -> datetime | None:
    """A log entry's RFC 3339 timestamp (nanoseconds and offsets included) as an aware datetime, or None."""
    match = _TIMESTAMP.fullmatch(text) if isinstance(text, str) else None
    if not match:
        return None
    whole, fraction, zone = match.groups()
    moment = datetime.strptime(whole, "%Y-%m-%dT%H:%M:%S")
    if fraction:
        moment = moment.replace(microsecond=int(fraction[:6].ljust(6, "0")))
    offset = timedelta(0) if zone == "Z" else timedelta(hours=int(zone[1:3]), minutes=int(zone[4:6])) * (
        1 if zone[0] == "+" else -1)
    return moment.replace(tzinfo=timezone(offset)).astimezone(timezone.utc)


def _minute(moment: datetime | None) -> str | None:
    return moment.strftime("%Y-%m-%dT%H:%MZ") if moment else None


def days(start: str, end: str) -> list[tuple[datetime, datetime]]:
    """The UTC day slices of [start, end): bounded, in the past, whole days or their edges."""
    first, last = _instant(start), _instant(end)
    if not first < last <= datetime.now(timezone.utc):
        raise ValueError("the window must be non-empty and end in the past")
    if last - first > timedelta(days=MAX_DAYS):
        raise ValueError(f"the window spans at most {MAX_DAYS} days")
    slices, cursor = [], first
    while cursor < last:
        edge = min(datetime(cursor.year, cursor.month, cursor.day, tzinfo=timezone.utc) + timedelta(days=1), last)
        slices.append((cursor, edge))
        cursor = edge
    return slices


def scope_filter() -> str:
    services = " OR ".join(f'"{name}"' for name in SERVICES)
    return (f'resource.labels.location="{REGION}" AND ('
            f'(resource.type="cloud_run_revision" AND resource.labels.service_name=({services})) OR '
            'resource.type="cloud_run_job")')


def day_filter(start: datetime, end: datetime) -> str:
    lines = ('"Excerpt provenance:"', '"SEC fetch completed. Text length:"', '"Starting SEC fetch for URL:"',
             '"Section parse skipped:"')
    payload = " OR ".join(f"textPayload:{line} OR jsonPayload.message:{line}" for line in lines)
    return f'timestamp>="{_stamp(start)}" AND timestamp<"{_stamp(end)}" AND {scope_filter()} AND ({payload})'


def message(entry: dict) -> str:
    text = entry.get("textPayload")
    if isinstance(text, str):
        return text
    payload = entry.get("jsonPayload")
    text = payload.get("message") if isinstance(payload, dict) else None
    return text if isinstance(text, str) else ""


def provenance(text: str) -> dict | None:
    """The record a provenance line carries, or None for a line that does not read as one."""
    at = text.find(PROVENANCE)
    if at < 0:
        return None
    try:
        record, _end = json.JSONDecoder().raw_decode(text, at + len(PROVENANCE))
    except ValueError:
        return None
    return record if isinstance(record, dict) else None


def _accession(value) -> str | None:
    digits = value.replace("-", "").strip() if isinstance(value, str) else ""
    return digits if len(digits) == 18 and digits.isdigit() else None


def era(moment: datetime) -> str:
    label = MARKS[0][0]
    for name, mark in MARKS[1:]:
        if moment >= _instant(mark):
            label = name
    return label


def _class(record: dict) -> str:
    if record.get("outcome") == "unavailable":
        return "unavailable"
    source = record.get("source")
    return source if source in SOURCES else "other"


def _form(value) -> str | None:
    """A schema-2 filing_type as its key: a read form or its amendment as given, anything else `other`."""
    if not isinstance(value, str):
        return None
    form = value.strip().upper()
    return form if form in (*CAP_FORMS, *(f"{base}/A" for base in CAP_FORMS)) else "other"


def _schema_two(sink: dict, name: str, record: dict, accession: str) -> None:
    """Add a schema-2 line's reason (regex and unavailable lines) and form to ``sink``; keys are closed shapes."""
    reason = record.get("fallback_reason")
    if name in ("regex_fallback", "unavailable") and isinstance(reason, str):
        key = reason if _KEY.fullmatch(reason) else "other"
        sink.setdefault("by_fallback_reason", {}).setdefault(name, {}).setdefault(key, set()).add(accession)
    form = _form(record.get("filing_type"))
    if form:
        sink.setdefault("by_form", {}).setdefault(name, {}).setdefault(form, set()).add(accession)


def _counted(sink: dict) -> dict:
    return {kind: {name: {key: len(found) for key, found in sorted(keys.items())} for name, keys in sorted(by.items())}
            for kind, by in sorted(sink.items())}


def tally(days_read: list[dict], start: datetime, end: datetime) -> dict:
    """Counts from each day's entries; the entries, accessions and filing ids never leave this function."""
    onset, deployed, cap_merged = _instant(MARKS[1][1]), _instant(MARKS[3][1]), _instant(CAP_MERGED)
    eras = {name: {era_name: set() for era_name, _ in MARKS} for name in CLASSES}
    in_window = {name: set() for name in CLASSES}
    whole = {name: set() for name in CLASSES}
    window_schema_two: dict = {}
    whole_schema_two: dict = {}
    filing_accession: dict[str, str] = {}
    length_filings: dict[int, set] = {}
    capped_lengths: list[int] = []
    capped_by_form: dict[str, int] = {}
    over_cap_fetches: list[tuple[str, datetime]] = []
    fetched: set[str] = set()
    last_native = None
    report_days = []
    for day in days_read:
        counts = {"lines": {}, "accessions": {}, "fetches": 0, "over_size_cap_fetches": 0, "size_cap_fallbacks": {},
                  "unmatched": 0}
        per_class: dict[str, set] = {}
        for entry in day["entries"]:
            text = message(entry)
            moment = parse_timestamp(entry.get("timestamp")) or day["start"]
            started = STARTED.search(text)
            if started:
                filing_accession[started.group(1)] = started.group(2)
                fetched.add(started.group(2))
                continue
            done = FETCHED.search(text)
            if done:
                counts["fetches"] += 1
                length = int(done.group(2))
                length_filings.setdefault(length, set()).add(done.group(1))
                if length > SIZE_CAP:
                    counts["over_size_cap_fetches"] += 1
                    over_cap_fetches.append((done.group(1), moment))
                continue
            capped = CAPPED.search(text)
            if capped:
                form = _form(capped.group(2)) or "other"
                counts["size_cap_fallbacks"][form] = counts["size_cap_fallbacks"].get(form, 0) + 1
                capped_by_form[form] = capped_by_form.get(form, 0) + 1
                capped_lengths.append(int(capped.group(1).replace(",", "")))
                continue
            if PROVENANCE not in text:
                counts["unmatched"] += 1
                continue
            record = provenance(text)
            name = _class(record) if record else "unreadable"
            counts["lines"][name] = counts["lines"].get(name, 0) + 1
            accession = _accession(record.get("accession")) if record else None
            if accession is None:
                continue
            per_class.setdefault(name, set()).add(accession)
            eras[name][era(moment)].add(accession)
            whole[name].add(accession)
            _schema_two(whole_schema_two, name, record, accession)
            if onset <= moment < deployed:
                in_window[name].add(accession)
                _schema_two(window_schema_two, name, record, accession)
                if name == "edgartools" and (last_native is None or moment > last_native):
                    last_native = moment
        counts["accessions"] = {name: len(found) for name, found in sorted(per_class.items())}
        report_days.append({"day": _stamp(day["start"])[:10], "state": day["state"],
                            **({"error": day["error"]} if day.get("error") else {}), **counts})
    # A skip line's length is its own run's fetched length: one fetch of that length names the run's accession.
    joined, unjoined = set(), 0
    for length in capped_lengths:
        filings = length_filings.get(length, set())
        named = {filing_accession[filing] for filing in filings if filing in filing_accession}
        if len(named) == 1 and len(named) == len({filing_accession.get(filing) for filing in filings}):
            joined |= named
        else:
            unjoined += 1
    # E28 (a): the filings fetched over the cap, by era, and since the cap's merge; a fetch whose run named no
    # accession is counted apart.
    over_cap_by_era = {era_name: set() for era_name, _ in MARKS}
    since_cap: set = set()
    over_cap_unnamed = 0
    for filing, moment in over_cap_fetches:
        accession = filing_accession.get(filing)
        if accession is None:
            over_cap_unnamed += 1
            continue
        over_cap_by_era[era(moment)].add(accession)
        if moment >= cap_merged:
            since_cap.add(accession)
    logged = set().union(*whole.values())
    cut = any(day["state"] in ("partial", "unavailable") for day in days_read)
    window_days = [day for day in days_read if day["start"] < deployed and day["start"] + timedelta(days=1) > onset]
    covered = start <= onset and end >= deployed and all(day["state"] == "complete" for day in window_days)
    return {
        "days": report_days,
        "e28_window": {"from": MARKS[1][1], "to": MARKS[3][1], "covered": covered,
                       "accessions": {name: len(found) for name, found in in_window.items()},
                       "schema_two": _counted(window_schema_two)},
        "accessions": {name: len(found) for name, found in whole.items()},
        "schema_two": _counted(whole_schema_two),
        "accessions_by_era": {name: {era_name: len(found) for era_name, found in by_era.items()}
                              for name, by_era in eras.items()},
        "accessions_native_and_regex": len(whole["edgartools"] & whole["regex_fallback"]),
        "last_native_line_in_e28_window": _minute(last_native),
        "size_cap": {"cap_merged": CAP_MERGED,
                     "over_cap_accessions_by_era": {era_name: len(found) for era_name, found in over_cap_by_era.items()},
                     "over_cap_accessions_since_cap_merged": len(since_cap),
                     "over_cap_fetches_unnamed": over_cap_unnamed,
                     "size_cap_fallbacks": dict(sorted(capped_by_form.items())),
                     "size_cap_fallback_accessions": len(joined), "size_cap_fallbacks_unjoined": unjoined},
        "accessions_fetched_without_provenance": None if cut else len(fetched - logged),
    }


def bucket_retention(api, project: str) -> dict:
    """The _Default log bucket's retentionDays, where the identity may read it."""
    data, error = api.call(f"https://logging.googleapis.com/v2/projects/{quote(project)}/locations/global/buckets/_Default")
    days_kept = data.get("retentionDays") if isinstance(data, dict) else None
    if error or isinstance(days_kept, bool) or not isinstance(days_kept, int) or days_kept <= 0:
        return {"state": "unavailable", "error": error or "invalid_response", "days": None}
    return {"state": "complete", "days": days_kept}


def oldest_retained(api, project: str, start: datetime) -> dict:
    """The oldest entry the scope still holds at or after ``start``. An answer with no entries and no token holds
    none; a slow search may answer with a token alone, followed a bounded number of times."""
    body = {"resourceNames": [f"projects/{project}"], "pageSize": 1, "orderBy": "timestamp asc",
            "filter": f'timestamp>="{_stamp(start)}" AND {scope_filter()} AND {APP_STREAMS}'}
    for _page in range(PROBE_PAGES):
        data, error = api.call(ENTRIES, body)
        if error:
            return {"state": "unavailable", "error": error, "timestamp": None}
        entries = data.get("entries")
        if entries is not None and not isinstance(entries, list):
            return {"state": "unavailable", "error": "invalid_response", "timestamp": None}
        if entries:
            moment = parse_timestamp(entries[0].get("timestamp")) if isinstance(entries[0], dict) else None
            return ({"state": "complete", "timestamp": moment} if moment else
                    {"state": "unavailable", "error": "invalid_response", "timestamp": None})
        token = data.get("nextPageToken")
        if not isinstance(token, str) or not token:
            return {"state": "complete", "timestamp": None}
        body = {**body, "pageToken": token}
    return {"state": "unknown", "error": "search_incomplete", "timestamp": None}


def read_day(api, project: str, start: datetime, end: datetime, deadline: float) -> dict:
    body = {"resourceNames": [f"projects/{project}"], "pageSize": PAGE_SIZE, "orderBy": "timestamp asc",
            "filter": day_filter(start, end)}
    items, tokens = [], set()
    for _page in range(MAX_PAGES_PER_DAY):
        if time.monotonic() > deadline:
            return {"state": "partial" if items else "unavailable", "error": "time_budget", "entries": items}
        data, error = api.call(ENTRIES, body)
        if error:
            return {"state": "partial" if items else "unavailable", "error": error, "entries": items}
        entries = data.get("entries")
        if entries is not None and not isinstance(entries, list):
            return {"state": "partial" if items else "unavailable", "error": "invalid_response", "entries": items}
        items.extend(entry for entry in entries or [] if isinstance(entry, dict))
        token = data.get("nextPageToken")
        if not isinstance(token, str) or not token:
            return {"state": "complete", "entries": items}
        if token in tokens:
            return {"state": "partial", "error": "invalid_pagination", "entries": items}
        tokens.add(token)
        body = {**body, "pageToken": token}
    return {"state": "partial", "error": "page_limit", "entries": items}


def collect(api, project: str, start: str, end: str, now: datetime | None = None,
            budget: float = BUDGET_SECONDS) -> dict:
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]|[0-9]+", project):
        raise ValueError("Invalid project identifier")
    slices = days(start, end)
    deadline = time.monotonic() + budget
    now = now or datetime.now(timezone.utc)
    bucket = bucket_retention(api, project)
    probe = oldest_retained(api, project, slices[0][0])
    # The later of the bucket's boundary and the oldest retained entry dates what is gone; a quiet start is none.
    floors = [now - timedelta(days=bucket["days"])] if bucket["days"] else []
    if probe["state"] == "complete" and probe["timestamp"] and probe["timestamp"] - slices[0][0] > QUIET_START:
        floors.append(probe["timestamp"])
    floor = max(floors) if floors else None
    nothing_kept = probe["state"] == "complete" and probe["timestamp"] is None
    verified = probe["state"] == "complete"
    seen_a_line = False
    days_read = []
    for first, last in slices:
        if nothing_kept or (floor is not None and last <= floor):
            days_read.append({"start": first, "state": "expired_or_absent", "entries": []})
            continue
        read = read_day(api, project, first, last, deadline)
        state = read["state"]
        if state == "complete":
            if floor is not None and first < floor:
                state = "partly_expired_or_absent"
            elif not verified and not seen_a_line:
                # Without the probe, the first day that holds a line may have lost its earlier hours.
                state = "retention_unverified"
        seen_a_line = seen_a_line or bool(read["entries"])
        days_read.append({"start": first, "state": state, "error": read.get("error"), "entries": read["entries"]})
    report = tally(days_read, slices[0][0], slices[-1][1])
    return {
        "window": {"start": start, "end": end},
        "retention": {"bucket": {key: value for key, value in bucket.items() if value is not None},
                      "oldest_retained": {"state": probe["state"], **({"error": probe["error"]} if probe.get("error")
                                                                       else {}), "timestamp": _minute(probe["timestamp"])},
                      "gone_before": _minute(floor)},
        **report,
        "counts_basis": ("retained lines only. A day not read whole (expired_or_absent, partly_expired_or_absent, "
                         "partial, unavailable, retention_unverified) makes its counts a floor; regex_fallback counts "
                         "every form, 6-K included, so the stored excerpts' per-form counts size the E28 (b) cohort; "
                         "a cause no line names is Unverified"),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", default="excerpt-cohort/logged.json")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    days(args.start, args.end)
    if args.validate_only:
        return 0

    def gcloud(*command):
        return subprocess.check_output(["gcloud", *command], text=True, stderr=subprocess.DEVNULL).strip()

    result = collect(Logging(gcloud("auth", "print-access-token")), gcloud("config", "get-value", "project"),
                     args.start, args.end)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        os.chmod(output, 0o600)
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    # Counts only, but a public Actions log needs none of them: the receipt is the run's artifact.
    print(f"Excerpt provenance receipt saved to {output}; inspect each day's state before reading its counts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
