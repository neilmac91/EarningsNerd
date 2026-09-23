"""Adversarial offline checks for the explicitly inventoried E7 claim surfaces."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from pathlib import Path

from evals.acceptance_ai_checks import run_checks


ACCESSION = "0000018230-26-000008"
CIK = "18230"
URL = "https://www.sec.gov/Archives/edgar/data/18230/000001823026000008/filing.htm"
SOURCE = "Revenue 110.0 prior 100.0; cash 30.0 plus 20.0. Exact issuer sentence."
SURFACE = ("Growth 10.0%; cash total 50.0; delta 10.0; ratio 1.10. "
           "Exact issuer sentence. Citation: " + URL)


def _span(text: str, part: str, nth: int = 0) -> list[int]:
    start = -1
    for _ in range(nth + 1):
        start = text.index(part, start + 1)
    return [start, start + len(part)]


def _input(part: str, *, basis: str, unit: str = "USD million") -> dict:
    return {"source_role": "primary", "source_sha256": hashlib.sha256(SOURCE.encode()).hexdigest(),
            "source_accession_number": ACCESSION, "source_range": _span(SOURCE, part),
            "unit": unit, "basis": basis}


def _inventory() -> dict:
    source_hash = hashlib.sha256(SOURCE.encode()).hexdigest()
    surface_hash = hashlib.sha256(SURFACE.encode()).hexdigest()
    source_quote = _span(SOURCE, "Exact issuer sentence.")
    output_quote = _span(SURFACE, "Exact issuer sentence.")
    common = {"source_role": "primary", "source_sha256": source_hash,
              "source_accession_number": ACCESSION, "source_range": source_quote,
              "output_range": output_quote}
    return {"schema_version": 1, "selected": {"accession_number": ACCESSION, "cik": CIK},
            "sources": {"primary": {"sha256": source_hash, "accession_number": ACCESSION,
                                    "cik": CIK, "official_url": URL}},
            "surfaces": {"rendered": {"sha256": surface_hash, "claims": [
                {"id": "q1", "kind": "quote", **common},
                {"id": "c1", "kind": "citation", **common,
                 "target_range": _span(SURFACE, URL)},
                {"id": "n1", "kind": "numeric", "operation": "percent_change",
                 "inputs": [_input("110.0", basis="revenue"), _input("100.0", basis="revenue")],
                 "output_range": _span(SURFACE, "10.0"), "output_unit": "%",
                 "output_basis": "revenue"},
                {"id": "n2", "kind": "numeric", "operation": "sum",
                 "inputs": [_input("30.0", basis="cash"), _input("20.0", basis="cash")],
                 "output_range": _span(SURFACE, "50.0"), "output_unit": "USD million",
                 "output_basis": "cash"},
                {"id": "n3", "kind": "numeric", "operation": "difference",
                 "inputs": [_input("110.0", basis="revenue"), _input("100.0", basis="revenue")],
                 "output_range": _span(SURFACE, "10.0", 1), "output_unit": "USD million",
                 "output_basis": "revenue"},
                {"id": "n4", "kind": "numeric", "operation": "ratio",
                 "inputs": [_input("110.0", basis="revenue"), _input("100.0", basis="revenue")],
                 "output_range": _span(SURFACE, "1.10"), "output_unit": "ratio",
                 "output_basis": "revenue/revenue"},
            ]}}}


def _files(tmp_path: Path) -> tuple[dict[str, Path], dict[str, Path]]:
    source = tmp_path / "source.htm"
    rendered = tmp_path / "rendered.md"
    source.write_text(SOURCE, encoding="utf-8")
    rendered.write_text(SURFACE, encoding="utf-8")
    return {"rendered": rendered}, {"primary": source}


def test_exact_spans_and_all_four_decimal_operations_pass(tmp_path: Path) -> None:
    surfaces, sources = _files(tmp_path)
    report = run_checks(_inventory(), surfaces, sources)
    assert report["status"] == "pass"
    assert report["complete"] is True
    assert report["passed_claims"] == 6
    assert report["issues"] == report["failures"] == []
    arithmetic = next(row for row in report["results"] if row["id"] == "n1")
    assert arithmetic["proof"]["operands"] == ["110.0", "100.0"]
    assert arithmetic["proof"]["rounded"] == arithmetic["proof"]["displayed"] == "10.0"


def test_changed_output_bytes_cannot_reuse_original_claim_inventory(tmp_path: Path) -> None:
    surfaces, sources = _files(tmp_path)
    surfaces["rendered"].write_text(SURFACE.replace("Growth 10.0%", "Growth 11.0%"), encoding="utf-8")
    report = run_checks(_inventory(), surfaces, sources)
    assert report["status"] == "incomplete"
    assert {row["code"] for row in report["issues"]} == {"file_hash"}
    assert report["checked_claims"] == 0


def test_exact_quote_citation_and_arithmetic_mismatches_have_stable_ids(tmp_path: Path) -> None:
    surfaces, sources = _files(tmp_path)
    inventory = _inventory()
    claims = inventory["surfaces"]["rendered"]["claims"]
    claims[0]["source_range"] = _span(SOURCE, "Revenue")
    claims[1]["target_range"] = _span(SURFACE, "Citation:")
    claims[2]["output_range"] = _span(SURFACE, "50.0")
    report = run_checks(inventory, surfaces, sources)
    assert report["status"] == "fail"
    assert {(row["id"], row["code"]) for row in report["failures"]} == {
        ("q1", "quote_mismatch"), ("c1", "citation_target_mismatch"),
        ("n1", "arithmetic_mismatch"),
    }


def test_unbound_source_wrong_basis_and_unsupported_check_are_incomplete(tmp_path: Path) -> None:
    surfaces, sources = _files(tmp_path)
    inventory = _inventory()
    claims = inventory["surfaces"]["rendered"]["claims"]
    claims[0]["source_accession_number"] = "0000000000-26-000001"
    claims[3]["inputs"][1]["basis"] = "restricted cash"
    claims.append({"id": "semantic-claim", "kind": "causal_claim"})
    report = run_checks(inventory, surfaces, sources)
    assert report["status"] == "incomplete"
    assert {(row["id"], row["code"]) for row in report["issues"]} == {
        ("q1", "source_identity_or_span"), ("n2", "incompatible_operand_metadata"),
        ("semantic-claim", "unsupported_claim_kind"),
    }


def test_every_supplied_surface_and_source_needs_an_explicit_inventory(tmp_path: Path) -> None:
    surfaces, sources = _files(tmp_path)
    inventory = _inventory()
    surfaces["preview_0"] = tmp_path / "preview.md"
    surfaces["preview_0"].write_text("A preview", encoding="utf-8")
    report = run_checks(inventory, surfaces, sources)
    assert report["status"] == "incomplete"
    assert any(row["code"] == "inventory_paths" for row in report["issues"])
    inventory["surfaces"]["preview_0"] = {
        "sha256": hashlib.sha256(b"A preview").hexdigest(), "claims": []}
    report = run_checks(inventory, surfaces, sources)
    assert report["status"] == "pass"
    assert "Only explicitly inventoried" in report["coverage_limit"]


def test_duplicate_id_and_zero_denominator_cannot_pass(tmp_path: Path) -> None:
    surfaces, sources = _files(tmp_path)
    inventory = _inventory()
    claims = inventory["surfaces"]["rendered"]["claims"]
    duplicate = deepcopy(claims[0])
    claims.append(duplicate)
    claims[5]["inputs"][1]["source_range"] = _span(SOURCE, "0")
    report = run_checks(inventory, surfaces, sources)
    assert report["status"] == "incomplete"
    assert {row["code"] for row in report["issues"]} == {"duplicate_claim", "zero_denominator"}
