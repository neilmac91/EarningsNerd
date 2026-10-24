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
webhook event's read, of its subscription or of its invoice (at most one), runs inside the event's one
worker unit, so another thread would free nothing. The subscription read also keeps the worker's
transaction and account lock through it; the invoice read comes before the lock and holds neither, so it
could leave the default threads only if the event were split into units. The account deletion called
Stripe on the event loop; it now hands its whole cancellation (the list, its later pages and the deletes)
to the Stripe threads as one plain def, `users.py`'s `_cancel_billable_subscriptions`, which finishes its
walk before it returns. A call queued for the threads still runs after its client has had the request-timeout
middleware's 504, which lets the route finish, as one waiting for a default token did; a brownout now
queues from the ninth call in flight, not the 41st. A cancelled request task would stop the account
deletion at its await on the Stripe threads, before its audit row and the row's deletion: a cancellation
a Stripe thread has taken runs there to its end, and one still queued for a thread never runs. Nothing
cancels one in the deploy today: uvicorn cancels a request task after a graceful-shutdown timeout, which
the deploy does not set, or on a forced quit (a second Ctrl+C), and Cloud Run stops an instance with
SIGTERM, then SIGKILL.

**Gate**: `backend/tests/unit/test_stripe_threads_allowlist.py`. Its scan reads `app/` and the backend's
top-level modules and lists each Stripe call a module names through the stripe module
(`stripe.Customer.create`, `stripe.billing_portal.Session.create`) and each `auto_paging_iter()`,
`next_page()`, `previous_page()` or `next_search_result_page()` call or handoff. It fails one that is
neither the first positional argument of a `run_on_stripe_threads` call nor called in the body of a
lambda that is that argument or of a plain def the module only ever hands there by name (not a generator
def or lambda, an async def, a method, a decorated def, a def or lambda nested in such a body, or a
generator expression's element, conditions or later loops), where a walk counts only if it is used up in
place (by a `for` loop, a list, set or dict comprehension, or a consumer such as `list`, `sorted` or
`str.join`, directly or through a call that is itself used up there). It has no allowlist: its failure
names each call by file, function, call and form, which ends with where the code around it runs
(`called on the loop` in an async def's own body; `in cancel_billable`, `in a lambda` or `in a generator
expression` in a nested body), but no key records where its call runs. A def's or lambda's body runs
wherever it is called, a generator expression's later parts and a walk's later pages wherever they are
iterated, and a named or handed method wherever its taker calls it, so an allowlist line could go on excusing
a call moved onto the loop; an exception is a change to the gate, in review.
`run_on_stripe_threads` itself refuses a generator, coroutine or async generator function, and a result
that is a coroutine, an async generator or an iterator from stripe-python, the builtins or `itertools`,
any of which may hold a walk, and a case proves it. The real-tree case also checks that it read the
top-level modules, the billing and users routers, the helper and more than 250 modules, and that it sees
the billing router's five calls and the deletion's three once they are handed anywhere else. Its burst holds 48 portal sessions inside Stripe
and fails unless eight of them run there at once, all on the Stripe threads and each in its request's
context, with no default worker token held and an unrelated usage read answering. Its planted forms score
each rule both ways and mark the rest. Gaps, which break the rule but pass, so review holds them: a
result's methods other than its page methods, a resource class held in a variable or reached through
`getattr`, a resource instance built from its class (`stripe.Subscription(sid).delete()`), the stripe
module held in a name or a parameter's default, a def handed by name that something also calls through
another name or from another module, a
walk kept by a call used up in place that does not consume it (`itertools.tee`), an async page method
(`next_page_async`), which holds no thread, a consumer's builtin name rebound, or a `join` or `deque`
method, that keeps a walk lazy, and a callable named `run_on_stripe_threads` that is not the helper.
Outside the rule: a `StripeClient`'s services and other SDKs. Strict, so their writers rewrite them in
place: a walk held in a variable before a loop uses it up, a generator expression of a walk handed to a
consumer or looped over, a walk unpacked into a display (`[*walk]`), a search result's `next_page` field
(a string) read as a page method, a Stripe method or def handed through `functools.partial(...)`, a def
called in a handed lambda, a def handed through a variable or an attribute or defined in another module,
a walk handed to a function the scan does not know, and a resource method that makes no request
(`construct_from`), which belongs beside `stripe.Webhook`'s in the scan's exemptions.

**Evidence**: E144's last-slice review on #1529, 2026-10-23, and its probe (E170); the fix in
`backend/app/services/stripe_threads.py`, the five Stripe calls in `backend/app/routers/subscriptions.py`
and the account deletion's cancellation in `backend/app/routers/users.py`, with the gate's mutation proofs
in its PR's body.
