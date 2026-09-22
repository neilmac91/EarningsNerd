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
from datetime import datetime, timezone
from pathlib import Path

GUARD_FILES = ('config.json', 'state.json', 'TEMPLATE.json', 'initialization.json',
               'template-configuration.json', 'sha256.txt')


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
    if initialized and (receipts is None or not any(p.is_file() for p in receipts.rglob('*'))):
        raise SystemExit('REFUSE: an initialized guard export requires --receipts pointing at a non-empty '
                         'receipts directory (attestation, readbacks, restore receipts)')
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
