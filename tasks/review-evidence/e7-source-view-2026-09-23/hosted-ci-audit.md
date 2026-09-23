# PR #940 hosted evaluation artifact audit

Audited read-only at 2026-09-23 06:23 UTC. The full machine-readable receipt is in `hosted-ci-audit.json`; downloaded artifacts are under `work/e7-source-method-2026-09-23/hosted-audit/`.

## Verdict

The actual baseline and Copilot artifacts pass their configured hard gates. I found no artifact execution error, missing planned result, hard-gate failure, or new inline review finding. Two quality advisories remain visible rather than being converted into a clean-quality claim: the baseline has untraceable-dollar/citation findings, and four Copilot answers contain one uncited figure each.

PR #940 was **not merge-ready at audit close** because [review-gate run 35825075792](https://github.com/neilmac91/EarningsNerd/actions/runs/35825075792) was still in progress, waiting for a completed Codex review of the exact current head. This is a hosted review-state hold, not an evaluation-artifact failure.

## Provenance

Both successful evaluation runs report PR head `829d95cb57f4614f4c9ecdc96824c9307f66c87f` in GitHub metadata. Their retained `source_sha` is `489ce2b44edff07650c88813f0b21a85b2ddb450`, which GitHub resolves as the synthetic pull-request merge commit created for these runs. Its parents are base `ebdc4c44c5c6aa01c94587646a4c365f84fe26ec` and the exact requested PR head `829d95cb…`. The artifacts therefore measured that exact head integrated with its then-current base; they did not measure a stale PR commit.

## Baseline artifact

[CI run 35824964267](https://github.com/neilmac91/EarningsNerd/actions/runs/35824964267), job `107064596156`, completed successfully. Artifact `eval-report-35824964267` is ID `10734544907`, API size 3,682,318 bytes, with upload digest `ce56f5bcbb6ca58e1be9829d69493eb22290cf1faebedef6d32702433c52a58b`. The downloaded JSON is 20,764,717 bytes with SHA-256 `f08af5a54953a6fda4b6de75f98514dd5cfb051af4c7b6ad47936b0b73ec552f`.

Offline recomputation found:

- 35 filing identities × 2 runs = 70 distinct result identities; 70 payloads and 70 distinct canonical payload hashes.
- 70 scored, 70 schema-valid, 70 `passed_gates=true`, 70 aggregate scores of 1.0, zero repairs, errors, first errors, retries, hard-gate failures, or missing sections.
- 70 successful `summary_primary` calls, zero unknown calls, actual model only `deepseek-flash`; 2,755,570 prompt and 284,587 completion tokens.
- Coverage inventory present for all 70; 699 retained preview frames, no reported preview truncation. Final-response association is explicitly `not_observed` for all 70, so those frames are evidence of the summary call including internal retries rather than proof of final-response attribution.
- Figure trace measured all 70: 180 untraceable dollar figures across 43 outputs, maximum 13 in one output, mean 2.5714. There are 14 citation violations across 10 outputs and one forward-quote violation. Attribution audit is present in 66 outputs. Source provenance is present in 64; the six absent records are exactly the six 6-K runs, which retain their `earnings` classification and coverage inventory.

The hosted regression step independently printed `expected=70 attempted=70 scored=70 errors=0` and `PASS — no hard regressions (1 warning(s))`. The warning is real and advisory: mean untraceable dollar figures remains above zero. Figure-trace, forward-quote, and attribution gates were disabled in the recorded harness, so the green job must not be described as clearing those advisory issues. The artifact's `$0.0` total is also not a billing receipt; actual provider usage is retained.

## Copilot artifact

[Copilot run 35824964205](https://github.com/neilmac91/EarningsNerd/actions/runs/35824964205), job `107064595730`, completed successfully. Artifact `copilot-fidelity-35824964205` is ID `10734188337`, API size 78,695,254 bytes, with upload digest `b60c2f24462d0155dac8aa8ecdedb857aea90e04aca87cd825e86e5580ff351e`. The downloaded `copilot-eval.json` is 9,963,994 bytes with SHA-256 `5bc2db80625aaf545f1813f11f66b75e311bdddfc6397c2ccf8f367642cbc4fe`.

Offline recomputation found:

- Source preparation complete for all six planned accessions with zero errors. The retained database hash exactly matches its declared `03c423ce81ee1d4b774f3f23aba4e85d4d0b661f6983cdffffbeff627405a3c7`.
- 6 questions × 3 draws = 18 unique attempts; 18 completed, terminal, scored, and passed; zero execution errors, gate failures, missing metrics, invalid provenance records, misplaced citations, or unverified excerpts.
- All 18 have numeric recall, citation faithfulness, and fact adjacency of 1.0. The report retains 38 citations and 72 tool-trace records.
- Figure coverage is advisory: 45 figures total, 38 recorded as grounded, four uncited figures across four answers. Fourteen answers have coverage 1.0, three have 0.6667, and one has 0.75.
- `runner.log` contains 35 successful `copilot_chat` calls, all actual model `deepseek-flash` and one system fingerprint, with 1,097,954 prompt and 5,454 completion tokens. This is 35 provider calls for 18 answer attempts, not an assumed one-call-per-answer count.
- Preparation logged two incoherent segment-table sums and explicitly dropped those tables before completing all six sources. No preparation error followed; the warnings should remain with the evidence.

This is a passing existing Copilot fidelity gate, not the weekly strong-judge readout and not a claim that every figure was cited.

## Review gate and inline findings

At the final snapshot, run `35825075792` was on current head `829d95cb…`; job `107065235674` was still in the step “Wait for the Codex review of this head, or an explicit recorded override.” No exact-current-head completed review was observable. The latest clean Codex message reviewed `efd0cb8051143b3558aed8bf075f7fa89e55cf16` and reported no major issues. No inline comment was created after that message. GitHub still shows 19 unresolved historical threads (11 on current diff positions and eight outdated), but no new thread followed the clean review; this audit does not reinterpret historical thread-resolution state as a new finding.

After the final documentation push, the repository's exact required mechanism is:

1. Comment `@codex review` on PR #940; pushing alone does not request a review.
2. Wait for the exact Codex GitHub App to publish a “Codex Review Summary” whose **Code Review** row says **Completed** for a unique commit prefix resolving to the final full head SHA.
3. The in-progress gate polls for up to 20 minutes. The `@codex review` issue-comment workflow reruns the latest completed gate; if the review completes after timeout, rerun the failed gate for that final head.

The only documented alternative is a PR-body line `Review override: <reason>` with a reason of at least ten characters. No comment, override, rerun, merge, push, or provider call was made by this audit.
