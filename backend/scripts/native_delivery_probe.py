#!/usr/bin/env python3
"""Bounded first engineering probe for the native-delivery adapter (route claude_code_cli_print).

One synthetic opaque-token packet, one reserved leaf, one CLI dispatch, no retry. This is a
transport/schema-discovery probe with an output-fidelity check; it is not a source-role dispatch and
borrows no E7 slot. Its journal is synthetic, and with its ledger it is retained evidence. The dispatch
roots must sit outside any Claude project context, so outside the home directory (its ``~/.claude`` makes
it one), and the releasing machine uses a temporary directory, which does not last: macOS clears
``/private/tmp`` at restart, and its daily maintenance removes entries untouched for three days (the
2026-10-01 probe's ledger is gone). So ``run`` copies both into the manifest's ``retain_root`` and
validates the copy.

Usage (from ``backend/``, on the releasing machine, outside iCloud; the parent directory of the
manifest's ``journal_root``/``delivery_root`` must already exist, e.g. ``mkdir -p /private/tmp/...``, and
``retain_root`` must be an existing durable directory outside temporary directories, cloud-synced home
directories and git work trees, e.g. ``mkdir -p ~/en-probe-ledgers``; ``probe_id`` is a label such as
``engineering-probe-native-delivery-4``):

    python scripts/native_delivery_probe.py plan --manifest <probe-manifest.json>
    python scripts/native_delivery_probe.py run  --manifest <probe-manifest.json>

``plan`` runs the same preflight the adapter will run (pinned CLI ``--version`` only, never a model
call; environment allow-list; home settings/memory observation; delivery-root isolation and hard
links; the rendered prompt against ``max_stdin_bytes``), prints the exact argv, limits and hashes,
and creates no journal or ledger. ``run`` repeats that preflight and performs the single dispatch
only when it is clean; every refusal happens before ``initialize_journal`` so nothing is on disk.
After the dispatch ``run`` copies the journal and the ledger to ``<retain_root>/<probe_id>/`` and
validates the copy with ``validate_delivery_binding``.

Exit codes: 0 complete with exact fidelity; 2 terminal non-complete outcome (settled, retained);
3 preflight refusal or CLI drift (nothing written; see the manifest's ``drift_plan``); 4 unknown
delivery (reservation left pending: inspect the retained ledger, then settle or retire it through the
retained journal and validate it there; when the copy did not validate, copy the original roots by hand
first and settle in that copy; never re-run against the same roots; 4 takes precedence over 6, and the
run still prints whether the copy validated); 5 complete but the reply is not the expected tokens
(settled eligible in the synthetic journal, fidelity recorded); 6 the retained copy did not validate (the
original stays at the dispatch roots: copy it by hand before it is cleared); 1 manifest/usage error or an
unexpected crash.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals import acceptance_source_review_delivery as delivery  # noqa: E402
from evals.acceptance_source_review_execution import initialize_journal, reserve_attempt  # noqa: E402
from evals.acceptance_source_review_prompts import render_leaf_prompt, validate_prompt_source  # noqa: E402
from evals.acceptance_source_units import build_unit_manifest  # noqa: E402


PROBE_KIND = "e7_native_delivery_probe_result"
EXIT_USAGE, EXIT_INEXACT_OR_TERMINAL, EXIT_REFUSED, EXIT_UNKNOWN, EXIT_INEXACT, EXIT_RETAIN = 1, 2, 3, 4, 5, 6
_MANIFEST_KEYS = frozenset({
    "probe_id", "cli_path", "expected_cli_version", "model", "accession_number", "programme_id",
    "journal_root", "delivery_root", "retain_root", "limits", "passthrough_env", "fixture", "drift_plan", "cost_accounting",
})
_OPTIONAL_KEYS = frozenset({"version_confound"})
_FIXTURE_KEYS = frozenset({"seed", "token_count", "echo_tokens"})
# A label: it names the retained copy's directory under the retain root and the context id's prefix.
_PROBE_ID = re.compile(r"engineering-probe-[a-z0-9]+(?:-[a-z0-9]+)*")
# Home directories a sync client uploads: iCloud Drive, iCloud Desktop & Documents, and the File Provider clients
# (Dropbox, OneDrive, Google Drive) under ~/Library/CloudStorage. Raw streams stay on the machine.
_SYNCED_HOME_DIRS = (("Library", "Mobile Documents"), ("Library", "CloudStorage"), ("Documents",), ("Desktop",))
# Directories whose contents do not last (macOS clears /private/tmp at restart and, by default, entries untouched for
# three days; the per-user /var/folders is cleared too).
_TEMP_ROOTS = ("/tmp", "/private/tmp", "/var/tmp", "/private/var/tmp", "/var/folders", "/private/var/folders")


def _temp_roots() -> tuple[Path, ...]:
    """This machine's temporary directories, resolved (on macOS /tmp is /private/tmp)."""
    return tuple(Path(name).resolve() for name in (*_TEMP_ROOTS, tempfile.gettempdir()) if Path(name).exists())


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
    if type(manifest["probe_id"]) is not str or _PROBE_ID.fullmatch(manifest["probe_id"]) is None:
        raise _usage_error("probe_id must be a label such as engineering-probe-native-delivery-4 "
                           "(lowercase letters and digits joined by single hyphens)")
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
            return path, f"{name} must not live under a cloud-synced directory ({synced})"
    if path.exists() or path.is_symlink():
        return path, f"{name} already exists; choose a fresh directory"
    if not path.parent.is_dir():
        return path, f"{name} parent {path.parent} must exist (mkdir -p it first)"
    return path, None


def _under(path: Path, ancestor: Path) -> bool:
    """``path`` (existing, resolved) is ``ancestor`` or lies under it, compared by file identity: a case variant on a
    case-insensitive volume or a macOS firmlink (``/System/Volumes/Data/private/tmp``) names the same directory under
    another string."""
    try:
        mark = ancestor.stat()
    except OSError:  # no such directory on this machine, so nothing lies under it
        return False
    return any(os.path.samestat(candidate.stat(), mark) for candidate in (path, *path.parents))


def _retain_root(value: Any, probe_id: str, *, temp_roots: tuple[Path, ...] | None = None,
                 home: Path | None = None) -> tuple[Path, str | None]:
    """The durable directory the run's journal and ledger are copied into; returns (target, refusal).

    The retain root exists and lies outside every temporary directory, every cloud-synced home directory and every git
    work tree (raw streams stay out of git, as the adapter's own isolation rule keeps the dispatch out of one);
    ``<retain_root>/<probe_id>`` is written once.
    """
    if type(value) is not str or not value or not Path(value).is_absolute():
        return Path("/"), "retain_root must be an absolute path"
    root = Path(value).resolve()
    if not root.is_dir():
        return root, f"retain_root {root} must be an existing directory (mkdir -p it first)"
    for temp in temp_roots if temp_roots is not None else _temp_roots():
        if _under(root, temp):
            return root, f"retain_root must not live under a temporary directory ({temp}); its contents do not last"
    home_dir = home or Path.home()
    for parts in _SYNCED_HOME_DIRS:
        if _under(root, home_dir.joinpath(*parts)):
            return root, f"retain_root must not live under a cloud-synced directory ({home_dir.joinpath(*parts)})"
    for candidate in (root, *root.parents):
        if (candidate / ".git").exists() or (candidate / ".git").is_symlink():
            return root, f"retain_root must not live inside a git work tree ({candidate}): raw streams stay out of git"
    target = root / probe_id
    if target.exists() or target.is_symlink():
        return target, f"{target} already exists; a probe's retained copy is written once"
    return target, None


def _same_tree(source: Path, copy: Path) -> bool:
    """Every file under ``source`` is under ``copy`` with the same bytes, and nothing else is."""
    def files(root: Path) -> list[Path]:
        return sorted(path.relative_to(root) for path in root.rglob("*") if path.is_file())
    listed = files(source)
    return listed == files(copy) and all((source / name).read_bytes() == (copy / name).read_bytes() for name in listed)


def _retain_copy(journal_root: Path, delivery_root: Path, target: Path, *, reservation_id: str) -> dict[str, Any]:
    """Copy the journal and the ledger to ``target``, check the copy byte for byte against them, and validate it;
    a failure is reported, never repaired (``lessons/evals-retain-a-probe-ledger-outside-the-temporary-directory.md``).

    A link is copied as the file it points to, so nothing in the copy points back into the temporary original.
    """
    try:
        target.mkdir(mode=0o700, parents=False)
        shutil.copytree(journal_root, target / "journal", symlinks=False)
        shutil.copytree(delivery_root, target / "delivery", symlinks=False)
        if not (_same_tree(journal_root, target / "journal") and _same_tree(delivery_root, target / "delivery")):
            return {"path": str(target), "valid": False, "error": "the copy differs from the original"}
        check = delivery.validate_delivery_binding(target / "journal", target / "delivery", reservation_id=reservation_id)
    except Exception as exc:  # the reporting boundary: whatever fails here, run still writes and prints its record
        return {"path": str(target), "valid": False, "error": f"{type(exc).__name__}: {exc}"}
    return {"path": str(target), "valid": True,
            **{key: check[key] for key in ("outcome", "journal_status", "classifier_version", "ledger_schema_version")}}


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
    retain_target, refusal = _retain_root(manifest["retain_root"], manifest["probe_id"])
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
        "retain_target": str(retain_target),
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
        "assistant_completion": receipt["assistant_completion"],
        "schema_version": receipt["schema_version"], "classifier_version": receipt["classifier_version"],
        "stream_event_type_counts": receipt["stream"]["event_type_counts"],
        "partial_stream_event_counts": receipt["stream"]["stream_events"]["counts"],
        "provider_delivery_verified": False, "source_role_dispatch": False, "admission_credit": False,
        "engineering_context_identity_for_exclusion_closure": context_id,
    }
    # The dispatch roots sit in a temporary directory; the evidence is the validated copy under the retain root.
    retained = _retain_copy(journal_root, delivery_root, Path(planned["retain_target"]),
                            reservation_id=reservation["reservation_id"])
    result_record["retained_copy"] = retained
    body = json.dumps(result_record, indent=2, sort_keys=True).encode("utf-8")
    (delivery_root / "probe-result.json").write_bytes(body)
    if retained["valid"]:
        (Path(retained["path"]) / "delivery" / "probe-result.json").write_bytes(body)
    print(json.dumps(result_record, indent=2, sort_keys=True))
    if retained["valid"]:
        print(f"Retained copy validated at {retained['path']}: it is the evidence; the dispatch roots are temporary.")
    else:
        print(f"RETAINED COPY DID NOT VALIDATE ({retained['error']}); the original stays at {journal_root} and "
              f"{delivery_root}: copy both by hand before they are cleared.")
    # An unknown delivery outranks a copy that did not validate: the reservation still needs settling, and it is
    # settled in a durable copy, so the settlement does not go when the temporary original is cleared.
    if outcome["outcome"] == "unknown":
        if retained["valid"]:
            print(f"UNKNOWN delivery: reservation left pending. Inspect the ledger under {retained['path']}/delivery, "
                  f"then settle or retire it through the journal at {retained['path']}/journal and validate it there. "
                  "Do not re-run this probe against the same journal.")
        else:
            print(f"UNKNOWN delivery: reservation left pending. First copy {journal_root} and {delivery_root} by hand "
                  "to a durable directory, then settle or retire it in your copy's journal and validate it there. "
                  "Do not re-run this probe against the same journal.")
        return EXIT_UNKNOWN
    if not retained["valid"]:
        return EXIT_RETAIN
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
