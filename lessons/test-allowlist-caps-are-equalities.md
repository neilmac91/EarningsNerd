# An allowlist cap is an equality, never a ceiling

Date: 2026-10-15   Area: test

**Context**: The brand series (#1288 to #1312, #1295, #1298) keeps every residue and allowlist as a
shrink-only table under a cap. #1288 holds its four lists with equalities (`expect(count).toBe(MAX)`),
and the principal review of 2026-10-15 found four siblings that wrote their new caps as ceilings
instead: #1298's `assert len(EXEMPT) <= EXEMPT_CAP`, #1299's
`toBeLessThanOrEqual(PERIOD_COUNT_OTHER_FACTS_CEILING)`, and the retry-label pair that #1301 and #1295
both lower in `busyControlsStayFocusable.spec.ts` (`<=`, so a merge that keeps either side's number
passes with spare room in the ratchet). A ceiling lets a shrink leave the cap where it was; the next
PR then adds an entry under the unchanged cap, and the gate never refuses the growth it exists to
refuse. The same form sits in seven allowlist specs on main (21 sites). The founder accepted the rule
for the series on 2026-10-15 (D-040).

**Rule**: A cap on a residue list or an allowlist is an equality: `expect(count).toBe(MAX)` in a spec,
`assert len(LIST) == LIST_MAX` in a test. The PR that shrinks the list lowers the cap in the same
commit; a PR that must add an entry raises it in the same diff, where review sees it. A genuine value
ceiling (a z-index bound, a byte budget) is not a list cap and keeps `<=`, with its reason beside it.

**Evidence**: `frontend/tests/unit/allowlistCapsAreEqualities.spec.ts` (the gate: every
`toBeLessThanOrEqual(NAMED_CONSTANT)` in a tracked unit spec is listed in `CEILINGS` with a reason, the
totals equal `CEILINGS_MAX`, and E59 converts the listed list caps after the series lands; the backend
has no residue-list cap on main today, and #1298 lands its `EXEMPT_CAP` as an equality). #1288's
`brandVoiceRules.spec.ts` `VOICE_RESIDUE_MAX`, the equality form. #1298's
`backend/tests/unit/test_frontend_matchers_parity.py:536` (`assert len(UNSOURCED) == UNSOURCED_MAX`)
beside its own `EXEMPT_CAP` ceiling at `test_user_facing_copy_voice.py:681`. The principal reviews on
#1298, #1299, #1301 and #1295 (2026-10-15).
