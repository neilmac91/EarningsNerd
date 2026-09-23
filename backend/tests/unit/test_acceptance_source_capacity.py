"""The capacity preflight measures exact source-view parser-event boundaries."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

import pytest

from evals import acceptance_source_capacity as capacity
from evals.acceptance_source_view import MAX_UNIT_BYTES, project_html


def _write_source(path: Path, raw: bytes) -> tuple[str, int]:
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest(), len(raw)


def test_capacity_preflight_preserves_events_and_rejects_identity_or_unit_overflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = (
        '<!doctype html>\n<html><head><style>.é::after{content:"&amp;"}</style>\n'
        '<script>const x = "<tag>&amp;";</script></head><body>\n<!-- café -->'
        '<p title=">">Résumé &amp; &#x20AC;<br/></p>\n<?audit ok?></body></html>'
    ).encode("utf-8")
    source = tmp_path / "representative.html"
    expected_sha256, expected_bytes = _write_source(source, raw)
    output = tmp_path / "audit.json"

    audit = capacity.write_capacity_audit(source, expected_sha256, expected_bytes, output)
    projection = project_html(raw)
    expected_counts = Counter(event["kind"] for event in projection["events"])
    expected_max = max(projection["events"], key=lambda event: event["bytes"])
    assert audit["source"] == {
        "path": str(source),
        "bytes": expected_bytes,
        "sha256": expected_sha256,
    }
    assert audit["event_count"] == len(projection["events"])
    assert audit["event_counts"] == dict(sorted(expected_counts.items()))
    assert audit["max_raw_event"] == {
        "index": projection["events"].index(expected_max) + 1,
        "kind": expected_max["kind"],
        "start": expected_max["start"],
        "end": expected_max["end"],
        "bytes": expected_max["bytes"],
        "sha256": expected_max["sha256"],
    }
    assert json.loads(output.read_text(encoding="utf-8")) == audit
    assert audit["semantic_review_attested"] is False
    assert audit["supported_markup_grammar_attested"] is False
    assert audit["admission_approved"] is False

    ignored_raw = b"</><!--x-->"
    ignored_source = tmp_path / "ignored-prefix.html"
    ignored_sha256, ignored_bytes = _write_source(ignored_source, ignored_raw)
    with pytest.raises(ValueError, match="parser callback position does not match consumed source"):
        capacity.preflight_source(ignored_source, ignored_sha256, ignored_bytes)
    with pytest.raises(ValueError, match="parser events do not partition"):
        project_html(ignored_raw)

    race_output = tmp_path / "race.json"
    original_preflight = capacity.preflight_source
    with monkeypatch.context() as concurrent_writer:
        def create_destination_before_return(*args: object, **kwargs: object) -> dict[str, object]:
            result = original_preflight(*args, **kwargs)
            race_output.write_text("concurrent-writer\n", encoding="utf-8")
            return result

        concurrent_writer.setattr(capacity, "preflight_source", create_destination_before_return)
        with pytest.raises(ValueError, match="output must not already exist"):
            capacity.write_capacity_audit(source, expected_sha256, expected_bytes, race_output)
    assert race_output.read_text(encoding="utf-8") == "concurrent-writer\n"

    with monkeypatch.context() as identity_guard:
        def forbidden_feed(*args: object, **kwargs: object) -> None:
            raise AssertionError("identity mismatch reached tokenizer")

        identity_guard.setattr(capacity._CapacityParser, "feed", forbidden_feed)
        with pytest.raises(ValueError, match="source size/hash mismatch"):
            capacity.preflight_source(source, "0" * 64, expected_bytes)
        with pytest.raises(ValueError, match="source size/hash mismatch"):
            capacity.preflight_source(source, expected_sha256, expected_bytes + 1)

    exact_raw = b"<p>" + b"x" * MAX_UNIT_BYTES + b"</p>"
    exact_source = tmp_path / "exact-limit.html"
    exact_sha256, exact_bytes = _write_source(exact_source, exact_raw)
    exact = capacity.preflight_source(exact_source, exact_sha256, exact_bytes)
    assert exact["max_raw_event"]["kind"] == "data"
    assert exact["max_raw_event"]["bytes"] == MAX_UNIT_BYTES

    oversized_values = (
        b"x" * (MAX_UNIT_BYTES + 1),
        ("é" * (MAX_UNIT_BYTES // 2 + 1)).encode("utf-8"),
    )
    for index, value in enumerate(oversized_values):
        oversized_raw = b"<p>" + value + b"</p>"
        oversized_source = tmp_path / f"oversized-{index}.html"
        oversized_sha256, oversized_bytes = _write_source(oversized_source, oversized_raw)
        with pytest.raises(ValueError, match=r"oversized single parser unit: 209715[34] bytes"):
            capacity.preflight_source(oversized_source, oversized_sha256, oversized_bytes)

    with monkeypatch.context() as source_limit:
        source_limit.setattr(capacity, "MAX_SOURCE_BYTES", expected_bytes - 1)
        with pytest.raises(ValueError, match="source exceeds offline review limit"):
            capacity.preflight_source(source, expected_sha256, expected_bytes)
