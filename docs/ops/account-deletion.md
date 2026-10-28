# Account deletion: failure policy and operator runbook (F18)

What `DELETE /api/users/me` does when part of it fails, what evidence each outcome leaves, and what an operator does
next. The code is the source: [`routers/users.py`](../../backend/app/routers/users.py) (`delete_user_account`),
[`user_account_service.delete_account`](../../backend/app/services/user_account_service.py) and
[`audit_service.stage_user_deletion`](../../backend/app/services/audit_service.py). The tests named below pin each
row. Where this page and the code differ, the code is right and this page is wrong; fix it in the same change.

This page holds no customer, account or provider identifier, and no figures. Any review of real accounts or provider
records is the founder's, through the founder's own consoles; see [Provider cleanup](#5-provider-cleanup).

## 1. What a deletion does, in order

1. **Provider steps, best effort, each in its own `try`.** They run before the database work, with no database
   connection held (E171). Each records an outcome in `third_party_deletions`:
   - **Stripe**: every subscription of the account's customer that can still bill is cancelled, page by page. The
     customer record is kept. Outcome `subscriptions_cancelled` when the walk finished, `error: …` when it raised, or
     `skipped` with no customer or no Stripe client. `subscriptions_cancelled` means the walk finished without error.
     It does not mean that request cancelled anything: a walk that found nothing left to cancel reports it too.
   - **PostHog**: a `$delete` event for the account's id, flushed (up to 10 s). Outcome `deletion_requested`,
     `error: …` or `skipped`. Sending it does not prove PostHog erased anything.
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

## 2. The accepted matrix

| Case | Answer | Account | `user_deleted` audit row | Cookies | Provider effects | Pinned by |
| --- | --- | --- | --- | --- | --- | --- |
| Every step succeeds | 200 | Deleted | One, with the outcomes | Cleared | As reported | `test_delete_account_audits_deletes_and_clears_session_cookies` |
| A provider step fails, the database unit succeeds | 200; that provider's outcome is `error: …` | Deleted | One, recording the `error: …` | Cleared | The others ran; the failed one may have done part of its work (Stripe stops where it failed) | `test_a_stripe_failure_is_reported_and_the_deletion_still_proceeds` |
| The audit row's insert fails | 500 | Kept | None | Not cleared | Already done; not undone | `test_failed_delete_rolls_back_keeps_account_and_sets_no_cookie[audit]`; after a Stripe cancellation, `test_a_deletion_that_fails_after_stripe_cancelled_keeps_the_account_and_logs_the_outcomes[audit]` |
| The account's delete fails | 500 | Kept | None | Not cleared | Already done; not undone | `…[account]` in both tests |
| The commit fails | 500 | Kept | None | Not cleared | Already done; not undone | `…[commit]` in both tests |
| The account is already gone (a second deletion at once) | 500 | Gone (the first deletion's) | None from this request; the first deletion's stands | Not cleared | This request's own provider calls ran | `test_a_delete_that_finds_the_account_gone_answers_the_routes_500`; on PostgreSQL `test_a_second_deletion_of_one_account_waits_out_the_first_and_finds_it_gone` |
| The request stops part-way (a cancelled request task, Cloud Run's SIGKILL after SIGTERM) | None, or the client's own timeout | Kept if the database unit had not started | None if the unit had not committed | Not cleared | Whatever ran before the stop | `lessons/ops-release-cached-filing-reads-before-yield.md`, `lessons/ops-stripe-calls-wait-on-threads-of-their-own.md` |

The policy this matrix states, accepted by the founder for F19:

- A mandatory audit failure blocks the application deletion.
- A successful database transaction records the provider outcomes in its audit row.
- A provider failure alone keeps the existing response: the deletion proceeds and reports `error: …`.
- The account and its cookies are cleared only after the application deletion succeeds.

A stop part-way follows how the route runs:
- A cancelled request stops at the `await` it is in.
- A thread-pool unit or a Stripe call that a thread has started runs to its end.
- One still queued never runs.

Nothing in the deploy cancels a request today; Cloud Run's SIGKILL stops a deletion wherever it is.

## 3. What evidence survives

| Case | Database | Logs (for as long as Cloud Logging keeps them) |
| --- | --- | --- |
| Success, with or without a provider failure | The `user_deleted` row: account id, email, each provider's outcome, a UTC timestamp | WARNING `USER DELETION: … account deletion initiated` (account id, email, Stripe customer); each provider's INFO or ERROR line; INFO `USER DELETION COMPLETED … Third-party deletion results: …` |
| A database or audit failure | Nothing new: the account and its rows as they were | The initiated WARNING; the provider lines; ERROR `Error deleting user account <id>: <cause>. Third-party deletion results: …` |
| The account already gone | The first deletion's row | The same ERROR, its cause `Account <id> was deleted after its lookup` |
| A stop part-way | As far as the unit got (all or nothing) | The lines written before the stop |

Production audit rows are not readable through the current Ops allowlist, so the logs are the operator's first
record. A total database outage writes no audit row at all, and durable logging cannot be promised then.

## 4. Operator walkthrough

Each case below is fixture-backed: the named test plays it against the real route, with Stripe's subscription list
and cancel endpoints faked on the wire.

**A user reports "We could not delete your account".**
1. Find the ERROR line `Error deleting user account <id>: …`. Its cause and its `Third-party deletion results` say
   which provider steps ran. The account still exists, with no deletion audit row, whether the audit insert, the
   delete or the commit failed (`test_a_deletion_that_fails_after_stripe_cancelled_keeps_the_account_and_logs_the_outcomes`,
   all three).
2. Provider effects already taken stand:
   - Stripe subscriptions were cancelled, and the customer record kept.
   - PostHog was asked to delete.
   - The request's Sentry context was cleared.

   Nothing undoes them, and nothing should.
3. Ask the user to retry from Account Settings once the cause is fixed. A retry walks the same subscriptions, finds the
   cancelled ones ended, cancels nothing again, deletes the account and commits its own audit row
   (`test_a_retry_after_a_deletion_failed_past_stripe_deletes_the_account_and_cancels_nothing_twice`). That row's
   Stripe outcome reads `subscriptions_cancelled` even though the retry cancelled nothing; the first attempt's ERROR
   line is the record of the cancellation.

**A deletion succeeded but a provider step failed** (`error: …` in the response and the audit row).
1. The account is deleted. The failed step may have done part of its work: the Stripe walk stops where it failed,
   so a later page's live subscription may still bill (`test_a_stripe_failure_is_reported_and_the_deletion_still_proceeds`).
2. That is a founder action: see [Provider cleanup](#5-provider-cleanup). The initiated WARNING names the account's
   Stripe customer. The account row that held it is gone.

**Two deletions of one account at once.** The second answers 500 and writes no audit row; the first's stands. Nothing
to do. A user who saw the 500 can be told the account is gone.

## 5. Provider cleanup

- **No automatic correction.** The code issues no automatic refund, no blanket cancellation, no orphan sweeper and
  no recurring worker. Any financial correction is a manual founder action, taken after review in Stripe's own
  console. Stripe cancellation outside a user's own deletion stays founder-owned (#1176).
- **Read-only reconciliation.** Finding accounts whose subscriptions outlived their deletion, or that the earlier
  checkout bug stranded, is the bounded read-only check of
  [F62](../../tasks/todo.md) (B's billing reconciliation). It reads, separates test-mode from live-mode observations,
  and reports what it cannot tell. It changes nothing.
- **No assumed harm.** This page asserts no historic paid-customer harm, volume or refund, and infers no zero
  future risk either.

## 6. Acceptance

F18 is accepted only after the founder reviews the F19 results and this matrix. Any cleanup of a real provider record
keeps its own later founder checkpoint. Production console access is not a prerequisite for the code fix.
