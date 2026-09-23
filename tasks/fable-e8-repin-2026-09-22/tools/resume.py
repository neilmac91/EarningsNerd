"""Inspect or resume retained singleton judgments; execution requires --execute.

No generation, installation, outer retry, model substitution or valid-verdict overwrite.
All paths in immutable indexes are bundle-relative. Mutable records stay in this bundle.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
import uuid

from binding import Validator
from guard_setup import validate_guard

ORDER = ('e3-candidate1', 'e3-candidate2')
PREREQUISITES = {'e3-candidate1': ('ko-corrected',), 'e3-candidate2': ('ko-corrected', 'e3-candidate1')}
ORIGINAL_MANIFEST_SHA256 = '0fe5cb9e45c1fca76d2d9d71b0a13f58958ea7242efe34ae2a9f64544402d2c3'
POLICY_ID = 'aapl017-harness-compatible-fail-reconciliation-v1'
AUTHORIZATION = 'ok please proceed with the next actionable steps'
KNOWN = {
    'slot': '017-AAPL-10-K-run0',
    'failed_dir': '.pending-017-AAPL-10-K-run0-4bfede2e6ad149b9860db61a9b4c8a38',
    'stop_sha256': '134234c500cbd29633e9117c964e14b4d8447db88b44415f54bf0b35b88200eb',
    'ledger_sha256': '336e971688a2bbdb559647248a7a54aa8d5a6b61d98cb61021f95bdfd002ea96',
    'request_sha256': 'f05f399ddf9a39f4a713e4839c1740a1975b0cd0660bbf36fd37a8bfedaf1bbf',
    'packet_sha256': '9923e14eaa712af35bad15566d88e21b8e90e85ee4b60668c22610fe67addf70',
    'row_sha256': '4a6f44adcddad9abbe273b1755f6dba6da5195ea472da575a78c488b5aa02b9e',
    'failed_files': {
        'judged.json': '26008528367a2175e518907c09332569bec7b531ca861d3792208a0b2ad71d2b',
        'judged.md': '1ce7e801718515efc8f2aa2b4c42ccf04f1a25a2e9d98d57c03971d6d381e4e3',
        'owner.json': 'dcdc04a2a4cea1e6093c05ff66c85ca96f989e4b4e34d3e31f495b616b18825a',
        'run.log': 'fbdc2d988c42414074c61b71d312c46a6bf1bb58e6d403be7a5c895ff703e529',
    },
}
RECONCILIATION = 'reconciliation-supplement.json'
SUPPLEMENT_STOP = 'STOP.supplement.json'
SUPPLEMENT_LEDGER = 'execution-ledger.supplement.jsonl'
BILLING = {'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_USE_VERTEX', 'CLAUDE_CODE_USE_FOUNDRY'}
def now(): return datetime.now(timezone.utc).isoformat()
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text())
def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.writing-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(value, f, indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(temp, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        if os.path.exists(temp): os.unlink(temp)
def append(path, value):
    with Path(path).open('a') as f:
        f.write(json.dumps(value, sort_keys=True) + '\n'); f.flush(); os.fsync(f.fileno())
def inside(root, value):
    p = (root / value).resolve()
    if not p.is_relative_to(root): raise ValueError('Path leaves bundle: ' + str(value))
    return p

def verify_supplement():
    root = Path(__file__).resolve().parents[1]
    manifest = read(root / 'supplement-sha256.json')
    if set(manifest) != {'tools/binding.py', 'tools/guard_setup.py', 'tools/readout.py', 'tools/resume.py'}:
        raise ValueError('Supplement manifest contents changed')
    for name, expected in manifest.items():
        if sha(inside(root, name)) != expected: raise ValueError('Supplement tool changed: ' + name)

def expected_reconciliation():
    return {'schema': 'fable-known-stop-reconciliation-v1', 'policy_id': POLICY_ID,
            'authorized_user_directive': AUTHORIZATION,
            'supplement_manifest_sha256': '8e43ac912126d5253f5a46b4e5cc88ffbaa5b4ab4e5d49bb37f3189d1b0c568c',
            'original_immutable_manifest_sha256': ORIGINAL_MANIFEST_SHA256,
            'known': KNOWN}

def verify_reconciliation_record(path):
    expected = expected_reconciliation()
    if path.read_bytes() != (json.dumps(expected, indent=2) + '\n').encode():
        raise ValueError('Reconciliation record changed')

def known_failed_output(root, validator, index):
    """Return the original failed output only after exact, immutable STOP binding."""
    work = root / 'stages/e3-candidate1'
    stop = work / 'STOP.json'; ledger = work / 'execution-ledger.jsonl'
    if not stop.is_file() or sha(stop) != KNOWN['stop_sha256']: raise ValueError('Original STOP missing or changed')
    if not ledger.is_file() or sha(ledger) != KNOWN['ledger_sha256']: raise ValueError('Original execution history changed')
    lines = ledger.read_text().splitlines()
    if len(lines) != 17 or sum(bool(json.loads(line).get('failure')) for line in lines) != 1:
        raise ValueError('Original ledger failure count changed')
    terminal = json.loads(lines[-1]); original_stop = read(stop)
    if terminal != original_stop or terminal['slot'] != KNOWN['slot'] or terminal['failure'] != 'Invalid gate reasons' or terminal['complete'] or terminal['exit_code'] != 0:
        raise ValueError('Original STOP and ledger do not bind the known failure')
    for field in ('request_sha256', 'packet_sha256', 'row_sha256'):
        if terminal[field] != KNOWN[field]: raise ValueError('Known request binding changed: ' + field)
    failed = work / 'failed' / KNOWN['failed_dir']
    if set(p.name for p in failed.iterdir()) != set(KNOWN['failed_files']): raise ValueError('Original failed directory contents changed')
    for name, expected in KNOWN['failed_files'].items():
        if sha(failed / name) != expected: raise ValueError('Original failed evidence changed: ' + name)
    if [p.name for p in (work / 'failed').iterdir()] != [KNOWN['failed_dir']]:
        raise ValueError('Unexpected original failed invocation')
    entry = next((p for p in index['packets'] if p['slot'] == KNOWN['slot']), None)
    if entry is None or any(entry[field] != KNOWN[field] for field in ('request_sha256', 'row_sha256')) or sha(entry['packet_path']) != KNOWN['packet_sha256']:
        raise ValueError('Known packet binding changed')
    judged = failed / 'judged.json'
    result = validator.validate_output(entry, read(judged))
    if result['verdict'] != 'FAIL' or not result['gate_failures']:
        raise ValueError('Known failed output lost hard FAIL veto')
    return judged

def reconciled_output(root, stage, slot, validator, index):
    if stage != 'e3-candidate1' or slot != KNOWN['slot']: return None
    record = root / 'stages/e3-candidate1' / RECONCILIATION
    if not record.exists(): return None
    verify_reconciliation_record(record)
    return known_failed_output(root, validator, index)

def load_index(root, stage):
    index = read(root / 'stages' / stage / 'index.json')
    if index.get('programme') != stage: raise ValueError('Index programme/stage mismatch')
    entries = index['packets']
    if len(entries) != (160 if stage == 'e8' else 70): raise ValueError('Unexpected stage denominator')
    if len({p['slot'] for p in entries}) != len(entries): raise ValueError('Duplicate slots')
    for p in entries + index.get('reused_main_slots', []):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', p['slot']): raise ValueError('Unsafe slot name')
        p['packet_path'] = str(inside(root, p['packet_path']))
    return index

def require_e8_guard(stage, index, guard_dir):
    e8 = stage == 'e8' or index.get('programme') == 'e8' or bool(index.get('reused_main_slots')) or any('condition' in p or 'slot_kind' in p for p in index['packets'])
    if e8 and (stage != 'e8' or guard_dir is None):
        raise ValueError('E8 requires its explicit shared guard; dispatch refused')
    if not e8 and guard_dir is not None: raise ValueError('Non-E8 calls must not charge the E8 guard')
    return e8

def inspect_stage(root, stage, validator):
    index = load_index(root, stage); completed = []; missing = []
    logged = {}; immutable = read(root / 'immutable-sha256.json')
    work = root / 'stages' / stage
    for ledger in (work / 'execution-ledger.jsonl', work / SUPPLEMENT_LEDGER):
        if ledger.exists():
            for line in ledger.read_text().splitlines():
                event = json.loads(line)
                if event.get('complete'):
                    if event['slot'] in logged: raise ValueError('Duplicate completed execution record')
                    logged[event['slot']] = event
                elif ledger.name == SUPPLEMENT_LEDGER and event.get('failure') and not (work / SUPPLEMENT_STOP).exists():
                    raise ValueError('Supplement failure lacks STOP')
    if stage == 'e3-candidate1' and (work / RECONCILIATION).exists():
        known_failed_output(root, validator, index)
    if set(logged) - {p['slot'] for p in index['packets']}:
        raise ValueError('Completed ledger references an unknown slot')
    for p in index['packets']:
        validator.validate_packet(p)
        jf = work / 'slots' / p['slot'] / 'judged.json'
        recovered = reconciled_output(root, stage, p['slot'], validator, index)
        if recovered:
            if jf.exists(): raise ValueError('Known failed slot must not be promoted or rejudged')
            jf = recovered
        if jf.exists():
            j = validator.validate_output(p, read(jf))
            if not recovered:
                relative = jf.relative_to(root).as_posix(); digest = sha(jf)
                event = logged.get(p['slot'])
                if event and (event.get('judged_json_sha256') != digest or
                              any(event.get(field) != p[field] for field in ('packet_sha256', 'request_sha256', 'row_sha256')) or
                              event.get('identity') != p['identity']):
                    raise ValueError('Completed output/ledger binding changed: ' + p['slot'])
                if immutable.get(relative) != digest and event is None:
                    raise ValueError('Completed output has no immutable or execution-ledger provenance: ' + p['slot'])
            completed.append({'slot': p['slot'], 'identity': p['identity'], 'verdict': j['verdict'], 'output_sha256': sha(jf)})
        else:
            if p['slot'] in logged: raise ValueError('Completed ledger output is missing: ' + p['slot'])
            missing.append(p['slot'])
    return index, {'stage': stage, 'planned': len(index['packets']), 'complete': len(completed), 'missing': missing, 'completed': completed}

def verify_bundle(root):
    if sha(root / 'immutable-sha256.json') != ORIGINAL_MANIFEST_SHA256:
        raise ValueError('Original immutable manifest changed')
    manifest = read(root / 'immutable-sha256.json')
    for name, expected in manifest.items():
        if sha(inside(root, name)) != expected: raise ValueError('Immutable bundle file changed: ' + name)

def admit(root, stage, validator):
    """Repeat all stage and predecessor terminal checks before and under the lock."""
    verify_supplement(); verify_bundle(root)
    selected = None
    for name in (*PREREQUISITES[stage], stage):
        work = root / 'stages' / name
        if list(work.glob('.pending-*')): raise ValueError('Unresolved pending invocation: ' + name)
        if (work / SUPPLEMENT_STOP).exists(): raise ValueError('Supplement STOP is terminal: ' + name)
        if name != 'e3-candidate1' and (work / 'STOP.json').exists(): raise ValueError('Unexpected original STOP: ' + name)
        if name != 'e3-candidate1' and (work / 'failed').exists() and list((work / 'failed').iterdir()):
            raise ValueError('Unexpected failed invocation: ' + name)
        for ledger in (work / 'execution-ledger.jsonl', work / SUPPLEMENT_LEDGER):
            if ledger.exists() and any(json.loads(line).get('failure') for line in ledger.read_text().splitlines()):
                if name != 'e3-candidate1' or ledger.name != 'execution-ledger.jsonl':
                    raise ValueError('Unreconciled failed execution: ' + name)
        index, status = inspect_stage(root, name, validator)
        if name == 'e3-candidate1':
            if not (work / RECONCILIATION).exists(): raise ValueError('Known STOP requires explicit reconciliation')
            # inspect_stage has already checked record content and the original evidence.
        if name != stage and status['missing']: raise ValueError('Prior required stage is incomplete: ' + name)
        if name == stage: selected = (index, status)
    return selected

def verified_cli(value):
    p = Path(value).resolve(strict=True)
    if not p.is_file() or not os.access(p, os.X_OK): raise ValueError('CLI is not executable')
    result = subprocess.run([str(p), '--version'], capture_output=True, text=True, timeout=20)
    if result.returncode or not re.match(r'^2\.1\.280(?:\s|$)', result.stdout.strip()):
        raise ValueError('Existing Claude CLI 2.1.280 required; no replacement or model probe performed')
    return p, result.stdout.strip()

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--bundle', type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument('--repo', type=Path, required=True)
    ap.add_argument('--stage', choices=ORDER, required=True)
    ap.add_argument('--python', type=Path)
    ap.add_argument('--cli', type=Path)
    ap.add_argument('--guard-dir', type=Path)
    ap.add_argument('--execute', action='store_true')
    ap.add_argument('--reconcile-known-stop', action='store_true')
    ap.add_argument('--max-new', type=int)
    args = ap.parse_args(); root = args.bundle.resolve(); stage = args.stage
    if args.execute and args.reconcile_known_stop: raise ValueError('Reconciliation and execution are separate actions')
    if args.reconcile_known_stop and stage != 'e3-candidate1': raise ValueError('Only the known E3 candidate 1 STOP is reconcilable')
    verify_supplement(); verify_bundle(root); validator = Validator(args.repo.resolve())
    if args.reconcile_known_stop:
        with (root / 'execution.lock').open('a') as owner:
            try: fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: raise ValueError('Another bundle executor owns the queue')
            verify_supplement(); verify_bundle(root)
            work = root / 'stages/e3-candidate1'
            if (work / SUPPLEMENT_STOP).exists() or list(work.glob('.pending-*')):
                raise ValueError('New STOP or pending invocation prevents reconciliation')
            if (work / SUPPLEMENT_LEDGER).exists() and any(json.loads(line).get('failure') for line in (work / SUPPLEMENT_LEDGER).read_text().splitlines()):
                raise ValueError('New failed ledger record prevents reconciliation')
            ko = root / 'stages/ko-corrected'
            if (ko / 'STOP.json').exists() or (ko / SUPPLEMENT_STOP).exists() or list(ko.glob('.pending-*')):
                raise ValueError('KO prerequisite has STOP or pending invocation')
            if (ko / 'execution-ledger.jsonl').exists() and any(json.loads(line).get('failure') for line in (ko / 'execution-ledger.jsonl').read_text().splitlines()):
                raise ValueError('KO prerequisite has a failed execution')
            _, ko_status = inspect_stage(root, 'ko-corrected', validator)
            if ko_status['missing']: raise ValueError('KO prerequisite is incomplete')
            index = load_index(root, stage)
            known_failed_output(root, validator, index)
            record = work / RECONCILIATION
            expected = expected_reconciliation()
            if record.exists():
                verify_reconciliation_record(record)
            else:
                if any((work / name).exists() for name in (SUPPLEMENT_LEDGER, 'environment.supplement.json', 'resume-manifest.supplement.json')):
                    raise ValueError('Missing reconciliation record after supplement activity')
                _, before = inspect_stage(root, stage, validator)
                if before['complete'] != 16 or KNOWN['slot'] not in before['missing']:
                    raise ValueError('Known pre-reconciliation state changed')
                write(record, expected)
            _, status = inspect_stage(root, stage, validator)
            print(json.dumps({k:v for k,v in status.items() if k != 'completed'}, indent=2))
            return 0
    index, status = inspect_stage(root, stage, validator)
    print(json.dumps({k:v for k,v in status.items() if k != 'completed'}, indent=2))
    if not args.execute: return 0
    if args.max_new is not None and args.max_new < 1: raise ValueError('--max-new must be positive')
    e8 = require_e8_guard(stage, index, args.guard_dir)
    index, status = admit(root, stage, validator)
    work = root / 'stages' / stage
    if not args.python or not args.cli: raise ValueError('--python and --cli are required for execution')
    real, version = verified_cli(args.cli)
    python = args.python.resolve(strict=True)
    cfg = st = None
    if e8:
        cfg, st = validate_guard(args.guard_dir.resolve())
        if Path(cfg['real_cli']) != real: raise ValueError('Explicit CLI differs from shared E8 guard')
    with (root / 'execution.lock').open('a') as owner:
        try: fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('Another bundle executor owns the queue')
        # Admission is authoritative only while this executor owns the lock.
        index, status = admit(root, stage, validator)
        # Stable PATH makes the frozen harness resolve only the selected existing CLI.
        bin_dir = root / 'runtime-bin'; bin_dir.mkdir(exist_ok=True)
        cli_link = bin_dir / 'claude'
        if cli_link.is_symlink():
            if cli_link.resolve() != real: raise ValueError('Runtime CLI link points elsewhere')
        elif cli_link.exists(): raise ValueError('Unexpected runtime CLI file')
        else: cli_link.symlink_to(real)
        env = {k:v for k,v in os.environ.items() if k not in BILLING}
        env.update(SKIP_REDIS_INIT='true', SECRET_KEY='offline-judge-run-not-a-real-secret-key')
        env['PATH'] = str(args.guard_dir.resolve() if e8 else bin_dir) + os.pathsep + env.get('PATH', '')
        expected = (args.guard_dir.resolve() / 'claude') if e8 else real
        if Path(shutil.which('claude', path=env['PATH'])).resolve() != expected.resolve(): raise ValueError('Incorrect CLI routing')
        write(work / 'environment.supplement.json', {'observed_at':now(), 'cli':str(real), 'version':version, 'python':str(python), 'repo':str(args.repo.resolve()), 'billing_environment_removed':sorted(BILLING)})
        count = 0
        for p in index['packets']:
            validator.validate_packet(p)
            slot = work / 'slots' / p['slot']; jf = slot / 'judged.json'
            if reconciled_output(root, stage, p['slot'], validator, index): continue
            if jf.exists(): validator.validate_output(p, read(jf)); continue
            if args.max_new is not None and count >= args.max_new: break
            pre = None
            if e8: cfg, pre = validate_guard(args.guard_dir.resolve())
            pending = work / ('.pending-' + p['slot'] + '-' + uuid.uuid4().hex)
            pending.mkdir(); start = now()
            write(pending / 'owner.json', {'driver_pid':os.getpid(), 'started_at':start, 'slot':p['slot'], 'request_sha256':p['request_sha256']})
            cmd = [str(python), '-m', 'evals.judge_report', p['packet_path'], '--judge', 'cli:claude-fable-5-1', '--output-dir', str(pending), '--concurrency', '1']
            proc = None; failure = None; code = None; stdout = stderr = ''; judge = None; post = None
            def interrupted(signum, frame): raise InterruptedError('Operator interrupted queue')
            old = {sig:signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
            try:
                proc = subprocess.Popen(cmd, cwd=args.repo.resolve()/'backend', env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
                write(pending/'owner.json', {'driver_pid':os.getpid(), 'harness_pid':proc.pid, 'started_at':start, 'slot':p['slot'], 'request_sha256':p['request_sha256']})
                stdout, stderr = proc.communicate(); code = proc.returncode
                if code: failure = 'Harness nonzero exit; cause not inferred from empty stderr'
                if (pending/'judged.json').exists():
                    try: judge = validator.validate_output(p, read(pending/'judged.json'))
                    except ValueError as exc: failure = str(exc)
                else: failure = failure or 'Missing judged output'
            except BaseException as exc:
                failure = type(exc).__name__ + ': ' + str(exc)
                if proc is not None and proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try: stdout, stderr = proc.communicate(timeout=8)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL); stdout, stderr = proc.communicate()
                    code = proc.returncode
            finally:
                for sig, handler in old.items(): signal.signal(sig, handler)
            (pending/'run.log').write_text(json.dumps({'command':cmd,'start':start,'end':now(),'exit':code})+'\nSTDOUT\n'+stdout+'\nSTDERR\n'+stderr)
            if e8:
                try:
                    post = read(Path(cfg['state_path'])); current_cfg = read(args.guard_dir/'config.json')
                    delta = post['real_cli_invocations']-pre['real_cli_invocations']
                    new = [x for x in post.get('completed',[]) if x['invocation']>pre['real_cli_invocations']]
                    if current_cfg != cfg or delta not in (1,2) or post.get('active') or len(new)!=delta or sorted(x['invocation'] for x in new)!=list(range(pre['real_cli_invocations']+1,post['real_cli_invocations']+1)):
                        failure = failure or 'Uncertain E8 invocation accounting/ownership'
                    if post.get('stop_reason') or any(x.get('quota') or x.get('owner_lost') for x in new): failure = failure or 'E8 guard stopped; preserve latch'
                except Exception as exc: failure = failure or 'Cannot reconcile E8 post-state: '+str(exc)
            record = {'slot':p['slot'],'identity':p['identity'],'start':start,'end':now(),'exit_code':code,'complete':judge is not None,'verdict':judge.get('verdict') if judge else None,'packet_sha256':sha(p['packet_path']),'row_sha256':p['row_sha256'],'request_sha256':p['request_sha256'],'judged_json_sha256':sha(pending/'judged.json') if (pending/'judged.json').exists() else None,'guard_before':pre,'guard_after':post,'failure':failure}
            # Keep the pending marker until every refusal/receipt is durable. A crash
            # cannot turn an attempted failed slot back into apparently missing work.
            if failure: write(work/SUPPLEMENT_STOP,record)
            append(work/SUPPLEMENT_LEDGER,record)
            if judge is not None:
                slot.parent.mkdir(exist_ok=True); pending.rename(slot)
            else:
                failed = work/'failed'; failed.mkdir(exist_ok=True); pending.rename(failed/pending.name)
            count += 1
            _, after = inspect_stage(root,stage,validator); write(work/'resume-manifest.supplement.json',after)
            print(json.dumps({'slot':p['slot'],'complete':judge is not None,'failure':failure}),flush=True)
            if failure: return 3
            if e8 and post['real_cli_invocations']>=601:
                print('E8 ceiling reached; no further calls',flush=True); return 0 if not after['missing'] else 3
        _, after = inspect_stage(root,stage,validator); write(work/'resume-manifest.supplement.json',after)
        return 0

if __name__ == '__main__':
    try: sys.exit(main())
    except Exception as exc:
        print(type(exc).__name__ + ': ' + str(exc),file=sys.stderr); sys.exit(2)
