# Derive current-trial presentation from the resolved entitlement

Date: 2026-09-06   Area: frontend

**Context**: The subscription API can return raw `status = trialing` with `is_pro = false`
when a trial has expired. Pricing disabled a backend-permitted upgrade, and settings labeled
that Free user Pro, because both surfaces used the raw status alone.

**Rule**: Use the server's resolved `is_pro` together with trial status for current-trial labels
and controls. Do not derive entitlement expiry from the browser clock. Preserve customer-ID
portal routing and existing checkout/analytics behavior.

**Evidence**: `frontend/tests/unit/PricingPage.spec.tsx` gates the expired-trial upgrade against
a resolved subscription snapshot; `frontend/tests/unit/BillingPanel.spec.tsx` gates the Free
label/countdown and both customer-ID routing cases. Existing entitled-trial cases remain.
`backend/tests/unit/test_checkout_session.py::test_expired_trial_remnant_can_resubscribe_without_trial`
locks the unchanged backend behavior. Both frontend predicates are exercised by one coordinated
original-predicate mutation proof.

**Billing-route follow-up (2026-09-28):** A monthly-trial CTA must arrive on the monthly offer,
and a selected annual offer must not advertise a trial. Carry only the bounded billing cycle
through the homepage/paywall link, pricing selection and guest registration destination; the
server still owns eligibility and the price ID mapping. Resolve the incoming cycle before the
once-per-mount `pricing_viewed` event. Keep the query reader isolated from server-rendered plans.
The free-beta presentation must not simultaneously advertise a card-required trial.

**Gate mapping:** `pricing-section.spec.tsx` covers selected-cycle links and monthly/non-beta
trial copy; `PricingPage.spec.tsx` covers query selection, initial analytics, later user selection,
and guest query/stash preservation; `StreamingSummaryDisplay.spec.tsx` covers the trial paywall
link. `pricing-server-render-guard.spec.ts` retains the existing Suspense boundary gate. Each new
invariant has one committed-state mutation proof recorded with the implementation evidence.

The guest stash covers the existing email/password login fallback, including verification in
a new tab. Google/Apple callbacks currently return to the homepage; this frontend routing change
does not establish OAuth destination preservation or change authentication policy.

**Completed-login cleanup (2026-09-28):** Consume the pending signup destination after an
accepted email login even when an explicit `redirect` parameter wins. A nullish fallback that
calls the consumer only when the parameter is absent leaves the old destination for the next
login. `LoginRedirect.spec.tsx` submits the real login page twice to guard this cleanup, explicit
destination precedence and unsafe-path rejection, with a failed-login/retry control. Its one
committed-state fault proof restores the old short-circuit and must fail the second-login check.

**Beta-entry follow-up (2026-09-28):** Public beta-offer copy describes the invite/promo
configuration, not the guest's account. Keep its Pro link at neutral `/pricing` until account
eligibility resolves; ordinary paid-offer links retain the chosen billing cycle. Otherwise a
neutral beta CTA can become a guest monthly-trial CTA at its destination. `PricingPage.spec.tsx`
follows the actual rendered homepage href into guest pricing, with a non-beta monthly control;
one committed-state mutation restoring the beta monthly link must fail that composed check.
