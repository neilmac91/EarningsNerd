# Guard every Stripe handler that writes the account's subscription binding — another subscription's non-entitling event never revokes an entitled one

Date: 2026-10-16   Area: arch

**Context**: An account holds one Stripe subscription binding (`Subscription.stripe_subscription_id`,
mirrored on `User`). A user whose old subscription A went past_due resolves to Free and may check
out again; replacement B binds and the account is Pro. Stripe keeps sending events for A (its
dunning ends in unpaid or canceled, the user schedules its cancellation in the portal, or a
delivery that got a 503 is retried late). `apply_checkout_completed` and
`apply_subscription_deleted` already refused events for a subscription other than the bound one,
but `apply_subscription_upsert` did not: a late `customer.subscription.updated` for A rebound the
account to A and revoked Pro while B was active and billed, and B's own deletion was then ignored
as not current. The worker reads Stripe only for the bound ID, so nothing healed it until B's next
event, up to a year on a yearly plan.

**Rule**: Every handler that writes the binding checks the event's subscription against the bound
one before writing. An event for a different subscription whose state does not grant Pro is
ignored while the account is entitled; the bound subscription's own events (downgrades and
deletion included) and an entitling event for another subscription still apply, and an account
with nothing entitled to protect still takes the new binding. Ask `entitlements.py` whether a
state grants Pro (`subscription_state_grants_pro`, `is_pro_user`), never a status list of your
own: an elapsed-trial "trialing" state is not entitling, a future one is. When you add a guard to
one writer, add the same late-event case for each sibling writer.

**Still open**: an *entitling* event for another subscription still rebinds (pinned in
`test_subscription_reconciliation.py`), and that strands a payer even with one live subscription.
A stale retry of A's earlier "active" update (Stripe retries a 503'd delivery for up to three
days) that arrives after B is bought passes this guard and rebinds the account to A. A's next
event then revokes Pro while B is active and billed: A's deletion is now current, and an update
for A is now reconciled from Stripe as unpaid or canceled. While A's stale row still grants Pro,
B's deletion is ignored as not current and this guard ignores B's non-entitling updates, so only
an entitling B update moves the binding back. Reading Stripe for a cross-ID created/updated event before
rebinding would resolve the stale replay to A's real state, but it reverses the no-read
"different" case of `test_outside_current_id_scope_preserves_existing_behavior_without_read`, so
it needs the founder. With two live subscriptions, either single-slot choice strands the account
on one cancellation order.

**Gate**: `backend/tests/unit/test_subscription_identity.py` —
`test_eligible_replacement_survives_old_checkout_and_deletion` (checkout, deletion) and
`test_late_old_update_cannot_unbind_entitled_replacement` (update; unpaid, past_due, canceled,
incomplete_expired, elapsed trialing), with the boundary pins
`test_bound_and_entitling_events_still_apply_to_a_replacement` (B's update, B's deletion, a newer
active or future-trial C) and `test_unentitled_account_still_binds_a_new_non_active_subscription`.
The three handlers in `subscription_sync.py` are the only writers of the binding today; a new
writer is review-checked.

**Evidence**: the bug hunt on main `1062046e` (account rebound to `sub_a` as Free with B active);
the fix in `apply_subscription_upsert`, with a mutation proof that removing the guard fails the
gate on all 5 late-update cases; the stale-replay gap above, found by the fix's review.
