"""Restore the Fable E8 judging environment in a fresh Claude Code web container, offline.

One script for every step that precedes the guard readback, so a new session does not have to
reassemble the procedure from prose. It performs, in order, refusing on any mismatch:

  0. Before anything is written: resolve all nine kit attachments in the uploads directory, check
     each against the launch kit's hash table (pinned below; a CI gate keeps the two equal) and
     the transport manifest's schema, and record each one's upload name, size and SHA-256. Then
     read ``claude --version`` and ``claude auth status`` (no model call): a CLI drift, the 22
     September failure mode, refuses before any state exists.
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
  7. Write the receipt ``receipts/restore-YYYY-MM-DDTHHMMSS.json`` (from ``finished_at_utc``),
     including the frozen commit that ``git rev-parse HEAD`` reports in the worktree.

Nothing here initializes the guard, writes an attestation, or runs the judge. Until guard setup,
a re-run re-verifies every completed step and skips it. After ``guard_setup.py`` has rewritten
``e8/guard/config.json`` and ``state.json``, which are members of the sealed bundle archive, a
re-run refuses at the bundle extraction without writing anything: do not re-run it after setup.
On a refusal the partial log is printed to stdout before exiting, and no receipt file is written.
All expected hashes are pinned below; the per-part payload hashes come from the transport
manifest, whose own hash is pinned, and the reassembled bundle must match its pinned hash.

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
TRANSPORT_MANIFEST = 'transport-manifest.json'
# The launch kit's attachment table (tasks/fable-e8-launch-kit.md). The gate
# backend/tests/unit/test_e8_launch_kit_matches_allow_rules.py keeps the two equal.
KIT_ATTACHMENTS = {
    'fable-upload-01-of-05.zip': '9bde2e064132a9fe246aae0aff38453e7412d39f274dba65edd158508448ef60',
    'fable-upload-02-of-05.zip': '3e33f6a25c3114dda1f166dead2aaf6ae3a6493b9911712895bf2c54c66371ea',
    'fable-upload-03-of-05.zip': 'b5cfee264ad5faf926f27125efb58581af6f69f33bd387ceb6ae30396d5a5f44',
    'fable-upload-04-of-05.zip': '80ce0eacb07db479a079057fd289e2d9244a051192df2df77863e70c02847622',
    'fable-upload-05-of-05.zip': 'eb390b28130f5ec7c55ff740d1c08b2fb14930922b50dd43c906487cc59f45ab',
    'fable-reconciliation-2026-09-22.zip': SUPPLEMENT_ZIP_SHA256,
    'fable-e8-continuation-2026-09-22.zip': ADDON_ZIP_SHA256,
    'fable-judging-e3-complete-2026-09-22.zip': DELIVERABLE_ZIP_SHA256,
    TRANSPORT_MANIFEST: 'e30ed42bc8e610a6cda7357e9911632f7fb07409f0b45689e25bf688d30a80ba',
}
MANIFEST_KEYS = ('original_sha256', 'original_bytes', 'parts')
PART_KEYS = ('attachment', 'attachment_sha256', 'member', 'payload_bytes', 'payload_sha256')
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
    """The one upload named exactly ``name`` or carrying any id prefix ending in ``-<name>``."""
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


def resolve_attachments(uploads: Path, log: dict) -> tuple[dict[str, Path], dict]:
    """Find and check all nine attachments and the manifest schema before anything is written."""
    paths = {name: find_upload(uploads, name) for name in KIT_ATTACHMENTS}
    log['uploads_dir'] = str(uploads)
    log['attachments'] = {name: {'upload': path.name, 'bytes': path.stat().st_size, 'sha256': sha(path)}
                          for name, path in paths.items()}
    wrong = sorted(name for name, seen in log['attachments'].items() if seen['sha256'] != KIT_ATTACHMENTS[name])
    if wrong:
        raise Refuse(f'attachments differ from the launch kit table: {wrong}')
    try:
        manifest = json.loads(paths[TRANSPORT_MANIFEST].read_text())
    except ValueError as exc:
        raise Refuse(f'{TRANSPORT_MANIFEST} is not JSON') from exc
    absent = [key for key in MANIFEST_KEYS if key not in manifest]
    parts = manifest.get('parts')
    if absent or not isinstance(parts, list) or not parts:
        raise Refuse(f'{TRANSPORT_MANIFEST} lacks {absent or ["a non-empty parts list"]}')
    for number, part in enumerate(parts, start=1):
        absent = [key for key in PART_KEYS if not isinstance(part, dict) or key not in part]
        if absent:
            raise Refuse(f'{TRANSPORT_MANIFEST} part {number} lacks {absent}')
    named = [part['attachment'] for part in parts]
    uploads_named = sorted(name for name in KIT_ATTACHMENTS if name.startswith('fable-upload-'))
    if sorted(named) != uploads_named:
        raise Refuse(f'{TRANSPORT_MANIFEST} parts {named} are not the five kit uploads {uploads_named}')
    stale = [part['attachment'] for part in parts if part['attachment_sha256'] != KIT_ATTACHMENTS[part['attachment']]]
    if stale:
        raise Refuse(f'{TRANSPORT_MANIFEST} part hashes disagree with the launch kit table: {stale}')
    return paths, manifest


def step_assemble(paths: dict[str, Path], manifest: dict, log: dict) -> Path:
    out = ASSEMBLY / 'fable-resume-corrected-2026-09-20.zip'
    if out.exists():
        if out.stat().st_size != BUNDLE_ZIP_BYTES or sha(out) != BUNDLE_ZIP_SHA256:
            raise Refuse(f'existing {out} does not match the pinned bundle archive')
        log['assemble'] = 'already present and verified'
        return out
    if manifest['original_sha256'] != BUNDLE_ZIP_SHA256 or manifest['original_bytes'] != BUNDLE_ZIP_BYTES:
        raise Refuse('transport manifest does not describe the pinned bundle archive')
    ASSEMBLY.mkdir(parents=True, exist_ok=True)
    partial = out.with_suffix('.partial')
    seen: set[str] = set()
    with partial.open('wb') as sink:
        for part in manifest['parts']:
            path = paths[part['attachment']]
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
                      'shim_mode': format(shim.stat().st_mode & 0o777, '04o'), 'immutable_ok': len(manifest)}


def frozen_head() -> str:
    head = subprocess.run(['git', '-C', str(FROZEN_REPO), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    if head != FROZEN_COMMIT:
        raise Refuse(f'frozen worktree is at {head}, not {FROZEN_COMMIT}')
    return head


def step_worktree(repo_root: Path, log: dict) -> None:
    if FROZEN_REPO.exists():
        frozen_head()
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
    log['frozen_commit'] = frozen_head()
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


def restore(uploads: Path, args: argparse.Namespace, log: dict) -> None:
    paths, manifest = resolve_attachments(uploads, log)  # read-only
    step_cli(log)  # read-only; a CLI drift refuses before any state exists
    bundle_zip = step_assemble(paths, manifest, log)
    step_extract(bundle_zip, BUNDLE_ZIP_SHA256, JUDGING, BUNDLE.name, log, 'extract_bundle')
    step_extract(paths['fable-reconciliation-2026-09-22.zip'], SUPPLEMENT_ZIP_SHA256, JUDGING, SUPPLEMENT.name, log, 'extract_supplement')
    step_extract(paths['fable-e8-continuation-2026-09-22.zip'], ADDON_ZIP_SHA256, JUDGING, ADDON.name, log, 'extract_addon')
    step_extract(paths['fable-judging-e3-complete-2026-09-22.zip'], DELIVERABLE_ZIP_SHA256, DELIVERABLE, None, log, 'extract_deliverable')
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--uploads', required=True, type=Path, help="this session's uploads directory")
    parser.add_argument('--repo-root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--skip-venv', action='store_true')
    args = parser.parse_args()
    uploads = args.uploads.resolve(strict=True)
    log: dict = {'started_at_utc': datetime.now(timezone.utc).isoformat()}
    try:
        restore(uploads, args, log)
    except BaseException as exc:
        # The tool result is the evidence of a refused restore: print what was verified first.
        log['refused'] = str(exc.code) if isinstance(exc, SystemExit) else f'{type(exc).__name__}: {exc}'
        log['refused_at_utc'] = datetime.now(timezone.utc).isoformat()
        print(json.dumps(log, indent=2))
        raise
    log['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    receipt = RECEIPTS / f'restore-{log["finished_at_utc"][:19].replace(":", "")}.json'
    receipt.write_text(json.dumps(log, indent=2) + '\n')
    print(json.dumps(log, indent=2))
    print(f'receipt: {receipt}')


if __name__ == '__main__':
    main()
