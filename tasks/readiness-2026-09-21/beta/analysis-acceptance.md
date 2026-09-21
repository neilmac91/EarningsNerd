# Multi-Period Analysis acceptance worksheet v1 — blank

This adds the missing Analysis proof to the existing acceptance plan. The Vercel Analysis flag was already observed true on 8 September; do not request it again as a missing setup step. A configured flag, warm data, a successful user workflow and product acceptance are four different states. The founder controls the live companyfacts warm-up and named Pro account; this sheet records their receipts only.

| Control | Receipt to fill |
|---|---|
| Candidate deployment SHA / backend revision / frontend preview | `[ ]` / `[ ]` / `[ ]` |
| Exact warm-up cohort tickers and source | `[explicit tickers; no broad watchlist default]` |
| Warm-up command and UTC start/end | `cd backend && python scripts/sync_companyfacts.py --tickers TICKER1,TICKER2` (replace with frozen cohort); `[ ]` |
| Warm-up attempted / synced / unsupported / error | `[ ] / [ ] / [ ] / [ ]`; counts must reconcile to attempted |
| Per-ticker supported annual/quarterly periods and latest facts timestamp | `[ ]` |
| Named Pro-account alias (no credential), entitlement source and observation time | `[ ]` |
| Frontend flag evidence and observation time | `[ ]` |
| Browser/console/network screenshot or artifact references | `[ ]` |
| Reviewer and acceptance decision/date | `[ ]`; `[pending/accepted/rejected]` |

Use the shipped `backend/scripts/sync_companyfacts.py` only after checking its help and setting an explicit bounded cohort. Record the exact command, output and source SHA. A successful job exit alone does not prove all tickers were synced; reconcile outcomes and coverage responses. Do not manufacture success rows for unavailable data.

| Case | Entitlement / evidence to observe | Light | Dark | Result / artifact |
|---|---|---|---|---|
| Signed-out picker/teaser | Coverage requires auth; no Pro dataset access | `[ ]` | `[ ]` | `[ ]` |
| Signed-in Free | Coverage visible; dataset, narrative and exports Pro-gated from `get_entitlements` | `[ ]` | `[ ]` | `[ ]` |
| Named Pro annual | Supported period range, deterministic grid/charts and citations consistent | `[ ]` | `[ ]` | `[ ]` |
| Named Pro quarterly | Same, including quarter labels and comparatives | `[ ]` | `[ ]` | `[ ]` |
| Fresh narrative | Terminal completion, source-linked figures, quota/cost observation | `[ ]` | `[ ]` | `[ ]` |
| Cached narrative | Same visible result on second run, cached completion, no fresh model/quota claim | `[ ]` | `[ ]` | `[ ]` |
| PDF export | Completed narrative PDF reflects displayed data and citations | `[ ]` | `[ ]` | `[ ]` |
| XLSX export | Deterministic dataset workbook reflects displayed periods/values | `[ ]` | `[ ]` | `[ ]` |
| Unsupported/IFRS | Explicit unsupported state; no implied fabricated coverage | `[ ]` | `[ ]` | `[ ]` |

Stop and classify any mismatch by ticker, period, source value and visible output. The `analysis_generated` event is an attempt before dataset success, and `analysis_inference_cost` covers fresh completed narratives with usage only; neither replaces this browser acceptance. Record whether the surface is accepted for the offered beta scope; do not infer it from the Summary E7 acceptance protocol.
