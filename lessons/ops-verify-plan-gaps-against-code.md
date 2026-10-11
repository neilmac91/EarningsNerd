# Re-read the actual code before implementing any plan item marked missing, or listing one as open

Date: 2026-06-16   Area: ops

**Context**: Executing the auth/privacy plan, almost rebuilt analytics consent-gating, the Privacy Policy, and the GDPR export/delete UI — all three already existed and were well-built. The audit/plan flagged them as gaps from a distance; the code said otherwise.

**Rule**: Re-read the relevant files immediately before implementing any plan item, even one the plan marked "missing". Confirm the gap is real before writing code — re-implementing working code is wasted effort at best and a regression risk at worst. The same holds when you write an open list for someone else to implement: check each item against the current code before you list it, and say what was checked and where.

**Evidence**: `posthog-provider.tsx` gates on consent; `/privacy`; `/dashboard/settings` — all already existed. On #1197 (2026-10-11), the comprehensive review's open list, which the hand-over told the next agent to implement, still named three changes `main` had already made. The dialog's summaries carry `tabIndex={0}`, so `Modal`'s focus list includes them. The chart letters use `chartTheme(dark).label`. `figureDisplay.ts` maps the per-share currency and operand units. The founder's review caught them before the hand-over (`tasks/analysis-redesign-2026-10/review-2026-10-10.md` items 16, 22 and 28).
