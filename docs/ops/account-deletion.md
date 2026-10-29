# Account deletion: failure policy and operator runbook (F18)

What `DELETE /api/users/me` does when part of it fails, what evidence each outcome leaves, and what an operator does
next. The code is the source: [`routers/users.py`](../../backend/app/routers/users.py) (`delete_user_account`),
[`user_account_service.delete_account`](../../backend/app/services/user_account_service.py) and
[`audit_service.stage_user_deletion`](../../backend/app/services/audit_service.py). Each row of the matrix names the
test that pins it, or the lesson that records it where no test can. Where this page and the code differ, the code is
right and this page is wrong; fix it in the same change.

This page holds no customer, account or provider identifier, and no figures. Any review of real accounts or provider
records is the founder's, through the founder's own consoles; see [Provider cleanup](#5-provider-cleanup).

## 1. What a deletion does, in order

1. **Provider steps, best effort, each in its own `try`.** They run before the database work, with no database
   connection held (E171). Each records an outcome in `third_party_deletions`:
   - **Stripe**: the account's customer's subscriptions are walked page by page, and each one that can still bill is
     cancelled. The customer record is kept.
     - Outcomes: `subscriptions_cancelled` when the walk finished, `error: …` when a call raised, or `skipped` when the
       account has no Stripe customer or the `stripe` package is not installed. A missing or rejected key raises, so it
       reads `error: …`.
     - `subscriptions_cancelled` means the walk finished without error, not that this request cancelled anything: a
       walk that found nothing left to cancel reports it too.
     - The record of a cancellation is its INFO line `Cancelled Stripe subscription <subscription> for user <id>`, one
       per subscription. A listed subscription of another customer is never cancelled; it gets the WARNING
       `Skipped Stripe subscription <subscription> of another customer for user <id>`.
   - **PostHog**: a `$delete` event for the account's id, then a flush (up to 10 s). Outcome `deletion_requested` when
     the capture and the flush returned, `error: …` when one raised, or `skipped` with no PostHog client. A flush that
     ran out its 10 s returns all the same, so the outcome does not prove PostHog received the event, let alone erased
     anything.
   - **Sentry**: the request's user context is cleared. Outcome `anonymized`, `error: …` or `skipped`. Historical
     Sentry events are untouched.
2. **The database unit, one transaction** (`delete_account`, F19):
   1. It takes the account's row lock. If the account is already gone, it raises with no audit row staged.
   2. It stages the `user_deleted` audit row with the provider outcomes and the email the locked row holds.
   3. It queues the account's feedback media for deletion and deletes the account. The ORM cascades remove the
      rows the account owns.
   4. One commit writes the audit row and the deletion together, or neither.
3. **Only after that commit**, the response clears the access, presence and refresh cookies and answers 200.

A failure anywhere in step 2 is rolled back before the session is released. The answer is 500 with "We could not
delete your account. Contact support.", and no `Set-Cookie`.

**The request timeout.** The request-timeout middleware (`main.py`, `request_timeout_middleware`; 30 s for this
route) answers 504 "Request timed out after 30.0s" when the route has not finished. That 504 does not stop the route
(`lessons/ops-give-a-long-request-a-timeout-inside-cloud-runs.md`). Its work goes on after the answer: the account may
still be deleted with its audit row, or the deletion may fail later, under Cloud Run's throttled CPU. The 504 carries
no `Set-Cookie`, so the server never clears this browser's cookies for that request. Stripe's retries during a
brownout, or PostHog's 10 s flush, can push a deletion past 30 s.

## 2. The accepted matrix

| Case | Answer | Account | `user_deleted` audit row | Cookies | Provider effects | Pinned by |
| --- | --- | --- | --- | --- | --- | --- |
| Every step succeeds within the timeout | 200 | Deleted | One, with the outcomes | Cleared | As reported | `test_delete_account_audits_deletes_and_clears_session_cookies` |
| A provider step fails, the database unit succeeds | 200; that provider's outcome is `error: …` | Deleted | One, recording the `error: …` | Cleared | The others ran. The failed one may have done part of its work: the Stripe walk stops at the first failed call, so any subscription it had not reached, and possibly the one whose call failed, may still bill | `test_a_stripe_failure_is_reported_and_the_deletion_still_proceeds` |
| The audit row's insert fails | 500 | Kept | None | Not cleared | Already done; not undone | `test_failed_delete_rolls_back_keeps_account_and_sets_no_cookie[audit]`; after a Stripe cancellation, `test_a_deletion_that_fails_after_stripe_cancelled_keeps_the_account_and_logs_the_outcomes[audit]` |
| The account's delete fails | 500 | Kept | None | Not cleared | Already done; not undone | `…[account]` in both tests |
| The commit fails | 500 | Kept | None | Not cleared | Already done; not undone | `…[commit]` in both tests |
| The account is already gone (a second deletion at once) | 500 | Gone (the first deletion's) | None from this request; the first deletion's stands | Not cleared | This request's own provider calls ran | `test_a_delete_that_finds_the_account_gone_answers_the_routes_500`; on PostgreSQL, at the service, `test_a_second_deletion_of_one_account_waits_out_the_first_and_finds_it_gone` |
| The route outlasts the request timeout | 504 | Decided later, as the rows above | Decided later, as the rows above | Not cleared | As the rows above, later | No test; the timeout's lesson (`lessons/ops-give-a-long-request-a-timeout-inside-cloud-runs.md`) |
| The request stops part-way (a cancelled request task, Cloud Run's SIGKILL after SIGTERM) | None, or the client's own timeout | Deleted if its database unit commits, before or after the stop (a cancel lets a unit a thread has started run to its end; SIGKILL rolls back one that had not committed); otherwise kept | One if the unit commits; otherwise none | Not cleared | Whatever ran before the stop | No test; the lessons `ops-release-cached-filing-reads-before-yield.md` and `ops-stripe-calls-wait-on-threads-of-their-own.md` |

The policy this matrix states is F19's, as its assignment records the founder's approval that an audit failure stops
the database deletion:

- A mandatory audit failure blocks the application deletion.
- A successful database transaction records the provider outcomes in its audit row.
- A provider failure alone keeps the existing response: the deletion proceeds and reports `error: …`.
- The account and its cookies are cleared only after the application deletion succeeds.

A stop part-way follows how the route runs:
- A cancelled request stops at the `await` it is in.
- A thread-pool unit or a Stripe call that a thread has started runs to its end.
- One still queued never runs.

Nothing in the deploy cancels a request task today (the 504 above does not); Cloud Run's SIGKILL stops a deletion
wherever it is.

## 3. What evidence survives

| Case | Database | Logs (for as long as Cloud Logging keeps them) |
| --- | --- | --- |
| Success, with or without a provider failure | The `user_deleted` row: account id, email, each provider's outcome, a UTC timestamp | WARNING `USER DELETION: … account deletion initiated` (account id, email, Stripe customer); one INFO `Cancelled Stripe subscription …` per cancellation and a WARNING `Skipped Stripe subscription … of another customer` per one skipped; each provider's INFO or ERROR line; INFO `USER DELETION COMPLETED … Third-party deletion results: …` |
| A database or audit failure | Nothing new: the account and its rows as they were | The initiated WARNING; the cancellation and provider lines; ERROR `Error deleting user account <id>: <cause>. Third-party deletion results: …` |
| The account already gone | The first deletion's row | The same ERROR, its cause `Account <id> was deleted after its lookup` |
| A 504 | As the route later ended | As the route later ended: the COMPLETED INFO line or the ERROR line, after the 504 |
| A stop part-way | As far as the unit got (all or nothing) | The lines written before the stop |

Production audit rows are not readable through the current Ops allowlist, so the logs are the operator's first
record. A total database outage writes no audit row at all, and durable logging cannot be promised then.

## 4. Operator walkthrough

The cases with a test are played over HTTP against the real route: the database failures are injected into the
request's own session, and Stripe's subscription list and cancel endpoints are faked on the wire. The exceptions are
the gone-account test, which plays the first deletion inside the Stripe step, and the PostgreSQL race, which drives
the service directly.

**A user reports that the deletion failed.** Settings shows "We could not delete your account. Contact support." and
`/delete-account` shows "Deletion failed" for every error, a timeout included: neither screen shows the server's 504
text, and the browser's own 30 s request timeout (`REQUEST_TIMEOUT_MS`) usually fires before the server's 30 s 504
arrives.
1. Search the logs by the account's id for what followed the request:
   - the INFO `USER DELETION COMPLETED …`: the deletion outlasted the timeout and then finished; see the next case;
   - the ERROR `Error deleting user account <id>: …`: its cause and its `Third-party deletion results` say which
     provider steps ran. Unless the cause is `Account <id> was deleted after its lookup` (see the last case below),
     the account still exists, with no deletion audit row, whether the audit insert, the delete or the commit
     failed (`test_a_deletion_that_fails_after_stripe_cancelled_keeps_the_account_and_logs_the_outcomes`, all three);
   - neither: look for the initiated WARNING `USER DELETION: … account deletion initiated`, the route's first line:
     - absent: the request never reached the deletion (its sign-in was refused, or it never arrived), and the
       account is untouched;
     - present, with no `USER DELETION COMPLETED …` or `Error deleting user account …` line after it (provider
       lines, INFO, WARNING or ERROR, such as `Cancelled Stripe subscription …`, `Skipped Stripe subscription … of
       another customer`, `Failed to cancel Stripe subscription …` or `Sentry user context cleared …`, may follow): the route is still running, or it was stopped part-way (the
       matrix's last row). A Stripe brownout can hold it for many minutes: the cancellation can queue for one of the
       eight Stripe threads, and each call waits up to 80 s to connect and 80 s between reads, retried twice
       (`lessons/ops-stripe-calls-wait-on-threads-of-their-own.md`). Search again an hour later; if nothing has
       followed, the route has most likely stopped. Firmer evidence is the end of the instance that wrote the
       initiated line: uvicorn's `Shutting down` line in Cloud Logging under that line's `labels.instanceId`,
       followed by `Waiting for background tasks to complete …` when the request had its 504 or its client went
       away, or `Waiting for connections to close …` while its response was still pending. A kill without SIGTERM
       can leave none of them, so their absence proves nothing. Then check whether the account still exists; it does unless its unit committed.
2. Provider effects already taken stand:
   - The subscriptions named by `Cancelled Stripe subscription …` lines are cancelled, and the customer record kept.
   - PostHog was sent its deletion event.
   - The request's Sentry context was cleared.

   Nothing undoes them, and nothing should.
3. Ask the user to retry from Account Settings once the cause is fixed. A retry walks the same subscriptions, finds the
   cancelled ones ended, cancels nothing again, deletes the account and commits its own audit row
   (`test_a_retry_after_a_deletion_failed_past_stripe_deletes_the_account_and_cancels_nothing_twice`). That row's
   Stripe outcome reads `subscriptions_cancelled` even though the retry cancelled nothing. The first attempt's
   `Cancelled Stripe subscription …` lines are the record of what was cancelled.

**The deletion outlasted its timeout** (the logs show `USER DELETION COMPLETED …` after the user's failure message).
1. The account is deleted, with its audit row. The user saw a failure only because the browser or the server stopped
   waiting first.
2. The server cleared no cookies for that request. A completed deletion leaves the browser holding cookies for an
   account that no longer exists; its next read is refused as signed out.

**A deletion succeeded but a provider step failed** (`error: …` in the response and the audit row).
1. The account is deleted. The failed step may have done part of its work. The Stripe walk stops at the first failed
   call, so any subscription it had not reached, and possibly the one whose call failed, may still bill
   (`test_a_stripe_failure_is_reported_and_the_deletion_still_proceeds`). The `Cancelled Stripe subscription …` lines
   say which ones were cancelled.
2. That is a founder action: see [Provider cleanup](#5-provider-cleanup). The initiated WARNING names the account's
   Stripe customer. The account row that held it is gone.

**Two deletions of one account at once** (the ERROR's cause is `Account <id> was deleted after its lookup`). The
second answers 500 and writes no audit row; the first's stands. Nothing to do. A user who saw the 500 can be told the
account is gone.

## 5. Provider cleanup

- **No automatic correction.** At this commit, the only call in the backend that cancels, refunds or voids anything in
  Stripe is the deletion's cancellation of the account's own billable subscriptions. The gate
  `backend/tests/unit/test_stripe_money_moves_allowlist.py` holds it there: a new such call, called or passed in a
  form the gate's docstring names, fails until it is reviewed and listed, and the forms it names as unseen are left to
  review. There is no automatic refund, blanket cancellation, orphan sweeper or recurring worker. Any financial
  correction is a manual founder action, taken after review in Stripe's own console. Stripe cancellation outside a
  user's own deletion stays founder-owned (#1176).
- **Read-only reconciliation.** [F62](../../tasks/todo.md)'s bounded read-only check finds subscriptions billed on a
  customer the account does not hold, which the earlier checkout bug stranded. It does not today look for
  subscriptions that outlived a deletion whose Stripe step reported `error: …`. Widening it to them is a request to its
  owner. So is keeping test-mode and live-mode observations apart, and reporting what it cannot tell. Either way it
  changes nothing.
- **No assumed harm.** This page asserts no historic paid-customer harm, volume or refund, and infers no zero future
  risk either.

## 6. Acceptance

F18 is accepted only after the founder reviews the F19 results and this matrix. Any cleanup of a real provider record
keeps its own later founder checkpoint. Production console access is not a prerequisite for F19's change.
