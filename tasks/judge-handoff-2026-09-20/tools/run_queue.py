"""Sequential, halting judge driver: one unchanged-harness command per packet, concurrency 1.

For each packet (in index order): skip if its slot already holds a complete contract-2 verdict; otherwise
run `python -m evals.judge_report <packet> --judge cli:claude-fable-5-1 --output-dir <slot> --concurrency 1`
from the pinned backend, then inspect exit status, the slot's judged.json and (E8) the guard state.
Appends one ledger line per command, rewrites the resume manifest after every packet, and STOPS on
the first anomaly (nonzero exit, missing/incomplete verdict, judge error, quota signature, guard latch).
No outer retry; a complete verdict is never re-run.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

JUDGE = 'cli:claude-fable-5-1'
ap = argparse.ArgumentParser()
ap.add_argument('--stage', required=True); ap.add_argument('--index', required=True)
ap.add_argument('--slots-root', required=True); ap.add_argument('--ledger', required=True); ap.add_argument('--manifest', required=True)
ap.add_argument('--repo', required=True); ap.add_argument('--python', required=True)
ap.add_argument('--guard-dir', default=None); ap.add_argument('--max', type=int, default=None)
args = ap.parse_args()

def now(): return datetime.now(timezone.utc).isoformat()
def sha_file(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def complete(j): return isinstance(j, dict) and not j.get('error') and j.get('input_complete') is True and j.get('verdict') in ('PASS', 'FAIL') and j.get('contract_version') == 2
def read_slot(slot):
    jf = slot / 'judged.json'
    if not jf.exists(): return None, None
    try: d = json.loads(jf.read_text()); return d, d['results'][0].get('judge')
    except Exception as exc: return None, {'error': f'unreadable judged.json: {exc}'}
def guard_state():
    if not args.guard_dir: return None, None
    cfg = json.loads((Path(args.guard_dir) / 'config.json').read_text()); st = json.loads(Path(cfg['state_path']).read_text()); return cfg, st

index = json.loads(Path(args.index).read_text()); packets = index['packets']
ledger = Path(args.ledger); manifest_path = Path(args.manifest); slots_root = Path(args.slots_root); slots_root.mkdir(parents=True, exist_ok=True)

def write_manifest(status, reason, current=None):
    done, failed, missing = [], [], []
    for p in packets:
        slot = slots_root / p['slot']; d, j = read_slot(slot)
        if d is None and j is None: missing.append({'identity': p['identity'], 'slot': str(slot)})
        elif complete(j): done.append({'identity': p['identity'], 'slot': str(slot), 'verdict': j['verdict']})
        else: failed.append({'identity': p['identity'], 'slot': str(slot), 'error': (j or {}).get('error')})
    cfg, st = guard_state()
    m = {'stage': args.stage, 'updated_at': now(), 'original_input_sha256': index.get('source_report_sha256'), 'index': args.index,
         'counts': {'planned': len(packets), 'completed': len(done), 'failed': len(failed), 'missing': len(missing)},
         'completed': done, 'failed': failed, 'missing': missing, 'active_process': status, 'stop_reason': reason, 'current_slot': current,
         'e8_guard_config': cfg, 'e8_guard_state': st}
    manifest_path.write_text(json.dumps(m, indent=2) + '\n')

def log(entry):
    with ledger.open('a') as f: f.write(json.dumps(entry, sort_keys=True) + '\n')

n_run = 0
write_manifest('running', None, None)
for p in packets:
    slot = slots_root / p['slot']; d, j = read_slot(slot)
    if d is not None or j is not None:
        if complete(j): print(f"SKIP {p['slot']} already complete ({j['verdict']})", flush=True); continue
        print(f"STOP {p['slot']} holds judged.json without a complete verdict: {(j or {}).get('error')!r}", flush=True)
        write_manifest('stopped', 'existing_incomplete_slot', p['slot']); sys.exit(3)
    if args.max is not None and n_run >= args.max:
        write_manifest('paused', 'max_slots_reached', p['slot']); print('MAX reached', flush=True); sys.exit(0)
    env = dict(os.environ); env.update(SKIP_REDIS_INIT='true', SECRET_KEY='offline-judge-run-not-a-real-secret-key', PYTHONPYCACHEPREFIX=str(slots_root / '.pycache'))
    pre = None
    if args.guard_dir:
        env['PATH'] = args.guard_dir + os.pathsep + env['PATH']
        which = shutil.which('claude', path=env['PATH']); cfg, st = guard_state(); pre = dict(st); problems = []
        if not which or Path(which).resolve() != (Path(args.guard_dir) / 'claude').resolve(): problems.append(f'PATH resolves claude to {which}, not the shim')
        if cfg.get('enabled') is not True: problems.append('guard disabled')
        if cfg.get('ceiling') != 601: problems.append('ceiling is not 601')
        if st.get('accounting_reconciled') is not True: problems.append('accounting unreconciled')
        if st.get('stop_reason'): problems.append('stop latch set: ' + str(st['stop_reason']))
        if st.get('active'): problems.append('active inflight owners present: ' + json.dumps(st['active']))
        if not isinstance(st.get('real_cli_invocations'), int) or st['real_cli_invocations'] >= 601: problems.append('invocation ceiling reached or counter invalid')
        if problems:
            print('STOP guard pre-check: ' + '; '.join(problems), flush=True); write_manifest('stopped', 'guard_precheck: ' + '; '.join(problems), p['slot']); sys.exit(3)
    slot.mkdir(parents=True, exist_ok=True)
    cmd = [args.python, '-m', 'evals.judge_report', p['packet_path'], '--judge', JUDGE, '--output-dir', str(slot), '--concurrency', '1']
    start = now(); t0 = time.time()
    proc = subprocess.run(cmd, cwd=str(Path(args.repo) / 'backend'), env=env, capture_output=True, text=True)
    end = now(); dur = round(time.time() - t0, 1); n_run += 1
    (slot / 'run.log').write_text(f"# cmd: {' '.join(cmd)}\n# cwd: {Path(args.repo) / 'backend'}\n# PATH[0]: {env['PATH'].split(os.pathsep)[0]}\n# start: {start}\n# end: {end}\n# exit: {proc.returncode}\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}\n")
    post, inv_range, quota, newc = None, None, False, None
    if args.guard_dir:
        cfg, st = guard_state(); post = dict(st); before = pre['real_cli_invocations']; after = st['real_cli_invocations']
        inv_range = [before + 1, after] if after > before else None
        newc = [c for c in st.get('completed', []) if isinstance(c.get('invocation'), int) and c['invocation'] > before]
        quota = any(c.get('quota') for c in newc)
    d, j = read_slot(slot)
    ok = (proc.returncode == 0 and complete(j) and d is not None and len(d['results']) == 1 and d['harness'].get('judge') == JUDGE and d['harness'].get('judge_contract_version') == 2
          and d['results'][0].get('ticker') == p['identity']['ticker'] and d['results'][0].get('filing_type') == p['identity']['filing_type'] and d['results'][0].get('run') == p['identity']['run'])
    jd = j if isinstance(j, dict) else {}
    entry = {'stage': args.stage, 'slot': p['slot'], 'identity': p['identity'], 'reuse': p.get('reuse'), 'packet_path': p['packet_path'], 'packet_sha256': p.get('packet_sha256'), 'row_sha256': p.get('row_sha256'), 'request_sha256': p.get('request_sha256'),
             'start': start, 'end': end, 'duration_s': dur, 'exit_code': proc.returncode,
             'judged_json_sha256': sha_file(slot / 'judged.json') if (slot / 'judged.json').exists() else None, 'judged_md_sha256': sha_file(slot / 'judged.md') if (slot / 'judged.md').exists() else None,
             'verdict': jd.get('verdict'), 'gate_failures': jd.get('gate_failures'), 'dimensions': jd.get('dimensions'), 'mean_dimension': jd.get('mean_dimension'), 'error': jd.get('error') if isinstance(j, dict) else 'no judge object', 'input_lengths': jd.get('input_lengths'), 'input_complete': jd.get('input_complete'), 'contract_version': jd.get('contract_version'), 'complete': bool(complete(j)),
             'guard_invocations_before': (pre or {}).get('real_cli_invocations'), 'guard_invocations_after': (post or {}).get('real_cli_invocations'), 'guard_invocation_range': inv_range, 'guard_stop_reason_after': (post or {}).get('stop_reason'), 'guard_quota_flag': quota, 'guard_completed_new': newc, 'stderr_tail': proc.stderr[-400:]}
    log(entry)
    print(f"{'OK  ' if ok else 'FAIL'} {p['slot']} exit={proc.returncode} verdict={entry['verdict']} gates={len(entry['gate_failures'] or [])} err={entry['error']!r} inv={inv_range} stop={entry['guard_stop_reason_after']} {dur}s", flush=True)
    stop = None
    if not ok: stop = f"packet_anomaly: exit={proc.returncode} error={entry['error']!r} complete={entry['complete']}"
    if args.guard_dir and (post.get('stop_reason') or quota): stop = (stop or '') + f" guard: stop_reason={post.get('stop_reason')} quota={quota}"
    blob = proc.stdout + proc.stderr + json.dumps(entry)
    if 'Fable limit' in blob or 'claude CLI exit 1: ' in blob or 'reached your' in blob: stop = (stop or '') + ' quota-signature'
    write_manifest('stopped' if stop else 'running', stop, p['slot'])
    if stop: print('STOP: ' + stop, flush=True); sys.exit(3)
write_manifest('finished', None, None); print('QUEUE COMPLETE', flush=True)
