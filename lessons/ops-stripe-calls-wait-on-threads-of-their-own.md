# Run calls through Stripe's global client on the Stripe threads, never on anyio's default worker threads — one such call can wait minutes

Date: 2026-10-23   Area: ops

**Context**: E144 took checkout's and the billing portal's Stripe calls off the event loop with
`run_in_threadpool`, which runs them on anyio's default worker threads: 40 tokens a process, which the
auth lookups and every route's thread-pool units also take. stripe-python 16's global client waits up
to 80 s a call and retries twice (`stripe.max_network_retries`), so in a Stripe brownout 40 such calls
in flight on one instance would hold every token, and every unit in the process would wait for one of
them to return. E144's last-slice review measured it with portal calls of 2 s: an unrelated usage read
waited 0.02 s behind 39 of them and 1.91 s behind 40. Recorded as E170.

**Rule**: Hand every call through stripe-python's global client to
`stripe_threads.run_on_stripe_threads`, which runs it on eight threads of its own, never call it on the
event loop or through `run_in_threadpool`: a call waiting for one of those threads holds no token and
no pool slot, so the rest of the instance keeps moving, and a brownout holds at most the eight. A
client whose own timeouts bound each call to seconds may keep the default threads, as
`stripe_subscription_reader.py`'s does. The account deletion calls Stripe on the loop until E171 moves
its calls onto the Stripe threads. Other blocking SDK calls that can wait that long get threads of
their own too, as the Copilot's lookups and the companyfacts sync have theirs
(`lessons/ops-auth-lookups-must-let-request-cleanup-progress.md`).

**Gate**: `backend/tests/unit/test_stripe_threads_allowlist.py`. Its scan lists each Stripe API
operation that a module under `app/` names through the stripe module (`stripe.Customer.create`,
`stripe.billing_portal.Session.create`), and fails one that is not the first positional argument of a
`run_on_stripe_threads` call unless `SITES` lists it with the reason (the account deletion's two, until
E171). Its burst holds 48 portal sessions inside Stripe and fails unless eight of them run there at
once, all on the Stripe threads, with no default worker token held and an unrelated usage read
answering. Out of reach, so review holds them: a result's own methods (a list's `auto_paging_iter`
pages), a `StripeClient`'s services, a resource class held in a variable, and other SDKs.

**Evidence**: E144's last-slice review on #1529, 2026-10-23, and its probe (E170); the fix in
`backend/app/services/stripe_threads.py` and the five Stripe calls in
`backend/app/routers/subscriptions.py`, with the gate's mutation proofs in its PR's body.
