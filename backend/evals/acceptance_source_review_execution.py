"""Operator-owned attempt history for one offline E7 source-review role.

The journal reserves one context before dispatch, retains every terminal attempt, and seals an
ordered history outside the review graph.  Binding validation combines that external history with
deterministic prompt rendering and the unchanged schema-1 review-graph validator.  It establishes
completeness only for contexts dispatched through this journal; it does not claim provider-global
history, private model attention, semantic review, modality completeness, or admission.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from evals.acceptance_source_review_graph import (
    ATTESTATION_FLAGS,
    CONTEXT_STATUSES,
    NODE_KINDS,
    validate_review_graph,
    validate_role_contract,
    validate_source_context_id,
)
from evals.acceptance_source_review_prompts import (
    INPUT_MANIFEST_KIND,
    RENDER_KIND,
    ValidatedPromptSource,
    render_leaf_prompt,
    render_parent_prompt,
    validate_prompt_source,
)


SCHEMA_VERSION = 1
JOURNAL_KIND = "e7_operator_source_review_journal"
HISTORY_KIND = "e7_operator_source_review_history"
VALIDATION_KIND = "e7_operator_source_review_execution_validation"
SETTLEMENT_INTENT_KIND = "e7_operator_source_review_settlement_intent"
RESERVED_STATUS = "reserved"
TERMINAL_STATUSES = tuple(CONTEXT_STATUSES)
LIMITATIONS = (
    "Attempt completeness covers only contexts dispatched through this operator journal, never provider-global history.",
    "Exact prompt construction binds retained bytes and declared inputs; it does not prove private model attention.",
    "The schema-1 graph remains non-admitting and does not validate issue propagation or modality completeness.",
    "No source review, E7 coverage_status or E7 admission is attested.",
)

_ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}")
_LABEL = re.compile(r"[a-z0-9][a-z0-9_.:-]{0,127}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_BINDING_KEYS = frozenset({
    "schema_version", "kind", "programme_id", "accession_number", "role_contract",
    "role_contract_sha256", "unit_manifest_sha256", "expected_packets_sha256",
    "packet_bytes_sha256", "limitations", *ATTESTATION_FLAGS,
})
_HISTORY_KEYS = frozenset({
    "schema_version", "kind", "programme_id", "accession_number", "role_contract_sha256",
    "unit_manifest_sha256", "attempts", "limitations", *ATTESTATION_FLAGS,
})
_ATTEMPT_KEYS = frozenset({
    "sequence", "reservation_id", "node_id", "node_kind", "context_id", "attempt", "status",
    "template_sha256", "input_sha256", "input_manifest_sha256", "prompt_sha256", "render_identity",
    "prompt_path", "input_manifest_path", "artifact_path", "artifact_sha256", "receipt_path",
    "receipt_sha256",
})
_GRAPH_INPUT_KEYS = frozenset({
    "accession_number", "expected_packets", "packet_bytes", "unit_manifest", "role_contract",
    "artifacts", "foreign_context_ids",
})
_RENDER_RESULT_KEYS = frozenset({
    "schema_version", "kind", "prompt_bytes", "prompt_sha256", "input_manifest_bytes",
    "input_manifest_sha256", "input_sha256",
})
_RECEIPT_KEYS = frozenset({
    "role_contract_sha256", "template_sha256", "rendered_prompt_sha256", "input_sha256",
    "provider", "model", "provider_version", "source_only", "truncated",
    "compaction_observed", "candidate_inputs",
})
_CHILD_KEYS = frozenset({"node_id", "artifact_sha256"})
_SETTLEMENT_INTENT_KEYS = frozenset({
    "schema_version", "kind", "reservation_id", "status", "artifact_sha256", "receipt_sha256",
    "artifact_base64", "receipt",
})
_SOURCE_CACHE: tuple[tuple[Path, str], ValidatedPromptSource] | None = None


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode("ascii")
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError("value is not canonical JSON") from exc


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _token(value: Any, pattern: re.Pattern[str], name: str) -> str:
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise ValueError(f"invalid {name}")
    return value


def _object(value: Any, keys: frozenset[str], name: str) -> dict[str, Any]:
    if type(value) is not dict or any(type(key) is not str for key in value) or set(value) != keys:
        raise ValueError(f"{name} must be an object with exactly: {', '.join(sorted(keys))}")
    return value


def _safe(root: Path, relative: str) -> Path:
    if type(relative) is not str or not relative or relative.startswith("/"):
        raise ValueError("invalid journal artifact path")
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("journal artifact path escapes its root") from exc
    return path


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _durable_new(path: Path, data: bytes) -> None:
    if type(data) is not bytes:
        raise ValueError("durable journal artifacts must be bytes")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Publish only complete, fsynced bytes. Exclusive linking preserves immutable-create
    # semantics, whereas writing directly to the final path can strand a partial file on crash.
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.pending")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)
        _fsync_directory(path.parent)


def _durable_exact(path: Path, data: bytes) -> None:
    """Create immutable bytes, or recover a pre-commit crash only when they are identical."""
    try:
        _durable_new(path, data)
    except FileExistsError:
        if not path.is_file() or path.read_bytes() != data:
            raise ValueError(f"immutable journal artifact already exists with different bytes: {path.name}")


def _connect(root: Path, *, read_only: bool = False) -> sqlite3.Connection:
    database = root / "execution.sqlite3"
    if read_only:
        connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    else:
        connection = sqlite3.connect(database)
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
    connection.row_factory = sqlite3.Row
    return connection


def _load_binding(root: Path, db: sqlite3.Connection) -> dict[str, Any]:
    row = db.execute(
        "SELECT binding_bytes, sealed_history_sha256 FROM programme WHERE singleton=1"
    ).fetchone()
    if row is None:
        raise ValueError("operator journal is not initialized")
    binding_bytes = bytes(row["binding_bytes"])
    path = root / "binding.json"
    if not path.is_file() or path.read_bytes() != binding_bytes:
        raise ValueError("frozen journal binding changed")
    try:
        binding = json.loads(binding_bytes.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("frozen journal binding is invalid") from exc
    _object(binding, _BINDING_KEYS, "journal binding")
    if _canonical(binding) != binding_bytes:
        raise ValueError("frozen journal binding is not canonical")
    if binding["schema_version"] != SCHEMA_VERSION or binding["kind"] != JOURNAL_KIND:
        raise ValueError("unsupported journal binding")
    if any(binding[flag] is not False for flag in ATTESTATION_FLAGS):
        raise ValueError("journal binding cannot attest review or admission")
    if binding["limitations"] != list(LIMITATIONS):
        raise ValueError("journal binding limitations changed")
    if validate_role_contract(binding["role_contract"]) != binding["role_contract_sha256"]:
        raise ValueError("frozen role contract changed")
    _token(binding["unit_manifest_sha256"], _SHA256, "frozen unit_manifest_sha256")
    _token(binding["expected_packets_sha256"], _SHA256, "frozen expected_packets_sha256")
    packet_hashes = binding["packet_bytes_sha256"]
    if (
        type(packet_hashes) is not dict
        or not packet_hashes
        or any(type(role) is not str or _LABEL.fullmatch(role) is None for role in packet_hashes)
    ):
        raise ValueError("frozen packet_bytes_sha256 must map packet roles to hashes")
    for role, digest in packet_hashes.items():
        _token(digest, _SHA256, f"frozen packet hash for {role}")
    return binding


def _read_frozen_source(root: Path, binding: dict[str, Any]) -> tuple[dict[str, Any], list[Any], dict[str, bytes]]:
    manifest_bytes = (root / "source" / "unit-manifest.json").read_bytes()
    packets_bytes = (root / "source" / "expected-packets.json").read_bytes()
    if _sha(manifest_bytes) != binding["unit_manifest_sha256"]:
        raise ValueError("frozen source unit manifest changed")
    if _sha(packets_bytes) != binding["expected_packets_sha256"]:
        raise ValueError("frozen expected packet declarations changed")
    try:
        manifest = json.loads(manifest_bytes.decode("ascii"))
        expected_packets = json.loads(packets_bytes.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("frozen source declarations are not canonical JSON") from exc
    if _canonical(manifest) != manifest_bytes or _canonical(expected_packets) != packets_bytes:
        raise ValueError("frozen source declarations are not canonical JSON")
    packet_bytes: dict[str, bytes] = {}
    for role, digest in binding["packet_bytes_sha256"].items():
        raw = (root / "source" / "packets" / f"{digest}.bin").read_bytes()
        if _sha(raw) != digest:
            raise ValueError(f"frozen packet bytes changed for {role}")
        packet_bytes[role] = raw
    return manifest, expected_packets, packet_bytes


def _validated_source(root: Path, binding: dict[str, Any]) -> ValidatedPromptSource:
    global _SOURCE_CACHE
    cache_key = (root, _sha(_canonical(binding)))
    if _SOURCE_CACHE is not None and _SOURCE_CACHE[0] == cache_key:
        return _SOURCE_CACHE[1]
    manifest, expected_packets, packet_bytes = _read_frozen_source(root, binding)
    source = validate_prompt_source(
        accession_number=binding["accession_number"],
        unit_manifest=manifest,
        expected_packets=expected_packets,
        packet_bytes=packet_bytes,
    )
    if source.manifest_sha256 != binding["unit_manifest_sha256"]:
        raise ValueError("validated prompt source differs from the frozen manifest")
    # A single owner is enough for the active operator session. Replacing it bounds retained corpus
    # bytes while avoiding a full corpus read and validation for every leaf reservation.
    _SOURCE_CACHE = (cache_key, source)
    return source


def _require_open(db: sqlite3.Connection) -> None:
    sealed = db.execute(
        "SELECT sealed_history_sha256 FROM programme WHERE singleton=1"
    ).fetchone()
    if sealed is None:
        raise ValueError("operator journal is not initialized")
    if sealed[0] is not None:
        raise ValueError("operator journal is sealed")


def _require_no_uncommitted_seal(root: Path) -> None:
    if (root / "history.json").exists():
        raise ValueError("journal has an uncommitted history seal; retry sealing before mutation")


def _validate_eligible_receipt(
    binding: dict[str, Any], row: sqlite3.Row, receipt: dict[str, Any]
) -> None:
    _object(receipt, _RECEIPT_KEYS, "eligible receipt")
    expected = {
        "role_contract_sha256": binding["role_contract_sha256"],
        "template_sha256": row["template_sha256"],
        "rendered_prompt_sha256": row["prompt_sha256"],
        "input_sha256": row["input_sha256"],
        "provider": binding["role_contract"]["provider"],
        "model": binding["role_contract"]["model"],
        "provider_version": binding["role_contract"]["provider_version"],
    }
    for field, value in expected.items():
        if type(receipt[field]) is not type(value) or receipt[field] != value:
            raise ValueError(f"eligible receipt {field} does not match the frozen reservation")
    if (
        receipt["source_only"] is not True
        or receipt["truncated"] is not False
        or receipt["compaction_observed"] is not False
    ):
        raise ValueError("eligible receipt must be source_only with no truncation or compaction")
    if type(receipt["candidate_inputs"]) is not list or receipt["candidate_inputs"]:
        raise ValueError("eligible receipt must have no candidate inputs")


def _validate_journal_children(
    root: Path,
    db: sqlite3.Connection,
    *,
    parent_node_id: str,
    children: Any,
    child_artifacts: Any,
) -> None:
    if type(children) is not list or not children:
        raise ValueError("parent children must be a non-empty ordered list")
    if type(child_artifacts) is not dict or any(
        type(digest) is not str or type(data) is not bytes
        for digest, data in child_artifacts.items()
    ):
        raise ValueError("child_artifacts must map artifact SHA-256 strings to immutable bytes")
    seen_nodes: set[str] = set()
    seen_hashes: set[str] = set()
    for value in children:
        child = _object(value, _CHILD_KEYS, "parent child")
        child_id = _token(child["node_id"], _LABEL, "child node_id")
        digest = _token(child["artifact_sha256"], _SHA256, "child artifact_sha256")
        if child_id == parent_node_id or child_id in seen_nodes or digest in seen_hashes:
            raise ValueError("parent children must be prior unique journal nodes and artifacts")
        row = db.execute(
            "SELECT * FROM attempts WHERE node_id=? ORDER BY attempt DESC LIMIT 1", (child_id,)
        ).fetchone()
        if (
            row is None
            or row["status"] != "eligible"
            or row["artifact_path"] is None
            or row["artifact_sha256"] != digest
        ):
            raise ValueError(f"parent child {child_id} is not a prior terminal eligible journal node")
        retained = _safe(root, row["artifact_path"]).read_bytes()
        if _sha(retained) != digest or child_artifacts.get(digest) != retained:
            raise ValueError(f"parent child {child_id} does not match its retained journal artifact")
        seen_nodes.add(child_id)
        seen_hashes.add(digest)
    if set(child_artifacts) != seen_hashes:
        raise ValueError("child_artifacts must contain exactly the journal children's artifacts")


def _settlement_intent(
    *,
    reservation_id: str,
    status: str,
    artifact_sha256: str | None,
    receipt_sha256: str,
    artifact_bytes: bytes | None,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": SETTLEMENT_INTENT_KIND,
        "reservation_id": reservation_id,
        "status": status,
        "artifact_sha256": artifact_sha256,
        "receipt_sha256": receipt_sha256,
        "artifact_base64": base64.b64encode(artifact_bytes).decode("ascii")
        if artifact_bytes is not None else None,
        "receipt": receipt,
    }


def _intent_payloads(intent: dict[str, Any]) -> tuple[bytes | None, dict[str, Any]]:
    """Recover complete payloads from the same atomic record that freezes their disposition."""
    encoded = intent["artifact_base64"]
    artifact = None
    if encoded is not None:
        if type(encoded) is not str:
            raise ValueError("settlement intent artifact encoding is invalid")
        try:
            artifact = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("settlement intent artifact encoding is invalid") from exc
        if base64.b64encode(artifact).decode("ascii") != encoded:
            raise ValueError("settlement intent artifact encoding is not canonical")
    if (_sha(artifact) if artifact is not None else None) != intent["artifact_sha256"]:
        raise ValueError("settlement intent artifact payload differs from its hash")
    receipt = intent["receipt"]
    if type(receipt) is not dict or _sha(_canonical(receipt)) != intent["receipt_sha256"]:
        raise ValueError("settlement intent receipt payload differs from its hash")
    return artifact, receipt


def _render_identity(node_kind: str, render_inputs: dict[str, Any]) -> tuple[dict[str, Any], bytes]:
    if type(render_inputs) is not dict or any(type(key) is not str for key in render_inputs):
        raise ValueError("render_inputs must be an object")
    template = render_inputs.get("template")
    if type(template) is not bytes:
        raise ValueError("render_inputs template must be bytes")
    if node_kind == "leaf":
        expected = {"template", "unit_id"}
        if set(render_inputs) != expected:
            raise ValueError("leaf render_inputs must contain template and unit_id")
        unit_id = _token(render_inputs["unit_id"], _SHA256, "leaf unit_id")
        return {"unit_id": unit_id}, template
    expected = {"template", "children", "child_artifacts"}
    if set(render_inputs) != expected:
        raise ValueError("parent render_inputs must contain template, children, child_artifacts")
    children = render_inputs["children"]
    if type(children) is not list:
        raise ValueError("parent children must be a list")
    # The renderer performs the authoritative child validation. This independent canonical copy is
    # retained as the retry scope and later reconstruction instruction.
    copied = json.loads(_canonical(children).decode("ascii"))
    return {"children": copied}, template


def _validate_render_result(result: Any) -> dict[str, Any]:
    _object(result, _RENDER_RESULT_KEYS, "prompt render result")
    if type(result["schema_version"]) is not int or result["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported prompt render schema_version")
    if type(result["kind"]) is not str or result["kind"] != RENDER_KIND:
        raise ValueError("unsupported prompt render kind")
    for name in ("prompt_bytes", "input_manifest_bytes"):
        if type(result[name]) is not bytes:
            raise ValueError(f"prompt render {name} must be bytes")
    for name, data_name in (
        ("prompt_sha256", "prompt_bytes"),
        ("input_manifest_sha256", "input_manifest_bytes"),
    ):
        _token(result[name], _SHA256, f"prompt render {name}")
        if result[name] != _sha(result[data_name]):
            raise ValueError(f"prompt render {name} does not match its bytes")
    _token(result["input_sha256"], _SHA256, "prompt render input_sha256")
    return result


def _render(
    binding: dict[str, Any],
    *,
    node_id: str,
    node_kind: str,
    reservation_id: str,
    render_inputs: dict[str, Any],
    source: ValidatedPromptSource | None = None,
) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    identity, template = _render_identity(node_kind, render_inputs)
    common = {
        "template": template,
        "accession_number": binding["accession_number"],
        "role": binding["role_contract"]["role"],
        "node_id": node_id,
        "role_contract_sha256": binding["role_contract_sha256"],
        "reservation_id": reservation_id,
    }
    if node_kind == "leaf":
        if type(source) is not ValidatedPromptSource:
            raise ValueError("leaf rendering requires the frozen validated prompt source")
        result = render_leaf_prompt(
            **common,
            source=source,
            unit_id=render_inputs["unit_id"],
        )
    else:
        result = render_parent_prompt(
            **common,
            node_kind=node_kind,
            children=render_inputs["children"],
            child_artifacts=render_inputs["child_artifacts"],
        )
    return _validate_render_result(result), identity, template


def initialize_journal(
    root: Path,
    *,
    programme_id: str,
    accession_number: str,
    role_contract: dict[str, Any],
    unit_manifest_sha256: str,
    unit_manifest: dict[str, Any],
    expected_packets: list[dict[str, Any]],
    packet_bytes: dict[str, bytes],
) -> dict[str, Any]:
    """Create a new immutable programme binding before any review context is opened."""
    root = Path(root)
    _token(programme_id, _LABEL, "programme_id")
    _token(accession_number, _ACCESSION, "accession_number")
    _token(unit_manifest_sha256, _SHA256, "unit_manifest_sha256")
    role_contract_sha256 = validate_role_contract(role_contract)
    # Canonical round-trip both rejects non-JSON values and detaches the frozen binding from caller
    # mutation after initialization.
    frozen_contract = json.loads(_canonical(role_contract).decode("ascii"))
    frozen_manifest_bytes = _canonical(unit_manifest)
    frozen_expected_bytes = _canonical(expected_packets)
    frozen_manifest = json.loads(frozen_manifest_bytes.decode("ascii"))
    frozen_expected = json.loads(frozen_expected_bytes.decode("ascii"))
    if type(packet_bytes) is not dict or any(
        type(role) is not str or type(data) is not bytes for role, data in packet_bytes.items()
    ):
        raise ValueError("packet_bytes must map packet roles to immutable bytes")
    frozen_packet_bytes = {role: bytes(data) for role, data in packet_bytes.items()}
    source = validate_prompt_source(
        accession_number=accession_number,
        unit_manifest=frozen_manifest,
        expected_packets=frozen_expected,
        packet_bytes=frozen_packet_bytes,
    )
    if source.manifest_sha256 != unit_manifest_sha256:
        raise ValueError("unit_manifest_sha256 does not match the validated source manifest")
    packet_hashes = {role: _sha(data) for role, data in frozen_packet_bytes.items()}
    binding = {
        "schema_version": SCHEMA_VERSION,
        "kind": JOURNAL_KIND,
        "programme_id": programme_id,
        "accession_number": accession_number,
        "role_contract": frozen_contract,
        "role_contract_sha256": role_contract_sha256,
        "unit_manifest_sha256": unit_manifest_sha256,
        "expected_packets_sha256": _sha(frozen_expected_bytes),
        "packet_bytes_sha256": packet_hashes,
        "limitations": list(LIMITATIONS),
        **{flag: False for flag in ATTESTATION_FLAGS},
    }
    binding_bytes = _canonical(binding)
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    root = root.resolve()
    (root / "attempts").mkdir(mode=0o700)
    (root / "source" / "packets").mkdir(mode=0o700, parents=True)
    _durable_new(root / "source" / "unit-manifest.json", frozen_manifest_bytes)
    _durable_new(root / "source" / "expected-packets.json", frozen_expected_bytes)
    written: set[str] = set()
    for role, data in frozen_packet_bytes.items():
        digest = packet_hashes[role]
        if digest not in written:
            _durable_new(root / "source" / "packets" / f"{digest}.bin", data)
            written.add(digest)
    _durable_new(root / "binding.json", binding_bytes)
    with _connect(root) as db:
        db.executescript(
            """
            CREATE TABLE programme (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                binding_bytes BLOB NOT NULL,
                sealed_history_path TEXT,
                sealed_history_sha256 TEXT
            );
            CREATE TABLE attempts (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                reservation_id TEXT NOT NULL UNIQUE,
                node_id TEXT NOT NULL,
                node_kind TEXT NOT NULL,
                context_id TEXT NOT NULL UNIQUE,
                attempt INTEGER NOT NULL,
                status TEXT NOT NULL,
                template_sha256 TEXT NOT NULL,
                input_sha256 TEXT NOT NULL,
                input_manifest_sha256 TEXT NOT NULL,
                prompt_sha256 TEXT NOT NULL,
                render_identity BLOB NOT NULL,
                prompt_path TEXT NOT NULL UNIQUE,
                input_manifest_path TEXT NOT NULL UNIQUE,
                artifact_path TEXT,
                artifact_sha256 TEXT,
                receipt_path TEXT,
                receipt_sha256 TEXT,
                UNIQUE(node_id, attempt)
            );
            """
        )
        db.execute("INSERT INTO programme(singleton,binding_bytes) VALUES (1,?)", (binding_bytes,))
    global _SOURCE_CACHE
    _SOURCE_CACHE = ((root, _sha(binding_bytes)), source)
    _fsync_directory(root)
    return binding


def reserve_attempt(
    root: Path,
    *,
    node_id: str,
    node_kind: str,
    context_id: str,
    render_inputs: dict[str, Any],
) -> dict[str, Any]:
    """Durably reserve and render the only prompt that the caller may dispatch."""
    root = Path(root).resolve()
    _token(node_id, _LABEL, "node_id")
    if type(node_kind) is not str or node_kind not in NODE_KINDS:
        raise ValueError(f"node_kind must be one of: {', '.join(NODE_KINDS)}")
    validate_source_context_id(context_id)
    with _connect(root) as db:
        db.execute("BEGIN IMMEDIATE")
        binding = _load_binding(root, db)
        _require_open(db)
        _require_no_uncommitted_seal(root)
        if db.execute("SELECT 1 FROM attempts WHERE status=? LIMIT 1", (RESERVED_STATUS,)).fetchone():
            raise ValueError("a pending attempt blocks another reservation")
        if db.execute("SELECT 1 FROM attempts WHERE context_id=?", (context_id,)).fetchone():
            raise ValueError("context_id is already reserved")
        prior = db.execute(
            "SELECT * FROM attempts WHERE node_id=? ORDER BY attempt", (node_id,)
        ).fetchall()
        if prior and prior[-1]["status"] == "eligible":
            raise ValueError("an eligible node cannot be redrawn")
        if prior and prior[-1]["status"] == RESERVED_STATUS:
            raise ValueError("a pending attempt blocks retry")
        _identity, template = _render_identity(node_kind, render_inputs)
        template_sha256 = _sha(template)
        declared_template = binding["role_contract"]["node_kinds"].get(node_kind)
        if declared_template is None or declared_template["template_sha256"] != template_sha256:
            raise ValueError("render template differs from the frozen role contract")
        if node_kind != "leaf":
            _validate_journal_children(
                root,
                db,
                parent_node_id=node_id,
                children=render_inputs["children"],
                child_artifacts=render_inputs["child_artifacts"],
            )
        source = _validated_source(root, binding) if node_kind == "leaf" else None
        reservation_id = uuid.uuid4().hex
        result, render_identity, template = _render(
            binding,
            node_id=node_id,
            node_kind=node_kind,
            reservation_id=reservation_id,
            render_inputs=render_inputs,
            source=source,
        )
        identity_bytes = _canonical(render_identity)
        if prior:
            previous = prior[-1]
            if (
                previous["status"] not in TERMINAL_STATUSES
                or previous["context_id"] == context_id
                or previous["node_kind"] != node_kind
                or previous["template_sha256"] != template_sha256
                or previous["input_sha256"] != result["input_sha256"]
                or bytes(previous["render_identity"]) != identity_bytes
            ):
                raise ValueError("retry must use a fresh context with identical node input scope")
        attempt = len(prior) + 1
        sequence = db.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM attempts").fetchone()[0]
        directory_rel = f"attempts/{sequence:04d}-{reservation_id}"
        directory = _safe(root, directory_rel)
        directory.mkdir(mode=0o700, parents=False, exist_ok=False)
        _fsync_directory(directory.parent)
        prompt_rel = f"{directory_rel}/prompt.bin"
        input_manifest_rel = f"{directory_rel}/input-manifest.json"
        _durable_new(_safe(root, prompt_rel), result["prompt_bytes"])
        _durable_new(_safe(root, input_manifest_rel), result["input_manifest_bytes"])
        db.execute(
            """
            INSERT INTO attempts(
                reservation_id,node_id,node_kind,context_id,attempt,status,template_sha256,
                input_sha256,input_manifest_sha256,prompt_sha256,render_identity,prompt_path,
                input_manifest_path
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                reservation_id,
                node_id,
                node_kind,
                context_id,
                attempt,
                RESERVED_STATUS,
                template_sha256,
                result["input_sha256"],
                result["input_manifest_sha256"],
                result["prompt_sha256"],
                identity_bytes,
                prompt_rel,
                input_manifest_rel,
            ),
        )
        db.commit()
    return {
        "reservation_id": reservation_id,
        "sequence": sequence,
        "node_id": node_id,
        "context_id": context_id,
        "attempt": attempt,
        "prompt_bytes": result["prompt_bytes"],
        "prompt_sha256": result["prompt_sha256"],
        "input_manifest_sha256": result["input_manifest_sha256"],
        "input_sha256": result["input_sha256"],
    }


def _pending_settlement_intent(
    root: Path, binding: dict[str, Any], row: sqlite3.Row
) -> dict[str, Any] | None:
    directory_relative = Path(row["prompt_path"]).parent
    intent_path = _safe(root, str(directory_relative / "settlement-intent.json"))
    if not intent_path.exists():
        return None
    if not intent_path.is_file():
        raise ValueError("retained settlement intent is not a file")
    intent_bytes = intent_path.read_bytes()
    try:
        intent = json.loads(intent_bytes.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("retained settlement intent is not canonical JSON") from exc
    _object(intent, _SETTLEMENT_INTENT_KEYS, "settlement intent")
    if _canonical(intent) != intent_bytes:
        raise ValueError("retained settlement intent is not canonical JSON")
    if (
        intent["schema_version"] != SCHEMA_VERSION
        or intent["kind"] != SETTLEMENT_INTENT_KIND
        or intent["reservation_id"] != row["reservation_id"]
        or intent["status"] not in TERMINAL_STATUSES
    ):
        raise ValueError("retained settlement intent differs from the pending reservation")
    receipt_sha256 = _token(
        intent["receipt_sha256"], _SHA256, "settlement intent receipt_sha256"
    )
    artifact_sha256 = intent["artifact_sha256"]
    if artifact_sha256 is not None:
        _token(artifact_sha256, _SHA256, "settlement intent artifact_sha256")
    if intent["status"] == "eligible" and artifact_sha256 is None:
        raise ValueError("eligible settlement intent requires an artifact identity")
    _, intent_receipt = _intent_payloads(intent)
    if intent["status"] == "eligible":
        _validate_eligible_receipt(binding, row, intent_receipt)

    artifact_path = _safe(root, str(directory_relative / "artifact.bin"))
    if artifact_path.exists():
        if not artifact_path.is_file() or artifact_sha256 is None:
            raise ValueError("retained artifact bytes differ from the settlement intent")
        if _sha(artifact_path.read_bytes()) != artifact_sha256:
            raise ValueError("retained artifact bytes differ from the settlement intent")
    receipt_path = _safe(root, str(directory_relative / "receipt.json"))
    if receipt_path.exists():
        if not receipt_path.is_file():
            raise ValueError("retained receipt bytes differ from the settlement intent")
        receipt_bytes = receipt_path.read_bytes()
        if _sha(receipt_bytes) != receipt_sha256:
            raise ValueError("retained receipt bytes differ from the settlement intent")
        if intent["status"] == "eligible":
            try:
                receipt = json.loads(receipt_bytes.decode("ascii"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("retained eligible receipt is not canonical JSON") from exc
            if _canonical(receipt) != receipt_bytes:
                raise ValueError("retained eligible receipt is not canonical JSON")
            _validate_eligible_receipt(binding, row, receipt)
    return intent


def recover_pending_attempt(root: Path) -> dict[str, Any] | None:
    """Recover the one durable reservation after its return value may have been lost.

    This read-only operation never reserves or dispatches work. A recovered prompt has uncertain
    delivery: the operator must inspect the provider/context receipt and then settle or retire the
    original reservation before opening a fresh context. The prompt must not be blindly resent.
    """
    root = Path(root).resolve()
    with _connect(root, read_only=True) as db:
        binding = _load_binding(root, db)
        programme = db.execute(
            "SELECT sealed_history_sha256 FROM programme WHERE singleton=1"
        ).fetchone()
        rows = db.execute(
            "SELECT * FROM attempts WHERE status=? ORDER BY sequence", (RESERVED_STATUS,)
        ).fetchall()
        if programme is None:
            raise ValueError("operator journal is not initialized")
        if programme["sealed_history_sha256"] is not None:
            if rows:
                raise ValueError("sealed journal contains a pending attempt")
            return None
        if not rows:
            return None
        if len(rows) != 1:
            raise ValueError("operator journal contains multiple pending attempts")
        row = rows[0]

        prompt = _safe(root, row["prompt_path"]).read_bytes()
        input_manifest_bytes = _safe(root, row["input_manifest_path"]).read_bytes()
        for name, data in (
            ("prompt_sha256", prompt),
            ("input_manifest_sha256", input_manifest_bytes),
        ):
            digest = _token(row[name], _SHA256, f"pending {name}")
            if _sha(data) != digest:
                retained = "prompt" if name == "prompt_sha256" else "input-manifest"
                raise ValueError(f"retained pending {retained} bytes changed")
        _token(row["template_sha256"], _SHA256, "pending template_sha256")
        _token(row["input_sha256"], _SHA256, "pending input_sha256")

        try:
            input_manifest = json.loads(input_manifest_bytes.decode("ascii"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("retained pending input manifest is not canonical JSON") from exc
        if _canonical(input_manifest) != input_manifest_bytes:
            raise ValueError("retained pending input manifest is not canonical JSON")
        if (
            input_manifest.get("schema_version") != SCHEMA_VERSION
            or input_manifest.get("kind") != INPUT_MANIFEST_KIND
        ):
            raise ValueError("retained pending input manifest has an unsupported schema")
        expected_identity = {
            "accession_number": binding["accession_number"],
            "role": binding["role_contract"]["role"],
            "node_id": row["node_id"],
            "node_kind": row["node_kind"],
            "role_contract_sha256": binding["role_contract_sha256"],
            "reservation_id": row["reservation_id"],
            "input_sha256": row["input_sha256"],
        }
        if any(input_manifest.get(name) != value for name, value in expected_identity.items()):
            raise ValueError("retained pending input manifest differs from the frozen reservation")
        template = input_manifest.get("template")
        if type(template) is not dict or template.get("sha256") != row["template_sha256"]:
            raise ValueError("retained pending input manifest differs from the frozen reservation")
        if row["node_kind"] == "leaf":
            leaf = input_manifest.get("leaf")
            if (
                type(leaf) is not dict
                or leaf.get("manifest_sha256") != binding["unit_manifest_sha256"]
            ):
                raise ValueError("retained pending leaf manifest differs from the frozen source")

        try:
            render_identity = json.loads(bytes(row["render_identity"]).decode("ascii"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("stored render identity is invalid") from exc
        if _canonical(render_identity) != bytes(row["render_identity"]):
            raise ValueError("stored render identity is not canonical JSON")
        manifest_identity = (
            {"unit_id": input_manifest.get("leaf", {}).get("unit_id")}
            if row["node_kind"] == "leaf"
            else {"children": input_manifest.get("children")}
        )
        if render_identity != manifest_identity:
            raise ValueError("stored render identity differs from the pending input manifest")
        intent = _pending_settlement_intent(root, binding, row)
        settlement_artifact, settlement_receipt = _intent_payloads(intent) if intent else (None, None)
        return {
            "reservation_id": row["reservation_id"],
            "sequence": row["sequence"],
            "node_id": row["node_id"],
            "node_kind": row["node_kind"],
            "context_id": row["context_id"],
            "attempt": row["attempt"],
            "template_sha256": row["template_sha256"],
            "render_identity": render_identity,
            "prompt_bytes": prompt,
            "prompt_sha256": row["prompt_sha256"],
            "input_manifest_sha256": row["input_manifest_sha256"],
            "input_sha256": row["input_sha256"],
            "delivery_uncertain": True,
            "redispatch_permitted": False,
            "settlement_recovery_required": intent is not None,
            "settlement_intent": intent,
            "settlement_artifact_bytes": settlement_artifact,
            "settlement_receipt": settlement_receipt,
        }


def settle_attempt(
    root: Path,
    *,
    reservation_id: str,
    status: str,
    artifact_bytes: bytes | None,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    """Settle exactly one reserved row and retain its receipt and optional output without overwrite."""
    root = Path(root).resolve()
    _token(reservation_id, re.compile(r"[0-9a-f]{32}"), "reservation_id")
    if type(status) is not str or status not in TERMINAL_STATUSES:
        raise ValueError(f"status must be one of: {', '.join(TERMINAL_STATUSES)}")
    if artifact_bytes is not None and type(artifact_bytes) is not bytes:
        raise ValueError("artifact_bytes must be bytes or null")
    if status == "eligible" and artifact_bytes is None:
        raise ValueError("eligible settlement requires artifact bytes")
    if type(receipt) is not dict or any(type(key) is not str for key in receipt):
        raise ValueError("receipt must be an object with string keys")
    receipt_bytes = _canonical(receipt)
    with _connect(root) as db:
        db.execute("BEGIN IMMEDIATE")
        binding = _load_binding(root, db)
        _require_open(db)
        _require_no_uncommitted_seal(root)
        row = db.execute(
            "SELECT * FROM attempts WHERE reservation_id=?", (reservation_id,)
        ).fetchone()
        if row is None or row["status"] != RESERVED_STATUS:
            raise ValueError("reservation is missing or already settled")
        if status == "eligible":
            _validate_eligible_receipt(binding, row, receipt)
        directory_rel = str(Path(row["prompt_path"]).parent)
        artifact_sha256 = _sha(artifact_bytes) if artifact_bytes is not None else None
        receipt_sha256 = _sha(receipt_bytes)
        intent = _settlement_intent(
            reservation_id=reservation_id,
            status=status,
            artifact_sha256=artifact_sha256,
            receipt_sha256=receipt_sha256,
            artifact_bytes=artifact_bytes,
            receipt=receipt,
        )
        # One atomic record retains disposition AND payloads before publishing their projections.
        # After a crash recovery needs no caller memory and cannot reinterpret adverse bytes.
        _durable_exact(
            _safe(root, f"{directory_rel}/settlement-intent.json"), _canonical(intent)
        )
        receipt_rel = f"{directory_rel}/receipt.json"
        artifact_rel = f"{directory_rel}/artifact.bin" if artifact_bytes is not None else None
        if artifact_rel is not None:
            _durable_exact(_safe(root, artifact_rel), artifact_bytes)
        _durable_exact(_safe(root, receipt_rel), receipt_bytes)
        changed = db.execute(
            """
            UPDATE attempts
               SET status=?, artifact_path=?, artifact_sha256=?, receipt_path=?, receipt_sha256=?
             WHERE reservation_id=? AND status=?
            """,
            (
                status,
                artifact_rel,
                artifact_sha256,
                receipt_rel,
                receipt_sha256,
                reservation_id,
                RESERVED_STATUS,
            ),
        ).rowcount
        if changed != 1:
            raise ValueError("reservation settlement race")
        db.commit()
        return {
            "reservation_id": reservation_id,
            "sequence": row["sequence"],
            "node_id": row["node_id"],
            "context_id": row["context_id"],
            "attempt": row["attempt"],
            "status": status,
            "artifact_sha256": artifact_sha256,
            "receipt_sha256": receipt_sha256,
        }


def _attempt_snapshot(row: sqlite3.Row) -> dict[str, Any]:
    try:
        render_identity = json.loads(bytes(row["render_identity"]).decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("stored render identity is invalid") from exc
    snapshot = {
        "sequence": row["sequence"],
        "reservation_id": row["reservation_id"],
        "node_id": row["node_id"],
        "node_kind": row["node_kind"],
        "context_id": row["context_id"],
        "attempt": row["attempt"],
        "status": row["status"],
        "template_sha256": row["template_sha256"],
        "input_sha256": row["input_sha256"],
        "input_manifest_sha256": row["input_manifest_sha256"],
        "prompt_sha256": row["prompt_sha256"],
        "render_identity": render_identity,
        "prompt_path": row["prompt_path"],
        "input_manifest_path": row["input_manifest_path"],
        "artifact_path": row["artifact_path"],
        "artifact_sha256": row["artifact_sha256"],
        "receipt_path": row["receipt_path"],
        "receipt_sha256": row["receipt_sha256"],
    }
    _object(snapshot, _ATTEMPT_KEYS, "history attempt")
    return snapshot


def seal_history(root: Path) -> dict[str, str]:
    """Seal the complete ordered terminal history; pending work and later mutation are forbidden."""
    root = Path(root).resolve()
    with _connect(root) as db:
        db.execute("BEGIN IMMEDIATE")
        binding = _load_binding(root, db)
        _require_open(db)
        rows = db.execute("SELECT * FROM attempts ORDER BY sequence").fetchall()
        if not rows:
            raise ValueError("cannot seal an empty attempt history")
        if any(row["status"] == RESERVED_STATUS for row in rows):
            raise ValueError("pending attempt blocks sealing")
        if any(
            row["status"] not in TERMINAL_STATUSES
            or row["receipt_path"] is None
            or row["receipt_sha256"] is None
            for row in rows
        ):
            raise ValueError("every attempt must be terminal with a retained receipt")
        history = {
            "schema_version": SCHEMA_VERSION,
            "kind": HISTORY_KIND,
            "programme_id": binding["programme_id"],
            "accession_number": binding["accession_number"],
            "role_contract_sha256": binding["role_contract_sha256"],
            "unit_manifest_sha256": binding["unit_manifest_sha256"],
            "attempts": [_attempt_snapshot(row) for row in rows],
            "limitations": list(LIMITATIONS),
            **{flag: False for flag in ATTESTATION_FLAGS},
        }
        history_bytes = _canonical(history)
        history_path = root / "history.json"
        _durable_exact(history_path, history_bytes)
        history_sha256 = _sha(history_bytes)
        db.execute(
            "UPDATE programme SET sealed_history_path=?,sealed_history_sha256=? WHERE singleton=1",
            (history_path.name, history_sha256),
        )
        db.commit()
    return {"history_path": str(history_path), "history_sha256": history_sha256}


def _load_history(path: Path, expected_sha256: str) -> tuple[dict[str, Any], bytes]:
    _token(expected_sha256, _SHA256, "expected_history_sha256")
    raw = path.read_bytes()
    if _sha(raw) != expected_sha256:
        raise ValueError("sealed history differs from the external expected hash")
    try:
        history = json.loads(raw.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("sealed history is not canonical JSON") from exc
    _object(history, _HISTORY_KEYS, "sealed history")
    if _canonical(history) != raw:
        raise ValueError("sealed history is not canonical JSON")
    if history["schema_version"] != SCHEMA_VERSION or history["kind"] != HISTORY_KIND:
        raise ValueError("unsupported sealed history")
    if any(history[flag] is not False for flag in ATTESTATION_FLAGS):
        raise ValueError("sealed history cannot attest review or admission")
    if history["limitations"] != list(LIMITATIONS):
        raise ValueError("sealed history limitations changed")
    if type(history["attempts"]) is not list or not history["attempts"]:
        raise ValueError("sealed history needs terminal attempts")
    return history, raw


def _verify_attempt_files(root: Path, attempt: dict[str, Any]) -> tuple[bytes, bytes, bytes | None, bytes]:
    _object(attempt, _ATTEMPT_KEYS, "history attempt")
    for name in (
        "template_sha256", "input_sha256", "input_manifest_sha256", "prompt_sha256", "receipt_sha256"
    ):
        _token(attempt[name], _SHA256, f"attempt {name}")
    prompt = _safe(root, attempt["prompt_path"]).read_bytes()
    input_manifest = _safe(root, attempt["input_manifest_path"]).read_bytes()
    receipt = _safe(root, attempt["receipt_path"]).read_bytes()
    if _sha(prompt) != attempt["prompt_sha256"]:
        raise ValueError("retained prompt bytes changed")
    if _sha(input_manifest) != attempt["input_manifest_sha256"]:
        raise ValueError("retained input-manifest bytes changed")
    if _sha(receipt) != attempt["receipt_sha256"]:
        raise ValueError("retained receipt bytes changed")
    artifact = None
    if attempt["artifact_path"] is not None:
        _token(attempt["artifact_sha256"], _SHA256, "attempt artifact_sha256")
        artifact = _safe(root, attempt["artifact_path"]).read_bytes()
        if _sha(artifact) != attempt["artifact_sha256"]:
            raise ValueError("retained artifact bytes changed")
    elif attempt["artifact_sha256"] is not None:
        raise ValueError("artifact identity exists without retained bytes")
    intent_path = _safe(
        root, str(Path(attempt["prompt_path"]).parent / "settlement-intent.json")
    )
    intent_bytes = intent_path.read_bytes()
    try:
        intent = json.loads(intent_bytes.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("retained settlement intent is not canonical JSON") from exc
    _object(intent, _SETTLEMENT_INTENT_KEYS, "settlement intent")
    if _canonical(intent) != intent_bytes or intent != _settlement_intent(
        reservation_id=attempt["reservation_id"],
        status=attempt["status"],
        artifact_sha256=attempt["artifact_sha256"],
        receipt_sha256=attempt["receipt_sha256"],
        artifact_bytes=artifact,
        receipt=json.loads(receipt.decode("ascii")),
    ):
        raise ValueError("retained settlement intent differs from sealed attempt history")
    return prompt, input_manifest, artifact, receipt


def validate_execution_binding(
    history_path: Path,
    *,
    expected_history_sha256: str,
    graph: dict[str, Any],
    graph_validation_inputs: dict[str, Any],
) -> dict[str, Any]:
    """Bind the external sealed journal, exact rendered prompts and schema-1 review graph."""
    history_path = Path(history_path).resolve()
    history, history_bytes = _load_history(history_path, expected_history_sha256)
    root = history_path.parent
    _object(graph_validation_inputs, _GRAPH_INPUT_KEYS, "graph_validation_inputs")
    with _connect(root, read_only=True) as db:
        binding = _load_binding(root, db)
        programme = db.execute(
            "SELECT sealed_history_path,sealed_history_sha256 FROM programme WHERE singleton=1"
        ).fetchone()
        if (
            programme is None
            or programme["sealed_history_path"] != history_path.name
            or programme["sealed_history_sha256"] != expected_history_sha256
        ):
            raise ValueError("journal database does not bind the expected sealed history")
    if (
        history["programme_id"] != binding["programme_id"]
        or history["accession_number"] != binding["accession_number"]
        or history["role_contract_sha256"] != binding["role_contract_sha256"]
        or history["unit_manifest_sha256"] != binding["unit_manifest_sha256"]
    ):
        raise ValueError("sealed history differs from the frozen journal binding")
    if _canonical(graph_validation_inputs["role_contract"]) != _canonical(binding["role_contract"]):
        raise ValueError("graph validation uses a different frozen role contract")
    frozen_manifest, frozen_expected, frozen_packets = _read_frozen_source(root, binding)
    if (
        graph_validation_inputs["accession_number"] != binding["accession_number"]
        or _canonical(graph_validation_inputs["unit_manifest"]) != _canonical(frozen_manifest)
        or _canonical(graph_validation_inputs["expected_packets"]) != _canonical(frozen_expected)
        or graph_validation_inputs["packet_bytes"] != frozen_packets
    ):
        raise ValueError("graph validation uses different frozen source inputs")
    source = _validated_source(root, binding)

    graph_result = validate_review_graph(graph, **graph_validation_inputs)
    attempts = history["attempts"]
    registry_projection = []
    prior_by_node: dict[str, dict[str, Any]] = {}
    eligible_before: dict[str, dict[str, Any]] = {}
    contexts: set[str] = set()
    attempts_by_context: dict[str, dict[str, Any]] = {}
    artifacts = graph_validation_inputs["artifacts"]
    for sequence, attempt in enumerate(attempts, start=1):
        _object(attempt, _ATTEMPT_KEYS, "history attempt")
        if type(attempt["sequence"]) is not int or attempt["sequence"] != sequence:
            raise ValueError("sealed attempt sequence is not consecutive from 1")
        _token(attempt["reservation_id"], re.compile(r"[0-9a-f]{32}"), "reservation_id")
        node_id = _token(attempt["node_id"], _LABEL, "attempt node_id")
        context_id = validate_source_context_id(attempt["context_id"], "attempt context_id")
        if context_id in contexts:
            raise ValueError("sealed history reuses a context_id")
        contexts.add(context_id)
        if attempt["node_kind"] not in NODE_KINDS or attempt["status"] not in TERMINAL_STATUSES:
            raise ValueError("sealed attempt has an invalid kind or non-terminal status")
        previous = prior_by_node.get(node_id)
        expected_attempt = 1 if previous is None else previous["attempt"] + 1
        if type(attempt["attempt"]) is not int or attempt["attempt"] != expected_attempt:
            raise ValueError(f"node {node_id} attempts are not consecutive from 1")
        if previous is not None:
            if previous["status"] == "eligible":
                raise ValueError("sealed history redraws an eligible node")
            if (
                previous["node_kind"] != attempt["node_kind"]
                or previous["template_sha256"] != attempt["template_sha256"]
                or previous["input_sha256"] != attempt["input_sha256"]
                or previous["render_identity"] != attempt["render_identity"]
                or previous["context_id"] == context_id
            ):
                raise ValueError("sealed retry changed node input scope or reused context")
        prior_by_node[node_id] = attempt
        attempts_by_context[context_id] = attempt
        prompt, input_manifest, artifact, receipt_bytes = _verify_attempt_files(root, attempt)
        if attempt["status"] == "eligible":
            try:
                eligible_receipt = json.loads(receipt_bytes.decode("ascii"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("eligible receipt is not canonical JSON") from exc
            if _canonical(eligible_receipt) != receipt_bytes:
                raise ValueError("eligible receipt is not canonical JSON")
            _validate_eligible_receipt(binding, attempt, eligible_receipt)
        template = artifacts.get(attempt["template_sha256"])
        if type(template) is not bytes:
            raise ValueError("graph artifacts omit a journal template")
        if attempt["node_kind"] == "leaf":
            identity = _object(attempt["render_identity"], frozenset({"unit_id"}), "leaf render identity")
            render_inputs = {
                "template": template,
                "unit_id": identity["unit_id"],
            }
        else:
            identity = _object(
                attempt["render_identity"], frozenset({"children"}), "parent render identity"
            )
            children = identity["children"]
            for child in children:
                if type(child) is not dict:
                    raise ValueError("parent render identity has an invalid child")
                prior_child = eligible_before.get(child.get("node_id"))
                if (
                    prior_child is None
                    or prior_child["artifact_sha256"] != child.get("artifact_sha256")
                ):
                    raise ValueError(
                        "parent attempt was not preceded by each terminal eligible journal child"
                    )
            child_artifacts = {
                child["artifact_sha256"]: artifacts.get(child["artifact_sha256"])
                for child in children
                if type(child) is dict and "artifact_sha256" in child
            }
            if any(type(data) is not bytes for data in child_artifacts.values()):
                raise ValueError("graph artifacts omit a journal child artifact")
            render_inputs = {
                "template": template,
                "children": children,
                "child_artifacts": child_artifacts,
            }
        rerendered, identity_check, _template = _render(
            binding,
            node_id=node_id,
            node_kind=attempt["node_kind"],
            reservation_id=attempt["reservation_id"],
            render_inputs=render_inputs,
            source=source if attempt["node_kind"] == "leaf" else None,
        )
        if identity_check != attempt["render_identity"]:
            raise ValueError("retained render identity is not canonical")
        if (
            rerendered["prompt_bytes"] != prompt
            or rerendered["input_manifest_bytes"] != input_manifest
            or rerendered["prompt_sha256"] != attempt["prompt_sha256"]
            or rerendered["input_manifest_sha256"] != attempt["input_manifest_sha256"]
            or rerendered["input_sha256"] != attempt["input_sha256"]
        ):
            raise ValueError("retained prompt was not constructed from the exact frozen inputs")
        if attempt["status"] == "eligible" and artifact is None:
            raise ValueError("eligible attempt lacks retained artifact bytes")
        if attempt["status"] == "eligible":
            eligible_before[node_id] = attempt
        registry_projection.append(
            {
                "context_id": context_id,
                "node_id": node_id,
                "attempt": attempt["attempt"],
                "status": attempt["status"],
            }
        )
    if graph.get("context_registry") != registry_projection:
        raise ValueError("graph context registry omits, renumbers or changes sealed attempt history")

    for node in graph.get("nodes", []):
        attempt = attempts_by_context.get(node.get("context_id"))
        if attempt is None or attempt["status"] != "eligible":
            raise ValueError("graph node does not name a terminal eligible journal attempt")
        receipt_bytes = _safe(root, attempt["receipt_path"]).read_bytes()
        artifact_bytes = _safe(root, attempt["artifact_path"]).read_bytes()
        if (
            node.get("node_id") != attempt["node_id"]
            or node.get("kind") != attempt["node_kind"]
            or node.get("artifact_sha256") != attempt["artifact_sha256"]
            or node.get("receipt", {}).get("role_contract_sha256") != history["role_contract_sha256"]
            or node.get("receipt", {}).get("template_sha256") != attempt["template_sha256"]
            or node.get("receipt", {}).get("input_sha256") != attempt["input_sha256"]
            or node.get("receipt", {}).get("rendered_prompt_sha256") != attempt["prompt_sha256"]
            or _canonical(node.get("receipt")) != receipt_bytes
            or artifacts.get(attempt["artifact_sha256"]) != artifact_bytes
            or artifacts.get(attempt["prompt_sha256"]) != _safe(root, attempt["prompt_path"]).read_bytes()
        ):
            raise ValueError("graph node differs from its terminal eligible journal attempt")

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": VALIDATION_KIND,
        "graph_sha256": graph_result["graph_sha256"],
        "history_sha256": _sha(history_bytes),
        "accession_number": history["accession_number"],
        "role": binding["role_contract"]["role"],
        "role_contract_sha256": history["role_contract_sha256"],
        "unit_manifest_sha256": history["unit_manifest_sha256"],
        "source_context_closure": [attempt["context_id"] for attempt in attempts],
        "ineligible_context_ids": [
            attempt["context_id"] for attempt in attempts if attempt["status"] != "eligible"
        ],
        "exact_prompt_construction_verified": True,
        "complete_operator_history_verified": True,
        **{flag: False for flag in ATTESTATION_FLAGS},
        "limitations": list(LIMITATIONS),
    }
