# Supplemental citation scope — bounded next-plan review, September 13

The existing ASML finding survives. There is no evidence here supporting a general safe semantic repair by regex. The smallest already-prepared product correction is source-match attribution; a backend sentence-removal change should not be represented as necessary or safe merely because this particular redundant sentence can be removed by hand.

## Actual retained regression

Artifact `outputs/pr842-copilot/copilot-fidelity-34734666066/copilot-eval.json`, ASML `us-gaap-sales-net-income-2025`, run_index 0, accession 0001628280-26-011378:

> For the year ended December 31, 2025, ASML reported total net sales of €32,667.3 million [1] and net income of €9,609.4 million [2]. The filing's operating results table confirms these figures, showing "Total net sales 32,667.3" and "Net income 9,609.4" for 2025 [3].

[1] is revenue EUR32,667,300,000; [2] is net income EUR9,609,400,000, both selected 2025-01-01–2025-12-31 facts. [3] is only:

> Total net sales 28,262.9 100.0 32,667.3 100.0 15.6

Actual cached `0001628280-26-011378/excerpt.txt` contains that exact whitespace-normalized row, following a 2024/2025 euro-million header. Neither inline quoted snippet (“Total net sales 32,667.3”; “Net income 9,609.4”) is a contiguous normalized source substring: they compress table columns. The primary figures are correct; the claimed supplemental quotation/support scope is not. Other two ASML draws simply give the correct two fact-backed values without this extra sentence. Seven total text citations exist in the 18-answer artifact; the cited acceptance review verifies their excerpt occurrence, not entailment.

**Should-fix existing scope defect.** Refutation 1: read actual selected-source row and surrounding header/table; correct source occurrence and unit/year context refute invented-source suspicion, but the selected [3] row contains no net income. Refutation 2: inspect both primary chip values/accession/durations and the other two ASML draws; they refute wrong-number/inability-to-answer allegations, but cannot make [3] support the added second assertion or turn compressed row snippets into verbatim quotations. This is not a newly introduced operating-to-pretax regression.

## Actual admission contract

`backend/app/services/copilot_service.py:400–425` checks each declared text excerpt with `verify_excerpt_in_text`, then sets `verified` and source fragment URL. `_resolve_citations:931–1038` assigns markers from actual inline uses. Its value/concept/currency adjacency guards apply to fact-backed markers; text citations are checked for source occurrence, without a claim-span association or entailment proof. The prompt at :99–109 already requires a shortest contiguous supporting excerpt, forbids stitched table cells and says not to add redundant text citations for tool values. More prompt instructions alone do not enforce this observed failure.

## Options and recommendation

**Finish the attribution correction already prepared.** Current isolated `work/citation-source-labels/.../citationVerification.ts` deliberately uses “Source match found” plus “A source match does not verify every claim in the answer.” That avoids inferring citation kind from model-controlled labels. Preserve excerpt, marker, source URL, accessible navigation and primary chips. This reduces verification overclaim; it does not fix the ASML sentence. Do not reopen backend scope or claim semantic acceptance from that wording.

**Do not suppress [3] alone.** It would leave the explicit table-confirmation assertion and two compressed quotations visible without a source, and can make the answer less inspectable. Marking an actually matched excerpt `verified=false` would also conflate mismatch with unsupported surrounding prose, corrupting the current API/telemetry meaning.

**Do not remove every sentence containing a supplemental text citation.** Such sentences can contain unique filing explanations, legal context or quoted source evidence that numeric tools cannot replace. This artifact supports removing this exact second ASML sentence manually, not a general rule for finding all redundant or partly supported claims. “Confirms”, multiple amounts, named concepts, or citation position are insufficient semantic boundaries. Nor may source proximity fill the missing net-income row or infer accounting basis from a missing raw tag.

**Next backend scope, if selected: source-owned supplementary passage representation.** A distinct optional structured source-passage channel could render a generic “Filing excerpt” followed by the exact matched excerpt, with no model-generated confirmation/inference sibling. It would preserve useful supplementary evidence while making the type of assertion code-owned. Keep primary answer/fact chips and numeric repair unchanged. This requires a deliberately specified output contract and migration of the supplemental channel; current flat free-form prose does not identify which sentence is safely removable. It must not silently transform all qualitative answers into quotes or pretend to solve entailment for the remaining prose. Treat this as a design/prototype slice before paid assessment, not a drop-in two-line fix.

## Done criteria and integration boundary

A future backend candidate must reproduce this actual final ASML answer plus exact selected source/DB facts through the real resolver/answer entry point, preserve the two correct primary chips and their full numeric provenance, and prevent the new source-owned channel from asserting support for the missing second row. Negative controls must retain unique qualitative source passages and leave unsupported/unclassified free-form prose explicit, rather than deleting it accidentally. Test mixed citation positions, repeated markers, tables, missing source and partial streams. Raw original provider marker spelling was not retained by the final artifact; do not claim the replay reconstructs that unseen stream.

Root owns backend publication, full gates, mutation proof and paid acceptance. Keep the current frontend attribution lane separate from any backend contract work. No finite backend parser is recommended from this evidence alone; preserve the finding as unresolved until a concrete representation contract makes the change reviewable.
