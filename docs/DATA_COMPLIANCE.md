# Data Compliance

EarningsNerd processes account details, correspondence, saved features and usage records.
This source inventory supports privacy review; it does not certify compliance or establish
which regional obligations apply to the service.

This page summarizes the **current state**. The retention implementation and unresolved schedule decisions are in
[`DATA_RETENTION_POLICY.md`](./DATA_RETENTION_POLICY.md); the original gap-analysis and remediation
roadmap is archived at [`history/plans/DATA_COMPLIANCE_PLAN.md`](./history/plans/DATA_COMPLIANCE_PLAN.md).

## Implemented

| Capability | Where | Right addressed |
|------------|-------|-----------------|
| **Data export** | `GET /api/users/export` (`backend/app/routers/users.py`) | GDPR Art. 20 / CCPA right to know |
| **Account deletion** | `DELETE /api/users/me` (`backend/app/routers/users.py`) | GDPR Art. 17 / CCPA right to delete |
| **Cookie consent** | `frontend/components/CookieConsent.tsx` | GDPR Art. 7 / ePrivacy |
| **Audit trail** | `AuditLog` model + `audit_service.py` | Accountability (Art. 5(2)) |
| **Retention inventory** | [`DATA_RETENTION_POLICY.md`](./DATA_RETENTION_POLICY.md) | Storage limitation (Art. 5(e)) |
| **Security baseline** | bcrypt password hashing, JWT, TLS in transit, rate limiting, no PCI data stored (Stripe handles payments) | Art. 25 / 32 |
| **Privacy & security pages** | `frontend/app/privacy/`, `frontend/app/security/` | Transparency |

## Third-party processors

| Processor | Purpose | Data shared |
|-----------|---------|-------------|
| Stripe | Payments | Email, customer/subscription IDs |
| Resend | Transactional email | Email, name, message content |
| PostHog | Analytics | User ID and events: the browser's start only after cookie consent; the API's account events (sign-ups, plan changes, payments, feedback, feature use) are keyed on the user ID whatever the cookie choice (D-051) |
| Sentry | Error tracking | Stack traces, user context |
| DeepSeek (OpenAI-compatible API; ADR-0006) | AI summaries and filing Q&A | Selected filing content/XBRL, financial context, typed questions and recent conversation text; user input is not automatically stripped of personal information |
| Optional configured AI fallback | Bounded failed-request recovery; disabled by default | Same selected filing inputs; another provider requires an explicit API base/model and separate credential, with processor review before enabling |
| SEC EDGAR | Filing data | Ticker queries (no PII) |

## Open items

Review before relying on public assurances or authorising release:

- Confirm applicable operator/contact disclosures, provider agreements and international-transfer arrangements without inventing an entity, jurisdiction or published personal details. See [privacy review notes](legal/PRIVACY_POLICY.md).
- Establish retention/deletion criteria for categories outside scheduled cleanup, correspondence and provider-held records. Contact submissions are eligible for cleanup after 365 days; that does not establish the lifecycle of mailbox copies.
- Periodic review of the retention jobs and privacy-policy accuracy.

> Contact for privacy/security inquiries is published on the in-app Privacy and Security pages.
