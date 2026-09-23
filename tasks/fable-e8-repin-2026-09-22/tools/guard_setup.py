"""Portable, fail-closed setup/admission for the frozen E8 transport shim.

Only ``--version`` may reach the explicit real CLI here. The CLI itself remains
unchanged; its state.with_suffix('.lock') flock is also used by these operations.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

SHIM_SHA256 = 'c0ade9e8d278683e8ccdf9546b97e4b65c496a7c55c195885b4bfa1a38d4c138'
MIN_PRIOR_COUNT = 287
CEILING = 601
BILLING_ENV = {'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'CLAUDE_CODE_USE_BEDROCK',
               'CLAUDE_CODE_USE_VERTEX', 'CLAUDE_CODE_USE_FOUNDRY'}


class GuardError(RuntimeError):
    """Guard not admissible; caller must stop before invoking a judge."""


def _read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise GuardError(f'Cannot read {path.name}: {exc}') from exc
    if not isinstance(value, dict):
        raise GuardError(f'{path.name} must be an object')
    return value


def _root(guard_dir: Path) -> Path:
    root = Path(guard_dir).resolve(strict=True)
    if not root.is_dir():
        raise GuardError('guard_dir is not a directory')
    shim = root / 'claude'
    if not shim.is_file() or hashlib.sha256(shim.read_bytes()).hexdigest() != SHIM_SHA256:
        raise GuardError('Frozen shim hash mismatch')
    if not os.access(shim, os.X_OK):
        raise GuardError('Frozen shim is not executable')
    return root


@contextmanager
def _locked(root: Path):
    # Exactly the shim's lock protocol: the chosen shared state is local state.json.
    path = (root / 'state.json').with_suffix('.lock')
    with path.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _atomic(path: Path, value: dict) -> None:
    fd, name = tempfile.mkstemp(prefix='.setup-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _state_path(root: Path, cfg: dict) -> Path:
    value = cfg.get('state_path')
    path = root / 'state.json'
    if not isinstance(value, str) or value != str(path) or path.resolve(strict=True) != path:
        raise GuardError('config.state_path must equal the absolute resolved guard_dir/state.json')
    if type(cfg.get('ceiling')) is not int or cfg['ceiling'] != CEILING:
        raise GuardError('Absolute ceiling must remain 601')
    return path


def _real_cli(value: str, root: Path) -> str:
    if not isinstance(value, str):
        raise GuardError('real_cli must be an explicit resolved path')
    try:
        path = Path(value).resolve(strict=True)
    except OSError as exc:
        raise GuardError('Real CLI does not exist') from exc
    if str(path) != value or not path.is_file() or not os.access(path, os.X_OK) or path == root / 'claude':
        raise GuardError('Real CLI must be an existing, executable, explicit resolved path')
    try:
        proc = subprocess.run([str(path), '--version'], stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=10,
                              env={k: v for k, v in os.environ.items() if k not in BILLING_ENV})
    except (OSError, subprocess.SubprocessError) as exc:
        raise GuardError('Version-only CLI check failed') from exc
    if proc.returncode or not re.fullmatch(r'2\.1\.280(?: \(Claude Code\))?\s*', proc.stdout) or proc.stderr.strip():
        raise GuardError('Real CLI must report exactly 2.1.280 (Claude Code)')
    return str(path)


def _idle(state: dict) -> None:
    if state.get('stop_reason') is not None:
        raise GuardError('Durable stop latch is set or malformed')
    if not isinstance(state.get('active', {}), dict) or state.get('active'):
        raise GuardError('Active owner or malformed active records; do not initialize/admit')
    if not isinstance(state.get('completed'), list):
        raise GuardError('Completed history must be a list')


def _pristine(cfg: dict, state: dict, root: Path) -> None:
    _idle(state)
    if (cfg.get('enabled') is not False or state.get('accounting_reconciled') is not False
            or type(state.get('real_cli_invocations')) is not int
            or state['real_cli_invocations'] != 0 or state['completed']):
        raise GuardError('Setup requires a pristine disabled, unreconciled, zero-count state')
    if (root / 'initialization.json').exists():
        raise GuardError('Initialization was already attempted; never reset or retry it')
    if type(cfg.get('ceiling')) is not int or cfg['ceiling'] != CEILING:
        raise GuardError('Absolute ceiling must remain 601')


def _finished_template(root: Path) -> None:
    record = root / 'template-configuration.json'
    if record.exists() and _read(record).get('status') != 'complete':
        raise GuardError('Template configuration interrupted; do not retry/reset')


def validate_guard(guard_dir: Path) -> tuple[dict, dict]:
    """Validate an idle guard; return locked config/state snapshots or raise.

    This is preflight, not a reservation. The unchanged shim performs atomic
    admission and increments the same shared counter immediately before its CLI.
    """
    root = _root(guard_dir)
    with _locked(root):
        cfg = _read(root / 'config.json')
        state = _read(_state_path(root, cfg))
        _idle(state)
        _finished_template(root)
        record = root / 'initialization.json'
        if record.exists():
            rec = _read(record)
            if (rec.get('status') != 'complete' or rec.get('state_path') != cfg['state_path']
                    or rec.get('real_cli') != cfg.get('real_cli')
                    or type(rec.get('prior_count')) is not int
                    or not MIN_PRIOR_COUNT <= rec['prior_count'] < CEILING):
                raise GuardError('Initialization record is incomplete or mismatched')
        used = state.get('real_cli_invocations')
        if (cfg.get('enabled') is not True or state.get('accounting_reconciled') is not True
                or type(used) is not int or not MIN_PRIOR_COUNT <= used < CEILING):
            raise GuardError('Disabled/unreconciled guard or counter outside 287..600')
        if record.exists() and used < rec['prior_count']:
            raise GuardError('Counter fell below attested initialization count')
        _real_cli(cfg.get('real_cli'), root)
        return cfg, state


def configure_template(guard_dir: Path, real_cli: str | Path) -> tuple[dict, dict]:
    """Bind a never-initialized relocated template, without enabling it.

    TEMPLATE.json must declare never_initialized:true and the exact pristine
    state_sha256. A differing existing original ledger is never forked.
    """
    root = _root(guard_dir)
    with _locked(root):
        cfg = _read(root / 'config.json')
        path = root / 'state.json'
        if path.resolve(strict=True) != path:
            raise GuardError('Template state must be the local resolved state.json')
        state = _read(path)
        _pristine(cfg, state, root)
        marker = _read(root / 'TEMPLATE.json')
        if (marker.get('never_initialized') is not True
                or marker.get('state_sha256') != hashlib.sha256(path.read_bytes()).hexdigest()):
            raise GuardError('Pristine template marker/hash missing or mismatched')
        receipt = root / 'template-configuration.json'
        if receipt.exists():
            raise GuardError('Template configuration already attempted; do not repeat')
        old = cfg.get('state_path')
        if not isinstance(old, str) or not Path(old).is_absolute():
            raise GuardError('Template prior state_path must be absolute')
        if old != str(path) and Path(old).exists():
            raise GuardError('Original ledger exists; refuse to fork it into a relocated template')
        real = _real_cli(str(real_cli), root)
        new = dict(cfg, real_cli=real, state_path=str(path))
        rec = {'status': 'in_progress', 'old_config': cfg, 'new_config': new,
               'state_sha256': marker['state_sha256'], 'at': datetime.now(timezone.utc).isoformat()}
        _atomic(receipt, rec)
        _atomic(root / 'config.json', new)
        _atomic(receipt, dict(rec, status='complete'))
        return new, state


def initialize(guard_dir: Path, real_cli: str | Path, prior_count: int) -> tuple[dict, dict]:
    """Attest prior actual invocations once, under the shim's exclusive lock."""
    if type(prior_count) is not int or not MIN_PRIOR_COUNT <= prior_count < CEILING:
        raise GuardError('Prior count must be an actual reconciled integer in 287..600')
    root = _root(guard_dir)
    with _locked(root):
        cfg = _read(root / 'config.json')
        path = _state_path(root, cfg)
        state = _read(path)
        _pristine(cfg, state, root)
        _finished_template(root)
        real = _real_cli(str(real_cli), root)
        new_cfg = dict(cfg, real_cli=real, enabled=True)
        new_state = dict(state, accounting_reconciled=True, real_cli_invocations=prior_count)
        record = root / 'initialization.json'
        rec = {'status': 'in_progress', 'prior_count': prior_count, 'state_path': str(path),
               'real_cli': real, 'shim_sha256': SHIM_SHA256,
               'at': datetime.now(timezone.utc).isoformat(), 'old_config': cfg, 'old_state': state}
        _atomic(record, rec)  # Interrupted initialization is permanently refused, not reset.
        _atomic(path, new_state)
        # Record complete before enabling; any partial earlier write leaves config disabled.
        _atomic(record, dict(rec, status='complete'))
        _atomic(root / 'config.json', new_cfg)
        return new_cfg, new_state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--guard-dir', required=True, type=Path)
    parser.add_argument('--real-cli', required=True)
    parser.add_argument('--prior-count', type=int)
    parser.add_argument('--configure-template', action='store_true')
    args = parser.parse_args()
    if args.configure_template:
        if args.prior_count is not None:
            parser.error('--configure-template cannot initialize a prior count')
        fn_args = (args.guard_dir, args.real_cli)
        fn = configure_template
    else:
        if args.prior_count is None:
            parser.error('initialization requires --prior-count')
        fn_args = (args.guard_dir, args.real_cli, args.prior_count)
        fn = initialize
    try:
        cfg, state = fn(*fn_args)
    except (GuardError, OSError) as exc:
        parser.exit(2, f'Guard setup refused: {exc}\n')
    print(json.dumps({'config': cfg, 'state': state}, sort_keys=True))


if __name__ == '__main__':
    main()
