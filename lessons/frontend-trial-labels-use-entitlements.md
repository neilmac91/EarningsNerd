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
