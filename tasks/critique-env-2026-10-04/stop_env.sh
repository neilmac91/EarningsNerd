#!/usr/bin/env bash
# Stop only the processes this environment started. Each server is identified by the PID file its start script
# wrote; the PID's /proc cmdline is checked against the expected command before anything is signalled, and the
# process GROUP the start script created (setsid) is terminated so child processes go too. No pattern kills:
# an unrelated process whose command line merely mentions "mock_api.py" or "next start" is never touched.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
stop_one() { # <pidfile> <expected cmdline substring> <label>
  local pidfile="$1" expect="$2" label="$3" pid pgid cmd
  [ -f "$pidfile" ] || { echo "$label: not started by this environment (no $(basename "$pidfile"))"; return 0; }
  pid="$(tr -dc '0-9' < "$pidfile")"
  if [ -z "$pid" ] || [ ! -d "/proc/$pid" ]; then echo "$label: pid ${pid:-?} not running; removing stale $(basename "$pidfile")"; rm -f "$pidfile"; return 0; fi
  cmd="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  case "$cmd" in
    *"$expect"*) ;;
    *) echo "$label: pid $pid is not ours (cmdline: ${cmd:-unreadable}); leaving it alone"; rm -f "$pidfile"; return 0 ;;
  esac
  pgid="$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ')"
  if [ -n "$pgid" ] && [ "$pgid" = "$pid" ]; then kill -TERM -- "-$pgid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
  else kill -TERM "$pid" 2>/dev/null || true; fi
  for _ in $(seq 1 40); do [ -d "/proc/$pid" ] || break; sleep 0.25; done
  if [ -d "/proc/$pid" ]; then kill -KILL "$pid" 2>/dev/null || true; sleep 0.2; fi
  rm -f "$pidfile"; echo "$label: stopped pid $pid (process group $pgid)"
}
stop_one "$HERE/next.pid" "next start" "next"
stop_one "$HERE/mock.pid" "mock_api.py" "mock api"
# An Impeccable live server is stopped through its own launcher, and only when this environment recorded starting one
# (touch live-server.started after `impeccable live-server --background`).
if [ -f "$HERE/live-server.started" ]; then
  L="${IMPECCABLE_LAUNCHER:-}"
  [ -z "$L" ] && L="$(ls -d "$HOME"/.claude/plugins/cache/impeccable/impeccable/*/skills/impeccable/scripts/impeccable 2>/dev/null | sort | tail -1 || true)"
  if [ -n "$L" ] && [ -x "$L" ]; then "$L" live-server stop > /dev/null 2>&1 && echo "impeccable live-server: stopped" || echo "impeccable live-server: stop command failed"; else echo "impeccable live-server: launcher not found; stop it with: <launcher> live-server stop"; fi
  rm -f "$HERE/live-server.started"
fi
