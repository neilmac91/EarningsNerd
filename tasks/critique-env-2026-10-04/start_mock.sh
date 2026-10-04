#!/usr/bin/env bash
# Start the mock backend (http://localhost:${MOCK_PORT:-8010}) in its own session/process group and record its PID.
# The child writes its own PID into mock.pid (not $!), so the file is correct whether or not setsid had to fork.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$HERE/mock.pid" ] && [ -d "/proc/$(tr -dc '0-9' < "$HERE/mock.pid")" ]; then
  echo "mock api already running (pid $(cat "$HERE/mock.pid"))"; exit 0
fi
cd "$HERE"; rm -f "$HERE/mock.pid"
setsid bash -c 'echo $$ > "$1"; exec python3 mock_api.py' _ "$HERE/mock.pid" > "$HERE/mock_api.stdout" 2>&1 < /dev/null &
for _ in $(seq 1 40); do
  [ -s "$HERE/mock.pid" ] && curl -sS -m 2 "http://localhost:${MOCK_PORT:-8010}/health" > /dev/null 2>&1 && { echo "mock api up (pid $(cat "$HERE/mock.pid"))"; exit 0; }
  sleep 0.25
done
echo "mock api did not come up"; tail -20 "$HERE/mock_api.stdout"; exit 1
