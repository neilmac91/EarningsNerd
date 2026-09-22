"""Offline E7 AI-assisted decision arithmetic over retained review evidence.

This module never calls a model. Its checks establish completeness and consistency of
retained assessments, not that a model's source interpretation is correct. The CLI also
verifies durable generation/packet evidence and retains every readiness hold. It cannot
grant human acceptance, production activation or permission to spend.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any

from evals.acceptance_readiness import (
    APPROVED_MANIFEST_SHA256, COMPARATOR_HOLDOUT_IDS, _evidence, _json, _safe_file, _sha256, _reviewer_artifact,
    inspect_readiness, verify_review_evidence_binding,
)


def expected_identities(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    filings = manifest.get("filings", [])
    if (len(filings) != 30 or {f["holdout_id"] for f in filings} !=
            {f"H{i:02d}" for i in range(1, 31)} or
            len({f["accession_number"] for f in filings}) != 30):
        raise ValueError("decision requires the complete 30-filing manifest")
    return {f"{f['holdout_id']}-{arm}-{draw}": {**f, "arm": arm, "draw": draw}
            for f in filings for arm in ("candidate", "comparator")
            if arm == "candidate" or f["holdout_id"] in COMPARATOR_HOLDOUT_IDS
            for draw in (1, 2, 3)}


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _score(value: Any) -> bool:
    return type(value) is int and 1 <= value <= 5


def decide(manifest: dict[str, Any], assessments: list[dict[str, Any]], *,
           measurement_issues: list[str] | None = None) -> dict[str, Any]:
    """Compute the fixed rubric; callers must validate provenance before using results.

    Each assessment covers one immutable output and every retained visible surface.
    ``checks`` are declared review outcomes, not automatically established facts.
    Missing, malformed or duplicate evidence cannot yield a favorable result.
    """
    expected = expected_identities(manifest)
    incomplete = list(measurement_issues or [])
    failures: list[str] = []
    indexed: dict[str, dict[str, Any]] = {}
    defects: list[dict[str, Any]] = []
    finding_ids: set[str] = set()
    for row in assessments:
        if not isinstance(row, dict):
            incomplete.append("assessment is not an object")
            continue
        slot = row.get("slot_id")
        if not isinstance(slot, str) or slot not in expected or slot in indexed:
            incomplete.append(f"unexpected or duplicate assessment: {slot}")
            continue
        indexed[slot] = row
        valid = True
        for dimension in ("completeness", "usefulness"):
            if not _score(row.get(dimension)) or not _nonempty(row.get(f"{dimension}_reason")):
                incomplete.append(f"{slot}: missing/invalid {dimension} assessment")
                valid = False
        semantic = row.get("semantic", {})
        if (not isinstance(semantic, dict) or semantic.get("model") != "cli:claude-fable-5-1" or
                str(semantic.get("contract_version")) != "2" or
                semantic.get("status") != "complete" or
                semantic.get("grounding_truncated") is not False or
                semantic.get("verdict") not in {"pass", "fail"}):
            incomplete.append(f"{slot}: missing, incompatible or truncated Fable verdict")
        findings = row.get("findings")
        if not isinstance(findings, list):
            incomplete.append(f"{slot}: missing finding register")
            findings = []
        if isinstance(semantic, dict) and semantic.get("verdict") == "fail" and not findings:
            incomplete.append(f"{slot}: negative Fable verdict lacks source adjudication")
        checks = row.get("checks", {})
        required = {"numeric_claims", "causal_claims", "financial_basis", "quotations", "citations"}
        if (not isinstance(checks, dict) or set(checks) != required or
                any(v not in ("checked", "defect", "unresolved") for v in checks.values())):
            incomplete.append(f"{slot}: incomplete claim-check coverage")
        elif "unresolved" in checks.values():
            incomplete.append(f"{slot}: unresolved source checks")
        elif "defect" in checks.values() and not findings:
            incomplete.append(f"{slot}: source check defects absent from register")
        for finding in findings:
            if (not isinstance(finding, dict) or
                    not all(_nonempty(finding.get(k)) for k in
                            ("id", "claim", "source_locator", "source_context", "reason")) or
                    finding.get("severity") not in {"S0", "S1", "S2", "S3"} or
                    finding.get("disposition") not in {"confirmed", "rejected", "unresolved"} or
                    finding.get("category") not in {"claim", "omission", "fabricated_quote", "misleading_citation"} or
                    not isinstance(finding.get("refutations"), list) or
                    len(finding["refutations"]) != 2 or
                    not all(_nonempty(v) for v in finding["refutations"])):
                incomplete.append(f"{slot}: incomplete source challenge")
                continue
            if finding["id"] in finding_ids:
                incomplete.append(f"{slot}: duplicate finding ID {finding['id']}")
            finding_ids.add(finding["id"])
            defects.append({"slot_id": slot, **finding})
            # Comparator defects remain visible but do not fail the candidate's absolute bar.
            candidate = expected[slot]["arm"] == "candidate"
            veto = (finding["severity"] in {"S0", "S1"} or
                    finding["category"] in {"fabricated_quote", "misleading_citation"})
            if finding["disposition"] == "unresolved":
                incomplete.append(f"{slot}: unresolved finding {finding['id']}")
            elif finding["disposition"] == "confirmed" and candidate and veto:
                failures.append(f"{slot}: confirmed {finding['severity']} {finding['category']}")
            if (finding["disposition"] == "confirmed" and finding["severity"] == "S2" and
                    valid and row["completeness"] >= 4 and row["usefulness"] >= 4):
                incomplete.append(f"{slot}: S2 finding conflicts with both quality scores >=4")
    missing = sorted(set(expected) - set(indexed))
    incomplete.extend(f"missing assessment: {slot}" for slot in missing)
    candidates = {s: r for s, r in indexed.items() if expected[s]["arm"] == "candidate" and
                  _score(r.get("completeness")) and _score(r.get("usefulness"))}
    joint = sum(r["completeness"] >= 4 and r["usefulness"] >= 4 for r in candidates.values())
    # A known failure remains a failure even when the rest of the exercise is incomplete.
    if len(candidates) - joint > 4:
        failures.append("more than four candidate outputs below the joint 4/5 target")
    triples = []
    for f in manifest["filings"]:
        rows = [candidates.get(f"{f['holdout_id']}-candidate-{d}") for d in (1, 2, 3)]
        deficient = sum(r is not None and (r["completeness"] < 4 or r["usefulness"] < 4) for r in rows)
        if deficient >= 2:
            failures.append(f"{f['holdout_id']}: at least two deficient draws")
        triples.append({"holdout_id": f["holdout_id"], "accession_number": f["accession_number"],
                        "filing_type": f["filing_type"], "scores": [
                            {k: r[k] for k in ("completeness", "usefulness")} if r else None for r in rows]})
    comparisons = {"better": 0, "tied": 0, "worse": 0, "mixed": 0, "missing": 0}
    for slot, identity in expected.items():
        if identity["arm"] != "comparator":
            continue
        control, candidate = indexed.get(slot), candidates.get(slot.replace("-comparator-", "-candidate-"))
        if candidate is None or control is None or not all(_score(control.get(k)) for k in ("completeness", "usefulness")):
            comparisons["missing"] += 1
            continue
        delta = [candidate[k] - control[k] for k in ("completeness", "usefulness")]
        relation = ("tied" if delta == [0, 0] else "better" if min(delta) >= 0
                    else "worse" if max(delta) <= 0 else "mixed")
        comparisons[relation] += 1
    status = "fail" if failures else "incomplete" if incomplete else "pass"
    strata: dict[str, dict[str, Any]] = {}
    for field in ("filing_type", "sector"):
        strata[field] = {}
        for label in sorted({str(f.get(field, "unspecified")) for f in manifest["filings"]}):
            group = [f for f in manifest["filings"] if str(f.get(field, "unspecified")) == label]
            scores = [candidates[f"{f['holdout_id']}-candidate-{d}"] for f in group for d in (1, 2, 3)
                      if f"{f['holdout_id']}-candidate-{d}" in candidates]
            strata[field][label] = {"filings": len(group), "expected_outputs": len(group) * 3,
                                    "scored_outputs": len(scores), "joint_at_least_4":
                                    sum(r["completeness"] >= 4 and r["usefulness"] >= 4 for r in scores)}
    return {"schema_version": 1, "review_protocol": "ai_assisted", "status": status,
            "human_acceptance": False, "production_activation_authorized": False,
            "recommendation": ("limited_beta_product_risk_decision" if status == "pass" else "hold"),
            "expected_candidate_outputs": 90, "expected_comparator_outputs": 30,
            "candidate_scores_present": len(candidates), "joint_at_least_4": joint,
            "completeness_at_least_4": sum(r["completeness"] >= 4 for r in candidates.values()),
            "usefulness_at_least_4": sum(r["usefulness"] >= 4 for r in candidates.values()),
            "filing_triples": triples, "strata": strata, "paired_comparison": comparisons,
            "failures": failures, "incomplete_reasons": incomplete, "defects": defects,
            "limitations": ["AI assessments are retained claims, not independent expert human validation.",
                            "Thirty selected filings are the independent sampling units; repeated draws are not independent filings."]}


def build_decision(manifest_path: Path, archive: Path, prerequisites_path: Path,
                   outputs_path: Path, mapping_path: Path, evidence_path: Path,
                   packets_path: Path, *,
                   expected_manifest_sha: str = APPROVED_MANIFEST_SHA256) -> dict[str, Any]:
    """Verify source, collector, packet and review receipts before reducing the rubric."""
    from evals.acceptance_outputs import inspect_outputs
    from evals.acceptance_ai_judge_evidence import validate_judge_ledger
    from evals.acceptance_ai_checks import run_checks

    readiness = inspect_readiness(manifest_path, archive, prerequisites_path,
                                  expected_manifest_sha=expected_manifest_sha)
    prereq, manifest, mapping, evidence = map(_json, (prerequisites_path, manifest_path, mapping_path, evidence_path))
    if readiness.get("source_contract") is not None:
        from evals.acceptance_source_contract import verify_source_contract_inventory

        source_contract = verify_source_contract_inventory(readiness["source_contract"])
        manifest = {**manifest, "filings": list(source_contract.effective_filings)}
    if prereq.get("schema_version") != 2 or prereq.get("review_protocol") != "ai_assisted":
        raise ValueError("decision requires explicit AI-assisted prerequisites")
    outputs = _json(outputs_path)
    ledger = _safe_file(outputs_path.parent, outputs["programme_ledger_path"])
    verify_review_evidence_binding(ledger.parent, prerequisites_path)
    actual = inspect_outputs(ledger.parent, outputs_path.parent, expected_manifest_sha=expected_manifest_sha)
    if actual != outputs:
        raise ValueError("outputs index differs from durable collector evidence")
    if (mapping.get("manifest_sha256") != _sha256(manifest_path) or
            mapping.get("collector_index", {}).get("sha256") != _sha256(outputs_path) or
            mapping.get("programme_ledger", {}).get("sha256") != _sha256(ledger)):
        raise ValueError("packet mapping differs from durable programme evidence")
    if (evidence.get("schema_version") != 1 or evidence.get("review_protocol") != "ai_assisted" or
            evidence.get("mapping_sha256") != _sha256(mapping_path) or
            evidence.get("protocol_sha256") != prereq["ai_assisted"]["protocol"]["sha256"]):
        raise ValueError("assessment inventory is not bound to AI protocol and packet mapping")
    _, protocol = _evidence(prerequisites_path.parent, prereq["ai_assisted"]["protocol"])
    roles = {r["role"]: r for r in protocol["roles"]}
    identities = expected_identities(manifest)
    slots = {(v["accession_number"], v["arm"], v["draw"]): k for k, v in identities.items()}
    retained = {r["slot_id"]: r for r in actual["records"]}
    filing_by_accession = {f["accession_number"]: f for f in manifest["filings"]}
    if mapping.get("schema_version") != 2 or mapping.get("review_protocol") != "ai_assisted":
        raise ValueError("mapping is not an AI-assisted packet set")
    packet_sets = mapping["packet_sets"]
    if set(packet_sets) != {"ai-packet-1", "ai-packet-2"}:
        raise ValueError("both independent packet sets are required")
    surface_paths: dict[str, dict[str, Path]] = {}
    for set_name, packets in packet_sets.items():
        packet_base = packets_path / set_name
        packet_index = _json(_safe_file(packet_base, "index.json"))["packets"]
        if len(packet_index) != 120 or len({p["packet_id"] for p in packet_index}) != 120:
            raise ValueError("packet directory index is incomplete or duplicated")
        index_by_id = {p["packet_id"]: p for p in packet_index}
        seen: set[str] = set()
        for packet in packets:
            slot = slots[(packet["accession_number"], packet["arm"], packet["draw"])]
            raw = retained.get(slot)
            if slot in seen or raw is None or packet["collector_evidence"] != raw["collector_evidence"]:
                raise ValueError("packet mapping differs from retained slot inventory")
            seen.add(slot)
            item = index_by_id[packet["packet_id"]]
            case_prefix = f"sources/{item['source_case_id']}/"
            packet_prefix = f"packets/{packet['packet_id']}/"
            if (item["packet_dir"] != packet_prefix.rstrip("/") or
                    item["source_identity"] != case_prefix + "identity.json"):
                raise ValueError("reviewer index points to a different packet or source case")
            # A coherent edited mapping cannot silently remove a preview or swap a draw.
            if (set(packet["raw_artifacts"]) != set(raw["artifact_sha256"]) or
                    {k: v["sha256"] for k, v in packet["raw_artifacts"].items()} != raw["artifact_sha256"] or
                    set(packet["reviewer_artifacts"]) != set(raw["artifact_sha256"])):
                raise ValueError("packet surface inventory differs from retained output")
            filing = filing_by_accession[packet["accession_number"]]
            _, config = _evidence(prerequisites_path.parent, prereq[f"{packet['arm']}_config"])
            surfaces = {}
            for key, projection in packet["reviewer_artifacts"].items():
                if not projection["path"].startswith(packet_prefix):
                    raise ValueError("reviewer artifact is outside its indexed packet")
                projected, _ = _evidence(packet_base, projection)
                original = _safe_file(outputs_path.parent, (raw[f"{key}_path"] if key in
                    {"canonical", "rendered", "export"} else raw["preview_paths"][int(key.split("_")[1])]))
                if projected.read_bytes() != _reviewer_artifact(original, key, raw, config, filing["holdout_id"]):
                    raise ValueError("reviewer projection differs from durable output")
                surfaces[key] = projected
            surface_paths[packet["packet_id"]] = surfaces
            identity_path = _safe_file(packet_base, item["source_identity"])
            identity = _json(identity_path)
            if (item["accession_number"] != filing["accession_number"] or
                    identity["accession_number"] != filing["accession_number"] or
                    identity["ticker"] != filing["ticker"] or identity["filing_type"] != filing["filing_type"]):
                raise ValueError("reviewer source identity differs")
            copied = identity["sources"]
            if len(copied) != len(filing["source_packets"]):
                raise ValueError("reviewer source copy inventory is incomplete")
            copied_roles = {p["role"]: p for p in copied}
            if len(copied_roles) != len(copied):
                raise ValueError("reviewer source copy has duplicate roles")
            for source in filing["source_packets"]:
                copy = copied_roles[source["role"]]
                if (not copy["path"].startswith(case_prefix) or
                        _sha256(_safe_file(packet_base, copy["path"])) != source["sha256"] or
                        copy["official_url"] != source["provenance"]["final_url"]):
                    raise ValueError("reviewer source copy differs from frozen source")
            brief = _json(_safe_file(identity_path.parent, "reference-brief.json"))
            _, reference = _evidence(prerequisites_path.parent, next(r for r in
                prereq["ai_assisted"]["reconciled_references"] if r["accession_number"] == filing["accession_number"]))
            if (brief["accession_number"] != filing["accession_number"] or
                    brief["material_issues"] != reference["material_issues"]):
                raise ValueError("reviewer reference copy differs from sealed reference")
        if seen != set(identities) or len({r["packet_id"] for r in packets}) != len(identities):
            raise ValueError("packet set is incomplete or has duplicate identities")
    packet_rows = {r["packet_id"]: r for r in packet_sets["ai-packet-1"]}
    challenge_rows = {(r["accession_number"], r["arm"], r["draw"]): r
                      for r in packet_sets["ai-packet-2"]}
    judge_inputs = {slot: _judge_input_sha(
        _json(_safe_file(outputs_path.parent, raw["canonical_path"])),
        _json(_safe_file(outputs_path.parent, raw["collector_evidence"]["grounding"]["path"])))
        for slot, raw in retained.items()}
    judge_inputs["development-smoke"] = _smoke_judge_input(ledger.parent)
    judging = validate_judge_ledger(evidence_path.parent, evidence.get("judge_ledger"), judge_inputs)
    assessments = []
    machine_reports = {}
    machine_issues: list[str] = []
    for record in evidence.get("assessments", []):
        _, row = _evidence(evidence_path.parent, record)
        if row is None or row.get("packet_id") not in packet_rows:
            raise ValueError("assessment lacks a known blinded packet identity")
        packet = packet_rows[row["packet_id"]]
        slot = slots[(packet["accession_number"], packet["arm"], packet["draw"])]
        raw = retained.get(slot)
        if raw is None:
            raise ValueError("assessment refers to an incomplete output")
        if (row.get("review_protocol") != "ai_assisted" or row.get("schema_version") != 1 or
                row.get("quality_context_id") != roles["blind_quality"]["context_id"] or
                row.get("challenge_context_id") != roles["source_challenge"]["context_id"] or
                row.get("reviewer_artifacts") != packet["reviewer_artifacts"] or
                row.get("surfaces_checked") != sorted(packet["reviewer_artifacts"]) or
                row.get("grounding_sha256") != raw["collector_evidence"]["grounding"]["sha256"] or
                row.get("reference_sha256") != next(r["sha256"] for r in
                    prereq["ai_assisted"]["reconciled_references"] if r["accession_number"] == packet["accession_number"])):
            raise ValueError("assessment contexts, surfaces or source grounding differ")
        challenge = challenge_rows[(packet["accession_number"], packet["arm"], packet["draw"])]
        _validate_responses(evidence_path.parent, row, packet, challenge, roles)
        _, semantic = _evidence(evidence_path.parent, row["semantic_response"])
        judged = judging["verdicts"].get(slot)
        if judged is None or judged["raw"] != semantic["raw"]:
            machine_issues.append(f"{slot}: semantic result absent from retained CLI ledger")
        _, inventory = _evidence(evidence_path.parent, row.get("machine_inventory"))
        _, quality = _evidence(evidence_path.parent, row["quality_response"])
        _, source_review = _evidence(evidence_path.parent, row["challenge_response"])
        if (quality.get("machine_inventory_sha256") != row["machine_inventory"]["sha256"] or
                source_review.get("machine_inventory_sha256") != row["machine_inventory"]["sha256"] or
                quality.get("claim_inventory_coverage") != "all_detected_claims_inventoried" or
                source_review.get("claim_inventory_coverage") != "all_detected_claims_inventoried"):
            raise ValueError("claim inventory was not independently reviewed by both contexts")
        filing = filing_by_accession[packet["accession_number"]]
        _verify_challenge_sources(row["findings"], filing, archive)
        if inventory.get("selected") != {k: str(filing[k]) for k in ("accession_number", "cik")}:
            raise ValueError("machine inventory refers to a different filing")
        for source in filing["source_packets"]:
            declared = inventory["sources"][source["role"]]
            if (declared["sha256"] != source["sha256"] or
                    declared["official_url"] != source["provenance"]["final_url"]):
                raise ValueError("machine inventory source differs from frozen filing")
        checks = run_checks(inventory, surface_paths[row["packet_id"]],
                            {p["role"]: _safe_file(archive, p["path"]) for p in filing["source_packets"]})
        machine_reports[slot] = checks
        machine_issues.extend(f"{slot}: machine check {i['id']}:{i['code']}" for i in checks["issues"])
        for failure in (r for r in checks["results"] if r["status"] == "failure"):
            matches = [f for f in row["findings"] if isinstance(f, dict) and
                       f.get("machine_check_id") == failure["id"]]
            allegation = f"machine:{failure['id']}:{failure['code']}"
            if (len(matches) != 1 or matches[0].get("surface") != failure["surface"] or
                    matches[0].get("original_allegation") != allegation):
                machine_issues.append(f"{slot}: deterministic failure {failure['id']} lacks its own source challenge")
        assessments.append({**row, "slot_id": slot})
    issues = ([] if readiness["ready_for_packets"] else
              [f"readiness:{i['code']}" for i in readiness["issues"]])
    if not actual["complete"]:
        issues.append("generation collector is incomplete")
    issues.extend(machine_issues)
    issues.extend(f"judging:{reason}" for reason in judging["issues"])
    spend = _spend_snapshot(ledger)
    if spend["pending_requests"] or spend["stop_reason"] or Decimal(spend["reserved_usd"]) > 10:
        issues.append("generator accounting pending, stopped or above the USD 10 ceiling")
    report = decide(manifest, assessments, measurement_issues=issues)
    report["limitations"].extend(readiness.get("evidence_limitations", []))
    report["exposure_status"] = readiness.get("exposure_status", "not_verified")
    report["evidence_sha256"] = {"manifest": _sha256(manifest_path), "mapping": _sha256(mapping_path),
                                 "outputs": _sha256(outputs_path), "assessments": _sha256(evidence_path)}
    report["machine_checks"] = machine_reports
    report["judge_invocations"] = judging.get("invocations")
    report["generator_spend"] = spend
    report["limitations"].append("Claim discovery, financial basis and source interpretation remain AI-reviewed; exact checks cover inventoried claims only.")
    return report


def _verify_challenge_sources(findings: list[dict[str, Any]], filing: dict[str, Any], archive: Path) -> None:
    """A rejected allegation needs a real passage from this selected filing too."""
    sources = {p["role"]: p for p in filing["source_packets"]}
    texts: dict[str, str] = {}
    for finding in findings:
        role, span = finding.get("source_role"), finding.get("source_range")
        if (not isinstance(role, str) or role not in sources or
                finding.get("source_sha256") != sources[role]["sha256"] or
                not isinstance(span, list) or len(span) != 2 or
                any(type(offset) is not int for offset in span)):
            raise ValueError("source challenge is not bound to the selected filing")
        if role not in texts:
            texts[role] = _safe_file(archive, sources[role]["path"]).read_text(encoding="utf-8")
        start, end = span
        if (start < 0 or end <= start or end > len(texts[role]) or
                finding.get("source_context") != texts[role][start:end]):
            raise ValueError("source challenge passage differs from the frozen source")


def _judge_input_sha(canonical: dict[str, Any], grounding: dict[str, Any]) -> str:
    """Reconstruct the existing frozen judge messages without truncation or a model call."""
    from evals.judge import build_judge_messages
    from evals.runner import _baseline_to_canonical, _model_metrics

    calls = grounding["summarizer_calls"]
    if len(calls) != 1 or len(calls[0]["args"]) != 3:
        raise ValueError("exact single production summarizer context unavailable")
    args, kwargs = calls[0]["args"], calls[0]["kwargs"]
    excerpt = kwargs.get("filing_excerpt")
    if not isinstance(excerpt, str) or not excerpt:
        raise ValueError("generator excerpt unavailable; do not infer or truncate judge grounding")
    statement = kwargs.get("statement_source")
    if statement:
        excerpt += ("\n\n[APPLICATION-OWNED PRIMARY-STATEMENT EVIDENCE; "
                    "independent of the generator excerpt]\n" +
                    json.dumps(statement, ensure_ascii=False, sort_keys=True) +
                    "\n[END APPLICATION-OWNED PRIMARY-STATEMENT EVIDENCE]")
    metrics = kwargs.get("xbrl_metrics")
    xbrl = json.dumps(_model_metrics(metrics), default=str) if metrics else ""
    _, user = build_judge_messages(_baseline_to_canonical(canonical), args[1], args[2], excerpt, xbrl)
    return hashlib.sha256(user.encode("utf-8")).hexdigest()


def _smoke_judge_input(programme: Path) -> str:
    with sqlite3.connect((programme / "budget.sqlite3").as_uri() + "?mode=ro", uri=True) as db:
        row = db.execute("SELECT status,result_sha FROM slots WHERE id='development-smoke'").fetchone()
    result_path = _safe_file(programme, "development-smoke/attempt-1/result.json")
    if row is None or row[0] != "completed" or row[1] != _sha256(result_path):
        raise ValueError("development smoke completion seal unavailable")
    receipt = _json(result_path)
    for key, relative in receipt["artifacts"].items():
        if _sha256(_safe_file(result_path.parent, relative)) != receipt["artifact_sha256"][key]:
            raise ValueError("development smoke artifact differs from completion seal")
    return _judge_input_sha(_json(_safe_file(result_path.parent, receipt["artifacts"]["canonical_summary"])),
                            _json(_safe_file(result_path.parent, receipt["artifacts"]["grounding"])))


def _spend_snapshot(ledger: Path) -> dict[str, Any]:
    # Read-only access: constructing BudgetLedger would initialize mutable accounting state.
    with sqlite3.connect(ledger.as_uri() + "?mode=ro", uri=True) as db:
        rows = db.execute("SELECT reserved_usd,known_usage_upper_usd,status FROM reservations").fetchall()
        programme = db.execute("SELECT stop_reason FROM programme WHERE id=1").fetchone()
    if programme is None:
        raise ValueError("permanent generator accounting state unavailable")
    return {"cap_usd": "10", "requests": len(rows),
            "reserved_usd": str(sum((Decimal(r[0]) for r in rows), Decimal(0))),
            "known_usage_upper_usd": str(sum((Decimal(r[1]) for r in rows if r[1] is not None), Decimal(0))),
            "unknown_usage_requests": sum(r[1] is None for r in rows),
            "pending_requests": sum(r[2] == "pending" for r in rows),
            "stop_reason": programme[0],
            "provider_invoice_total_usd": None}


def _validate_responses(base: Path, row: dict[str, Any], packet: dict[str, Any],
                        challenge: dict[str, Any], roles: dict[str, Any]) -> None:
    """Check normalized scores against retained model response contents, including dissent."""
    from evals.judge import parse_judge_response

    _, quality = _evidence(base, row.get("quality_response"))
    _, semantic = _evidence(base, row.get("semantic_response"))
    _, source = _evidence(base, row.get("challenge_response"))
    for response, role, binding in ((quality, "blind_quality", packet),
                                    (source, "source_challenge", challenge)):
        if (response is None or response.get("schema_version") != 1 or
                response.get("review_protocol") != "ai_assisted" or
                response.get("role_identity") != roles[role] or
                response.get("packet_id") != binding["packet_id"] or
                response.get("reviewer_artifacts") != binding["reviewer_artifacts"] or
                response.get("reference_sha256") != row.get("reference_sha256") or
                response.get("grounding_sha256") != row.get("grounding_sha256")):
            raise ValueError("raw review response identity or input binding differs")
    for key in ("completeness", "usefulness", "completeness_reason", "usefulness_reason"):
        if row.get(key) != quality.get(key):
            raise ValueError("normalized score differs from retained quality response")
    if source.get("checks") != row.get("checks") or source.get("findings") != row.get("findings"):
        raise ValueError("normalized source checks differ from retained challenge response")
    if (semantic is None or semantic.get("schema_version") != 1 or
            semantic.get("packet_id") != packet["packet_id"] or
            semantic.get("grounding_sha256") != row.get("grounding_sha256") or
            semantic.get("reviewer_artifacts") != packet["reviewer_artifacts"] or
            semantic.get("model") != "cli:claude-fable-5-1" or
            str(semantic.get("contract_version")) != "2" or
            semantic.get("error") is not None or semantic.get("grounding_truncated") is not False or
            not _nonempty(semantic.get("raw"))):
        raise ValueError("retained Fable response missing or incompatible")
    verdict = parse_judge_response(semantic["raw"])
    normalized = {"model": semantic["model"], "contract_version": "2", "status": "complete",
                  "grounding_truncated": False, "verdict": verdict.verdict.lower()}
    if verdict.error or row.get("semantic") != normalized:
        raise ValueError("normalized Fable verdict differs from retained response")
    # Every original allegation must survive into the source challenge, including rejected ones.
    allegations = quality.get("allegations")
    if not isinstance(allegations, list) or not all(_nonempty(a) for a in allegations):
        raise ValueError("quality allegation inventory missing")
    allegations = allegations + verdict.gate_failures
    if not verdict.passed and not verdict.gate_failures:
        allegations.append(verdict.notes or "Fable returned FAIL without gate text")
    findings = row.get("findings")
    if not isinstance(findings, list):
        raise ValueError("challenge register missing")
    challenged = {f.get("original_allegation") for f in findings if isinstance(f, dict)}
    if not set(allegations).issubset(challenged):
        raise ValueError("source challenge omitted an original reviewer allegation")
    for finding in findings:
        if not isinstance(finding, dict) or finding.get("surface") not in packet["reviewer_artifacts"]:
            raise ValueError("challenged surface is absent from the retained output")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("manifest", "archive", "prerequisites", "outputs", "mapping", "evidence", "packets"):
        parser.add_argument(f"--{key}", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = build_decision(args.manifest, args.archive, args.prerequisites,
                                args.outputs, args.mapping, args.evidence, args.packets)
    except (OSError, ValueError, TypeError, KeyError, StopIteration, sqlite3.Error) as exc:
        result = {"schema_version": 1, "review_protocol": "ai_assisted", "status": "incomplete",
                  "human_acceptance": False, "recommendation": "hold", "error": str(exc)}
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
