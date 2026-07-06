# Re-read the actual files before implementing a plan item — confirm the gap is real

**Area:** process · **Date:** 2026-06-16

While executing the auth/privacy plan I almost rebuilt analytics consent-gating, the
Privacy Policy, and the GDPR export/delete UI — all three already existed and were
well-built (`posthog-provider.tsx` gates on consent; `/privacy`; `/dashboard/settings`).
The audit/plan flagged them as gaps from a distance; the code said otherwise.

**Rule:** re-read the relevant files immediately before implementing any plan item, even
one the plan marked "missing". Confirm the gap is real before writing code — re-implementing
working code is wasted effort at best and a regression risk at worst.
