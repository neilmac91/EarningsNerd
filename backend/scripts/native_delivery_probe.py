#!/usr/bin/env python3
"""Bounded first engineering probe for the native-delivery adapter (route claude_code_cli_print).

One synthetic opaque-token packet, one reserved leaf, one CLI dispatch, no retry. This is a
transport/schema-discovery probe with an output-fidelity check; it is not a source-role dispatch,
borrows no E7 slot, and its journal is synthetic and discarded afterwards.

Usage (from ``backend/``, on the releasing machine, outside iCloud; the parent directory of the
manifest's ``journal_root``/``delivery_root`` must already exist, e.g. ``mkdir -p /private/tmp/...``):

    python scripts/native_delivery_probe.py plan --manifest <probe-manifest.json>
    python scripts/native_delivery_probe.py run  --manifest <probe-manifest.json>

``plan`` runs the same preflight the adapter will run (pinned CLI ``--version`` only, never a model
call; environment allow-list; home settings/memory observation; delivery-root isolation and hard
links; the rendered prompt against ``max_stdin_bytes``), prints the exact argv, limits and hashes,
and creates no journal or ledger. ``run`` repeats that preflight and performs the single dispatch
only when it is clean; every refusal happens before ``initialize_journal`` so nothing is on disk.

Exit codes: 0 complete with exact fidelity; 2 terminal non-complete outcome (settled, retained);
3 preflight refusal or CLI drift (nothing written; see the manifest's ``drift_plan``); 4 unknown
delivery (reservation left pending: inspect the ledger, then settle or retire through the journal;
never re-run against the same roots); 5 complete but the reply is not the expected tokens (settled
eligible in the synthetic journal, fidelity recorded); 1 manifest/usage error or an unexpected crash.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals import acceptance_source_review_delivery as delivery  # noqa: E402
from evals.acceptance_source_review_execution import initialize_journal, reserve_attempt  # noqa: E402
from evals.acceptance_source_review_prompts import render_leaf_prompt, validate_prompt_source  # noqa: E402
from evals.acceptance_source_units import build_unit_manifest  # noqa: E402


PROBE_KIND = "e7_native_delivery_probe_result"
EXIT_USAGE, EXIT_INEXACT_OR_TERMINAL, EXIT_REFUSED, EXIT_UNKNOWN, EXIT_INEXACT = 1, 2, 3, 4, 5
_MANIFEST_KEYS = frozenset({
    "probe_id", "cli_path", "expected_cli_version", "model", "accession_number", "programme_id",
    "journal_root", "delivery_root", "limits", "passthrough_env", "fixture", "drift_plan", "cost_accounting",
})
_OPTIONAL_KEYS = frozenset({"version_confound"})
_FIXTURE_KEYS = frozenset({"seed", "token_count", "echo_tokens"})
_SYNCED_HOME_DIRS = (("Library", "Mobile Documents"), ("Documents",), ("Desktop",))


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _usage_error(message: str) -> SystemExit:
    print(f"USAGE ERROR: {message}", file=sys.stderr)
    return SystemExit(EXIT_USAGE)


def _load_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_bytes())
    if type(manifest) is not dict or not _MANIFEST_KEYS <= set(manifest) or set(manifest) - _MANIFEST_KEYS - _OPTIONAL_KEYS:
        raise _usage_error(f"manifest must have exactly {', '.join(sorted(_MANIFEST_KEYS))}"
                           f" (optional: {', '.join(sorted(_OPTIONAL_KEYS))})")
    manifest.setdefault("version_confound", False)
    if type(manifest["version_confound"]) is not bool:
        raise _usage_error("version_confound must be a boolean")
    if type(manifest["fixture"]) is not dict or set(manifest["fixture"]) != _FIXTURE_KEYS:
        raise _usage_error(f"fixture must have exactly: {', '.join(sorted(_FIXTURE_KEYS))}")
    if type(manifest["passthrough_env"]) is not list or any(type(n) is not str for n in manifest["passthrough_env"]):
        raise _usage_error("passthrough_env must be a list of variable names")
    if type(manifest["accession_number"]) is not str or delivery._SYNTHETIC_ACCESSION.fullmatch(manifest["accession_number"]) is None:
        raise _usage_error("probe accession must be synthetic (CIK 0000000000)")
    if not str(manifest["programme_id"]).startswith("engineering-probe-"):
        raise _usage_error("probe programme_id must start with engineering-probe-")
    return manifest


def _local_root(value: Any, name: str) -> tuple[Path, str | None]:
    """A fresh absolute directory on a local volume whose parent exists; returns (path, refusal)."""
    if type(value) is not str or not value or not Path(value).is_absolute():
        return Path("/"), f"{name} must be an absolute path"
    path = Path(value)
    resolved = path.parent.resolve() / path.name if path.parent.exists() else path
    home = Path.home().resolve()
    for parts in _SYNCED_HOME_DIRS:
        synced = home.joinpath(*parts)
        if resolved == synced or synced in resolved.parents:
            return path, f"{name} must not live under an iCloud-synced directory ({synced})"
    if path.exists() or path.is_symlink():
        return path, f"{name} already exists; choose a fresh directory"
    if not path.parent.is_dir():
        return path, f"{name} parent {path.parent} must exist (mkdir -p it first)"
    return path, None


def _fixture(fixture: dict[str, Any]) -> tuple[bytes, bytes, list[str]]:
    """Deterministic opaque-token packet, leaf template and the exact expected reply lines."""
    seed, count, echo = fixture["seed"], fixture["token_count"], fixture["echo_tokens"]
    if type(seed) is not str or type(count) is not int or not 8 <= count <= 4096:
        raise _usage_error("fixture seed must be a string and token_count an int in 8..4096")
    if type(echo) is not list or not echo or any(type(i) is not int or not 1 <= i <= count for i in echo):
        raise _usage_error("fixture echo_tokens must name 1-based token indexes within token_count")
    tokens = {index: hashlib.sha256(f"{seed}:{index}".encode("utf-8")).hexdigest() for index in range(1, count + 1)}
    packet = "<p>Opaque engineering fixture; no financial content.</p>\n" + "".join(
        f"<p>TOKEN-{index:04d}: {digest}</p>\n" for index, digest in tokens.items()
    )
    labels = ", ".join(f"TOKEN-{index:04d}" for index in echo)
    template = (
        "Below is one exact source span of opaque tokens. Reply with exactly the 64-character "
        f"hexadecimal values of {labels}, one per line, in that order, and nothing else.\n"
    )
    return packet.encode("utf-8"), template.encode("utf-8"), [tokens[index] for index in echo]


def _source(accession: str, packet: bytes) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    packets = [{"role": "primary", "sha256": _sha(packet), "byte_length": len(packet)}]
    manifest = build_unit_manifest(
        accession_number=accession, packets=packets, packet_bytes={"primary": packet},
        units=[{"packet_role": "primary", "structural_kind": "markup", "registrant_scope": "registrant",
                "coverage_spans": [{"start": 0, "end": len(packet)}], "context_spans": []}],
    )
    return packets, manifest


def _contract(manifest: dict[str, Any], template: bytes, synthesis_template: bytes, provider_version: str) -> dict[str, Any]:
    return {
        "schema_version": 1, "kind": "e7_offline_source_role_contract", "role": "engineering-probe",
        "node_kinds": {"leaf": {"template_sha256": _sha(template)},
                       "role_synthesis": {"template_sha256": _sha(synthesis_template)}},
        "provider": delivery.ROUTE_PROVIDER, "model": manifest["model"],
        "provider_version": provider_version, "exposure_limit": None,
    }


def plan(manifest: dict[str, Any]) -> dict[str, Any]:
    """Run the adapter's own preflight with no side effects and describe the single planned dispatch."""
    refusals: list[str] = []
    passthrough = tuple(manifest["passthrough_env"])
    limits = manifest["limits"]
    env: dict[str, str] = {}
    env_record: dict[str, Any] = {}
    settings: dict[str, Any] = {}
    try:
        env, env_record = delivery._child_env(dict(os.environ), passthrough)
        settings = delivery._settings_observation(Path(env["HOME"]))
    except (ValueError, AssertionError) as exc:
        refusals.append(f"environment/settings: {exc}")
    journal_root, refusal = _local_root(manifest["journal_root"], "journal_root")
    if refusal:
        refusals.append(refusal)
    delivery_root, refusal = _local_root(manifest["delivery_root"], "delivery_root")
    if refusal:
        refusals.append(refusal)
    elif delivery_root.parent.is_dir():
        try:
            delivery._verify_project_isolation(delivery_root.parent.resolve(), "delivery_root parent")
            delivery._prove_hard_links(delivery_root.parent)
        except ValueError as exc:
            refusals.append(f"delivery_root: {exc}")
    cli: dict[str, Any] = {"path": None, "sha256": None, "version_observed": None}
    executable: Path | None = None
    try:
        executable, cli_sha256 = delivery._cli_identity(manifest["cli_path"])
        cli = {"path": str(executable), "sha256": cli_sha256, "version_observed": None}
        if env:
            version = delivery._observe_version(executable, provider_version=manifest["expected_cli_version"],
                                                env=env, runner=delivery.run_route_process)
            cli["version_observed"] = version["observed"]
    except (ValueError, OSError) as exc:
        refusals.append(f"cli: {exc}")
    drift = any(entry.startswith("cli:") and "drift" in entry for entry in refusals)
    packet, template, expected = _fixture(manifest["fixture"])
    packets, unit_manifest = _source(manifest["accession_number"], packet)
    source = validate_prompt_source(accession_number=manifest["accession_number"], unit_manifest=unit_manifest,
                                    expected_packets=packets, packet_bytes={"primary": packet})
    rendered = render_leaf_prompt(template, accession_number=manifest["accession_number"], role="engineering-probe",
                                  node_id="probe-leaf", role_contract_sha256="0" * 64, source=source,
                                  unit_id=unit_manifest["units"][0]["unit_id"], reservation_id="plan-preview")
    fits = len(rendered["prompt_bytes"]) <= limits.get("max_stdin_bytes", 0)
    if not fits:
        refusals.append(f"rendered prompt {len(rendered['prompt_bytes'])} bytes exceeds max_stdin_bytes")
    argv = list(delivery._argv(executable, manifest["model"], delivery._limits(limits))) if executable else []
    return {
        "probe_id": manifest["probe_id"],
        "route": delivery.ROUTE,
        "model": manifest["model"],
        "expected_cli_version": manifest["expected_cli_version"],
        "version_confound": manifest["version_confound"],
        "cli_measured": cli,
        "drift_detected": drift,
        "preflight_refusals": refusals,
        "preflight_clean": not refusals,
        "environment": env_record,
        "settings_observation": settings,
        "fixture": {"packet_bytes": len(packet), "packet_sha256": _sha(packet), "template_sha256": _sha(template),
                    "rendered_prompt_bytes_excluding_reservation_id_variance": len(rendered["prompt_bytes"]),
                    "fits_max_stdin_bytes": fits, "expected_reply_sha256": _sha(("\n".join(expected) + "\n").encode("utf-8")),
                    "echo_tokens": manifest["fixture"]["echo_tokens"]},
        "limits": limits,
        "planned_argv": argv,
        "route_system_prompt_sha256": _sha(delivery.ROUTE_SYSTEM_PROMPT.encode("utf-8")),
        "dispatches_planned": 1,
        "retries": 0,
        "journal_root": manifest["journal_root"],
        "delivery_root": manifest["delivery_root"],
        "drift_plan": manifest["drift_plan"],
        "cost_accounting": manifest["cost_accounting"],
    }


def run(manifest: dict[str, Any]) -> int:
    planned = plan(manifest)
    print(json.dumps({"plan": planned}, indent=2, sort_keys=True))
    if not planned["preflight_clean"]:
        print("REFUSED before initialize_journal; nothing was written:\n  - " + "\n  - ".join(planned["preflight_refusals"]))
        return EXIT_REFUSED
    journal_root = Path(manifest["journal_root"])
    delivery_root = Path(manifest["delivery_root"])
    packet, template, expected = _fixture(manifest["fixture"])
    synthesis_template = b"Unused by probe 1; required by the role contract shape.\n"
    packets, unit_manifest = _source(manifest["accession_number"], packet)
    observed_version = planned["cli_measured"]["version_observed"]
    contract = _contract(manifest, template, synthesis_template, manifest["expected_cli_version"])
    initialize_journal(
        journal_root, programme_id=manifest["programme_id"], accession_number=manifest["accession_number"],
        role_contract=contract, unit_manifest_sha256=_sha(_canonical(unit_manifest)),
        unit_manifest=unit_manifest, expected_packets=packets, packet_bytes={"primary": packet},
    )
    delivery_root.mkdir(mode=0o700, parents=False)
    context_id = f"{manifest['probe_id']}-ctx-1"
    try:
        reservation = reserve_attempt(
            journal_root, node_id="probe-leaf", node_kind="leaf", context_id=context_id,
            render_inputs={"template": template, "unit_id": unit_manifest["units"][0]["unit_id"]},
        )
        outcome = delivery.deliver_reserved_attempt(
            journal_root, delivery_root, reservation_id=reservation["reservation_id"],
            prompt_bytes=reservation["prompt_bytes"], cli_path=planned["cli_measured"]["path"],
            environment=dict(os.environ), limits=manifest["limits"],
            native_members=[{"label": "synthetic-packet", "bytes": packet, "required": True}],
            passthrough_env=tuple(manifest["passthrough_env"]), engineering_probe=True,
        )
    except ValueError as exc:
        print(f"REFUSED after initialize_journal (no dispatch reached the route): {exc}\n"
              f"Delete {journal_root} and {delivery_root} before another attempt.")
        return EXIT_REFUSED
    receipt = outcome["receipt"]
    output = outcome["settlement_proposal"]["artifact_bytes"] if outcome["settlement_proposal"] else None
    observed_lines = [line.strip() for line in output.decode("utf-8", "replace").strip().splitlines()] if output else []
    fidelity = {"expected_lines": len(expected),
                "matched_lines": sum(1 for a, b in zip(observed_lines, expected) if a == b),
                "exact": observed_lines == expected}
    settled = None
    if outcome["outcome"] != "unknown":
        settled = delivery.settle_delivery(journal_root, delivery_root, reservation_id=reservation["reservation_id"])
    results = receipt["stream"]["results"]
    result_record = {
        "kind": PROBE_KIND, "probe_id": manifest["probe_id"], "outcome": outcome["outcome"],
        "reasons": receipt["reasons"], "delivery_receipt_sha256": outcome["receipt_sha256"],
        "ledger_path": outcome["ledger_path"], "journal_root": str(journal_root),
        "reservation_id": reservation["reservation_id"], "context_id": context_id,
        "settled": settled, "fidelity": fidelity,
        "dispatches_made": 1, "retries": 0,
        "model_call_observed": receipt["stream"]["init"] is not None,
        "cli_version_observed": observed_version, "version_confound": manifest["version_confound"],
        "route_reported_usage": results[0]["usage"] if results else None,
        "route_reported_assistant_usage": receipt["stream"]["usage_reported"],
        "route_reported_total_cost_usd_estimate": results[0]["total_cost_usd"] if results else None,
        "stdin_bytes": receipt["stdin"]["byte_length"], "output_bytes": receipt["output"]["byte_length"],
        "finish_metadata_observed": receipt["finish_metadata_observed"],
        "stream_event_type_counts": receipt["stream"]["event_type_counts"],
        "provider_delivery_verified": False, "source_role_dispatch": False, "admission_credit": False,
        "engineering_context_identity_for_exclusion_closure": context_id,
    }
    (delivery_root / "probe-result.json").write_bytes(json.dumps(result_record, indent=2, sort_keys=True).encode("utf-8"))
    print(json.dumps(result_record, indent=2, sort_keys=True))
    if outcome["outcome"] == "unknown":
        print("UNKNOWN delivery: reservation left pending; inspect the ledger, then settle or retire via the journal. "
              "Do not re-run this probe against the same journal.")
        return EXIT_UNKNOWN
    if outcome["outcome"] != "complete":
        return EXIT_INEXACT_OR_TERMINAL
    return 0 if fidelity["exact"] else EXIT_INEXACT


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("plan", "run"))
    parser.add_argument("--manifest", required=True, type=Path)
    arguments = parser.parse_args(argv)
    manifest = _load_manifest(arguments.manifest)
    if arguments.command == "plan":
        planned = plan(manifest)
        print(json.dumps(planned, indent=2, sort_keys=True))
        return 0 if planned["preflight_clean"] else EXIT_REFUSED
    return run(manifest)


if __name__ == "__main__":
    raise SystemExit(main())
