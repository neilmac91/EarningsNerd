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

Evidence is never withheld. Every stop is exported, including a partial guard setup, a missing
receipt or a STOP: README.md says to export after every stop. Whether the export can serve as a
sole-guard recovery checkpoint is a separate verdict, written to ``export-summary.json`` as
``recovery_eligible`` with every blocker named. The verdict applies the checks the sealed
``guard_setup.validate_guard`` makes before every slot (no latch, no owner, enabled, reconciled,
counter within 287..600 and not below its recorded prior count, config state path and ceiling,
initialization record bound to the config) except the CLI identity check, which needs the real
binary; ``attest()``'s prior count 287 and its accounting continuity (the supplement ledger chains
from 287 to the counter in steps of one or two, and the completed history is 288..counter);
``inspect_e8``'s ledger rules; e8_resume's quota and owner-loss markers; README condition 6's
terminal states (STOP, pending, failed); and the receipts. Only a missing bundle or ``stages/e8/index.json``,
an existing output directory or a ``--receipts`` path that is not a directory refuses outright.

README.md condition 1 requires the copied files to be verified against the inventory and the
unchanged source before the checkpoint is committed. This tool does that itself: each file is
hashed before copying, the copy is re-read and hashed, and the source is hashed again; after
all copies the source trees are listed again and compared with what was copied. Any
disagreement is recorded (``destination_verified``, ``source_unchanged``), the directory is
kept as evidence and the exit status is 1. ``inventory_sha256`` in the summary identifies the
inventory for the handoff receipt. Git cannot track empty directories, so every directory under
``stages/e8``, including an empty ``.pending-*`` owner marker, is listed in the summary.

Restore is governed by README.md's sole-guard recovery policy. ``attest()`` checks internal
ledger continuity; it cannot distinguish a consistent stale checkpoint or fork. This copier
takes no lock: keep the source quiescent throughout export, and establish latest-checkpoint
provenance and source retirement externally. A failed-stop export is evidence, not permission
to resume. This tool only exports.

Usage (the launch kit's step 7 command; the stamp placeholders are defined there):

  python3 tasks/fable-e8-repin-2026-09-22/export_e8_state.py \
      --bundle /home/user/fable-judging/fable-resume-corrected-2026-09-20 \
      --receipts /home/user/fable-judging/receipts \
      --out tasks/review-evidence/e8-fable-state-<post-run stamp>
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
TEMPLATE_RECORD = 'template-configuration.json'
INIT_RECORD = 'initialization.json'
# The guard's lifecycle stages and the files each must carry: a pristine template has four,
# ``guard_setup.py --configure-template`` adds its record, ``--prior-count`` adds the other.
STAGE_FILES = {
    'pristine': ('config.json', 'state.json', 'TEMPLATE.json', 'sha256.txt'),
    'template-configured': ('config.json', 'state.json', 'TEMPLATE.json', 'sha256.txt', TEMPLATE_RECORD),
    'initialized': GUARD_FILES,
}
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
# stages/e8 entries that make a checkpoint terminal (tools/e8_resume.py::inspect_e8).
STOP_FILES = ('STOP.json', 'STOP.supplement.json')
# The supplement ledger e8_resume appends one row to per slot, and the original ledger it refuses.
LEDGER = 'execution-ledger.supplement.jsonl'
ORIGINAL_LEDGER = 'execution-ledger.jsonl'
# The guard's absolute ceiling (tools/guard_setup.py CEILING): a counter at it can admit no call.
CEILING = 601


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


def read_json(path: Path) -> dict:
    """A JSON object from ``path``; empty when the file is absent, unreadable or not an object."""
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def count(value: object, default: dict | list) -> object:
    """A collection by its length; an absent value as its empty default; anything else as is.

    A corrupt ``active`` or ``completed`` (a number or a flag) must not crash the export before
    its summary is written: it is reported as the raw value and blocks recovery instead.
    """
    value = default if value is None else value
    return len(value) if isinstance(value, (dict, list)) else value


def guard_observation(guard: Path) -> dict:
    """The live guard values a readback must agree with (the readback.json shape the operator writes)."""
    state = read_json(guard / 'state.json')
    config = read_json(guard / 'config.json')
    return {
        'config_enabled': config.get('enabled'),
        'state_accounting_reconciled': state.get('accounting_reconciled'),
        'state_real_cli_invocations': state.get('real_cli_invocations'),
        'state_stop_reason': state.get('stop_reason'),
        'state_active_owners': count(state.get('active'), {}),
        'state_completed_calls': count(state.get('completed'), []),
        'initialization_json_present': (guard / INIT_RECORD).is_file(),
        'template_configuration_json_present': (guard / TEMPLATE_RECORD).is_file(),
    }


def _recorded_count(value: object, live_key_absent: bool) -> object:
    """A readback's owners/completed entry as a count: a collection by its length, and null as 0
    only when the live state.json has no such key (pristine and freshly initialized guards have
    no ``active`` key; the launch kit records it as ``{}``), so a real owner is never masked."""
    if isinstance(value, (dict, list)):
        return len(value)
    if value is None and live_key_absent:
        return 0
    return value


def valid_readback(value: dict, guard: Path, observation: dict) -> bool:
    """A readback of THIS guard in ITS CURRENT state: path, UTC observation and every live value.

    A pre-initialization readback (count 0, nothing initialized) therefore stops qualifying the
    moment the guard is initialized; the post-run readback of the launch kit's step 7 is the one
    that must match.
    """
    if not (READBACK_KEYS <= set(value) and value.get('guard_dir') == str(guard)
            and utc_timestamp(value.get('observed_at_utc'))):
        return False
    state = read_json(guard / 'state.json')
    recorded_active = _recorded_count(value.get('state_active', value.get('state_active_owners')),
                                      'active' not in state)
    recorded_completed = _recorded_count(value.get('state_completed', value.get('state_completed_calls')),
                                         'completed' not in state)
    recorded = dict(value, state_active_owners=recorded_active, state_completed_calls=recorded_completed)
    return all(recorded.get(key) == expected for key, expected in observation.items())


def receipt_classes(receipts: Path, guard: Path) -> dict:
    """Which recovery-critical receipt classes the directory holds, validated against this guard."""
    found = {'attestation': False, 'readback': False}
    observation = guard_observation(guard)
    for path in sorted(receipts.rglob('*.json')):
        value = read_json(path)
        if not value:
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


def guard_stage(guard: Path, state: dict) -> str:
    """Where the guard is in its one-time setup, from the records it carries."""
    if (guard / INIT_RECORD).exists() or state.get('accounting_reconciled') is True:
        return 'initialized'
    if (guard / TEMPLATE_RECORD).exists():
        return 'template-configured'
    return 'pristine'


def copy_verified(path: Path, target: Path, rel: Path, inventory: dict, mismatches: list) -> None:
    """Copy one file and prove it: source hash before, copy hash, source hash after, and sizes.

    A file that disappears while it is copied (a finishing slot renames its pending directory)
    is recorded as a mismatch rather than crashing the export; the source re-listing reports it
    as a source change as well.
    """
    try:
        _copy_verified(path, target, rel, inventory, mismatches)
    except FileNotFoundError as exc:
        mismatches.append({'path': str(rel), 'error': f'vanished during export: {exc}'})


def _copy_verified(path: Path, target: Path, rel: Path, inventory: dict, mismatches: list) -> None:
    before = sha(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    copied, after = sha(target), sha(path)
    size, copied_size = path.stat().st_size, target.stat().st_size
    inventory[str(rel)] = {'sha256': copied, 'bytes': copied_size}
    if not before == copied == after or size != copied_size:
        mismatches.append({'path': str(rel), 'source_before': before, 'copy': copied,
                           'source_after': after, 'source_bytes': size, 'copy_bytes': copied_size})


def copy_tree(src: Path, dst_root: Path, rel_root: Path, inventory: dict, mismatches: list) -> None:
    for path in sorted(src.rglob('*')):
        if not path.is_file():
            continue
        rel = rel_root / path.relative_to(src)
        copy_verified(path, dst_root / rel, rel, inventory, mismatches)


def source_listing(guard: Path, stages: Path, receipts: Path | None) -> dict:
    """{inventory path: sha256} for every exportable source file, to compare after copying."""
    files = [(guard / name, Path('e8/guard') / name) for name in GUARD_FILES]
    for src, rel_root in ((stages, Path('stages/e8')), (receipts, Path('receipts'))):
        if src is not None:
            files += [(path, rel_root / path.relative_to(src)) for path in sorted(src.rglob('*'))]
    listing = {}
    for path, rel in files:
        try:
            if path.is_file():
                listing[str(rel)] = sha(path)
        except FileNotFoundError:
            continue  # vanished while listed: absent from this listing, so it counts as a change
    return listing


def terminal_markers(stages: Path) -> dict:
    """What tools/e8_resume.py treats as terminal, listed explicitly because git drops empty directories."""
    pending = sorted(stages.glob('.pending-*'))
    failed = stages / 'failed'
    return {
        'directories': sorted(str(p.relative_to(stages)) for p in stages.rglob('*') if p.is_dir()),
        'pending_markers': [{'name': p.name, 'empty': p.is_dir() and not any(p.iterdir())} for p in pending],
        'stop_files': [name for name in STOP_FILES if (stages / name).exists()],
        'failed_entries': sorted(p.name for p in failed.iterdir()) if failed.is_dir() else [],
    }


def ledger_blockers(stages: Path, state: dict) -> list[str]:
    """The accounting continuity the sealed tools require before any slot: attest() chains the
    supplement ledger from prior count 287 in steps of one or two real calls to the guard counter and
    requires the completed history 288..counter; inspect_e8 requires complete, failure-free,
    unrepeated rows, no original ledger and a judged.json in every slot directory."""
    blockers = []
    if (stages / ORIGINAL_LEDGER).exists():
        blockers.append(f'unexpected original E8 ledger {ORIGINAL_LEDGER}')
    rows: list = []
    if (stages / LEDGER).is_file():
        try:
            rows = [json.loads(line) for line in (stages / LEDGER).read_text().splitlines()]
        except ValueError:
            return blockers + [f'{LEDGER} is not JSON lines']
    if not all(isinstance(row, dict) for row in rows):
        return blockers + [f'{LEDGER} holds a row that is not an object']
    if any(not row.get('complete') or row.get('failure') for row in rows):
        blockers.append(f'{LEDGER} has an unresolved execution')
    slots = [row.get('slot') for row in rows]
    if len(set(slots)) != len(slots):
        blockers.append(f'{LEDGER} repeats a slot')
    count = PRIOR_COUNT
    for row in rows:
        before, after = row.get('guard_before'), row.get('guard_after')
        if not isinstance(before, dict) or not isinstance(after, dict) or before.get('real_cli_invocations') != count:
            blockers.append(f'ledger/guard continuity broken before slot {row.get("slot")!r}')
            break
        new_count = after.get('real_cli_invocations')
        if type(new_count) is not int or new_count - count not in (1, 2) or new_count > CEILING:
            blockers.append(f'ledger/guard delta invalid at slot {row.get("slot")!r}')
            break
        count = new_count
    else:
        if state.get('real_cli_invocations') != count:
            blockers.append(f'guard counter {state.get("real_cli_invocations")!r} differs from the ledger total {count}: '
                            'unaccounted calls since initialization')
        completed = state.get('completed')
        invocations = [x.get('invocation') if isinstance(x, dict) else None for x in completed] if isinstance(completed, list) else None
        if invocations != list(range(PRIOR_COUNT + 1, count + 1)):
            blockers.append(f'guard completion history is not the sequence {PRIOR_COUNT + 1}..{count}')
    slot_dir = stages / 'slots'
    outputs = {p.name for p in slot_dir.iterdir() if p.is_dir()} if slot_dir.is_dir() else set()
    blockers += [f'slot directory without judged.json: {name}' for name in sorted(outputs)
                 if not (slot_dir / name / 'judged.json').is_file()]
    completed_slots = {row.get('slot') for row in rows if row.get('complete')}
    blockers += [f'slot output without a ledger row: {name}' for name in sorted(outputs - completed_slots)]
    blockers += [f'ledger row without a slot output: {name}' for name in sorted(completed_slots - outputs, key=str)]
    return blockers


def recovery_blockers(guard: Path, stages: Path, stage: str, state: dict, classes: dict | None,
                      markers: dict) -> list[str]:
    """Every reason this export cannot serve as a sole-guard recovery checkpoint (README.md)."""
    if stage == 'pristine':
        return ['guard never initialized: nothing to recover; a new session starts from the sealed template']
    blockers = [f'guard file missing for a {stage} guard: {name}'
                for name in STAGE_FILES['initialized'] if not (guard / name).is_file()]
    for name in (TEMPLATE_RECORD, INIT_RECORD):
        status = read_json(guard / name).get('status') if (guard / name).is_file() else None
        if (guard / name).is_file() and status != 'complete':
            blockers.append(f'{name} status is {status!r}, not complete (interrupted setup)')
    if classes is None:
        blockers.append('no --receipts directory: attestation and readback absent')
    else:
        blockers += [f'receipts lack a valid {name} bound to the live guard'
                     for name, present in classes.items() if not present]
    # The idle, initialized, path, ceiling and record checks the sealed guard_setup.validate_guard
    # applies before every slot, and attest()'s prior-count binding. The CLI identity check needs the
    # real binary and is left to the resumed session's own admission.
    config = read_json(guard / 'config.json')
    if not state or not config:
        blockers.append('guard state.json or config.json is missing or not a JSON object')
    if state.get('stop_reason') is not None:
        blockers.append(f'guard stop latch set: {state["stop_reason"]!r}')
    active = state.get('active', {})
    if not isinstance(active, dict) or active:
        blockers.append(f'guard has active or malformed owner records: {active!r}')
    completed = state.get('completed')
    if not isinstance(completed, list):
        blockers.append('guard completed history is not a list')
        completed = []
    flagged = [entry.get('invocation') for entry in completed
               if isinstance(entry, dict) and (entry.get('quota') or entry.get('owner_lost'))]
    if flagged:
        blockers.append(f'guard recorded a quota or owner-loss latch on invocations {flagged}')
    if config.get('enabled') is not True or state.get('accounting_reconciled') is not True:
        blockers.append('guard is not enabled and reconciled (interrupted initialization)')
    used = state.get('real_cli_invocations')
    if type(used) is not int or not PRIOR_COUNT <= used < CEILING:
        blockers.append(f'guard counter {used!r} is outside {PRIOR_COUNT}..{CEILING - 1}: no call can be admitted')
    # guard_setup._state_path and validate_guard's record checks, and attest()'s prior-count binding.
    if config.get('state_path') != str(guard / 'state.json') or type(config.get('ceiling')) is not int or config.get('ceiling') != CEILING:
        blockers.append(f'guard config state_path/ceiling is not {guard / "state.json"} / {CEILING}')
    record = read_json(guard / INIT_RECORD)
    if (guard / INIT_RECORD).is_file():
        if type(record.get('prior_count')) is not int or record.get('prior_count') != PRIOR_COUNT:
            blockers.append(f'initialization.json prior_count {record.get("prior_count")!r} is not the attested {PRIOR_COUNT}')
        if record.get('state_path') != config.get('state_path') or record.get('real_cli') != config.get('real_cli'):
            blockers.append('initialization.json state_path/real_cli differ from config.json')
        if type(used) is int and type(record.get('prior_count')) is int and used < record['prior_count']:
            blockers.append('guard counter fell below its initialization prior_count')
    blockers += [f'STOP present: {name}' for name in markers['stop_files']]
    blockers += [f'pending invocation marker: {m["name"]}' for m in markers['pending_markers']]
    if markers['failed_entries']:
        blockers.append(f'failed invocations: {markers["failed_entries"]}')
    if stage == 'initialized':
        blockers += ledger_blockers(stages, state)
    return blockers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--bundle', required=True, type=Path)
    parser.add_argument('--receipts', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    bundle = args.bundle.resolve(strict=True)
    out = args.out.resolve()
    if out.exists():
        raise SystemExit(f'REFUSE: output directory exists: {out}')
    guard, stages = bundle / 'e8/guard', bundle / 'stages/e8'
    if not (stages / 'index.json').is_file():
        raise SystemExit(f'REFUSE: stages/e8 tree is missing or has no index.json under {bundle}')
    receipts = args.receipts.resolve() if args.receipts else None
    if receipts is not None and not receipts.is_dir():
        raise SystemExit(f'REFUSE: --receipts path is not a directory: {receipts}')
    stage = guard_stage(guard, read_json(guard / 'state.json'))
    missing = [name for name in STAGE_FILES[stage] if not (guard / name).is_file()]

    inventory: dict = {}
    mismatches: list = []
    before = source_listing(guard, stages, receipts)
    for name in GUARD_FILES:
        if (guard / name).is_file():
            rel = Path('e8/guard') / name
            copy_verified(guard / name, out / rel, rel, inventory, mismatches)
    copy_tree(stages, out, Path('stages/e8'), inventory, mismatches)
    if receipts is not None:
        copy_tree(receipts, out, Path('receipts'), inventory, mismatches)
    after = source_listing(guard, stages, receipts)
    source_changes = sorted({*before, *after} - {k for k in before if after.get(k) == before[k]})

    # Guard values come from the exported bytes, so the summary cannot drift from the copy.
    state = read_json(out / 'e8/guard/state.json')
    markers = terminal_markers(stages)
    classes = receipt_classes(receipts, guard) if receipts is not None else None
    blockers = [f'guard file missing for a {stage} guard: {name}' for name in missing]
    blockers += [b for b in recovery_blockers(guard, stages, stage, state, classes, markers) if b not in blockers]
    destination_verified = not mismatches
    source_unchanged = not source_changes
    if not destination_verified:
        blockers.append('copied files differ from their source (see mismatches)')
    if not source_unchanged:
        blockers.append('source changed during export: it was not quiescent (see source_changes)')
    inventory_bytes = (json.dumps(inventory, indent=2, sort_keys=True) + '\n').encode()
    (out / 'sha256-inventory.json').write_bytes(inventory_bytes)
    summary = {
        'exported_at_utc': datetime.now(timezone.utc).isoformat(),
        'bundle': str(bundle),
        'guard_stage': stage,
        'guard_real_cli_invocations': state.get('real_cli_invocations'),
        'guard_accounting_reconciled': state.get('accounting_reconciled'),
        'guard_stop_reason': state.get('stop_reason'),
        'guard_active_owners': count(state.get('active'), {}),
        'guard_completed_calls': count(state.get('completed'), []),
        'files': len(inventory),
        'inventory_sha256': hashlib.sha256(inventory_bytes).hexdigest(),
        'destination_verified': destination_verified,
        'source_unchanged': source_unchanged,
        'mismatches': mismatches,
        'source_changes': source_changes,
        'receipt_classes': classes,
        **markers,
        'recovery_eligible': not blockers,
        'recovery_blockers': blockers,
    }
    (out / 'export-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
    print('export written: commit this directory whatever the verdict below; it is evidence')
    print('recovery checkpoint: ' + ('ELIGIBLE' if not blockers else 'NOT ELIGIBLE: ' + '; '.join(blockers)))
    return 0 if destination_verified and source_unchanged else 1


if __name__ == '__main__':
    raise SystemExit(main())
