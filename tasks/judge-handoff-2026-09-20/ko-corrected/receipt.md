# Judge receipt — KO corrected corpus (PR run 35467365092) — PARTIAL: 50 of 70 identities judged

- Generation run: https://github.com/neilmac91/EarningsNerd/actions/runs/35467365092
- Artifact: `eval-report-35467365092`; report `eval_20260919T203644Z.json`
- Report source_sha: `6af1393efc923b141397e84f91830515ebb50f89` (synthetic PR merge commit 6af1393e; parents 356663dd (main) and ee724436 (generator head); whole tree identical to ee724436)
- Golden set sha256 (report and checkout): `e1ca0cfcb7d0f9f51eff911586437c503a1945a64763284f48c9cd5524498b6b`
- Generator: `deepseek-flash`; AI_ATTRIBUTION_VERIFY=False; AI_ATTRIBUTION_GATE=False
- Input JSON sha256: `57049cab3a997fe4934680e5425ad7816035b6d35f0bb641ee29d0304875dd39`
- Output judged.json sha256: `5a0983c75ba48ba13e524dc061097cc0d66753a1ae9989d9547365fe42ee74cd`
- Output judged.md sha256: `52a891e0b1e35245c270ee689040979b6f8a44cf22f0bc43394fa22af7b7fc08`
- Judge: `cli:claude-fable-5-1`; contract version 2; per-verdict contract versions: {2: 50}
- Judged at: 2026-09-20T00:26:47.250707Z; harness: unmodified `evals.judge_report` at checkout 73cc31162c3dfe7ec497c8c88c43cf397afce4a7, one unchanged-harness `evals.judge_report` command per original-row singleton packet (concurrency 1), consolidated without re-judging; claude CLI 2.1.278 at /opt/claude-code/bin/claude (symlink /opt/node22/bin/claude), auth oauth_token/firstParty (subscription)

- Planned attempts: 70 (35 filings × 2 repeats); attempts in report: 70; judgeable: 70; completely judged: 50; judge errors/missing: 20 (missing identities: [['COIN', '10-Q', 0], ['COIN', '10-Q', 1], ['BYND', '10-Q', 0], ['BYND', '10-Q', 1], ['BABA', '20-F', 0], ['BABA', '20-F', 1], ['ASML', '20-F', 0], ['ASML', '20-F', 1], ['TSM', '20-F', 0], ['TSM', '20-F', 1], ['JD', '20-F', 0], ['JD', '20-F', 1], ['SE', '20-F', 0], ['SE', '20-F', 1], ['NVO', '20-F', 0], ['NVO', '20-F', 1], ['PDD', '20-F', 0], ['PDD', '20-F', 1], ['MELI', '10-K', 0], ['MELI', '10-K', 1]]; error identities: [])
- Negative verdicts (complete only): 27/50 = 54.0%
- Gate attempt counts: G2=0 G3=13 G4=14 G5=15
- Dimension means: faithfulness=3.74 insight=3.22 clarity=3.6 specificity=4.14
- Errors: none
- Incomplete/truncated judge input: none (max excerpt chars 231325, cap 400000; max summary chars 32236, cap 100000; max xbrl chars 22500, cap 40000)
- Attempt-level overlap (not clause recall): Fable G4=14, nonempty attribution_audit.unverified=13, both=3, G4 without flag=11, flag without G4=10
- Full per-attempt reasons: analysis.txt; side-by-side flagged clauses vs G4 reasons: overlap-detail.txt
