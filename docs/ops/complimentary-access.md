# Complimentary Pro for private-beta testers (PB-02)

This page holds no tester, account id, address or roster. The roster, every manifest and every operational receipt
live in the founder's private store; anything an operation prints is safe for the public Ops log by construction.

The code: `backend/app/services/complimentary_access_service.py` (the checks and writes),
`backend/app/services/complimentary_access_manifest.py` (the manifest, checked offline) and the operator command
`backend/scripts/complimentary_access.py`. The ledger is `earningsnerd_complimentary_access_grants`
(`backend/migrations/20261102_earningsnerd_complimentary_access_grants.sql`).

## What a grant does

A grant makes an invited tester's account Pro without a payment, a card or a Stripe object. It sets `User.is_pro`, the
flag `entitlements.get_plan` falls back to when the account has no `Subscription` row, for an account that holds no
billing state. Every Pro capability follows from the plan, at the routes that enforce it: unlimited summaries (within
the 300-a-month fair-use cap), the Copilot (within its monthly cap), Multi-Period Analysis (dataset and generation),
PDF, CSV and Excel exports, real-time and 8-K filing alerts, the 100-company earnings-alert cap, forced regeneration
and the Change Report's full wording diff where that flag is on. `/api/auth/me`, `/api/subscriptions/subscription` and
`/api/subscriptions/usage` all read Pro.

Screenshot feedback is not plan-gated: any signed-in account can attach screenshots once feedback media is switched
on, which is the feedback-media workstream's operation (PB-03), not a grant.

Billing names the access: the plan reads Pro, an "Access" line reads "Complimentary (private beta)", and the page shows
no renewal date, price, trial or checkout button. `/api/subscriptions/subscription` carries `complimentary: true` for
it. Paid and trial accounts see what they saw before.

## Design decision

- **The existing mechanism, not a new engine.** The no-subscription `is_pro` fallback already gives every Pro
  feature, so a grant writes that flag and nothing else that decides access. There is no new plan, trial, price or
  Stripe object, and `entitlements.py` keeps its precedence: a `Subscription` row of any status decides the plan, and
  the flag decides only when there is none.
- **A small ledger is needed.** `is_pro` has no source or expiry, and the Stripe webhook keeps it for billed accounts.
  Without a record of which Pro a grant set, a revoke could not tell a tester's complimentary Pro from a paying
  account's, the cap and reruns would have nothing to count, and Billing could not say the access is complimentary.
  Audit rows alone were considered and rejected: Billing needs an indexed per-account read on every status request,
  and a unique row per account makes "one grant per account" a database fact. `audit_logs` still records every grant
  and revoke, with the account's state before and after.
- **A founder operation, not a signup hook.** Granting automatically at invited signup or verification would put a
  plan write inside the auth flow (PB-01's files, a locked contract area) and would grant whoever redeemed an invite,
  with no founder check at the moment of the grant. An operator run against an explicit roster keeps the grant
  auditable and leaves signup untouched. The cost is a delay: a tester is Free between verifying and the next apply,
  so invitation copy should promise Pro only once the founder has run the grant; PB-01 owns that copy.
- **Grants never touch billing state.** A grant refuses an account with a `Subscription` row or any Stripe id, and a
  revoke of an account that has gained a Subscription row since closes the ledger row and leaves the flag to the
  webhook, whose every write of it goes through that row.

## End date

`review_on` is an operational review or end date. **Nothing expires on it.** The readout counts the grants whose date
has come (`due_for_review`), and the founder revokes them with a revoke manifest. Billing does not show the date.

To move the date, apply a grant manifest of the cohort with the new `review_on` that names every account whose date
should move, dry run first, since the digest changes. Each named account whose active grant is that cohort's, whose
date differs and that passes every check moves to it (`review_date_moves` in the dry run, `review_date_moved` in the
apply), with an audit row of its own (`complimentary_access_review_moved`, the dates before and after and the run's
reason); its Pro, its grant time and the cap are untouched. An account the manifest does not name keeps its date, so a
cohort granted over several manifests moves only as far as the one manifest names it. The manifest is a grant like any
other: an account it names that was revoked since is granted again (`eligible`, then `granted`), and an older manifest
moves its accounts back to its own date, so read the dry run's outcomes before the apply. The window still holds: after
the day of the apply, at most 366 days later.

Automatic expiry is not built. If the founder approves one, the narrowest form is a scheduled revoke of the grants
past their date through the same service, so the plan still resolves through `entitlements.py` alone. Until then,
nothing may say that access ends by itself: Settings › Billing and the dashboard's plan card, the two places that name
the access, carry no end, renewal, expiry, trial, price, date or countdown
(`frontend/tests/unit/complimentaryAccess.ts`, read by their specs over each whole surface); any other page or message, the invitation and the mail included (PB-01's), is review-checked.

## Who can be granted

The dry run and every apply check each account; a refusal names the reason, and an account can carry several.

| Reason | Meaning |
|---|---|
| `account_not_found` | No account has this id. |
| `identity_mismatch` | The account's address does not match the entry's fingerprint: a mistyped id, or a changed address. Nothing more is read. |
| `account_inactive` | The account is deactivated. |
| `email_not_verified` | The tester has not verified their address yet. |
| `not_invited_beta` | The account did not register with an invite. |
| `no_redeemed_invite` | No redeemed invite names the account. |
| `no_signup_agreement` | The account holds no signup confirmation of its own. |
| `subscription_exists` | The account has a `Subscription` row (any status): that row decides its plan. |
| `stripe_identity` | The account holds a Stripe customer or subscription id: a Stripe event could reach it. |
| `pro_from_another_source` | The account is Pro already, not through a grant. |
| `granted_in_another_cohort` | Another cohort's grant holds the account. |
| `grant_without_pro` | The account's grant is active but its Pro was cleared by something else: investigate before anything else. |
| `cap_reached` | Twenty grants are active (the apply re-checks this under its lock). |

Outcomes that are not refusals: `eligible` (dry run) and `granted`; `already_granted` (a rerun);
`review_date_moves` (dry run) and `review_date_moved` (a rerun with another review date, "End date"); for a revoke,
`revocable`/`revoked`, `revocable_billing_owned`/`revoked_billing_untouched` and `not_granted`. A grant that would take
the active grants past 20, across every cohort, stops the whole manifest (`stopped: cap_exceeded`) before any write.

## The manifest

A JSON file with the action, the cohort (`private-beta-YYYY-MM`, with an optional wave: `-w2`), the reason, the operator's admin
account id (an active admin with a verified address, whom every audit row names as the actor; the check attributes the
run and authenticates no one, since the authority to run it is the database credential and, in production, the
founder's `ops-apply` approval), a secret salt, at most 20 accounts and, for a grant, the review date. Each account is named by its id and
the SHA-256 of its address as accounts store it (trimmed and lower-cased). Unknown keys and loosely typed values are
refused, and a fault names its place and kind, never the value. This example is synthetic (reserved `.invalid`
addresses):

```json
{
  "action": "grant",
  "cohort": "private-beta-2026-11",
  "reason": "Private beta tester",
  "review_on": "2027-01-31",
  "operator_account_id": 1,
  "salt": "<draw your own: openssl rand -hex 16>",
  "accounts": [
    {"account_id": 1001, "email_sha256": "bc53630744f19d9b2dd6f1cf057b98e578f0c268be59d6dee4b8470b5729e7ac"},
    {"account_id": 1002, "email_sha256": "11d9c00d37a6b24a9b5e918b9eb4bf4111a9274b76309773065e6cc52955b0f4"}
  ]
}
```

A revoke manifest has `"action": "revoke"`, the same cohort and entries, its own reason and salt, and no `review_on`.
The manifest's digest (`manifest_sha256`) is the SHA-256 of its canonical JSON; any change to any field changes it.

Every report prints the digest, so it is in the public Ops log, and every other field can be guessed: a stock reason,
the founder's id, sequential account ids, the fingerprint of a candidate address. The salt is what stops anyone from
matching the digest of a small manifest (a one-account revoke, say) to its tester by trying guesses offline. Draw a
fresh one for every manifest with `openssl rand -hex 16` (32 to 128 lower-case hex characters), keep it with the
manifest, and never publish it. The example's placeholder is refused, so a copy of the example cannot run with a
published salt.

The cohort is an opaque public code: every report prints it and the readout counts grants by it, so it appears in the
public Ops log. Its scheme leaves no letter free, so no name, address, workplace or private description fits in it;
keep what each code stands for with the private roster.

Keep every real manifest in the private store. Never commit one, paste one into an issue or pull request, or pass one
as a workflow input: the repository and its Actions logs are public. A committed one fails
`test_no_file_in_the_repository_is_a_manifest_but_the_runbooks_synthetic_example`, and so does a draft the command
would refuse, or a roster, that holds a fingerprint other than the example's two; a committed address list (a file
named for one, an editor's backup of one, or any small file of bare addresses one per line) fails
`test_no_file_in_the_repository_is_the_operators_address_list`. The rest, a roster of names and addresses among them,
is review-checked.

## Procedure

Each step's report is JSON: counts, refusals by their 1-based place in the manifest, the digest, and never an id, an
address or the reason.

Before the first grant, the testers' accounts must exist as a grant can see them:

- **Invited, under invite-only registration.** Registration sets `is_beta` and records the redeemed invite only while
  `REGISTRATION_MODE` is `invite_only`; in the default public mode an invite is ignored, so the grant refuses the
  account (`not_invited_beta`, `no_redeemed_invite`). Invitations are PB-01's (an email-bound invite per tester, under
  one invite cohort label, keeps each link to its person).
- **New accounts.** Nothing tags an account registered before its invite, so an existing account cannot be granted
  unless the founder decides to widen the rule.
- **The stored address.** Fingerprint the address the account holds, which is the invite's address for an email-bound
  invite (an Apple sign-in that hides the address holds Apple's relay address instead).
- **The reverse trial off.** With `REVERSE_TRIAL_ENABLED` on, verifying an address through its emailed link gives a
  password account a trialing `Subscription` row, and a grant refuses an account with a row of any status, the lapsed
  trial's included (`subscription_exists`). Keep it off, its default, while testers verify.

1. **Prepare, offline.** On the founder's machine, with no settings and no database, from `backend/`, with both files
   in a folder of the private store outside the repository, `$HOME/beta-private` (the Ops procedure's location too;
   the checkout ignores the two names at its root and under `backend/` as a backstop, never as a place to keep them):
   `python scripts/complimentary_access.py fingerprint < "$HOME/beta-private/addresses.txt"` prints one fingerprint
   per address, in order. Write `"$HOME/beta-private/manifest.json"` with each account's id and fingerprint and a
   fresh salt (`openssl rand -hex 16`), then
   `python scripts/complimentary_access.py check --manifest "$HOME/beta-private/manifest.json"` validates it and
   prints its digest.
2. **Dry run (read-only).** `python scripts/complimentary_access.py dry-run --manifest "$HOME/beta-private/manifest.json"`
   against production. It writes nothing.
3. **Review.** Compare the counts, every refusal and the digest with the private roster. Fix what is refused (a tester
   who has not verified yet is granted by a later rerun) and dry-run again after any edit, since an edit changes the
   digest.
4. **Apply (founder-approved).** `python scripts/complimentary_access.py apply --manifest "$HOME/beta-private/manifest.json"
   --confirm-digest <manifest_sha256> --runner <ops-run:id>`. It runs only the manifest whose digest it is handed.
   Each account is one unit: under the grants' lock and the account's row lock it is checked again, then its ledger
   row, its flag and its audit row commit together, or nothing does. A rerun grants what is newly eligible and changes
   nothing it already changed; with another review date it moves the named accounts' active grants to it ("End date").
5. **Verify.** `python scripts/complimentary_access.py readout` reports the active grants by cohort, the reviews due
   and any drift. A tester's Settings, Billing shows Pro with "Complimentary (private beta)" and no checkout button.
6. **Revoke.** Write the revoke manifest with a fresh salt, dry-run it, and apply it with its own digest. The account returns to Free:
   five summaries a month (this month's count included), three lifetime Copilot questions (the Pro questions never
   spent them), no exports or Multi-Period Analysis. Its saved summaries, watchlist and alert choices stay; the alert
   caps apply where alerts are sent.

### Running it in production

Production's database is reachable only from Cloud Run and the Ops proxy, so steps 2, 4 and 5 run through three Ops
operations in `.github/workflows/ops.yml`: `complimentary-access-dry-run`, `complimentary-access-apply` and
`complimentary-access-readout`, for a grant and a revoke alike. The dry run and the readout run read-only. The apply
runs only after the founder approves `ops-apply` for its run, takes the dry run's `manifest_sha256` in its
`confirm_digest` input and records `ops-run:<run id>` as its runner. The manifest is never an input: it reaches the
run only as the repository secret `COMPLIMENTARY_ACCESS_MANIFEST`, set from the founder's machine before the dry run
(`jq -c . "$HOME/beta-private/manifest.json" | gh secret set COMPLIMENTARY_ACCESS_MANIFEST`, after the offline
`check`, with the file kept outside this repository's checkout) and deleted as soon as the apply has run
(`gh secret delete COMPLIMENTARY_ACCESS_MANIFEST`). The step hands it to the script on stdin, never through a file, an
argument or the log. `docs/DEPLOYMENT.md`, "Complimentary access", gives the order. Nothing can be dispatched before
the code is on `main` and deployed.

## Deploying

The change deploys the backend with two migrations (`applied=2` on the deploy's migration line). Both lock `users`,
which every signed-in request reads, so deploy it in a quiet window, as the only backend deploy in flight:

- `20261102_earningsnerd_complimentary_access_grants.sql` creates the ledger. Its reference to `users` takes SHARE ROW
  EXCLUSIVE on `users` for a catalog change: reads go on, and writes to `users` wait until it commits.
- `20261102_trend_analysis_creator_set_null.sql` swaps the analysis stamp's reference in one statement and validates it
  in another, each committing on its own. The swap takes ACCESS EXCLUSIVE on `users` and `trend_analysis` for a catalog
  change, so while it waits for that lock every query on `users` waits behind it. The validation takes SHARE UPDATE
  EXCLUSIVE on `trend_analysis` and ROW SHARE on `users`, which stop no read or write.
- Each file waits at most 2 s to acquire a lock, not the session's 10 s, so a blocked attempt holds those queries for
  at most 2 s. The bound is on each wait for a lock, not on how long a statement runs or holds a lock once it has it
  (here catalog changes and the validation's read of `trend_analysis`). `apply_migrations.sh` retries a lock timeout up to five times, 15 s apart, then fails the deploy and prints the
  blocking sessions. A failed deploy is not retried: run it again once the blocker has finished, and it resumes where
  the file stopped, since each step reads the catalog first.

`tests/integration/test_subscription_event_transactions.py` reads the locks each statement holds, and probes `users`
from a second session, on CI's PostgreSQL.

## Rollback

- **A mistaken grant:** revoke it (above). **A mistaken revoke:** grant again; a re-grant reopens the account's ledger
  row and writes a new audit row.
- **Code rollback:** the ledger table is additive. A backend revision without this code still reads `is_pro`, so
  granted accounts stay Pro under it; with this frontend, Billing then loses only its complimentary line (it reads a
  missing `complimentary` as false and sends no Pro outside a trial to checkout). A frontend revision without it shows
  a complimentary Pro "Upgrade to Pro", whose checkout refuses it (409), and the dashboard's "Manage billing", whose
  portal fails without a Stripe customer.
  Revoke before rolling back if the grants should end with the code. The stamp's reference stays `ON DELETE SET NULL`
  under an older revision, which only lets an account's deletion through.
- **Schema:** the migration only creates the table (`CREATE TABLE IF NOT EXISTS`). Dropping it would need a migration
  of its own after the grants are revoked.

## Limits

- A grant is inert for an account with a `Subscription` row: that row decides its plan, so the grant refuses it.
- A checkout reads the account's entitlement before it stores a Stripe customer, so one that read the account just
  before its grant committed can store a customer after it (checkout is closed today). The grant's Pro stands, and a
  revoke still clears it: only a Subscription row makes the flag the webhook's. A checkout completed that way would bind
  a subscription, which then decides the account's plan.
- Product analytics count a complimentary Pro account as Pro.
- The grant's ledger row is not part of the account's data export; it is deleted with the account, while its audit
  rows remain, as every account audit row does.
