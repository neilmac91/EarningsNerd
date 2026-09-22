"""Restore the Fable E8 judging environment in a fresh Claude Code web container, offline.

One idempotent script for every step that precedes the guard readback, so a new session does not
have to reassemble the procedure from prose. It performs, in order, refusing on any mismatch:

  1. Reassemble the five ``fable-upload-NN-of-05.zip`` attachments (transport manifest checked
     per part: outer hash, single member, payload size, payload hash) into the corrected bundle
     ZIP and verify its size and SHA-256.
  2. Extract the bundle, the E3 supplement, the E8 add-on and the E3-complete deliverable to their
     fixed locations, never over an existing directory, never with unsafe member paths.
  3. Verify ``immutable-sha256.json`` (818 sealed files), ``supplement-sha256.json``,
     ``payload-inventory.json``, ``code-sha256.json`` and the deliverable's
     ``records/sha256-inventory-e3.json``.
  4. Overlay the deliverable's ``bundle-stage-records/<stage>/…`` onto ``stages/<stage>/…`` and
     ``readouts-supplement/*`` onto the bundle (the same rules as the reviewed
     ``restore_session_state.py``: never an immutable path, hash each source, refuse a differing
     existing file, copy only what is absent), then restore the frozen guard shim's 0755 mode.
  5. Fetch the frozen commit into a detached worktree and verify the five pinned eval hashes.
  6. Create the judging venv from the frozen ``backend/requirements.txt``.
  7. Record ``claude --version`` and ``claude auth status`` (no model call) and write a readback.

Nothing here initializes the guard, writes an attestation, or runs the judge. Every step is safe
to re-run: completed steps are detected and skipped. All expected hashes are pinned below and
were read from the founder's transport manifest and the 22 September handoff prompt.

Usage (from the repository root, in the judging session):

  python3 tasks/fable-e8-repin-2026-09-22/restore_e8_session.py \
      --uploads /root/.claude/uploads/<session-uploads-dir>

Add ``--skip-venv`` to leave the venv for a later step. Exit status 0 means every step verified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ASSEMBLY = Path('/home/user/fable-assembly')
JUDGING = Path('/home/user/fable-judging')
BUNDLE = JUDGING / 'fable-resume-corrected-2026-09-20'
SUPPLEMENT = JUDGING / 'fable-reconciliation-2026-09-22'
ADDON = JUDGING / 'fable-e8-continuation-2026-09-22'
DELIVERABLE = Path('/home/user/fable-e3-deliverable')
FROZEN_REPO = Path('/home/user/earningsnerd-fable-frozen')
VENV = JUDGING / 'venv'
RECEIPTS = JUDGING / 'receipts'
REAL_CLI = Path('/opt/claude-code/bin/claude')
EXPECTED_CLI_VERSION = '2.1.280 (Claude Code)'  # the re-pin package's exact gate (tools/guard_setup.py, tools/resume.py)
FROZEN_COMMIT = '73cc31162c3dfe7ec497c8c88c43cf397afce4a7'

BUNDLE_ZIP_SHA256 = '38db06d2c3815893f5d48c96b1f2f8bfd0984f45c538026e19d2e034cc9b5256'
BUNDLE_ZIP_BYTES = 123221172
IMMUTABLE_MANIFEST_SHA256 = '0fe5cb9e45c1fca76d2d9d71b0a13f58958ea7242efe34ae2a9f64544402d2c3'
SUPPLEMENT_ZIP_SHA256 = '0ac918a0f38456250b5db634728a3461f6b2f921c1efbd11f599320aa4e5c1bd'
ADDON_ZIP_SHA256 = '5298a21e818c105a2a33f12859813446b1cde635d7bb48f3ce46e4a58f140909'
DELIVERABLE_ZIP_SHA256 = '281095aa83f560ded61961c09479f9b9d917947c21ffac887be338d729019ed6'
SHIM_SHA256 = 'c0ade9e8d278683e8ccdf9546b97e4b65c496a7c55c195885b4bfa1a38d4c138'
PINNED_EVAL_FILES = {
    'judge_report.py': '11a79f1e8288d4f91b6ae0051f31a93d08a113b7541e540f733cee20c8c0e780',
    'judge.py': '7522f977e1f1a6704508c587c525a1d213cd460ff68af229530ec414bc308857',
    'runner.py': '63b010b7968c3f4bdbcfd62114af82dcfcd8c5eb56e892b0c0da77f4943c0029',
    'weekly_readout.py': '8b171455199aacd135acda99ce8641af8b5e8a1cea8fe029276c6e1cd944070d',
    'golden_set.json': 'e1ca0cfcb7d0f9f51eff911586437c503a1945a64763284f48c9cd5524498b6b',
}
EXPECTED_SLOT_DIRS = {'ko-corrected': 70, 'e3-candidate1': 69, 'e3-candidate2': 70}
BILLING_ENV = {'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'CLAUDE_CODE_USE_BEDROCK',
               'CLAUDE_CODE_USE_VERTEX', 'CLAUDE_CODE_USE_FOUNDRY'}


class Refuse(SystemExit):
    def __init__(self, message: str) -> None:
        super().__init__(f'REFUSE: {message}')


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def find_upload(uploads: Path, name: str) -> Path:
    """Uploaded files carry an id prefix; match on the suffix after the last '-'."""
    matches = [p for p in uploads.iterdir() if p.name == name or p.name.endswith('-' + name)]
    if len(matches) != 1:
        raise Refuse(f'expected exactly one upload named {name}, found {[m.name for m in matches]}')
    return matches[0]


def check_zip(path: Path, expected_sha: str) -> zipfile.ZipFile:
    actual = sha(path)
    if actual != expected_sha:
        raise Refuse(f'{path.name} sha256 {actual} != {expected_sha}')
    archive = zipfile.ZipFile(path)
    for name in archive.namelist():
        if name.startswith('/') or '..' in name.split('/'):
            raise Refuse(f'unsafe member {name} in {path.name}')
    if archive.testzip() is not None:
        raise Refuse(f'CRC failure in {path.name}')
    return archive


def step_assemble(uploads: Path, log: dict) -> Path:
    out = ASSEMBLY / 'fable-resume-corrected-2026-09-20.zip'
    if out.exists():
        if out.stat().st_size != BUNDLE_ZIP_BYTES or sha(out) != BUNDLE_ZIP_SHA256:
            raise Refuse(f'existing {out} does not match the pinned bundle archive')
        log['assemble'] = 'already present and verified'
        return out
    manifest = json.loads(find_upload(uploads, 'transport-manifest.json').read_text())
    if manifest['original_sha256'] != BUNDLE_ZIP_SHA256 or manifest['original_bytes'] != BUNDLE_ZIP_BYTES:
        raise Refuse('transport manifest does not describe the pinned bundle archive')
    ASSEMBLY.mkdir(parents=True, exist_ok=True)
    partial = out.with_suffix('.partial')
    seen: set[str] = set()
    with partial.open('wb') as sink:
        for part in manifest['parts']:
            path = find_upload(uploads, part['attachment'])
            if sha(path) != part['attachment_sha256']:
                raise Refuse(f'attachment hash mismatch for {part["attachment"]}')
            with zipfile.ZipFile(path) as archive:
                if archive.namelist() != [part['member']] or part['member'] in seen:
                    raise Refuse(f'unexpected members in {part["attachment"]}: {archive.namelist()}')
                if archive.testzip() is not None:
                    raise Refuse(f'CRC failure in {part["attachment"]}')
                data = archive.read(part['member'])
            if len(data) != part['payload_bytes'] or hashlib.sha256(data).hexdigest() != part['payload_sha256']:
                raise Refuse(f'payload mismatch for {part["member"]}')
            seen.add(part['member'])
            sink.write(data)
    if partial.stat().st_size != BUNDLE_ZIP_BYTES or sha(partial) != BUNDLE_ZIP_SHA256:
        partial.unlink()
        raise Refuse('assembled archive does not match the pinned size/hash')
    partial.rename(out)
    log['assemble'] = f'assembled {len(seen)} parts -> {out}'
    return out


def step_extract(archive_path: Path, expected_sha: str, dest: Path, top: str | None, log: dict, key: str) -> None:
    """Extract a verified archive, or prove an existing extraction is byte-for-byte that archive.

    The archive hash is checked on every run, before any early return, so a stale but
    internally consistent prior extraction can never stand in for the supplied sealed kit.
    """
    archive = check_zip(archive_path, expected_sha)
    members = [i for i in archive.infolist() if not i.is_dir()]
    tops = {n.split('/')[0] for n in archive.namelist()}
    if top and tops != {top}:
        raise Refuse(f'{archive_path.name} top-level entries {sorted(tops)} != {top}')
    target = dest / top if top else dest
    if target.exists():
        differing = []
        for info in members:
            path = dest / info.filename
            if not path.is_file() or hashlib.sha256(archive.read(info)).hexdigest() != sha(path):
                differing.append(info.filename)
                if len(differing) >= 5:
                    break
        if differing:
            raise Refuse(f'existing extraction at {target} differs from {archive_path.name}: {differing}')
        log[key] = f'already extracted at {target}; {len(members)} members re-verified against the archive'
        return
    dest.mkdir(parents=True, exist_ok=True)
    archive.extractall(dest)
    log[key] = f'extracted {len(archive.namelist())} members to {target}'


def verify_manifest(root: Path, manifest_name: str, log: dict, key: str, sizes: bool = False) -> dict:
    manifest = json.loads((root / manifest_name).read_text())
    bad = []
    for rel, value in manifest.items():
        expected = value if isinstance(value, str) else value['sha256']
        path = root / rel
        if not path.exists() or sha(path) != expected:
            bad.append(rel)
        elif sizes and path.stat().st_size != value['bytes']:
            bad.append(rel)
    if bad:
        raise Refuse(f'{manifest_name} under {root}: {len(bad)} mismatches, first {bad[:5]}')
    log[key] = f'{len(manifest)} entries verified'
    return manifest


def step_overlay(log: dict) -> None:
    manifest = json.loads((BUNDLE / 'immutable-sha256.json').read_text())
    if sha(BUNDLE / 'immutable-sha256.json') != IMMUTABLE_MANIFEST_SHA256:
        raise Refuse('immutable manifest hash changed')
    bad = [k for k, v in manifest.items() if sha(BUNDLE / k) != v]
    if bad:
        raise Refuse(f'immutable files differ before overlay: {bad[:5]}')
    inventory = json.loads((DELIVERABLE / 'records/sha256-inventory-e3.json').read_text())
    copied = present = 0
    for arc, meta in inventory.items():
        if arc.startswith('bundle-stage-records/'):
            rel = 'stages/' + arc[len('bundle-stage-records/'):]
        elif arc.startswith('readouts-supplement/'):
            rel = arc
        else:
            continue
        if rel in manifest:
            raise Refuse(f'overlay would touch immutable file {rel}')
        src, dst = DELIVERABLE / arc, BUNDLE / rel
        if sha(src) != meta['sha256']:
            raise Refuse(f'deliverable file changed in transit: {arc}')
        if dst.exists():
            if sha(dst) != meta['sha256']:
                raise Refuse(f'existing bundle file differs from deliverable: {rel}')
            present += 1
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
    shim = BUNDLE / 'e8/guard/claude'
    if sha(shim) != SHIM_SHA256:
        raise Refuse('guard shim content differs from the sealed hash')
    os.chmod(shim, 0o755)
    bad = [k for k, v in manifest.items() if sha(BUNDLE / k) != v]
    if bad:
        raise Refuse(f'immutable files changed by overlay: {bad[:5]}')
    slots = {s: len(list((BUNDLE / 'stages' / s / 'slots').iterdir())) if (BUNDLE / 'stages' / s / 'slots').exists() else 0
             for s in EXPECTED_SLOT_DIRS}
    if slots != EXPECTED_SLOT_DIRS:
        raise Refuse(f'slot directories {slots} != expected {EXPECTED_SLOT_DIRS}')
    log['overlay'] = {'copied': copied, 'already_present': present, 'slot_dirs': slots,
                      'shim_mode': oct(shim.stat().st_mode & 0o777), 'immutable_ok': len(manifest)}


def step_worktree(repo_root: Path, log: dict) -> None:
    if FROZEN_REPO.exists():
        head = subprocess.run(['git', '-C', str(FROZEN_REPO), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
        if head != FROZEN_COMMIT:
            raise Refuse(f'existing frozen worktree is at {head}, not {FROZEN_COMMIT}')
        # The five pinned files import unpinned modules and step_venv trusts requirements.txt,
        # so an existing checkout is accepted only when git reports it clean: no tracked
        # modification and no untracked file (gitignored __pycache__ from the harness is fine).
        dirty = subprocess.run(['git', '-C', str(FROZEN_REPO), 'status', '--porcelain'],
                               capture_output=True, text=True, check=True).stdout.strip()
        if dirty:
            raise Refuse(f'existing frozen worktree is not clean:\n{dirty[:2000]}')
        log['worktree'] = 'already present at the frozen commit and clean'
    else:
        subprocess.run(['git', '-C', str(repo_root), 'fetch', 'origin', FROZEN_COMMIT], check=True)
        subprocess.run(['git', '-C', str(repo_root), 'worktree', 'add', '--detach', str(FROZEN_REPO), FROZEN_COMMIT], check=True)
        log['worktree'] = f'created at {FROZEN_REPO}'
    bad = [n for n, h in PINNED_EVAL_FILES.items() if sha(FROZEN_REPO / 'backend/evals' / n) != h]
    if bad:
        raise Refuse(f'pinned eval files differ: {bad}')
    log['pinned_eval_files'] = f'{len(PINNED_EVAL_FILES)} verified'


def step_venv(log: dict) -> None:
    """Create the venv, or reuse it only if a marker proves its install completed for this requirements file."""
    python = VENV / 'bin/python'
    requirements = FROZEN_REPO / 'backend/requirements.txt'
    marker = VENV / '.requirements-installed.sha256'
    if python.exists() and marker.exists() and marker.read_text().strip() == sha(requirements):
        log['venv'] = 'already present; completion marker matches the frozen requirements'
    else:
        if python.exists():
            log['venv_note'] = 'existing venv had no completion marker; reinstalling requirements'
        else:
            subprocess.run([sys.executable, '-m', 'venv', str(VENV)], check=True)
        subprocess.run([str(VENV / 'bin/pip'), 'install', '--disable-pip-version-check', '-q', '-r',
                        str(requirements)], check=True)
        marker.write_text(sha(requirements) + '\n')  # written only after pip exited 0
        log['venv'] = f'installed into {VENV}'
    log['venv_python'] = subprocess.run([str(python), '--version'], capture_output=True, text=True, check=True).stdout.strip()


def step_cli(log: dict) -> None:
    env = {k: v for k, v in os.environ.items() if k not in BILLING_ENV}
    version = subprocess.run([str(REAL_CLI), '--version'], capture_output=True, text=True, timeout=30, env=env)
    auth = subprocess.run([str(REAL_CLI), 'auth', 'status'], capture_output=True, text=True, timeout=30, env=env)
    log['cli'] = {'path': str(REAL_CLI.resolve()), 'version_stdout': version.stdout.strip(), 'version_exit': version.returncode}
    if version.returncode:
        raise Refuse(f'claude --version exited {version.returncode}')
    if version.stdout.strip() != EXPECTED_CLI_VERSION:
        raise Refuse(f'CLI reports {version.stdout.strip()!r}; this package is pinned to {EXPECTED_CLI_VERSION!r} '
                     '(guard_setup.py and resume.py would refuse it too; a drift is a founder decision, not a restore)')
    try:
        status = json.loads(auth.stdout)
    except ValueError as exc:
        raise Refuse(f'claude auth status did not return JSON (exit {auth.returncode})') from exc
    observed = {k: status.get(k) for k in ('loggedIn', 'authMethod', 'apiProvider')}
    log['cli']['auth'] = observed
    expected = {'loggedIn': True, 'authMethod': 'oauth_token', 'apiProvider': 'firstParty'}
    if auth.returncode or observed != expected:
        raise Refuse(f'CLI auth state {observed} (exit {auth.returncode}) is not the subscription route {expected}')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--uploads', required=True, type=Path, help="this session's uploads directory")
    parser.add_argument('--repo-root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--skip-venv', action='store_true')
    args = parser.parse_args()
    uploads = args.uploads.resolve(strict=True)
    log: dict = {'started_at_utc': datetime.now(timezone.utc).isoformat()}
    bundle_zip = step_assemble(uploads, log)
    step_extract(bundle_zip, BUNDLE_ZIP_SHA256, JUDGING, BUNDLE.name, log, 'extract_bundle')
    step_extract(find_upload(uploads, 'fable-reconciliation-2026-09-22.zip'), SUPPLEMENT_ZIP_SHA256, JUDGING, SUPPLEMENT.name, log, 'extract_supplement')
    step_extract(find_upload(uploads, 'fable-e8-continuation-2026-09-22.zip'), ADDON_ZIP_SHA256, JUDGING, ADDON.name, log, 'extract_addon')
    step_extract(find_upload(uploads, 'fable-judging-e3-complete-2026-09-22.zip'), DELIVERABLE_ZIP_SHA256, DELIVERABLE, None, log, 'extract_deliverable')
    if sha(BUNDLE / 'immutable-sha256.json') != IMMUTABLE_MANIFEST_SHA256:
        raise Refuse('immutable manifest hash mismatch')
    verify_manifest(BUNDLE, 'immutable-sha256.json', log, 'immutable')
    verify_manifest(SUPPLEMENT, 'supplement-sha256.json', log, 'supplement_manifest')
    verify_manifest(SUPPLEMENT, 'payload-inventory.json', log, 'supplement_inventory', sizes=True)
    verify_manifest(ADDON, 'code-sha256.json', log, 'addon_manifest')
    verify_manifest(DELIVERABLE, 'records/sha256-inventory-e3.json', log, 'deliverable_inventory')
    step_overlay(log)
    step_worktree(args.repo_root.resolve(strict=True), log)
    if not args.skip_venv:
        step_venv(log)
    step_cli(log)
    log['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    receipt = RECEIPTS / f'restore-{log["finished_at_utc"][:19].replace(":", "")}.json'
    receipt.write_text(json.dumps(log, indent=2) + '\n')
    print(json.dumps(log, indent=2))
    print(f'receipt: {receipt}')


if __name__ == '__main__':
    main()
