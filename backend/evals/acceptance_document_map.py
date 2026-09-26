"""Offline byte-accounted document map; not semantic coverage or execution clearance."""

from __future__ import annotations
import collections
import hashlib
import json
import mmap
from pathlib import Path
import re
import argparse
from typing import Any

from evals.acceptance_source_contract import resolve_source_contract, verify_source_contract_inventory

BOUNDARY = re.compile(rb"(?m)^<(DOCUMENT|/DOCUMENT|TEXT|/TEXT)>\r?$")
FIELD = re.compile(rb"(?m)^<(TYPE|SEQUENCE|FILENAME|DESCRIPTION)>([^\r\n]*)\r?$")
INLINE_XBRL = re.compile(
    rb"(?:https?://www\.xbrl\.org/(?:2008|2013)/inlineXBRL|<ix:(?:nonFraction|nonNumeric|fraction|hidden)\b)",
    re.IGNORECASE,
)
SPACE = b" \t\r\n\v\f"


def digest_span(data: mmap.mmap, start: int, end: int) -> str:
    h = hashlib.sha256()
    for pos in range(start, end, 1024 * 1024):
        h.update(data[pos : min(end, pos + 1024 * 1024)])
    return h.hexdigest()


def span(data: mmap.mmap, start: int, end: int, kind: str) -> dict[str, Any]:
    return {"kind": kind, "start": start, "end": end, "bytes": end - start, "sha256": digest_span(data, start, end)}


def review_route(metadata: dict[str, str]) -> str:
    name = metadata["filename"].lower()
    typ = metadata["type"].upper()
    if typ == "GRAPHIC" or name.endswith((".jpg", ".jpeg", ".png", ".gif", ".svg", ".pdf")):
        return "visual_or_binary_review_required"
    if typ == "ZIP" or name.endswith(".zip"):
        return "encoded_archive_inventory_required"
    if name.endswith((".xml", ".xsd", ".json")) or typ.startswith("EX-101"):
        return "structured_data_review_required"
    if typ == "XML" and re.fullmatch(r"r\d+\.htm[l]?", name):
        return "structured_rendering_review_required"
    if name.endswith((".htm", ".html", ".txt")):
        return "readable_document_review_required"
    return "unclassified_review_required"


def map_submission(path: Path, expected_sha: str, expected_bytes: int, contract: dict) -> dict:
    """Inventory one frozen submission; ranges use byte offsets and exclusive ends.

    Only the selected embedding contract may identify the primary/exhibit. Routing
    never excludes a document or attests that its contents have been reviewed.
    """
    if not expected_bytes:
        raise ValueError("empty complete submission")
    with path.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        size = len(data)
        if size != expected_bytes or digest_span(data, 0, size) != expected_sha:
            raise ValueError("source size/hash mismatch")
        tokens = list(BOUNDARY.finditer(data))
        if not tokens or len(tokens) % 4:
            raise ValueError("unbalanced SGML document/text boundaries")
        documents, envelope, cursor = [], [], 0
        filenames = set()
        for number in range(0, len(tokens), 4):
            a, b, c, d = tokens[number : number + 4]
            if [m.group(1) for m in (a, b, c, d)] != [b"DOCUMENT", b"TEXT", b"/TEXT", b"/DOCUMENT"]:
                raise ValueError("nested or ambiguous SGML boundaries")
            if a.start() < cursor:
                raise ValueError("overlapping document boundaries")
            envelope.append(span(data, cursor, a.start(), "submission_envelope"))
            fields = {}
            for key, value in FIELD.findall(data[a.end() : b.start()]):
                key = key.decode().lower()
                if key in fields:
                    raise ValueError("duplicate SGML header field")
                fields[key] = value.decode("utf-8", errors="strict")
            if not fields.get("filename") or not fields.get("type") or not fields.get("sequence"):
                raise ValueError("incomplete SGML document identity")
            if fields["filename"] in filenames:
                raise ValueError("duplicate SGML filename")
            filenames.add(fields["filename"])
            start = b.end()
            if data[start : start + 1] != b"\n":
                raise ValueError("TEXT start has no line break")
            start += 1
            end = c.start()
            trimmed_start, trimmed_end = start, end
            while trimmed_start < trimmed_end and data[trimmed_start] in SPACE:
                trimmed_start += 1
            while trimmed_end > trimmed_start and data[trimmed_end - 1] in SPACE:
                trimmed_end -= 1
            body = span(data, start, end, "document_payload")
            stripped = span(data, trimmed_start, trimmed_end, "whitespace_trimmed_payload")
            content_start, content_end = trimmed_start, trimmed_end
            wrapper = None
            for tag in (b"XBRL", b"XML"):
                opening = b"<" + tag + b">"
                closing = b"</" + tag + b">"
                if data[content_start : content_start + len(opening)] == opening:
                    if data[content_end - len(closing) : content_end] != closing:
                        raise ValueError("unbalanced SGML format envelope")
                    wrapper = tag.decode()
                    content_start += len(opening)
                    content_end -= len(closing)
                    while content_start < content_end and data[content_start] in SPACE:
                        content_start += 1
                    while content_end > content_start and data[content_end - 1] in SPACE:
                        content_end -= 1
                    break
            content = span(data, content_start, content_end, "document_content")
            route = review_route(fields)
            inline_xbrl = INLINE_XBRL.search(data, content_start, content_end) is not None
            requirements = [route]
            if inline_xbrl:
                requirements.append("inline_xbrl_structured_review_required")
            item = {
                "ordinal": len(documents) + 1,
                **fields,
                "route": route,
                "review_requirements": requirements,
                "inline_xbrl_markers_present": inline_xbrl,
                "document": span(data, a.start(), d.end(), "sgml_document"),
                "header": span(data, a.start(), start, "sgml_header"),
                "payload": body,
                "footer": span(data, end, d.end(), "sgml_footer"),
                "trimmed_payload": stripped,
                "content": content,
                "format_wrapper": wrapper,
                "content_prefix": span(data, start, content_start, "payload_prefix"),
                "content_suffix": span(data, content_end, end, "payload_suffix"),
                "selected_roles": [],
            }
            documents.append(item)
            cursor = d.end()
        envelope.append(span(data, cursor, size, "submission_envelope"))
        selected = {}
        for role, declared in contract["attachments"].items():
            matches = [v for v in documents if v["filename"] == declared["document"]]
            if len(matches) != 1:
                raise ValueError("selected attachment is absent or ambiguous")
            doc = matches[0]
            matches = [
                v
                for v in (doc["payload"], doc["trimmed_payload"], doc["content"])
                if v["sha256"] == declared["embedded_sha256"] and v["bytes"] == declared["embedded_bytes"]
            ]
            if not matches:
                raise ValueError("selected attachment differs from frozen embedding contract")
            doc["selected_roles"].append(role)
            selected[role] = {
                "document_ordinal": doc["ordinal"],
                "filename": doc["filename"],
                "source_span": matches[0],
                "direct_packet_sha256": declared["packet_sha256"],
                "relationship": declared["relationship"],
                "difference_classification": declared["difference_audit"]["classification"],
            }
        partition = sorted([*envelope, *[d["document"] for d in documents]], key=lambda r: r["start"])
        cursor = 0
        for piece in partition:
            if piece["start"] != cursor or piece["end"] < cursor:
                raise ValueError("source byte accounting gap or overlap")
            cursor = piece["end"]
        if cursor != size:
            raise ValueError("source byte accounting does not cover whole submission")
        duplicates = collections.defaultdict(list)
        for doc in documents:
            duplicates[doc["payload"]["sha256"]].append(doc["ordinal"])
        if digest_span(data, 0, size) != expected_sha:
            raise ValueError("source changed during document mapping")
        return {
            "source_sha256": expected_sha,
            "source_bytes": size,
            "every_source_byte_accounted": True,
            "semantic_coverage_attested": False,
            "documents": documents,
            "submission_envelope": envelope,
            "selected_attachments": selected,
            "exact_payload_duplicates": [v for v in duplicates.values() if len(v) > 1],
            "route_counts": dict(collections.Counter(d["route"] for d in documents)),
            "route_payload_bytes": dict(
                (k, sum(d["payload"]["bytes"] for d in documents if d["route"] == k))
                for k in sorted({d["route"] for d in documents})
            ),
        }


def _write_json(path: Path, value: object) -> dict:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with path.open("xb") as stream:
        stream.write(payload)
    return {"path": path.name, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def build_document_maps(selection: Path, source_root: Path, output: Path) -> dict:
    """Verify the entire approved archive, then write deterministic preparation maps.

    A partial directory has no index.json. An existing output is never overwritten.
    These files have no readiness/acceptance authority and require semantic review.
    """
    if output.exists() or output.is_symlink():
        raise ValueError("document map output must not already exist")
    resolved = resolve_source_contract(selection, source_root)
    root = Path(resolved.inventory["source_root"])
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for filing in sorted(resolved.effective_filings, key=lambda item: item["holdout_id"]):
        holdout = filing["holdout_id"]
        complete = next(p for p in filing["source_packets"] if p["role"] == "complete_submission")
        binding = resolved.bindings_by_holdout[holdout]
        embedding = json.loads((root / binding["embedding"]["path"]).read_text(encoding="utf-8"))
        mapped = map_submission(root / complete["path"], complete["sha256"], complete["bytes"], embedding)
        mapped.update(
            schema_version=1,
            kind="e7_submission_document_map",
            holdout_id=holdout,
            accession_number=filing["accession_number"],
            source_packet=complete,
            embedding_contract=binding["embedding"],
            source_binding=binding["contract"],
            source_packets=filing["source_packets"],
            limitations=[
                "Byte accounting does not establish semantic review coverage.",
                "Every document, envelope and format wrapper remains retained.",
                "Routing by declared type/filename does not prove irrelevance.",
                "Images, structured data, archives and unknown types need review.",
                "Only exact payload duplicates are grouped; none are removed.",
            ],
        )
        reference = _write_json(output / (holdout + ".json"), mapped)
        rows.append(
            {
                "holdout_id": holdout,
                "accession_number": filing["accession_number"],
                "document_count": len(mapped["documents"]),
                "document_map": reference,
                "source_bytes": complete["bytes"],
                "route_counts": mapped["route_counts"],
                "route_payload_bytes": mapped["route_payload_bytes"],
            }
        )
    # Recheck the full inventory before publishing a complete index, including direct
    # packets and contracts that a filesystem writer could have replaced mid-run.
    verify_source_contract_inventory(resolved.inventory)
    index = {
        "schema_version": 1,
        "kind": "e7_document_map_preparation",
        "semantic_coverage_attested": False,
        "byte_accounting_scope": "complete_submission packets only",
        "other_packet_scope": "hash-bound inventory; semantic and format review still required",
        "source_contract": resolved.inventory,
        "filings": rows,
    }
    _write_json(output / "index.json", index)
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_document_maps(args.selection, args.source_root, args.output)
    print(
        json.dumps(
            {
                "filings": len(result["filings"]),
                "documents": sum(row["document_count"] for row in result["filings"]),
                "semantic_coverage_attested": False,
                "index": str(args.output / "index.json"),
            }
        )
    )


if __name__ == "__main__":
    main()
