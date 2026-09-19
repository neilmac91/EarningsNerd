# E8 frozen duplicate panel and judgment queue plan

Frozen 2026-09-19T20:02:13.120117+00:00; seed **20260919**. Offline preparation only: no model/judge invocation, CI call, source fetch or verdict inspection. n artifacts are not yet bound. The existing E2 generation reports were read only for identities, retained input channels and provenance. Historical manual diagnostics were known, but selection is entirely mechanical from identity keys; no selected identity was replaced on substantive grounds.

## Frozen selection and order

There are 280 main output slots (n/o × two corpora × 35 filings × two draws) and 20 duplicate occurrences. Each condition contributes ten duplicate outputs: three 10-K, three 10-Q, two 20-F and two 6-K; five outputs per corpus. The seed gives each condition corpus 1 two 10-K/one 10-Q and corpus 2 one 10-K/two 10-Q, with one of each foreign form in each corpus. These are balanced form/corpus output slots, not twenty distinct companies.

Identity keys include condition, corpus, ticker, filing type, frozen accession, candidate baseline and draw index. SHA256 of canonical JSON `{seed,domain,value}` ranks identities within each stratum; select the quota-lowest ranks. Separate hash domains derive output IDs, blind IDs and the judgment order. The 280 single occurrences plus twenty second occurrences are hash-sorted. The earlier occurrence of each selected output is designated main; its later occurrence is duplicate. This assigns labels before any judgment and guarantees the first completed substantive verdict remains main. The algorithm and complete map are in `e8-select-judge-panel.py` and `e8-judge-panel.json`; the condition-free dispatch order is `e8-judge-order.json`.

Core canonical SHA256: `a4d68b47f7524febbca1c45a8726fa633bdd56b0fc3a2d766f1a8a5bdc23f401`. Canonical blinded-order SHA256: `e5931d556f23889884682d65b113f954246fbae00910e7f671bc0f55df73caf4`. Artifact byte hashes are in `e8-judge-panel.sha256`. The shortest planned gap is 12 intervening slots; actual gaps may differ when pre-existing main judgments are reused.

| Condition | Corpus | Filing | Draw | Main order / blind ID | Duplicate order / blind ID |
| --- | --- | --- | --- | --- | --- |
| n | 1 | RIVN 10-K | 0 | 202 / `J-06465135d0517214` | 242 / `J-9a81d4ab2de07275` |
| n | 1 | TSLA 10-K | 1 | 54 / `J-fa664e8c96b591b0` | 288 / `J-f97efb73994ac7aa` |
| n | 1 | KO 10-Q | 1 | 20 / `J-babfb955a60617a4` | 68 / `J-4ee2877ff3abdb99` |
| n | 1 | TSM 20-F | 0 | 86 / `J-fdef1432d802a95b` | 118 / `J-110a831b0d11fe4f` |
| n | 1 | ASML 6-K | 0 | 36 / `J-560036636fd8f5ba` | 170 / `J-54f8416aeb656cf0` |
| n | 2 | BRK.B 10-K | 0 | 5 / `J-4ceb720c55caf532` | 82 / `J-d8958135bca3af8b` |
| n | 2 | F 10-Q | 0 | 80 / `J-59b7cba49777da86` | 110 / `J-d6c5b6f22879ec4e` |
| n | 2 | KO 10-Q | 1 | 124 / `J-d86b0958ddeeec73` | 159 / `J-44cb9fdf5ec28b53` |
| n | 2 | PDD 20-F | 0 | 94 / `J-81a3bd9458ab074b` | 107 / `J-7cdfc063d095fd87` |
| n | 2 | PDD 6-K | 1 | 161 / `J-d88c92306d97654d` | 245 / `J-f07010dc863b71be` |
| o | 1 | JPM 10-K | 1 | 75 / `J-ec0c012c575e1883` | 209 / `J-a087fad732843cc9` |
| o | 1 | XOM 10-K | 1 | 70 / `J-effc7a4fa1b9e502` | 127 / `J-e9979ae851a37d5a` |
| o | 1 | INTC 10-Q | 0 | 35 / `J-cd1a5cc529538149` | 66 / `J-46202a0268c1981b` |
| o | 1 | BABA 20-F | 1 | 32 / `J-8439585980476249` | 284 / `J-155d2e2191966ff9` |
| o | 1 | SE 6-K | 1 | 121 / `J-453b8c470e7ef690` | 199 / `J-746fd1c81fd44db3` |
| o | 2 | PGR 10-K | 1 | 34 / `J-87bedd08aa71fe5c` | 216 / `J-f8bb156b5f2e93dc` |
| o | 2 | F 10-Q | 1 | 151 / `J-cf1b803e57a009d5` | 282 / `J-afe652425a9df47d` |
| o | 2 | PLTR 10-Q | 0 | 64 / `J-744c2fe9d9a7f975` | 83 / `J-ee1056540272b7a1` |
| o | 2 | JD 20-F | 1 | 63 / `J-3b0b5cbf9bed4217` | 241 / `J-a54488316071ba7d` |
| o | 2 | SE 6-K | 1 | 81 / `J-38406c4b85cb3e19` | 141 / `J-66f30d6d1bad69bf` |

## Provenance and binding

The retained o reports are E2 run 1 `eval_20260919T184629Z.json` (SHA256 `8574ee7ccac4976e66b20fe9ee2bc64a509d36d3275f1f400ec29f64408c5fee`) and run 2 `eval_20260919T190325Z.json` (`2c1fb37fae2c719fa016b8c55c53d3532973afeb7229d9c4218bf3424e1053e9`). Both match the same 70 ticker/form/draw keys and frozen golden SHA256 `e1ca0cfcb7d0f9f51eff911586437c503a1945a64763284f48c9cd5524498b6b`. Exact source commits and raw input fingerprints are retained per output. These fingerprints cover payload/excerpt/XBRL/statement/company/form; they are **not assembled judge-message hashes**.

Before binding each n slot, audit exact frozen accession/source channels and all non-prompt execution configuration against its o counterpart under the common 73cc functional base. Bind the existing slot to the matching retained n row; do not substitute identities or rerun generation when a selected output is absent. Capture the artifact SHA, code/prompt hashes, actual assembled system/user request hashes, input lengths and full-coverage result. Preserve the frozen manifest and append a separate binding/execution record rather than rewrite the preselection.

## Queue packaging without harness changes

1. Audit any already-completed control main judgment against the exact retained input, judge model `cli:claude-fable-5-1`, contract 2, judge prompt/code hashes and source-channel caps. Reuse only a valid match; record its original timestamp, request/output artifact and attempt lineage. Do not call judge_report on a reusable main row: it deliberately discards carried verdicts and judges every supplied row anew.
2. For each remaining slot in frozen order, prepare a singleton report containing a deep copy of the original source harness and one exact unchanged original result row. Keep slot ID, condition/corpus, source artifact SHA and duplicate linkage in an external private manifest. Do not rename candidate/run/accession to make identities appear unique, and do not copy the source report’s full-cohort summary into a one-row packet. Main/duplicate inputs must originate from the same retained row. No packets were generated here.
3. The existing check_provenance requires a matching golden hash, nonempty distinct attempt identities and unique golden resolution; it does not require the complete cohort. A singleton therefore fits the existing contract. Combining corresponding rows across corpora/conditions would duplicate the native candidate/ticker/form/accession/run identity and be refused. Use unmodified judge_report on one packet at a time with concurrency 1 to preserve the dispatch order. Validate provenance before every call.
4. Preserve the exact assembled input, per-slot output artifact, actual dispatch/completion time, request hash, invocation count and reuse reference. Expose no condition or duplicate label in the model request. Company/form and the actual source/summary remain visible; wording may permit inference, so this is label blinding rather than guaranteed inferential blinding.
5. Keep the first usable verdict as main and the preselected second judgment only for judge-disagreement analysis. Retry only errors within the existing one-retry limit; never retry an unfavorable complete verdict or regenerate an output. Missing/unusable outputs remain missing.

## Execution limits and unresolved prerequisite

The existing `_judge_with_retry` already invokes the CLI up to twice for any exception or malformed verdict. That consumes the one permitted error-only retry; adding an outer retry could exceed the plan. The generic helper also retries a quota error once rather than stopping immediately. Consequently, unchanged judge_report alone does **not** guarantee the plan’s immediate quota-exhaustion stop or retain a separate artifact for every internal failed call. This is an execution prerequisite to reconcile before dispatch, not permission for an extra retry or a harness change in this task. Stop the queue on any returned quota exhaustion; do not probe repeatedly or substitute a model.

The plan’s ceilings remain 280 main minus valid reused mains plus 20 duplicates, at most one error-only retry each and one quota probe (absolute maximum 601 CLI invocations). Judge API-credit spend is zero; only existing subscription capacity is permitted. This prep spent nothing and authorized no invocation. Source caps remain 400,000 excerpt characters including appended statement evidence, 100,000 canonical payload and 40,000 XBRL; no truncation to force a verdict.

The planned random order cannot retroactively interleave E2 judgments already executed. Filter valid reused main slots from future dispatch while preserving their frozen identities and original chronological main status. Record actual order separately. The remaining queue retains its preselected order, but the completed study cannot claim fully randomized contemporaneous judging across both conditions if controls were judged earlier. Later n generation also preserves the plan’s pre-existing generation timing confound.

## Verification and reporting boundary

An independent stdlib check of the written artifacts confirmed 280 outputs, 300 unique blind IDs in consecutive planned order, 280 mains/20 duplicates, all four 70-output condition/corpus cells, exact per-form/per-corpus panel quotas, earlier-main linkage for every pair, and matching canonical and byte hashes. No app imports, tests, network calls or judging were needed.

Completion still requires 280 usable main verdicts plus all twenty duplicates. Report incomplete counts and named exclusions separately; a common-intersection secondary analysis does not complete the full cohort. Retain the predeclared filing-block and issuer-block uncertainty analyses, mean shifts beside binary disagreement, and exploratory endpoint-specific interpretation. Twenty duplicated outputs measure limited judge repeatability, not judge accuracy or causal generation variance.

### Local execution guard prepared after the panel freeze

`work/e8-judge-guard/README.md` describes a separate, currently disabled PATH shim addressing the automatic quota retry and absolute invocation ceiling without changing the judge prompt/harness. Its single offline stub invariant passes; the quota-latch mutation fails and the restored source passes. This resolves the missing mechanism only subject to independent review, prior-call accounting and enablement; it does not authorize or perform judging. The frozen selection/order JSON files and their hashes are unchanged.
