"""Measure hash-bound HTML parser-event capacity without building a source projection."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
from typing import Any

from evals.acceptance_source_view import MAX_SOURCE_BYTES, MAX_UNIT_BYTES


READ_CHUNK_BYTES = 1024 * 1024


def _sha(data: bytes | bytearray) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_verified_source(
    source: Path,
    expected_sha256: str,
    expected_bytes: int,
) -> tuple[bytearray, str]:
    if expected_bytes < 1:
        raise ValueError("expected source bytes must be positive")
    if expected_bytes > MAX_SOURCE_BYTES:
        raise ValueError("HTML source exceeds offline review limit")
    raw = bytearray()
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        while chunk := stream.read(READ_CHUNK_BYTES):
            if len(raw) + len(chunk) > MAX_SOURCE_BYTES:
                raise ValueError("HTML source exceeds offline review limit")
            digest.update(chunk)
            raw.extend(chunk)
    observed_sha256 = digest.hexdigest()
    if len(raw) != expected_bytes or observed_sha256 != expected_sha256:
        raise ValueError("source size/hash mismatch")
    return raw, observed_sha256


class _CapacityParser(HTMLParser):
    """Count whole-input HTMLParser callbacks while retaining only aggregate metadata."""

    def __init__(self, raw: bytearray) -> None:
        super().__init__(convert_charrefs=False)
        self.raw = raw
        self.cursor = 0
        self.event_count = 0
        self.event_counts: Counter[str] = Counter()
        self.max_event: dict[str, Any] | None = None

    def _markup_end(self, start: int) -> int:
        quote: int | None = None
        for index in range(start + 1, len(self.raw)):
            value = self.raw[index]
            if quote is not None:
                if value == quote:
                    quote = None
            elif value in (34, 39):
                quote = value
            elif value == 62:
                return index + 1
        raise ValueError("truncated markup boundary")

    def _record_span(self, kind: str, end: int) -> None:
        start = self.cursor
        if not start < end <= len(self.raw):
            raise ValueError("invalid parser-event byte span")
        size = end - start
        if size > MAX_UNIT_BYTES:
            raise ValueError(f"oversized single parser unit: {size} bytes")
        self.event_count += 1
        self.event_counts[kind] += 1
        if self.max_event is None or size > self.max_event["bytes"]:
            self.max_event = {
                "index": self.event_count,
                "kind": kind,
                "start": start,
                "end": end,
                "bytes": size,
                "sha256": _sha(self.raw[start:end]),
            }
        self.cursor = end

    def _record_exact(self, kind: str, expected: bytes, *, case_insensitive: bool = False) -> None:
        end = self.cursor + len(expected)
        observed = self.raw[self.cursor:end]
        matches = observed.lower() == expected.lower() if case_insensitive else observed == expected
        if not matches:
            raise ValueError(f"{kind} cannot be mapped unambiguously to source bytes")
        self._record_span(kind, end)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del tag, attrs
        source = self.get_starttag_text()
        if source is None:
            raise ValueError("start tag has no source text")
        self._record_exact("start_tag", source.encode("utf-8"))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        del tag
        self._record_span("end_tag", self._markup_end(self.cursor))

    def handle_data(self, data: str) -> None:
        self._record_exact("data", data.encode("utf-8"))

    def handle_entityref(self, name: str) -> None:
        self._record_exact("entity_reference", f"&{name};".encode("ascii"), case_insensitive=True)

    def handle_charref(self, name: str) -> None:
        self._record_exact("character_reference", f"&#{name};".encode("ascii"), case_insensitive=True)

    def handle_comment(self, data: str) -> None:
        del data
        end_marker = self.raw.find(b"-->", self.cursor + 4)
        if end_marker < 0:
            raise ValueError("truncated comment")
        self._record_span("comment", end_marker + 3)

    def handle_decl(self, decl: str) -> None:
        del decl
        self._record_span("declaration", self._markup_end(self.cursor))

    def unknown_decl(self, data: str) -> None:
        raise ValueError(f"unknown declaration cannot be measured safely: {data[:40]}")

    def handle_pi(self, data: str) -> None:
        del data
        self._record_span("processing_instruction", self._markup_end(self.cursor))

    def measure(self, text: str) -> dict[str, Any]:
        # One full feed preserves the logical data callbacks used by project_html.
        self.feed(text)
        self.close()
        if self.cursor != len(self.raw):
            raise ValueError("parser events do not cover the complete source")
        if self.max_event is None:
            raise ValueError("HTML source produced no parser events")
        return {
            "event_count": self.event_count,
            "event_counts": dict(sorted(self.event_counts.items())),
            "max_raw_event": self.max_event,
        }


def preflight_source(source: Path, expected_sha256: str, expected_bytes: int) -> dict[str, Any]:
    """Verify one explicit source identity, then measure whole-input parser events."""
    raw, source_sha256 = _read_verified_source(source, expected_sha256, expected_bytes)
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise ValueError("HTML source is not strict UTF-8") from exc
    measurements = _CapacityParser(raw).measure(text)
    return {
        "schema_version": 1,
        "kind": "e7_offline_html_parser_event_capacity",
        "source": {
            "path": str(source),
            "bytes": len(raw),
            "sha256": source_sha256,
        },
        "limits": {
            "max_source_bytes": MAX_SOURCE_BYTES,
            "max_parser_event_bytes": MAX_UNIT_BYTES,
        },
        **measurements,
        "within_capacity_limits": True,
        "semantic_review_attested": False,
        "supported_markup_grammar_attested": False,
        "admission_approved": False,
        "limitations": [
            "This measures raw HTMLParser event spans only; it does not build or verify a structural projection.",
            "It does not attest source meaning, semantic coverage, supported markup grammar, or admission.",
            "Projection memory, model context, hierarchy, and non-text modality capacity remain unmeasured.",
        ],
    }


def write_capacity_audit(
    source: Path,
    expected_sha256: str,
    expected_bytes: int,
    output: Path,
) -> dict[str, Any]:
    """Write one new JSON capacity audit after identity and event-limit checks pass."""
    if output.exists() or output.is_symlink():
        raise ValueError("capacity audit output must not already exist")
    audit = preflight_source(source, expected_sha256, expected_bytes)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    except FileExistsError as exc:
        raise ValueError("capacity audit output must not already exist") from exc
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--expected-bytes", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit = write_capacity_audit(
        args.source,
        args.expected_sha256,
        args.expected_bytes,
        args.output,
    )
    print(json.dumps(audit, sort_keys=True))


if __name__ == "__main__":
    main()
