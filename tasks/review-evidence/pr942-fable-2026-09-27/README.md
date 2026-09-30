# PR942 Fable comparison: evidence and engineering disposition

27 September 2026. The returned judging programme is complete. **Do not promote q or apply the q3 baseline proposal.** PR942 remains draft; production remains on p. Retaining p is an operational hold, not an acceptance of p's quality. Formal E7 generation has not started.

## Evidence received

The [transport receipt](transport-verification.json) verifies both archive SHA-256 values, exact sizes and entry counts against the supplied manifest before extraction. ZIP CRC, path traversal, symlink and duplicate-file checks passed; the restored directory contains 1,871 files. The separately attached receipt is byte-identical to the archived receipt. Raw archives, reports, request/response channels, agent hand-checks and original conclusions are retained unchanged in the operator workspace under `outputs/pr942-fable-ingest-2026-09-27/`.

The comparison uses retained p run [36272463033](https://github.com/neilmac91/EarningsNerd/actions/runs/36272463033) and q run [36276521637](https://github.com/neilmac91/EarningsNerd/actions/runs/36276521637), with the unchanged judge at `2a00fcfadee12845c3cae906b681b454d18916e5`, contract 2, `cli:claude-fable-5-1`. This comparison is separate from E7 and E8; its calls do not redraw either programme's evidence.

## Independent recomputation

The [accounting/provenance audit](accounting-audit.json) reconciles all 140 frozen packets, exact prompt bytes and subprocess arguments, reservations, raw responses, parsed verdicts and assembled report rows. The judge files match the required Git commit. Both arms have 70 judged / 70 judgeable slots, zero judge errors and no pending slots. There are 140 recorded physical calls of the 280-call ceiling, all first attempts, with maximum concurrency two. All retained responses report `claude-fable-5-1`; none has truncated input or an incomplete terminal result. These are checks of the retained evidence, not independent observation of remote execution. The omitted CLI binary and hashed endpoint value cannot be independently re-observed from this handback.

| Arm | Negative / judged | Run 0 | Run 1 | G2 | G3 | G4 | G5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| p | 48 / 70 (68.6%) | 25 / 35 (71.4%) | 23 / 35 (65.7%) | 0 | 17 | 31 | 26 |
| q | 40 / 70 (57.1%) | 19 / 35 (54.3%) | 21 / 35 (60.0%) | 2 | 14 | 22 | 22 |

Paired results are 13 both pass, 31 both fail, 17 p-fail/q-pass and nine p-pass/q-fail. The lower observed q negative rate does not establish a causal effect of the label: generated text differs between arms and the judge sometimes treats identical text differently. Hand-checks are agent-authored source readings, separate from the contract verdicts and from human review.

The CLI's nominal cost fields sum to USD 210.783710 under the retained subscription metadata. This is not an API invoice or verified billed expense. Ingestion and independent audits made no new model calls.

Three outgoing reporting corrections preserve all original files and verdicts:

- The exact new-q gate union is **nine matched identities: seven new G3 plus two disjoint new G2**, not seven combined G2/G3 findings. The delivered comparison table and raw verdicts support the corrected count.
- The early claim that JPM's issuer “ROE of 17% and ROTCE of 20%” survives alongside the q formula line overstates the evidence. The later coexistence check correctly reports only ROTCE in q JPM run 1. That does not exercise issuer ROE/ROA beside the formula-named line.

- Five of the nine new-q gate rows concern generated text absent from matched p; four have the same flagged text in p. The five q-only sentences are outside the ratio line, but changed prompt bytes and regenerated prose prevent a claim that those differences are causally unrelated to the change.

## Adoption decision

The [independent semantic review](semantic-adoption-review.md) and its [machine-readable disposition](semantic-adoption.json) confirm the decision after source inspection of JPM, WMT, FIGS, RIVN and the q-only G2/G3 cases. Its source readings are AI-assisted, not human acceptance.

The [RUNBOOK grounding-candidate bar](../../../backend/evals/RUNBOOK.md) requires controls to abstain from unsupported explanations, no new G2/G3 failures, and an unchanged deterministic regression gate. PR942 changes generator grounding and its actual instruction as well as rendering, so the bar applies. A local label improvement does not waive it.

The candidate does not meet that bar. Keep `baseline_scores.json` unchanged; do not apply the prospective q3 citation-fidelity reduction from 0.9648 to 0.9532. Preserve the 105-output q3 report as evidence, not an accepted replacement baseline. Keep the existing production content stamp, attribution flags and generation scope unchanged. The completed 140-slot queue must not be repeated to obtain more favorable verdicts.

The formula label has a credible narrow benefit: JPM run 1 and WMT run 0 no longer receive the period-end-versus-issuer-ratio name-collision gate. FIGS run 0 remains gated because its sequential-quarter comparator is labeled only “prior”. Neither the label correction nor lower aggregate negatives establishes that q solves causal transfer or meets E7 acceptance.

## Next implementation tranche

1. Keep #942 focused: date the actual return-ratio comparator (FIGS), test legitimate issuer ROE/ROA alongside the formula line (JPM), and clarify numerator scope only where the existing source concept supports it (WMT). Preserve prior-selection policy and valid issuer disclosure. The returned q outputs do not exercise the coexistence case.
2. Track the free-cash-flow issuer-definition caveat and misleading missing-filing language as separate source-backed wording corrections. Use the retained WMT, JPM, AAPL and ASML cases; preserve useful supported content rather than deleting it to improve a score.
3. Address the separately evidenced causal-transfer path (especially JPM net-interest-income drivers transferred to total revenue) as its own bounded candidate. Keep original outputs and judgments; evaluate corrected outputs under a stated, metered protocol rather than weakening the adoption rule or reclassifying failures as passes.
4. Resolve the chosen candidate before E7 freeze. Source views, complete role briefs/reconciliations and review capacity can progress independently; the paid holdout remains held until the actual configuration and source prerequisites are ready.

No additional Fable run or founder decision is needed merely to accept this handback and retain q on hold. The next measurement is a new, explicitly scoped engineering decision; unused invocation capacity is not a reason to redraw completed slots.
