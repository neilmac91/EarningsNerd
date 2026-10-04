#!/usr/bin/env bash
# Stop only the servers this environment started and can still prove are its own (see lifecycle.sh). Linux only.
# For each record (next.proc, mock.proc) the live process must match every recorded identity field before its process
# group is signalled (SIGTERM, then SIGKILL after 10 s). A record whose process is gone is removed; a malformed record or
# a live process that does not match (reused pid, other directory, other command, not a group leader) is REFUSED: nothing
# is signalled and the record is moved to <name>.proc.rejected. Exit 0 when nothing was refused, 1 otherwise.
set -u
HERE="$(cd "$(dirname "$0")" && pwd -P)"
source "$HERE/lifecycle.sh"; lc_require_linux
refused=0
stop_one() { # <record> <expected cmd token> <expected cwd> <label>
  local rec="$1" token="$2" want_cwd="$3" label="$4" rc pid pgid
  lc_verify "$rec" "$token" "$want_cwd"; rc=$?
  case $rc in
    3) echo "$label: not started by this environment (no $(basename "$rec"))"; return 0 ;;
    5) echo "$label: $LC_REASON; removing stale $(basename "$rec")"; rm -f "$rec"; return 0 ;;
    4|6) lc_reject_record "$rec" "$label" "$LC_REASON"; refused=1; return 0 ;;
  esac
  pid="$LC_PID"; pgid="$LC_PGID"
  kill -TERM -- "-$pgid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
  for _ in $(seq 1 40); do [ -d "/proc/$pid" ] || break; sleep 0.25; done
  if [ -d "/proc/$pid" ]; then kill -KILL -- "-$pgid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true; sleep 0.2; fi
  rm -f "$rec"; echo "$label: stopped pid $pid (process group $pgid, verified owner)"
}
stop_one "$HERE/next.proc" "next" "$(cd "$HERE/../../frontend" 2>/dev/null && pwd -P)" "next"
stop_one "$HERE/mock.proc" "mock_api.py" "$HERE" "mock api"
# An Impeccable live server is stopped through its own launcher, and only when this environment recorded starting one
# (touch live-server.started after `impeccable live-server --background`).
if [ -f "$HERE/live-server.started" ]; then
  L="${IMPECCABLE_LAUNCHER:-}"
  [ -z "$L" ] && L="$(ls -d "$HOME"/.claude/plugins/cache/impeccable/impeccable/*/skills/impeccable/scripts/impeccable 2>/dev/null | sort | tail -1 || true)"
  if [ -n "$L" ] && [ -x "$L" ]; then "$L" live-server stop > /dev/null 2>&1 && echo "impeccable live-server: stopped" || echo "impeccable live-server: stop command failed"; else echo "impeccable live-server: launcher not found; stop it with: <launcher> live-server stop"; fi
  rm -f "$HERE/live-server.started"
fi
exit $refused
