**Verdict: NEEDS CHANGES.** The changes are small and stay inside the wording. Rule A would plausibly stop both retained shapes: the ASML label-plus-one-cell quotes and the BABA quotes with an ellipsis inside. Three phrases in A add risk on the measured path without adding any benefit there. Neither the deletion (a) nor the rule's subject matter needs to change.

I worked read-only at `153cfc46`; the worktree is still clean. I made no provider call and no GitHub write. My one scratch file is `/tmp/claude-0/-home-user-EarningsNerd/4aaef390-9924-5295-aa90-251d71b700b2/scratchpad/prompt-research/critique-mb/compose_d.py`.

## Issues, most severe first

**1. "state table figures without quotation marks" may bring back the tool-skipping cue, and the checks would mostly miss it. Severity: medium-high.**
- **Why it's risky.** It is the only part of A that tells the model what to put in the answer (state figures from the table) rather than how to use quote marks. Hypothesis 1 is that answer-shape text makes skipping tools look compliant, because every requested figure is already in the context (`tasks/copilot-tool-nonexecution-2026-09-30.md:155-160`).
- **Placement makes it worse.** A sits directly after the no-tool fallback sentence: "If a tool returned an error (or you did not call one) and you state a number quoted from the filing text instead…" (`copilot_service.py:109-111`). The result is two consecutive "state a number / state table figures" directives about the text path.
- **The brief's mitigation doesn't hold.** It argues that placing the rule after every tool directive protects tool use (design.md:73, :79, :320). But the deleted clause was also after every tool directive (offset 2914 against the tool MUST at 674), and it still caused the 20-F suppression (`tasks/copilot-tool-nonexecution-2026-09-30.md:291`, :328-331).
- **The checks would mostly miss a regression.** In G plus later main, 58 of the 59 tool-less 20-F rows published with server-repaired XBRL citations and no quotes. The one exception is C1 BABA d2, which errored on a string-ID declaration under arm C. Most re-suppressed draws would therefore pass checks 1-5 (design.md:316). The exception is the uncited-ASML shape, which can fail check 5 (`tasks/copilot-tool-nonexecution-2026-09-30.md:93-96`).
- **Fix:** replace the imperative with formatting-only wording: "Keep table figures outside quotation marks".

**2. The absence sentence sits on the disclosed path with no measured benefit. Severity: medium.**
- "When you say the filing lacks a metric…" assumes absence statements happen. Two bullets earlier, the prompt says "never announce that a figure was omitted or unavailable" (`:100-102`).
- It is the only wording in A that touches a scored gate. Refusing a disclosed question fails REFUSAL (`evals/copilot_scorers.py:136-139`, :257-262).
- All 6 live questions are disclosed, so its benefit can't be measured (design.md:117).
- **Fix:** use C's placement, in the not-disclosed template only (`:143`): "…; name the missing metric without quotation marks>".

**3. "may enclose only one … such as a sentence or phrase" invites quoting and is ambiguous. Severity: low-medium.**
- **Quoting only adds risk.** No scorer check rewards quotes (`copilot_scorers.py:1-26`), and any failed quote withholds the whole answer. 10-K answers almost never quote: 1 of 108 rows in G plus main, and 1 of 90 earlier (`failure_shapes.md:130-140`).
- **ASML has no sentence to quote for net sales.** In the ASML context, 32,667.3 appears only as a table cell (scratch `asml_ctx.txt:1025`) and the KPI tile shows €32.7bn (:672, :880). The net-sales MD&A sentence carries no total (:1117-1125). So pushing the model toward sentence quotes there invites a reconstructed sentence.
- **ASML text is fragile to quote.** The extraction has about 91 words broken across lines ("Ho\nw", "p\nerformance"). A model that silently repairs them produces a quote that `normalize_for_match` will not find in the source.
- **"only one" can be read as a limit of one quotation per answer.**
- **Fix:** drop "such as a sentence or phrase" and frame it per quotation: "Each quotation in your answer must be one contiguous span copied verbatim from the filing." This still allows genuine contiguous quotes, which is all "preserve" requires.

**4. A contradicts itself on full rows. Severity: low.** "Never quote a table row with cells left out" implies a full row may be quoted, while "state table figures without quotation marks" says no table figure may be. The fix in issue 1 resolves this.

**5. "a label joined to its value" is unclear. Severity: low.** "Joined" can be read as the glued AAPL extraction (`Total net sales416,161`, from the AAPL context in the artifact for run 37029964566) rather than a label followed by a figure. **Fix:** "a label with its value".

**6. The model could switch to quote forms that nothing checks. This is a measurement gap, not a wording problem.**
- Decision F and `prose_quote_audit` only see double quotes (`copilot_service.py:500-506`; `RUNBOOK.md:726`, "Single quotes, guillemets… are not checked"; `prose_quote_audit.py:60`).
- Baseline: 0 of 384 retained answers across 22 runs use single quotes, backticks, guillemets, blockquotes or italicised figures.
- **Fixes:**
  - Keep the generic phrase "quotation marks"; never narrow it to "double".
  - Add these forms to the pre-registered quote inventory, and report any table figure inside them as displacement.

**7. Make a 20-F tool-use regression visible.** Predeclare a descriptive label for it. One example: a run with 20-F tool-using question-runs ≤ 1/3, against arm B's 3/3 per run (`tasks/copilot-tool-nonexecution-2026-09-30.md:322-330`), is labelled "deletion effect not preserved". This adds no new check, but it stops a run from qualifying silently while undoing the reason for the deletion (design.md:316).

## Proposed wording D (replaces A)

RULES bullet, in A's position:
> - Each quotation in your answer must be one contiguous span copied verbatim from the filing. Keep table figures outside quotation marks, and never put quotation marks around a label with its value, a table row with cells left out, or text with an ellipsis inside it.

Not-disclosed template extended at `:143`:
> <one sentence stating what is missing and why this filing would not contain it; name the missing metric without quotation marks>

- **Size and hash:** 46 + 7 words. Composed in memory: sha256 `ed566fc5d262c0ba8db898d9663a2b4a6587e5046c09609574715301927411e4`, 5322 characters.
- **Identity:** removing both insertions gives arm B (`16457055`). The clause is absent, the only non-ASCII character is the em dash, the new text has no braces, and the step-3 pins are untouched.
- **Fallback:** if reviewers also want the absence sentence in RULES, append A's last sentence unchanged (rules-only form: `2ed7b66d…`, 5273 characters, without it).
- **Owner-test assertion updates** (design.md:145-148):

| Assertion | New text |
|---|---|
| Rule head | "Each quotation in your answer must be one contiguous span copied verbatim from the filing" |
| Table figures | "Keep table figures outside quotation marks" |
| Absence | "name the missing metric without quotation marks>" |

**How D covers each shape:**
- Label plus cell, AAPL label plus value, the near-miss `"Net income 7,571.6"`, and bare cells: "Keep table figures outside quotation marks" and "a label with its value".
- BABA `"Revenue ... 996,347"`: the ellipsis clause.
- Still allowed: the BABA and ASML MD&A sentences (not table text), quoted labels, and edge ellipses (`test_copilot_prose_quotations.py:110`).
- Target shape: the unquoted cross-check already happens without instruction (B1 ASML d0, A1 d2, A2 d1, C2 d1), so no worked example is needed.

## Concerns checked and found not to be problems

- **MSFT string IDs (check 1):** neither A nor D touches the JSON. The "never a string or an F marker" sentence and "output []" stay (`copilot_service.py:119-121`). Arm B emitted `[]` on 6 of 6 MSFT draws.
- **AAPL/TSLA/MSFT tool use (check 2):** 10-K questions called tools in every draw under every prompt except #1023's lead-rule rewrite (`tasks/copilot-tool-nonexecution-2026-09-30.md:73-79`). D does not touch `:90`.
- **The model stopping quoting altogether:** no scorer gate depends on quotes (`copilot_scorers.py:1-26`, :252-262), so this would only cost authenticity.
- **Quotes spreading to other surfaces:** follow-up chips have 0 of 429 quotes, and quoted section labels are 0 across 22 runs. "In your answer" keeps the JSON arrays out of scope.