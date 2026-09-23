"""E8-only add-on to the sealed corrected bundle and E3 supplement.

Inspection is read-only. Execution requires an independent prior-call attestation,
the original shared 601-call guard, and an explicit --execute. Never run E1 here.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import uuid

ORIGINAL_MANIFEST_SHA256 = '0fe5cb9e45c1fca76d2d9d71b0a13f58958ea7242efe34ae2a9f64544402d2c3'
E3_SUPPLEMENT_MANIFEST_SHA256 = '1ef772b3157106bcf9bee52675f89bdf0cf643f0457eb405b6ce28e5fe950f6f'
PRIOR_EVIDENCE_SHA256 = 'ef5ef4dda0ac71dbc3480381f2d9febe3c2f09ffc4c0ce391c5814769a62f26c'
FOUNDER_STATEMENT_SHA256 = '67527fd115135ae78c7e339423f7c798d53e78bb878d820ac77262e45d36ec8c'
MIN_PRIOR = 287
CEILING = 601
LEDGER = 'execution-ledger.supplement.jsonl'
STOP = 'STOP.supplement.json'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def trusted_common(supplement: Path):
    """Verify the delivered E3 code *before* importing any of it."""
    supplement = supplement.resolve(strict=True)
    manifest_path = supplement / 'supplement-sha256.json'
    if sha(manifest_path) != E3_SUPPLEMENT_MANIFEST_SHA256:
        raise ValueError('E3 supplement manifest changed')
    manifest = read(manifest_path)
    if set(manifest) != {'tools/binding.py', 'tools/guard_setup.py', 'tools/readout.py', 'tools/resume.py'}:
        raise ValueError('E3 supplement file list changed')
    for name, digest in manifest.items():
        if sha(supplement / name) != digest:
            raise ValueError('E3 supplement tool changed: ' + name)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(supplement / 'tools'))
    path = supplement / 'tools/resume.py'
    spec = importlib.util.spec_from_file_location('trusted_e3_resume', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.verify_supplement()
    return module


def verify_addon() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = read(root / 'code-sha256.json')
    expected = {'tools/e8_resume.py', 'README.md', 'founder-history-attestation.md',
                'tests/test_e8_addon.py', 'verification.md'}
    if set(manifest) != expected:
        raise ValueError('E8 add-on file list changed')
    for name, digest in manifest.items():
        if sha(root / name) != digest:
            raise ValueError('E8 add-on file changed: ' + name)


def verify_panel(root: Path, common, validator) -> dict:
    """Bind all 300 frozen slots: 140 reused controls, 140 new mains, 20 duplicates."""
    index = common.load_index(root, 'e8')
    packets = index['packets']
    reused = index['reused_main_slots']
    if len(packets) != 160 or len(reused) != 140:
        raise ValueError('E8 frozen denominators changed')
    if sum(p.get('slot_kind') == 'main' and p.get('condition') == 'n' for p in packets) != 140:
        raise ValueError('E8 new-main panel changed')
    if sum(p.get('slot_kind') == 'duplicate' for p in packets) != 20:
        raise ValueError('E8 duplicate panel changed')
    if any(p.get('slot_kind') != 'main' or p.get('condition') != 'o' for p in reused):
        raise ValueError('E8 reused controls changed')
    ordered = sorted([*packets, *reused], key=lambda p: p['order'])
    frozen = read(root / 'e8/frozen/e8-judge-order.json')
    if [p['order'] for p in ordered] != list(range(1, 301)) or [p['blind_id'] for p in ordered] != [s['blind_id'] for s in frozen['slots']]:
        raise ValueError('E8 frozen order changed')
    mapping = read(root / 'e8/e8-control-main-reuse-2026-09-19.json')['main_verdicts']
    by_key = {(m['corpus'], tuple(m['identity'])): m for m in mapping}
    if len(by_key) != 140:
        raise ValueError('E8 reused-main mapping has duplicates')
    source_rows = {}
    for corpus, name in ((1, 'e2'), (2, 'e2-control2')):
        report = root / 'preserved' / name / 'judged.json'
        report_sha = sha(report)
        rows = read(report)['results']
        if len(rows) != 70:
            raise ValueError('E8 control source denominator changed')
        for row in rows:
            key = (corpus, (row['candidate'], row['ticker'], row['filing_type'], row['run']))
            if key in source_rows:
                raise ValueError('E8 control source repeats an identity')
            source_rows[key] = (row['judge'], report_sha)
    for p in reused:
        validator.validate_packet(p)
        i = p['identity']
        key = (p['corpus'], (i['candidate'], i['ticker'], i['filing_type'], i['run']))
        m = by_key.get(key)
        judge, report_sha = source_rows.get(key, (None, None))
        reuse = p.get('reuse', {})
        if not m or judge != m['verdict'] or report_sha != m['judged_report_sha256'] or any((
                m['main_blind_id'] != p['blind_id'], m['output_id'] != p['output_id'],
                m['planned_order'] != p['order'], m['request_sha256'] != p['request_sha256'],
                m['source_report_sha256'] != p['source_report_sha256'],
                sha_bytes(json.dumps(judge, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()) != m['verdict_sha256'],
                reuse.get('verdict_sha256') != m['verdict_sha256'],
                reuse.get('judged_report_sha256') != report_sha,
                reuse.get('judged_at') != m['judged_at'],
                reuse.get('verdict') != judge['verdict'])):
            raise ValueError('E8 reused-main binding changed: ' + p['slot'])
    return index


def inspect_e8(root: Path, common, validator) -> tuple[dict, dict]:
    index = verify_panel(root, common, validator)
    _, status = common.inspect_stage(root, 'e8', validator)
    work = root / 'stages/e8'
    if any((work / name).exists() for name in ('STOP.json', STOP)) or list(work.glob('.pending-*')):
        raise ValueError('E8 STOP or pending invocation is terminal')
    failed = work / 'failed'
    if failed.exists() and list(failed.iterdir()):
        raise ValueError('E8 failed invocation requires investigation')
    slots = work / 'slots'
    if slots.exists():
        names = {p.name for p in slots.iterdir()}
        if names != {p['slot'] for p in index['packets'] if (slots / p['slot'] / 'judged.json').exists()}:
            raise ValueError('E8 unknown or incomplete slot directory')
    if (work / 'execution-ledger.jsonl').exists():
        raise ValueError('Unexpected original E8 execution ledger')
    ledger = work / LEDGER
    rows = [json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else []
    if any(not row.get('complete') or row.get('failure') for row in rows):
        raise ValueError('E8 ledger has an unresolved execution')
    if len({row.get('slot') for row in rows}) != len(rows):
        raise ValueError('E8 ledger repeats a slot')
    return index, status


def admit(root: Path, common, validator) -> tuple[dict, dict]:
    """Call the E3 supplement's full prerequisite audit, then inspect E8."""
    common.verify_bundle(root)
    if sha(root / 'immutable-sha256.json') != ORIGINAL_MANIFEST_SHA256:
        raise ValueError('Original manifest changed')
    _, c2 = common.admit(root, 'e3-candidate2', validator)
    if c2['complete'] != 70 or c2['missing']:
        raise ValueError('E3 candidate 2 is incomplete')
    return inspect_e8(root, common, validator)


def admit_next_slot(root: Path, common, validator, expected_missing: list[str], slot: str) -> None:
    """Repeat the full prerequisite/E8 audit immediately before creating a pending owner."""
    _, status = admit(root, common, validator)
    if status['missing'] != expected_missing:
        raise ValueError('E8 missing-slot state changed under the execution lock')
    if slot not in status['missing']:
        raise ValueError('E8 next slot is no longer missing: ' + slot)


def attest(root: Path, guard_dir: Path, attestation: Path, common,
           observed_now: datetime | None = None) -> tuple[dict, dict]:
    """Require affirmative external-history attestation and exact ledger continuity."""
    a = read(attestation)
    guard_dir = guard_dir.resolve(strict=True)
    expected_keys = {'schema', 'operator', 'observed_at_utc', 'prior_count',
                     'prior_evidence_sha256', 'founder_statement_sha256', 'original_manifest_sha256',
                     'e3_supplement_manifest_sha256', 'guard_state_path',
                     'no_untracked_e8_or_probe_calls', 'sole_persistent_guard',
                     'exclusive_e8_dispatch_during_continuation'}
    if set(a) != expected_keys or a['schema'] != 'fable-e8-accounting-attestation-v1':
        raise ValueError('E8 accounting attestation missing or malformed')
    if not isinstance(a['operator'], str) or not a['operator'].strip() or not isinstance(a['observed_at_utc'], str) or not a['observed_at_utc'].strip():
        raise ValueError('E8 attestation requires a named operator and observation time')
    try:
        observed = datetime.fromisoformat(a['observed_at_utc'].replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('E8 attestation observation time is malformed') from exc
    if observed.tzinfo is None or observed.utcoffset() != timedelta(0):
        raise ValueError('E8 attestation observation time must be UTC')
    clock = observed_now or datetime.now(timezone.utc)
    if clock.tzinfo is None or clock.utcoffset() != timedelta(0):
        raise ValueError('E8 admission clock must be UTC')
    age = clock - observed
    if age > timedelta(hours=6) or age < -timedelta(minutes=5):
        raise ValueError('E8 attestation expired or is future-dated; obtain a new human readback before any call')
    if type(a['prior_count']) is not int or a['prior_count'] != MIN_PRIOR:
        raise ValueError('E8 attested prior count must equal the reviewed conservative charge of 287')
    if any(a[k] is not True for k in ('no_untracked_e8_or_probe_calls', 'sole_persistent_guard', 'exclusive_e8_dispatch_during_continuation')):
        raise ValueError('E8 cross-session and exclusive-guard assertions are absent')
    if (a['prior_evidence_sha256'] != PRIOR_EVIDENCE_SHA256 or
            sha(root / 'preserved/e8-pilot/accounting-reconciliation.md') != PRIOR_EVIDENCE_SHA256 or
            a['founder_statement_sha256'] != FOUNDER_STATEMENT_SHA256 or
            sha(Path(__file__).resolve().parents[1] / 'founder-history-attestation.md') != FOUNDER_STATEMENT_SHA256 or
            a['original_manifest_sha256'] != ORIGINAL_MANIFEST_SHA256 or
            a['e3_supplement_manifest_sha256'] != E3_SUPPLEMENT_MANIFEST_SHA256 or
            a['guard_state_path'] != str(guard_dir / 'state.json')):
        raise ValueError('E8 attestation is not bound to the sealed evidence and one guard')
    if not (guard_dir / 'initialization.json').is_file():
        raise ValueError('E8 guard has not completed one-time initialization')
    initialization = read(guard_dir / 'initialization.json')
    if (initialization.get('status') != 'complete' or initialization.get('prior_count') != a['prior_count'] or
            initialization.get('state_path') != a['guard_state_path']):
        raise ValueError('E8 guard initialization does not match the attested prior count')
    cfg, state = common.validate_guard(guard_dir)
    if cfg['state_path'] != a['guard_state_path'] or cfg['ceiling'] != CEILING:
        raise ValueError('E8 guard config changed')
    rows_path = root / 'stages/e8' / LEDGER
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()] if rows_path.exists() else []
    count = a['prior_count']
    for row in rows:
        before, after = row.get('guard_before'), row.get('guard_after')
        if not isinstance(before, dict) or not isinstance(after, dict) or before.get('real_cli_invocations') != count:
            raise ValueError('E8 ledger/guard continuity broken before slot')
        new_count = after.get('real_cli_invocations')
        if type(new_count) is not int or new_count - count not in (1, 2) or new_count > CEILING:
            raise ValueError('E8 ledger/guard delta is invalid')
        count = new_count
    if state['real_cli_invocations'] != count:
        raise ValueError('E8 guard contains unaccounted calls since initialization')
    completed = state.get('completed')
    if not isinstance(completed, list) or [x.get('invocation') for x in completed] != list(range(a['prior_count'] + 1, count + 1)):
        raise ValueError('E8 guard completion history is incomplete')
    return cfg, state


def execute(args, root: Path, common, validator) -> int:
    if not all((args.python, args.cli, args.guard_dir, args.attestation)):
        raise ValueError('Execution requires --python, --cli, --guard-dir and --attestation')
    if args.max_new is not None and not 1 <= args.max_new <= 160:
        raise ValueError('--max-new must be in 1..160')
    guard = args.guard_dir.resolve(strict=True)
    if guard != (root / 'e8/guard').resolve(strict=True):
        raise ValueError('E8 must use the original guard in the one persistent bundle')
    python = args.python.resolve(strict=True)
    with (root / 'execution.lock').open('a') as owner:
        try:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('Another bundle executor owns the queue') from exc
        index, status = admit(root, common, validator)
        cfg, state = attest(root, guard, args.attestation, common)
        real, version = common.verified_cli(args.cli)
        if Path(cfg['real_cli']) != real:
            raise ValueError('E8 CLI differs from the shared guard')
        if not status['missing']:
            return 0
        env = {k: v for k, v in os.environ.items() if k not in common.BILLING}
        env.update(SKIP_REDIS_INIT='true', SECRET_KEY='offline-judge-run-not-a-real-secret-key')
        env['PATH'] = str(guard) + os.pathsep + env.get('PATH', '')
        if Path(shutil.which('claude', path=env['PATH'])).resolve() != (guard / 'claude').resolve():
            raise ValueError('E8 CLI does not route through the original shared shim')
        work = root / 'stages/e8'
        attestation_sha = sha(args.attestation)
        common.write(work / 'environment.supplement.json', {'observed_at': now(), 'cli': str(real),
            'version': version, 'python': str(python), 'repo': str(args.repo.resolve()),
            'guard': str(guard), 'attestation_sha256': attestation_sha,
            'billing_environment_removed': sorted(common.BILLING)})
        count = 0
        expected_missing = list(status['missing'])
        for p in index['packets']:
            validator.validate_packet(p)
            slot = work / 'slots' / p['slot']
            if p['slot'] not in expected_missing:
                continue
            if args.max_new is not None and count >= args.max_new:
                break
            if sha(args.attestation) != attestation_sha:
                raise ValueError('E8 accounting attestation changed during execution')
            admit_next_slot(root, common, validator, expected_missing, p['slot'])
            cfg, pre = attest(root, guard, args.attestation, common)
            pending = work / ('.pending-' + p['slot'] + '-' + uuid.uuid4().hex)
            pending.mkdir()
            start = now()
            common.write(pending / 'owner.json', {'driver_pid': os.getpid(), 'started_at': start,
                                                  'slot': p['slot'], 'request_sha256': p['request_sha256']})
            cmd = [str(python), '-m', 'evals.judge_report', p['packet_path'], '--judge',
                   'cli:claude-fable-5-1', '--output-dir', str(pending), '--concurrency', '1']
            proc = None
            failure = None
            code = None
            stdout = stderr = ''
            judge = post = None
            def interrupted(signum, frame):
                raise InterruptedError('Operator interrupted E8 queue')
            old = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
            try:
                proc = subprocess.Popen(cmd, cwd=args.repo.resolve() / 'backend', env=env,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        text=True, start_new_session=True)
                common.write(pending / 'owner.json', {'driver_pid': os.getpid(), 'harness_pid': proc.pid,
                    'started_at': start, 'slot': p['slot'], 'request_sha256': p['request_sha256']})
                stdout, stderr = proc.communicate()
                code = proc.returncode
                if code:
                    failure = 'Harness nonzero exit; cause not inferred from empty stderr'
                if (pending / 'judged.json').exists():
                    try:
                        judge = validator.validate_output(p, read(pending / 'judged.json'))
                    except ValueError as exc:
                        failure = str(exc)
                else:
                    failure = failure or 'Missing judged output'
            except BaseException as exc:
                failure = type(exc).__name__ + ': ' + str(exc)
                if proc is not None and proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        stdout, stderr = proc.communicate(timeout=8)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        stdout, stderr = proc.communicate()
                    code = proc.returncode
            finally:
                for sig, handler in old.items():
                    signal.signal(sig, handler)
            (pending / 'run.log').write_text(json.dumps({'command': cmd, 'start': start,
                'end': now(), 'exit': code}) + '\nSTDOUT\n' + stdout + '\nSTDERR\n' + stderr)
            try:
                post = read(Path(cfg['state_path']))
                current_cfg = read(guard / 'config.json')
                delta = post['real_cli_invocations'] - pre['real_cli_invocations']
                new = [x for x in post.get('completed', []) if x['invocation'] > pre['real_cli_invocations']]
                if (current_cfg != cfg or delta not in (1, 2) or post.get('active') or len(new) != delta or
                        sorted(x['invocation'] for x in new) != list(range(pre['real_cli_invocations'] + 1,
                                                                           post['real_cli_invocations'] + 1))):
                    failure = failure or 'Uncertain E8 invocation accounting/ownership'
                if post.get('stop_reason') or any(x.get('quota') or x.get('owner_lost') for x in new):
                    failure = failure or 'E8 guard stopped; preserve latch'
            except Exception as exc:
                failure = failure or 'Cannot reconcile E8 post-state: ' + str(exc)
            record = {'slot': p['slot'], 'identity': p['identity'], 'start': start, 'end': now(),
                'exit_code': code, 'complete': judge is not None, 'verdict': judge.get('verdict') if judge else None,
                'packet_sha256': sha(Path(p['packet_path'])), 'row_sha256': p['row_sha256'],
                'request_sha256': p['request_sha256'],
                'judged_json_sha256': sha(pending / 'judged.json') if (pending / 'judged.json').exists() else None,
                'guard_before': pre, 'guard_after': post, 'failure': failure}
            if failure:
                common.write(work / STOP, record)
            common.append(work / LEDGER, record)
            if judge is not None:
                slot.parent.mkdir(exist_ok=True)
                pending.rename(slot)
            else:
                failed = work / 'failed'
                failed.mkdir(exist_ok=True)
                pending.rename(failed / pending.name)
            count += 1
            _, after = common.inspect_stage(root, 'e8', validator)
            common.write(work / 'resume-manifest.supplement.json', after)
            print(json.dumps({'slot': p['slot'], 'complete': judge is not None, 'failure': failure}), flush=True)
            if failure:
                return 3
            expected_missing = list(after['missing'])
            if post['real_cli_invocations'] >= CEILING:
                print('E8 ceiling reached; no further calls', flush=True)
                return 0 if not after['missing'] else 3
        _, after = admit(root, common, validator)
        if after['missing'] != expected_missing:
            raise ValueError('E8 missing-slot state changed before final readout')
        common.write(work / 'resume-manifest.supplement.json', after)
        return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--bundle', required=True, type=Path)
    ap.add_argument('--supplement', required=True, type=Path)
    ap.add_argument('--repo', required=True, type=Path)
    ap.add_argument('--guard-dir', type=Path)
    ap.add_argument('--attestation', type=Path)
    ap.add_argument('--python', type=Path)
    ap.add_argument('--cli', type=Path)
    ap.add_argument('--max-new', type=int)
    ap.add_argument('--execute', action='store_true')
    args = ap.parse_args()
    verify_addon()
    common = trusted_common(args.supplement)
    root = args.bundle.resolve(strict=True)
    validator = common.Validator(args.repo.resolve(strict=True))
    index, status = admit(root, common, validator)
    print(json.dumps({'stage': 'e8', 'reused_control_mains': len(index['reused_main_slots']),
                      'new_planned': status['planned'], 'new_complete': status['complete'],
                      'new_missing': len(status['missing']), 'missing_slots': status['missing']}, indent=2))
    if not args.execute:
        return 0
    return execute(args, root, common, validator)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print(type(exc).__name__ + ': ' + str(exc), file=sys.stderr)
        sys.exit(2)
