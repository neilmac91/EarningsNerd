# Exact-head review, round 2 (head `61cce875`): findings as received

Three independent lenses (scope and correctness, model behaviour, rules/gates/custody) reviewed head
`61cce875f73fc1563c157e77119e6f2f4edb343f` (the round-1 fix commit on merge `3264cdcc`, base `b40fa703`). The
findings below are the reviewers' text as handed to the implementer, kept verbatim. The README section "Review round
2" records how each one was resolved.

## Blocking and should-fix

### R2-1. scope-and-correctness, SHOULD-FIX

**Where:** tasks/review-evidence/prompt-candidate-2026-10-02/PREREGISTRATION.md:53-55 ('Disclosed deliberately',
second bullet); introduced by 61cce875

**Finding:** The frozen pre-registration cites a quotation that does not exist in the run it names. It says
`"by 3% to RMB1,023,670 million …"` (run 36800236360 d1) passes F's per-span test. The published d1 quotation in that
run is `"by 3% to RMB1,023,670 million (US$148,401 million) in fiscal year 2026"`, with no ellipsis. I checked the
whole row JSON (answer, candidate_deltas, service events) of every BABA row in 36800236360: there are 0 U+2026
characters. No answer or candidate in any of the 23 retained runs contains '1,023,670 million' together with an
ellipsis. Grepping the scratch directory for the string finds it only in prompt-research/failure_shapes.md:127, where
'…' abbreviated the span. R1-N2 then quoted it as if it were literal, and the fix commit copied it into the PREREG as
evidence. The mechanism itself is true: I ran the product's unsupported_prose_quotations on that row's source, and it
returns [] for both the '…' and '...' edge-ellipsis variants and ['elided_quotation'] for an interior one. But the
file attributes to a specific retained draw a model behaviour that draw never showed, so it overstates the observed
reach of the new 'never put an ellipsis' ban. The file is hashed at step 0 and cannot change after freeze. The
README:140 example carries no run attribution and is fine.

**Fix:** Before freeze, edit PREREGISTRATION.md:53-55. Either drop the run attribution and mark the example as
illustrative (for example 'an edge ellipsis such as `"by 3% to RMB1,023,670 million …"` passes F's per-span test
after stripping'), or state that no retained run used an edge ellipsis inside a quotation. Then regenerate the
PREREG sha256 for the step-0 comment.

## Nits

### R2-N1. scope-and-correctness

**Where:** tasks/review-evidence/prompt-candidate-2026-10-02/composed_quotes.py:44-48 (uses
quote_inventory.classify(...)[1] only); PREREGISTRATION.md:191-197 ('Registered measurement')

**Finding:** The registered reading is described as F's per-span test, but it omits F's floor. F skips a span whose
marker-blanked, edge-stripped needle is under _MIN_QUOTED_LEN (8) with no interior ellipsis (copilot_service.py:897),
treating it as a label. The audit's floor counts raw characters between the marks (`"([^"]{8,})"`). So a short label
padded to 8 or more characters by an inner marker or edge punctuation can be flagged by the audit. If it is absent
from the source, composed_quotes then calls it composed, even though F exempts and publishes it. Example:
`"OpEx [1]"`. The product returns [] for `"EBITDA [1]"`. This is rare and only in the stricter direction, but it is
the same class of measurement-caused false failure that the reading exists to remove, and the PREREG does not
mention it.

**Fix:** In composed_quotes.py, classify a flagged span whose needle is under 8 characters, with no interior
ellipsis, as 'F-exempt label' (reported, not composed). Alternatively, add one sentence to the PREREG and README
limitations saying the reading omits F's floor and is stricter than F there.

### R2-N2. scope-and-correctness

**Where:** PREREGISTRATION.md:19-27 (Base) and precondition 2; README.md:5-12

**Finding:** Main has moved again since the integration merge: origin/main is now ed58cee7 (09c8bf4d #1064 frontend;
ed58cee7 #1071 docs plus tasks/). `git diff --name-only b40fa703 origin/main -- backend .github` is empty, so
precondition 2 holds and the measured backend equals the gated one. A trial `git merge --no-commit origin/main` in my
scratch worktree was clean, and the 14 tasks-reading backend tests passed on it (386). 'The gated tree is the tree
the runs measure' is now true for backend/.github only; the merge ref will also carry #1064/#1071.

**Fix:** No change needed. Record the origin/main SHA in force at step 1 alongside the precondition-2 diff result in
the #1029 comment.

### R2-N3. model-behaviour

**Where:** tasks/review-evidence/prompt-candidate-2026-10-02/PREREGISTRATION.md:167-173 ('Why the raw audit cannot
be the measurement'), :191-197 ('Registered measurement'); README.md:108-110; composed_quotes.py docstring

**Finding:** The registered reading clears every normalization gap between the audit and F. It does not clear F's
markdown rendering, which quote_inventory.py's docstring says is not copied. The pre-registration still says that on
this build a raw audit hit 'is a normalization artifact or an F defect', and it lists only normalization gaps.

I checked the product's unsupported_prose_quotations offline against retained run 37029964566's ASML source:
- Markdown emphasis inside a quotation publishes under F, but composed_quotes.py classes it 'composed'. Cases:
  `"**Total net sales**"`, `"**Net income**"`, `"*Net income for 2025 amounted to €9,609.4 million*"`, and
  `"Net income for 2025 amounted to **€9,609.4 million**"`.
- So a run could fail check 4, and check 3 on ASML, with no composed quotation.

The exposure is low:
- 0 of 402 retained published answers contain `**`.
- Every one of the 15 audit spans on the 23 runs matches a span in F's own rendered reading.
- The strict reading would fail these cases too, so the fix introduced no regression.

The risk is documentation. If this happens, the frozen file gives the reader no way to tell a rendering artifact from
a real composition.

**Fix:** Add one sentence to the 'Why the raw audit…' paragraph and the README: F's markdown reading (emphasis
delimiters * _ ~) and its quote pairing are not copied. A published quotation that contains markdown emphasis is
therefore still read as composed under the registered reading, and is reported with its span. Keep the measurement
as it is, so Codex's acknowledgement under precondition 5 covers it unchanged.

### R2-N4. rules-gates-custody

**Where:** tasks/review-evidence/prompt-candidate-2026-10-02/PREREGISTRATION.md:66 (identity table, 'Runtime between
runs'), :80-82 (precondition 2), :122-128 (Validity)

**Finding:** The validity chain has no anchor to the frozen head. Precondition 2 compares b40fa703 with origin/main
once, at step 1, before the draft opens. The chain then compares only consecutive merge refs: eval-baseline, Q1, Q2,
Q3. Suppose a backend merge lands between the precondition-2 check and the draft opening. Every merge ref would then
contain it. The chain and the step-2 `^1` check would both pass, and the measured tree would differ from the gated
tree without anyone seeing it. Precondition 4 (the backend-slot acknowledgement) makes this unlikely, and the window
is short. Still, the file claims 'the gated tree is the tree the runs measure' and does not check it mechanically.

**Fix:** Add one condition to the identity table's runtime row and to Validity: for every run (eval-baseline, Q1, Q2,
Q3), `git diff --quiet <frozen head> <source_sha> -- backend .github` exits 0. Both sides contain the candidate, so
this works directly. It subsumes the consecutive-pair chain and binds R(i) and Q1–Q3 to the gated tree.

### R2-N5. rules-gates-custody

**Where:** PREREGISTRATION.md:75-79 (precondition 1, enumerated list)

**Finding:** The general rule ('every backend-touching merge on main … has a verified deploy receipt') is correct.
The enumerated 'that list' leaves out #1041 (5525a91d, backend/app/data/index_membership.json, merged between #1056
and #1060). #1060's verified revision 00436-pkk already contains #1041's change, so nothing is unverified in
practice, but the list as written is incomplete. Context checked read-only on #1029: #1066 was verified as 00438-v8g
(comment 5962491931) and #1067 as 00439-llg (comment 5962762092), and the slot is released. Precondition 1 and the
slot-release part of precondition 4 are therefore currently satisfiable.

**Fix:** Add #1041 (covered by #1060's 00436-pkk) to the list, or call the list 'including' instead of 'that list
was'.

### R2-N6. rules-gates-custody

**Where:** tasks/review-evidence/prompt-candidate-2026-10-02/README.md:160 (Review round 1 table, R1-1/2/5
resolution)

**Finding:** The README says 'This lane cannot post on #1029'. That contradicts PREREGISTRATION step 0, where this
lane posts the step-0 comment on #1029. The intended meaning is that Codex's acknowledgement cannot be obtained
before the freeze.

**Fix:** Reword to: 'Codex's choice cannot be obtained before freeze, so both readings are fixed in the frozen file
and Codex's choice is recorded on #1029 before step 1.'

### R2-N7. rules-gates-custody

**Where:** composed_quotes.py:44-47 with quote_inventory.classify; PREREGISTRATION.md:191-197

**Finding:** The registered reading is stricter than F in one narrow case: a sub-floor term with a citation marker or
edge punctuation inside the marks. Take `"EBITDA [1]"`. Its raw text is 10 characters, so the audit flags it. F
blanks the marker, gets a 6-character needle, exempts it as under the floor and publishes. `in_source` does not apply
the floor, so the span is classed composed and fails check 4. This conservative direction cannot clear a real
composition, and the shape is rare. Still, a false 'not qualified' with no retry is possible.

**Fix:** Optional before freeze: in composed_quotes.py, treat a flagged span whose F needle is under 8 characters and
has no interior ellipsis as 'audit normalization difference (sub-floor)', and state it in the registered-measurement
paragraph. Otherwise, disclose it as an accepted exposure in the paragraph and the handback limitations.
