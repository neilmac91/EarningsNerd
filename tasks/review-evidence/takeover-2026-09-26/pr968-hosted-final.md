# PR968 hosted artifact audit

Audited 2026-09-27 from the completed pull-request workflows for [`c56fe7925443b2d74361b8122f207037fc986f0e`](https://github.com/neilmac91/EarningsNerd/commit/c56fe7925443b2d74361b8122f207037fc986f0e). Both hosted workflows succeeded. The retained evidence supports the deterministic gates and the focused Copilot fidelity gate. It does not supply a strong-judge verdict or a release/deployment receipt.

## Identity and custody

- CI run [`36286423496`](https://github.com/neilmac91/EarningsNerd/actions/runs/36286423496) and Copilot run [`36286453794`](https://github.com/neilmac91/EarningsNerd/actions/runs/36286453794) both record exact PR head `c56fe7925443b2d74361b8122f207037fc986f0e`.
- Both reports record workflow source `a2f5cbd9e219abb2d12674d112602a05ef4803b7`, GitHub's synthetic pull-request merge of base `537bf59b923922d2215ae1399920756e014bd4e5` and head `c56fe7925443b2d74361b8122f207037fc986f0e`.
- The synthetic commit and exact head have the same Git tree, `8ace43f5956a5398ff52d026fe1343794c1f3154`. The generated artifacts therefore exercised the exact head's file tree.
- Ordinary golden-set SHA-256: `f165468c3161a5defc2e6980b2f6870dd4113e89e5c638e94b80b5ba3cadc55c`. Copilot golden-set SHA-256: `15f8e7f92f934a5b040d905e8f684896cb11b2309d41737bbb58d59d0127b3c0`.

## Measured results

| Measure | Ordinary summary eval | Copilot filing fidelity |
| --- | ---: | ---: |
| Population | 35 filings × 2 draws = 70 | 6 accessions × 3 draws = 18 |
| Completed / scored | 70 / 70 | 18 / 18 |
| Execution errors / retries | 0 / 0 | 0 / n/a |
| Hard-gate failures | 0 | 0 |
| Passed | 70 (100%) | 18 (100%) |
| Terminal responses | 70 complete reports | 18 / 18 |
| Judge verdicts | 0; harness `judge=false` | 0; explicitly not the weekly strong-judge readout |

The ordinary regression gate compared all 70 attempted and scored outputs with the pinned 35-filing baseline and returned `PASS — no hard regressions (1 warning)`. Every result had aggregate `1.0`, valid unrepaired schema, numeric recall/precision/coverage `1.0`, and no hard veto.

The Copilot report retained 18 answers, 38 citations, and 42 counted figures. All citations were verified; numeric recall and citation faithfulness were `1.0`; there were no invalid-provenance, contradictory-currency, misplaced-citation, or unverified-excerpt findings.

## Telemetry and cost

| Measure | Ordinary | Copilot | Combined |
| --- | ---: | ---: | ---: |
| Provider calls | 70 | 35 | 105 |
| Successful calls | 70 | 35 | 105 |
| Prompt tokens | 2,755,570 | 1,097,982 | 3,853,552 |
| Completion tokens | 282,099 | 5,516 | 287,615 |
| Total tokens | 3,037,669 | 1,103,498 | 4,141,167 |
| Cache-hit tokens | 2,741,494 | 1,091,072 | 3,832,566 |
| Cache-miss tokens | 14,076 | 6,910 | 20,986 |
| Estimated cost | $0.179593 | $0.007622 | $0.187215 |

All 105 calls used provider `primary`, requested and actually ran `deepseek-flash`, and recorded fingerprint `aeb56401ca74e127821c4f9126dcb669`. Prompt, completion, total-token, and cost telemetry had zero unknown calls. `reasoning_tokens` was unavailable. The ordinary report's legacy `total_cost_usd` field is `0.0`; the per-call hosted telemetry in `logs/ci-run.log` supplies the measured $0.179593 estimate and is used above.

## Retained soft limits and runtime warnings

- Ordinary dollar-figure tracing measured all 70 outputs: 163 untraceable dollar figures across 41 outputs, mean `2.3286`, maximum 11 in one output. This is the regression gate's single explicit warning; figure tracing is advisory and disabled as a hard gate.
- Ordinary prose metrics remained soft: mean/min specificity `0.9962/0.9362` (14 outputs below 1), mean/min one-home redundancy `0.9184/0.75` (59 below 1), and mean/min citation fidelity `0.9789/0.6667` (9 below 1; 10 violations among 525 checked excerpts). Delta consistency and forward-quote fidelity were `1.0` throughout. Preview evidence was retained for every output with no preview truncation.
- The ordinary log contains 32 `Persisted XBRL read failed ... OperationalError` messages and two incoherent segment-table drops. These were runtime warnings rather than attempt errors: the report still contains 70/70 scored outputs, zero retries, and zero hard-gate failures.
- Copilot figure coverage was advisory: three MSFT draws each shipped one uncited figure out of three. Across all answers, 3 of 42 figures were uncited; minimum figure coverage was `0.6667` and mean coverage `0.94445`. Answers remained compact (13–50 words, maximum 302 characters).
- Copilot source preparation completed all six accessions with zero preparation errors, while explicitly dropping two incoherent segment tables. ASML's retained `sections.json` is the four-byte JSON `null`; its answer draws still passed using retained filing/XBRL evidence. This is preserved as a source-preparation limitation.

## Review and release boundary

Codex review completed against exact head `c56fe79` at 2026-09-27 01:45:53 UTC. The GitHub review API returned zero inline comments and zero review findings. No branch edit was made during this audit.

The evidence establishes hosted deterministic and Copilot-gate success for the PR tree. It does not establish semantic acceptance by the strong judge, eliminate the retained advisory findings, or prove a production deployment. Merge and deployment verification remain separate actions.

The [copied inventory](pr968-hosted-inventory.json) and [file hashes](pr968-hosted-files.sha256) bind the external workspace bundle `outputs/takeover-2026-09-26/pr968-hosted-final/`. Original inventory SHA-256: `3881bddcc83700a2eb749a9151da0be422f79f2ec65cfc4bf11930b90981faee`; file-manifest SHA-256: `142366e342f132978f78672155ef71a204ed5b4b50e991421add3b32696db913`. API responses, complete logs and downloaded artifacts remain under that external bundle’s `metadata/`, `logs/` and `raw/`; they are not beside this repository copy.
