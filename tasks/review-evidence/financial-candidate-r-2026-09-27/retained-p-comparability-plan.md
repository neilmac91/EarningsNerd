# Retained-p comparability decision for the unobserved r candidate

Date: 2026-09-27. This is a read-only pre-execution decision. No workflow, generator, SEC, Copilot, or Fable call was made. The r report does not yet exist, so this document does not pre-certify r or authorize semantic adoption.

## Decision

The already judged p corpus is **conditionally reusable** as the control for r. Do not regenerate or rejudge p before seeing r. First run the ordinary hosted r measurement once (35 frozen filings × two generator draws) and audit its retained inputs. Reuse p only if the checks below pass. If they do, a later Fable programme needs only the 70 r judgment slots under the frozen contract-2 judge; the 70 completed p judgments remain immutable. If they do not, stop before any Fable call and decide separately whether a newly matched p generation is necessary.

This saves an unnecessary 70-summary regeneration and 70 p judgment slots without weakening the source match. It does not remove generator variance, judge variance, or the RUNBOOK adoption bar.

## Facts that are fixed now

The retained p report is workflow run `36272463033`, report SHA-256 `6715966b0fde06bba8e2d5257542e637a0ea5cd81a3092996b3d18d4b8004f76`, source `a41794c9e3330852823fde5c462cf5db3137a548`, and golden-set SHA-256 `f165468c3161a5defc2e6980b2f6870dd4113e89e5c638e94b80b5ba3cadc55c`. It contains 70 unique `baseline × ticker × form × run` identities: 35 run 0 and 35 run 1, 70 scored, 70 deterministic-gate passes, zero generation errors, zero runner retries, and 70 recorded `deepseek-flash` provider calls.

The retained p judgment is SHA-256 `fed3b645ff87232c27ced1c4e8fab56805c04c9c883e959d7cef030f09bbca4a`: contract 2, `cli:claude-fable-5-1`, 70/70 judged, zero judge errors, 48 negatives. Its reservations, responses, parsed verdicts, and completion ledger are already closed; they must not be redrawn.

The historic p and q reports have exact equality on all 70 matched identities for each retained judge-evidence field:

| retained field | exact p/q matches |
| --- | ---: |
| `grounding_excerpt` | 70/70 |
| `xbrl_grounding` | 70/70 |
| `statement_source` | 70/70 |
| `source_provenance` | 70/70 |
| `coverage_inventory` | 70/70 |

That establishes the prior comparison's source match. It does not establish the unseen r match.

The current checkout still carries the exact frozen judge/evaluator bytes recorded by the returned Fable receipt: `judge.py` `7522f9…8857`, `judge_report.py` `11a79f…e780`, `runner.py` `28bd69…45f`, `weekly_readout.py` `8b1714…070d`, and `golden_set.json` `f16546…55c`. The current `.github/ai-model.env`, CI workflow, application config, and `backend/requirements.txt` are byte-identical to judge checkout `2a00fcfadee12845c3cae906b681b454d18916e5`. Static configuration therefore supports the same intended run: `deepseek-flash`, the same DeepSeek base URL, no fallback, structured output off, statement financials on, section streaming on, evidence snap on, figure/forward/attribution gates off, richer financials and edgartools sections on, one allowed transient retry, two draws, and concurrency two.

The working candidate was observed at merge HEAD `76793ebfd897e2c7701a26b6aa60771a50ad76e3` with uncommitted r changes. That is not a final candidate identity and cannot be used as the report source SHA.

Machine-readable fixed facts and the exact control queues are in `retained-p-precheck.json` (SHA-256 `ad73d1aa71a3a4a2b403eab8c0773c3aa361d4f66fc74b096d4f3ff171c77dea`).

## What the r artifact must prove before p is reused

Preserve the raw r archive, report, job log, and checksums before analysis. Then require all of the following:

1. **Final code identity.** The report and job receipt bind one final candidate commit/synthetic-merge tree. Its tree must contain the reviewed r bytes and the intended current-main base. `harness.source_sha` must equal that executed identity. A local dirty-tree hash is insufficient.
2. **Exact run plan.** `candidate=[baseline]`, `runs_per_candidate=2`, the same ordered 35-entry filing manifest, golden hash `f16546…55c`, and exactly one row for each of the 70 p identities. No foreign, missing, or duplicate row.
3. **Actual runtime.** The retained harness must report the same model, base URL, flags, fallback emptiness, richer-financials/edgartools settings, streaming setting, and retry policy. Provider telemetry must show 70 successful summary outcomes, actual model `deepseek-flash`, and no hidden extra operation. Record any retry; never redraw a failed or retried row merely to improve comparability.
4. **Source identity and excerpt bytes.** Per identity, require exact equality with p for `grounding_excerpt`, `coverage_inventory` (including accession and excerpt SHA), `source_provenance` (including URL, representation, byte/text SHA where present), and `statement_source`. Six historic rows have no `source_provenance`; for those, absence must remain absence and accession/excerpt equality remains mandatory.
5. **XBRL evidence delta.** Compare canonical `xbrl_grounding` per identity. Byte equality is not expected on affected rows, but only two reviewed provenance enrichments are allowed:
   - Derived `return_on_equity` and `return_on_assets` points may add exact copied `numerator` and `denominator` point dictionaries. Their values, selected periods, arithmetic, form, ordering, and band eligibility must remain unchanged.
   - Primary-instance `shareholders_equity` and `total_assets` points in `current`, `prior`, and `series` may change `raw_tag` from missing/`None` to the exact concept returned by the unchanged ordered selector. Equity is limited to the qualified US-GAAP/IFRS forms of `StockholdersEquity`, `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest`, `Equity`, or `EquityAttributableToOwnersOfParent`; assets is limited to qualified `Assets`. For every enriched point, value, period, currency, form, fiscal metadata, order, and current/prior/series membership must be identical to p. Each nested ratio denominator must equal its selected standardized asset/equity point, including that tag. Companyfacts and legacy/fallback points must remain missing/`None`; they render numerator scope as unestablished and may not borrow a tag.

   Debt and cash changes are wording changes; they do not authorize metric-value or source-identity differences. Any different tag, a tag outside the primary selector's unchanged whitelist, a fallback tag, or any other XBRL delta stops the reuse decision for investigation.
6. **Judgeability before calls.** Offline, using the frozen `2a00fcfa` judge files, verify 70/70 rows resolve uniquely to the frozen golden set and retain complete payload, excerpt, XBRL, and statement inputs within the existing judge bounds. This is a no-model validation.
7. **Deterministic and code review gates.** The hosted deterministic regression gate must pass on all 70. The planned 18-draw Copilot review must be retained and audited separately; it is code-review evidence and never substitutes for summary judging or the hand-check below.

If all seven checks pass, retain a signed/hash inventory stating that p is reused and why. A later r-only Fable packet should reference the immutable p report and judged-p hashes, contain the exact r report hash, use judge checkout `2a00fcfa`, contract 2 and `cli:claude-fable-5-1`, authorize exactly 70 new r slots with at most 140 physical CLI invocations from the unchanged built-in retry, checkpoint each call, and prohibit probes, manual redraws, and full reruns. Keep both generator draws (`run=0` and `run=1`); one draw is not a replacement.

If any identity, source excerpt, statement evidence, or unapproved XBRL field differs, do not call Fable. Preserve the mismatch. A current-source p regeneration may then be needed for a matched experiment, but that is a new metered decision, not an automatic fallback. Never relabel the old p judgments as judgments of a regenerated p.

## Source-backed hand-check queue

Perform this against retained r bytes before deciding whether Fable is useful. It is a factual source review, not replacement verdicts.

First preserve all 18 RUNBOOK negative-control slots (two draws each):

- AAPL 10-K runs 0/1
- AMZN 10-K runs 0/1
- BA 10-K runs 0/1
- JPM 10-K runs 0/1
- MELI 10-K runs 0/1
- NVDA 10-Q runs 0/1
- PFE 10-Q runs 0/1
- PLTR 10-Q runs 0/1
- RIVN 10-K runs 0/1

For each, inspect every causal/basis sentence against the retained excerpt, XBRL and statement evidence. Record whether the candidate abstains from the historical false explanation; do not infer success from a lower aggregate score.

Next preserve the exact nine-identity union where q introduced a G2 or G3 code relative to matched p:

- AAPL 10-K run 1 — G3
- ASML 20-F run 0 — G3
- PGR 10-K run 1 — G3
- PLD 10-K run 1 — G3
- RIVN 10-K run 0 — G3
- RIVN 10-K run 1 — G3
- WMT 10-K run 0 — G3
- WMT 10-K run 1 — G2
- XOM 10-K run 1 — G2

Compare the exact flagged q text with p and r and read the source. Four historical q flags were on text also present in p; five were q-only generated text. That classification must be recomputed for r, not copied forward. The three overlaps with the 18 controls are AAPL run 1 and RIVN runs 0/1, so these two lists comprise 24 unique r slots.

Finally add FIGS 10-Q runs 0/1, producing a 26-slot unique queue. On FIGS, verify the code-owned comparative names its actual selected prior date and does not imply YoY. On JPM, verify an issuer ROE/ROA quote remains intact beside the formula-qualified derived ratio and that current/prior numerator scopes come from their own selected concepts. On WMT, verify the attributable-income qualifier, issuer-defined FCF caveat, and selected-XBRL debt wording against the source. On AAPL/ASML/JPM, verify selected-XBRL absence language is not a claim that the filing text lacks debt. Preserve any unsupported claim even when it is outside the ratio line.

## Interpretation limits

Reusing p preserves a matched, immutable control and the same two-draw design. It does not make the arms contemporaneous: r generation and any later r judgment occur after p, so provider and judge time effects remain unmeasured. Generated prose will vary across arms. Treat paired gate counts as observations over 70 identities, not a causal estimate of the wording change.

No r result may be called release-cleared unless the literal RUNBOOK bar is met: all 18 negative controls abstain from the historical G4/G5 errors, no new G2/G3 is established after source review, the deterministic gate remains intact, and the correction-specific checks above pass. Existing p's 48/70 negatives are a control description, not an acceptable quality floor.
