#!/usr/bin/env bash
# Recorded stop method for every temporary server started for the critique.
HERE="$(cd "$(dirname "$0")" && pwd)"
[ -f "$HERE/next.pid" ] && kill "$(cat "$HERE/next.pid")" 2>/dev/null && echo "stopped next $(cat "$HERE/next.pid")"
pkill -f "[n]ext start -p 3000" 2>/dev/null || true
pkill -f "[m]ock_api.py" 2>/dev/null && echo "stopped mock api" || true
pkill -f "[i]mpeccable.*live-server" 2>/dev/null && echo "stopped impeccable live-server" || true
rm -f "$HERE/next.pid"
