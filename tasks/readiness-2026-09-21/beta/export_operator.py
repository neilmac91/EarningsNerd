#!/usr/bin/env python3
"""Founder-side PostHog file-download batch-export operator and verifier.

Implements the readout contract (revision 3) section 2.0 lifecycle, steps 1-8, for
the founder-operated route (decision D1 option O2) and the founder-side private
store (decision D3). The founder runs it on their own machine; nothing else does.

  1. record the project identity as given (no project-get call);
  2. count-rows with the bound query -> n_before; n_before >= 10000 stops with the
     verdict ``incomplete (cap)`` before any create;
  3. ONE create per invocation with the identical hogql_query bytes, file
     {format: JSONLines, compression: null, max_size_mb: null} and
     hogql_modifiers {convertToProjectTimezone: false} -> run_id;
  4. poll retrieve at a bounded interval until a terminal status; a 5xx or a
     transport error on a poll is retried until the deadline; anything other than
     Completed, or an ``error`` field, is ``source-unavailable``; FailedBilling or any
     response text naming payment, plan (whole word), billing, trial or quota stops
     the run: the HTTP status, the matched word and the redacted structured error
     fields are printed; the raw response stays in the private store (no PostHog
     charge is authorised);
  5. count-rows again -> n_after;
  6. one GET per id in files[] in order, following the single 302 by hand: the
     Location value lives in a local variable only; raw bytes saved; sha256 and
     byte length per part;
  7. parse and verify each part as JSONLines: BOM, CR bytes, trailing newline,
     duplicate lines, key set equal to the 21 released aliases, key order recorded;
  8. completeness verdict per section 2.0 step 8: when file_export_to_v1.py sits
     beside this script its file_export_completeness record IS the verdict (single
     rule owner); otherwise a byte-equivalent inline fallback runs, and the receipt
     names which rule ran.

``--resume RUN_ID --n-before N`` runs steps 4-8 only (zero creates) for a run that
an earlier invocation created, carrying n_before from that invocation's saved
count response; the receipt states that n_before is carried.

Outputs, under <private-dir>/<label>-<run_id>/ (files 0600, directories 0700):
bound-query.hogql, responses/*.json (every response as returned, UTC-stamped),
parts/*.jsonl, VERIFICATION.json, v1-events.json (only when the adapter module is
present), RECEIPT-PUBLIC.json (hashes, counts, ids, statuses, the verdict class
with the sha256/length of the verdict text, window, N, exclusion count, labels,
UTC times - nothing else) and CUSTODY.txt (sha256 and byte length per file plus a
TOTAL=<files> <bytes> line, also printed).

``--offline-verify PART [PART ...] --run-record JSON --n-before N [--n-after N]``
runs steps 7-8 only on existing parts, with no network call.

Redaction: before anything reaches stdout or RECEIPT-PUBLIC.json, every
``hogql_query`` value and every occurrence of the bound query text is replaced by
``<bound query; sha256 ...>``. This script never prints, logs or writes the personal
API key (read only from the environment variable POSTHOG_PERSONAL_API_KEY), a
signed URL or Location header, or the content of any row. Standard library only;
Python 3.11+.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
KEY_ENV = "POSTHOG_PERSONAL_API_KEY"
LIMIT_CAP = 10_000
MAX_QUERY_BYTES = 1024 * 1024
MAX_API_BYTES = 4 * 1024 * 1024
MAX_PART_BYTES = 512 * 1024 * 1024
USER_AGENT = "earningsnerd-export-operator/1 (python stdlib urllib)"
TERMINAL_STATUSES = {
    "Completed", "Cancelled", "Failed", "FailedRetryable", "FailedBilling", "Terminated", "TimedOut",
}
REDIRECT_CODES = (301, 302, 303, 307, 308)
PRICING_TERMS = ("payment", "plan", "billing", "trial", "quota")  # plan(s) whole word; the rest substrings
PRICING_WORD = re.compile(r"\bplans?\b", re.IGNORECASE)
HOGQL_VALUE = re.compile(r'("hogql_query"\s*:\s*)"(?:[^"\\]|\\.)*"')
INVENTORY_KEYS = ("id", "sha256", "bytes", "rows")
LABEL_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,39}")
UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
UUID_PATTERN = re.compile(UUID)
PART_NAME_PATTERN = re.compile(r"posthog-hogql-(" + UUID + r")-(" + UUID + r")\.jsonl")
OPERATOR_LABEL = "founder-operated (decision D1 option O2)"
EMBEDDED_FIELDS = (
    "evidence_version", "auth_state_at_event", "account_id_at_event",
    "analytics_consent_at_event", "filing_id", "summary_id", "request_id",
    "logical_request_id", "client_attempt", "transport_attempt", "identity_evidence",
    "consent_evidence", "outcome", "delivery_path", "summary_service_invoked",
    "duration_ms", "reason", "entry_point",
)
EMBEDDED_COLUMNS = ["uuid", "event", "timestamp_s", *[f"{name}_json" for name in EMBEDDED_FIELDS]]

EXIT_COMPLETE = 0
EXIT_INCOMPLETE = 2
EXIT_SOURCE_UNAVAILABLE = 3
EXIT_STOP = 4
EXIT_REFUSED = 5

# Redaction context: the bound query text and its sha256, set once per export run.
_REDACTION: dict[str, str] = {}


class Refused(Exception):
    """Usage or safety refusal raised before any network call."""


class SourceUnavailable(Exception):
    """Connector/HTTP failure or malformed response: an unknown, never a zero."""


class PricingStop(Exception):
    """A billing/pricing signal: stop at once; no PostHog charge is authorised."""

    def __init__(self, word: str, http_status: int | None, summary: str) -> None:
        super().__init__(word)
        self.word = word
        self.http_status = http_status
        self.summary = summary  # redacted structured fields only; the raw response stays in responses/


def _say(line: str) -> None:
    """The only stdout site. Callers pass counts, hashes, ids, statuses, verdicts and
    redacted connector-leg error summaries: never the key, never a row, never a signed URL."""
    sys.stdout.write(_redact(line) + "\n")
    sys.stdout.flush()


def _redact(text: str) -> str:
    """Replace every hogql_query value and every occurrence of the bound query text."""
    text = HOGQL_VALUE.sub(lambda match: match.group(1) + '"<hogql_query redacted>"', text)
    query = _REDACTION.get("query")
    if query:
        marker = f"<bound query; sha256 {_REDACTION.get('sha256', '')}>"
        text = text.replace(query, marker)
        escaped = json.dumps(query)[1:-1]
        if escaped != query:
            text = text.replace(escaped, marker)
    return text


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_bytes(path: Path, data: bytes) -> None:
    """Exclusive create, mode 0600: outputs are never overwritten."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)


def _write_json(path: Path, payload: Any) -> None:
    _write_bytes(path, (json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8"))


def _git_ancestor(path: Path) -> bool:
    return any((candidate / ".git").exists() for candidate in (path, *path.parents))


def _prepare_private_dir(raw: str) -> Path:
    path = Path(raw).expanduser().resolve()
    if _git_ancestor(path):
        raise Refused(
            "--private-dir lies inside a git work tree (a .git ancestor exists); "
            "choose a directory outside any repository (decision D3)"
        )
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def _load_columns() -> tuple[list[str], str]:
    """The 21 released aliases: readout_v1.COLUMNS when that file sits beside this script."""
    if (SCRIPT_DIR / "readout_v1.py").exists():
        if str(SCRIPT_DIR) not in sys.path:
            sys.path.insert(0, str(SCRIPT_DIR))
        module = importlib.import_module("readout_v1")
        columns = list(module.COLUMNS)
        note = "" if columns == EMBEDDED_COLUMNS else " (differs from the embedded list; the released consumer governs)"
        return columns, "readout_v1.COLUMNS" + note
    return list(EMBEDDED_COLUMNS), "embedded (readout_v1.py not present beside the script)"


def _load_adapter() -> Any | None:
    """file_export_to_v1 (decision D5, Option A) when it sits beside this script; else None."""
    if not (SCRIPT_DIR / "file_export_to_v1.py").exists():
        return None
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    return importlib.import_module("file_export_to_v1")


def _pricing_terms(text: str) -> list[str]:
    """plan/plans as whole words; payment, billing, trial, quota as substrings (adapter semantics)."""
    lowered = text.lower()
    matched: list[str] = []
    for term in PRICING_TERMS:
        hit = PRICING_WORD.search(text) is not None if term == "plan" else term in lowered
        if hit:
            matched.append(term)
    return matched


def _pricing_signal(status: Any, text: str) -> str | None:
    if status == "FailedBilling":
        return "FailedBilling"
    terms = _pricing_terms(text)
    return terms[0] if terms else None


def _strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def verify_part(data: bytes, columns: list[str]) -> dict[str, Any]:
    """Step 7 for one part. Returns counts, hashes and key names only: no row content."""
    expected = set(columns)
    deviations: list[str] = []
    bom = (
        "utf-8" if data.startswith(b"\xef\xbb\xbf")
        else "utf-16-le" if data.startswith(b"\xff\xfe")
        else "utf-16-be" if data.startswith(b"\xfe\xff")
        else None
    )
    if bom:
        deviations.append(f"byte order mark present ({bom})")
    cr_bytes = data.count(b"\r")
    if cr_bytes:
        deviations.append(f"{cr_bytes} CR byte(s) present")
    ends_with_newline = data.endswith(b"\n")
    trailing_newline_count = len(data) - len(data.rstrip(b"\n"))
    if data and not ends_with_newline:
        deviations.append("no terminal newline")
    if trailing_newline_count > 1:
        deviations.append(f"{trailing_newline_count} trailing newlines (one expected)")
    lines = data.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()  # the single trailing empty element produced by the terminal LF
    duplicate_lines = sum(count - 1 for count in Counter(lines).values() if count > 1)
    if duplicate_lines:
        deviations.append(f"{duplicate_lines} duplicate line(s)")

    flags: list[bool] = []

    def hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        keys = [key for key, _ in pairs]
        if len(keys) != len(set(keys)):
            flags.append(True)
        return dict(pairs)

    rows = empty_lines = undecodable_lines = non_object_lines = duplicate_key_rows = 0
    key_set_equal_rows = key_order_equal_rows = 0
    missing: set[str] = set()
    extra: set[str] = set()
    key_orders: list[list[str]] = []
    timestamp_types: Counter[str] = Counter()
    uuids: Counter[str] = Counter()
    order_keys: list[tuple[Any, Any]] = []
    for line in lines:
        if not line.strip():
            empty_lines += 1
            continue
        flags.clear()
        try:
            value = json.loads(line.decode("utf-8"), object_pairs_hook=hook)
        except (UnicodeDecodeError, ValueError):
            undecodable_lines += 1
            continue
        if flags:
            duplicate_key_rows += 1
        if not isinstance(value, dict):
            non_object_lines += 1
            continue
        rows += 1
        keys = list(value.keys())
        if set(keys) == expected:
            key_set_equal_rows += 1
        else:
            missing |= expected - set(keys)
            extra |= set(keys) - expected
        if keys == columns:
            key_order_equal_rows += 1
        if keys not in key_orders and len(key_orders) < 8:
            key_orders.append(keys)
        timestamp_types[type(value.get("timestamp_s")).__name__] += 1
        uuid_value = value.get("uuid")
        if isinstance(uuid_value, str):
            uuids[uuid_value] += 1
        order_keys.append((value.get("timestamp_s"), uuid_value))
    ordered: bool | None = None
    if order_keys and all(type(ts) is int and isinstance(uid, str) for ts, uid in order_keys):
        ordered = all(order_keys[i] <= order_keys[i + 1] for i in range(len(order_keys) - 1))
    duplicate_uuids = sum(count - 1 for count in uuids.values() if count > 1)
    if empty_lines:
        deviations.append(f"{empty_lines} empty line(s) besides the terminal newline")
    if undecodable_lines:
        deviations.append(f"{undecodable_lines} line(s) not decodable as UTF-8 JSON")
    if non_object_lines:
        deviations.append(f"{non_object_lines} line(s) whose JSON is not an object")
    if duplicate_key_rows:
        deviations.append(f"{duplicate_key_rows} row(s) with duplicate keys inside the object")
    if rows - key_set_equal_rows:
        deviations.append(f"key set differs from the {len(columns)} aliases on {rows - key_set_equal_rows} of {rows} rows")
    if rows and key_order_equal_rows != rows:
        deviations.append(f"key order differs from the projection on {rows - key_order_equal_rows} of {rows} rows")
    if duplicate_uuids:
        deviations.append(f"{duplicate_uuids} duplicate uuid value(s) within the part")
    other_types = sorted(set(timestamp_types) - {"int"})
    if other_types:
        deviations.append(f"timestamp_s rendered as {other_types} (integer expected) on some rows")
    if ordered is False:
        deviations.append("rows are not ordered by (timestamp_s, uuid)")
    return {
        "bytes": len(data),
        "sha256": _sha256(data),
        "bom": bom,
        "cr_bytes": cr_bytes,
        "ends_with_newline": ends_with_newline,
        "trailing_newline_count": trailing_newline_count,
        "lines": len(lines),
        "rows": rows,
        "empty_lines": empty_lines,
        "undecodable_lines": undecodable_lines,
        "non_object_lines": non_object_lines,
        "duplicate_lines": duplicate_lines,
        "rows_with_duplicate_keys": duplicate_key_rows,
        "key_set_equal_rows": key_set_equal_rows,
        "key_set_deviant_rows": rows - key_set_equal_rows,
        "missing_keys_seen": sorted(missing),
        "extra_keys_seen": sorted(extra),
        "key_order_equals_projection_rows": key_order_equal_rows,
        "key_orders_observed": key_orders,
        "expected_key_order": list(columns),
        "timestamp_s_types": dict(sorted(timestamp_types.items())),
        "duplicate_uuids": duplicate_uuids,
        "rows_ordered_by_timestamp_then_uuid": ordered,
        "deviations": deviations,
    }


def completeness_inline(
    run_record: dict[str, Any],
    parts: list[dict[str, Any]],
    n_before: int | None,
    n_after: int | None,
    source_availability_recorded: bool = False,
) -> dict[str, Any]:
    """Fallback only: byte-equivalent to file_export_to_v1.file_export_completeness (contract
    section 2.0 step 8). ``error`` fails only when present and not in (None, ""); plan/plans
    match as whole words, the other pricing terms as substrings; zero rows are complete only
    with the explicit source-availability flag."""
    failing: list[str] = []
    status = run_record.get("status")
    if status != "Completed":
        failing.append(f"status {status!r} is not Completed")
    if "error" in run_record and run_record.get("error") not in (None, ""):
        failing.append(f"error field present: {run_record['error']!r}")
    inventory: dict[str, dict[str, Any]] = {}
    for part in parts:
        if not isinstance(part, dict) or any(key not in part for key in INVENTORY_KEYS):
            failing.append(f"part inventory entry lacks {'/'.join(INVENTORY_KEYS)}: {part!r}")
        else:
            inventory[part["id"]] = part
    rows_parsed = sum(part["rows"] for part in inventory.values())
    records_completed = run_record.get("records_completed")
    counts = {
        "n_before": n_before, "n_after": n_after, "records_completed": records_completed, "rows_parsed": rows_parsed,
    }
    for name, value in counts.items():
        if value is None:
            failing.append(f"{name} not observed")
        elif type(value) is not int:
            failing.append(f"{name} is not an integer: {value!r}")
    if len({value for value in counts.values() if type(value) is int}) > 1:
        failing.append("counts differ: " + ", ".join(f"{name}={value!r}" for name, value in counts.items()))
    if type(n_before) is int and n_before >= LIMIT_CAP:
        failing.append(f"n_before {n_before} is not below the LIMIT cap {LIMIT_CAP}")
    declared = run_record.get("files")
    if isinstance(declared, list) and all(isinstance(item, str) for item in declared):
        failing.extend(f"file {file_id} not downloaded and hashed" for file_id in declared if file_id not in inventory)
        failing.extend(
            f"part {part_id} is not in this run's files inventory" for part_id in inventory if part_id not in declared
        )
    else:
        failing.append("files inventory absent from the run record")
    if status == "FailedBilling":
        failing.append("status FailedBilling (pricing signal)")
    for text in _strings(run_record):
        terms = _pricing_terms(text)
        if terms:
            failing.append(f"pricing signal {terms} in run record text: {text!r}")
    if rows_parsed == 0 and not source_availability_recorded:
        failing.append("zero rows without a source-availability record")
    return {
        "status": status,
        "error": run_record.get("error"),
        "records_completed": records_completed,
        "n_before": n_before,
        "n_after": n_after,
        "rows_parsed": rows_parsed,
        "files": list(parts),
        "file_export_complete_observed": not failing,
        "failing_rules": failing,
    }


def _verdict_text(completeness: dict[str, Any]) -> str:
    if completeness.get("file_export_complete_observed"):
        return "complete (zero rows)" if completeness.get("rows_parsed") == 0 else "complete"
    rules = completeness.get("failing_rules") or ["no failing rule listed"]
    return "incomplete (" + "; ".join(str(rule) for rule in rules) + ")"


def _verdict_class(verdict: str) -> str:
    """The public verdict class; the full verdict text stays in VERIFICATION.json (hash and length in the receipt)."""
    if verdict.startswith("source-unavailable (pricing signal"):
        return "source-unavailable (pricing signal)"
    for prefix in ("complete (zero rows)", "incomplete (cap)"):
        if verdict.startswith(prefix):
            return prefix
    return verdict.split(" (")[0]


def _public_rules(rules: list[Any]) -> list[str]:
    """Failing rules for the receipt: rule statements only; remote text stays in VERIFICATION.json."""
    public: list[str] = []
    for rule in rules:
        text = str(rule)
        if text.startswith("error field present"):
            public.append("error field present (text in VERIFICATION.json)")
        elif text.startswith("pricing signal") and " in run record text" in text:
            public.append("pricing signal in run record text (text in VERIFICATION.json)")
        else:
            public.append(_redact(text))
    return public


def _completeness(
    adapter: Any | None,
    run_record: dict[str, Any],
    parts: list[dict[str, Any]],
    n_before: int | None,
    n_after: int | None,
    source_availability_recorded: bool,
) -> tuple[dict[str, Any], str]:
    """Step 8 has one owner: the adapter when present beside the script, else the inline fallback."""
    summary = [
        {"id": part.get("id"), "sha256": part.get("sha256"), "bytes": part.get("bytes"), "rows": part.get("rows")}
        for part in parts
        if part.get("sha256") and part.get("rows") is not None
    ]
    if adapter is not None and hasattr(adapter, "file_export_completeness"):
        try:
            try:
                result = adapter.file_export_completeness(
                    run_record, summary, n_before, n_after, source_availability_recorded=source_availability_recorded,
                )
                source = "file_export_to_v1.file_export_completeness"
            except TypeError:
                result = adapter.file_export_completeness(run_record, summary, n_before, n_after)
                source = (
                    "file_export_to_v1.file_export_completeness (adapter without the source_availability_recorded "
                    "keyword; its own zero-row default applied)"
                )
        except Exception as err:  # noqa: BLE001 - the adapter is another module; record, never crash
            result = {
                "status": run_record.get("status"), "error": run_record.get("error"),
                "records_completed": run_record.get("records_completed"), "n_before": n_before, "n_after": n_after,
                "rows_parsed": None, "files": summary, "file_export_complete_observed": False,
                "failing_rules": [f"adapter completeness raised {type(err).__name__}"],
            }
            source = "file_export_to_v1.file_export_completeness (raised; recorded, nothing verified)"
        if not isinstance(result, dict):
            result = {
                "rows_parsed": None, "files": summary, "file_export_complete_observed": False,
                "failing_rules": ["adapter completeness returned a non-dict record"],
            }
        result.setdefault("failing_rules", [])
        result["verdict"] = _verdict_text(result)
        return result, source
    result = completeness_inline(run_record, summary, n_before, n_after, source_availability_recorded)
    result["verdict"] = _verdict_text(result)
    return result, (
        "inline fallback (file_export_to_v1.py not present beside the script; byte-equivalent to its "
        "file_export_completeness)"
    )


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow a redirect automatically (urllib would forward the bearer header)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _read_error_body(err: urllib.error.HTTPError) -> bytes:
    try:
        return err.read(MAX_API_BYTES + 1) if getattr(err, "fp", None) is not None else b""
    except Exception:  # noqa: BLE001
        return b""


def _api_call(
    host: str, path: str, key: str, method: str, body: dict[str, Any] | None, timeout: float,
) -> tuple[int, bytes, str | None]:
    """Connector leg (count-rows, create, retrieve). Returns (http_status, raw_body, request_compact_json_sha256)."""
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json", "User-Agent": USER_AGENT}
    data = None
    request_sha = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request_sha = _sha256(data)
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(host + path, data=data, headers=headers, method=method)
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            return response.status, response.read(MAX_API_BYTES + 1), request_sha
    except urllib.error.HTTPError as err:
        return err.code, _read_error_body(err), request_sha
    except (urllib.error.URLError, OSError) as err:
        raise SourceUnavailable(f"{type(err).__name__} during {method} {path}") from None


def _download_part(host: str, path: str, key: str, timeout: float) -> tuple[int, int, bytes]:
    """Download leg: one authenticated GET, one redirect followed by hand.

    The Location value is held in the local variable ``target`` only; it is never
    written, printed or returned, and the bearer header is not sent to it unless its
    host is the API host. Returns (first_response_status, body_fetch_status, body)."""
    url = host + path
    first = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {key}", "User-Agent": USER_AGENT}, method="GET",
    )
    try:
        with _OPENER.open(first, timeout=timeout) as response:
            return response.status, response.status, response.read(MAX_PART_BYTES + 1)
    except urllib.error.HTTPError as err:
        if err.code not in REDIRECT_CODES:
            return err.code, err.code, _read_error_body(err)
        first_status = err.code
        location = err.headers.get("Location")
        if not location:
            raise SourceUnavailable("redirect without a Location header") from None
        target = urllib.parse.urljoin(url, location)
        del location
    except (urllib.error.URLError, OSError) as err:
        raise SourceUnavailable(f"{type(err).__name__} during download GET") from None
    split = urllib.parse.urlsplit(target)
    if split.scheme != "https" or not split.netloc:
        raise SourceUnavailable("redirect target is not an https URL; not followed")
    headers = {"User-Agent": USER_AGENT}
    if split.netloc.lower() == urllib.parse.urlsplit(host).netloc.lower():
        headers["Authorization"] = f"Bearer {key}"
    second = urllib.request.Request(target, headers=headers, method="GET")
    del target
    try:
        with _OPENER.open(second, timeout=timeout) as response:
            return first_status, response.status, response.read(MAX_PART_BYTES + 1)
    except urllib.error.HTTPError as err:
        return first_status, err.code, _read_error_body(err)  # a second redirect surfaces here: not followed
    except (urllib.error.URLError, OSError) as err:
        raise SourceUnavailable(f"{type(err).__name__} during redirected download GET") from None


def _bounded_error_summary(body: bytes) -> str:
    """Redacted structured fields of a failed response only; never a body that could hold rows."""
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return f"non-JSON body of {len(body)} bytes (not printed)"
    if not isinstance(payload, dict) or "uuid" in payload:
        return f"JSON body of {len(body)} bytes (not printed)"
    fields = {name: str(payload[name])[:300] for name in ("type", "code", "detail", "attr") if name in payload}
    if not fields:
        return f"JSON object without type/code/detail fields ({len(body)} bytes, not printed)"
    return _redact(json.dumps(fields, sort_keys=True))


def _connector_check(status_code: int, body: bytes, what: str, retry_5xx: bool = False) -> dict[str, Any] | None:
    """Pricing stop first (redacted summary), then HTTP status, then the JSON object.
    With ``retry_5xx`` a 5xx returns None so the caller can retry until its deadline."""
    text = body.decode("utf-8", "replace")
    try:
        payload = json.loads(text) if text.strip() else {}
    except ValueError:
        payload = None
    status_value = payload.get("status") if isinstance(payload, dict) else None
    word = _pricing_signal(status_value, text)
    if word:
        raise PricingStop(word, status_code, _bounded_error_summary(body))
    if retry_5xx and 500 <= status_code <= 599:
        return None
    if status_code not in (200, 201):
        raise SourceUnavailable(f"{what}: HTTP {status_code}; {_bounded_error_summary(body)}")
    if not isinstance(payload, dict):
        raise SourceUnavailable(f"{what}: response is not a JSON object")
    return payload


def _save_response(
    run_dir: Path, seq: int, name: str, method: str, path: str, status: int, body: bytes, request_sha: str | None,
) -> dict[str, Any]:
    """Every response is saved exactly as returned, UTC-stamped, under responses/."""
    utc = _utc_now()
    file_name = f"{seq:02d}-{name}-{_stamp()}.json"
    _write_bytes(run_dir / "responses" / file_name, body)
    return {
        "seq": seq, "name": name, "method": method, "path": path, "http_status": status, "utc": utc,
        "response_file": f"responses/{file_name}", "response_sha256": _sha256(body), "response_bytes": len(body),
        "request_compact_json_sha256": request_sha,
    }


def _part_line(entry: dict[str, Any]) -> str:
    report = entry["verification"]
    return (
        f"part {entry['index']} {entry.get('id')}: sha256={entry['sha256']} bytes={entry['bytes']} "
        f"rows={report['rows']} key_set_equal_rows={report['key_set_equal_rows']} "
        f"key_order_equals_projection_rows={report['key_order_equals_projection_rows']} bom={report['bom']} "
        f"cr_bytes={report['cr_bytes']} ends_with_newline={report['ends_with_newline']} "
        f"duplicate_lines={report['duplicate_lines']} duplicate_uuids={report['duplicate_uuids']} "
        f"deviations={len(report['deviations'])}"
    )


def _receipt(record: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    """RECEIPT-PUBLIC.json: hashes, counts, ids, statuses, verdict class, window, N, exclusion count, labels, UTC."""
    terminal = record.get("terminal") or {}
    completeness = record.get("completeness") or {}
    query = record.get("query") or {}
    verdict = str(record.get("verdict") or "")
    return {
        "receipt": "RECEIPT-PUBLIC (hashes and counts only)",
        "mode": record["mode"],
        "label": record["label"],
        "labels": {"readout": record["label"], "operator": OPERATOR_LABEL, "script": SCRIPT_PATH.name},
        "host": record.get("host"),
        "project": record.get("project"),
        "run_id": record.get("run_id"),
        "resumed_run": record.get("resumed_run", False),
        "n_before_carried": record.get("n_before_carried", False),
        "file_ids": terminal.get("files"),
        "status": terminal.get("status"),
        "error_field_present": terminal.get("error_field_present"),
        "n_before": record.get("n_before"),
        "n_after": record.get("n_after"),
        "records_completed": terminal.get("records_completed"),
        "rows_parsed": completeness.get("rows_parsed"),
        "verdict": _verdict_class(verdict),
        "verdict_text_sha256": _sha256(verdict.encode("utf-8")),
        "verdict_text_bytes": len(verdict.encode("utf-8")),
        "failing_rules": _public_rules(completeness.get("failing_rules") or []),
        "completeness_rule_source": record.get("completeness_rule_source"),
        "source_availability_recorded": record.get("source_availability_recorded"),
        "pricing_signal": record.get("pricing_signal"),
        "window": record.get("window"),
        "N": args.n,
        "excluded_count": args.excluded_count,
        "query_sha256": query.get("sha256"),
        "query_bytes": query.get("bytes"),
        "parts": [
            {
                "id": part.get("id"), "sha256": part.get("sha256"), "bytes": part.get("bytes"), "rows": part.get("rows"),
                "key_set_equal_rows": (part.get("verification") or {}).get("key_set_equal_rows"),
                "deviation_count": len((part.get("verification") or {}).get("deviations", [])),
            }
            for part in record.get("parts", [])
        ],
        "columns_source": record.get("columns_source"),
        "v1_events_written": (record.get("v1_events") or {}).get("written", False),
        "utc": record.get("utc"),
        "script_sha256": _sha256(SCRIPT_PATH.read_bytes()),
        "statement": (
            "Hashes, counts, ids, statuses and UTC times only: no row, roster literal, key, private path, "
            "remote error text or signed URL. Nothing here marks cohort reporting, beta admission or capacity "
            "complete or admitted."
        ),
    }


def _write_custody(run_dir: Path) -> list[str]:
    """Custody-check style: one 'sha256  bytes  relative-path' line per file, then TOTAL=<files> <bytes>."""
    lines: list[str] = []
    total_files = total_bytes = 0
    for path in sorted(p for p in run_dir.rglob("*") if p.is_file() and p.name != "CUSTODY.txt"):
        data = path.read_bytes()
        lines.append(f"{_sha256(data)}  {len(data)}  {path.relative_to(run_dir).as_posix()}")
        total_files += 1
        total_bytes += len(data)
    lines.append(f"TOTAL={total_files} {total_bytes}")
    _write_bytes(run_dir / "CUSTODY.txt", ("\n".join(lines) + "\n").encode("utf-8"))
    return lines


def _write_v1_events(adapter: Any | None, run_dir: Path, part_bytes: list[bytes], record: dict[str, Any]) -> None:
    """v1-events.json only when the adapter module is present (private dir; it holds rows)."""
    if adapter is None or not hasattr(adapter, "v1_response_from_parts") or not part_bytes:
        record["v1_events"] = {"written": False, "reason": "adapter module absent or no parts"}
        return
    try:
        payload = adapter.v1_response_from_parts(part_bytes)
        _write_json(run_dir / "v1-events.json", payload)
        record["v1_events"] = {"written": True, "sha256": _sha256((run_dir / "v1-events.json").read_bytes())}
    except Exception as err:  # noqa: BLE001 - another module; record, never crash
        record["v1_events"] = {"written": False, "error": type(err).__name__}


def _finish(run_dir: Path, record: dict[str, Any], args: argparse.Namespace, verdict: str, exit_code: int) -> int:
    record["verdict"] = _redact(verdict)
    record["exit_code"] = exit_code
    record["utc"]["verified"] = _utc_now()
    _write_json(run_dir / "VERIFICATION.json", record)
    _write_json(run_dir / "RECEIPT-PUBLIC.json", _receipt(record, args))
    _say(f"verdict: {record['verdict']}")
    _say(f"custody {run_dir.name}:")
    for line in _write_custody(run_dir):
        _say(line)
    return exit_code


def run_export(args: argparse.Namespace) -> int:
    key = os.environ.get(KEY_ENV, "")
    if not key.strip():
        raise Refused(f"{KEY_ENV} is not set in the environment; the key is never an argument")
    if not args.query or not args.private_dir:
        raise Refused("--query and --private-dir are required for an export run")
    if args.resume is not None:
        if not UUID_PATTERN.fullmatch(args.resume):
            raise Refused("--resume needs the run id the earlier invocation printed")
        if args.n_before is None:
            raise Refused("--resume needs --n-before, carried from the earlier invocation's saved count-rows response")
    host = args.host.rstrip("/")
    if urllib.parse.urlsplit(host).scheme != "https" or not urllib.parse.urlsplit(host).netloc:
        raise Refused("--host must be an https URL")
    private = _prepare_private_dir(args.private_dir)
    query_bytes = Path(args.query).expanduser().read_bytes()
    if not query_bytes or len(query_bytes) > MAX_QUERY_BYTES:
        raise Refused("bound query is empty or exceeds the 1 MiB bound")
    try:
        query_text = query_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise Refused("bound query is not valid UTF-8") from None
    if "{{" in query_text or "}}" in query_text:
        raise Refused("bound query still contains {{...}} placeholders; bind every literal before the first call")
    _REDACTION["query"] = query_text
    _REDACTION["sha256"] = _sha256(query_bytes)
    poll_seconds = min(max(args.poll_seconds, 5), 300)
    timeout_seconds = min(max(args.timeout_minutes, 1), 240) * 60
    columns, columns_source = _load_columns()
    adapter = _load_adapter()
    if args.resume is not None:
        run_dir = private / f"{args.label}-{args.resume}-resume-{_stamp()}"
    else:
        run_dir = private / f"{args.label}-pending-{_stamp()}"
    run_dir.mkdir(mode=0o700)
    (run_dir / "responses").mkdir(mode=0o700)
    (run_dir / "parts").mkdir(mode=0o700)
    _write_bytes(run_dir / "bound-query.hogql", query_bytes)
    base = f"/api/projects/{args.project}/file_download_batch_exports/"
    modifiers = {"convertToProjectTimezone": False}
    count_body = {"model": "hogql", "hogql_query": query_text, "hogql_modifiers": modifiers}
    create_body = {
        "model": "hogql",
        "file": {"format": "JSONLines", "compression": None, "max_size_mb": None},
        "hogql_query": query_text,
        "hogql_modifiers": modifiers,
    }
    redacted = "<bound query bytes; see bound-query.hogql>"
    record: dict[str, Any] = {
        "mode": "export",
        "label": args.label,
        "operator": OPERATOR_LABEL,
        "host": host,
        "project": args.project,
        "project_identity": "recorded as given; no project-get call (step 1)",
        "window": {"start": args.window_start, "end": args.window_end},
        "query": {
            "sha256": _REDACTION["sha256"], "bytes": len(query_bytes),
            "trailing_newline": query_bytes.endswith(b"\n"), "cr_bytes": query_bytes.count(b"\r"),
        },
        "request_shapes": {
            "count_rows": {**count_body, "hogql_query": redacted},
            "create": {**create_body, "hogql_query": redacted},
        },
        "poll_seconds": poll_seconds,
        "timeout_minutes": timeout_seconds // 60,
        "columns_source": columns_source,
        "expected_columns": columns,
        "adapter_module_present": adapter is not None,
        "resumed_run": args.resume is not None,
        "n_before_carried": args.resume is not None,
        "source_availability_recorded": False,
        "calls": [],
        "polls": 0,
        "run_id": None,
        "terminal": None,
        "n_before": None,
        "n_after": None,
        "parts": [],
        "pricing_signal": None,
        "stop": None,
        "notes": [],
        "utc": {"started": _utc_now()},
    }
    parts: list[dict[str, Any]] = []
    part_bytes: list[bytes] = []
    terminal: dict[str, Any] | None = None
    run_id: str | None = None
    verdict: str | None = None
    exit_code = EXIT_INCOMPLETE
    seq = 0
    _say(
        f"export_operator export label={args.label} project={args.project} host={host} "
        f"query_sha256={record['query']['sha256']} query_bytes={len(query_bytes)}"
    )
    _say(f"columns: {len(columns)} (source: {columns_source})")
    try:
        if args.resume is not None:
            # Resume: steps 4-8 only; zero creates; n_before carried from the earlier invocation.
            run_id = args.resume
            record["run_id"] = run_id
            record["n_before"] = args.n_before
            record["notes"].append(
                "resume: steps 4-8 only; zero creates; n_before carried from the earlier invocation's saved "
                "count-rows response"
            )
            _say(f"resume run_id={run_id} n_before={args.n_before} (carried)")
        else:
            # Step 2: count before.
            seq += 1
            status_code, body, request_sha = _api_call(host, base + "count_rows/", key, "POST", count_body, 120)
            record["calls"].append(
                _save_response(run_dir, seq, "count-rows-before", "POST", base + "count_rows/", status_code, body, request_sha)
            )
            record["utc"]["count_before"] = record["calls"][-1]["utc"]
            payload = _connector_check(status_code, body, "count-rows before") or {}
            n_before = payload.get("count")
            if type(n_before) is not int or n_before < 0:
                raise SourceUnavailable("count-rows before: no integer count in the response")
            record["n_before"] = n_before
            _say(f"n_before={n_before}")
            if n_before >= LIMIT_CAP:
                verdict = "incomplete (cap)"
                exit_code = EXIT_STOP
                record["stop"] = (
                    f"n_before={n_before} >= {LIMIT_CAP}: the window is capped; narrow it under a new receipt; "
                    "no create was sent"
                )
                _say(f"STOP: {record['stop']}")
            else:
                # Step 3: create, once.
                seq += 1
                status_code, body, request_sha = _api_call(host, base, key, "POST", create_body, 120)
                record["calls"].append(
                    _save_response(run_dir, seq, "create", "POST", base, status_code, body, request_sha)
                )
                record["utc"]["created"] = record["calls"][-1]["utc"]
                payload = _connector_check(status_code, body, "create") or {}
                created_id = payload.get("id")
                if not isinstance(created_id, str) or not UUID_PATTERN.fullmatch(created_id):
                    raise SourceUnavailable("create: no run id in the response")
                run_id = created_id
                record["run_id"] = run_id
                target_dir = private / f"{args.label}-{run_id}"
                if target_dir.exists():
                    record["notes"].append("run directory name already existed; outputs stay in the pending directory")
                else:
                    run_dir.rename(target_dir)
                    run_dir = target_dir
                _say(f"run_id={run_id}")
        if run_id is not None:
            # Step 4: poll to a terminal status; 5xx and transport errors retry until the deadline.
            deadline = time.monotonic() + timeout_seconds
            run_path = f"{base}{run_id}/"
            last_status: Any = None
            while True:
                seq += 1
                payload = None
                try:
                    status_code, body, _ = _api_call(host, run_path, key, "GET", None, 120)
                except SourceUnavailable as err:
                    record["calls"].append({
                        "seq": seq, "name": "retrieve", "method": "GET", "path": run_path, "http_status": None,
                        "utc": _utc_now(), "transport_error": str(err), "retryable": True,
                    })
                    _say(f"poll {record['polls'] + 1}: transport error ({err}); retrying until the deadline")
                else:
                    record["calls"].append(
                        _save_response(run_dir, seq, "retrieve", "GET", run_path, status_code, body, None)
                    )
                    payload = _connector_check(status_code, body, "retrieve", retry_5xx=True)
                    if payload is None:
                        record["calls"][-1]["retryable"] = True
                        _say(f"poll {record['polls'] + 1}: HTTP {status_code}; retrying until the deadline")
                record["polls"] += 1
                if payload is not None:
                    last_status = payload.get("status")
                    _say(f"poll {record['polls']}: status={last_status}")
                    if last_status in TERMINAL_STATUSES or "error" in payload:
                        terminal = payload
                        break
                if time.monotonic() >= deadline:
                    raise SourceUnavailable(
                        f"poll timeout after {timeout_seconds // 60} minutes; last status {last_status!r}; "
                        "resume with --resume under the same authorisation"
                    )
                time.sleep(poll_seconds)
            record["utc"]["terminal"] = record["calls"][-1]["utc"]
            record["source_availability_recorded"] = True  # the terminal retrieve response is saved as returned
            record["terminal"] = {
                "status": terminal.get("status"),
                "error_field_present": "error" in terminal,
                "records_completed": terminal.get("records_completed"),
                "files": terminal.get("files"),
            }
            if terminal.get("status") != "Completed" or "error" in terminal:
                raise SourceUnavailable(
                    f"terminal status {terminal.get('status')!r}"
                    + ("; error field present" if "error" in terminal else "")
                )
            files = terminal.get("files")
            if not isinstance(files, list) or not all(
                isinstance(item, str) and UUID_PATTERN.fullmatch(item) for item in files
            ):
                raise SourceUnavailable("retrieve: files[] is not a list of file ids")
            _say(f"terminal status=Completed records_completed={terminal.get('records_completed')} files={len(files)}")
            # Step 5: count after.
            seq += 1
            status_code, body, request_sha = _api_call(host, base + "count_rows/", key, "POST", count_body, 120)
            record["calls"].append(
                _save_response(run_dir, seq, "count-rows-after", "POST", base + "count_rows/", status_code, body, request_sha)
            )
            record["utc"]["count_after"] = record["calls"][-1]["utc"]
            try:
                payload = _connector_check(status_code, body, "count-rows after") or {}
                n_after = payload.get("count")
                if type(n_after) is not int or n_after < 0:
                    raise SourceUnavailable("count-rows after: no integer count in the response")
                record["n_after"] = n_after
            except SourceUnavailable as err:
                record["notes"].append(f"n_after not observed: {err}")
            _say(f"n_after={record['n_after']}")
            # Step 6: download every part in files[] order.
            for index, file_id in enumerate(files, 1):
                download_path = f"{run_path}download/{file_id}/"
                first_status, body_status, body = _download_part(host, download_path, key, 600)
                entry: dict[str, Any] = {
                    "id": file_id, "index": index, "path": download_path, "utc": _utc_now(),
                    "first_response_status": first_status, "body_fetch_status": body_status,
                    "redirect_followed": first_status in REDIRECT_CODES,
                }
                if body_status != 200:
                    entry["failure"] = _bounded_error_summary(body)
                    parts.append(entry)
                    raise SourceUnavailable(
                        f"download of file {index}/{len(files)}: first HTTP {first_status}, "
                        f"body HTTP {body_status}; {entry['failure']}"
                    )
                if len(body) > MAX_PART_BYTES:
                    raise SourceUnavailable(f"download of file {index}/{len(files)} exceeds the {MAX_PART_BYTES} byte bound")
                file_name = f"posthog-hogql-{run_id}-{file_id}.jsonl"
                _write_bytes(run_dir / "parts" / file_name, body)
                entry.update({"file_name": f"parts/{file_name}", "sha256": _sha256(body), "bytes": len(body)})
                parts.append(entry)
                part_bytes.append(body)
                _say(
                    f"download {index}/{len(files)} {file_id}: sha256={entry['sha256']} bytes={len(body)} "
                    f"first_http={first_status} body_http={body_status}"
                )
            record["utc"]["download_complete"] = _utc_now()
    except PricingStop as stop:
        record["pricing_signal"] = stop.word
        record["stop"] = f"pricing signal '{stop.word}' at HTTP {stop.http_status}: {stop.summary}"
        verdict = f"source-unavailable (pricing signal: {stop.word})"
        exit_code = EXIT_STOP
        _say(
            f"STOP: pricing signal '{stop.word}' (HTTP {stop.http_status}); no PostHog charge is authorised; "
            f"redacted structured fields: {stop.summary}; the raw response stays in responses/"
        )
    except SourceUnavailable as err:
        verdict = f"source-unavailable ({err})"
        exit_code = EXIT_SOURCE_UNAVAILABLE
        _say(f"STOP: {verdict}")
    record["parts"] = parts
    # Step 7: parse and verify every downloaded part.
    for entry, data in zip(parts, part_bytes):
        entry["verification"] = verify_part(data, columns)
        entry["rows"] = entry["verification"]["rows"]
        _say(_part_line(entry))
    # Step 8: completeness (single rule owner).
    run_record = terminal if terminal is not None else {"status": None}
    completeness, rule_source = _completeness(
        adapter, run_record, parts, record["n_before"], record["n_after"],
        record["source_availability_recorded"] is True,
    )
    record["completeness"] = completeness
    record["completeness_rule_source"] = rule_source
    _say(f"completeness rule: {rule_source}")
    _say(
        f"n_before={record['n_before']} n_after={record['n_after']} "
        f"records_completed={run_record.get('records_completed')} rows_parsed={completeness.get('rows_parsed')} "
        f"status={run_record.get('status')}"
    )
    if verdict is None:
        verdict = completeness["verdict"]
        exit_code = EXIT_COMPLETE if completeness.get("file_export_complete_observed") else EXIT_INCOMPLETE
    if terminal is not None and len(part_bytes) == len(parts):
        _write_v1_events(adapter, run_dir, part_bytes, record)
    else:
        record["v1_events"] = {"written": False, "reason": "run not completed or not every part downloaded"}
    return _finish(run_dir, record, args, verdict, exit_code)


def run_offline(args: argparse.Namespace) -> int:
    """Steps 7-8 only, on existing parts, with no network call."""
    if not args.run_record or args.n_before is None:
        raise Refused("--offline-verify needs --run-record and --n-before")
    part_paths = [Path(item).expanduser().resolve() for item in args.offline_verify]
    if any(not path.is_file() for path in part_paths):
        raise Refused("every --offline-verify argument must be an existing part file")
    run_record_bytes = Path(args.run_record).expanduser().read_bytes()
    try:
        run_record = json.loads(run_record_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise Refused("--run-record is not UTF-8 JSON") from None
    if not isinstance(run_record, dict):
        raise Refused("--run-record must hold a JSON object (the terminal retrieve response)")
    files = run_record.get("files") if isinstance(run_record.get("files"), list) else []
    run_id = run_record.get("id") if isinstance(run_record.get("id"), str) else None
    for path in part_paths:
        match = PART_NAME_PATTERN.fullmatch(path.name)
        if run_id is None and match:
            run_id = match.group(1)
    run_id = run_id or "unknown-run"
    source_availability_recorded = run_record.get("source_availability_recorded") is True
    out_root = _prepare_private_dir(
        args.private_dir if args.private_dir else str(part_paths[0].parent.parent / "offline-verify")
    )
    run_dir = out_root / f"{args.label}-{run_id}"
    if run_dir.exists():
        raise Refused("the output directory for this label and run id already exists; outputs are never overwritten")
    run_dir.mkdir(mode=0o700)
    columns, columns_source = _load_columns()
    adapter = _load_adapter()
    record: dict[str, Any] = {
        "mode": "offline-verify",
        "label": args.label,
        "operator": OPERATOR_LABEL,
        "host": None,
        "project": args.project,
        "window": {"start": args.window_start, "end": args.window_end},
        "run_record": {"sha256": _sha256(run_record_bytes), "bytes": len(run_record_bytes)},
        "run_id": run_id,
        "terminal": {
            "status": run_record.get("status"),
            "error_field_present": "error" in run_record,
            "records_completed": run_record.get("records_completed"),
            "files": files,
        },
        "n_before": args.n_before,
        "n_after": args.n_after,
        "source_availability_recorded": source_availability_recorded,
        "columns_source": columns_source,
        "expected_columns": columns,
        "adapter_module_present": adapter is not None,
        "parts": [],
        "pricing_signal": None,
        "notes": ["offline verification of existing parts: steps 7-8 only; no network call"],
        "utc": {"started": _utc_now()},
    }
    _say(f"export_operator offline-verify label={args.label} run_id={run_id} parts={len(part_paths)}")
    _say(f"columns: {len(columns)} (source: {columns_source})")
    parts: list[dict[str, Any]] = []
    part_bytes: list[bytes] = []
    for index, path in enumerate(part_paths, 1):
        data = path.read_bytes()
        if len(data) > MAX_PART_BYTES:
            raise Refused(f"part {index} exceeds the {MAX_PART_BYTES} byte bound")
        file_id = next((item for item in files if isinstance(item, str) and item in path.name), None)
        if file_id is None and index <= len(files):
            file_id = files[index - 1]
        entry: dict[str, Any] = {
            "id": file_id, "index": index, "file_name": path.name, "sha256": _sha256(data), "bytes": len(data),
        }
        entry["verification"] = verify_part(data, columns)
        entry["rows"] = entry["verification"]["rows"]
        parts.append(entry)
        part_bytes.append(data)
        _say(_part_line(entry))
    record["parts"] = parts
    completeness, rule_source = _completeness(
        adapter, run_record, parts, args.n_before, args.n_after, source_availability_recorded,
    )
    record["completeness"] = completeness
    record["completeness_rule_source"] = rule_source
    _say(f"completeness rule: {rule_source}")
    _say(
        f"n_before={args.n_before} n_after={args.n_after} records_completed={run_record.get('records_completed')} "
        f"rows_parsed={completeness.get('rows_parsed')} status={run_record.get('status')}"
    )
    _write_v1_events(adapter, run_dir, part_bytes, record)
    exit_code = EXIT_COMPLETE if completeness.get("file_export_complete_observed") else EXIT_INCOMPLETE
    return _finish(run_dir, record, args, completeness["verdict"], exit_code)


def _parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="export_operator",
        description=(
            "Founder-side PostHog file-download batch-export operator and verifier "
            "(readout contract revision 3, section 2.0 steps 1-8). The personal API key is read only from "
            f"the environment variable {KEY_ENV} and is never printed or written."
        ),
    )
    parser.add_argument("--host", default="https://eu.posthog.com", help="PostHog API host (EU cloud default)")
    parser.add_argument("--project", type=int, default=117863, help="project id, recorded as given")
    parser.add_argument("--query", help="path to the bound HogQL text (private: carries roster literals)")
    parser.add_argument("--private-dir", help="directory OUTSIDE any git work tree that receives every output")
    parser.add_argument("--label", required=True, help="readout label such as W1, W2 or C")
    parser.add_argument("--window-start", help="UTC window start, recorded only")
    parser.add_argument("--window-end", help="UTC window end, recorded only")
    parser.add_argument("--poll-seconds", type=int, default=15, help="retrieve poll interval (bounded 5-300)")
    parser.add_argument("--timeout-minutes", type=int, default=30, help="poll timeout (bounded 1-240)")
    parser.add_argument("--n", type=int, help="N = eligible roster size after exclusions, recorded only")
    parser.add_argument("--excluded-count", type=int, help="exclusion count, recorded only")
    parser.add_argument(
        "--resume", metavar="RUN_ID",
        help="steps 4-8 only for a run an earlier invocation created (zero creates); needs --n-before (carried)",
    )
    parser.add_argument("--offline-verify", nargs="+", metavar="PART", help="verify existing parts; no network")
    parser.add_argument("--run-record", help="offline mode: JSON of the terminal retrieve response")
    parser.add_argument("--n-before", type=int, help="count-rows before (offline mode, or carried on --resume)")
    parser.add_argument("--n-after", type=int, help="offline mode: count-rows after, if observed")
    args = parser.parse_args(argv)
    if not LABEL_PATTERN.fullmatch(args.label):
        raise Refused("--label must be 1-40 characters of letters, digits, '_', '.' or '-'")
    if args.resume is not None and args.offline_verify:
        raise Refused("--resume and --offline-verify are exclusive")
    return args


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse(argv)
        if args.offline_verify:
            return run_offline(args)
        return run_export(args)
    except Refused as err:
        _say(f"refused: {err}")
        return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
