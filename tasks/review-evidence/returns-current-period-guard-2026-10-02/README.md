# Returns current-period guard: offline evidence

This is the item-B follow-up from the close-out research (R4), as the founder approved it (`tasks/pr-disposition-2026-09-30.md`, log entry 13:10Z): the code-rendered `value_drivers.returns_on_capital` line leaves out a ratio whose current point is not the filing's period. It does not date the current point, and there is no drain.

Branch `claude/returns-current-period-guard`, on main `06ad809a`, then merged with main `a541c3c8` (#1036: one `test_copilot.py` test change and `tasks/` only):

| Commit | Content |
| --- | --- |
| `a31ff53e` | the guard in `markdown_render._ratio_clause` and its test |
| `4b354ed6` | content stamp `summary-2026-09-u` |
| `c2880a47` | this folder and the `tasks/todo.md` entry |
| `0c6376a0` | merge of main `a541c3c8`, clean |
| `69929b5a` | review nits in this README, and the post-merge gate |
| `edc5d3db` | test case `10k-assets-missing` (misaligned ROA beside an aligned ROE) and mutation M3 (review finding, LOW) |
| `7fee4b08` | `mutations.json`/`.log` regenerated; this README for the seventh shape and M3 |
| this commit | this table and the gate on `7fee4b08` |

Everything here is offline: provider keys unset, sockets blocked in the scripts, no provider call and no spend.

## Defect (R4 §1)

- The ROE/ROA derivation walks net income newest-first and keeps only periods whose same-date denominator is positive (`xbrl_service.py:1232-1252`, check at `:1241`). The ratio's current point is the newest survivor, not necessarily net income's current point.
- On the instance path, net income and balances are anchored at `period_of_report` (`instance_extractor.py:367-368`). Equity is not in `NON_NEGATIVE_CONCEPTS` (`facts_service.py:89-93`), so negative equity is kept. When equity at the report date is zero, negative or missing, that period is skipped and an older positive-equity ROE point becomes "current".
- ROA cannot shift this way on the instance path, because assets are anchored and positive.
- The current clause is undated. On main, the older ratio therefore reads as the filing's own, next to a dated prior two years back.

Probe on main (`probe_current_period.py`, case A: net income 2025/24/23 = 100/80/60, equity −50/400/300). ROE current is 2024-12-31 and ROA current is 2025-12-31:

> Period net income attributable to the parent / period-end equity, not annualized: 20.0% (prior at 2023-12-31: 20.0%); period net income attributable to the parent / period-end assets, not annualized: 5.0% (prior at 2024-12-31: 4.2%).

This is R4's line, byte for byte. The 10-Q (FIGS-like) form, case E, renders Q1's ROE as if it were Q2's: `…equity, not annualized: 1.5%;` with no prior. This is not a regression: before #1039, main rendered the same stale value with no date at all (`../pr942-successor-2026-09-30/README.md:202-206`).

## Fix

`_ratio_clause` returns `None` when net income's current period is known and the ratio's current period is known and different. The guard is at `markdown_render.py:578`. It mirrors the existing rule of leaving out an undated prior rather than guessing (`:586`). Each ratio is judged on its own point, so dropping ROE never drops an aligned ROA. Both periods go through `return_ratio_period`, the same normalizer the dated prior uses.

**Model-facing bytes are unchanged** (`ast_scope.py`, `ast-scope.txt`):
- In `backend/app`, the only changed definitions are `_apply_structured_fallbacks` with its `_ratio_clause` closure, and the `SUMMARY_PROMPT_VERSION` assignment.
- The fallbacks run after the model calls (`openai_service.py:552`, preview `:641`).
- The stamp is read only by the pipeline's row write, `summary_refresh` and the admin endpoint, and never by a prompt.
- The grounding block, which dates the ratio itself as `(period: …)`, is identical to main in 6 of 6 probe cases and 70 of 70 cohort results (below).
- Copilot reads `Filing.xbrl_data`, not summaries, and is untouched.

This guard is about dating, not value quality, so `lessons/arch-guard-every-model-facing-surface.md` asks nothing more here: the grounding dates the point itself as `(period: …)`, and model-facing bytes stay unchanged by founder scope.

## Probe (`probe-current-period.json`, `.stdout`)

| Case | NI current | ROE current | Grounding vs main | Line vs main |
| --- | --- | --- | --- | --- |
| A 10-K, negative equity at report date | 2025-12-31 | 2024-12-31 | identical | ROE clause dropped, ROA kept |
| B 10-K, equity missing at report date | 2025-12-31 | 2024-12-31 | identical | ROE clause dropped, ROA kept |
| C 10-K, aligned | 2025-12-31 | 2025-12-31 | identical | identical |
| D 10-K, zero equity at report date | 2025-12-31 | 2024-12-31 | identical | ROE clause dropped, ROA kept |
| E 10-Q FIGS-like, negative equity at Q2 end | 2026-06-30 | 2026-03-31 | identical | ROE clause dropped, ROA kept |
| F 10-Q FIGS-like, aligned (sequential prior) | 2026-06-30 | 2026-06-30 | identical | identical |

Markdown outside the returns line is identical in all six cases. The new test, `test_return_ratio_not_at_net_income_period_abstains` in `tests/unit/test_xbrl_narrative_section.py` (not a locked file), pins the same six shapes plus a seventh: assets missing at the report date, where ROA's current point is 2024-12-31 and its clause is dropped while the aligned ROE stays (added after review, `10k-assets-missing`). The aligned lines are main's bytes, and each case keeps main's dated grounding ROE line. The locked `test_structured_markdown_render.py` is unchanged.

## Offline replay of B's hosted cohort (`replay_hosted_cohort.py`, `replay-hosted-36993299710.json`)

The input is the retained report of CI run 36993299710, `eval_20261002T101321Z.json`, with sha256 `08672385…71d2c`, the one revalidated in `../pr1039-condition2-2026-10-02/`. Main is a `git archive` of `06ad809a`; the branch is `4b354ed6`, tracked-clean. Each result is re-rendered as `revalidate.py` does: its own `raw_sections` and its own `xbrl_grounding`.

| Check | Result |
| --- | --- |
| Grounding blocks changed | **0** (identical 70 of 70) |
| Returns lines changed | **0** of 64 (the 6 6-K results have no line on either side) |
| Other section fields / Markdown lines changed | 0 / 0 |
| Hosted line equals the re-render | 70 of 70 on main, 70 of 70 on the branch |
| Ratio clauses whose current is not net income's current | 0 of 126, as `clauses_current_not_ni_current: 0` in `../pr1039-condition2-2026-10-02/hosted-36993299710.json` |

## Mutations (`mutate.py`, `mutations.json`, `mutations.log`)

Each run covers the owner test file plus the locked render file, 114 tests on the unmutated tree. Tracked files were clean afterwards.

| Mutation | Result |
| --- | --- |
| M1: guard removed | 5 failed: the five misaligned cases of the new test |
| M2: period comparison inverted (`not in` → `in`) | 14 failed: all 7 new-test cases, including both aligned ones, plus all 7 cases of the existing `test_return_ratios_own_their_selected_operands_across_periods` |
| M3: guard limited to ROE (`key == "return_on_equity" and …`) | 1 failed: `10k-assets-missing`. This was a reviewer mutation that survived the first six cases; the seventh case was added for it |

Expected survivors (reviewer mutations, not in `mutate.py`): making an undated ratio abstain too, and comparing raw periods without `return_ratio_period`. Both behave identically for every input the real producer can make, because each ratio point copies its period string from a net-income point (`xbrl_service.py:1243`); the undated branch of the "known and differs" rule cannot be reached, so no test is added.

## Content stamp `summary-2026-09-u`, and what it triggers

The bump follows how `t` was introduced in `f896afbe`: only `summary_versioning.py` changes, and no test pins the current stamp by literal. `u` has never been set on any ref in the local clone, nor in main's history through `a541c3c8` (`git log -S`), where the stamp is still `t`; `q` and `r` stay reserved.

A bump makes `t`-and-earlier rows version-stale (`is_stale`, `summary_refresh.stale_filter`). It regenerates nothing by itself:

| Path | Reads the stamp? | Automatic? |
| --- | --- | --- |
| Admin `POST /api/admin/summaries/refresh-stale` (`admin.py:879`) | yes | no. Operator call; `dry_run=True` by default |
| `scripts/refresh_stale_summaries.py` (D4 drain) | yes | no. Dry run unless `--execute`; not scheduled (`docs/OPERATIONS.md`, D4) |
| Weekly pregenerate cron (Mondays 06:00 UTC, `scripts/pregenerate_examples.py`; args set out of band, `docs/DEPLOYMENT.md` §9) | no | stamp-agnostic either way; skips any filing that has a summary unless forced (`precompute_service.py:171-178`) |
| `POST /internal/jobs/precompute` | no | same `precompute_one`; `force` comes from the request |
| Pro regenerate (`summaries.py:230-253`) | no | user-initiated |
| Read path / provenance API | passes `prompt_version` through | nothing regenerates on read |
| Frontend | no reader of `prompt_version`/`schema_version` (grep: 0 matches) | no outdated badge |

Compared with `t`, which shipped today, the only addition is that rows generated under `t` since its deploy also count as stale in the operator dry-run totals. There is no user-visible change and no automatic spend. Opening a PR from this branch runs the paid `eval-baseline` job (`ci.yml:298-305`, about USD 0.17), and `copilot-eval` once the PR is ready. Neither has been run here.

## Census decision: no drain (R4 §3)

The 47 census filings with summaries (58 untagged snapshots; `../stamp-t-snapshot-census-2026-10-01/README.md`) get no drain or refresh, for the guard or for `t`:
1. **Nothing shown today is newly false.** Stored summaries keep the line text from generation, built from each filing's own snapshot. The guard changes a line only when a row is regenerated.
2. **A drain cannot target them.** It selects every stale summary, filterable only by form (`summary_refresh.py:50-58`). Order is random (`:114`) and each row is fully regenerated (`:125`). That re-draws the whole production corpus of about 50 summaries, changes every model-written section, and the keep-better gate can leave rows stale anyway.
3. **The useful version is not authorized.** Naming the numerator scope needs `xbrl_data` cleared (`summaries.py:252-253`, `admin.py:446`). Re-extraction would rewrite 58 snapshots and their FinancialFact rows, a data change that has not been authorized (`tasks/pr-disposition-2026-09-30.md`, item 5).
4. **Cost is not the issue** (about USD 0.12–0.25 at eval rates); content churn and the data change are.
5. **These rows fix themselves on demand.** A Pro regenerate clears the snapshot and re-extracts.

## Optional zero-spend check: the one class-7 filing with a summary (not run)

Census class 7 (6 filings, 1 with a summary) is the only class that can hold a pre-#785 (`fc2bf2f7`) snapshot from `_fetch_from_latest_financials`. That fallback copied the company's latest 10-K values and wrote every point as exactly `{period, value, form: null, accn: <this filing's accession>}`. If the newest net-income period is not the filing's own period, the snapshot carries another filing's figures under this filing's accession number. That would break the filing-only rule regardless of item B.

`class7_snapshot_check.sql` (sha256 `48e9ad2f…2632b3`) is one read-only `SELECT` for Cloud SQL Studio; it can be wrapped in `BEGIN TRANSACTION READ ONLY; … ROLLBACK;` in psql. For each class-7 filing with a summary, it returns:
- the filing's accession and period end;
- the summary stamp;
- the net-income series;
- point-shape counts;
- the company's latest stored annual period;
- the stored returns line;
- a `verdict` of `pre_785_shape_period_mismatch`, `pre_785_shape_period_matches`, `companyfacts_fallback_shape` or `other_shape`.

It has **not** been run against production. It was validated only on a local PostgreSQL 16 scratch database with 7 synthetic rows (`class7-fixture/`):
- every class-7 row with a summary was selected (3, equal to `census.sql`'s class-7 `with_summary` count on the same fixture);
- each verdict was correct;
- the class-0, class-4 and class-6 rows and the class-7 row without a summary were excluded.

If the result is `pre_785_shape_period_mismatch`, clearing and regenerating that one filing (`admin.py:446`) is a separate founder decision.

## Gate

Full backend gate on `4b354ed6` from `backend/`, provider keys unset: `ruff check .` all checks passed, `bandit -q -r app -ll` exit 0 with no findings, `python -m pytest -q -p no:cacheprovider` **5544 passed**, 39 skipped, 2 deselected, 40 warnings in 644.03s. The log is kept in scratch and not committed. This folder's commit changes only `tasks/`.

After the merge of main `a541c3c8`, the same gate on merge `0c6376a0` (backend identical at this commit): ruff all checks passed, bandit exit 0, pytest **5544 passed**, 39 skipped, 2 deselected, 40 warnings in 678.39s. `mutate.py` re-run there: baseline 113 passed, M1 4 failed, M2 13 failed, tree clean after.

After the `10k-assets-missing` case (`edc5d3db`), the same gate on `7fee4b08`: ruff all checks passed, bandit exit 0, pytest **5545 passed** (one new case), 39 skipped, 2 deselected, 40 warnings in 677.97s. `mutate.py` on `edc5d3db`: baseline 114 passed, M1 5 failed, M2 14 failed, M3 1 failed, tree clean after (`mutations.json`).
