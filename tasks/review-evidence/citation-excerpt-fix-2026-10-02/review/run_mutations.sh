#!/bin/bash
SP=/tmp/claude-0/-home-user-EarningsNerd/4aaef390-9924-5295-aa90-251d71b700b2/scratchpad
cd /home/user/wt/cite-rev/backend
unset OPENAI_API_KEY DEEPSEEK_API_KEY OPENAI_BASE_URL ANTHROPIC_API_KEY
TESTS="tests/unit/test_copilot.py tests/unit/test_provenance_service.py tests/unit/test_copilot_prose_quotations.py tests/unit/test_forward_quote_gate.py"
for m in "$@"; do
  /home/user/venv/bin/python $SP/cite-rev/mutate.py $m || { echo "$m APPLY FAILED"; git checkout -- app; continue; }
  out=$(/home/user/venv/bin/python -m pytest -q -p no:cacheprovider $TESTS 2>&1)
  summary=$(echo "$out" | tail -1)
  failed=$(echo "$out" | grep -E "^FAILED" | sed -E 's/ - .*//' | sed 's#tests/unit/##' | head -12)
  echo "=== $m: $summary"; echo "$failed"
  git checkout -- app
  [ -f earningsnerd.db ] && mv earningsnerd.db $SP/stale-dbs/cite-rev-$(date -u +%Y%m%dT%H%M%SZ)-$m.db
  echo "$(date -u +%FT%TZ) cite-rev: mutation $m -> $summary (restored)" >> $SP/cite-rev-progress.md
done
git status --short
