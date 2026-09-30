# Notable Filings bounded rollout — September 28

Codex owns this rollout under the founder's September 27–28 delegation. The product decision is to retain and enable the existing, source-faithful filing discovery cards so their usefulness can be observed. This is a serving change: it generates no summaries, sends no notifications and changes no registration, capacity, scoring, scan schedule or retention setting. The application default remains off. Existing deployment parity pins service and pregenerate to the same value; the scanner already runs independently of this flag.

## Evidence and release prerequisites

The seven-day observation has 14/14 eventual scheduled-slot successes, with four failed first attempts recovered by automatic retry (10/14 first-attempt successes). The retained cohort has 312 accessions, 291 issuers and no duplicate accessions. The unchanged twelve-card sample covers all eight observed reasons. A bounded additive source read resolved four initially inaccessible indices; the original adverse evidence is preserved in [the September 28 checkpoint PR](https://github.com/neilmac91/EarningsNerd/pull/1001).

[PR #1002](https://github.com/neilmac91/EarningsNerd/pull/1002) narrows regulatory labels so an S-1 does not imply an IPO and non-reliance does not imply a completed restatement. Its longest labels must fit narrow cards. Merge this activation only after that PR's exact-head checks, source/layout review, serial deployment and independent API/database readback succeed. [#997](https://github.com/neilmac91/EarningsNerd/pull/997) has already been deployed and independently verified. No failed candidate, earlier UI overclaim or indeterminate source result is being rewritten as a pass.

The source sample supports the corrected categories for those filings. It does not establish all-cohort precision, investor usefulness, E7 acceptance or consent to beta outreach. Zero impressions while the section was disabled were not utility evidence.

## Execution and observation

The normal backend deployment applies the reviewed service/pregenerate pins. Verify the main CI run, migrations 0 applied / 40 skipped, ready revision with 100% traffic, unchanged service/revision maximum 2, matching worker images and independent healthy database/API response. Then read `/api/notable_filings?limit=8`: expect status `ok`, three to eight distinct issuers, canonical SEC URLs, filing dates within the serving window and the corrected reason labels. These are operator checks; do not synthesize clicks or count them as customer evidence.

Check the public homepage after its existing ISR refresh and record the actual result. It may retain an earlier empty response for up to 3,600 seconds. A successful API read is not proof that the homepage has refreshed. If native-browser access remains unavailable, retain that visual-check limitation rather than fabricating acceptance. The preceding label PR includes local responsive checks in both themes.

The live verification reservation is USD 0.10 with zero model calls and no job dispatch. One ready-for-review head may separately run the existing Copilot regression under a USD 0.10 CI planning ceiling; retain actual calls and telemetry. The ordinary summary evaluator should skip because generation paths are unchanged; verify the job's own evidence. No paid rerun is authorized by this plan.

## Rollback and follow-up

For a source-label overclaim, duplicated/out-of-window cards, or a health regression attributable to the rollout, restore `NOTABLE_FILINGS_ENABLED=false` on the service and in both durable workflow pins. Verify that the API returns an empty feed. Previously cached homepage HTML can remain until its existing hourly refresh; this flag is not an immediate frontend cache purge. A correction must preserve the initial observation and offending source, rather than replace the sample.

Read impressions and card clicks only after real exposure exists, using observed section impressions as the CTR denominator. They are directional discovery evidence, not proof of summary quality or a substitute for the consenting beta cohort and two weekly readouts. The quality, wider-generation and attribution holds remain in force.
