#!/bin/bash
# ONE documented initialization of the E8 guard (run exactly once, at Stage 3 start, after prerequisites pass).
# Sets state.real_cli_invocations to the reconciled prior count (287, see accounting-reconciliation.md),
# accounting_reconciled=true, then config.enabled=true. Never re-run; never reset the counter or a latch.
set -euo pipefail
G=<judge-checkout>/work/e8/e8-judge-guard
[ -f $G/initialization-record.json ] && { echo "already initialized; refusing"; exit 2; }
python3 - "$G" <<'PY'
import json,sys,hashlib,datetime
from pathlib import Path
G=Path(sys.argv[1]); st=json.loads((G/'state.json').read_text()); cfg=json.loads((G/'config.json').read_text())
assert st=={'accounting_reconciled':False,'real_cli_invocations':0,'stop_reason':None,'completed':[]}, st
assert cfg['enabled'] is False and cfg['ceiling']==601 and cfg['real_cli']=='/opt/claude-code/bin/claude'
assert hashlib.sha256((G/'claude').read_bytes()).hexdigest()=='c0ade9e8d278683e8ccdf9546b97e4b65c496a7c55c195885b4bfa1a38d4c138'
before_state=dict(st); before_cfg=dict(cfg)
st['real_cli_invocations']=287; st['accounting_reconciled']=True   # stop_reason stays null, completed stays []
(G/'state.json').write_text(json.dumps(st,sort_keys=True)+'\n')
cfg['enabled']=True; (G/'config.json').write_text(json.dumps(cfg,indent=2)+'\n')
rec={'initialized_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'state_before':before_state,'state_after':st,'config_before':before_cfg,'config_after':cfg,
     'prior_count_provenance':'accounting-reconciliation.md: 140x2 reused E2 mains + founder original probe + my 4 probes (18:42, 18:45 x2, 19:09) + 2 killed in-flight calls of the aborted first control-1 launch = 287',
     'ceiling':601,'remaining_allowance':601-287,'shim_sha256':'c0ade9e8d278683e8ccdf9546b97e4b65c496a7c55c195885b4bfa1a38d4c138','real_cli':cfg['real_cli'],'real_cli_version':'2.1.278'}
(G/'initialization-record.json').write_text(json.dumps(rec,indent=2)+'\n'); print(json.dumps(rec,indent=1))
PY
