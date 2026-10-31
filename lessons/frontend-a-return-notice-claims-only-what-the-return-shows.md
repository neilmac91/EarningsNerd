# After a redirect back from checkout, say only what the return URL and the page's own reads show

Date: 2026-10-15 · Area: frontend / copy

**Context.** Stripe's checkout sends a buyer who backs out to `/pricing?canceled=true` (the
`cancel_url` in `backend/app/routers/subscriptions.py`). The page's first notice read "Checkout
cancelled" with "Nothing was charged." The founder's review of PR #1291 (the thread on
`frontend/app/pricing/page.tsx`) corrected it: the return URL carries no checkout session and no
charge outcome, so the page cannot know what was charged. The notice became "You returned from
checkout", with the plan the subscription query reports once it answers ("You can choose a plan
below." or "Your plan is Pro."). The dashboard's `?success=true` notice follows the same rule: "Pro
is active" only when the query says Pro, "Checkout finished" while it still says Free.

**Rule.**
- After a redirect back from a payment or identity provider, a notice states the return (the flag in
  the URL) and what the page's own reads show (the subscription query), nothing more: never an
  outcome the URL does not carry, such as a charge, a refund or a cancelled subscription.
- Until the read answers, the notice is the return alone; the plan joins it when the query resolves.
- Drop the flag from the address once read (`router.replace`, other params kept), so a reload, a
  history entry or a bookmark does not announce the return again, and keep the notice through a
  remount in the same commit (`features/subscriptions/lib/returnNotice.ts`).

**Evidence.** The founder's review thread on `frontend/app/pricing/page.tsx:327` (PR #1291),
rechecked by the principal review on 2026-10-14; D-033 in `docs/brand/decisions-log.md`, whose
Rejected column names "Nothing was charged."; `frontend/app/pricing/page.tsx` and
`frontend/app/dashboard/page.tsx`; `frontend/tests/unit/PricingPage.spec.tsx`, whose cancelled-return
cases refuse any "charged" text and hold the notice to its title while the query is pending, and
`dashboardCheckoutReturn.spec.tsx`; both assert the dropped flag and the notice kept through a
parent's remount.
