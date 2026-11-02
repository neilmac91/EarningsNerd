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
  revoke of an account that has gained one since closes the ledger row and leaves the flag to the webhook.

## End date

`review_on` is an operational review or end date. **Nothing expires on it.** The readout counts the grants whose date
has come (`due_for_review`), and the founder revokes them with a revoke manifest. Billing does not show the date.

Automatic expiry is not built. If the founder approves one, the narrowest form is a scheduled revoke of the grants
past their date through the same service, so the plan still resolves through `entitlements.py` alone; until then, no
page or message may say that access ends by itself.

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

Outcomes that are not refusals: `eligible` (dry run) and `granted`; `already_granted` (a rerun); for a revoke,
`revocable`/`revoked`, `revocable_billing_owned`/`revoked_billing_untouched` and `not_granted`. A grant that would take
the active grants past 20, across every cohort, stops the whole manifest (`stopped: cap_exceeded`) before any write.

## The manifest

A JSON file with the action, the cohort (lower-case letters, digits and hyphens), the reason, the operator's admin
account id, at most 20 accounts and, for a grant, the review date. Each account is named by its id and the SHA-256 of
its address as accounts store it (trimmed and lower-cased). Unknown keys and loosely typed values are refused, and a
fault names its place and kind, never the value. This example is synthetic (reserved `.invalid` addresses):

```json
{
  "action": "grant",
  "cohort": "private-beta-2026-11",
  "reason": "Private beta tester",
  "review_on": "2027-01-31",
  "operator_account_id": 1,
  "accounts": [
    {"account_id": 1001, "email_sha256": "bc53630744f19d9b2dd6f1cf057b98e578f0c268be59d6dee4b8470b5729e7ac"},
    {"account_id": 1002, "email_sha256": "11d9c00d37a6b24a9b5e918b9eb4bf4111a9274b76309773065e6cc52955b0f4"}
  ]
}
```

A revoke manifest has `"action": "revoke"`, the same cohort and entries, its own reason, and no `review_on`. The
manifest's digest (`manifest_sha256`) is the SHA-256 of its canonical JSON; any change to any field changes it.

Keep every real manifest in the private store. Never commit one, paste one into an issue or pull request, or pass one
as a workflow input: the repository and its Actions logs are public.

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

1. **Prepare, offline.** On the founder's machine, with no settings and no database:
   `python scripts/complimentary_access.py fingerprint < addresses.txt` prints one fingerprint per address, in order.
   Write the manifest with each account's id and fingerprint, then
   `python scripts/complimentary_access.py check --manifest manifest.json` validates it and prints its digest.
2. **Dry run (read-only).** `python scripts/complimentary_access.py dry-run --manifest manifest.json` against
   production. It writes nothing.
3. **Review.** Compare the counts, every refusal and the digest with the private roster. Fix what is refused (a tester
   who has not verified yet is granted by a later rerun) and dry-run again after any edit, since an edit changes the
   digest.
4. **Apply (founder-approved).** `python scripts/complimentary_access.py apply --manifest manifest.json
   --confirm-digest <manifest_sha256> --runner <ops-run:id>`. It runs only the manifest whose digest it is handed.
   Each account is one unit: under the grants' lock and the account's row lock it is checked again, then its ledger
   row, its flag and its audit row commit together, or nothing does. A rerun grants what is newly eligible and changes
   nothing it already changed.
5. **Verify.** `python scripts/complimentary_access.py readout` reports the active grants by cohort, the reviews due
   and any drift. A tester's Settings, Billing shows Pro with "Complimentary (private beta)" and no checkout button.
6. **Revoke.** Write the revoke manifest, dry-run it, and apply it with its own digest. The account returns to Free:
   five summaries a month (this month's count included), three lifetime Copilot questions (the Pro questions never
   spent them), no exports or Multi-Period Analysis. Its saved summaries, watchlist and alert choices stay; the alert
   caps apply where alerts are sent.

### Running it in production

Production's database is reachable only from Cloud Run and the Ops proxy, so these commands run through Ops
operations in `.github/workflows/ops.yml`, the dry run read-only and the apply behind the founder's `ops-apply`
approval. Those operations are not wired yet: the shared workflow's single writer is the integration workstream
(PB-05), and the wiring tracks this programme's PB-02 pull request. The intended shape: the manifest reaches the step
as a masked repository secret, read only in that step's environment and never echoed, as
`.github/workflows/monthly-sql-export.yml` reads its configuration; the digest the founder confirms is the apply's
input. Nothing can be dispatched before the code is on `main` and deployed.

## Rollback

- **A mistaken grant:** revoke it (above). **A mistaken revoke:** grant again; a re-grant reopens the account's ledger
  row and writes a new audit row.
- **Code rollback:** the ledger table is additive. A revision without this code still reads `is_pro`, so granted
  accounts stay Pro under it, and Billing loses only its complimentary line (the flag keeps them out of checkout).
  Revoke before rolling back if the grants should end with the code.
- **Schema:** the migration only creates the table (`CREATE TABLE IF NOT EXISTS`). Dropping it would need a migration
  of its own after the grants are revoked.

## Limits

- A grant is inert for an account with a `Subscription` row: that row decides its plan, so the grant refuses it.
- A checkout started before a grant could still complete for up to a day; the grant refuses any account that already
  holds a Stripe customer, which every checkout claims before it opens.
- Product analytics count a complimentary Pro account as Pro.
- The grant's ledger row is not part of the account's data export; it is deleted with the account, while its audit
  rows remain, as every account audit row does.
