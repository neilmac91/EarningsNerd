"""Count the summary excerpts' builders from retained logs (E28 (a)/(b); read-only, counts only).

The `Excerpt provenance: {json}` line (summary_generation_service.get_or_cache_excerpt) is the only record of
which builder wrote an excerpt: `source` `edgartools` (native sections), `regex_fallback`, or
`legacy_cached_excerpt` (a stored excerpt reused), with the filing's `accession`. Schema 2 (E80-C1) adds
`outcome` (`unavailable`: no excerpt was built) and `fallback_reason`. The summary stream's
`[stream:<filing id>] Starting SEC fetch for URL: <url>` line names the accession it fetched, and its
`SEC fetch completed. Text length: N` line the document's length, the measure of #1347's size cap
(edgar/xbrl_sections.py `_MAX_SECTION_HTML_CHARS`).

For each UTC day of the window this reads those lines from Cloud Logging (the API service, the task worker and
the Cloud Run jobs) and counts:
- per day: lines and distinct accessions by class (a source, `unavailable`, `other`, or `unreadable`), fetches,
  and fetches over the size cap;
- over E28 (b)'s window (from the last native eval report to #1350's deploy) and over the whole read: distinct
  accessions by class, and regex and unavailable ones by schema 2's fallback_reason where a line names one;
- the last native line inside E28 (b)'s window, rounded down to its minute: native sections stopped after it,
  so it bounds the onset CI could not. A regex line bounds nothing: a 6-K, a thin native assembly, a parse
  timeout or the size cap falls back on any day, and a provenance line names no form;
- the accessions fetched over the size cap, by what their runs logged: `regex_fallback` is a size-cap
  fallback, a stored excerpt reused is not;
- the accessions fetched with no provenance line, only when every day read whole (else null).

Retention fails closed. The `_Default` bucket's `retentionDays`, where the identity may read it, dates the
oldest retained day: a day wholly before it reads `expired`, the day it falls in `partly_expired`. Without it,
the oldest entry the scope still holds (one bounded probe) stands in, with an hour's slack for a quiet start,
and a day read empty when neither could be read reads `retention_unverified`, never `complete` with 0. A day
whose pages ran out reads `partial`, one that could not be read `unavailable` with a closed class.

The receipt holds counts and minute-rounded timestamps only: no accession, filing id, URL, message text or
principal. Standard library only (the Ops runner's python3); requests are paced under Logging's read quota.

Local usage:
  python3 ops/excerpts/provenance_count.py --start 2026-10-01T00:00:00Z --end 2026-10-28T00:00:00Z \
      --output excerpt-provenance/receipt.json
"""
from __future__ import annotations

import argparse
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
SIZE_CAP = 16_000_000  # edgar/xbrl_sections.py _MAX_SECTION_HTML_CHARS since #1347
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
        except (URLError, TimeoutError, OSError, ValueError):
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
    lines = ('"Excerpt provenance:"', '"SEC fetch completed. Text length:"', '"Starting SEC fetch for URL:"')
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


def tally(days_read: list[dict]) -> dict:
    """Counts from each day's entries; the entries, accessions and filing ids never leave this function."""
    onset, deployed = _instant(MARKS[1][1]), _instant(MARKS[3][1])
    eras = {name: {era_name: set() for era_name, _ in MARKS} for name in CLASSES}
    in_window = {name: set() for name in CLASSES}
    whole = {name: set() for name in CLASSES}
    reasons: dict[str, dict[str, set]] = {}
    filing_accession: dict[str, str] = {}
    over_cap_filings: set[str] = set()
    fetched: set[str] = set()
    last_native = None
    report_days = []
    for day in days_read:
        counts = {"lines": {}, "accessions": {}, "fetches": 0, "over_size_cap_fetches": 0, "unmatched": 0}
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
                if int(done.group(2)) > SIZE_CAP:
                    counts["over_size_cap_fetches"] += 1
                    over_cap_filings.add(done.group(1))
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
            if onset <= moment < deployed:
                in_window[name].add(accession)
                reason = record.get("fallback_reason")
                if name in ("regex_fallback", "unavailable") and isinstance(reason, str):
                    reasons.setdefault(name, {}).setdefault(reason, set()).add(accession)
                if name == "edgartools" and (last_native is None or moment > last_native):
                    last_native = moment
        counts["accessions"] = {name: len(found) for name, found in sorted(per_class.items())}
        report_days.append({"day": _stamp(day["start"])[:10], "state": day["state"],
                            **({"error": day["error"]} if day.get("error") else {}), **counts})
    over_cap = {filing_accession[filing] for filing in over_cap_filings if filing in filing_accession}
    logged = set().union(*whole.values())
    # A run's provenance line follows its fetch lines within seconds, so only a day whose pages were cut (or never
    # read) can show a fetch without its provenance; a day the logs no longer hold shows neither.
    whole_read = not any(day["state"] in ("partial", "unavailable") for day in days_read)
    return {
        "days": report_days,
        "e28_window": {"from": MARKS[1][1], "to": MARKS[3][1],
                       "accessions": {name: len(found) for name, found in in_window.items()},
                       "accessions_by_fallback_reason": {
                           name: {reason: len(found) for reason, found in sorted(by_reason.items())}
                           for name, by_reason in sorted(reasons.items())}},
        "accessions": {name: len(found) for name, found in whole.items()},
        "accessions_by_era": {name: {era_name: len(found) for era_name, found in by_era.items()}
                              for name, by_era in eras.items()},
        "accessions_native_and_regex": len(whole["edgartools"] & whole["regex_fallback"]),
        "last_native_line_in_e28_window": _minute(last_native),
        "size_cap": {
            "over_cap_filings_unnamed": len(over_cap_filings - set(filing_accession)),
            "over_cap_accessions": len(over_cap),
            "size_cap_fallback": len(over_cap & whole["regex_fallback"]),
            "stored_excerpt_reused": len(over_cap & whole["legacy_cached_excerpt"] - whole["regex_fallback"]),
            "native": len(over_cap & whole["edgartools"] - whole["regex_fallback"] - whole["legacy_cached_excerpt"]),
            "none_logged": len(over_cap - logged),
        },
        "accessions_fetched_without_provenance": len(fetched - logged) if whole_read else None,
    }


def bucket_retention(api, project: str) -> dict:
    """The _Default log bucket's retentionDays, where the identity may read it."""
    data, error = api.call(f"https://logging.googleapis.com/v2/projects/{quote(project)}/locations/global/buckets/_Default")
    days_kept = data.get("retentionDays") if isinstance(data, dict) else None
    if error or not isinstance(days_kept, int) or days_kept <= 0:
        return {"state": "unavailable", "error": error or "invalid_response", "days": None}
    return {"state": "complete", "days": days_kept}


def oldest_retained(api, project: str, start: datetime) -> dict:
    """The oldest entry the scope still holds at or after ``start``, to the minute. An answer with no entries and no
    token holds none; a slow search may answer with a token alone, followed a bounded number of times."""
    body = {"resourceNames": [f"projects/{project}"], "pageSize": 1, "orderBy": "timestamp asc",
            "filter": f'timestamp>="{_stamp(start)}" AND {scope_filter()}'}
    for _page in range(PROBE_PAGES):
        data, error = api.call(ENTRIES, body)
        if error:
            return {"state": "unavailable", "error": error, "timestamp": None}
        entries = data.get("entries") or []
        moment = parse_timestamp(entries[0].get("timestamp")) if entries and isinstance(entries[0], dict) else None
        if entries:
            return ({"state": "complete", "timestamp": moment} if moment else
                    {"state": "unavailable", "error": "invalid_response", "timestamp": None})
        token = data.get("nextPageToken")
        if not isinstance(token, str) or not token:
            return {"state": "complete", "timestamp": None}
        body = {**body, "pageToken": token}
    return {"state": "unknown", "error": "search_incomplete", "timestamp": None}


def read_day(api, project: str, start: datetime, end: datetime) -> dict:
    body = {"resourceNames": [f"projects/{project}"], "pageSize": PAGE_SIZE, "orderBy": "timestamp asc",
            "filter": day_filter(start, end)}
    items, tokens = [], set()
    for _page in range(MAX_PAGES_PER_DAY):
        data, error = api.call(ENTRIES, body)
        if error:
            return {"state": "partial" if items else "unavailable", "error": error, "entries": items}
        items.extend(entry for entry in data.get("entries") or [] if isinstance(entry, dict))
        token = data.get("nextPageToken")
        if not isinstance(token, str) or not token:
            return {"state": "complete", "entries": items}
        if token in tokens:
            return {"state": "partial", "error": "invalid_pagination", "entries": items}
        tokens.add(token)
        body = {**body, "pageToken": token}
    return {"state": "partial", "error": "page_limit", "entries": items}


def collect(api, project: str, start: str, end: str, now: datetime | None = None) -> dict:
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]|[0-9]+", project):
        raise ValueError("Invalid project identifier")
    slices = days(start, end)
    now = now or datetime.now(timezone.utc)
    bucket = bucket_retention(api, project)
    boundary = now - timedelta(days=bucket["days"]) if bucket["days"] else None
    probe = oldest_retained(api, project, slices[0][0])
    oldest = probe["timestamp"]
    days_read = []
    for first, last in slices:
        if boundary is not None and last <= boundary:
            days_read.append({"start": first, "state": "expired", "entries": []})
            continue
        if boundary is None and probe["state"] == "complete" and (oldest is None or last <= oldest):
            days_read.append({"start": first, "state": "expired_or_absent", "entries": []})
            continue
        read = read_day(api, project, first, last)
        state = read["state"]
        if state == "complete":
            if boundary is not None and first < boundary:
                state = "partly_expired"
            elif boundary is None and probe["state"] == "complete" and oldest - first > QUIET_START:
                state = "partly_expired_or_absent"
            elif boundary is None and probe["state"] != "complete" and not read["entries"]:
                state = "retention_unverified"
        days_read.append({"start": first, "state": state, "error": read.get("error"), "entries": read["entries"]})
    report = tally(days_read)
    return {
        "window": {"start": start, "end": end},
        "retention": {"bucket": {key: value for key, value in bucket.items() if value is not None},
                      "boundary": _minute(boundary),
                      "oldest_retained": {"state": probe["state"], **({"error": probe["error"]} if probe.get("error")
                                                                       else {}), "timestamp": _minute(oldest)}},
        **report,
        "counts_basis": ("retained lines only. A day not read whole (expired, partly_expired, partial, unavailable, "
                         "retention_unverified) makes its counts a floor; regex_fallback counts every form, 6-K "
                         "included, so the stored excerpts' per-form counts size the E28 (b) cohort; a cause no "
                         "line names is Unverified"),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", default="excerpt-provenance/receipt.json")
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
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
