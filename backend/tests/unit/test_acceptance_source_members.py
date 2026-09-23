"""Every complete-submission member gets exactly one hash-bound disposition, nothing more."""

from __future__ import annotations

import binascii
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from evals.acceptance_document_map import map_submission
from evals.acceptance_source_members import build_member_ledger, validate_member_ledger
from evals.acceptance_source_units import build_unit_manifest


ACCESSION = "0000000000-26-000001"
PRIMARY = b"<html><body><p>Quarterly results: revenue \xe2\x82\xac1,204 million.</p></body></html>"
EXHIBIT = b"<html><body><table><tr><td>Q2</td><td>1,318</td></tr></table></body></html>"
IMAGE = b"\x89PNG\r\n\x1a\n" + bytes(range(200))
SUMMARY_XML = b"<?xml version='1.0'?><FilingSummary><ReportCount>0</ReportCount></FilingSummary>"
SCHEMA = b"<xs:schema xmlns:xs='http://www.w3.org/2001/XMLSchema'/>"
FLAGS = ("semantic_review_attested", "semantic_labels_verified", "modality_completeness_attested",
         "admission_approved")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _uuencode(data: bytes, name: str) -> bytes:
    lines = [binascii.b2a_uu(data[index:index + 45]) for index in range(0, len(data), 45)]
    return b"begin 644 " + name.encode("ascii") + b"\n" + b"".join(lines) + b"`\nend"


def _document(doc_type: str, sequence: int, filename: str, content: bytes) -> bytes:
    header = f"<DOCUMENT>\n<TYPE>{doc_type}\n<SEQUENCE>{sequence}\n<FILENAME>{filename}\n<TEXT>\n"
    return header.encode("ascii") + content + b"\n</TEXT>\n</DOCUMENT>\n"


SUBMISSION = (
    b"<SEC-DOCUMENT>0000000000-26-000001.txt\n<SEC-HEADER>synthetic</SEC-HEADER>\n"
    + _document("6-K", 1, "d1.htm", PRIMARY)
    + _document("EX-99.1", 2, "d1ex991.htm", EXHIBIT)
    + _document("GRAPHIC", 3, "g1.png", _uuencode(IMAGE, "g1.png"))
    + _document("EX-99.2", 4, "d1ex992.htm", EXHIBIT)
    + _document("XML", 5, "FilingSummary.xml", SUMMARY_XML)
    + _document("EX-101.SCH", 6, "d1-20260630.xsd", SCHEMA)
    + b"</SEC-DOCUMENT>\n"
)


def _document_map(tmp_path: Path, submission: bytes = SUBMISSION) -> dict[str, Any]:
    path = tmp_path / "submission.txt"
    path.write_bytes(submission)
    return map_submission(path, _sha(submission), len(submission), {"attachments": {}})


def _unit_manifest() -> dict[str, Any]:
    packets = {"earnings_exhibit": EXHIBIT, "graphic": IMAGE, "primary": PRIMARY}
    return build_unit_manifest(
        accession_number=ACCESSION,
        packets=[{"role": role, "sha256": _sha(raw), "byte_length": len(raw)} for role, raw in packets.items()],
        packet_bytes=packets,
        units=[{"packet_role": role, "structural_kind": "document", "registrant_scope": "registrant",
                "coverage_spans": [{"start": 0, "end": len(raw)}], "context_spans": []}
               for role, raw in packets.items()],
    )


def _dispositions(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    manifest_sha256 = _sha(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("ascii"))

    def assigned(role: str, representation: str) -> dict[str, Any]:
        return {"kind": "assigned_to_review_units", "unit_manifest_sha256": manifest_sha256,
                "packet_role": role, "representation": representation}

    return [
        assigned("primary", "content"),
        assigned("earnings_exhibit", "content"),
        assigned("graphic", "decoded"),
        {"kind": "exact_duplicate", "duplicate_of_ordinal": 2},
        {"kind": "declared_non_content_packaging", "basis": "filing_summary_index"},
        {"kind": "unresolved", "reason": "xbrl_schema_not_inventoried"},
    ]


def _oracle_member_id(ordinal: int, doc_type: str, filename: str, payload: dict[str, Any]) -> str:
    identity = {"accession_number": ACCESSION, "submission_sha256": _sha(SUBMISSION), "ordinal": ordinal,
                "declared_type": doc_type, "declared_filename": filename, "declared_sequence": str(ordinal),
                "payload": {"start": payload["start"], "end": payload["end"], "sha256": payload["sha256"]}}
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return _sha(b"e7-source-member-id-v1\x00" + canonical)


def test_member_ledger_dispositions_every_member_and_proves_only_hash_linkages(tmp_path: Path) -> None:
    document_map = _document_map(tmp_path)
    manifest = _unit_manifest()
    dispositions = _dispositions(manifest)
    pristine = copy.deepcopy((document_map, dispositions, manifest))
    ledger = build_member_ledger(accession_number=ACCESSION, submission=SUBMISSION, document_map=document_map,
                                 dispositions=dispositions, unit_manifests=[manifest])
    assert (document_map, dispositions, manifest) == pristine, "construction must not mutate its inputs"

    # Identities recompute independently; the graphic decodes to its exact original bytes.
    expected_names = [("6-K", "d1.htm"), ("EX-99.1", "d1ex991.htm"), ("GRAPHIC", "g1.png"),
                      ("EX-99.2", "d1ex992.htm"), ("XML", "FilingSummary.xml"), ("EX-101.SCH", "d1-20260630.xsd")]
    assert [entry["member_id"] for entry in ledger["members"]] == [
        _oracle_member_id(index + 1, doc_type, filename, document_map["documents"][index]["payload"])
        for index, (doc_type, filename) in enumerate(expected_names)]
    assert ledger["members"][2]["encoding"] == "uuencode"
    assert ledger["members"][2]["decoded"] == {"sha256": _sha(IMAGE), "byte_length": len(IMAGE)}
    assert all(entry["decoded"] is None for index, entry in enumerate(ledger["members"]) if index != 2)
    assert "coverage_status" not in ledger and all(ledger[flag] is False for flag in FLAGS)

    summary = validate_member_ledger(json.loads(json.dumps(ledger)), accession_number=ACCESSION,
                                     submission=SUBMISSION, document_map=document_map, unit_manifests=[manifest])
    assert summary["disposition_counts"] == {"assigned_to_review_units": 3, "exact_duplicate": 1,
                                             "declared_non_content_packaging": 1, "unresolved": 1}
    assert summary["encoded_member_count"] == 1
    assert summary["unresolved_member_ids"] == [ledger["members"][5]["member_id"]]
    assert summary["member_count"] == 6 and all(summary[flag] is False for flag in FLAGS)

    def rejected(candidate: Any, message: str, *, submission: bytes = SUBMISSION, mapped: Any = None,
                 manifests: Any = None, accession: str = ACCESSION) -> None:
        before = copy.deepcopy(candidate)
        with pytest.raises(ValueError, match=message):
            validate_member_ledger(candidate, accession_number=accession, submission=submission,
                                   document_map=document_map if mapped is None else mapped,
                                   unit_manifests=[manifest] if manifests is None else manifests)
        assert candidate == before, "validation must not repair a rejected ledger"

    def tampered(path: tuple[Any, ...], value: Any) -> dict[str, Any]:
        changed = copy.deepcopy(ledger)
        target = changed
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        return changed

    # Hash-proven duplicates only: a same-length but different member cannot be a duplicate.
    for path, value, message in (
        (("members", 3, "disposition", "duplicate_of_ordinal"), 1, "not a byte-identical duplicate"),
        (("members", 3, "disposition", "duplicate_of_ordinal"), 4, "must name another member ordinal"),
        (("members", 3, "disposition", "duplicate_of_ordinal"), True, "must name another member ordinal"),
        (("members", 3, "disposition", "duplicate_of_ordinal"), 6, "not a byte-identical duplicate"),
        (("members", 1, "disposition", "representation"), "decoded", "not the named unit-manifest packet"),
        (("members", 0, "disposition", "packet_role"), "earnings_exhibit", "not the named unit-manifest packet"),
        (("members", 0, "disposition", "unit_manifest_sha256"), "0" * 64, "not the named unit-manifest packet"),
        (("members", 4, "disposition"), {"kind": "reviewed", "basis": "x"}, "disposition kind must be one of"),
        (("members", 5, "disposition", "coverage_status"), "complete", "unresolved disposition must be an object"),
        (("members", 0, "member_id"), "0" * 64, "member_id does not match"),
        (("members", 2, "decoded"), None, "decoded does not match"),
        (("members", 2, "declared_type"), "EX-99.3", "declared_type does not match"),
        (("submission", "member_count"), 5, "submission identity does not match"),
        (("admission_approved",), True, "cannot attest"),
        (("modality_completeness_attested",), 0, "cannot attest"),
        (("limitations",), ledger["limitations"][:-1], "limitations differ"),
        (("coverage_status",), "complete", "source member ledger must be an object"),
    ):
        rejected(tampered(path, value), message)
    two_claims = tampered(("members", 3, "disposition"), dict(ledger["members"][1]["disposition"]))
    rejected(two_claims, "cannot claim the same unit-manifest packet")
    duplicate_of_unresolved = tampered(("members", 1, "disposition"),
                                       {"kind": "unresolved", "reason": "not_reviewed"})
    rejected(duplicate_of_unresolved, "must point at a member assigned to review units")
    rejected({**ledger, "members": ledger["members"][:-1]}, "exactly one entry per mapped member")
    rejected({**ledger, "members": [ledger["members"][1], ledger["members"][0], *ledger["members"][2:]]},
             "does not match the submission bytes")
    rejected(ledger, "different accession", accession="0000000000-26-000002")
    rejected(ledger, "not the named unit-manifest packet", manifests=[])
    changed = SUBMISSION.replace(b"1,318", b"1,319")
    rejected(ledger, "does not describe the supplied submission bytes", submission=changed)
    rejected(ledger, "bytes do not match the document map", submission=changed,
             mapped={**document_map, "source_sha256": _sha(changed)})

    # Encoded members decode strictly or not at all; nothing is repaired.
    broken = SUBMISSION.replace(b"`\nend", b"`\n")
    with pytest.raises(ValueError, match="no end line"):
        build_member_ledger(accession_number=ACCESSION, submission=broken,
                            document_map=_document_map(tmp_path, broken), dispositions=dispositions,
                            unit_manifests=[manifest])
    with pytest.raises(ValueError, match="exactly one disposition per mapped member"):
        build_member_ledger(accession_number=ACCESSION, submission=SUBMISSION, document_map=document_map,
                            dispositions=dispositions[:-1], unit_manifests=[manifest])
