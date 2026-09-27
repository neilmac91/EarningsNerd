# PR 967 final hosted audit

**Result:** final CI `36284201570` and Copilot filing fidelity `36284201573` succeeded for PR head `ac60f49f270bc42503d52005391af70727561d58`. Both reports identify synthetic merge `22657e04124ec450c3cfcca502dbd814f7ffb366`; its tree `bb20367d7aebe07418e4f06d87c8f11895563a3d` is identical to the exact-head tree, so the tested path diff is empty.

The full local backend gate was run at production-code commit `1bc5a9f921adc599eb578b0a10d4108d488bb1b5`. The only following commit, `ac60f49f`, adds two retained evidence JSON files and changes no production or test code. The final hosted workflows nevertheless tested the exact final tree.

## Denominators, failures, and retries

| Run | Logical denominator | Result | Recorded provider events | Actual model | Explicit eval retries |
| --- | ---: | --- | ---: | --- | ---: |
| CI `36284201570` | 70 results (35 filings × 2) | 70 scored/pass, 0 errors | 70 success | `deepseek-flash` 70/70 | 0 |
| Copilot `36284201573` | 18 draws (6 sources × 3) | 18 terminal/scored/pass, 0 errors | 36 success | `deepseek-flash` 36/36 | 0 |

Every Copilot draw used one tool round and one terminal call. The runners recorded no redraw or result retry. Application telemetry cannot exclude transport retries hidden inside one SDK call.

## Actual usage and cost

| Run | Prompt | Completion | Total | Cache hit | Cache miss | Telemetry cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| CI | 2,755,570 | 273,270 | 3,028,840 | 2,741,494 | 14,076 | USD 0.174298 |
| Copilot | 1,128,365 | 5,578 | 1,133,943 | 1,121,280 | 7,085 | USD 0.007773 |
| Combined | 3,883,935 | 278,848 | 4,162,783 | 3,862,774 | 21,161 | USD 0.182071 |

All 106 recorded provider events used actual model `deepseek-flash`, outcome `success`, and fingerprint `aeb56401ca74e127821c4f9126dcb669`.

## Jobs and review

CI completed six successful jobs: `backend-tests`, `e2e-tests`, `migrations-postgres`, `lighthouse`, `frontend-tests`, and `eval-baseline`; PR-only `deploy-backend` was skipped. Copilot's sole job succeeded. Final review gate `36284203330` succeeded against the same head.

The latest substantive Codex response at `2026-09-27T01:04:12Z` explicitly reviewed `ac60f49f27` and reported no major issues. The dynamic review summary completed at `01:04:15Z`, and no later inline review comment was created. The prior P2 artifact-pairing finding targeted `e9efafa1`; commit `1bc5a9f9` corrected it before the final review.

## Material soft advisories

- CI measured all 70 results and found a mean 2.3143 untraceable dollar figures in raw model prose.
- CI logged 32 persisted-XBRL read failures across 32 accessions. All 70 results completed and scored, but the storage warnings remain evidence.
- CI used deterministic scorers with `judge=false`. Its report cost field is `0.0`; application telemetry measured USD 0.174298.
- Copilot preparation dropped two incoherent segment-revenue tables before completing all six sources.
- Four of 18 Copilot draws shipped one uncited figure advisory. All passed because figure coverage is advisory; this run is not the weekly strong-judge readout.
- GitHub emitted the informational `ubuntu-latest` migration notice for five CI jobs.

All required hosted checks are complete and there are no observed execution failures or unresolved exact-head review findings. This supports the release decision together with the accepted code review and custody evidence. Green automation alone does not establish source correctness or independent quality acceptance.

Raw GitHub API responses, logs, original ZIPs and extracted reports remain outside the repository under workspace `outputs/takeover-2026-09-26/pr967-hosted-final/`. The copied [105-file inventory](pr967-hosted-inventory.json) binds that external bundle; its original SHA-256 is `402c8d59432584239ea6bb814c1da469217797582b3f2b86bc605d547fd5c6d4`. This compact repository copy does not contain the raw bundle.
