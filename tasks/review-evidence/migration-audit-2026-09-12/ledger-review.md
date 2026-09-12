# Migration ledger audit — 2026-09-12

Read-only audit of GitHub main `8e9ad24cb643688b7cbc146e0ecd1cfe4a2d069f`, migration PRs #809–#813 and the backend-deploy implication of #814. Inputs were retrieved from exact GitHub contents/PR/run/job APIs; source copies and API responses live under `work/migration-ledger-read/`. No model calls, console actions, remote writes or source edits were performed. This is ledger evidence, not a substitute for the root agent's code audit/full gate.

## Must-fix before the next release or paid assessment

### M1 — Latest-production handover points at the wrong deploy

`tasks/handover-astra-2026-09-11-prompt.md:44` identifies production as the #812 revision while excluding #814 from audit beyond a note. #814 actually adds `backend/app/routers/auth.py` registration metadata and a backend test and deploys revision `earningsnerd-backend-00329-cx2`. Using the instruction would verify or attribute the wrong serving release before the next serial backend merge.

Refutation 1: read #814's body independently; it explicitly describes the new registration API and backend gate, so the landing-page title does not establish frontend-only scope. Refutation 2: actual deploy job103057415505 reports migrations0/39, revision00329-cx2 at100%, and healthy detailed health. #815 explicitly skips backend deployment, so it does not restore #812. Append a dated correction; do not rewrite frozen history. This audit verifies the historical Actions evidence, not today's console traffic or an independent historical curl.

### M2 — New instructions tell the next agent to reimplement/reassess merged work

`tasks/handover-astra-2026-09-11-prompt.md:61,169–170`, `tasks/deepseek-v41-flash-migration-2026-09-10.md:224,226`, and September10 `tasks/todo.md:35` call eval-error-outcome and reported-metric d local/prepared. They direct rebase/re-measure as if unreleased. Failure scenario: duplicate error-outcome implementation or an unnecessary third assessment of already-released #799.

Refutation 1: fresh GitHub PR796/799 APIs confirm merged squashes295daaaa1e67ef8cc89358819646d32a9edddf94 /3917cce5dbb58934a18b463c3cc7ab457ab0dde1. Refutation 2: current runner's application-status:error path is already present and existing September9 todo records both exact merges and verified revisions. Actual unfinished #805 remains separate. Correct the active continuation instructions with a dated superseding note; do not redo these releases.

### M3 — W10 provider-call/spend and elapsed-time claims omit failed outer attempts

`backend/evals/runner.py:336,394–406,241–259,412–432`; `tasks/review-evidence/deepseek-v41-flash-2026-09-10/w10-thinking-mode-readout.md:21,48`. The slim JSON has 11 retried outcomes and two final timeouts, but `provider_calls=79` sums only surviving provider_usage rows. Two terminal errors carry `provider_usage=null`; the 76 scored rows already contain three unknown-usage calls. Exception handling drops collected call records and outer retry retains only final outcome usage. The claimed approximately$0.60/79calls is consequently not a complete measured bill. Likewise36.779s is final-attempt latency, not full user wait including prior timeout plus5s retry delay. In an adoption decision this understates the reliability/cost penalty; the decision to keep thinking off remains supported.

Refutation 1: independently recounted all78 rows:76 scored,2errors,11retried,79recordedcalls,3recordedunknowncalls; JPM0 and ASML2 have no usage. The nine successful outer retries generally show only one provider call despite a prior TimeoutError. Refutation 2: fresh runner control-flow read shows usage summarization occurs after awaited generation and is bypassed on exception; outer retry overwrites the outcome and preserves first_latency only. This proves the missing-record mechanism rather than assuming every timeout was billed. Unknown historical usage cannot be invented. Fix future accounting and append a readout qualification; preserve the frozen slim report.

## Should-fix / evidence limitations

### S1 — Flash source SHA does not identify the measured working tree

`backend/evals/baselines/README.md:11–12`, Flash report harness and `baseline_scores.json` claim sourcea811faf; the same Flash report contains per-attempt provider_usage introduced in f134983. Pro arm records f134983. Thus “same code” can mean identical generation code, but a clean measured Flash commit is not established.

Refutation 1: API compare a811faf...f134983 changes observer/harness/tests/docs only, not generator prompts; this refutes a demonstrated prompt mismatch. Refutation 2: the older committed runner lacks the new usage capture while the Flash report has it, so matching HEAD metadata cannot certify its effective working tree. Preserve source_sha as recorded and explicitly note the unrecorded working-tree prerequisite; do not fabricate a replacement SHA. The pin's full candidate summary and harness exactly match the stored Flash report, and its timing precedes #810 normalizer/#812 telemetry: no false pin mismatch finding.

### S2 — Historical full-gate/independent verification evidence is incomplete

PR809–812 bodies explicitly report `python -m pytest` with39skipped and2deselected, not the requested four-PostgreSQL/performance gate. Their bodies have no mutation tails and no exact post-merge independent health output. Refutation 1: actual main CI/deploy jobs are successful with healthy CI curls, so this is not a red deployment. Refutation 2: issue-comment pages contain bot/Vercel notices, not the missing independent curl or local full-gate evidence. Do not claim those checks happened. Root's present full gate can resolve present-state validation, but cannot retroactively establish historical runs. No observed overlap in backend deployment sequencing: each successor merge is after predecessor deploy completion.

## Nits

N1: ADR0008:27–28 quotes Flash forward fidelity0.923 and depth0.936; actual frozen summary and independently recounted score means are0.9103 and0.9316. Refutation1: tracked report summary differs. Refutation2: averaging per-row scores reproduces the report, not ADR. PR809's table carries the correctly rounded0.910/0.932. Append corrected figures.

N2: baseline README:12 says the Pro arm ran “minutes before” Flash, but report stamps are15:43:18 vs15:35:41. Refutation1: filenames alone could be misleading; refutation2: report/pin snapshot records also identify Flash15:35:41 and no raw start log establishing reverse chronology is retained here. State report stamps rather than an unsupported execution ordering.

## Verified or refuted candidates

The W10 principal figures reproduce:76/78scored,11outer retries,mean completion8749.1,mean reasoning4712.4605,max8029,mean latency36.779,forward fidelity0.9803,citation0.9645. The non-thinking reference has78/78,0retry,3894.3completion,14.540s,forward0.9103,citation0.9061. These are deterministic scorer outcomes, not a strong-judge or financial-quality verdict; judge=false in both. Token mean difference and scorer gain are descriptive, not proof that reasoning alone caused them: output cap and temperature differ and the arms predate/follow other code changes.

The monitoring recipe is correctly described as unprovisioned: `docs/OPERATIONS.md:119` explicitly says one-time setup, not applied by CI. Todo W7 claims a recipe, not a created dashboard/alert. No infrastructure-existence finding retained. No console check was attempted.

The Flash pin exactly copies its recorded summary/harness. Archived5Sept reference and newer cutover model remain distinct. Post-#810 rescoring may differ legitimately from the older Flash pin; do not alter the baseline to hide a candidate regression.

All backend deploys below show migrations applied=0 skipped=39, 100% revision traffic and healthy CI detailed health. The docs-only #813/#815 deploy jobs explicitly skip. All actual main CI runs completed success.

| PR | Merge SHA | Main CI | Deploy job | Revision / result |
|---|---|---|---|---|
| #809 | `ea7a715f7c2ba828715666e3576d24e994010090` | 34507894761 | 102975560425 | earningsnerd-backend-00325-75d |
| #810 | `3605465ae18958aa7007374de706d7219d78282b` | 34512371710 | 102990435178 | earningsnerd-backend-00326-694 |
| #811 | `465800f5642cb9e1a26efb1fbea57f5c54158ba5` | 34513076190 | 102992821185 | earningsnerd-backend-00327-4tk |
| #812 | `1c3544bc995d787e1169dcb3e2e37f215d01935f` | 34514224880 | 102996595346 | earningsnerd-backend-00328-9lx |
| #813 | `440b717aa8cc9569bdd894b9bf1b6e00ac5a7d77` | 34516699021 | 103004807590 | No backend changes — skipped |
| #814 | `d26289e5345eaf75986d38ba674e77574c272be6` | 34532285336 | 103057415505 | earningsnerd-backend-00329-cx2 |
| #815 | `8e9ad24cb643688b7cbc146e0ecd1cfe4a2d069f` | 34580374370 | 103203221461 | No backend changes — skipped |

PR bodies, comments, exact deploy logs, full slim measurements and source documents are retained locally for root reconciliation. No additional paid assessment is needed to establish these ledger corrections.
