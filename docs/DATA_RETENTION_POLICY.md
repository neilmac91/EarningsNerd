# Data retention and deletion — implementation review

Reviewed **23 October 2026**. This records current source behaviour and remaining operational checks. It is not an approved legal retention schedule, a compliance certification or proof that every production cleanup has succeeded. The maintained customer copy is [the privacy page source](../frontend/app/privacy/page.tsx); [privacy review notes](legal/PRIVACY_POLICY.md) track unresolved disclosures.

## 1. Implementation owners

[retention_service.py](../backend/app/services/retention_service.py) owns scheduled cleanup criteria. [user_account_service.py](../backend/app/services/user_account_service.py) owns the database step of account deletion; [the users router](../backend/app/routers/users.py) owns provider requests, the audit event and session-cookie clearing. Treat the implementation as the evidence for these behaviours, rather than the historical schedules this document replaces.

## 2. Scheduled cleanup targets

These are eligibility cutoffs, not a promise of deletion at an exact instant. Cleanup uses bounded batches; `dry_run` counts candidates without deleting. Actual deployment, invocation frequency and successful outcome counts require operational verification.

### 2.1 Scope and exclusions

The service explicitly excludes inactivity-based account deletion, waitlist/referral records, audit logs, usage counters and billing rows. No inactivity warning/deletion schedule or manual purge of those categories is established by this code. Do not claim a 24-month account purge, one-year waitlist expiry, three-year audit expiry or twelve-month usage expiry.

### 2.2 Authentication and login state

| Target | Source eligibility |
| --- | --- |
| Failed-login state | `updated_at` older than seven days, with no current lock or an expired lock |
| OAuth state | Past `expires_at` |
| Refresh tokens | Expired or revoked more than thirty days ago |

These are cleanup criteria. They do not define every authentication token's lifetime or imply that all expired token rows are immediately erased.

### 2.3 Search history

`UserSearch` rows with `created_at` older than **365 days** qualify for cleanup. Account-related rows owned by the user model can also be removed through its deletion cascades. Verify actual purge outcomes before asserting the age of every remaining row.

### 2.4 Usage, audit and provider records

Usage and audit rows are not scheduled targets here. The [audit model](../backend/app/models/audit_log.py) stores account ID and email independently of the user row, so those fields can survive account deletion. [audit_service.py](../backend/app/services/audit_service.py) writes a deletion event before the account is removed. These records are not universally anonymised.

PostHog, Sentry, Resend, Google Workspace and hosting logs/backups have separate account settings and data lifecycles. No universal ninety-day event/error limit, thirty-day recording/email-log limit or backup deletion limit has been verified in this review. Do not infer provider erasure from a successful local database deletion.

### 2.5 Contact submissions

`ContactSubmission` rows with `created_at` older than **365 days** qualify for scheduled cleanup. This says nothing about copies in correspondence inboxes or provider email records. No automated two-year support-email purge is established.

## 3. Account deletion and export

An authenticated `DELETE /api/users/me` request drives the following source behaviour:

1. It attempts to cancel eligible Stripe subscriptions while retaining the Stripe customer record. Provider errors are captured in the result rather than proving all provider operations succeeded.
2. Where configured, it emits a PostHog `$delete` event and flushes it. Sending this event does not confirm that any historical provider-held records were erased.
3. It clears Sentry context for future events; this does not erase or anonymise all historical Sentry events.
4. It writes an audit record, then calls `user_account_service.delete_user` to delete the user row and commit the ORM cascades.
5. It clears sign-in cookies and returns the provider-result statuses. A final confirmation email is a future integration in the current router; this review establishes no separate confirmation-link or twenty-four-hour grace-period workflow.

Stripe, audit, operational logs and backup copies can remain. The router success message and source comments now acknowledge retained billing, audit and provider records. No fixed tax deadline or jurisdiction is asserted. The endpoint test keeps the qualified success expectation separate from the failure message, “We could not delete your account. Contact support.” Its cookie, audit, rollback and Stripe assertions remain intact.

The authenticated export route is `GET /api/users/export`. [user_data_export_service.py](../backend/app/services/user_data_export_service.py) builds the feature's export. It is not a complete export of every provider's logs, correspondence or backups. Users can use Account Settings or contact **privacy@earningsnerd.io** for help; no response commitment faster than two business days is added.

## 4. Remaining verification and decisions

- Confirm the actual cleanup schedule, deployed code, recent successful counts and handling of failures. Existence of a job/service or a passing unit gate is not proof of every production outcome; do not run a destructive purge just to create evidence.
- Establish meaningful category-specific periods or deletion criteria for billing, audit, usage, waitlist/referrals, correspondence and provider logs. Confirm any genuine preservation requirement before changing retention or deleting data.
- Review provider deletion acknowledgements and failure handling, including retained Stripe records and historical Sentry events. No provider setting or data was changed by this document.
- Read actual backup configuration and restore procedures before promising encryption/access details, deletion deadlines or replay of past deletions after a restore. No daily/weekly/monthly backup schedule is assumed.
- Keep legal scope, identity/contact and international-transfer review items in the privacy companion; no entity, personal identity details, address, jurisdiction, DPO or representative is introduced here.

## 5. Primary references

[GDPR Articles 5 and 13](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32016R0679) and [EDPB transparency guidance](https://www.edpb.europa.eu/system/files/documents/2023-09/wp260rev01_en.pdf) require meaningful retention information or criteria where applicable. These references do not set a universal period for every EarningsNerd record. [FDPIC notice guidance](https://www.edoeb.admin.ch/en/duty-to-provide-information) requires descriptions grounded in actual processing and relevant disclosures. The remaining operational and legal reviews above are not resolved by this source inventory.
