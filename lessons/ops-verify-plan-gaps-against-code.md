# Re-read the actual code before implementing any plan item marked missing

Date: 2026-06-16   Area: ops

**Context**: Executing the auth/privacy plan, almost rebuilt analytics consent-gating, the Privacy Policy, and the GDPR export/delete UI — all three already existed and were well-built. The audit/plan flagged them as gaps from a distance; the code said otherwise.

**Rule**: Re-read the relevant files immediately before implementing any plan item, even one the plan marked "missing". Confirm the gap is real before writing code — re-implementing working code is wasted effort at best and a regression risk at worst.

**Evidence**: `posthog-provider.tsx` gates on consent; `/privacy`; `/dashboard/settings` — all already existed.
