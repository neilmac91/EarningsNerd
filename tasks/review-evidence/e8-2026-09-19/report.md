# E8 bounded pilot artifact audit — 2026-09-19

The single dispatched pilot completed successfully. Both new n corpora contain 70 unique scored slots, with 0 errors and 0 missing: 140 total. All corresponding retained source channels match their pinned E2 o-control rows. This is successful measurement capture, not a semantic-quality verdict.

Run: https://github.com/neilmac91/EarningsNerd/actions/runs/35465430465
Job: https://github.com/neilmac91/EarningsNerd/actions/runs/35465430465/job/105956770245
Artifact: `e8-usd5-pilot-35465430465`, downloaded to this directory.
Source: `3a079a90f45838bc406db57a8b58ca13339fe35f` (never-merge PR #923).
Job start: 2026-09-19T19:47:37Z; completion: 2026-09-19T20:03:41Z; conclusion: success.

| Corpus | Slots | Scored | Errors | Missing | Deterministic mean aggregate | SHA256 |
|---|---:|---:|---:|---:|---:|---|
| n1 |70|70|0|0|1.0|`fab392e8a79614a5ceaa5919da7052603f3d280002fd3ed30183ff3dda276140`|
| n2 |70|70|0|0|1.0|`11fb4918cebe2316c36877ead522150334ac66621b69ef70e64c12e2b89fc47e`|

The deterministic aggregates are saturated and do not establish semantic safety or resolve Fable verdict variability. No judge calls were made during this task. Same-judge evaluation and the planned filing-level disagreement analysis remain separate work.

## Provider accounting

- Pre-run provider balance: USD 75.77, available=true, recorded in balance-before.json.
- 187 actual provider requests and 187 captured response bodies; all 187 usage_settled.
- 140 distinct filing/repeat slots with requests; evaluator retry count 0.
- Raw-request role classification by exact full system-message match to the committed owners: 140 primary calls and 47 attribution-verifier calls (28 in n1, 19 in n2), with no unclassified or actual section-recovery request. The legacy telemetry labels those verifier calls section_recovery; that label must not be reported as actual missing-section recovery. See request-roles.json for every request's classification.
- Provider identity: deepseek-flash for every request and response packet.
- Reported input tokens 5,472,195 = 5,412,208 cache-hit + 59,987 cache-miss; output 506,441; total 5,978,636.
- Conservative peak-price accounting upper bound: **USD 0.658198548**, within the shared **USD 5** ceiling. This is calculated from complete provider token usage at verified peak rates, not an invoice and not the evaluator's historical cost_usd=0 field.
- Unknown/reserved-but-unsettled amount: 0. Admission stop: null. Final programme snapshot exactly equals the ledger.
- Raw provider files: 376, 171,771,462 bytes including request/response captures, ledger and programme lock.

## Checks performed

The offline audit verified every captured request SHA, every recorded response SHA, complete SSE DONE or non-streaming packet usage, exact response identity, input/output reservation bounds, cache/total token arithmetic and settlement amount. It checked all 140 row-level input hashes against immutable E2 control artifacts and compared every scored row's retained excerpt, XBRL, statement evidence, 6-K class, provenance and coverage inventory to its control. Both reported source heads and control hashes match. No audit problems were found (`audit.json`: problems=[]).

The final ledger does not contain event timestamps, so historical concurrent reservation occupancy cannot be reconstructed independently from the final snapshot. The admission guarantee is supported by the reviewed transport code and its mutation-tested concurrent gate; this audit confirms the retained requests and final accounting. Actual settled cost is bounded using peak tariffs, not claimed as the exact account charge. No post-run balance read or new model call was made.

No rerun, restart, replacement generation, extra spend or PR closure was performed by this monitoring task. Parent may now close the never-merge draft after recording the result. Full evidence: audit.json, audit-output.txt, job.json, job.log, workflow-watch.log, both n-corpus files, programme-final.json, balance-before.json and provider/.
