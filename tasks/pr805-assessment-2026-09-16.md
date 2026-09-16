# #805 "Ground financial explanations in the source measure and accounting basis" — assessment and path — 2026-09-16

Read-only review of [#805](https://github.com/neilmac91/EarningsNerd/pull/805) (draft, held, head
`b6a3272e03ea397e3b434bfeba1e764ff91b099e`, branch `codex/wave3-supported-financial-explanations`)
against main `926a7828` and the evidence retained since September 9. No model call, generation, source
fetch or production change was made for this assessment. Founder decision recorded at the end.

## 1. What #805 is

A prompt-only candidate from September 9. It adds three shared instruction constants to
`backend/app/services/summary_schema.py` — `FINANCIAL_EXPLANATION_SUPPORT` (one source-identity
condition: preserve measure, entity/component scope, period, accounting/tax basis, unit and the number's
role), `FINANCIAL_DRIVER` (explain a movement only on the supported basis; no invented cause or
comparator; an acceleration claim needs a prior growth rate) and `EARNINGS_RECONCILIATION` (adjusted or
"core" results only from a filed definition or a transparent signed same-period reconciliation) — wires
them into the primary schema template and rules in `openai_service.py` and into the recovery snippets in
`ai/section_recovery.py`, attaches them as Pydantic field descriptions on `PLMetricRow.commentary`,
`ThePrint.headline/key_takeaways/what_changed` and `EarningsQuality.operating_vs_one_time`, reserves stamp
`summary-2026-09-e`, and adds one wire test
(`test_supported_explanations_reach_actual_primary_recovery_and_schema`). Six files, +160/−26.

## 2. Why it stalled

- **The first paid assessment rejected it** (run `34340378513`, 52 outputs, read by hand;
  [rejected readout](quality-explanations-first-readout-2026-09-09.md)). Tables were correct; the
  explanations between the numbers were not: BA "core" described as excluding a disposal gain it
  includes; RIVN and PLTR signed subtotals reversed; MELI coupon and principal conflated; AMZN component
  presented as a total; JPM Visa gain sign; NVDA a margin cause the filing does not give; PFE pretax
  drivers applied to net income; AAPL tax direction on a false ex-charge basis; omitted debt components.
- **Codex's P1 is confirmed and unfixed.** `FINANCIAL_EXPLANATION_SUPPORT` permits a "comparison or
  cause" whenever "the signed figures or filing explanation support it". Signed figures support direction
  and size; they never support cause, and co-movement is not cause. The recovery snippets for
  `value_drivers` and `balance_sheet_liquidity` carry no driver descriptor, so the re-ask path is looser
  than the primary path.
- **The branch is stale.** Main advanced from stamp `d` to `n` (nine releases). #805 conflicts in exactly
  the three files that changed most: `openai_service.py`, `ai/section_recovery.py`,
  `summary_versioning.py`. Stamp `e` was reserved and never shipped; `f` advanced directly from `d`.
- **Its acceptance instrument did not scale.** One paid Flash cohort read by people, once. No second
  assessment was ever launched, by design (ledger: "a coherent correction and review decision remain
  required").

## 3. What changed since September 9

1. **Code now owns the arithmetic classes.** Releases `i` (source-owned financing comparison,
   `ai/financing_comparison.py`, `edgar/financing_source.py`), `k`/`m` (qualified conventional cash
   claims), `l` (operating-to-pretax bridge, `ai/statement_relationship.py`,
   `edgar/statement_relationship_source.py`) and `g`/`h` (unit context) shipped. MELI financing direction
   and the PFE-type bridge are code-owned on eligible fresh filings; the model no longer authors those
   relationships. That part of #805's ground is covered, and covered better than prose could.
2. **The residual defect class is confirmed live.** The first complete strong-judge readout
   (2026-09-15, run `35012740718`, 24 attempts, 14 negative;
   [evidence](review-evidence/w3-7/2026-09-15-run-35012740718-400k/readout.md)) found in current production output
   exactly what sank #805: NVDA and KO "growth accelerated" without a prior growth rate (the literal
   example inside `FINANCIAL_DRIVER`), AAPL's ex-charge tax basis (one of #805's own controls), KO
   derived segment margins, fabricated comparatives.
3. **Acceptance is now cheap and repeatable.** The judge runs on the founder's Claude subscription
   (`cli:claude-fable-5-1`, W3-7, #884) at no marginal API cost, and every PR's `eval-baseline` artifact
   already retains the judge inputs (payload, grounding excerpt, XBRL grounding, statement evidence)
   for all 35 × 2 attempts. What #805 lacked in September — a scalable semantic check — exists, but only
   for the weekly cohort; the eval artifact of an arbitrary PR cannot be judged yet.

What no code owner can take over is the model-authored prose: P&L row commentary, `what_changed`,
`key_takeaways`, `headline`, `operating_vs_one_time` and segment commentary. That is the ground #805 was
written for and it is still unguarded on main: the only instruction there is "Only cite figures present
in the excerpts or XBRL data", which says nothing about causes, comparators or basis.

## 4. Assessment

#805 should not be revived as it stands: the P1 wording flaw is unfixed, the base is nine stamps stale
with conflicts in the files that matter, and its reconciliation constant now overlaps code-owned
bridges. Its central idea — one shared support condition applied to every model-authored explanation
slot across primary and recovery — is still the right shape for the prose that code cannot own, and the
subscription judge gives it the acceptance instrument it never had.

## 5. Path (each item one reviewable PR)

1. **Record this assessment** (this file, ledger, handover) and close #805 with a pointer to it. Branch
   retained, nothing deleted.
2. **Turn the judge into the acceptance gate before the candidate is measured.** Generalise the local
   subscription judge so it judges any retained eval report (a PR's `eval-baseline` artifact or a local
   `eval_*.json`), not only the weekly cohort; add explanation-faithfulness gates alongside the existing
   fabricated-comparative and hallucination gates: an unsupported cause or attribution (co-movement is
   not cause), and a basis mismatch (measure, entity/component scope, period, accounting or tax basis
   changed from the source; an ex-item total the filing does not define; "accelerated" without a prior
   rate). Write a per-attempt verdict table with gate failures and a control section for the #805
   negative controls, all of which are in the golden set (AAPL, AMZN, BA, JPM, MELI, NVDA, PFE, PLTR,
   RIVN). Version the judge contract so readouts under the old gates are not compared to the new ones
   silently. Spot-check five verdicts from the September 15 readout by hand before trusting the judge as
   a gate on causal claims.
3. **Re-land a corrected candidate on current main, stamp `o`.** Keep the shared support condition,
   reworded so that a cause requires a filing statement and signed figures only ever support the
   movement; keep `FINANCIAL_DRIVER`; narrow `EARNINGS_RECONCILIATION` to describing disclosed items
   with no ex-item total (bridges are code-owned); carry the driver descriptor into every recovery
   snippet that has a model-authored explanation slot, including `balance_sheet_liquidity` and segment
   commentary. Acceptance: the PR's `eval-baseline` artifact judged through step 2; the negative
   controls must move from false explanation to abstention, with no new hallucination or comparative
   gate failures, and the deterministic regression gate unchanged. Re-pin only if the deterministic
   scores move.
4. **Keep the [September 13 relationship plan](financial-relationship-next-2026-09-13.md) separate** for
   AAPL distributions versus operating cash flow and issuer free-cash-flow reconciliation. Those are
   arithmetic and belong to code, not to this prompt.

Boundaries unchanged: no universe-wide pregeneration, no historical replay, no provider or production
flag change; the candidate's eval run costs about USD 0.3 of the CI-only DeepSeek key; every judged
verdict runs on the subscription.

## 6. Decision

Founder, 2026-09-16: "write it up in tasks and proceed with your recommended path". Steps 1–3 are
authorised in that order; #805 is closed, not deleted; the September 13 relationship plan continues
separately.
