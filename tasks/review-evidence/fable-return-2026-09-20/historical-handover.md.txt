# Handover — independent Fable judge session, 2026-09-19/20 (for the Astra chief engineering agent)

Status at handover (2026-09-20 ~00:30 UTC): the founder stopped this session at 50 completed KO packets
(session usage limit). Nothing in `backend/app`, `backend/prompts`, `backend/evals` or production was
changed. This PR carries only the handover, the evidence receipts/ledgers and the operator tooling used;
the large `judged.json` files were returned to the founder in the Claude conversation (see §9).

Judge contract for every verdict below: `cli:claude-fable-5-1`, judge contract version 2, unchanged
`evals.judge_report` at checkout `73cc31162c3dfe7ec497c8c88c43cf397afce4a7`, Claude CLI **2.1.278**
(`/opt/node22/bin/claude` -> `/opt/claude-code/bin/claude`, ELF), auth `oauth_token`/`firstParty`
(subscription; no API key, no cloud routing). Frozen file hashes verified before every call:
`judge_report.py 11a79f1e…`, `judge.py 7522f977…`, `runner.py 63b010b7…`, `weekly_readout.py 8b171455…`,
`golden_set.json e1ca0cfc…` (full values in `judge-handoff-2026-09-20/e8-pilot/accounting-reconciliation.md`
and the receipts).

## 1. Stage status

| Stage | Corpus / run | Result | Files |
|---|---|---|---|
| 0 | E2 control 1, run `35461717484` | **complete** 70/70, 38 negative (54.3%), G2 2 / G3 14 / G4 23 / G5 22; judged.json `d5c6a293…` | `judge-handoff-2026-09-20/e2/` |
| 0 | E2 control 2, run `35462609093` | **complete** 70/70, 42 negative (60.0%), G2 2 / G3 12 / G4 25 / G5 24; judged.json `15ec6a1c…` | `judge-handoff-2026-09-20/e2-control2/` |
| 0/4 | E1 baseline, run `35460844028` | **partial** 60/70 complete, 29 negative; 10 quota-error identities (below); judged.json `97e71836…` | `judge-handoff-2026-09-20/e1/` |
| 1 | KO corrected, run `35467365092` | **partial** 50/70 complete, 27 negative (54.0%), G2 0 / G3 13 / G4 14 / G5 15, zero judge errors; 20 identities unjudged (below); judged.json `5a0983c7…` | `judge-handoff-2026-09-20/ko-corrected/` |
| 2 | E3 candidate 1 (`35463689504`) and 2 (`35463743007`) | **not started**; inputs downloaded, hashed and provenance-verified; 70 singleton packets built per corpus | §5 |
| 3 | E8 (140 n mains + 20 duplicates) | **not started**; package verified, reuse mapping validated 140/140, guard relocated but **disabled and uninitialized**, accounting reconciled at 287 | §6 |
| 4 | E1 missing 10 | **not started**; 10 singleton packets built | §7 |

No verdict was re-run, no model substituted, no probe made after the founder's reset confirmation, no
credits purchased. Denominators are quoted from `judged_summary.judged`; partial outputs are not "clean".

## 2. Execution method (all stages after the reset)

Per the consolidated handoff: one unchanged-harness command per original-row singleton packet,
`--judge cli:claude-fable-5-1 --concurrency 1`, packets = `{"harness": <original header>, "results": [<row>]}`
(same shape as the E8 packager), built by `tools/build_packets.py` (records packet/row/request sha256 using the
harness's pure `build_judge_messages` via AST, exactly as the E8 packager does). `tools/run_queue.py` runs the
packets sequentially, inspects exit status + `judged.json` after every packet, appends `ledger.jsonl`, rewrites
`resume-manifest.json`, and halts on the first anomaly (nonzero exit, incomplete verdict, error text, quota
signature, guard latch). No outer retry. `tools/consolidate.py` merges slot outputs into the harness's own
`judged.json`/`judged.md` shape using the harness's `summarize`/`render_markdown`; missing identities are listed
under `consolidation.missing_identities` and counted as `errors` by `summarize`.

## 3. Stage 0 — preserved work

E2 controls: both delivered files match the handoff hashes; all 140 entries of
`e8-control-main-reuse-2026-09-19.json` were validated against my judged files (verdict equality, verdict sha,
request sha vs private map, row sha vs original E2 reports): 140/140, zero problems.

E1 partial (`work/judged-e1/judged.json`, sha256 `97e718364dea742f60a1c9b0a102c092bfa6fa56766445909f8984aae89a76ec`):
60 complete, 29 negative, gates G2 0 / G3 10 / G4 16 / G5 18. The 10 error rows carry the exact error text
`RuntimeError: claude CLI exit 1: ` (empty stderr = the documented Fable-limit signature) for
JD 20-F 0/1, SE 20-F 0/1, NVO 20-F 0/1, PDD 20-F 0/1, MELI 10-K 0/1. Two in-flight calls timed out while the
process was paused (SIGSTOP) to prioritise control 2 and were retried by the harness's own retry.

## 4. Stage 1 — KO corrected corpus (PARTIAL 50/70)

Input `eval_20260919T203644Z.json` sha256 `57049cab3a997fe4934680e5425ad7816035b6d35f0bb641ee29d0304875dd39`;
`ci-execution.txt` source `6af1393efc923b141397e84f91830515ebb50f89` = merge of `ee724436…` into main
`356663dd…`; whole-tree diff `6af1393e` vs `ee724436` is empty (verified with git). Report: 70/70 scored, zero
errors/retries, gate_fail_rate 0, verify/gate false, untraceable-dollar advisory 2.5, golden hash matches.
All 70 inputs fit the caps (max excerpt 260,154 incl. statement evidence; max summary 36,970; max XBRL 22,500).

Judged in report order, slots 001–050 (one command each, all exit 0, all complete contract-2 verdicts,
zero errors, no truncated grounding). **Unjudged (missing, not errors):** COIN 10-Q 0/1, BYND 10-Q 0/1,
BABA 20-F 0/1, ASML 20-F 0/1, TSM 20-F 0/1, JD 20-F 0/1, SE 20-F 0/1, NVO 20-F 0/1, PDD 20-F 0/1, MELI 10-K 0/1.
At the founder's stop the driver was terminated after slot 050; the harness for slot 051 (COIN 10-Q run 0)
had just started and was killed ~1 s in: one aborted KO-programme CLI call, no verdict, no output
(`ko-corrected/stop-at-50.log`, last ledger line). Output judged.json sha256
`5a0983c75ba48ba13e524dc061097cc0d66753a1ae9989d9547365fe42ee74cd`.

Attempt-level overlap (not clause recall): Fable G4 = 14, nonempty `attribution_audit.unverified` = 13,
both = 3, G4 without flag = 11, flag without G4 = 10 (lexical audit only; verifier off in this corpus).

### 4.1 Hand review of the two KO draws (both judged PASS, no gate failures)

Witnesses are in `ko-corrected/ko-hand-review-witnesses.txt` (retained excerpt + XBRL of the judged rows).

- **Segment table basis (both draws, supported):** five rows (North America, EMEA, Latin America, Bottling
  investments, A. Pacific) with revenue, operating income, change, commentary; no `Operating margin:` prefix
  and no segment margin ratio anywhere in either payload or in the three segment-table previews per draw.
  Revenue and change come from XBRL segment facts (NA 4,893 vs 4,361 = +12.2%; EMEA 3,012/2,657 = +13.4%;
  LatAm 1,678/1,477 = +13.6%; BI 1,640/1,463 = +12.1%; AP 1,508/1,421 = +6.1%). Operating income matches the
  MD&A narrative (NA $1,606M, EMEA $1,259M, LatAm $1,038M, AP $536M, BI $191M).
- **Commentary (both draws, supported):** every segment sentence traces to a source unit-case-volume
  sentence, including "Trademark Coca-Cola was even" (EMEA), "2% growth in Brazil, partially offset by declines
  of 5% in Argentina and 1% in Mexico", "8% growth in the Greater China and Mongolia operating unit", and BI
  "after considering the impact of structural changes … increased 4%" (footnote 5).
- **Why the old ratio was unsafe (context, not a claim about this corpus):** the E2 controls at `73cc311…`
  carried "33%/42%/62%/12%/36% operating margin —" prefixes computed as OI ÷ XBRL segment revenue. The filing
  itself reports segment operating margins of NA 32.8, EMEA 44.8, LatAm 61.9, AP 37.6, BI 11.7 (%), so the
  machine ratio matched for NA/LatAm/BI but not EMEA (41.8 vs 44.8) or AP (35.5 vs 37.6): the XBRL revenue
  denominator differs from the issuer's margin basis. The corrected corpus makes no segment-margin claim.
  The intermediate corpus `35466463047` (source `5b6d65dd…` = merge of `640d514c`, the first commit on the
  branch) already lacks the prefix but still carries the prompt's stale promise and prompt version `o`;
  the corrected head `ee724436` also removes the promise and stamps `summary-2026-09-p`. That older corpus
  was downloaded for this comparison only; it was not judged.
- **Unresolved (rendering interpretation):** the segment table column is headed "Change" without stating
  that it is *revenue* change. For A. Pacific it reads +6.1% while segment operating income fell to $536M from
  $624M (−14%); a reader could take the column as an operating-income change. This is a table-labelling
  ambiguity, not a false figure; neither draw asserts an OI change for that row.
- **Outlook citation (run 0, supported):** "Context: Item 2. MD&A - Operating Income and Operating Margin" is
  the source section heading for the guidance quote; no ratio claim. Both draws' only margin statements are
  the consolidated gross-margin sentence (63.0% from 62.6%) quoted from the source.
- Judge dimensions: run 0 faithfulness 5 / insight 3 / clarity 4 / specificity 5; run 1: 4 / 3 / 4 / 4.

### 4.2 Representative non-KO failures and #805 negative controls (judged subset)

Negative controls in the 50: AAPL PASS/PASS, AMZN FAIL/FAIL, BA PASS/PASS, JPM FAIL/FAIL, NVDA PASS/FAIL,
PFE FAIL/FAIL, PLTR FAIL/FAIL, RIVN PASS/FAIL; MELI unjudged. Full reasons in `ko-corrected/analysis.txt`;
spot checks in `ko-corrected/non-ko-spot-witnesses.txt`:

- FIGS 10-Q run 1 (G3×3, G4, G5) — **supported**: source gross profit 147,855 vs 102,246 = +44.6%; the summary
  states +44.7% in one table and 44.6% in another.
- JPM 10-K run 0/1 (G5 ROE/ROA) — **supported**: source table reports ROE 17%/18% and ROA 1.29/1.43; the
  summary presents 15.7% (prior 17.0%) computed on a different basis under the filing's measure name.
- PLTR 10-Q run 0 (G3 RPO) — **supported**: source says RPO "represents noncancelable contracted revenue";
  the summary says "subject to cancellation". Debt: the source states "no outstanding debt balances under the
  2014 Credit Facility"; the summary's "not zero debt" characterisation contradicts it (scope of the broader
  statement not re-checked by me: partially supported).
- AMZN 10-K run 0 (G5 Italy $1.1B scope) — **unresolved**: I did not locate the exact source sentence by
  pattern in the time available; the judge's reason is quoted verbatim in `analysis.txt`.
- BRK.B 10-K run 1 (G3, G5×4) and PLD 10-K run 0 (G3, G5×2, G4) — **not hand-checked**; reasons retained.

This is one corrected corpus: no improvement, causal effect or release approval is claimed.

## 5. Stage 2 — E3 candidates (not started; ready)

| Corpus | Run / artifact | Report | sha256 | Source |
|---|---|---|---|---|
| Candidate 1 | `35463689504` / `eval-report-35463689504` | `eval_20260919T192439Z.json` | `3f0b4d9c…077880f` (matches handoff) | `d59b0b13…` = merge of `8a8065b7…` into `f6f84aa1…`; whole-tree diff vs `8a8065b7` empty |
| Candidate 2 | `35463743007` / `eval-report-35463743007` | `eval_20260919T192513Z.json` | `2f4015e4…126e805` (matches handoff) | `8a8065b7…` directly |

Both: 70 unique identities, zero errors, verify true / gate false, golden hash matches, caps satisfied;
judge/golden files identical to the pinned checkout. Verifier flags: 18 (c1) and 21 (c2) attempts with
nonempty `unverified`. Packets built (`work/e3-candidate{1,2}/packets/`, indexes with request hashes) and
stage drivers written; nothing judged. Resume: `work/e3-candidate1/run-stage.sh` then `…candidate2/run-stage.sh`,
then `tools/finish-stage.sh e3-candidate1 <report> …`; compare with `tools/compare_runs.py o1=… o2=… e3c1=… e3c2=…`
(report per-run results and ranges only; generated claims differ across corpora).

## 6. Stage 3 — E8 (not started; prerequisites done except initialization)

- ZIP `6502d565…` (16,136,159 bytes, 321 entries) and mapping `a6738040…` (266,693 bytes) verified; queue
  `sha256.txt` all OK; private map `cc4d71e4…`; canonical order `e5931d55…` reproduced
  (`sha256(json.dumps(slots, sort_keys, compact))`); 280 mains + 20 duplicates; all 20 duplicate packets and
  request hashes equal their mains; 140 n/o channel matches. Shim `claude` sha256 `c0ade9e8…` unchanged.
- `e8-pilot/e8-execution-index.json`: the 160 slots to execute (140 n mains + 20 duplicates, incl. 10
  duplicates of reused o mains) in frozen order; the 140 o mains marked reused with verdict/request/report hashes.
- Guard relocated (`e8-pilot/relocation-record.json`): `real_cli` -> `/opt/claude-code/bin/claude` (2.1.278),
  `state_path` -> the scratch guard dir; `enabled` still **false**, `state.json` untouched
  (`accounting_reconciled false, real_cli_invocations 0`). The package's own offline invariant
  (`check_guard_offline.py`, fake CLI only) passes on this Linux host.
- Accounting (`e8-pilot/accounting-reconciliation.md`): reconciled prior count **287** = 140×2 reused mains +
  founder's original probe + my probes (18:42; 18:45 ×2; 19:09) + 2 killed in-flight calls of the aborted first
  control-1 launch. Remaining allowance 601 − 287 = 314 for 160 slots (worst case 320): stop incomplete if
  exhausted; never raise the ceiling. KO/E3/E1 calls are excluded from this ledger (same subscription).
- To start: run `e8-pilot/initialize-guard.sh` exactly once (sets 287 + reconciled + enabled, writes
  `initialization-record.json`), then `work/e8/run-stage.sh` (driver with `--guard-dir`, checks PATH shim
  resolution and guard state before/after every slot, stops on any latch/quota/anomaly), then
  `tools/e8_analyze.py`. Report n1/n2/o1/o2 separately, mains /280 and duplicates /20, judging-time and
  generation-time confounds; no causal claim.

## 7. Stage 4 — E1 missing identities (not started)

Ten singleton packets built from the original E1 report (sha256 `49ca1e62…`) for the 10 error identities;
driver `work/e1-stage/run-stage.sh`; consolidate with
`tools/finish-stage.sh e1-stage <E1 report> … work/judged-e1/judged.json` (prior file supplies the 60 first
valid verdicts; nothing is re-judged).

## 8. Invocation record for this session (all programmes; for quota bookkeeping)

| Programme | Calls (bounds) |
|---|---|
| Probes | 4 (18:42, 18:45 ×2, 19:09); none after the reset |
| Aborted first control-1 launch | 2 killed in flight |
| E2 control 1 / control 2 | [70, 140] each; 140 charged each in E8 accounting |
| E1 | [82, 140]; 10 quota-failed attempts (2 calls each) |
| KO corrected (after reset) | 50 packets, [50, 100] + 1 aborted call (slot 051) |

## 9. Where the evidence is

- This PR: `tasks/judge-handoff-2026-09-20/` — receipts, per-attempt analyses (every raw gate reason),
  overlap details, execution ledgers, resume manifests, packet indexes (with request hashes), KO hand-review
  witnesses, E1 partial analysis, E8 accounting/relocation/index/initialization script, and `tools/`.
- Returned to the founder in the Claude conversation (too large for the PR): full `judged.json`/`judged.md`
  for E2 control 1, E2 control 2, KO corrected (partial), E1 (partial 60/70).
- The working checkout (`<judge-checkout>`, a scratch directory in the judge session's container, pinned to
  `73cc3116…`, with the venv, all downloaded artifacts, packets, per-slot outputs and the relocated guard) may
  not survive the container's reclamation. If it is gone: re-clone at `73cc3116…`, install
  `backend/requirements.txt` + `requirements-eval.txt`, re-download the artifacts by run id (hashes above),
  rebuild packets with `tools/build_packets.py`, and resume; completed KO slots can be reconstructed from the
  delivered consolidated `judged.json` by copying rows into slot outputs, or simply re-consolidated from it.
  Do **not** re-judge identities that already hold a complete verdict.

## 10. Boundaries observed

No generation, no SEC re-fetch, no prompt/code/harness/golden edits, no re-pin, no CI reruns, no merges, no
production flags, no emails. No GitHub posts other than this handover PR, which the founder requested. The
judge model, contract and evidence channels were never changed; no verdict was re-run.
