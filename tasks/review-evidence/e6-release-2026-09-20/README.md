# E6 measurement, pin and local release evidence — 20 September 2026

[PR #928](https://github.com/neilmac91/EarningsNerd/pull/928) is pending actual PR CI and 70-output/Copilot artifact acceptance, merge and deployment verification in this snapshot. This archive records completed measurement, authorized pinning and local gates; it does not claim release or semantic acceptance.

Authoritative [workflow 35472665559](https://github.com/neilmac91/EarningsNerd/actions/runs/35472665559) generated 35 filings × 3 at source `4614153286d42a47727f7fad1ba1620be9300b0e`. Exact report `eval_20260919T222710Z.json` SHA256 `1829062317b90c83339c585ad51c9c7f14aed8776f21dc9dd73da837c1bd7b5f`: 105 expected/attempted/scored, zero missing/duplicate/extra slots, errors, retries or hard vetoes. All 105 primary calls returned deepseek-flash; fallback was empty, evidence snap on and attribution verifier/gate off. Frozen applicability was 99 general / 6 insurer; every insurer evidence quote matched its own retained excerpt. No strong-judge results are present.

The [historical pre-pin read](pre-pin-audit.md), [manual accounting](pre-pin-manual-audit.json), [independent mechanical audit](independent-audit.json) and [targeted witnesses](targeted-witnesses.json) retain their original audit-stage statements. Their “no pin written,” “baseline unchanged” and pending-review language describes that earlier stage, superseded by the completed pin below. Raw document bodies were not retained, so declared raw-document hashes are not independently rehashed; nine existing 6-K rows lack raw-source provenance. The full report and complete generation/gate logs remain outside Git at the paths and hashes in [source provenance](source-hashes.json).

The existing pin tool consumed that exact report after authorization; [actual pin output](pin.txt) and [post-pin preservation proof](post-pin-gate.json) show candidate summary and harness equality and the exact old-note prefix preserved. Final pinned head `fb5b61ca46c26b37f41c33a96feb7785af79ba98`; new pin SHA256 `6ca0f4a8654b49111a823e3c6998edc6c375506e82adbf670576479f56126387`. Previous pin SHA256 `7d47f73c49c3932aa76a3d346346ebe71ba130e42a808e1bdb0ab2f673130032`. The E6 branch already carries `tasks/review-evidence/e6-2026-09-19/authoritative-repin.json` and `previous-baseline_scores.json`; those are intentionally not duplicated on this documentation branch and will arrive with main integration.

[Actual final local tail](gate-tail.txt): 3,428 passed, 78 warnings in 128.40s, Ruff/Bandit passed, all four PostgreSQL 15.15 lanes and performance included, exit 0 at 2026-09-19T22:38:48Z. A Yahoo-client shutdown logging error after the passing summary is preserved in the full log; it did not change exit status. All eleven locked files equal actual base `299cb1bfdc5392ff6ab8d04a7d999f23eb029183`. Scorer, runner, schema, pin tool, golden and tests are byte-identical to the measured head.

[Independent code review](independent-code-review.md), [artifact review](independent-artifact-review.md) and [pin-delta review](independent-pin-review.md) each record their scope and evidence limits. [Completed exact-head remote review](remote-review.json) separately records the Codex summary at 2026-09-19T22:44:58.763670Z and subsequent PR thumbs-up, with no findings; review-gate 35474075589 also passed. Actual baseline/Copilot artifacts and remaining CI still require their own acceptance. Two historical mutation types are retained as actual logs (only trailing spaces on three blank lines in the profile log are normalized; its original source hash is preserved): [old proximity matcher](mutation-delta.log) fails the GPRO invariant (1 failed, 2 warnings in 1.06s); [missing alternative-runner profile propagation](mutation-profile.log) fails the profile invariant (1 failed, 2 warnings in 5.35s); [restored targeted suite](restored-targeted.log) passes 146 tests, 2 warnings in 8.41s. No new mutation or test was run for archival.

| Dimension | Previous pin | New 105-output pin |
|---|---:|---:|
| Financial depth |0.7937|0.7746|
| Delta consistency |0.8438|0.9976|
| Citation fidelity |0.9706|0.9648|
| Citation checked |7.0857|7.1810|
| Redundancy |0.9115|0.9274|
| Forward quote fidelity |0.9952|0.9952|
| Untraceable-dollar mean |2.1619|2.4857|

Actual regression passed with the standing absolute untraceable-dollar WARN 2.4857: 261 signals, none unavailable. Changes mix altered scoring/applicability, later runtime and stochastic generation; they do not estimate generated-quality improvement. The recorded cost zero is unmetered, not free. No previously absent WARN dimension was activated by the pin.

Coverage remains bounded: direct matching checks 113 of 371 percentage-bearing rows versus 148 before (249 versus 434 pair occurrences). All 113 matcher-selected percentage corruptions are detected; this is conditional sensitivity, not semantic recall. Unsupported grammar and sign remain unmeasured, a correct duplicate can mask another wrong claim, and depth remains a term-near-digit heuristic. General and known 6-K applicability are unchanged.

BABA 20-F run 2 preserves the qualified-name collision: a 44% segment adjusted-EBITA sentence is matched against the consolidated 56% table figure, yielding delta 0.75. This is a scorer false positive, not a confirmed prose contradiction. Separately, PLD run 0 retains four non-verbatim evidence strings (citation 0.4286), and BABA run 2 retains prose assigning nonoperating investment/disposal gains to operating income. These generated semantic residuals remain open; the scorer was not tuned to remove them. Perfect deterministic scores neither close those defects nor arm production attribution deletion.

[Package checksums](SHA256SUMS) cover this compact archive. No large generated report, duplicate prior pin, source change, model call or production operation is part of archival.
