"""Every table, inline-XBRL fact and image in a packet gets exactly one checked disposition."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

import pytest

from evals.acceptance_source_modalities import (
    build_modality_inventory,
    load_modality_inventory,
    validate_modality_inventory,
)
from evals.acceptance_source_units import build_unit_manifest


ACCESSION = "0000000000-26-000001"
HIDDEN_FACT = b'<ix:nonNumeric name="dei:AmendmentFlag" contextRef="c1">false</ix:nonNumeric>'
HEADER = b'<div style="display:none"><ix:header><ix:hidden>' + HIDDEN_FACT + b"</ix:hidden></ix:header></div>"
FACT = b'<ix:nonFraction name="us-gaap:Revenues" contextRef="c1" unitRef="usd" decimals="-6">1,204</ix:nonFraction>'
TABLE = b"<table><tr><th>Quarter</th><th>Revenue</th></tr><tr><td>Q1</td><td>" + FACT + b"</td></tr></table>"
IMAGE = b'<img src="g1.jpg" alt="Revenue chart">'
PRIMARY = b"<html><body>" + HEADER + b"<p>Results</p>" + TABLE + b"<p>" + IMAGE + b"</p></body></html>"
GRAPHIC = b"\x89PNG\r\n\x1a\n" + bytes(range(64))
RAW_BY_ROLE = {"graphic": GRAPHIC, "primary": PRIMARY}
FLAGS = ("semantic_review_attested", "visual_review_attested", "fact_values_verified",
         "modality_completeness_attested", "admission_approved")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _at(part: bytes) -> tuple[int, int]:
    start = PRIMARY.index(part)
    return start, start + len(part)


PACKETS = [{"role": role, "sha256": _sha(raw), "byte_length": len(raw)} for role, raw in RAW_BY_ROLE.items()]
# The table straddles the unit boundary inside its header row, so it needs both units.
SPLIT = PRIMARY.index(b"<th>Revenue")


def _unit(role: str, start: int, end: int) -> dict[str, Any]:
    return {"packet_role": role, "structural_kind": "text", "registrant_scope": "registrant",
            "coverage_spans": [{"start": start, "end": end}], "context_spans": []}


MANIFEST = build_unit_manifest(accession_number=ACCESSION, packets=PACKETS, packet_bytes=RAW_BY_ROLE, units=[
    _unit("graphic", 0, len(GRAPHIC)),
    _unit("primary", 0, SPLIT),
    _unit("primary", SPLIT, len(PRIMARY)),
])
GRAPHIC_UNIT, FIRST, SECOND = (unit["unit_id"] for unit in MANIFEST["units"])


def _dispositions(**overrides: Any) -> dict[str, Any]:
    dispositions = {
        "T00001": {"kind": "assigned_to_review_units", "unit_ids": [FIRST, SECOND]},
        "F00001": {"kind": "assigned_to_review_units", "unit_ids": [FIRST]},
        "F00002": {"kind": "assigned_to_review_units", "unit_ids": [SECOND]},
        "I00001": {"kind": "unresolved", "reason": "graphic_not_viewed"},
    }
    dispositions.update(overrides)
    return dispositions


def _build(**overrides: Any) -> dict[str, Any]:
    arguments = {"accession_number": ACCESSION, "expected_packets": PACKETS, "packet_bytes": RAW_BY_ROLE,
                 "unit_manifest": MANIFEST, "packet_role": "primary", "dispositions": _dispositions()}
    arguments.update(overrides)
    return build_modality_inventory(**arguments)


def _validate(inventory: Any, **overrides: Any) -> dict[str, Any]:
    arguments = {"accession_number": ACCESSION, "expected_packets": PACKETS, "packet_bytes": RAW_BY_ROLE,
                 "unit_manifest": MANIFEST, "packet_role": "primary"}
    arguments.update(overrides)
    return validate_modality_inventory(inventory, **arguments)


def _rejected(inventory: Any, message: str, **overrides: Any) -> None:
    before = copy.deepcopy(inventory)
    with pytest.raises(ValueError, match=message):
        _validate(inventory, **overrides)
    assert inventory == before, "validation must not repair or reorder a rejected inventory"


# Independent reimplementation of the documented item identity; it imports no module helper.
def _oracle_item(modality: str, view_id: str, part: bytes, hidden: list[str]) -> dict[str, Any]:
    start, end = _at(part)
    record = {"modality": modality, "view_id": view_id, "start": start, "end": end,
              "sha256": _sha(part), "hidden_reasons": hidden}
    identity = {"accession_number": ACCESSION, "packet_sha256": _sha(PRIMARY), **record}
    return {"item_id": _sha(b"e7-source-modality-item-id-v1\x00" + _canonical(identity)), **record}


def test_every_table_fact_and_image_is_enumerated_and_dispositioned_once() -> None:
    inventory = _build()
    expected = [
        _oracle_item("table", "T00001", TABLE, []),
        _oracle_item("inline_xbrl_fact", "F00001", HIDDEN_FACT, ["inline_style_hidden", "inline_xbrl_hidden"]),
        _oracle_item("inline_xbrl_fact", "F00002", FACT, []),
        _oracle_item("image", "I00001", IMAGE, []),
    ]
    assert [{k: v for k, v in item.items() if k != "disposition"} for item in inventory["items"]] == expected
    assert all(inventory[flag] is False for flag in FLAGS) and "coverage_status" not in inventory

    stored = _canonical(inventory)
    summary = _validate(load_modality_inventory(stored))
    assert summary == {
        "schema_version": 1,
        "kind": "e7_offline_source_modality_validation",
        "inventory_sha256": _sha(stored),
        "accession_number": ACCESSION,
        "packet_role": "primary",
        "unit_manifest_sha256": _sha(_canonical(MANIFEST)),
        "item_counts": {"table": 1, "inline_xbrl_fact": 2, "image": 1},
        # The hidden header fact stays counted rather than dropping out of scope.
        "hidden_item_counts": {"table": 0, "inline_xbrl_fact": 1, "image": 0},
        "assigned_item_count": 3,
        "unresolved_item_ids": [expected[3]["item_id"]],
        "every_item_dispositioned": True,
        **{flag: False for flag in FLAGS},
        "limitations": inventory["limitations"],
    }

    # An item cannot drop out of scope: every omission, addition, reorder or relabel is rejected.
    items = inventory["items"]
    _rejected({**inventory, "items": items[:-1]}, "exactly the 4 items enumerated")
    _rejected({**inventory, "items": [*items, items[-1]]}, "exactly the 4 items enumerated")
    _rejected({**inventory, "items": [items[0], items[2], items[1], items[3]]}, "fact F00001 view_id does not match")
    unhidden = copy.deepcopy(items)
    unhidden[1]["hidden_reasons"] = []
    _rejected({**inventory, "items": unhidden}, "F00001 hidden_reasons does not match")
    relabelled = copy.deepcopy(items)
    relabelled[3]["modality"] = "table"
    _rejected({**inventory, "items": relabelled}, "image I00001 modality does not match")
    with pytest.raises(ValueError, match="no disposition for items: I00001"):
        _build(dispositions={k: v for k, v in _dispositions().items() if k != "I00001"})
    with pytest.raises(ValueError, match="packet does not contain: T00002"):
        _build(dispositions=_dispositions(T00002={"kind": "unresolved", "reason": "extra"}))

    # The inventory is bound to this packet, manifest, accession and the frozen contract.
    changed = PRIMARY.replace(b"1,204", b"1,205")
    changed_packets = [PACKETS[0], {**PACKETS[1], "sha256": _sha(changed)}]
    _rejected(inventory, "differs from the expected contract", expected_packets=changed_packets)
    other_manifest = build_unit_manifest(accession_number=ACCESSION, packets=PACKETS, packet_bytes=RAW_BY_ROLE,
                                         units=[_unit("graphic", 0, len(GRAPHIC)), _unit("primary", 0, len(PRIMARY))])
    _rejected(inventory, "bound to a different unit manifest", unit_manifest=other_manifest)
    _rejected(inventory, "inventory packet does not match the unit manifest packet", packet_role="graphic")
    with pytest.raises(ValueError, match="graphic cannot be projected as an HTML source view"):
        _build(packet_role="graphic", dispositions={})
    _rejected(inventory, "not declared in the unit manifest", packet_role="index")
    for key, value, message in (
        ("accession_number", "0000000000-26-000002", "different accession"),
        ("packet", {**inventory["packet"], "role": "graphic"}, "packet does not match"),
        ("admission_approved", True, "cannot attest"),
        ("visual_review_attested", 0, "cannot attest"),
        ("limitations", inventory["limitations"][:-1], "limitations differ"),
        ("schema_version", True, "unsupported"),
        ("coverage_status", "complete", "must be an object with exactly"),
    ):
        _rejected({**inventory, key: value}, message)
    for variant in (json.dumps(inventory, indent=2).encode("ascii"), stored + b"\n"):
        with pytest.raises(ValueError, match="not canonical JSON"):
            load_modality_inventory(variant)

    # A hidden element left open at end of file has an ambiguous scope, so enumeration fails closed.
    open_hidden = b"<html><body hidden><p>" + FACT + b"</p>"
    open_packets = [{"role": "primary", "sha256": _sha(open_hidden), "byte_length": len(open_hidden)}]
    open_manifest = build_unit_manifest(accession_number=ACCESSION, packets=open_packets,
                                        packet_bytes={"primary": open_hidden},
                                        units=[_unit("primary", 0, len(open_hidden))])
    with pytest.raises(ValueError, match="hidden element N000002 has no explicit end"):
        build_modality_inventory(accession_number=ACCESSION, expected_packets=open_packets,
                                 packet_bytes={"primary": open_hidden}, unit_manifest=open_manifest,
                                 packet_role="primary", dispositions={})


def test_assigned_items_must_lie_inside_the_named_review_units() -> None:
    # The table straddles both units, so naming either unit alone leaves bytes uncovered.
    table_start, table_end = _at(TABLE)
    with pytest.raises(ValueError, match=f"table T00001 bytes {SPLIT}:{table_end} are outside the named review units"):
        _build(dispositions=_dispositions(T00001={"kind": "assigned_to_review_units", "unit_ids": [FIRST]}))
    with pytest.raises(ValueError, match=f"table T00001 bytes {table_start}:{table_end} are outside"):
        _build(dispositions=_dispositions(T00001={"kind": "assigned_to_review_units", "unit_ids": [SECOND]}))
    for unit_ids, message in (
        ([SECOND], "F00001 names a unit that does not cover any of its bytes"),
        ([GRAPHIC_UNIT], "outside this packet's unit manifest"),
        ([FIRST, FIRST], "unique and in manifest order"),
        ([], "at least one review unit"),
        (["0" * 64], "outside this packet's unit manifest"),
    ):
        with pytest.raises(ValueError, match=message):
            _build(dispositions=_dispositions(F00001={"kind": "assigned_to_review_units", "unit_ids": unit_ids}))
    with pytest.raises(ValueError, match="unique and in manifest order"):
        _build(dispositions=_dispositions(T00001={"kind": "assigned_to_review_units", "unit_ids": [SECOND, FIRST]}))
    for disposition, message in (
        ({"kind": "unresolved", "reason": "Not Viewed"}, "invalid unresolved reason"),
        ({"kind": "reviewed"}, "kind must be one of"),
        ({"kind": "unresolved", "reason": "x", "unit_ids": [FIRST]}, "must be an object with exactly"),
    ):
        with pytest.raises(ValueError, match=message):
            _build(dispositions=_dispositions(I00001=disposition))
