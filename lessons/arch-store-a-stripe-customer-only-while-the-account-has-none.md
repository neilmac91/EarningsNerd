# Store an account's Stripe customer only while it has none, and check out with the stored one — a check of a loaded attribute orders nothing

Date: 2026-10-23   Area: arch

**Context**: Checkout created a Stripe customer when `current_user.stripe_customer_id` was empty
and stored it with a plain write. The check reads the id as the auth lookup loaded it, in the thread
pool, before the route body runs; the event loop runs one body at a time, but not the lookups. So two
checkouts of one account (two tabs) whose lookups both read no customer each created one, and the
later save wrote over the first. On one instance the window was the first request's lookup, a few
milliseconds or the pool's wait when it was full; across instances it spanned the first
`Customer.create`, which one tab clicking again after the client's 30 s timeout could also hit. A
payment through the session whose customer lost named a customer the account no longer held:
checkout refused it as `customer_mismatch`, the subscription's events found no owner and were
recorded as processed, so no re-delivery repaired the account, and its payments were attributed to
no account. Stripe billed an account that stayed on Free. E144's second-slice review found it, and
two lenses and two refuters reproduced it on one server and on two, with Stripe faked at its
boundary.

**Rule**: Store the customer checkout creates for an account only while the account has none, in one
conditional statement (`billing_account_service.claim_stripe_customer_id`), and check out with the
customer it returns, the one stored first: a check and a write in two statements race across
instances. A loser's own customer stays in Stripe without a subscription, and the route logs it. The
webhook's writers of the column work differently: checkout's completion writes under the account's
row lock after its identity check, and a subscription update writes the customer of the subscription
bound to the account (`lessons/arch-guard-every-writer-of-the-billing-binding.md`). More generally,
a check that reads an attribute an earlier query loaded (the auth lookup's user above all) orders
nothing between requests: the write it guards re-reads the database, as a condition of the write
itself or under a lock taken before the re-read
(`lessons/ops-release-cached-filing-reads-before-yield.md`'s lock rule).

**Gate**:
- `backend/tests/unit/test_subscription_routes.py`:
  - `test_a_customer_another_checkout_stored_first_stays_and_is_checked_out_with`: another
    checkout's customer lands between this request's lookup and its save;
  - `test_two_checkouts_whose_lookups_both_read_no_customer_check_out_with_one`: two requests
    through the real `get_current_user`, with a barrier holding each lookup until both have read.

  Both fail on a blind write.
- `backend/tests/integration/test_subscription_event_transactions.py`'s
  `test_postgres_concurrent_customer_claims_keep_the_first` (CI's PostgreSQL job): two claims for
  one account on two connections, the first holding its write until PostgreSQL shows the second
  waiting for the row. It fails on a blind write and on a check and a write in two statements,
  which pass both cases above, since one process runs the route bodies one at a time.

Any other check of a loaded attribute before a write is review-checked.

**Evidence**: E144's second-slice review on #1523 and its two refutations, 2026-10-23 (E166); the
fix in `claim_stripe_customer_id` and `create_checkout_session`, whose review found the two-statement
gap above, with its mutation proofs in its PR's body.
