# E8 prior real-CLI invocation reconciliation (operator attestation)

Environment: Claude Code remote Linux container (this judge session), real CLI `/opt/node22/bin/claude` ->
`/opt/claude-code/bin/claude`, version 2.1.278, auth `oauth_token` / `firstParty` (subscription; no
ANTHROPIC_API_KEY, no Bedrock/Vertex/Foundry routing). All judge and probe calls from this environment
were made by me (the judge agent) on 2026-09-19 UTC; the execution records are the harness logs
`work/judge-e2.log`, `work/judge-e2c2.log`, `work/judge-e1.log` and this conversation's tool records.
The unchanged harness (`_judge_with_retry`) makes up to two real CLI calls per attempt and does not
log the second call separately, so per-attempt call counts are bounded, not exact.

| # | Event (UTC) | Real CLI invocations | Charged to E8 ledger |
|---|---|---:|---:|
| a | Founder's original Mac availability probe (quota-exhausted; "the known original probe" in the handoff and measurement note) | 1 | 1 |
| b | 18:42 my availability probe (`Reply with exactly: OK`; is_error=false) | 1 | 1 |
| c | 18:45 my two concurrent probes (`OK1`, `OK2`; both is_error=false) | 2 | 2 |
| d | 18:48 first E2 control-1 launch aborted by me after ~26 s; two real CLI children (pids 942, 944) were started then killed, no verdict | 2 | 2 |
| e | 18:48-19:09 E2 control-1 (run 35461717484): 70 complete verdicts, zero errors; actual calls in [70, 140] | ≤140 | 140 (2 per reused main) |
| f | 19:09 my post-control-1 availability probe (is_error=false) | 1 | 1 |
| g | 19:13-19:36 E2 control-2 (run 35462609093): 70 complete verdicts, zero errors; actual calls in [70, 140] | ≤140 | 140 (2 per reused main) |
| h | 19:10-19:51 E1 baseline (run 35460844028): 60 complete, 10 quota errors (each error = 2 failed calls), 2 paused calls timed out and retried; actual calls in [82, 140] | ≤140 | 0 (separate programme, same subscription) |
| i | 23:54 onward: KO corrected stage (separate programme) | see `ko-corrected/ledger.jsonl` | 0 |
| j | E3 candidate stages (separate programme) | see `e3-candidate*/ledger.jsonl` | 0 |

Reconciled prior count charged to E8 = 140 × 2 (reused mains, both corpora) + 1 (a) + 1 (b) + 2 (c) + 2 (d) + 1 (f) = **287**.
Handoff baseline was 281 (140 × 2 + one probe); the six additional known calls (b, c, d, f minus the one
probe already counted) are added explicitly. Remaining allowance under the 601 ceiling: 601 − 287 = **314**
for 160 planned slots (worst case with every permitted internal retry: 320). If the allowance is
exhausted, E8 stops incomplete; the ceiling is not raised or reset.

Attestation: no other judge or probe invocations of `claude -p` were made from this environment. I cannot
observe calls made from other machines or sessions (e.g. the founder's Mac beyond the one known probe);
the E8 counter therefore covers this environment's history plus that one known external probe.
