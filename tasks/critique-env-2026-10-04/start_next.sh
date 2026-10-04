#!/usr/bin/env bash
# Start the production Next server (http://localhost:3000) against the mock API, in its own session/process group,
# and record its PID. Build first: (cd ../../frontend && npm ci && npm run build) with env.sh sourced and the mock running.
# The child writes its own PID into next.pid (not $!), so the file is correct whether or not setsid had to fork.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/env.sh"
if [ -f "$HERE/next.pid" ] && [ -d "/proc/$(tr -dc '0-9' < "$HERE/next.pid")" ]; then
  echo "next already running (pid $(cat "$HERE/next.pid"))"; exit 0
fi
cd "$HERE/../../frontend"; rm -f "$HERE/next.pid"
setsid bash -c 'echo $$ > "$1"; exec npx next start -p 3000' _ "$HERE/next.pid" > "$HERE/next-start.log" 2>&1 < /dev/null &
for _ in $(seq 1 60); do
  [ -s "$HERE/next.pid" ] && curl -sS -o /dev/null -m 2 http://localhost:3000/ 2>/dev/null && { echo "next up (pid $(cat "$HERE/next.pid"))"; exit 0; }
  sleep 0.5
done
echo "next did not come up"; tail -20 "$HERE/next-start.log"; exit 1
