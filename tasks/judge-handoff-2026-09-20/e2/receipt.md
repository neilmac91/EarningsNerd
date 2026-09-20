# Judge receipt — E2 control 1 (PR #920 run 35461717484)

- Generation run: https://github.com/neilmac91/EarningsNerd/actions/runs/35461717484
- Artifact: `eval-report-35461717484`; report `eval_20260919T184629Z.json`
- Report source_sha: `e1b52bafb18c4d1cb69f489ccbdfd8ebd7407deb` (synthetic PR merge commit; parents f6f84aa1… (main) and 73cc3116… (PR head); tree identical to 73cc3116…)
- Golden set sha256 (report and checkout): `e1ca0cfcb7d0f9f51eff911586437c503a1945a64763284f48c9cd5524498b6b`
- Generator: `deepseek-flash`; AI_ATTRIBUTION_VERIFY=True; AI_ATTRIBUTION_GATE=False
- Input JSON sha256: `8574ee7ccac4976e66b20fe9ee2bc64a509d36d3275f1f400ec29f64408c5fee`
- Output judged.json sha256: `d5c6a293aa7fb79b416f0df5c47bf90f67960601c8946b3180248838dbacb54d`
- Output judged.md sha256: `e35eddc3f7e6b58b6416c640935ff026e6fb491926bf33179c08ad8440a94543`
- Judge: `cli:claude-fable-5-1`; contract version 2; per-verdict contract versions: {2: 70}
- Judged at: 2026-09-19T19:09:09.920346Z; harness: unmodified `evals.judge_report` at checkout 73cc31162c3dfe7ec497c8c88c43cf397afce4a7, concurrency 2, claude CLI 2.1.278, auth oauth_token/firstParty (subscription)

- Planned attempts: 70 (35 filings × 2 repeats); attempts in report: 70; judgeable: 70; completely judged: 70; judge errors: 0
- Negative verdicts (complete only): 38/70 = 54.3%
- Gate attempt counts: G2=2 G3=14 G4=23 G5=22
- Dimension means: faithfulness=3.657 insight=3.157 clarity=3.571 specificity=4.057
- Errors: none
- Incomplete/truncated judge input: none (max excerpt chars 260154, cap 400000; max summary chars 32610, cap 100000; max xbrl chars 22500, cap 40000)
- Attempt-level overlap (not clause recall): Fable G4=23, nonempty attribution_audit.unverified=17, both=7, G4 without flag=16, flag without G4=10
- Full per-attempt reasons: analysis.txt; side-by-side flagged clauses vs G4 reasons: overlap-detail.txt
