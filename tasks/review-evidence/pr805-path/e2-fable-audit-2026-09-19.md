# Delivered E2 controls: independent audit and E8 reuse

Both delivered judged reports pass the offline audit against their actual generation artifacts and frozen checkout `73cc31162c3dfe7ec497c8c88c43cf397afce4a7`. All 140 non-judge result records are exactly unchanged, including payload, raw sections, previews, excerpts, XBRL, statement evidence, source/coverage records, verifier audits, deterministic scores and identity. Original generation summary and all non-judge harness fields are unchanged. No generation error, missing/duplicate slot, judge error, incomplete input, invalid dimension or malformed gate reason was found. Received-file manifests match all ten delivered files' sizes/hashes.

| Observation | Control 1 | Control 2 |
|---|---:|---:|
| Complete attempts | 70/70 | 70/70 |
| Negative verdicts | 38/70 (54.3%) | 42/70 (60.0%) |
| G2 / G3 / G4 / G5 attempt counts | 2 / 14 / 23 / 22 | 2 / 12 / 25 / 24 |
| Finder-flagged attempts | 17 | 12 |
| Finder flag and G4 overlap | 7 | 6 |
| G4 without finder flag | 16 | 19 |
| Finder flag without G4 | 10 | 6 |

Pooled: 80/140 negative (57.1%); G4=48, finder-flagged=29, both=13, G4 without flag=35, flag without G4=16. These are **attempt-level sets**, not clause-level precision/recall. An overlapping attempt can have different clauses flagged by the finder and Fable. The audit preserves each full supplied gate reason; it checks structure/count consistency, not independent semantic truth of every judgment.

Source identity is verified: control 1's synthetic merge `e1b52bafb18c4d1cb69f489ccbdfd8ebd7407deb` has exactly the same full Git tree as `73cc3116`; control 2 reports `73cc3116` directly. Both bind frozen golden SHA `e1ca0cfcb7d0f9f51eff911586437c503a1945a64763284f48c9cd5524498b6b`; every retained excerpt rehashes and its coverage accession resolves to that cohort. Full raw SEC document bodies are not delivered, so declared document hashes remain declarations rather than independently rehashed bodies.

Actual frozen serialization was reconstructed offline by executing only the existing `_model_metrics`, `_maybe_judge` and `build_judge_messages` AST functions, replacing the network judge with a capture stub and replacing its constant import with the exact frozen literals. This includes default JSON escaping/indentation, removal of internal `financial_classification`, and the complete appended application-owned statement evidence. All 140 recorded length triples match this reconstruction. Maxima: excerpt 260,154/400,000 and XBRL 22,500/40,000 characters in both; summary 32,610/100,000 for control 1 and 32,912/100,000 for control 2. No truncation or exceeded input cap occurred in that serialization.

All 140 reconstructed system/user/request hashes equal the frozen E8 queue's corresponding o-condition requests. All four frozen judge/panel code-file hashes match. `e8-main-reuse-manifest.json` maps each existing verdict to its one exact E8 main slot, report hash, request hash, verdict hash and original batch time. **All 140 main verdicts are admissible for reuse under the stated normalized contract and exact-input criteria.** The 20 preselected duplicate slots remain independently due; existing mains must not be substituted for duplicates, and no selections/order/guard state were changed.

Both external receipts attest unmodified Fable contract 2, `cli:claude-fable-5-1`, CLI 2.1.278, concurrency 2 and subscription authentication. Normalized JSON independently confirms the alias and per-verdict contract 2; receipt-only facts include CLI build/auth/concurrency and actual execution environment. Raw CLI envelopes and a resolved backend snapshot were not delivered. That absence is an evidence limitation, not a blanket reuse refusal. Continue future E8 calls with **2.1.278 in the actual executing environment**; the disabled local guard points at 2.1.273 and must not be mistaken for an execution match. This audit installs/updates nothing and enables no guard.

Control 1 is stamped 2026-09-19T19:09:09.920346Z; control 2 is stamped 19:36:26.499175Z. These prior batch judgments precede the frozen randomized queue and later n judgments. Preserve those times/order strata; do not describe existing main calls as randomized/interleaved. Fine-grained subprocess order is unavailable. Receipt metadata supports comparability but cannot prove invariant service internals across time.

**Invocation accounting remains separate:** 140 complete verdicts do not establish exactly 140 real CLI invocations. Prior retries, probes and failed calls require actual execution attestation before shared guard accounting is reconciled. `prior_real_cli_invocations` is deliberately null. No new call or rerun is requested by this audit.

Detailed evidence: `control1-audit.json`, `control2-audit.json`, `frozen-panel-code-parity.json`, `e8-main-reuse-manifest.json`, and reproducible `audit.py` (argument 1 or 2). Earlier `audit.json`/`run.txt` are the initial control-1-only pass; the paired named receipts and this report are authoritative for reuse. All work is scratch-only; no tracked repository changes, calls, pinning or production actions.


## Publication note

The final paragraph describes the independent auditor's scratch-only work before the parent archived it. The committed counterparts are [control 1 audit](e2-control1-fable-audit-2026-09-19.json), [control 2 audit](e2-control2-fable-audit-2026-09-19.json), [frozen-code parity](e2-fable-frozen-code-2026-09-19.json), [reuse manifest](e8-control-main-reuse-2026-09-19.json), and [all normalized verdicts](e2-fable-verdicts-2026-09-19.json). The original auditor script/logs remain in `/private/tmp/earningsnerd-wave3-20260919/work/e2-control1-external-audit/`; full original judged reports and received-file hashes are preserved in the founder's Codex task outputs. This publication changes no frozen input, verdict or source hash.
