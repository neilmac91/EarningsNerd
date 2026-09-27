# PR #942 Fable evidence — independent semantic/adoption review

Date: 2026-09-27
Reviewer role: read-only independent semantic/adoption review
Repository comparison: `origin/main` (`c53c7361c6d63efd7a2399467c4980854d48d7b3`) … `origin/codex/wave3-return-ratio-basis` (`be1f98f42cdd70ffb7219357cdbd1f1715316fcf`)
Judged checkout recorded by the returned receipt: `2a00fcfadee12845c3cae906b681b454d18916e5`
No model/provider call, judgment change, baseline change, prompt change, repository edit, or test run was made for this review.

## Recommended chief-engineer disposition

**Hold PR #942 under the current RUNBOOK acceptance rule. Keep the current backend baseline pinned; do not apply the q3 proposal.**

The returned evidence supports the narrow correction: formula labels avoid presenting the application's period-end calculations under issuer-facing ROE/ROA names. It does not satisfy the repository's adoption rule. Candidate q leaves G4/G5 on 5 of 18 negative-control attempts and introduces newly appearing G2/G3 gate codes. The q3 deterministic proposal is therefore premature and would lower the pinned citation-fidelity reference from `0.9648` to `0.9532`.

This is a rule disposition, not a claim that the label change is harmful. If the chief engineer wants to release this isolated correction despite the global semantic bar, the clean route is an explicit, scoped founder disposition after the small code-owned FIGS comparator defect is fixed. The RUNBOOK's September 20 exception cannot be reused: it says it is not an exception for other candidates.

## Findings

### 1. Blocker: q does not clear either semantic limb of the adoption bar

The applicable RUNBOOK text requires a grounding candidate's negative controls to move from false explanation to abstention (no G4/G5), no new G2/G3 failure, and an unchanged deterministic regression gate. It also says a better mean score is not the bar (`origin/main:backend/evals/RUNBOOK.md`, lines 1176–1179).

The returned comparison is complete enough to apply that rule: 70/70 attempts were judged in each arm, with zero errors or pending judgments, under contract 2 and the same recorded Fable model. Deterministic scoring is unchanged at 70/70 in both arms. But:

- q retains G4/G5 on **5/18 negative-control attempts**: AMZN run 0, JPM runs 0 and 1, NVDA run 1, and RIVN run 1.
- q has **nine newly appearing gate-code instances by matched identity: seven G3 and two G2**. Four of the seven G3 texts are byte-present in the matched p output; five rows contain q-only generated text. Regardless of causal classification, the literal `no new G2/G3 failure` condition is not met.

The returned `comparison/conclusion.md` reaches the same adoption failure at lines 26–35, but line 30 misstates the count as “seven new G2/G3 findings” and then separately adds two G2 findings. The retained inventory has nine rows, and the matched gate sets confirm seven newly appearing G3 codes plus two newly appearing G2 codes.

Two attempted refutations of rule applicability fail:

1. **“This is only a deterministic label correction, so prompt-candidate acceptance does not apply.”** The branch also changes generator grounding and the generator instruction in `openai_service.py`, and advances the content stamp to q. It therefore is a grounding/prompt candidate by the RUNBOOK's own terms, even though the intended semantic effect is narrow.
2. **“The new failures occur in unrelated sentences, so they can be excluded.”** Their topics make a direct label mechanism implausible, but every q output was regenerated after a prompt change. The evidence does not isolate the label perturbation from stochastic full-output resampling. More decisively, the RUNBOOK's `no new G2/G3 failure` rule contains no same-sentence exception, and its only scoped founder disposition says it is not precedent for other candidates (`RUNBOOK.md`, lines 1119–1128).

A third possible argument—48/70 p negatives versus 40/70 q negatives—also cannot clear the hold. The RUNBOOK expressly says a better mean is not the bar, and the two-run result mixes a prompt perturbation, generator sampling, and documented judge inconsistency.

### 2. The mechanism evidence is valid but narrower than the conclusion's wording

The source packets independently support two issuer-name collisions:

- **JPM:** the filing reports ROE on average common equity and ROA on average assets. The p line calls the application's period-end calculations “Return on equity” and “return on assets,” producing 15.7%/17.0% and 1.3%/1.5% beside issuer measures of 17%/18% and 1.29%/1.43%. q names only the formula. This removes the borrowed metric names.
- **WMT:** the filing defines ROA as consolidated net income divided by average total assets and reports 8.2%/7.9%. The p line calls a different calculation “return on assets” at 7.7%/7.5%; q names the period-end formula instead.

The ratio-line judgments move from p 3 gates to q 1. JPM run 1 and WMT run 0 are direct supporting examples. JPM run 0 shows judge under-sensitivity: its p line has the same collision but the judge explicitly declined to gate it because the trailing basis was disclosed. The correct inference is therefore **“the evidence supports a narrow labeling correction.”** It does not prove a general claim about all issuer comparisons or overall semantic quality.

The change does not address JPM's causal transfers. Both q JPM runs still transfer net-interest-income drivers to total net revenue; q run 0 also carries the EPS/share-count attribution. Those failures are separate and remain.

### 3. The returned conclusion incorrectly says issuer ROE survives in q

`comparison/conclusion.md:22` says JPM's issuer “ROE of 17% and ROTCE of 20%” remains in q output. It does not. Direct inspection of both q JPM summaries finds no issuer ROE string; q run 1 retains only ROTCE. `comparison/q-coexistence-check.md:3-10` states the correct result: the issuer ROE disappeared through resampling, and no q output exercises issuer ROE/ROA alongside the formula-named line.

The same internal inconsistency appears in the agent-authored `hand-check/HAND-CHECK.md`: its early direct-hand-check prose claims ROE survives, while its later synthesis and the retained packet correctly say it does not. The agent hand checks remain useful navigation and corroboration, but they are separate evidence and should not be treated as a replacement for packet inspection.

This gap does not overturn the deterministic naming fix. It limits the empirical claim: the returned runs do not test whether Fable accepts legitimate issuer ROE/ROA prose when it coexists with q's formula line.

The added JPM unit test also does not close coexistence. It supplies the placeholder filing text `Retained JPM filing excerpt.` and then asserts that ROE/ROA are absent from the prompt. It verifies that the application's XBRL label does not introduce those names, but it never places a legitimate issuer ROE/ROA quote in the prompt and checks that the quote survives unchanged.

### 4. The q-only generated findings cannot be labeled noncausal from this experiment

The nine-row inventory is directionally useful:

- Four newly gated G3 texts are byte-present in matched p output: AAPL run 1 `+6.5%`, ASML 20-F run 0 short-term borrowings, RIVN run 1 `(MD&A)`, and WMT run 0's free-cash-flow caveat. These are strong evidence of judge inconsistency rather than changed generated text.
- Five rows contain q-only generated text: PGR run 1 unclassified balance sheet, PLD run 1 classified balance sheet, RIVN run 0 affiliate/Chase fusion, WMT run 1 `+12.9%`, and XOM run 1 weaker Chemical margins. Source inspection supports the judgments: RIVN fuses distinct disclosures; WMT's exact figures imply 12.6%; XOM says margins remained bottom-of-cycle, not that they weakened; PLD's excerpt does not support the claim; PGR's supplied excerpt does not establish the balance-sheet classification.

The inventory calls the five q-only sentences “not the label change.” That is too strong. Their content is outside the ratio sentence and offers no plausible direct semantic pathway from the new label, but the experiment regenerated all prose after changing model-facing prompt bytes. It cannot distinguish prompt-induced global sampling changes from ordinary stochastic variation. They are best described as **nonlocal to the intended mechanism and not causally attributable from these two runs**, while still counting under the adoption rule.

There is additional judge variability around WMT: the same `+12.9%` cell exists in q run 0 but receives G2 only in q run 1. This reinforces the need to avoid effect-size claims from individual slots; it does not erase the gated q run 1.

### 5. A real code-owned FIGS defect remains in q

The only q gate aimed at the changed ratio line is FIGS run 0. Its return-on-equity prior is the sequential quarter, 2026-03-31 at 1.46%, while revenue and the dominant income-statement comparison use the prior-year quarter, 2025-06-30. The rendered sentence says only `(prior 1.5%)` and omits the date. The retained series contains a comparable 2025-06-30 value of 1.79%.

The branch renderer has the prior period available but discards it when building the parenthetical (`markdown_render.py`, branch lines 567–570). This is a code-owned ambiguity and survives unchanged in q. The current formula label is accurate as far as it goes, but q is not a complete correction of the sentence's basis disclosure.

The WMT packet also shows a smaller precision gap: the selected `us-gaap:NetIncomeLoss` value is the parent-attributable $21.893B figure, while Walmart's issuer ROA uses consolidated net income of $22.270B. “Period net income” does not expose that numerator scope. This strengthens the case for naming the selected concept/scope, but no retained judge gated q on it.

## Minimal follow-up, ordered by value

1. **Fix the code-owned comparator ambiguity before seeking an exception or rerunning acceptance.** Include the actual prior period in the deterministic ratio clause (for example, `prior at 2026-03-31`) and preserve the same date on the grounding/render surfaces. This directly closes the retained q ratio-line G5 without changing prior selection policy.
2. **Add one deterministic coexistence test.** Feed a retained JPM-style excerpt that actually contains legitimate issuer ROE/ROA text alongside the XBRL formula line; assert the issuer quote remains byte-preserved and only the application-derived label uses the formula name. This closes the current placeholder-test blind spot without a model call.
3. **Clarify numerator scope only if it can reuse existing XBRL identity.** Prefer a small label such as “selected period net income” or a concept/scope-qualified phrase over a new selection algorithm. Treat numerator selection changes as separate work.
4. **Keep unrelated semantic defects out of PR #942.** The WMT free-cash-flow caveat, leverage inventory wording, and generator attribution errors are real follow-ups, but folding them into this label PR would obscure the isolated mechanism and require a new semantic comparison.

After items 1–2, either rerun the existing acceptance protocol or obtain an explicit scoped founder disposition acknowledging that the global negative-control bar is not tailored to a formula-label-only correction. Do not infer that exception from the segment-margin precedent.

## Baseline pin

The q3 proposal has the required 35 × 3 deterministic shape (105/105 scored; zero errors/retries; exact source recorded in its receipt), so its mechanics are eligible once semantic adoption is settled. It is not semantically admissible now. Its citation-fidelity reference is lower than the current E6 baseline (`0.9532` versus `0.9648`), although other deterministic metrics remain passing. Keep the current pin and leave q3 as a prospective artifact.

## Evidence boundary

This review relied on the repository's current RUNBOOK, the target-branch diff, the retained p/q judgment reports and comparison artifacts, and direct inspection of the JPM, WMT, FIGS, RIVN and q-only G2/G3 summary/source material. The ZIP integrity and call-ledger accounting were accepted as root-verified and were not independently re-performed here. Agent-authored hand-check workflows were read as separate corroborative material, not as Fable judgments or independent ground truth.
