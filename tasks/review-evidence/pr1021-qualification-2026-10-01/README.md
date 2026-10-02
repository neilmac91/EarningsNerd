# #1021 qualification evidence (2026-10-01)

These are the offline, zero-cost audit tool and its outputs. The #1021 acceptance decision used them, and future Copilot readiness runs can use them too. They are evidence files only: nothing in `backend/` imports them, and CI does not run them.

## Tool

`prose_quote_audit.py <copilot-eval.json> [...]` audits retained Copilot eval artifacts, i.e. the `copilot-eval.json` file inside the `copilot-fidelity-<run>` Actions artifact.

**Composed quotation.** A double-quoted span of at least 8 characters in a published answer that, after normalization, is not a contiguous substring of that row's retained `inputs.source_text`. Normalization folds whitespace, curly quotes and dashes, and lower-cases. The scorer and the publication verifier check only declared citation excerpts, never the prose, so an 18/18 run can still contain composed quotations.

**Grounding escalation classes, recorded per row.** The scorer treats all of these as advisory:
- `uncited_answer_rows`: figures were stated (`figure_count > 0`), but there are zero verified citations.
- `uncited_figure_rows`: `uncited_figures > 0`.
- `tool_less_rows`: `tool_trace.tool_results` is empty.

**Exit codes:**
- **0:** clean.
- **1:** at least one composed quotation, or a row without source text. Under the #1021 policy this is FAIL.
- **2:** no exit-1 condition, but at least one escalation row. The policy below decides whether that holds.

## Policy used for #1021

This policy was pre-registered before the ready run. It is recorded in `tasks/pr-disposition-2026-09-30.md`.

**FAIL and hold** on any of the following:
- any error, failed or withheld row;
- any composed quotation;
- any row without source text;
- any answer stating figures with zero verified citations.

**Advisory (recorded):**
- individual uncited figures inside otherwise-cited answers;
- fully-cited answers that made no tool call.

## Audits (`audits/<run id>.json`)

| Run | Code | Scored / passed / errors | Composed rows | Uncited answers |
| --- | --- | --- | --- | --- |
| 36500418287 | old #1021 prompt `93dc6565` | 17 / 17 / 1 | BABA d0, d2; ASML d0 | 0 |
| 36511300921 | old | 18 / 18 / 0 | ASML d0, d1 | 0 |
| 36516634768 | old (`55e89142`) | 18 / 17 / 0 | BABA d0, d1; ASML d1 | 0 |
| 36519321075 | old | 18 / 18 / 0 | BABA d0; ASML d0, d1 | 0 |
| 36624149908 | old | 17 / 17 / 1 | ASML d0–d2 | 0 |
| 36630506944 | old | 17 / 17 / 1 | ASML d0–d2 | 0 |
| 36640254449 | main `a88b6fb1` | 18 / 18 / 0 | ASML d2 | 0 |
| 36754723895 | main | 18 / 18 / 0 | none | 0 |
| 36777581481 | main (#1030) | 18 / 18 / 0 | BABA d0 | ASML d1 |
| 36798834277 | main (#1038) | 18 / 18 / 0 | none | 0 |
| 36800236360 | main (#952) | 18 / 18 / 0 | ASML d0 | 0 |
| 36809122540 | main code at #1021 `c4629ffc` | 18 / 18 / 0 | none | 0 → **PASS** |

**Main's Copilot code, 6 runs and 108 rows:**
- Composed quotations: 3 rows.
- Uncited answers: 1 row.
- Clean under the policy: 3 of 6 runs.
- Every run has the MSFT advisory pattern: 1 of 3 figures uncited, inside answers whose other figures are cited.

**Artifact digests.** The `artifact` paths inside the JSON files are local download names.
- Run 36809122540: zip `501748cc5de46fca5485c391e008f5341ba9531516e2f5e0fa161484b9172732`; `copilot-eval.json` `9cb7368ec031f6130493e4994ec5ce2179ac78c9a6bb80bfe1cf456491a25cd1`.
- The other runs are retained as Actions artifacts under their run ids.
