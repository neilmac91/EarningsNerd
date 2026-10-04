#!/usr/bin/env bash
# Start the production Next server for the critique environment (port 3000) against the mock API (8010).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/env.sh"
cd "$HERE/../../frontend"
nohup npx next start -p 3000 > "$HERE/next-start.log" 2>&1 &
echo $! > "$HERE/next.pid"
for i in $(seq 1 40); do curl -sS -o /dev/null -m 2 http://localhost:3000/ && { echo "next up (pid $(cat "$HERE/next.pid"))"; exit 0; }; sleep 0.5; done
echo "next did not come up"; tail -20 "$HERE/next-start.log"; exit 1
