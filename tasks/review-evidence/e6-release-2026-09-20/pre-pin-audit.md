# E6 authoritative artifact audit — run 35472665559

Audit of the actual 105-output report, before any pin. Mechanical checks clear; independent acceptance review remains pending. No model call, source fetch, rerun, pin or tracked edit occurred during this audit.

## Identity and completeness

- Actual workflow_dispatch source: `4614153286d42a47727f7fad1ba1620be9300b0e`; reported source and full Git tree match exactly. Full workflow succeeded; generation, regression and artifact-upload steps each completed successfully. Job 105976371985 ran2026-09-19T22:12:50Z–2026-09-19T22:27:14Z; actual invocation `python -m evals.runner --candidates baseline --runs 3 --concurrency 2`, no limit. See `run-final.json`, `eval-baseline.log`, and `report/ci-execution.txt`.
- Report `report/eval_20260919T222710Z.json`, SHA256 `1829062317b90c83339c585ad51c9c7f14aed8776f21dc9dd73da837c1bd7b5f`.
- Exactly 35 filings × 3 runs: 105 expected/attempted/scored, 0 errors/retries/vetoes/missing/extra/duplicate identities. Frozen golden SHA256 `f165468c3161a5defc2e6980b2f6870dd4113e89e5c638e94b80b5ba3cadc55c` matches committed bytes. Every coverage accession/excerpt hash matches. Raw document body is not retained, so its declared SHA cannot be independently recomputed; all 9 six-K rows retain the existing absent raw-source-provenance behavior.
- All 105 requested and actual models are `deepseek-flash`, provider `https://api.deepseek.com/v1`, both fallback fields empty. Evidence snap true; statement financials true; structured output false; figure/forward/attribution gates false and attribution verifier false. Streaming/EdgarTools/richer financials true. Judge false. Flags match committed deploy declarations and the retained pre-run live whitelist.
- Profiles:99 general, 6 insurer(PGR/BRK.B×3); each score/result matches frozen applicability and source metadata. All six insurer source-evidence quotes are present in their own retained excerpts. Candidate prose did not select a profile.
- Read-only helper exited 0 with no refusals; pure pin builder accepted in memory only. Historical baseline remains byte-identical to `previous-baseline_scores.json`, SHA256 `7d47f73c49c3932aa76a3d346346ebe71ba130e42a808e1bdb0ab2f673130032`.

## Actual measurements and warnings

| Dimension | Historical pin | New105 | Difference |
|---|---:|---:|---:|
| Financial depth |0.7937|0.7746|-0.0191|
| Delta consistency |0.8438|0.9976|+0.1538|
| Citation fidelity |0.9706|0.9648|-0.0058|
| Citation checked |7.0857|7.1810|+0.0953|
| Redundancy |0.9115|0.9274|+0.0159|
| Forward quote fidelity |0.9952|0.9952|0|
| Untraceable dollar figures |2.1619|2.4857|+0.3238|

Actual regression log: `PASS — no hard regressions (1 warning(s)).` Its single WARN is the standing absolute untraceable-dollar advisory, mean 2.4857. All 105 figure traces measured,0 unavailable/errors, 261 total signals. No warning or per-row residual was removed. Comparisons combine a changed scorer/profile with later generation runtime and run variation; they do not estimate improved generated quality. `total_cost_usd=0` is unmetered, not free execution.

Recomputed provider ledger matches report: 105 calls, all summary_primary,0 unknown, no recovery or verifier calls;4,133,670 prompt tokens,419,714 completion tokens,4,112,628 cache-hit and 21,042 cache-miss input tokens. A balance movement is a separate parent-owned receipt, not inferred from these token totals.

## Targeted manual read and known limitations

GPRO's three draws score delta 1.0. Each actually checks total revenue 18.7% and hardware revenue 21.5% pairings; unquantified net-loss narrowing no longer borrows revenue’s percentage. It remains unmeasured for that net-loss clause, not certified correct.

BRK.B insurer depth is 0.6667/1.0/0.3333, versus 0.3333 each under the unchanged general profile on the same outputs. The missing categories are balance sheet in run 0 and balance sheet/margins in run 2; run 1includes numbered float and underwriting. PGR remains 0.6667 each under either profile (margins category missing). ASML/SE 6-K depth remains 0.3333 each and PDD 6-K 0.0 each. A frozen insurer declaration does not award unconditional credit or alter known 6-K applicability; the existing term-near-digit heuristic still limits recognition.

The one delta score below 1 is BABA 20-F run 2, 0.75. Its consolidated Adjusted EBITA table change 56% is matched to “Alibaba China E-commerce Group adjusted EBITA fell 44%” in the prose. This is a concrete instance of the already disclosed qualified-name ambiguity, not a verified generator contradiction. Other BABA revenue matches include total, like-for-like and segment percentages; a correct duplicate can mask other matches as previously documented. Do not treat 0.9976 as semantic recall or zero false positives.

Citation minima were read from retained rows/violations. PLD run 0 is 0.4286 (3 of 7) with four synthesized P&L evidence strings, not direct verbatim quotes. ASML 20-F and TSM 20-F contain strict near-miss penalties; AMZN run 1 is 0.8333. These outcomes remain in the artifact. The lone forward penalty is PDD 6-K run 0: source ends “second quarter,” while quoted output ends “second quarter.” The words match but punctuation fails the strict verbatim scorer. No score is corrected by this audit.

The largest trace count is PDD 20-F run 1 with 19 signals. At least the operating profit 93,102.1 million is explicitly present in retained source and output despite the diagnostic floating representation `93102.100000000006m`; this signal alone is not proof of fabrication. The other signals were not individually adjudicated. The next largest is Ford run 2 with 10; all top-eight rows are retained in `targeted-manual-index.json`.

One qualitative BABA run 2 concern also remains visible: its earnings-quality prose says income from operations includes investment/disposal gains while locating them in interest and investment income, net. The hard numeric gates do not establish basis/attribution correctness. This is not a new Fable verdict or evidence that the scorer change caused the prose. The report is a deterministic measurement, not a full semantic acceptance judgment.

## Handoff

Read `audit.json` for all 105 profile/source/score checks, `targeted-manual-index.json` for exact scorer witnesses, `manual-audit.json` for independently recomputed usage and limits, and the unchanged actual report. Independent parent/acceptance audit must precede any pin authorization. No pin was written; the parent owns the next step.
