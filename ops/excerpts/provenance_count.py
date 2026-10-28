"""Count the summary excerpts' builders from retained logs (E28 (a)/(b); read-only, counts only).

The `Excerpt provenance: {json}` line (summary_generation_service.get_or_cache_excerpt) is the only record of
which builder wrote an excerpt: `source` `edgartools` (native sections), `regex_fallback`, or
`legacy_cached_excerpt` (a stored excerpt reused), with the filing's `accession`; schema 2 (E80-C1) adds
`outcome` and `fallback_reason`. The summary stream's `[stream:<filing id>] SEC fetch completed. Text length: N`
line gives the fetched document's length, the measure of #1347's 16,000,000-character size cap, and its
`Starting SEC fetch for URL: <url>` line the accession of what it fetched.

For each UTC day of the window this reads those lines from Cloud Logging (the API service, the task worker and
the Cloud Run jobs) and counts:
- per day and source: provenance lines and distinct accessions;
- over the window, per builder era (the marks below): distinct accessions per source, and accessions seen with
  both a native and a regex excerpt;
- the first regex_fallback line after the last native report, which bounds the onset CI could not;
- per day: fetches over the size cap (distinct filings), and accessions fetched with no provenance line in the
  whole window (a run that ended before its excerpt, or a builder that recorded none), a floor;
- the earliest entry Cloud Logging still holds for the scope: a day before it reads `expired_or_absent`, never 0.

Missing permissions or data are recorded as a closed class, never zeroed; a day whose pages ran out is
`partial` and its counts are a floor. The receipt holds counts only: no accession, filing id, URL, message
text or principal. Run with an existing gcloud identity; the operation that runs it is the Ops workflow's.

Local usage:
  python3 ops/excerpts/provenance_count.py --start 2026-10-01T00:00:00Z --end 2026-10-28T00:00:00Z \
      --output excerpt-provenance/receipt.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

REGION = "us-west1"
SERVICES = ("earningsnerd-backend", "earningsnerd-task-worker")
MAX_DAYS = 45
MAX_PAGES_PER_DAY = 40  # 40 x 1,000 entries; a day that needs more is partial
PAGE_SIZE = 1000
SIZE_CAP = 16_000_000  # edgar/xbrl_sections.py since #1347
# The builder eras (tasks/todo.md E28; tasks/review-evidence/e28-native-sections-2026-10-15/README.md): the last
# native eval report, the first all-regex one, #1350's deploy. The onset between the first two is unmeasured.
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


def _readout():
    """The capacity readout's Logging client (ops/capacity/readout.py): bounded pages, closed error classes."""
    path = Path(__file__).resolve().parents[1] / "capacity" / "readout.py"
    spec = importlib.util.spec_from_file_location("ops_capacity_readout", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _instant(text: str) -> datetime:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", text or ""):
        raise ValueError("timestamps are UTC, YYYY-MM-DDTHH:MM:SSZ")
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def days(start: str, end: str) -> list[tuple[str, str]]:
    """The UTC day slices of [start, end): bounded, in the past, whole days or their edges."""
    first, last = _instant(start), _instant(end)
    if not first < last <= datetime.now(timezone.utc):
        raise ValueError("the window must be non-empty and end in the past")
    if last - first > timedelta(days=MAX_DAYS):
        raise ValueError(f"the window spans at most {MAX_DAYS} days")
    slices, cursor = [], first
    while cursor < last:
        edge = min(datetime(cursor.year, cursor.month, cursor.day, tzinfo=timezone.utc) + timedelta(days=1), last)
        slices.append((_stamp(cursor), _stamp(edge)))
        cursor = edge
    return slices


def scope_filter() -> str:
    services = " OR ".join(f'"{name}"' for name in SERVICES)
    return (f'resource.labels.location="{REGION}" AND ('
            f'(resource.type="cloud_run_revision" AND resource.labels.service_name=({services})) OR '
            'resource.type="cloud_run_job")')


def day_filter(start: str, end: str) -> str:
    lines = ('"Excerpt provenance:"', '"SEC fetch completed. Text length:"', '"Starting SEC fetch for URL:"')
    payload = " OR ".join(f"textPayload:{line} OR jsonPayload.message:{line}" for line in lines)
    return f'timestamp>="{start}" AND timestamp<"{end}" AND {scope_filter()} AND ({payload})'


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
    return digits if re.fullmatch(r"\d{18}", digits) else None


def era(timestamp: str) -> str:
    label = MARKS[0][0]
    for name, mark in MARKS[1:]:
        if timestamp >= mark:
            label = name
    return label


def tally(days_read: list[dict]) -> dict:
    """Counts from each day's entries; the entries never leave this function."""
    by_source = {name: {era_name: set() for era_name, _ in MARKS} for name in (*SOURCES, "other", "unreadable")}
    native_and_regex: set[str] = set()
    seen_native: set[str] = set()
    seen_regex: set[str] = set()
    fetched_accessions: set[str] = set()
    provenance_accessions: set[str] = set()
    first_regex_after_onset = None
    report_days = []
    for day in days_read:
        counts = {"lines": {}, "accessions": {}, "over_size_cap_filings": 0, "fetches": 0}
        per_source: dict[str, set] = {}
        over_cap: set[str] = set()
        for entry in day["entries"]:
            text, stamp = message(entry), entry.get("timestamp") or day["start"]
            started = STARTED.search(text)
            if started:
                fetched_accessions.add(started.group(2))
                continue
            fetched = FETCHED.search(text)
            if fetched:
                counts["fetches"] += 1
                if int(fetched.group(2)) > SIZE_CAP:
                    over_cap.add(fetched.group(1))
                continue
            record = provenance(text)
            accession = _accession(record.get("accession")) if record else None
            source = record.get("source") if record else None
            name = source if source in SOURCES else ("other" if record else "unreadable")
            counts["lines"][name] = counts["lines"].get(name, 0) + 1
            if accession is None:
                continue
            provenance_accessions.add(accession)
            per_source.setdefault(name, set()).add(accession)
            by_source[name][era(stamp)].add(accession)
            if name == "edgartools":
                seen_native.add(accession)
            elif name == "regex_fallback":
                seen_regex.add(accession)
                if stamp >= MARKS[1][1] and (first_regex_after_onset is None or stamp < first_regex_after_onset):
                    first_regex_after_onset = stamp
        counts["accessions"] = {name: len(found) for name, found in sorted(per_source.items())}
        counts["over_size_cap_filings"] = len(over_cap)
        report_days.append({"day": day["start"][:10], "state": day["state"], **({"error": day["error"]} if
                            day.get("error") else {}), **counts})
    native_and_regex = seen_native & seen_regex
    return {
        "days": report_days,
        "accessions_by_source_and_era": {
            name: {era_name: len(found) for era_name, found in eras.items()} for name, eras in by_source.items()
        },
        "accessions_native_and_regex": len(native_and_regex),
        "first_regex_fallback_after_last_native_report": first_regex_after_onset,
        "accessions_fetched_without_provenance": len(fetched_accessions - provenance_accessions),
    }


def earliest_retained(api, project: str, start: str) -> dict:
    """The oldest entry Cloud Logging still holds for the scope at or after ``start``: its timestamp alone, from one
    request (never paged)."""
    data, error = api.request("https://logging.googleapis.com/v2/entries:list", {
        "resourceNames": [f"projects/{project}"], "pageSize": 1, "orderBy": "timestamp asc",
        "filter": f'timestamp>="{start}" AND {scope_filter()}'}, post=True)
    entries = data.get("entries") if isinstance(data, dict) else None
    if error or not isinstance(entries, list):
        return {"state": "unavailable", "error": error or "invalid_response", "timestamp": None}
    stamp = entries[0].get("timestamp") if entries and isinstance(entries[0], dict) else None
    return {"state": "complete", "timestamp": stamp if isinstance(stamp, str) else None}


def collect(api, project: str, start: str, end: str) -> dict:
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]|[0-9]+", project):
        raise ValueError("Invalid project identifier")
    slices = days(start, end)
    retained = earliest_retained(api, project, start)
    days_read = []
    oldest = retained["timestamp"]
    for first, last in slices:
        # A day wholly before the oldest retained entry reads as gone or empty, never as zero; a day it starts in
        # is partly gone. With no entry retained at all, every day is.
        if retained["state"] == "complete" and (oldest is None or last <= oldest):
            days_read.append({"start": first, "state": "expired_or_absent", "entries": []})
            continue
        api_pages = api.pages("https://logging.googleapis.com/v2/entries:list", {
            "resourceNames": [f"projects/{project}"], "pageSize": PAGE_SIZE, "orderBy": "timestamp asc",
            "filter": day_filter(first, last)}, "entries", post=True)
        state = api_pages.get("state")
        if state == "complete" and oldest and first < oldest:
            state = "partly_expired"
        days_read.append({"start": first, "state": state, "error": api_pages.get("error"),
                          "entries": [item for item in api_pages.get("items") or [] if isinstance(item, dict)]})
    report = tally(days_read)
    return {"window": {"start": start, "end": end}, "earliest_retained": retained, **report,
            "counts_basis": "retained lines only; a partial, partly_expired, unavailable or expired_or_absent day makes "
                            "its counts a floor, and a cause the lines do not name is Unverified"}


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
    readout = _readout()
    readout.MAX_PAGES = MAX_PAGES_PER_DAY

    def gcloud(*command):
        return subprocess.check_output(["gcloud", *command], text=True, stderr=subprocess.DEVNULL).strip()

    api = readout.Api(gcloud("auth", "print-access-token"))
    result = collect(api, gcloud("config", "get-value", "project"), args.start, args.end)
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
