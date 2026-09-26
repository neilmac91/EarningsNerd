"""Document maps preserve byte coverage and cannot admit a changed selected source."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from evals import acceptance_document_map as mapper
from evals.acceptance_source_contract import SourceContract
from evals.acceptance_document_map import build_document_maps, map_submission


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _doc(filename: bytes, payload: bytes, kind: bytes = b"10-K", newline: bytes = b"\n") -> bytes:
    return newline.join(
        (
            b"<DOCUMENT>",
            b"<TYPE>" + kind,
            b"<SEQUENCE>1",
            b"<FILENAME>" + filename,
            b"<DESCRIPTION>Retained source",
            b"<TEXT>",
            payload,
            b"</TEXT>",
            b"</DOCUMENT>",
        )
    )


def test_maps_exact_source_bytes_and_rejects_changed_identity(tmp_path: Path) -> None:
    content = '<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><p>€ 1,000</p></html>'.encode()
    payload = b" \n<XBRL>\n" + content + b"\n</XBRL>\n "
    raw = (
        b"<SEC-DOCUMENT>\r\n"
        + _doc(b"issuer.htm", payload)
        + b"\n"
        + _doc(b"copy.htm", payload)
        + b"\r\n"
        + _doc(b"opaque.dat", b"begin 644 image\nENCODED\nend", b"GRAPHIC", b"\r\n")
        + b"\r\n</SEC-DOCUMENT>"
    )
    path = tmp_path / "submission.txt"
    path.write_bytes(raw)
    contract = {
        "attachments": {
            "primary": {
                "document": "issuer.htm",
                "embedded_sha256": _sha(content),
                "embedded_bytes": len(content),
                "packet_sha256": "f" * 64,
                "relationship": "distinct",
                "difference_audit": {"classification": "wrapper_only"},
            }
        }
    }
    mapped = map_submission(path, _sha(raw), len(raw), contract)
    assert mapped["every_source_byte_accounted"] is True
    assert mapped["semantic_coverage_attested"] is False
    documents = mapped["documents"]
    assert len(documents) == 3
    assert mapped["exact_payload_duplicates"] == [[1, 2]]
    assert documents[0]["format_wrapper"] == "XBRL"
    assert documents[0]["review_requirements"] == [
        "readable_document_review_required",
        "inline_xbrl_structured_review_required",
    ]
    assert documents[2]["route"] == "visual_or_binary_review_required"
    assert mapped["selected_attachments"]["primary"]["source_span"] == documents[0]["content"]

    def assert_partition(parts: list[dict], start: int, end: int) -> None:
        cursor = start
        for part in sorted(parts, key=lambda item: item["start"]):
            assert part["start"] == cursor
            assert part["bytes"] == part["end"] - cursor
            assert _sha(raw[cursor : part["end"]]) == part["sha256"]
            cursor = part["end"]
        assert cursor == end

    assert_partition(mapped["submission_envelope"] + [d["document"] for d in documents], 0, len(raw))
    for doc in documents:
        assert_partition(
            [doc["header"], doc["payload"], doc["footer"]], doc["document"]["start"], doc["document"]["end"]
        )
        assert_partition(
            [doc["content_prefix"], doc["content"], doc["content_suffix"]],
            doc["payload"]["start"],
            doc["payload"]["end"],
        )
    assert map_submission(path, _sha(raw), len(raw), contract) == mapped
    changed = copy.deepcopy(contract)
    changed["attachments"]["primary"]["embedded_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="differs from frozen embedding contract"):
        map_submission(path, _sha(raw), len(raw), changed)
    changed["attachments"]["primary"]["document"] = "missing.htm"
    with pytest.raises(ValueError, match="absent or ambiguous"):
        map_submission(path, _sha(raw), len(raw), changed)
    with pytest.raises(ValueError, match="size/hash mismatch"):
        map_submission(path, "0" * 64, len(raw), contract)
    for malformed in (
        raw.replace(b"</XBRL>", b"</XML>"),
        raw.replace(b"<FILENAME>copy.htm", b"<FILENAME>issuer.htm"),
        raw.replace(b"</TEXT>\n", b"", 1),
        raw.replace(b"<TYPE>10-K", b"<TYPE>10-K\n<TYPE>10-Q", 1),
    ):
        path.write_bytes(malformed)
        with pytest.raises(ValueError):
            map_submission(path, _sha(malformed), len(malformed), contract)
    # The public command must resolve the real fixed archive before creating artifacts.
    selection = tmp_path / "selection.json"
    selection.write_text("{}")
    output = tmp_path / "maps"
    with pytest.raises(ValueError, match="approved selection manifest bytes changed"):
        build_document_maps(selection, tmp_path, output)
    assert not output.exists()
    output.mkdir()
    with pytest.raises(ValueError, match="must not already exist"):
        build_document_maps(selection, tmp_path, output)


def test_publishes_index_only_after_full_inventory_reverification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = _doc(b"primary.htm", b"<html>Source</html>")
    (tmp_path / "source.txt").write_bytes(raw)
    complete = {"role": "complete_submission", "path": "source.txt", "bytes": len(raw), "sha256": _sha(raw)}
    contract_path = tmp_path / "embedding.json"
    contract_path.write_text(
        json.dumps(
            {
                "attachments": {
                    "primary": {
                        "document": "primary.htm",
                        "embedded_sha256": _sha(b"<html>Source</html>"),
                        "embedded_bytes": len(b"<html>Source</html>"),
                        "packet_sha256": "f" * 64,
                        "relationship": "distinct",
                        "difference_audit": {"classification": "wrapper_only"},
                    }
                }
            }
        )
    )
    inventory = {"source_root": str(tmp_path)}
    contract = SourceContract(
        ({"holdout_id": "H01", "accession_number": "accession", "source_packets": [complete]},),
        {"H01": {"embedding": {"path": "embedding.json"}, "contract": {"kind": "test"}}},
        inventory,
    )
    calls = []

    def resolve(selection, root):
        calls.append("resolve")
        return contract

    monkeypatch.setattr(mapper, "resolve_source_contract", resolve)
    output = tmp_path / "maps"

    def verify(observed):
        assert observed == inventory
        assert (output / "H01.json").is_file()
        assert not (output / "index.json").exists()
        calls.append("reverify")
        return contract

    monkeypatch.setattr(mapper, "verify_source_contract_inventory", verify)
    result = build_document_maps(tmp_path / "selection.json", tmp_path, output)
    assert calls == ["resolve", "reverify"]
    assert json.loads((output / "index.json").read_text()) == result
    assert result["semantic_coverage_attested"] is False
    assert result["byte_accounting_scope"] == "complete_submission packets only"
    reference = result["filings"][0]["document_map"]
    assert reference["sha256"] == _sha((output / reference["path"]).read_bytes())
    output = tmp_path / "failed"

    def reject_changed_inventory(observed):
        verify(observed)
        raise ValueError("archive changed during preparation")

    monkeypatch.setattr(mapper, "verify_source_contract_inventory", reject_changed_inventory)
    with pytest.raises(ValueError, match="archive changed during preparation"):
        build_document_maps(tmp_path / "selection.json", tmp_path, output)
    assert (output / "H01.json").is_file()
    assert not (output / "index.json").exists()
