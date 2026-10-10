#!/usr/bin/env bash
# One deterministic Impeccable scan over detect_targets.txt: comment and blank lines are filtered, every path is
# validated under frontend/, the paths are passed as an argument array, and the result is recorded under scans/
# with the source commit SHA. Exit code is the detector's (0 clean, 2 findings, 1 a target could not be scanned).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
L="${IMPECCABLE_LAUNCHER:-}"
[ -z "$L" ] && L="$(ls -d "$HOME"/.claude/plugins/cache/impeccable/impeccable/*/skills/impeccable/scripts/impeccable 2>/dev/null | sort | tail -1 || true)"
if [ -z "$L" ] || [ ! -x "$L" ]; then echo "Impeccable launcher not found; set IMPECCABLE_LAUNCHER=<…/skills/impeccable/scripts/impeccable>" >&2; exit 3; fi
targets=(); bad=()
while IFS= read -r line || [ -n "$line" ]; do
  line="${line%%#*}"; line="${line#"${line%%[![:space:]]*}"}"; line="${line%"${line##*[![:space:]]}"}"
  [ -z "$line" ] && continue
  if [ -e "$REPO/frontend/$line" ]; then targets+=("frontend/$line"); else bad+=("$line"); fi
done < "$HERE/detect_targets.txt"
if [ ${#bad[@]} -gt 0 ]; then printf 'missing target: %s\n' "${bad[@]}" >&2; exit 4; fi
sha="$(git -C "$REPO" rev-parse --short HEAD)"; mkdir -p "$HERE/scans"
out="$HERE/scans/detect-$sha.json"; err="$HERE/scans/detect-$sha.stderr"
set +e; ( cd "$REPO" && "$L" detect --json "${targets[@]}" > "$out" 2> "$err" ); code=$?; set -e
python3 - "$out" "$err" "$sha" "$code" "${#targets[@]}" "$L" "$REPO" <<'PY'
import json, sys, collections, datetime, pathlib, subprocess
out, err, sha, code, n, launcher, repo = sys.argv[1:8]
try: data = json.load(open(out))
except Exception: data = None
rules = collections.Counter(); files = collections.Counter(); seen = set()
def rel(fp):
    fp = str(fp or '')
    return fp[len(repo) + 1:] if fp.startswith(repo + '/') else fp
for f in (data or []):
    key = (f.get('antipattern'), rel(f.get('file')), f.get('line'), f.get('snippet'))
    if key in seen: continue
    seen.add(key); rules[f.get('antipattern')] += 1; files[rel(f.get('file'))] += 1
ver = pathlib.Path(launcher).parent / 'VERSION'
meta = {'source_sha': sha, 'source_full_sha': subprocess.run(['git', '-C', repo, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip(),
        'frontend_tree': subprocess.run(['git', '-C', repo, 'rev-parse', 'HEAD:frontend'], capture_output=True, text=True).stdout.strip(),
        'frontend_dirty': bool(subprocess.run(['git', '-C', repo, 'status', '--porcelain', '--', 'frontend'], capture_output=True, text=True).stdout.strip()),
        'run_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'), 'launcher': launcher,
        'engine_version': ver.read_text().strip() if ver.exists() else None, 'targets_passed': int(n), 'exit_code': int(code),
        'exit_meaning': {0: 'clean', 1: 'a target could not be scanned', 2: 'findings'}.get(int(code), 'other'),
        'raw_entries': len(data) if isinstance(data, list) else None, 'distinct_findings': len(seen),
        'by_antipattern': dict(rules), 'by_file': dict(files), 'severities': dict(collections.Counter(f.get('severity') for f in (data or []))), 'stderr_lines': len(open(err).read().splitlines())}
json.dump(meta, open(out.replace('.json', '.meta.json'), 'w'), indent=1)
print(json.dumps(meta, indent=1))
PY
exit "$code"
