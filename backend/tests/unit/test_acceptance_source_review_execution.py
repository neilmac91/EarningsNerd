"""The operator journal owns complete attempt history and exact prompt/graph binding."""

from __future__ import annotations

import copy
import base64
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any

import pytest

import evals.acceptance_source_review_execution as execution
from evals.acceptance_source_review_execution import (
    initialize_journal,
    recover_pending_attempt,
    reserve_attempt,
    seal_history,
    settle_attempt,
    validate_execution_binding,
)
from evals.acceptance_source_review_graph import LIMITATIONS as GRAPH_LIMITATIONS
from evals.acceptance_source_units import build_unit_manifest


ACCESSION = "0000000000-26-000001"
PRIMARY = b"<p>Revenue rose.</p><p>Margins fell.</p>"
PACKETS = [{"role": "primary", "sha256": hashlib.sha256(PRIMARY).hexdigest(),
            "byte_length": len(PRIMARY)}]
CUT = PRIMARY.index(b"<p>Margins")
MANIFEST = build_unit_manifest(
    accession_number=ACCESSION,
    packets=PACKETS,
    packet_bytes={"primary": PRIMARY},
    units=[
        {"packet_role": "primary", "structural_kind": "markup", "registrant_scope": "registrant",
         "coverage_spans": [{"start": 0, "end": CUT}], "context_spans": []},
        {"packet_role": "primary", "structural_kind": "markup", "registrant_scope": "registrant",
         "coverage_spans": [{"start": CUT, "end": len(PRIMARY)}], "context_spans": []},
    ],
)
UNITS = MANIFEST["units"]
TEMPLATES = {"leaf": b"Read the exact source span.", "role_synthesis": b"Synthesize exact child reviews."}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


CONTRACT = {
    "schema_version": 1,
    "kind": "e7_offline_source_role_contract",
    "role": "role-b",
    "node_kinds": {kind: {"template_sha256": _sha(template)} for kind, template in TEMPLATES.items()},
    "provider": "example-provider",
    "model": "example-model-1",
    "provider_version": "2026-09-01",
    "exposure_limit": None,
}


def _receipt(reservation: dict[str, Any], kind: str) -> dict[str, Any]:
    return {
        "role_contract_sha256": _sha(_canonical(CONTRACT)),
        "template_sha256": _sha(TEMPLATES[kind]),
        "rendered_prompt_sha256": reservation["prompt_sha256"],
        "input_sha256": reservation["input_sha256"],
        "provider": CONTRACT["provider"],
        "model": CONTRACT["model"],
        "provider_version": CONTRACT["provider_version"],
        "source_only": True,
        "truncated": False,
        "compaction_observed": False,
        "candidate_inputs": [],
    }


def _initialize(root: Path) -> dict[str, Any]:
    return initialize_journal(
        root,
        programme_id="e7-role-b-synthetic",
        accession_number=ACCESSION,
        role_contract=CONTRACT,
        unit_manifest_sha256=_sha(_canonical(MANIFEST)),
        unit_manifest=MANIFEST,
        expected_packets=PACKETS,
        packet_bytes={"primary": PRIMARY},
    )


def _leaf(root: Path, node_id: str, context_id: str, unit_id: str) -> dict[str, Any]:
    return reserve_attempt(
        root,
        node_id=node_id,
        node_kind="leaf",
        context_id=context_id,
        render_inputs={"template": TEMPLATES["leaf"], "unit_id": unit_id},
    )


def _complete(root: Path) -> tuple[dict[str, str], dict[str, Any], dict[str, Any]]:
    _initialize(root)
    first = _leaf(root, "l1", "/root/h29_reference_a", UNITS[0]["unit_id"])
    settle_attempt(
        root,
        reservation_id=first["reservation_id"],
        status="compacted",
        artifact_bytes=b"partial:l1",
        receipt={"outcome": "compacted", "source_only": True},
    )

    l1 = _leaf(root, "l1", "ctx-l1-fresh", UNITS[0]["unit_id"])
    l1_artifact = b"artifact:l1"
    l1_receipt = _receipt(l1, "leaf")
    settle_attempt(root, reservation_id=l1["reservation_id"], status="eligible",
                   artifact_bytes=l1_artifact, receipt=l1_receipt)

    l2 = _leaf(root, "l2", "ctx-l2", UNITS[1]["unit_id"])
    l2_artifact = b"artifact:l2"
    l2_receipt = _receipt(l2, "leaf")
    settle_attempt(root, reservation_id=l2["reservation_id"], status="eligible",
                   artifact_bytes=l2_artifact, receipt=l2_receipt)

    children = [
        {"node_id": "l1", "artifact_sha256": _sha(l1_artifact)},
        {"node_id": "l2", "artifact_sha256": _sha(l2_artifact)},
    ]
    synthesis = reserve_attempt(
        root,
        node_id="s",
        node_kind="role_synthesis",
        context_id="ctx-s",
        render_inputs={
            "template": TEMPLATES["role_synthesis"],
            "children": children,
            "child_artifacts": {_sha(l1_artifact): l1_artifact, _sha(l2_artifact): l2_artifact},
        },
    )
    synthesis_artifact = b"artifact:s"
    synthesis_receipt = _receipt(synthesis, "role_synthesis")
    settle_attempt(root, reservation_id=synthesis["reservation_id"], status="eligible",
                   artifact_bytes=synthesis_artifact, receipt=synthesis_receipt)

    graph = {
        "schema_version": 1,
        "kind": "e7_offline_source_review_graph",
        "accession_number": ACCESSION,
        "role": CONTRACT["role"],
        "unit_manifest_sha256": _sha(_canonical(MANIFEST)),
        "role_contract_sha256": _sha(_canonical(CONTRACT)),
        "context_registry": [
            {"context_id": "/root/h29_reference_a", "node_id": "l1", "attempt": 1,
             "status": "compacted"},
            {"context_id": "ctx-l1-fresh", "node_id": "l1", "attempt": 2, "status": "eligible"},
            {"context_id": "ctx-l2", "node_id": "l2", "attempt": 1, "status": "eligible"},
            {"context_id": "ctx-s", "node_id": "s", "attempt": 1, "status": "eligible"},
        ],
        "nodes": [
            {"node_id": "l1", "kind": "leaf", "unit_id": UNITS[0]["unit_id"], "children": [],
             "context_id": "ctx-l1-fresh", "receipt": l1_receipt,
             "artifact_sha256": _sha(l1_artifact)},
            {"node_id": "l2", "kind": "leaf", "unit_id": UNITS[1]["unit_id"], "children": [],
             "context_id": "ctx-l2", "receipt": l2_receipt,
             "artifact_sha256": _sha(l2_artifact)},
            {"node_id": "s", "kind": "role_synthesis", "unit_id": None, "children": children,
             "context_id": "ctx-s", "receipt": synthesis_receipt,
             "artifact_sha256": _sha(synthesis_artifact)},
        ],
        "semantic_review_attested": False,
        "issue_propagation_verified": False,
        "modality_completeness_attested": False,
        "admission_approved": False,
        "limitations": list(GRAPH_LIMITATIONS),
    }
    artifacts = {_sha(value): value for value in TEMPLATES.values()}
    for reservation, artifact in ((l1, l1_artifact), (l2, l2_artifact),
                                  (synthesis, synthesis_artifact)):
        artifacts[reservation["prompt_sha256"]] = reservation["prompt_bytes"]
        artifacts[_sha(artifact)] = artifact
    validation_inputs = {
        "accession_number": ACCESSION,
        "expected_packets": PACKETS,
        "packet_bytes": {"primary": PRIMARY},
        "unit_manifest": MANIFEST,
        "role_contract": CONTRACT,
        "artifacts": artifacts,
        "foreign_context_ids": ["ctx-role-a"],
    }
    return seal_history(root), graph, validation_inputs


def test_sealed_journal_binds_exact_prompts_graph_and_complete_adverse_history(tmp_path: Path) -> None:
    seal, graph, inputs = _complete(tmp_path / "journal")
    result = validate_execution_binding(
        Path(seal["history_path"]),
        expected_history_sha256=seal["history_sha256"],
        graph=graph,
        graph_validation_inputs=inputs,
    )
    assert result["history_sha256"] == seal["history_sha256"]
    assert result["source_context_closure"] == [
        "/root/h29_reference_a", "ctx-l1-fresh", "ctx-l2", "ctx-s"
    ]
    assert result["ineligible_context_ids"] == ["/root/h29_reference_a"]
    assert result["exact_prompt_construction_verified"] is True
    assert result["complete_operator_history_verified"] is True
    assert result["semantic_review_attested"] is False
    assert result["admission_approved"] is False

    # A self-consistent graph rewrite that drops and renumbers the adverse first attempt still
    # fails against the externally sealed operator history.
    omitted = copy.deepcopy(graph)
    omitted["context_registry"] = omitted["context_registry"][1:]
    omitted["context_registry"][0]["attempt"] = 1
    with pytest.raises(ValueError, match="omits, renumbers or changes sealed attempt history"):
        validate_execution_binding(
            Path(seal["history_path"]), expected_history_sha256=seal["history_sha256"],
            graph=omitted, graph_validation_inputs=inputs,
        )

    # Even a newly endorsed external seal plus matching graph cannot reinterpret the originally
    # durable adverse terminal status after a settlement crash.
    reinterpreted = tmp_path / "reinterpreted-status"
    shutil.copytree(tmp_path / "journal", reinterpreted)
    rewritten_history = json.loads((reinterpreted / "history.json").read_text(encoding="ascii"))
    rewritten_history["attempts"][0]["status"] = "failed"
    rewritten_bytes = _canonical(rewritten_history)
    rewritten_hash = _sha(rewritten_bytes)
    (reinterpreted / "history.json").write_bytes(rewritten_bytes)
    with sqlite3.connect(reinterpreted / "execution.sqlite3") as db:
        db.execute(
            "UPDATE programme SET sealed_history_sha256=? WHERE singleton=1", (rewritten_hash,)
        )
    rewritten_graph = copy.deepcopy(graph)
    rewritten_graph["context_registry"][0]["status"] = "failed"
    with pytest.raises(ValueError, match="settlement intent differs from sealed attempt history"):
        validate_execution_binding(
            reinterpreted / "history.json", expected_history_sha256=rewritten_hash,
            graph=rewritten_graph, graph_validation_inputs=inputs,
        )

    # Retained prompt and output bytes are independent, no-overwrite artifacts rather than hashes
    # that a graph may coherently redraw.
    for relative, replacement, message in (
        ("attempts/0002-", b"rewritten prompt", "retained prompt bytes changed"),
        ("attempts/0003-", b"rewritten output", "retained artifact bytes changed"),
    ):
        copied = tmp_path / ("tampered-" + relative.split("/")[1])
        shutil.copytree(tmp_path / "journal", copied)
        attempt_dir = next((copied / "attempts").glob(relative.split("/")[1] + "*"))
        target = attempt_dir / ("prompt.bin" if "prompt" in replacement.decode() else "artifact.bin")
        target.write_bytes(replacement)
        with pytest.raises(ValueError, match=message):
            validate_execution_binding(
                copied / "history.json", expected_history_sha256=seal["history_sha256"],
                graph=graph, graph_validation_inputs=inputs,
            )


def test_retry_rules_pending_state_and_seal_are_fail_closed(tmp_path: Path) -> None:
    eligible_root = tmp_path / "eligible"
    _initialize(eligible_root)
    eligible = _leaf(eligible_root, "l1", "ctx-one", UNITS[0]["unit_id"])
    invalid_receipt = _receipt(eligible, "leaf")
    invalid_receipt["source_only"] = False
    with pytest.raises(ValueError, match="source_only with no truncation or compaction"):
        settle_attempt(
            eligible_root,
            reservation_id=eligible["reservation_id"],
            status="eligible",
            artifact_bytes=b"eligible",
            receipt=invalid_receipt,
        )
    settle_attempt(eligible_root, reservation_id=eligible["reservation_id"], status="eligible",
                   artifact_bytes=b"eligible", receipt=_receipt(eligible, "leaf"))
    with pytest.raises(ValueError, match="cannot be redrawn"):
        _leaf(eligible_root, "l1", "ctx-two", UNITS[0]["unit_id"])

    changed_root = tmp_path / "changed"
    _initialize(changed_root)
    adverse = _leaf(changed_root, "l1", "ctx-one", UNITS[0]["unit_id"])
    settle_attempt(changed_root, reservation_id=adverse["reservation_id"], status="failed",
                   artifact_bytes=None, receipt={"outcome": "failed"})
    with pytest.raises(ValueError, match="identical node input scope"):
        _leaf(changed_root, "l1", "ctx-two", UNITS[1]["unit_id"])

    pending_root = tmp_path / "pending"
    _initialize(pending_root)
    pending = _leaf(pending_root, "l1", "ctx-pending", UNITS[0]["unit_id"])
    with sqlite3.connect(pending_root / "execution.sqlite3") as db:
        row_count = db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
        prompt_relative = db.execute(
            "SELECT prompt_path FROM attempts WHERE reservation_id=?", (pending["reservation_id"],)
        ).fetchone()[0]
    recovered = recover_pending_attempt(pending_root)
    assert recovered is not None
    assert {
        key: recovered[key]
        for key in (
            "reservation_id", "sequence", "node_id", "context_id", "attempt", "prompt_bytes",
            "prompt_sha256", "input_manifest_sha256", "input_sha256",
        )
    } == pending
    assert recovered["delivery_uncertain"] is True
    assert recovered["redispatch_permitted"] is False
    assert recovered["settlement_recovery_required"] is False
    assert recovered["settlement_intent"] is None
    with sqlite3.connect(pending_root / "execution.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] == row_count

    retained_prompt = pending_root / prompt_relative
    exact_prompt = retained_prompt.read_bytes()
    retained_prompt.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="retained pending prompt bytes changed"):
        recover_pending_attempt(pending_root)
    retained_prompt.write_bytes(exact_prompt)
    with pytest.raises(ValueError, match="pending attempt blocks another reservation"):
        _leaf(pending_root, "l2", "ctx-other", UNITS[1]["unit_id"])
    with pytest.raises(ValueError, match="pending attempt blocks sealing"):
        seal_history(pending_root)
    settle_attempt(
        pending_root, reservation_id=recovered["reservation_id"], status="retired",
        artifact_bytes=None, receipt={"outcome": "delivery-uncertain-retired"},
    )
    assert recover_pending_attempt(pending_root) is None
    retry = _leaf(pending_root, "l1", "ctx-fresh", UNITS[0]["unit_id"])
    assert retry["attempt"] == 2

    seal, _graph, _inputs = _complete(tmp_path / "sealed")
    with pytest.raises(ValueError, match="operator journal is sealed"):
        _leaf(tmp_path / "sealed", "later", "ctx-later", UNITS[0]["unit_id"])
    history = json.loads(Path(seal["history_path"]).read_text(encoding="ascii"))
    with pytest.raises(ValueError, match="operator journal is sealed"):
        settle_attempt(
            tmp_path / "sealed", reservation_id=history["attempts"][0]["reservation_id"],
            status="retired", artifact_bytes=None, receipt={"outcome": "retired"},
        )
    assert recover_pending_attempt(tmp_path / "sealed") is None


def test_parent_requires_prior_eligible_journal_children_and_retained_bytes(tmp_path: Path) -> None:
    root = tmp_path / "children"
    _initialize(root)
    child_artifact = b"artifact:l1"
    digest = _sha(child_artifact)
    parent_inputs = {
        "template": TEMPLATES["role_synthesis"],
        "children": [{"node_id": "l1", "artifact_sha256": digest}],
        "child_artifacts": {digest: child_artifact},
    }
    with pytest.raises(ValueError, match="not a prior terminal eligible journal node"):
        reserve_attempt(
            root, node_id="s", node_kind="role_synthesis", context_id="ctx-s-early",
            render_inputs=parent_inputs,
        )

    leaf = _leaf(root, "l1", "ctx-l1", UNITS[0]["unit_id"])
    settle_attempt(
        root, reservation_id=leaf["reservation_id"], status="eligible",
        artifact_bytes=child_artifact, receipt=_receipt(leaf, "leaf"),
    )
    changed = copy.deepcopy(parent_inputs)
    changed["child_artifacts"] = {digest: b"foreign bytes"}
    with pytest.raises(ValueError, match="retained journal artifact"):
        reserve_attempt(
            root, node_id="s", node_kind="role_synthesis", context_id="ctx-s-foreign",
            render_inputs=changed,
        )
    reservation = reserve_attempt(
        root, node_id="s", node_kind="role_synthesis", context_id="ctx-s",
        render_inputs=parent_inputs,
    )
    assert reservation["attempt"] == 1


def test_identical_files_recover_precommit_settle_and_seal_crashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A pre-publication crash must not expose a partial immutable record at its final path.
    atomic_path = tmp_path / "atomic-record.json"
    with monkeypatch.context() as patch:
        def interrupt_publication(source: Path, destination: Path) -> None:
            assert source.read_bytes() == b"complete record"
            assert not destination.exists()
            raise RuntimeError("simulated crash before atomic publication")

        patch.setattr(execution.os, "link", interrupt_publication)
        with pytest.raises(RuntimeError, match="before atomic publication"):
            execution._durable_new(atomic_path, b"complete record")
    assert not atomic_path.exists()
    execution._durable_new(atomic_path, b"complete record")
    assert atomic_path.read_bytes() == b"complete record"

    adverse_root = tmp_path / "intent-recover"
    _initialize(adverse_root)
    adverse = _leaf(adverse_root, "l1", "ctx-adverse", UNITS[0]["unit_id"])
    original = execution._durable_exact
    intent_interrupted = False

    def interrupt_after_intent(path: Path, data: bytes) -> None:
        nonlocal intent_interrupted
        original(path, data)
        if path.name == "settlement-intent.json" and not intent_interrupted:
            intent_interrupted = True
            raise RuntimeError("simulated crash after settlement intent")

    monkeypatch.setattr(execution, "_durable_exact", interrupt_after_intent)
    with pytest.raises(RuntimeError, match="simulated crash"):
        settle_attempt(
            adverse_root, reservation_id=adverse["reservation_id"], status="failed",
            artifact_bytes=b"adverse output survived", receipt={"outcome": "failed"},
        )
    monkeypatch.setattr(execution, "_durable_exact", original)
    intent_path = next((adverse_root / "attempts").iterdir()) / "settlement-intent.json"
    external_intent = tmp_path / "external-intent.json"
    external_intent.write_bytes(intent_path.read_bytes())
    for name, target in (
        ("external-intent-link", external_intent),
        ("dangling-external-intent-link", tmp_path / "missing-external-intent.json"),
    ):
        escaped = tmp_path / name
        shutil.copytree(adverse_root, escaped)
        escaped_intent = next((escaped / "attempts").iterdir()) / "settlement-intent.json"
        escaped_intent.unlink()
        escaped_intent.symlink_to(target)
        with pytest.raises(ValueError, match="journal artifact path escapes its root"):
            recover_pending_attempt(escaped)
    interrupted = recover_pending_attempt(adverse_root)
    assert interrupted is not None
    assert interrupted["delivery_uncertain"] is True
    assert interrupted["redispatch_permitted"] is False
    assert interrupted["settlement_recovery_required"] is True
    assert interrupted["settlement_intent"] == {
        "schema_version": 1,
        "kind": "e7_operator_source_review_settlement_intent",
        "reservation_id": adverse["reservation_id"],
        "status": "failed",
        "artifact_sha256": _sha(b"adverse output survived"),
        "receipt_sha256": _sha(_canonical({"outcome": "failed"})),
        "artifact_base64": base64.b64encode(b"adverse output survived").decode("ascii"),
        "receipt": {"outcome": "failed"},
    }
    # Neither projected file exists yet: all recovery bytes come from the atomic intent.
    assert not intent_path.with_name("artifact.bin").exists()
    assert not intent_path.with_name("receipt.json").exists()
    assert interrupted["settlement_artifact_bytes"] == b"adverse output survived"
    assert interrupted["settlement_receipt"] == {"outcome": "failed"}
    corrupted = tmp_path / "intent-payload-corrupted"
    shutil.copytree(adverse_root, corrupted)
    corrupt_path = next((corrupted / "attempts").iterdir()) / "settlement-intent.json"
    corrupt_intent = json.loads(corrupt_path.read_bytes())
    corrupt_intent["artifact_base64"] = base64.b64encode(b"different payload").decode("ascii")
    corrupt_path.write_bytes(_canonical(corrupt_intent))
    with pytest.raises(ValueError, match="artifact payload differs"):
        recover_pending_attempt(corrupted)
    with pytest.raises(ValueError, match="already exists with different bytes"):
        settle_attempt(
            adverse_root, reservation_id=adverse["reservation_id"], status="compacted",
            artifact_bytes=None, receipt={"outcome": "failed"},
        )
    with pytest.raises(ValueError, match="already exists with different bytes"):
        settle_attempt(
            adverse_root, reservation_id=adverse["reservation_id"], status="failed",
            artifact_bytes=None, receipt={"outcome": "changed"},
        )
    settle_attempt(
        adverse_root, reservation_id=interrupted["reservation_id"],
        status=interrupted["settlement_intent"]["status"],
        artifact_bytes=interrupted["settlement_artifact_bytes"],
        receipt=interrupted["settlement_receipt"],
    )
    assert recover_pending_attempt(adverse_root) is None

    root = tmp_path / "recover"
    _initialize(root)
    leaf = _leaf(root, "l1", "ctx-l1", UNITS[0]["unit_id"])
    attempt_dir = next((root / "attempts").iterdir())
    artifact = b"artifact:l1"
    receipt = _receipt(leaf, "leaf")
    (attempt_dir / "artifact.bin").write_bytes(artifact)
    (attempt_dir / "receipt.json").write_bytes(_canonical(receipt))
    settle_attempt(
        root, reservation_id=leaf["reservation_id"], status="eligible",
        artifact_bytes=artifact, receipt=receipt,
    )

    interrupted = False

    def interrupt_after_history_write(path: Path, data: bytes) -> None:
        nonlocal interrupted
        original(path, data)
        if path.name == "history.json" and not interrupted:
            interrupted = True
            raise RuntimeError("simulated crash before SQLite seal marker")

    monkeypatch.setattr(execution, "_durable_exact", interrupt_after_history_write)
    with pytest.raises(RuntimeError, match="simulated crash"):
        seal_history(root)
    monkeypatch.setattr(execution, "_durable_exact", original)
    seal = seal_history(root)
    assert Path(seal["history_path"]).read_bytes()
    # A commit-before-return loss must recover the stored authority without writing or resealing.
    with monkeypatch.context() as patch:
        def reject_republication(_path: Path, _data: bytes) -> None:
            raise AssertionError("committed seal recovery must not publish new authority")

        patch.setattr(execution, "_durable_exact", reject_republication)
        assert seal_history(root) == seal
    edited_history = tmp_path / "edited-sealed-history"
    shutil.copytree(root, edited_history)
    (edited_history / "history.json").write_bytes(b"{}")
    with pytest.raises(ValueError, match="committed seal differs"):
        seal_history(edited_history)
    edited_rows = tmp_path / "edited-sealed-rows"
    shutil.copytree(root, edited_rows)
    with sqlite3.connect(edited_rows / "execution.sqlite3") as db:
        db.execute("UPDATE attempts SET status='failed'")
    with pytest.raises(ValueError, match="committed seal differs"):
        seal_history(edited_rows)


def test_initialization_freezes_real_source_and_rejects_foreign_unit_before_dispatch(tmp_path: Path) -> None:
    root = tmp_path / "frozen"
    contract = copy.deepcopy(CONTRACT)
    manifest = copy.deepcopy(MANIFEST)
    packets = copy.deepcopy(PACKETS)
    source_bytes = {"primary": PRIMARY}
    initialize_journal(
        root,
        programme_id="e7-role-b-frozen",
        accession_number=ACCESSION,
        role_contract=contract,
        unit_manifest_sha256=_sha(_canonical(MANIFEST)),
        unit_manifest=manifest,
        expected_packets=packets,
        packet_bytes=source_bytes,
    )
    contract["model"] = "mutated-after-initialize"
    manifest["units"].clear()
    packets.clear()
    source_bytes["primary"] = b"mutated"
    reservation = _leaf(root, "l1", "ctx-frozen", UNITS[0]["unit_id"])
    assert reservation["input_sha256"] == UNITS[0]["unit_id"]
    settle_attempt(root, reservation_id=reservation["reservation_id"], status="eligible",
                   artifact_bytes=b"eligible", receipt=_receipt(reservation, "leaf"))

    with pytest.raises(ValueError, match="unit_id must identify exactly one unit"):
        _leaf(root, "l2", "ctx-foreign", "f" * 64)
    # The rejected foreign unit did not create a second durable attempt or dispatchable prompt.
    assert len(list((root / "attempts").iterdir())) == 1
