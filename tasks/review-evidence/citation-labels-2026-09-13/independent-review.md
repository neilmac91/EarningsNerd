# Citation labels independent review — 2026-09-13

Reviewed final `96bad10202e73901bc24e21cc69d0837ddc4ad2c` against main `5c050cc3d7efabe9360927abf5aecb214f9bc34c`. Read-only: no test execution, repository edits, network, model or publication actions. Read AGENTS.md, CLAUDE.md, DESIGN_SYSTEM.md, relevant citation-offset, preview and Next-build lessons, the full application/test diff, task ledger, backend verification/resolution owners and saved gate/proof output.

## Ranked findings

### Should-fix: numeric assurance still depends on a model-controlled source label

`frontend/features/filings/components/copilot/citationVerification.ts:9`, with `CitationChip.tsx:177` and `CopilotMessage.tsx:270`.

An ordinary text citation can contain a correctly matched quotation and model-supplied `section_ref="XBRL …"`. The unchanged API convention treats this as numeric. The new UI then says “Numeric source verified” and withholds the excerpt-match scope explanation even though only text matching occurred. This is not a claim that the backend numeric fact checks are weak; this particular citation never traversed those checks.

Refutation attempt 1: checked backend `_verify_citations` (`copilot_service.py:400–429`). It copies `section`/`section_ref` from the model, with `verified` obtained only from `verify_excerpt_in_text`; no source-kind attestation or reserved-XBRL rejection exists. Refutation attempt 2: checked `_resolve_citations` and frontend `copilot-api.ts:22–24`. The backend assigns numeric display markers to both kinds; frontend's OR predicate accepts an XBRL-prefixed section independently of marker provenance. The prior dense visual presentation already had this ambiguity, but explicit numeric verification wording strengthens the assurance.

Small frontend-only remedy: use neutral “Source check passed” wording and an explanation that covers both matched passages and numeric sources, unless an authenticated numeric-kind discriminator is added separately. Do not broaden backend scope merely to preserve a label. Root should adjudicate the bounded copy change; no code was changed here.

### Should-fix: added popover text can exceed the unchanged positioning allowance

`frontend/features/filings/components/copilot/CitationChip.tsx:177–180`, interacting with `:69–71` and the card at `:149–164`.

A verified text citation near y=250 with an excerpt tall enough to reach max-h-40 takes the “above” branch. The old one-line header, capped excerpt and badge can fit in the approximately 242 pixels above the chip; the new scope paragraph adds several lines and can move the card's top outside the viewport. The added content expands an existing position heuristic's failure region. No browser geometry was measured in this read-only review; the structural overflow path is definite, and root's visual pass should verify the exact viewport/font case before choosing the fix.

Refutation attempt 1: inspected height containment. Only the excerpt has max-h-40/overflow-y-auto; the new paragraph and entire popover have no viewport max-height or scroll containment. Refutation attempt 2: inspected positioning and dismissal. A fixed 220-pixel trigger-height threshold decides above/below; no measured card-height correction or viewport clamp follows rendering. Scroll/resize listeners dismiss the card but cannot prevent its initial clipping. Prefer measured placement or bounded whole-card height, preserving keyboard access and the Open original action.

## Correctness lens: refuted candidates

The normal text path no longer presents excerpt matching as verification of surrounding claims: both Sources and focused popover contain explicit scope language. `verify_excerpt_in_text` normalizes typography/spacing and can select the quoted span from a larger evidence string, so “quoted passage” is appropriately narrower than asserting every displayed character matches. The footer's matched-source count describes the backend's count of distinct resolved verified citations; no whole-answer success claim remains there.

Numeric-label wording does not explicitly promise annual duration, full issuer scope or semantic entailment. Existing numeric sources still pass provenance and adjacency guards; their amounts, source excerpts, links and markers are untouched. This refutes a blanket numerical-verification regression, while the source-kind ambiguity above survives separately.

Chip/link loss was refuted by the unchanged marker injection, http(s) URL guard, viewer handler and fragment target code, and by retained navigation assertions plus the mixed-source keyboard-popover test. Sources wrapping remains flex-wrap with min-w-0; no new palette or typography token was introduced. Actual narrow-screen and both-theme fit remains root's visual acceptance, particularly the popover issue above.

## Rules-and-brief lens

The diff is limited to frontend components, ordinary tests, DESIGN_SYSTEM documentation and a task record. No orchestrator, filing data, SEC transport, model/prompt, entitlements, migration, config or pricing boundary changed. The implementation corrects the previous DESIGN_SYSTEM wording in the affected contract paragraph. No theme/token migration occurs. All eleven locked anchors are byte-identical against the reviewed main; exact hashes are in `outputs/citation-labels-locked-anchors.json`.

## Tests-and-gates lens

The saved full gate on feature `45a0a61fcd9b50a074ca4e151d66aa0dea546a29` is application/test-equivalent to final head; only the task ledger differs. Lint and TypeScript logs contain no reported errors. Full Vitest tail: 106 files passed; 593 tests passed; 31.79 seconds. Build log records successful compilation and 27/27 static pages. No test was rerun by this reviewer.

The one attribution invariant mutation `acbc8f7177afe8da6145ceb40884d87c1ea8dc9a` causes 1 failed / 14 passed. Restoration `ceddc5359b1b640ebcee7893becab50206ed8a1d` has the identical feature tree `83e117a9c41490da3f9e5dea54de8eefe2c0c2f1` and 15 passed. The fixture checks retained mixed-source shape, exact excerpt/link and focused popover distinction. This proof is valid for ordinary source-kind conventions; it does not refute the model-controlled-section counterexample or viewport geometry.

The ledger correctly retains the earlier stale-footer test failure and dependency/build environment failures without treating them as successful gates. It explicitly leaves independent review and both-theme preview pending. This review gives no visual or deployed acceptance and no publication clearance while the two findings await root adjudication.


## Root-adjudicated wording correction

Root chose neutral “Source match found” plus “A source match does not verify every claim in the answer.” I implemented this bounded follow-up at feature `01492a7deb9f7741bced40fa0fac51862ede05bc`, preserving visual grouping and adding the model-labelled-XBRL counterexample to the existing invariant control. The source-kind assurance finding is resolved. Focused 15 tests pass; updated same-invariant mutation `764f13efc8118457a45fb005c4d3690acb6a59a2` yields 1 failed/14 passed and restored head `f5e502e345132a47b2164c0048c5632eb49d64b5` has feature-identical tree `d1278a4c718d1f2eb756d5d9326bca053e925c89`, with 15 passed again. Full logs are `outputs/citation-attribution-neutral-{feature,mutation,restored}.log`. Root owns layout adjudication, final full frontend gate and both-theme visual acceptance; the earlier independent-read-only review remains the record for its original head.


## Final correction and clearance

The viewport finding is now resolved by measured placement, whole-card viewport bounds and internal-scroll preservation. Root reproduced the original top −67 / bottom 245 geometry and verified the corrected top 279 / bottom 591 card in an 863 px viewport; full visual scope and fallback-font limitations are recorded in `outputs/citation-labels-root-visual-review.md`. The pre-existing long XBRL tag overflow remains a bounded unrelated limitation.

A follow-up runtime-path mistake was caught and recorded: the initial follow-up PATH fell back to Node18. Those outputs do not fulfill the final Node22 gate. Both same-invariant proofs and the full gate were re-established under directly verified `/usr/local/bin/node` v22.14.0. Final application head `1f4bdf110fe758aace29e8e1d91b47722ef0ecd6` passes lint, TypeScript, 106 files / 595 Vitest tests, and unchanged production build. A independently completed the successful build after archiving only generated `.next`; the prior worker-port failure's exact cause was not proved.

Final source-scope proof: `f6bdb1dc756358c7728886813a36ab8ff71dac8b` gives 1 failed / 14 passed, restoration `7128b59635e2606bd284cf3fd708ffad9509f78d` gives 15 passed. Final viewport proof: `bf8cc56cae7d231be9e6c2eae4023374ecfe2bfc` gives 2 failed / 3 passed, restoration `1f4bdf110fe758aace29e8e1d91b47722ef0ecd6` gives 5 passed. Both restore the complete feature tree `ce56956a705c4ad4a8df0dcdfe7aa7ee17dcad14`. Final ledger-only head is `2cd9ace36e634e3b789eee4b0801023b4ce6348a`; application and tests are unchanged from the gated head. All eleven locks remain identical, with no new scoped correctness/rules/gate survivor. This is engineering clearance for root's normal publication process, not a claim of deployed Vercel acceptance.
