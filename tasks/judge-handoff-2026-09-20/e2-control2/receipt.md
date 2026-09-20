# Judge receipt — E2 control 2 (workflow_dispatch run 35462609093)

- Generation run: https://github.com/neilmac91/EarningsNerd/actions/runs/35462609093
- Artifact: `eval-report-35462609093`; report `eval_20260919T190325Z.json`
- Report source_sha: `73cc31162c3dfe7ec497c8c88c43cf397afce4a7` (PR head directly)
- Golden set sha256 (report and checkout): `e1ca0cfcb7d0f9f51eff911586437c503a1945a64763284f48c9cd5524498b6b`
- Generator: `deepseek-flash`; AI_ATTRIBUTION_VERIFY=True; AI_ATTRIBUTION_GATE=False
- Input JSON sha256: `2c1fb37fae2c719fa016b8c55c53d3532973afeb7229d9c4218bf3424e1053e9`
- Output judged.json sha256: `15ec6a1c23cdaeda1a56432c152d45fc7c6a9c6e9cd790e073d63db58f207faa`
- Output judged.md sha256: `6febea9b13fd3078a84de2a2837e81e03381ac2b0bb9190486ba258389d0d557`
- Judge: `cli:claude-fable-5-1`; contract version 2; per-verdict contract versions: {2: 70}
- Judged at: 2026-09-19T19:36:26.499175Z; harness: unmodified `evals.judge_report` at checkout 73cc31162c3dfe7ec497c8c88c43cf397afce4a7, concurrency 2, claude CLI 2.1.278, auth oauth_token/firstParty (subscription)

- Planned attempts: 70 (35 filings × 2 repeats); attempts in report: 70; judgeable: 70; completely judged: 70; judge errors: 0
- Negative verdicts (complete only): 42/70 = 60.0%
- Gate attempt counts: G2=2 G3=12 G4=25 G5=24
- Dimension means: faithfulness=3.657 insight=3.143 clarity=3.557 specificity=4.1
- Errors: none
- Incomplete/truncated judge input: none (max excerpt chars 260154, cap 400000; max summary chars 32912, cap 100000; max xbrl chars 22500, cap 40000)
- Attempt-level overlap (not clause recall): Fable G4=25, nonempty attribution_audit.unverified=12, both=6, G4 without flag=19, flag without G4=6
- Full per-attempt reasons: analysis.txt; side-by-side flagged clauses vs G4 reasons: overlap-detail.txt
