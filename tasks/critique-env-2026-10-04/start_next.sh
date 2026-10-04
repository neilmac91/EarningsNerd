#!/usr/bin/env bash
# Start the production Next server (http://localhost:3000) against the mock API, in its own session/process group, and
# record its identity in next.proc (see lifecycle.sh). Linux only. Next is launched directly from node_modules (not npx) so
# the recorded command line is stable. Build first with env.sh sourced and the mock running:
# (cd ../../frontend && npm ci && npm run build). An existing record is honoured only when it still verifies as this
# environment's own server; a stale record is removed, a mismatching one is set aside as next.proc.rejected.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd -P)"
source "$HERE/lifecycle.sh"; lc_require_linux
source "$HERE/env.sh"
FRONTEND="$(cd "$HERE/../../frontend" && pwd -P)"
REC="$HERE/next.proc"
set +e; lc_verify "$REC" "next" "$FRONTEND"; rc=$?; set -e
case $rc in
  0) echo "next already running (pid $LC_PID, verified)"; exit 0 ;;
  3) ;;
  5) echo "next: stale record ($LC_REASON); removing it"; rm -f "$REC" ;;
  4|6) lc_reject_record "$REC" "next" "$LC_REASON" ;;
esac
cd "$FRONTEND"; rm -f "$HERE/next.pid.tmp"
[ -f "$FRONTEND/node_modules/next/dist/bin/next" ] || { echo "next: node_modules/next is missing; run npm ci in $FRONTEND"; exit 1; }
# Launch Next's bin directly (not via npx) so the server is a single process that execs nothing else; Next then sets its
# process title to "next-server (v…)", and lifecycle.sh records that stable command line.
setsid bash -c 'echo $$ > "$1"; exec node node_modules/next/dist/bin/next start -p 3000' _ "$HERE/next.pid.tmp" > "$HERE/next-start.log" 2>&1 < /dev/null &
for _ in $(seq 1 40); do [ -s "$HERE/next.pid.tmp" ] && break; sleep 0.1; done
pid="$(tr -dc '0-9' < "$HERE/next.pid.tmp" 2>/dev/null || true)"; rm -f "$HERE/next.pid.tmp"
[ -n "$pid" ] || { echo "next: child did not report its pid"; tail -20 "$HERE/next-start.log"; exit 1; }
ready=0
for _ in $(seq 1 60); do
  curl -sS -o /dev/null -m 2 http://localhost:3000/ 2>/dev/null && { ready=1; break; }
  [ -d "/proc/$pid" ] || break
  sleep 0.5
done
if ! lc_write_record "$REC" "$pid" "next" "$FRONTEND"; then
  if [ ! -d "/proc/$pid" ]; then echo "next: pid $pid exited during start-up (port in use? see next-start.log):" >&2; tail -20 "$HERE/next-start.log" >&2; exit 1; fi
  echo "next: started pid $pid but could not verify its identity; not recorded, not signalled. Inspect and stop it manually (pid kept in next.unverified)." >&2
  echo "$pid" > "$HERE/next.unverified"; tail -20 "$HERE/next-start.log"; exit 1
fi
[ "$ready" = 1 ] && { echo "next up (pid $pid, recorded in next.proc)"; exit 0; }
echo "next did not answer on :3000; record kept so stop_env.sh can stop it"; tail -20 "$HERE/next-start.log"; exit 1
