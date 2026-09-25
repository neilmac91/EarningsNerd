"""Give every table, inline-XBRL fact and image in one HTML source packet an explicit disposition.

This is an internal, non-admitting engineering format built on the existing source view
(``acceptance_source_view.project_html``) and a validated unit manifest
(``acceptance_source_units``). It proves only that the expected items were enumerated from the
packet's own bytes by that deterministic parser, that each received exactly one disposition, and
that each assigned item's bytes lie inside the coverage of the review units it names. Hidden items
stay counted. It never attests review, visual inspection, fact values, E7 coverage status or
admission; unresolved items stay visible and hold completion.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from evals.acceptance_source_units import validate_unit_manifest
from evals.acceptance_source_view import VOID_TAGS, project_html


SCHEMA_VERSION = 1
INVENTORY_KIND = "e7_offline_source_modality_inventory"
VALIDATION_KIND = "e7_offline_source_modality_validation"
MODALITIES = ("table", "inline_xbrl_fact", "image")
DISPOSITIONS = ("assigned_to_review_units", "unresolved")
FACT_TAGS = frozenset({"ix:nonfraction", "ix:nonnumeric", "ix:fraction"})
# Any change to these strings, the flags, the modalities, the dispositions or any key set requires
# a new schema_version.
LIMITATIONS = (
    "Items are enumerated by the deterministic source-view parser; hidden status covers HTML attributes, inline style and ix:hidden only, and external CSS, scripts and browser rendering are not evaluated.",
    "An assignment proves only that the item's bytes lie inside the named review units' coverage; it does not prove the item was reviewed or that a table's caption, headers and footnotes were supplied together.",
    "Inline-XBRL facts are identified by their element spans; concepts, values, contexts, units, scale and sign are not validated.",
    "Image references are counted from img tags; the referenced graphic bytes, their member linkage and any visual inspection are not proven.",
    "No source review, E7 coverage_status or E7 admission is attested; unresolved items hold completion.",
)
ATTESTATION_FLAGS = (
    "semantic_review_attested",
    "visual_review_attested",
    "fact_values_verified",
    "modality_completeness_attested",
    "admission_approved",
)

_ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}")
_LABEL = re.compile(r"[a-z0-9][a-z0-9_.:-]{0,127}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_ITEM_ID_TAG = b"e7-source-modality-item-id-v1\x00"
_VIEW_PREFIX = {"table": "T", "inline_xbrl_fact": "F", "image": "I"}

_INVENTORY_KEYS = frozenset({
    "schema_version", "kind", "accession_number", "packet", "unit_manifest_sha256", "items", "limitations",
    *ATTESTATION_FLAGS,
})
_PACKET_KEYS = frozenset({"role", "sha256", "byte_length"})
_ITEM_KEYS = frozenset({"item_id", "modality", "view_id", "start", "end", "sha256", "hidden_reasons", "disposition"})
# Checked in this order so a rejection names the specific field; the identity hash comes last.
_ITEM_FIELDS = ("modality", "view_id", "start", "end", "sha256", "hidden_reasons", "item_id")
_DISPOSITION_KEYS = {
    "assigned_to_review_units": frozenset({"kind", "unit_ids"}),
    "unresolved": frozenset({"kind", "reason"}),
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def _same(value: Any, expected: Any) -> bool:
    """Exact structural equality with exact type identity at every level (no subclasses)."""
    if type(value) is not type(expected):
        return False
    if type(expected) is dict:
        return (all(type(key) is str for key in value) and set(value) == set(expected)
                and all(_same(value[key], expected[key]) for key in expected))
    if type(expected) is list:
        return len(value) == len(expected) and all(_same(a, b) for a, b in zip(value, expected))
    return value == expected


def _sha(data: bytes | memoryview) -> str:
    return hashlib.sha256(data).hexdigest()


def _object(value: Any, keys: frozenset[str], name: str) -> dict[str, Any]:
    if type(value) is not dict or any(type(key) is not str for key in value) or set(value) != keys:
        raise ValueError(f"{name} must be an object with exactly: {', '.join(sorted(keys))}")
    return value


def _token(value: Any, pattern: re.Pattern[str], name: str) -> str:
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise ValueError(f"invalid {name}")
    return value


def _packet(unit_manifest: Any, packet_role: Any) -> dict[str, Any]:
    role = _token(packet_role, _LABEL, "packet_role")
    for packet in unit_manifest["declared_packets"]:
        if packet["role"] == role:
            return packet
    raise ValueError(f"packet {role} is not declared in the unit manifest")


def _expected_items(accession: str, packet: dict[str, Any], raw: bytes) -> list[dict[str, Any]]:
    """Enumerate every table, inline-XBRL fact and image from the packet's own bytes, in view order."""
    try:
        projection = project_html(raw)
    except ValueError as exc:
        raise ValueError(f"packet {packet['role']} cannot be projected as an HTML source view: {exc}") from exc
    events = {event["id"]: event for event in projection["events"]}

    def bounds(start_event_id: str, end_event_id: str | None) -> tuple[int, int]:
        end_event = events[end_event_id] if end_event_id else events[start_event_id]
        return events[start_event_id]["start"], end_event["end"]

    hiding: list[tuple[int, int, list[str]]] = []
    for element in projection["elements"]:
        if element["hidden_reasons"]:
            if not element.get("end_event_id") and element["tag"] not in VOID_TAGS:
                raise ValueError(f"hidden element {element['id']} has no explicit end; its scope is ambiguous")
            hiding.append((*bounds(element["start_event_id"], element.get("end_event_id")),
                           element["hidden_reasons"]))

    found: list[tuple[str, str, int, int]] = []
    for table in projection["tables"]:
        found.append(("table", table["id"], *bounds(table["event_id"], table["end_event_id"])))
    facts = [element for element in projection["elements"] if element["tag"] in FACT_TAGS]
    for index, element in enumerate(facts, start=1):
        if not element.get("end_event_id"):
            raise ValueError(f"inline-XBRL fact element {element['id']} has no explicit end tag")
        found.append(("inline_xbrl_fact", f"F{index:05d}", *bounds(element["start_event_id"], element["end_event_id"])))
    for image in projection["images"]:
        found.append(("image", image["id"], *bounds(image["event_id"], None)))

    view = memoryview(raw)
    items = []
    for modality, view_id, start, end in found:
        reasons: list[str] = []
        for hidden_start, hidden_end, hidden_reasons in hiding:
            if hidden_start <= start and end <= hidden_end:
                reasons.extend(reason for reason in hidden_reasons if reason not in reasons)
        record = {"modality": modality, "view_id": view_id, "start": start, "end": end,
                  "sha256": _sha(view[start:end]), "hidden_reasons": reasons}
        identity = {"accession_number": accession, "packet_sha256": packet["sha256"], **record}
        items.append({"item_id": _sha(_ITEM_ID_TAG + _canonical(identity)), **record})
    return items


def _disposition(value: Any) -> dict[str, Any]:
    if type(value) is not dict or type(value.get("kind")) is not str or value["kind"] not in DISPOSITIONS:
        raise ValueError(f"item disposition kind must be one of: {', '.join(DISPOSITIONS)}")
    return _object(value, _DISPOSITION_KEYS[value["kind"]], f"{value['kind']} disposition")


def _check_assignment(item: dict[str, Any], unit_ids: Any, units: dict[str, tuple[int, list[tuple[int, int]]]]) -> None:
    """The named units must be unique, in manifest order, each touch the item, and jointly cover it."""
    name = f"{item['modality']} {item['view_id']}"
    if type(unit_ids) is not list or not unit_ids:
        raise ValueError(f"{name} assignment must name at least one review unit")
    positions = []
    for unit_id in unit_ids:
        if _token(unit_id, _SHA256, "unit_id") not in units:
            raise ValueError(f"{name} names a unit outside this packet's unit manifest")
        positions.append(units[unit_id][0])
    if positions != sorted(set(positions)):
        raise ValueError(f"{name} unit_ids must be unique and in manifest order")
    start, end = item["start"], item["end"]
    spans = sorted(span for unit_id in unit_ids for span in units[unit_id][1])
    for unit_id in unit_ids:
        if not any(span_start < end and start < span_end for span_start, span_end in units[unit_id][1]):
            raise ValueError(f"{name} names a unit that does not cover any of its bytes")
    cursor = start
    for span_start, span_end in spans:
        if span_end <= cursor or span_start >= end:
            continue
        if span_start > cursor:
            break
        cursor = span_end
    if cursor < end:
        raise ValueError(f"{name} bytes {cursor}:{end} are outside the named review units")


def validate_modality_inventory(
    inventory: Any,
    *,
    accession_number: Any,
    expected_packets: Any,
    packet_bytes: Any,
    unit_manifest: Any,
    packet_role: Any,
) -> dict[str, Any]:
    """Re-validate the unit manifest, re-enumerate the packet's items and check every disposition.

    ``expected_packets`` must come from the frozen source contract, never from the manifest. The
    item list is recomputed from the packet bytes, so an omitted, added, reordered or relabelled
    item is rejected. Nothing is repaired, coerced or reordered; any difference raises ``ValueError``.
    """
    manifest_summary = validate_unit_manifest(unit_manifest, accession_number=accession_number,
                                              expected_packets=expected_packets, packet_bytes=packet_bytes)
    accession = manifest_summary["accession_number"]
    packet = _packet(unit_manifest, packet_role)
    _object(inventory, _INVENTORY_KEYS, "source modality inventory")
    version, kind = inventory["schema_version"], inventory["kind"]
    if type(version) is not int or version != SCHEMA_VERSION or type(kind) is not str or kind != INVENTORY_KIND:
        raise ValueError("unsupported source modality inventory version or kind")
    if any(inventory[flag] is not False for flag in ATTESTATION_FLAGS):
        raise ValueError("a source modality inventory cannot attest review, completeness or admission")
    limitations = inventory["limitations"]
    if type(limitations) is not list or any(type(item) is not str for item in limitations) or limitations != list(LIMITATIONS):
        raise ValueError("source modality inventory limitations differ from this format")
    if type(inventory["accession_number"]) is not str or inventory["accession_number"] != accession:
        raise ValueError("source modality inventory declares a different accession")
    if not _same(inventory["packet"], {key: packet[key] for key in _PACKET_KEYS}):
        raise ValueError("inventory packet does not match the unit manifest packet")
    if type(inventory["unit_manifest_sha256"]) is not str or inventory["unit_manifest_sha256"] != manifest_summary["manifest_sha256"]:
        raise ValueError("inventory is bound to a different unit manifest")

    expected = _expected_items(accession, packet, packet_bytes[packet["role"]])
    recorded = inventory["items"]
    if type(recorded) is not list or len(recorded) != len(expected):
        raise ValueError(f"inventory must record exactly the {len(expected)} items enumerated from the packet, in view order")
    units = {unit["unit_id"]: (index, [(span["start"], span["end"]) for span in unit["coverage_spans"]])
             for index, unit in enumerate(unit_manifest["units"]) if unit["packet_id"] == packet["packet_id"]}
    unresolved = []
    for item, entry in zip(expected, recorded):
        _object(entry, _ITEM_KEYS, "inventory item")
        for field in _ITEM_FIELDS:
            if not _same(entry[field], item[field]):
                raise ValueError(f"{item['modality']} {item['view_id']} {field} does not match the packet bytes")
        disposition = _disposition(entry["disposition"])
        if disposition["kind"] == "unresolved":
            _token(disposition["reason"], _LABEL, "unresolved reason")
            unresolved.append(item["item_id"])
        else:
            _check_assignment(item, disposition["unit_ids"], units)

    def count(modality: str, hidden: bool | None = None) -> int:
        return sum(1 for item in expected if item["modality"] == modality
                   and (hidden is None or bool(item["hidden_reasons"]) == hidden))

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": VALIDATION_KIND,
        "inventory_sha256": _sha(_canonical(inventory)),
        "accession_number": accession,
        "packet_role": packet["role"],
        "unit_manifest_sha256": manifest_summary["manifest_sha256"],
        "item_counts": {modality: count(modality) for modality in MODALITIES},
        "hidden_item_counts": {modality: count(modality, hidden=True) for modality in MODALITIES},
        "assigned_item_count": len(expected) - len(unresolved),
        "unresolved_item_ids": unresolved,
        "every_item_dispositioned": True,
        **{flag: False for flag in ATTESTATION_FLAGS},
        "limitations": list(LIMITATIONS),
    }


def load_modality_inventory(raw: Any) -> dict[str, Any]:
    """Parse stored inventory bytes, requiring exactly ``canonical_json(inventory)``."""
    if type(raw) is not bytes:
        raise ValueError("stored source modality inventory must be bytes")
    try:
        inventory = json.loads(raw.decode("ascii"))
        canonical = _canonical(inventory)
    except (UnicodeDecodeError, ValueError, TypeError, RecursionError) as exc:
        raise ValueError("stored source modality inventory is not canonical JSON") from exc
    if canonical != raw or type(inventory) is not dict:
        raise ValueError("stored source modality inventory is not canonical JSON")
    return inventory


def build_modality_inventory(
    *,
    accession_number: Any,
    expected_packets: Any,
    packet_bytes: Any,
    unit_manifest: Any,
    packet_role: Any,
    dispositions: Any,
) -> dict[str, Any]:
    """Enumerate the packet's items and attach one disposition each (keyed by view ID), then validate.

    Every enumerated item needs a disposition; a missing or unknown view ID raises.
    """
    manifest_summary = validate_unit_manifest(unit_manifest, accession_number=accession_number,
                                              expected_packets=expected_packets, packet_bytes=packet_bytes)
    accession = manifest_summary["accession_number"]
    packet = _packet(unit_manifest, packet_role)
    items = _expected_items(accession, packet, packet_bytes[packet["role"]])
    if type(dispositions) is not dict or any(type(key) is not str for key in dispositions):
        raise ValueError("dispositions must map each item view_id to one disposition")
    view_ids = [item["view_id"] for item in items]
    missing = [view_id for view_id in view_ids if view_id not in dispositions]
    if missing:
        raise ValueError("no disposition for items: " + ", ".join(missing))
    unknown = sorted(set(dispositions) - set(view_ids))
    if unknown:
        raise ValueError("dispositions name items the packet does not contain: " + ", ".join(unknown))
    inventory = {
        "schema_version": SCHEMA_VERSION,
        "kind": INVENTORY_KIND,
        "accession_number": accession,
        "packet": {key: packet[key] for key in _PACKET_KEYS},
        "unit_manifest_sha256": manifest_summary["manifest_sha256"],
        "items": [{**item, "disposition": json.loads(_canonical(_disposition(dispositions[item["view_id"]])))}
                  for item in items],
        **{flag: False for flag in ATTESTATION_FLAGS},
        "limitations": list(LIMITATIONS),
    }
    validate_modality_inventory(inventory, accession_number=accession, expected_packets=expected_packets,
                                packet_bytes=packet_bytes, unit_manifest=unit_manifest, packet_role=packet_role)
    return inventory
