#!/usr/bin/env bash
# Start the mock backend (http://localhost:${MOCK_PORT:-8010}) in its own session/process group and record its identity in
# mock.proc (see lifecycle.sh). Linux only. An existing record is honoured only when it still verifies as this environment's
# own server; a stale record is removed, a mismatching one is set aside as mock.proc.rejected and a new server is started.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd -P)"
source "$HERE/lifecycle.sh"; lc_require_linux
REC="$HERE/mock.proc"
set +e; lc_verify "$REC" "mock_api.py" "$HERE"; rc=$?; set -e
case $rc in
  0) echo "mock api already running (pid $LC_PID, verified)"; exit 0 ;;
  3) ;;
  5) echo "mock api: stale record ($LC_REASON); removing it"; rm -f "$REC" ;;
  4|6) lc_reject_record "$REC" "mock api" "$LC_REASON" ;;
esac
cd "$HERE"; rm -f "$HERE/mock.pid.tmp"
setsid bash -c 'echo $$ > "$1"; exec python3 mock_api.py' _ "$HERE/mock.pid.tmp" > "$HERE/mock_api.stdout" 2>&1 < /dev/null &
for _ in $(seq 1 40); do [ -s "$HERE/mock.pid.tmp" ] && break; sleep 0.1; done
pid="$(tr -dc '0-9' < "$HERE/mock.pid.tmp" 2>/dev/null || true)"; rm -f "$HERE/mock.pid.tmp"
[ -n "$pid" ] || { echo "mock api: child did not report its pid"; tail -20 "$HERE/mock_api.stdout"; exit 1; }
ready=0
for _ in $(seq 1 40); do
  curl -sS -m 2 "http://localhost:${MOCK_PORT:-8010}/health" > /dev/null 2>&1 && { ready=1; break; }
  [ -d "/proc/$pid" ] || break
  sleep 0.25
done
if ! lc_write_record "$REC" "$pid" "mock_api.py" "$HERE"; then
  if [ ! -d "/proc/$pid" ]; then echo "mock api: pid $pid exited during start-up (port in use? see mock_api.stdout):" >&2; tail -20 "$HERE/mock_api.stdout" >&2; exit 1; fi
  echo "mock api: started pid $pid but could not verify its identity; not recorded, not signalled. Inspect and stop it manually (pid kept in mock.unverified)." >&2
  echo "$pid" > "$HERE/mock.unverified"; tail -20 "$HERE/mock_api.stdout"; exit 1
fi
[ "$ready" = 1 ] && { echo "mock api up (pid $pid, recorded in mock.proc)"; exit 0; }
echo "mock api did not answer /health; record kept so stop_env.sh can stop it"; tail -20 "$HERE/mock_api.stdout"; exit 1
