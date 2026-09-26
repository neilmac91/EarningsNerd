"""Exact, offline E7 surface checks over an explicit claim inventory.

This proves only the listed byte/character spans and arithmetic. It does not discover
claims or judge whether the inventory covers every material statement in a filing.
"""

from __future__ import annotations

import hashlib
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from pathlib import Path
from typing import Any


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_NUMBER = re.compile(r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\Z")
_ACCESSION = re.compile(r"\d{10}-\d{2}-\d{6}\Z")
_KIND_KEYS = {
    "quote": {"id", "kind", "source_role", "source_sha256", "source_accession_number",
              "source_range", "output_range"},
    "citation": {"id", "kind", "source_role", "source_sha256", "source_accession_number",
                 "source_range", "output_range", "target_range"},
    "numeric": {"id", "kind", "operation", "inputs", "output_range", "output_unit",
                "output_basis"},
}
_INPUT_KEYS = {"source_role", "source_sha256", "source_accession_number",
               "source_range", "unit", "basis"}


def _issue(items: list[dict[str, str]], check_id: str, code: str, detail: str) -> None:
    items.append({"id": check_id, "code": code, "detail": detail})


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _span(text: str, value: Any) -> str | None:
    """Return a nonempty Python-character (Unicode code-point) half-open span."""
    if (not isinstance(value, list) or len(value) != 2 or
            any(type(offset) is not int for offset in value)):
        return None
    start, end = value
    if start < 0 or end <= start or end > len(text):
        return None
    return text[start:end]


def _number(text: str) -> Decimal | None:
    if len(text) > 128 or not _NUMBER.fullmatch(text):
        return None
    try:
        number = Decimal(text.replace(",", ""))
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _load_files(specs: Any, paths: dict[str, Path], kind: str,
                issues: list[dict[str, str]]) -> tuple[dict[str, str], dict[str, str]]:
    contents: dict[str, str] = {}
    hashes: dict[str, str] = {}
    if not isinstance(specs, dict) or not specs or not isinstance(paths, dict):
        _issue(issues, kind, "inventory_shape", f"{kind} inventory and paths must be nonempty mappings")
        return contents, hashes
    if set(specs) != set(paths):
        _issue(issues, kind, "inventory_paths", f"{kind} inventory and supplied paths differ")
    for name in sorted(set(specs) & set(paths), key=str):
        spec = specs[name]
        if not _nonempty(name) or not isinstance(spec, dict) or not _SHA256.fullmatch(str(spec.get("sha256", ""))):
            _issue(issues, f"{kind}:{name}", "inventory_shape", "missing name or SHA256")
            continue
        try:
            raw = Path(paths[name]).read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            hashes[name] = digest
            if digest != spec["sha256"]:
                _issue(issues, f"{kind}:{name}", "file_hash", "retained bytes differ from inventory")
                continue
            contents[name] = raw.decode("utf-8", errors="strict")
        except (OSError, TypeError, ValueError, UnicodeError) as error:
            _issue(issues, f"{kind}:{name}", "file_unavailable", type(error).__name__)
    return contents, hashes


def _source_text(claim: dict[str, Any], sources: dict[str, Any], source_texts: dict[str, str],
                 accession: str) -> str | None:
    role = claim.get("source_role")
    if not isinstance(role, str) or role not in source_texts:
        return None
    spec = sources[role]
    if (claim.get("source_sha256") != spec.get("sha256") or
            claim.get("source_accession_number") != accession):
        return None
    return _span(source_texts[role], claim.get("source_range"))


def _check_quote(claim: dict[str, Any], output: str, sources: dict[str, Any],
                 source_texts: dict[str, str], accession: str) -> tuple[str, str, dict[str, Any]]:
    if set(claim) != _KIND_KEYS[claim["kind"]]:
        return "issue", "claim_shape", {}
    source_part = _source_text(claim, sources, source_texts, accession)
    output_part = _span(output, claim.get("output_range"))
    if source_part is None or output_part is None:
        return "issue", "source_identity_or_span", {}
    proof = {"source_text_sha256": hashlib.sha256(source_part.encode("utf-8")).hexdigest(),
             "output_text_sha256": hashlib.sha256(output_part.encode("utf-8")).hexdigest()}
    if source_part != output_part:
        return "failure", "quote_mismatch", proof
    if claim["kind"] == "citation":
        target = _span(output, claim.get("target_range"))
        expected_url = sources[claim["source_role"]].get("official_url")
        if target is None or not _nonempty(expected_url):
            return "issue", "citation_target_unavailable", proof
        proof["target_text_sha256"] = hashlib.sha256(target.encode("utf-8")).hexdigest()
        proof["official_url_sha256"] = hashlib.sha256(expected_url.encode("utf-8")).hexdigest()
        if target != expected_url:
            return "failure", "citation_target_mismatch", proof
    return "passed", "exact_span_match", proof


def _check_numeric(claim: dict[str, Any], output: str, sources: dict[str, Any],
                   source_texts: dict[str, str], accession: str) -> tuple[str, str, dict[str, Any]]:
    if (set(claim) != _KIND_KEYS["numeric"] or
            not _nonempty(claim.get("output_unit")) or not _nonempty(claim.get("output_basis"))):
        return "issue", "claim_shape", {}
    operation = claim.get("operation")
    inputs = claim.get("inputs")
    if (operation not in {"sum", "difference", "ratio", "percent_change"} or
            not isinstance(inputs, list) or
            len(inputs) < 2 or (operation != "sum" and len(inputs) != 2)):
        return "issue", "unsupported_operation", {}
    values: list[Decimal] = []
    units: list[str] = []
    bases: list[str] = []
    for item in inputs:
        if (not isinstance(item, dict) or set(item) != _INPUT_KEYS or
                not _nonempty(item.get("unit")) or not _nonempty(item.get("basis"))):
            return "issue", "input_shape", {}
        source_part = _source_text(item, sources, source_texts, accession)
        value = _number(source_part) if source_part is not None else None
        if value is None:
            return "issue", "source_identity_span_or_number", {}
        values.append(value)
        units.append(item["unit"])
        bases.append(item["basis"])
    displayed = _span(output, claim.get("output_range"))
    actual = _number(displayed) if displayed is not None else None
    if actual is None:
        return "issue", "output_span_or_number", {}
    if operation in {"sum", "difference", "percent_change"}:
        if len(set(units)) != 1 or len(set(bases)) != 1:
            return "issue", "incompatible_operand_metadata", {}
        expected_unit = "%" if operation == "percent_change" else units[0]
        expected_basis = bases[0]
    else:
        expected_unit = "ratio" if units[0] == units[1] else f"{units[0]}/{units[1]}"
        expected_basis = f"{bases[0]}/{bases[1]}"
    if claim["output_unit"] != expected_unit or claim["output_basis"] != expected_basis:
        return "issue", "output_metadata_mismatch", {}
    if operation in {"ratio", "percent_change"} and values[1] == 0:
        return "issue", "zero_denominator", {}
    places = len(displayed.partition(".")[2]) if "." in displayed else 0
    try:
        with localcontext() as context:
            context.prec = max(50, sum(len(value.as_tuple().digits) for value in values) + places + 20)
            if operation == "sum":
                expected = sum(values, Decimal(0))
            elif operation == "difference":
                expected = values[0] - values[1]
            elif operation == "ratio":
                expected = values[0] / values[1]
            else:
                expected = (values[0] - values[1]) / values[1] * Decimal(100)
            rounded = expected.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return "issue", "unsupported_precision", {}
    proof = {"operands": [str(value) for value in values], "computed": str(expected),
             "rounded": str(rounded), "displayed": str(actual), "decimal_places": places,
             "unit": expected_unit, "basis": expected_basis, "rounding": "ROUND_HALF_UP"}
    return (("passed", "arithmetic_match", proof) if actual == rounded else
            ("failure", "arithmetic_mismatch", proof))


def run_checks(inventory: dict[str, Any], surfaces: dict[str, Path],
               sources: dict[str, Path]) -> dict[str, Any]:
    """Check listed spans from exact retained files; never infer omitted claims.

    ``complete`` is true only when all declared checks pass. A mismatch is a
    machine failure; an absent/unsupported input is an incomplete issue.
    """
    issues: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    results: list[dict[str, Any]] = []
    hashes: dict[str, dict[str, str]] = {"surfaces": {}, "sources": {}}
    if not isinstance(inventory, dict) or inventory.get("schema_version") != 1:
        _issue(issues, "inventory", "schema_version", "expected checks inventory v1")
        inventory = {}
    selected = inventory.get("selected")
    if (not isinstance(selected, dict) or set(selected) != {"accession_number", "cik"} or
            not _ACCESSION.fullmatch(str(selected.get("accession_number", ""))) or
            not _nonempty(selected.get("cik"))):
        _issue(issues, "selected", "source_identity", "selected accession and CIK required")
        selected = {"accession_number": "", "cik": ""}
    source_specs = inventory.get("sources")
    surface_specs = inventory.get("surfaces")
    source_texts, hashes["sources"] = _load_files(source_specs, sources, "sources", issues)
    surface_texts, hashes["surfaces"] = _load_files(surface_specs, surfaces, "surfaces", issues)
    if isinstance(source_specs, dict):
        for role, spec in sorted(source_specs.items(), key=lambda item: str(item[0])):
            if (not isinstance(spec, dict) or
                    set(spec) != {"sha256", "accession_number", "cik", "official_url"} or
                    spec.get("accession_number") != selected["accession_number"] or
                    spec.get("cik") != selected["cik"] or
                    not _nonempty(spec.get("official_url"))):
                _issue(issues, f"sources:{role}", "source_identity", "source differs from selected identity")
    seen_ids: set[str] = set()
    if isinstance(surface_specs, dict):
        for name, spec in sorted(surface_specs.items(), key=lambda item: str(item[0])):
            if not isinstance(spec, dict) or set(spec) != {"sha256", "claims"} or not isinstance(spec.get("claims"), list):
                _issue(issues, f"surfaces:{name}", "surface_inventory", "explicit claim list required")
                continue
            if name not in surface_texts:
                continue
            for ordinal, claim in enumerate(spec["claims"]):
                fallback_id = f"{name}#{ordinal}"
                if not isinstance(claim, dict) or not _nonempty(claim.get("id")):
                    _issue(issues, fallback_id, "claim_id", "stable nonempty claim ID required")
                    continue
                check_id = claim["id"]
                if check_id in seen_ids:
                    _issue(issues, check_id, "duplicate_claim", "claim ID reused")
                    continue
                seen_ids.add(check_id)
                kind = claim.get("kind")
                if kind in {"quote", "citation"}:
                    status, code, proof = _check_quote(claim, surface_texts[name], source_specs,
                                                       source_texts, selected["accession_number"])
                elif kind == "numeric":
                    status, code, proof = _check_numeric(claim, surface_texts[name], source_specs,
                                                         source_texts, selected["accession_number"])
                else:
                    status, code, proof = "issue", "unsupported_claim_kind", {}
                results.append({"id": check_id, "surface": name, "kind": str(kind),
                                "status": status, "code": code, "proof": proof})
                if status == "issue":
                    _issue(issues, check_id, code, f"{name}: check could not be completed")
                elif status == "failure":
                    _issue(failures, check_id, code, f"{name}: exact check failed")
    status = "fail" if failures else "incomplete" if issues else "pass"
    return {"schema_version": 1, "status": status, "complete": status == "pass",
            "selected": selected, "file_sha256": hashes, "checked_claims": len(results),
            "passed_claims": sum(row["status"] == "passed" for row in results),
            "results": results, "failures": failures, "issues": issues,
            "coverage_limit": "Only explicitly inventoried spans are checked; empty claim lists do not prove natural-language coverage."}
