"""Read only the 2026-10-30 REGN incident; emit classifications, never raw logs.

The scope is fixed in reviewed code. No arguments or environment values select a
query. At most 501 entries are requested (one lookahead); only 500 are classified.
Raw stdout is captured, never printed or retained as an artifact. A response over
8 MiB is refused before decoding; gcloud's stderr is discarded. The entry limit
also bounds the upstream response; the byte limit is a post-capture acceptance
limit, not a subprocess memory limit. See docs/OPERATIONS.md for interpretation.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

PROJECT = "earnings-nerd"
SERVICE = "earningsnerd-backend"
REVISION = "earningsnerd-backend-00661-zr9"
START = "2026-10-30T11:00:00Z"
END = "2026-10-30T11:15:00Z"
FILING_IDS = (45003, 45004)
MAX_ENTRIES = 500
MAX_BYTES = 8 * 1024 * 1024
TIMEOUT_SECONDS = 60
PREFIX = re.compile(r"^\[stream:(45003|45004)\] (.*)", re.DOTALL)
STAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,9})?Z")
# HTTPX's generated status prefix, immediately after this transport's wrapper.
# Never interpret arbitrary numbers in a URL, response body or traceback as a status.
HTTP_STATUS = re.compile(r"^Failed to fetch document: (?:Client|Server) error '([45][0-9]{2})(?: [^'\n]*)?' for url '")
EXCEPTION_CLASSES = (
    ("timeout", ("httpx.ReadTimeout", "httpx.ConnectTimeout", "httpx.WriteTimeout", "httpx.PoolTimeout", "TimeoutError")),
    ("connection_error", ("httpx.ConnectError", "httpx.ReadError", "httpx.WriteError", "httpx.RemoteProtocolError")),
    ("invalid_url", ("httpx.InvalidURL", "httpx.UnsupportedProtocol")),
)


def command() -> list[str]:
    """The sole outbound operation; fields and targets are code-owned."""
    query = (
        f'resource.type="cloud_run_revision" AND resource.labels.service_name="{SERVICE}" '
        f'AND resource.labels.revision_name="{REVISION}" '
        f'AND timestamp>="{START}" AND timestamp<"{END}" '
        'AND (jsonPayload.message:"[stream:45003]" OR jsonPayload.message:"[stream:45004]" '
        'OR textPayload:"[stream:45003]" OR textPayload:"[stream:45004]")'
    )
    return ["gcloud", "logging", "read", query, f"--project={PROJECT}",
            f"--limit={MAX_ENTRIES + 1}", "--order=asc",
            "--format=json(timestamp,resource.type,resource.labels.service_name,resource.labels.revision_name,"
            "jsonPayload.message,jsonPayload.exception,textPayload)"]


def classify_error(message: str, exception: str) -> tuple[str, int | None]:
    """Return closed reason codes. Matching text is never returned."""
    if match := HTTP_STATUS.match(message):
        status = int(match.group(1))
        reason = {403: "http_forbidden", 429: "http_rate_limited", 404: "http_not_found"}.get(
            status, "http_server_error" if status >= 500 else "http_other_client_error")
        return reason, status
    if message.startswith("SEC EDGAR circuit breaker is open:"):
        return "circuit_open", None
    if message == "Filing document is empty or inaccessible":
        return "empty_document", None
    for reason, classes in EXCEPTION_CLASSES:
        if any(re.search(r"(?:^|\n)" + re.escape(name) + r":", exception) for name in classes):
            return reason, None
    return "unclassified", None


def project_entry(record: Any) -> dict[str, Any] | None:
    """Independently check scope; project only validated primitives and enums."""
    if not isinstance(record, dict):
        return None
    resource = record.get("resource")
    if not isinstance(resource, dict) or resource.get("type") != "cloud_run_revision":
        return None
    labels = resource.get("labels")
    if not isinstance(labels, dict) or labels.get("service_name") != SERVICE or labels.get("revision_name") != REVISION:
        return None
    stamp = record.get("timestamp")
    if not isinstance(stamp, str) or not STAMP.fullmatch(stamp):
        return None
    try:
        instant = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if not datetime.fromisoformat(START.replace("Z", "+00:00")) <= instant < datetime.fromisoformat(END.replace("Z", "+00:00")):
        return None
    payload = record.get("jsonPayload")
    payload = payload if isinstance(payload, dict) else {}
    message = payload.get("message", record.get("textPayload"))
    if not isinstance(message, str) or not (match := PREFIX.match(message)):
        return None
    filing_id, message = int(match.group(1)), match.group(2)
    exception = payload.get("exception", "")
    exception = exception if isinstance(exception, str) else ""
    stage, reason, status = "other_stream_event", None, None
    if message.startswith("Error fetching SEC document: "):
        stage = "document_fetch_error"
        reason, status = classify_error(message.removeprefix("Error fetching SEC document: "), exception)
    elif message.startswith("Starting SEC fetch for URL: "):
        stage = "document_fetch_started"
    elif message.startswith("SEC fetch completed. Text length: "):
        stage = "document_fetched"
    elif message == "Skipping main thread SEC fetch, using cache.":
        stage = "document_cache_hit"
    elif message == "Yielding fetching stage":
        stage = "fetching"
    elif message.startswith("SEC fetch heartbeat "):
        stage = "document_fetch_waiting"
    elif message.startswith("Pipeline timeout after "):
        stage, reason = "pipeline_error", "timeout"
    elif message.startswith("Error in streaming summary: "):
        stage, reason = "pipeline_error", "unclassified"
    return {"timestamp": instant.astimezone(timezone.utc).isoformat(), "filing_id": filing_id,
            "stage": stage, "reason": reason, "upstream_http_status": status}


def receipt(records: Any) -> dict[str, Any]:
    """A capped or malformed read is never reported as a complete census."""
    if not isinstance(records, list):
        return unavailable("invalid_response")
    entries = []
    rejected = 0
    for record in records[:MAX_ENTRIES]:
        if (entry := project_entry(record)) is None:
            rejected += 1
        else:
            entries.append(entry)
    state = "truncated" if len(records) > MAX_ENTRIES else "partial" if rejected else "complete"
    return {"schema_version": 1, "state": state,
            "scope": {"filing_ids": list(FILING_IDS), "start": START, "end": END, "revision": REVISION},
            "entry_limit": MAX_ENTRIES, "scope_or_shape_rejected": rejected, "entries": entries}


def unavailable(reason: str) -> dict[str, Any]:
    return {"schema_version": 1, "state": "unavailable", "reason": reason, "entries": []}


def collect() -> dict[str, Any]:
    try:
        raw = subprocess.check_output(command(), stderr=subprocess.DEVNULL, timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return unavailable("command_timeout")
    except subprocess.CalledProcessError:
        return unavailable("gcloud_failed")
    except OSError:
        return unavailable("command_unavailable")
    if len(raw) > MAX_BYTES:
        return unavailable("response_size_limit")
    try:
        return receipt(json.loads(raw))
    except (ValueError, TypeError, RecursionError):
        return unavailable("invalid_response")


def main() -> int:
    # No future caller can accidentally turn this fixed read into an input-driven query.
    result = unavailable("arguments_not_supported") if len(sys.argv) != 1 else collect()
    print(json.dumps(result, sort_keys=True))
    return 1 if result["state"] == "unavailable" else 0


if __name__ == "__main__":
    raise SystemExit(main())
