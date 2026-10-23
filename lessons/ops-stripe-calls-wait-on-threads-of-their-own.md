# Run calls through Stripe's global client on the Stripe threads, never on anyio's default worker threads — one such call can wait minutes

Date: 2026-10-23   Area: ops

**Context**: E144 took checkout's and the billing portal's Stripe calls off the event loop with
`run_in_threadpool`, which runs them on anyio's default worker threads: 40 tokens a process, which the
auth lookups and every route's thread-pool units also take. stripe-python 16's global client waits up to
80 s to connect and 80 s for each read, and retries twice (`stripe.max_network_retries`), so in a Stripe
brownout 40 such calls in flight on one instance would hold every token, and every unit in the process
would wait for one of them to return. E144's last-slice review measured it with portal calls of 2 s: an
unrelated usage read waited 0.02 s behind 39 of them and 1.91 s behind 40. Recorded as E170.

**Rule**: Hand every call through stripe-python's global client to
`stripe_threads.run_on_stripe_threads`, which runs it on eight threads of its own, never call it on the
event loop or through `run_in_threadpool`: a call waiting for one of those threads holds no token and no
pool slot, so the rest of the instance keeps moving, and a brownout holds at most the eight. Work that
makes Stripe requests as it goes (a list walked with `auto_paging_iter()`, a cancellation loop) goes over
whole, as one plain def handed by name that finishes its walk before it returns: a generator, an async
def or a returned walk, bare or wrapped in `filter`, `map` or `itertools.islice`, would make its requests
wherever it is used, on the loop: the gate's scan lists each, and `run_on_stripe_threads` refuses each at
run time (a returned walk after the call, so that work has run up to its return).
`stripe_subscription_reader.py`'s calls keep the default threads: its own client makes one attempt with
connect and read-inactivity limits of 2 s and 3 s by default (at most 10 s each), not a total deadline
(`docs/CONFIGURATION.md`), so a Stripe that stops answering frees the thread in seconds unless DNS or a
slow, progressing response takes longer; the serving-price read runs one at a time per process; and a
webhook event's one read, of its subscription or of its invoice, runs inside the event's one worker unit,
so another thread would free nothing. The subscription read also keeps the worker's transaction and
account lock through it; the invoice read comes before the lock and holds neither, so it could leave the
default threads only if the event were split into units. The account deletion calls Stripe on the loop
until E171 hands its whole cancellation (the list, its later pages and the deletes) to the Stripe
threads. A call queued for the threads still runs after its client has had the request-timeout
middleware's 504, which lets the route finish, as one waiting for a default token did; a brownout now
queues from the ninth call in flight, not the 41st.

**Gate**: `backend/tests/unit/test_stripe_threads_allowlist.py`. Its scan reads `app/` and the backend's
top-level modules and lists each Stripe call a module names through the stripe module
(`stripe.Customer.create`, `stripe.billing_portal.Session.create`) and each `auto_paging_iter()`,
`next_page()` or `previous_page()` call or handoff. It fails one that is neither the first positional
argument of a `run_on_stripe_threads` call nor called in the body of a lambda that is that argument or of
a plain def the module only ever hands there by name (not a generator def or lambda, an async def, a
method, a decorated def, a def or lambda nested in such a body, or a generator expression's element,
conditions or later loops), where a walk counts only if it is used up in place (by a `for` loop, a list,
set or dict comprehension, or a consumer such as `list` or `sorted`, directly or through a call that is
itself used up there), unless `SITES` lists it, by its form, with the reason (the account deletion's
three, until E171); a listed call that changes its form, or a second call with its key, fails too.
`run_on_stripe_threads` itself refuses a generator, coroutine or async generator function, and a result
that is a coroutine, an async generator or an iterator from stripe-python, the builtins or `itertools` (a
walk, bare or wrapped in `filter`, `map` or `itertools.islice`), and a case proves it. Its burst holds 48
portal sessions inside Stripe and fails unless eight of them run there at once, all on the Stripe threads
and each in its request's context, with no default worker token held and an unrelated usage read
answering. Out of reach, so review holds them: a result's methods other than its page methods, a
`StripeClient`'s services, a resource class held in a variable or reached through `getattr`, a def handed
through an attribute or a variable, or called through another name or from another module (the refusal
still refuses what such a def returns when it is a walk, bare or wrapped by the builtins or `itertools`,
a coroutine or an async generator, though not a walk inside a container or an iterator from another
module), a consumer's name bound to something that keeps a walk lazy, a callable named
`run_on_stripe_threads` that is not the helper, and other SDKs.

**Evidence**: E144's last-slice review on #1529, 2026-10-23, and its probe (E170); the fix in
`backend/app/services/stripe_threads.py` and the five Stripe calls in
`backend/app/routers/subscriptions.py`, with the gate's mutation proofs in its PR's body.
