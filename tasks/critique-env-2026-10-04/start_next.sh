#!/usr/bin/env bash
# Start the production Next server (http://localhost:3000) against the mock API, in its own session/process group, and
# record its identity in next.proc (see lifecycle.sh). Linux only. Next is launched directly from node_modules (not npx) so
# the recorded command line is stable. Build first with env.sh sourced and the mock running:
# (cd ../../frontend && npm ci && npm run build). An existing record is honoured only when it still verifies as this
# environment's own server; a stale record is removed, a mismatching or malformed one is set aside as
# next.proc.rejected.<timestamp>. Exit codes: 0 up and recorded | 1 failed (died, unverifiable, port taken) | 3 recorded but
# not answering within the readiness budget (stop_env.sh can still stop it).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd -P)"
source "$HERE/lifecycle.sh"; lc_require_linux
source "$HERE/env.sh"
FRONTEND="$(cd "$HERE/../../frontend" && pwd -P)"
REC="$HERE/next.proc"; TOKEN="next"
set +e; lc_verify "$REC" "$TOKEN" "$FRONTEND"; rc=$?; set -e
case $rc in
  0) echo "next already running (pid $LC_PID, verified)"; exit 0 ;;
  3) ;;
  5) echo "next: stale record ($LC_REASON); removing it"; rm -f "$REC" ;;
  4|6) lc_reject_record "$REC" "next" "$LC_REASON" ;;
  *) echo "next: unexpected verify status $rc; not starting" >&2; exit 1 ;;
esac
if lc_leftovers "$HERE" next > /dev/null; then echo "next: earlier refusals need attention (starting anyway):"; lc_leftovers "$HERE" next; fi
[ -f "$FRONTEND/node_modules/next/dist/bin/next" ] || { echo "next: node_modules/next is missing; run npm ci in $FRONTEND"; exit 1; }
TMP="$HERE/next.pid.$$.tmp"; rm -f "$TMP"
cd "$FRONTEND"
# Launch Next's bin directly (not via npx) so the server is a single process that execs nothing else; Next then sets its
# process title to "next-server (v…)", and lifecycle.sh records that stable command line.
setsid bash -c 'echo $$ > "$1"; exec node node_modules/next/dist/bin/next start -p 3000' _ "$TMP" > "$HERE/next-start.log" 2>&1 < /dev/null &
launcher=$!
while [ ! -s "$TMP" ] && [ -d "/proc/$launcher" ]; do sleep 0.1; done
for _ in $(seq 1 20); do [ -s "$TMP" ] && break; sleep 0.1; done
pid="$(cat "$TMP" 2>/dev/null || true)"; pid="${pid%$'\n'}"; rm -f "$TMP"
[[ "$pid" =~ ^[1-9][0-9]{0,8}$ ]] || { echo "next: child did not report a valid pid ('${pid}')"; tail -20 "$HERE/next-start.log"; exit 1; }
ready=0
for _ in $(seq 1 60); do
  lc_pid_listens "$pid" 3000 && curl -sSf -o /dev/null -m 2 http://localhost:3000/ 2>/dev/null && { ready=1; break; }
  [ -d "/proc/$pid" ] || break
  sleep 0.5
done
if ! lc_write_record "$REC" "$pid" "$TOKEN" "$FRONTEND"; then
  if [ ! -d "/proc/$pid" ]; then echo "next: pid $pid exited during start-up (port 3000 in use? see next-start.log):" >&2; tail -20 "$HERE/next-start.log" >&2; exit 1; fi
  echo "next: started pid $pid but could not verify its identity; not recorded, not signalled. Inspect and stop it manually (pid kept in next.unverified)." >&2
  echo "$pid" > "$HERE/next.unverified"; tail -20 "$HERE/next-start.log"; exit 1
fi
set +e; lc_verify "$REC" "$TOKEN" "$FRONTEND"; rc=$?; set -e
[ "$rc" = 0 ] || { echo "next: the record just written does not verify ($LC_REASON); see next.proc" >&2; exit 1; }
[ "$ready" = 1 ] && [ -d "/proc/$pid" ] && { echo "next up (pid $pid, recorded in next.proc; it owns the :3000 listener)"; exit 0; }
echo "next: pid $pid is recorded but did not own the :3000 listener and answer within 30 s; stop_env.sh can still stop it"; tail -20 "$HERE/next-start.log"; exit 3
