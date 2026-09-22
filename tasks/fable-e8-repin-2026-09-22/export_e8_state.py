"""Export the live E8 guard and stage state out of an ephemeral judging container.

The E8 guard is the sole persistent 601-call counter, but Claude Code web containers are not
persistent: the image that ran E3 on 21–22 September had been replaced by the time the next
session started. If a container is recycled between two E8 slots, the counter would be orphaned.
This tool copies everything a resumed session needs to prove ledger/guard continuity into a
directory the session can commit, and it never modifies the bundle.

Exported, with relative paths and a SHA-256 inventory:

  e8/guard/{config.json, state.json, TEMPLATE.json, initialization.json,
            template-configuration.json, sha256.txt}          (the sealed shim is NOT copied)
  stages/e8/**                                               (index, ledgers, manifests, env,
                                                              STOP/failed/pending, slot outputs)
  receipts/**                                                (attestations, readbacks, restore
                                                              receipts written by the operator)

Restore is governed by README.md's sole-guard recovery policy. ``attest()`` checks internal
ledger continuity; it cannot distinguish a consistent stale checkpoint or fork. This copier
takes no lock and hashes the source after copying: keep the source quiescent throughout export,
verify the destination inventory, and establish latest-checkpoint provenance and source
retirement externally. A failed-stop export is evidence, not permission to resume. This tool
only exports.

Usage:

  python3 tasks/fable-e8-repin-2026-09-22/export_e8_state.py \
      --bundle /home/user/fable-judging/fable-resume-corrected-2026-09-20 \
      --receipts /home/user/fable-judging/receipts \
      --out tasks/review-evidence/e8-fable-state-<UTC stamp>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

GUARD_FILES = ('config.json', 'state.json', 'TEMPLATE.json', 'initialization.json',
               'template-configuration.json', 'sha256.txt')
# The two receipt classes README.md's recovery policy requires before a source may be retired:
# the operator's accounting attestation (schema pinned by the add-on) and a live guard readback.
ATTESTATION_SCHEMA = 'fable-e8-accounting-attestation-v1'
READBACK_KEYS = frozenset({'observed_at_utc', 'guard_dir'})


ATTESTATION_KEYS = frozenset({
    'schema', 'operator', 'observed_at_utc', 'prior_count', 'prior_evidence_sha256',
    'founder_statement_sha256', 'original_manifest_sha256', 'e3_supplement_manifest_sha256',
    'guard_state_path', 'no_untracked_e8_or_probe_calls', 'sole_persistent_guard',
    'exclusive_e8_dispatch_during_continuation'})
ATTESTATION_AFFIRMATIVES = ('no_untracked_e8_or_probe_calls', 'sole_persistent_guard',
                            'exclusive_e8_dispatch_during_continuation')
PRIOR_COUNT = 287
# The sealed evidence an attestation must be bound to: the same constants tools/e8_resume.py
# pins (prior-evidence, founder statement, original immutable manifest) plus this package's
# regenerated supplement manifest (build-summary.json: repin_supplement_manifest_sha256).
SEALED_HASHES = {
    'prior_evidence_sha256': 'ef5ef4dda0ac71dbc3480381f2d9febe3c2f09ffc4c0ce391c5814769a62f26c',
    'founder_statement_sha256': '67527fd115135ae78c7e339423f7c798d53e78bb878d820ac77262e45d36ec8c',
    'original_manifest_sha256': '0fe5cb9e45c1fca76d2d9d71b0a13f58958ea7242efe34ae2a9f64544402d2c3',
    'e3_supplement_manifest_sha256': '1ef772b3157106bcf9bee52675f89bdf0cf643f0457eb405b6ce28e5fe950f6f',
}


def utc_timestamp(value: object) -> bool:
    """True for a parseable ISO-8601 timestamp carrying an explicit UTC offset."""
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0)


def valid_attestation(value: dict, guard: Path) -> bool:
    """The add-on's attestation shape and bindings, minus freshness (an export follows a run)."""
    return (set(value) == ATTESTATION_KEYS
            and value.get('schema') == ATTESTATION_SCHEMA
            and isinstance(value.get('operator'), str) and bool(value['operator'].strip())
            and utc_timestamp(value.get('observed_at_utc'))
            and type(value.get('prior_count')) is int and value['prior_count'] == PRIOR_COUNT
            and all(value.get(k) is True for k in ATTESTATION_AFFIRMATIVES)
            and all(value.get(k) == expected for k, expected in SEALED_HASHES.items())
            and value.get('guard_state_path') == str(guard / 'state.json'))


def guard_observation(guard: Path) -> dict:
    """The live guard values a readback must agree with (the readback.json shape the operator writes)."""
    state = json.loads((guard / 'state.json').read_text())
    config = json.loads((guard / 'config.json').read_text())
    return {
        'config_enabled': config.get('enabled'),
        'state_accounting_reconciled': state.get('accounting_reconciled'),
        'state_real_cli_invocations': state.get('real_cli_invocations'),
        'state_stop_reason': state.get('stop_reason'),
        'state_active_owners': len(state.get('active', {}) or {}),
        'state_completed_calls': len(state.get('completed', []) or []),
        'initialization_json_present': (guard / 'initialization.json').is_file(),
        'template_configuration_json_present': (guard / 'template-configuration.json').is_file(),
    }


def valid_readback(value: dict, guard: Path, observation: dict) -> bool:
    """A readback of THIS guard in ITS CURRENT state: path, UTC observation and every live value.

    A pre-initialization readback (count 0, nothing initialized) therefore stops qualifying the
    moment the guard is initialized; the operator must take a fresh readback after the run.
    """
    if not (READBACK_KEYS <= set(value) and value.get('guard_dir') == str(guard)
            and utc_timestamp(value.get('observed_at_utc'))):
        return False
    recorded_active = value.get('state_active', value.get('state_active_owners'))
    recorded_active = len(recorded_active) if isinstance(recorded_active, (dict, list)) else recorded_active
    recorded_completed = value.get('state_completed', value.get('state_completed_calls'))
    recorded_completed = len(recorded_completed) if isinstance(recorded_completed, list) else recorded_completed
    recorded = dict(value, state_active_owners=recorded_active, state_completed_calls=recorded_completed)
    return all(recorded.get(key) == expected for key, expected in observation.items())


def receipt_classes(receipts: Path, guard: Path) -> dict:
    """Which recovery-critical receipt classes the directory holds, validated against this guard."""
    found = {'attestation': False, 'readback': False}
    observation = guard_observation(guard)
    for path in sorted(receipts.rglob('*.json')):
        try:
            value = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(value, dict):
            continue
        if valid_attestation(value, guard):
            found['attestation'] = True
        if valid_readback(value, guard, observation):
            found['readback'] = True
    return found


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def copy_tree(src: Path, dst_root: Path, rel_root: Path, inventory: dict) -> None:
    for path in sorted(src.rglob('*')):
        if not path.is_file():
            continue
        rel = rel_root / path.relative_to(src)
        target = dst_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        inventory[str(rel)] = {'sha256': sha(path), 'bytes': path.stat().st_size}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--bundle', required=True, type=Path)
    parser.add_argument('--receipts', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    bundle = args.bundle.resolve(strict=True)
    out = args.out.resolve()
    if out.exists():
        raise SystemExit(f'REFUSE: output directory exists: {out}')
    inventory: dict = {}
    guard = bundle / 'e8/guard'
    # Refuse an incomplete checkpoint rather than exporting one an operator could retire the
    # source against. A guard that has been initialized (or even had its template configured)
    # must export all six recovery-critical files; a pristine template has only four.
    state_path = guard / 'state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    initialized = ((guard / 'initialization.json').exists() or (guard / 'template-configuration.json').exists()
                   or state.get('accounting_reconciled') is True)
    required = set(GUARD_FILES) if initialized else set(GUARD_FILES) - {'initialization.json', 'template-configuration.json'}
    missing = sorted(name for name in required if not (guard / name).is_file())
    if missing:
        raise SystemExit(f'REFUSE: guard export would be incomplete; missing {missing} in {guard}')
    if not (bundle / 'stages/e8/index.json').is_file():
        raise SystemExit(f'REFUSE: stages/e8 tree is missing or has no index.json under {bundle}')
    # A supplied receipts path must exist, and an initialized checkpoint must carry the operator's
    # attestations and readbacks: the recovery policy requires them before the source is retired.
    receipts = args.receipts.resolve() if args.receipts else None
    if receipts is not None and not receipts.is_dir():
        raise SystemExit(f'REFUSE: --receipts path is not a directory: {receipts}')
    if initialized:
        if receipts is None:
            raise SystemExit('REFUSE: an initialized guard export requires --receipts')
        missing_classes = [name for name, present in receipt_classes(receipts, guard).items() if not present]
        if missing_classes:
            raise SystemExit(f'REFUSE: receipts directory lacks valid recovery-critical records {missing_classes}: '
                             f'an operator attestation (full {ATTESTATION_SCHEMA!r} shape, named operator, '
                             f'prior_count {PRIOR_COUNT}, all three affirmatives true, guard_state_path bound to '
                             f'{guard / "state.json"}) and a guard readback bound to {guard} with a UTC observation '
                             f'whose recorded counter, reconciliation, latch, owners, completed calls, config and '
                             f'initialization/template records equal the live guard (take a fresh readback after the run)')
    for name in GUARD_FILES:
        path = guard / name
        if path.exists():
            rel = Path('e8/guard') / name
            (out / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, out / rel)
            inventory[str(rel)] = {'sha256': sha(path), 'bytes': path.stat().st_size}
    copy_tree(bundle / 'stages/e8', out, Path('stages/e8'), inventory)
    if receipts is not None:
        copy_tree(receipts, out, Path('receipts'), inventory)
    summary = {
        'exported_at_utc': datetime.now(timezone.utc).isoformat(),
        'bundle': str(bundle),
        'guard_real_cli_invocations': state.get('real_cli_invocations'),
        'guard_accounting_reconciled': state.get('accounting_reconciled'),
        'guard_stop_reason': state.get('stop_reason'),
        'guard_active_owners': len(state.get('active', {}) or {}),
        'guard_completed_calls': len(state.get('completed', []) or []),
        'files': len(inventory),
    }
    (out / 'sha256-inventory.json').write_text(json.dumps(inventory, indent=2, sort_keys=True) + '\n')
    (out / 'export-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
