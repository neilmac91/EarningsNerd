#!/usr/bin/env bash
# Start the mock backend (http://localhost:${MOCK_PORT:-8010}) in its own session/process group and record its identity in
# mock.proc (see lifecycle.sh). Linux only. An existing record is honoured only when it still verifies as this environment's
# own server; a stale record is removed, a mismatching or malformed one is set aside as mock.proc.rejected.<timestamp> and a
# new server is started. Exit codes: 0 up and recorded | 1 failed (died, unverifiable, port taken) | 3 recorded but not
# answering within the readiness budget (stop_env.sh can still stop it).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd -P)"
source "$HERE/lifecycle.sh"; lc_require_linux
PORT="${MOCK_PORT:-8010}"; REC="$HERE/mock.proc"; TOKEN="mock_api.py"
set +e; lc_verify "$REC" "$TOKEN" "$HERE"; rc=$?; set -e
case $rc in
  0) echo "mock api already running (pid $LC_PID, verified)"; exit 0 ;;
  3) ;;
  5) echo "mock api: stale record ($LC_REASON); removing it"; rm -f "$REC" ;;
  4|6) lc_reject_record "$REC" "mock api" "$LC_REASON" ;;
  *) echo "mock api: unexpected verify status $rc; not starting" >&2; exit 1 ;;
esac
if lc_leftovers "$HERE" mock > /dev/null; then echo "mock api: earlier refusals need attention (starting anyway):"; lc_leftovers "$HERE" mock; fi
TMP="$HERE/mock.pid.$$.tmp"; rm -f "$TMP"
cd "$HERE"
setsid bash -c 'echo $$ > "$1"; exec python3 mock_api.py' _ "$TMP" > "$HERE/mock_api.stdout" 2>&1 < /dev/null &
launcher=$!
while [ ! -s "$TMP" ] && [ -d "/proc/$launcher" ]; do sleep 0.1; done
for _ in $(seq 1 20); do [ -s "$TMP" ] && break; sleep 0.1; done
pid="$(cat "$TMP" 2>/dev/null || true)"; pid="${pid%$'\n'}"; rm -f "$TMP"
[[ "$pid" =~ ^[1-9][0-9]{0,8}$ ]] || { echo "mock api: child did not report a valid pid ('${pid}')"; tail -20 "$HERE/mock_api.stdout"; exit 1; }
ready=0
for _ in $(seq 1 40); do
  if lc_pid_listens "$pid" "$PORT" && curl -sSf -m 2 "http://localhost:$PORT/health" 2>/dev/null | python3 -c "import json,sys; sys.exit(0 if json.load(sys.stdin).get('pid') == $pid else 1)" 2>/dev/null; then ready=1; break; fi
  [ -d "/proc/$pid" ] || break
  sleep 0.25
done
if ! lc_write_record "$REC" "$pid" "$TOKEN" "$HERE"; then
  if [ ! -d "/proc/$pid" ]; then echo "mock api: pid $pid exited during start-up (port $PORT in use? see mock_api.stdout):" >&2; tail -20 "$HERE/mock_api.stdout" >&2; exit 1; fi
  echo "mock api: started pid $pid but could not verify its identity; not recorded, not signalled. Inspect and stop it manually (pid kept in mock.unverified)." >&2
  echo "$pid" > "$HERE/mock.unverified"; tail -20 "$HERE/mock_api.stdout"; exit 1
fi
set +e; lc_verify "$REC" "$TOKEN" "$HERE"; rc=$?; set -e
[ "$rc" = 0 ] || { echo "mock api: the record just written does not verify ($LC_REASON); see mock.proc" >&2; exit 1; }
[ "$ready" = 1 ] && [ -d "/proc/$pid" ] && { echo "mock api up (pid $pid, recorded in mock.proc; it owns the :$PORT listener and /health reports the same pid)"; exit 0; }
echo "mock api: pid $pid is recorded but did not own the :$PORT listener and answer /health with its own pid within 10 s; stop_env.sh can still stop it"; tail -20 "$HERE/mock_api.stdout"; exit 3
