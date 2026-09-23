"""Source review units prove byte custody and exact declared-packet coverage, nothing more."""

from __future__ import annotations

import copy
import hashlib
import json
import struct
from typing import Any

import pytest

from evals.acceptance_source_units import build_unit_manifest, load_unit_manifest, validate_unit_manifest


ACCESSION = "0000000000-26-000001"
OTHER_ACCESSION = "0000000000-26-000002"
CAPTION = "<caption>Revenue (€ million)</caption>".encode("utf-8")
HEADER = b"<tr><th>Quarter</th><th>Amount</th></tr>"
ROW_1 = b"<tr><td>Q1</td><td>1,204*</td></tr>"
ROW_2 = b"<tr><td>Q2</td><td>1,318*</td></tr>"
FOOTNOTE = "<p>* Unaudited; café segment excluded.</p>".encode("utf-8")
PRIMARY = b"<table>" + CAPTION + HEADER + ROW_1 + ROW_2 + b"</table>" + FOOTNOTE
GRAPHIC = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + bytes(range(256))
RAW_BY_ROLE = {"graphic": GRAPHIC, "primary": PRIMARY}
FLAGS = ("semantic_review_attested", "semantic_labels_verified", "source_set_completeness_attested",
         "member_modality_completeness_attested", "admission_approved")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _range(part: bytes) -> dict[str, int]:
    start = PRIMARY.index(part)
    return {"start": start, "end": start + len(part)}


def _packets() -> list[dict[str, Any]]:
    return [{"role": role, "sha256": _sha(raw), "byte_length": len(raw)} for role, raw in RAW_BY_ROLE.items()]


def _units() -> list[dict[str, Any]]:
    caption, header = _range(CAPTION), _range(HEADER)
    return [
        {"packet_role": "graphic", "structural_kind": "binary_image", "registrant_scope": "registrant",
         "coverage_spans": [{"start": 0, "end": len(GRAPHIC)}], "context_spans": []},
        {"packet_role": "primary", "structural_kind": "table_fragment", "registrant_scope": "registrant",
         "coverage_spans": [{"start": 0, "end": _range(ROW_1)["end"]}], "context_spans": []},
        # Non-contiguous coverage (second row plus its footnote); the touching caption and header
        # are separately hashed context items, and the header repeats in the next unit.
        {"packet_role": "primary", "structural_kind": "table_fragment", "registrant_scope": "registrant",
         "coverage_spans": [_range(ROW_2), _range(FOOTNOTE)], "context_spans": [caption, header]},
        {"packet_role": "primary", "structural_kind": "markup", "registrant_scope": "registrant",
         "coverage_spans": [_range(b"</table>")], "context_spans": [header]},
    ]


def _declared(accession: str = ACCESSION, **overrides: Any) -> dict[str, Any]:
    declaration = {"accession_number": accession, "packets": _packets(), "packet_bytes": dict(RAW_BY_ROLE),
                   "units": _units()}
    declaration.update(overrides)
    return declaration


# Independent reimplementation of the documented encoding; it deliberately imports no module helper.
def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _oracle_packet_id(accession: str, role: str, raw: bytes) -> str:
    identity = {"accession_number": accession, "byte_length": len(raw), "role": role, "sha256": _sha(raw)}
    return _sha(b"e7-source-unit-packet-id-v1\x00" + _canonical(identity))


def _oracle_unit_sha256(fragments: list[bytes]) -> str:
    framed = b"".join(struct.pack(">Q", len(fragment)) + fragment for fragment in fragments)
    return _sha(b"e7-source-unit-coverage-v1\x00" + struct.pack(">Q", len(fragments)) + framed)


def _oracle_unit(accession: str, raw: bytes, declared: dict[str, Any]) -> dict[str, Any]:
    def hashed(spans: list[dict[str, int]]) -> list[dict[str, Any]]:
        return [{**span, "sha256": _sha(raw[span["start"]:span["end"]])} for span in spans]

    record = {
        "packet_id": _oracle_packet_id(accession, declared["packet_role"], raw),
        "structural_kind": declared["structural_kind"],
        "registrant_scope": declared["registrant_scope"],
        "coverage_spans": hashed(declared["coverage_spans"]),
        "context_spans": hashed(declared["context_spans"]),
        "unit_sha256": _oracle_unit_sha256([raw[s["start"]:s["end"]] for s in declared["coverage_spans"]]),
    }
    unit_id = _sha(b"e7-source-unit-id-v1\x00" + _canonical({"accession_number": accession, **record}))
    return {"unit_id": unit_id, **record}


def _rejected(manifest: Any, message: str, packet_bytes: Any = None, accession: str = ACCESSION) -> None:
    before = copy.deepcopy(manifest)
    with pytest.raises(ValueError, match=message):
        validate_unit_manifest(manifest, accession_number=accession,
                               packet_bytes=RAW_BY_ROLE if packet_bytes is None else packet_bytes)
    assert manifest == before, "validation must not repair or reorder a rejected manifest"


def _tampered(manifest: dict[str, Any], path: tuple[Any, ...], value: Any) -> dict[str, Any]:
    changed = copy.deepcopy(manifest)
    target = changed
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return changed


class _LyingBytes(bytes):
    def __len__(self) -> int:
        return 1


class _MasqueradingKey(str):
    """A key that hashes and compares like another key while serializing as itself."""

    def __hash__(self) -> int:
        return hash("kind")

    def __eq__(self, other: object) -> bool:
        return other == "kind"


def test_units_partition_declared_packets_and_bind_recomputable_identities() -> None:
    declared = _declared()
    pristine = copy.deepcopy(declared)
    manifest = build_unit_manifest(**declared)
    assert declared == pristine, "construction must not mutate its declarations"

    # Every identity matches an independent reimplementation of the documented encoding.
    assert [packet["packet_id"] for packet in manifest["declared_packets"]] == [
        _oracle_packet_id(ACCESSION, role, raw) for role, raw in RAW_BY_ROLE.items()]
    assert manifest["units"] == [_oracle_unit(ACCESSION, RAW_BY_ROLE[unit["packet_role"]], unit)
                                 for unit in declared["units"]]
    assert "coverage_status" not in manifest and all(manifest[flag] is False for flag in FLAGS)
    disclaimers = " ".join(manifest["limitations"])
    for required in ("unverified declarations", "not every source in the filing", "not a semantically safe",
                     "hidden inline-XBRL facts, images", "model-context custody",
                     "E7 coverage_status or E7 admission"):
        assert required in disclaimers

    # A JSON round trip validates; repeated context is reported separately and never counted as coverage.
    round_tripped = json.loads(json.dumps(manifest))
    summary = validate_unit_manifest(round_tripped, accession_number=ACCESSION, packet_bytes=RAW_BY_ROLE)
    context_bytes = len(CAPTION) + 2 * len(HEADER)
    assert summary == {
        "schema_version": 1,
        "kind": "e7_offline_source_unit_validation",
        "manifest_sha256": _sha(_canonical(manifest)),
        "accession_number": ACCESSION,
        "packet_count": 2,
        "unit_count": 4,
        "declared_packet_bytes": len(GRAPHIC) + len(PRIMARY),
        "coverage_bytes": len(GRAPHIC) + len(PRIMARY),
        "context_span_count": 3,
        "context_span_bytes_not_counted_as_coverage": context_bytes,
        "declared_packet_byte_partition": "exact",
        **{flag: False for flag in FLAGS},
        "limitations": manifest["limitations"],
    }
    assert _canonical(build_unit_manifest(**_declared())) == _canonical(manifest)

    # Offsets are bytes, not characters ("€" before "é" is three bytes). A byte-valid split inside
    # "é" is accepted as custody only; nothing decodes or repairs it.
    accent = PRIMARY.index("é".encode("utf-8"))
    assert PRIMARY.decode("utf-8").index("é") == accent - 2
    split_units = _units()
    split_units[2]["coverage_spans"][1] = {"start": _range(FOOTNOTE)["start"], "end": accent + 1}
    split_units.append({**_units()[3], "structural_kind": "text", "context_spans": [],
                        "coverage_spans": [{"start": accent + 1, "end": len(PRIMARY)}]})
    split = build_unit_manifest(**_declared(units=split_units))
    assert split["units"][4]["coverage_spans"][0]["sha256"] == _sha(PRIMARY[accent + 1:])
    with pytest.raises(UnicodeDecodeError):
        PRIMARY[accent + 1:].decode("utf-8")

    # Identical bytes under two declared roles remain two packets, each partitioned and counted.
    copies = build_unit_manifest(**_declared(
        packets=[_packets()[0], {**_packets()[0], "role": "graphic_copy"}, _packets()[1]],
        packet_bytes={**RAW_BY_ROLE, "graphic_copy": GRAPHIC},
        units=[_units()[0], {**_units()[0], "packet_role": "graphic_copy"}, *_units()[1:]]))
    assert len({packet["packet_id"] for packet in copies["declared_packets"]}) == 3
    assert validate_unit_manifest(copies, accession_number=ACCESSION, packet_bytes={
        **RAW_BY_ROLE, "graphic_copy": GRAPHIC})["coverage_bytes"] == 2 * len(GRAPHIC) + len(PRIMARY)

    # Exact union, not equal total length: shifting one span keeps the byte total but opens a gap
    # on one side and an overlap on the other; both directions are rejected.
    row_2 = _range(ROW_2)
    for shift, message in ((-1, f"coverage spans overlap in packet primary at byte {row_2['start'] - 1}"),
                           (1, f"coverage gap in packet primary at byte {row_2['start']}")):
        shifted = _units()
        shifted[2]["coverage_spans"][0] = {"start": row_2["start"] + shift, "end": row_2["end"] + shift}
        covered = sum(span["end"] - span["start"] for unit in shifted for span in unit["coverage_spans"])
        assert covered == len(GRAPHIC) + len(PRIMARY)
        with pytest.raises(ValueError, match=message):
            build_unit_manifest(**_declared(units=shifted))

    # Context cannot fill a coverage gap, and every declared packet needs coverage units.
    context_only = _units()[:3]
    context_only[2]["context_spans"].append(_range(b"</table>"))
    with pytest.raises(ValueError, match=f"coverage gap in packet primary at byte {row_2['end']}"):
        build_unit_manifest(**_declared(units=context_only))
    with pytest.raises(ValueError, match="declared packet graphic has no coverage units"):
        build_unit_manifest(**_declared(units=_units()[1:]))
    for edge, message in (({"start": 1, "end": len(GRAPHIC)}, "coverage gap in packet graphic at byte 0"),
                          ({"start": 0, "end": len(GRAPHIC) - 1}, f"coverage gap in packet graphic at byte {len(GRAPHIC) - 1}")):
        with pytest.raises(ValueError, match=message):
            build_unit_manifest(**_declared(units=[{**_units()[0], "coverage_spans": [edge]}, *_units()[1:]]))

    # Validator custody: each tampered manifest is rejected and left exactly as supplied.
    _rejected({**manifest, "units": manifest["units"][:3]}, f"coverage gap in packet primary at byte {row_2['end']}")
    _rejected({**manifest, "units": [*manifest["units"], manifest["units"][3]]}, "duplicate unit_id")
    _rejected({**manifest, "units": [manifest["units"][0], manifest["units"][2], manifest["units"][1],
                                     manifest["units"][3]]}, "units must be ordered")
    _rejected({**manifest, "declared_packets": manifest["declared_packets"][::-1]}, "ascending role order")
    _rejected({**manifest, "declared_packets": []}, "declared_packets must be a non-empty list", {})
    masquerade = {(_MasqueradingKey("coverage_status") if key == "kind" else key): value
                  for key, value in manifest.items()}
    _rejected(masquerade, "source unit manifest must be an object")
    changed_byte = PRIMARY.replace(b"1,318", b"1,319")
    for packet_bytes, message in (
        ({**RAW_BY_ROLE, "primary": changed_byte}, "primary bytes do not match"),
        ({**RAW_BY_ROLE, "primary": PRIMARY + b" "}, "primary bytes do not match"),
        ({**RAW_BY_ROLE, "primary": bytearray(PRIMARY)}, "immutable bytes"),
        ({**RAW_BY_ROLE, "graphic": _LyingBytes(GRAPHIC)}, "immutable bytes"),
        ({"primary": PRIMARY}, "exactly the declared packet roles"),
        ({**RAW_BY_ROLE, "index": b"extra"}, "exactly the declared packet roles"),
        ({"graphic": GRAPHIC, _MasqueradingKey("primary"): PRIMARY}, "exactly the declared packet roles"),
    ):
        _rejected(manifest, message, packet_bytes)
    _rejected(_tampered(manifest, ("accession_number",), OTHER_ACCESSION), "declares a different accession")
    for path, value, message in (
        (("accession_number",), OTHER_ACCESSION, "packet_id does not match declared packet graphic"),
        (("declared_packets", 1, "byte_length"), len(PRIMARY) + 1, "packet_id does not match"),
        (("declared_packets", 1, "byte_length"), float(len(PRIMARY)), "positive integer"),
        (("declared_packets", 1, "role"), "primary_v2", "packet_id does not match"),
        (("declared_packets", 1, "sha256"), _sha(changed_byte), "packet_id does not match"),
        (("declared_packets", 1, "admitted"), True, "declared packet must be an object with exactly"),
        (("units", 2, "structural_kind"), "text", "unit unit_id does not match"),
        (("units", 2, "registrant_scope"), "guarantor", "unit unit_id does not match"),
        (("units", 2, "unit_sha256"), _oracle_unit_sha256([ROW_2 + FOOTNOTE]), "unit unit_sha256 does not match"),
        (("units", 2, "coverage_spans", 0, "start"), row_2["start"] + 1, "unit coverage_spans does not match"),
        (("units", 2, "context_spans", 1, "end"), _range(HEADER)["end"] - 1, "unit context_spans does not match"),
        (("units", 2, "context_spans", 1, "reviewed"), True, "context_spans entry must be an object"),
        (("units", 2, "coverage_status"), "complete", "unit must be an object with exactly"),
        (("units", 0), build_unit_manifest(**_declared(OTHER_ACCESSION))["units"][0], "undeclared packet"),
        (("coverage_status",), "complete", "source unit manifest must be an object"),
        (("kind",), "e7_offline_source_unit_manifest_v2", "unsupported source unit manifest"),
        (("schema_version",), True, "unsupported source unit manifest"),
        (("schema_version",), 1.0, "unsupported source unit manifest"),
        (("admission_approved",), True, "cannot attest"),
        (("semantic_review_attested",), 0, "cannot attest"),
        (("source_set_completeness_attested",), None, "cannot attest"),
        (("limitations",), manifest["limitations"][:-1], "limitations differ"),
    ):
        accession = OTHER_ACCESSION if path == ("accession_number",) else ACCESSION
        _rejected(_tampered(manifest, path, value), message, accession=accession)


def test_unit_encoding_separates_fragment_boundaries_and_pins_canonical_bytes() -> None:
    def framed_unit(raw: bytes, first: tuple[int, int], second: tuple[int, int]) -> dict[str, Any]:
        gap = {"start": first[1], "end": second[0]}
        return build_unit_manifest(
            accession_number=ACCESSION,
            packets=[{"role": "primary", "sha256": _sha(raw), "byte_length": len(raw)}],
            packet_bytes={"primary": raw},
            units=[
                {"packet_role": "primary", "structural_kind": "text", "registrant_scope": "registrant",
                 "coverage_spans": [{"start": first[0], "end": first[1]},
                                    {"start": second[0], "end": second[1]}], "context_spans": []},
                {"packet_role": "primary", "structural_kind": "text", "registrant_scope": "registrant",
                 "coverage_spans": [gap], "context_spans": []},
            ],
        )["units"][0]

    left, right = framed_unit(b"abXc", (0, 2), (3, 4)), framed_unit(b"aXbc", (0, 1), (2, 4))
    assert _sha(b"ab" + b"c") == _sha(b"a" + b"bc"), "plain concatenation would collide"
    assert left["unit_sha256"] == _oracle_unit_sha256([b"ab", b"c"])
    assert right["unit_sha256"] == _oracle_unit_sha256([b"a", b"bc"])
    assert left["unit_sha256"] != right["unit_sha256"]

    # The documented worked example is pinned byte for byte (an independent design review recomputed
    # the same vectors from the specification alone).
    raw = b"abXcde"
    manifest = build_unit_manifest(
        accession_number=ACCESSION,
        packets=[{"role": "primary", "sha256": _sha(raw), "byte_length": len(raw)}],
        packet_bytes={"primary": raw},
        units=[
            {"packet_role": "primary", "structural_kind": "text", "registrant_scope": "registrant",
             "coverage_spans": [{"start": 0, "end": 2}, {"start": 3, "end": 4}], "context_spans": []},
            {"packet_role": "primary", "structural_kind": "text", "registrant_scope": "registrant",
             "coverage_spans": [{"start": 2, "end": 3}, {"start": 4, "end": 6}],
             "context_spans": [{"start": 0, "end": 2}]},
        ],
    )
    assert manifest["declared_packets"] == [{
        "packet_id": "8b5a7530cecb1e5ef0a5f9ab011e5238cb8a3987851d5fa568528db6a36d8a39",
        "role": "primary",
        "sha256": "535c9349dd5a5816c1d21c89aed279c46320a9693036e973ea547f0bd0f482c8",
        "byte_length": 6,
    }]
    assert [(unit["unit_id"], unit["unit_sha256"]) for unit in manifest["units"]] == [
        ("a4f6def0bfa75f139b4f145b01ad19b18ed202de5758fc19ed9b579bf721044a",
         "7ae7f33b1c1424603f480fa8ddd79064bb71a15e1aa2c3b1513623f3387f77a4"),
        ("e575eeaf1918dc720ecc75be88cb6a4d5fc7bffba553afbc59eb3fc2b55d2f4e",
         "b031a940ab59b3a68f207048db42605a357d1aafd08a06c1d5adc4be62502d83"),
    ]
    # One whole-manifest vector freezes the limitation text, flags, key sets, kind and encoding:
    # changing any of them without a new schema_version fails here.
    stored = _canonical(manifest)
    assert _sha(stored) == "ea73eff3b57db48cd9f3c127e719ca389d60d5afd93f4861ea496464fc521e7b"
    summary = validate_unit_manifest(load_unit_manifest(stored), accession_number=ACCESSION,
                                     packet_bytes={"primary": raw})
    assert summary["manifest_sha256"] == _sha(stored)

    # Stored bytes must be exactly the canonical form: variants would give one manifest two hashes,
    # and a duplicate key would hash one claim while parsing another.
    duplicate_flag = stored.replace(b'"admission_approved":false', b'"admission_approved":true,"admission_approved":false')
    for variant in (json.dumps(manifest, indent=2, sort_keys=True).encode("ascii") + b"\n", stored + b"\n",
                    duplicate_flag, stored.replace(b'"schema_version":1', b'"schema_version":1e0')):
        assert variant != stored
        with pytest.raises(ValueError, match="not canonical JSON"):
            load_unit_manifest(variant)
    with pytest.raises(ValueError, match="must be bytes"):
        load_unit_manifest(stored.decode("ascii"))


def _with(unit_index: int, field: str, value: Any) -> dict[str, Any]:
    units = _units()
    units[unit_index][field] = value
    return _declared(units=units)


def _with_packet(field: str, value: Any) -> dict[str, Any]:
    return _declared(packets=[_packets()[0], {**_packets()[1], field: value}])


@pytest.mark.parametrize(("declaration", "message"), [
    (_with(1, "coverage_spans", [{"start": False, "end": 10}]), "offsets must be integers"),
    (_with(1, "coverage_spans", [{"start": 0, "end": True}]), "offsets must be integers"),
    (_with(1, "coverage_spans", [{"start": 0.0, "end": 10}]), "offsets must be integers"),
    (_with(1, "coverage_spans", [{"start": "0", "end": 10}]), "offsets must be integers"),
    (_with(1, "coverage_spans", [{"start": None, "end": 10}]), "offsets must be integers"),
    (_with(1, "coverage_spans", [{"start": 5, "end": 5}]), "0 <= start < end"),
    (_with(1, "coverage_spans", [{"start": 6, "end": 5}]), "0 <= start < end"),
    (_with(1, "coverage_spans", [{"start": -1, "end": 5}]), "0 <= start < end"),
    (_with(1, "coverage_spans", [{"start": 0, "end": len(PRIMARY) + 1}]), "0 <= start < end"),
    (_with(1, "coverage_spans", [{"start": 4, "end": 8}, {"start": 0, "end": 2}]), "ascending and non-overlapping"),
    (_with(1, "coverage_spans", [{"start": 0, "end": 4}, {"start": 3, "end": 8}]), "ascending and non-overlapping"),
    (_with(1, "coverage_spans", [{"start": 0, "end": 4}, {"start": 4, "end": 8}]), "at least one byte between"),
    (_with(1, "coverage_spans", [[0, 10]]), "exactly: end, start"),
    (_with(1, "coverage_spans", [{"start": 0, "end": 10, "sha256": "0" * 64}]), "exactly: end, start"),
    (_with(1, "coverage_spans", []), "at least one byte"),
    (_with(1, "coverage_spans", ({"start": 0, "end": 10},)), "must be a list"),
    (_with(2, "context_spans", [_range(HEADER), _range(CAPTION)]), "context_spans must be ascending"),
    (_with(2, "context_spans", [_range(CAPTION), _range(HEADER),
                                {"start": _range(FOOTNOTE)["start"] - 2, "end": _range(FOOTNOTE)["start"] + 1}]),
     "must not overlap the unit's own coverage"),
    (_with(0, "structural_kind", "Binary Image"), "invalid structural_kind"),
    (_with(0, "registrant_scope", ""), "invalid registrant_scope"),
    (_with(0, "registrant_scope", "r" * 129), "invalid registrant_scope"),
    (_with(0, "packet_role", "index"), "undeclared packet"),
    (_declared(units=[{k: v for k, v in _units()[0].items() if k != "context_spans"}, *_units()[1:]]),
     "declared unit must be an object"),
    (_declared(units=[_units()[1], _units()[0], *_units()[2:]]), "units must be ordered"),
    (_declared(accession_number=" 0000000000-26-000001"), "invalid accession_number"),
    (_declared(accession_number="0000000000-26-000001\n"), "invalid accession_number"),
    (_declared(accession_number="٠٠٠٠٠٠٠٠٠٠-26-000001"), "invalid accession_number"),
    (_declared(accession_number="000000000０-26-000001"), "invalid accession_number"),
    (_declared(accession_number=""), "invalid accession_number"),
    (_with_packet("role", "Primary"), "invalid packet role"),
    (_with_packet("role", "primary\n"), "invalid packet role"),
    (_with_packet("byte_length", 0), "empty packets"),
    (_with_packet("byte_length", True), "positive integer"),
    (_with_packet("byte_length", float(len(PRIMARY))), "positive integer"),
    (_with_packet("sha256", _sha(PRIMARY).upper()), "invalid packet sha256"),
    (_declared(packets=[_packets()[1], _packets()[0]]), "ascending role order"),
    (_declared(packets=[_packets()[1], _packets()[1]], packet_bytes={"primary": PRIMARY}), "ascending role order"),
    (_declared(packets=[], packet_bytes={}, units=[]), "non-empty list"),
])
def test_malformed_declarations_are_rejected_without_coercion(declaration: dict[str, Any], message: str) -> None:
    pristine = copy.deepcopy(declaration)
    with pytest.raises(ValueError, match=message):
        build_unit_manifest(**declaration)
    assert declaration == pristine
