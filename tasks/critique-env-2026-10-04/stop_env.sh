#!/usr/bin/env bash
# Stop only the servers this environment started and can still prove are its own (see lifecycle.sh). Linux only.
# For each record (next.proc, mock.proc) the live process must match every recorded identity field before its process
# group is signalled (SIGTERM, then SIGKILL after 10 s; "stopped" is reported only once no live member of the group is
# left). A record whose process is gone is removed. A malformed record or a live process that does not match (reused pid,
# other directory, other command, not a group leader) is REFUSED: nothing is signalled and the record is moved to
# <name>.proc.rejected.<timestamp>. Earlier refusals (<name>.proc.rejected.*) and unverified starts (<name>.unverified) are
# reported on every run until the operator removes the files. Exit 0 when nothing was refused or left over, 1 otherwise.
set -u
HERE="$(cd "$(dirname "$0")" && pwd -P)"
source "$HERE/lifecycle.sh"; lc_require_linux
refused=0
stop_one() { # <record> <expected cmd token> <expected cwd> <label> <name>
  local rec="$1" token="$2" want_cwd="$3" label="$4" name="$5" rc pid pgid live
  lc_verify "$rec" "$token" "$want_cwd"; rc=$?
  case $rc in
    0) ;;
    3) echo "$label: not started by this environment (no $(basename "$rec"))" ;;
    5) echo "$label: $LC_REASON; removing stale $(basename "$rec")"; rm -f "$rec" ;;
    4|6) lc_reject_record "$rec" "$label" "$LC_REASON"; refused=1 ;;
    *) echo "$label: unexpected verify status $rc; nothing done" >&2; refused=1 ;;
  esac
  if [ "$rc" != 0 ]; then
    if lc_leftovers "$HERE" "$name" > /dev/null; then echo "$label: leftovers from earlier runs need attention:"; lc_leftovers "$HERE" "$name"; refused=1; fi
    return 0
  fi
  pid="$LC_PID"; pgid="$LC_PGID"
  [[ "$pgid" =~ ^[1-9][0-9]{0,8}$ ]] || { echo "$label: refusing to signal malformed process group '$pgid'" >&2; refused=1; return 0; }
  kill -TERM -- "-$pgid" 2>/dev/null || true
  for _ in $(seq 1 40); do live="$(lc_group_live "$pgid")"; [ "$live" = 0 ] && break; sleep 0.25; done
  if [ "$live" != 0 ]; then
    kill -KILL -- "-$pgid" 2>/dev/null || true
    for _ in $(seq 1 12); do live="$(lc_group_live "$pgid")"; [ "$live" = 0 ] && break; sleep 0.25; done
  fi
  if [ "$live" != 0 ]; then
    echo "$label: SIGTERM and SIGKILL sent to process group $pgid but $live process(es) are still present; record kept" >&2; refused=1; return 0
  fi
  rm -f "$rec"; echo "$label: stopped pid $pid (process group $pgid, verified owner)"
  if lc_leftovers "$HERE" "$name" > /dev/null; then echo "$label: leftovers from earlier runs need attention:"; lc_leftovers "$HERE" "$name"; refused=1; fi
}
stop_one "$HERE/next.proc" "next" "$(cd "$HERE/../../frontend" 2>/dev/null && pwd -P)" "next" next
stop_one "$HERE/mock.proc" "mock_api.py" "$HERE" "mock api" mock
# An Impeccable live server is outside the identity scheme: it is stopped through its own launcher (best effort), and only
# when this environment recorded starting one (touch live-server.started after `impeccable live-server --background`).
if [ -f "$HERE/live-server.started" ]; then
  L="${IMPECCABLE_LAUNCHER:-}"
  [ -z "$L" ] && L="$(ls -d "${HOME:-/root}"/.claude/plugins/cache/impeccable/impeccable/*/skills/impeccable/scripts/impeccable 2>/dev/null | sort -V | tail -1 || true)"
  if [ -n "$L" ] && [ -x "$L" ]; then "$L" live-server stop > /dev/null 2>&1 && echo "impeccable live-server: stopped" || echo "impeccable live-server: stop command failed"; else echo "impeccable live-server: launcher not found; stop it with: <launcher> live-server stop"; fi
  rm -f "$HERE/live-server.started"
fi
exit $refused
