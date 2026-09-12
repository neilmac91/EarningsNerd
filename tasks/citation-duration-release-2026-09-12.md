# Citation and source-duration release — September 12, 2026

[PR #831](https://github.com/neilmac91/EarningsNerd/pull/831) merged as `9d3b8b472502fd27c70980ba8b5b73e6b130d2e8` at 22:16:12 UTC. This dated record supersedes the candidate-only citation status in earlier entries. Agent A's debt release is recorded [separately](debt-scope-release-2026-09-12.md).

## Accepted behavior

New per-filing instance and companyfacts-fallback facts retain the selected source fact's period start. Missing or ambiguous dates stay absent. A narrowly recognized uncited annual revenue statement receives a citation only when its fact proves matching concept, accession, amount, currency, period end and annual duration. Other answer bytes remain unchanged. Computed growth and margins refuse operands whose fiscal labels contradict their reported duration; genuine annual and quarterly computations remain available. Existing rows are not backfilled or replayed.

Independent review rejected annual-form/FY substitution for observed duration, then reproduced a newly enabled Q4/Q4 growth calculation incorrectly labelled FY. The final guard covers current, prior and margin-denominator operands. The founder approved the narrow T9 exception: seven fixture dictionaries gain their source starts, preserving original assertions. Ten other locked anchors remain byte-identical. Original failed proposals and their corrections remain in the lane ledger and PR body.

## Verification

Combined committed A+B code passed Ruff, Bandit and full pytest, including performance and all four concurrency lanes on PostgreSQL 15.15:

```text
All checks passed!
Bandit exit 0
3071 passed, 29 warnings in 90.28s (0:01:30)
```

The gated code at `d8adc299c4eb178f9dbf2be16085752bad71a4e9` is byte-identical in application and tests to published head `096cbeb214086f2b1fe82983a2e03d66a11e3d98`. Three committed mutation proofs, one per duration-certification, source-date fidelity and computed-scope invariant, are retained in the PR body. No baseline floor was relaxed or cosmetically re-pinned.

[CI 34721656080](https://github.com/neilmac91/EarningsNerd/actions/runs/34721656080), summary job `103628556629`, passed. Source merge `bd1a4f9d54c1cc20d6bfb99f56796dc4d8dd52d4` binds released debt main `b251ead4ff52bf05576adedd857e123af82c0d1e` and the exact candidate. Intervening #830 changes three task documents only. Summary artifact `10306861655`, `eval_20260912T221101Z.json`, SHA256 `ad83d7e9b7242e98423a066331f32cfc278dfccd4bd252080021ea6892b822a4`, has 52 unique attempts with zero errors, retries, repairs or hard vetoes. Actual gate at 22:11:02.1905259 UTC:

```text
PASS — no hard regressions (1 warning(s)).
```

The warning is mean untraceable raw-prose dollar figures 1.846. All 52 source, excerpt and coverage records match the accepted debt assessment; all XBRL records match after removing newly preserved period_start. Harness settings are unchanged. Provider records show 52 primary calls, zero unknown calls, 2,178,056 prompt and 194,014 completion tokens. The report's zero-dollar field does not establish zero spend.

Independent debt acceptance found all 52 leverage fields unchanged, all 78 component amounts and labels correct, and all raw/final fields matching. All 86 leverage-bearing occurrences across 497 previews match their finals; SE run 1 has no leverage-bearing preview, so its preview parity is unobserved.

[Copilot 34721670711](https://github.com/neilmac91/EarningsNerd/actions/runs/34721670711), job `103628601238`, completed 18/18 without errors. Requested figures, years and currencies are correct; 26 numeric chips match tool/source data, and eight text excerpts occur in the filing. Initial messages and source text match the accepted debt run. The run observes fresh dates reaching tool results and chips, but contains no server_citation_lookup: automatic repair activation and computed-metric abstention are proven by deterministic tests, not this live model draw.

## Limits and remaining work

ASML results 15–16 remain uncited. ASML 17 and AAPL 0 retain overly broad text-citation associations despite correct numeric chips. General citation behavior, historical undated rows, source completeness, accounting relationships and financial explanations remain open. No strong judge ran; source inventories remain partial and preview/final response association remains not_observed. This is bounded acceptance, not world-class corpus certification.

Both external agents have completed their implementation slices. Codex integrated, independently reviewed, corrected and serially released them. Next engineering work should address the verified financial-relationship defects and missing-source coverage before expanding generation. The original Notable review/retain decision, Analysis warm-up/live acceptance, exact W3-7 strong-judge artifact, E06 natural payment observation, E09 proposal/capacity decision and other founder-held items remain open. Universe-wide pregeneration and historical replay remain held.

The preceding debt documentation PR #830 merged as `331d280a0ca62c8cc2ebf7a1b70fa9075c2527bb`; main CI `34721795511` passed. Deploy job `103629311692` succeeded by explicitly reporting `No backend changes - skipping deploy.` at 22:09:05.4438110 UTC. It did not deploy a new revision.

## Production verification

Main [CI 34722282522](https://github.com/neilmac91/EarningsNerd/actions/runs/34722282522) succeeded on merge `9d3b8b472502fd27c70980ba8b5b73e6b130d2e8`. Deploy job `103630629427` records `apply_migrations: applied=0 skipped=39` at 22:21:16.1488563 UTC. Revision `earningsnerd-backend-00336-47r` serves 100 percent at 22:21:58.4839828 UTC, confirmed by the explicit traffic listing at 22:22:00.0186290 UTC. CI reports deployed image `9d3b8b4`.

CI detailed health was healthy at 22:22:39.0456829 UTC (database 6.89 ms). Independent post-deploy `curl -fsS https://api.earningsnerd.io/health/detailed` exited 0 and returned healthy, database 7.63 ms, timestamp 1789251796.0848694. Redis was disabled/healthy and the SEC circuit closed in both. Local retained evidence: `work/pr831-main-deploy.log` and `work/pr831-independent-health.json`. No live-account generation was used as a test.

## Next verified defects

The [next financial relationship plan](financial-relationship-next-2026-09-13.md) records current #831 witnesses and two refutations each: AAPL result 0 says distributions exceed OCF although $106.132B is below $111.482B; MELI result 51 says financing cash flow turned positive although both current and prior are positive; MELI result 50 labels derived $10.8B FCF without its basis. These are inherited open interpretation defects, not closed by the debt/citation releases. The next bounded design preserves source context before allowing a code-owned financing comparison; dates alone are insufficient.
