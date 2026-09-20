#!/bin/bash
# finish-stage.sh <stage-dir-name> <original report> <label> <run_id> <artifact> <source-note> [prior judged.json]
# Consolidates per-slot outputs (no judging), runs the analysis/overlap/receipt scripts, copies deliverables.
set -euo pipefail
S=/tmp/claude-0/-home-user-EarningsNerd/40bee418-8bbf-584f-97e5-bb7b21721c91/scratchpad; W=$S/earningsnerd-fable-handoff-20260919
STAGE=$1; REPORT=$2; LABEL=$3; RUN=$4; ART=$5; NOTE=$6; PRIOR=${7:-}
D=$W/work/$STAGE; OUT=$D/consolidated; mkdir -p $OUT
cd $W/backend
PYTHONPATH=$W/backend SKIP_REDIS_INIT=true SECRET_KEY=offline-judge-run-not-a-real-secret-key PYTHONPYCACHEPREFIX=$D/.pycache-consolidate \
  $W/.venv/bin/python $W/work/tools/consolidate.py "$REPORT" $D/packets/packets-index.json $D/slots $OUT $PRIOR
cd $W/work
python3 $S/analyze_judged.py $OUT/judged.json > $OUT/analysis.txt
python3 $W/work/overlap_detail.py $OUT/judged.json > $OUT/overlap-detail.txt
python3 $S/receipt.py "$LABEL" "$RUN" "$ART" "$REPORT" "$OUT" "$NOTE" > /dev/null
cp $D/ledger.jsonl $OUT/execution-ledger.jsonl; cp $D/resume-manifest.json $OUT/resume-manifest.json; cp $D/packets/packets-index.json $OUT/packets-index.json
DEL=$W/deliver/claude-judge-results/$STAGE; mkdir -p $DEL; cp $OUT/{judged.json,judged.md,receipt.md,analysis.txt,overlap-detail.txt,execution-ledger.jsonl,resume-manifest.json,packets-index.json} $DEL/
sha256sum $DEL/* > $DEL/sha256.txt
echo "finished $STAGE -> $DEL"; head -25 $OUT/receipt.md
