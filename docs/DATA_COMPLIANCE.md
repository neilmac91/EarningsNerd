# Data Compliance

EarningsNerd processes personal data (email, name, hashed password, search history, watchlists,
usage metrics) and serves users in the EU and North America, so it is built against **GDPR**,
**CCPA/CPRA**, **PIPEDA**, and **CAN-SPAM**.

This page summarizes the **current state**. The detailed retention schedule is in
[`DATA_RETENTION_POLICY.md`](./DATA_RETENTION_POLICY.md); the original gap-analysis and remediation
roadmap is archived at [`history/plans/DATA_COMPLIANCE_PLAN.md`](./history/plans/DATA_COMPLIANCE_PLAN.md).

## Implemented

| Capability | Where | Right addressed |
|------------|-------|-----------------|
| **Data export** | `GET /api/users/export` (`backend/app/routers/users.py`) | GDPR Art. 20 / CCPA right to know |
| **Account deletion** | `DELETE /api/users/me` (`backend/app/routers/users.py`) | GDPR Art. 17 / CCPA right to delete |
| **Cookie consent** | `frontend/components/CookieConsent.tsx` | GDPR Art. 7 / ePrivacy |
| **Audit trail** | `AuditLog` model + `audit_service.py` | Accountability (Art. 5(2)) |
| **Documented retention** | [`DATA_RETENTION_POLICY.md`](./DATA_RETENTION_POLICY.md) | Storage limitation (Art. 5(e)) |
| **Security baseline** | bcrypt password hashing, JWT, TLS in transit, rate limiting, no PCI data stored (Stripe handles payments) | Art. 25 / 32 |
| **Privacy & security pages** | `frontend/app/privacy/`, `frontend/app/security/` | Transparency |

## Third-party processors

| Processor | Purpose | Data shared |
|-----------|---------|-------------|
| Stripe | Payments | Email, customer/subscription IDs |
| Resend | Transactional email | Email, name, message content |
| PostHog | Analytics | User ID, events (gated by cookie consent) |
| Sentry | Error tracking | Stack traces, user context |
| Google AI Studio (Gemini) | AI summaries | SEC filing content (no PII) |
| SEC EDGAR | Filing data | Ticker queries (no PII) |

## Open items

Tracked for ongoing compliance hygiene (not launch-blocking):

- Obtain/record Data Processing Agreements (DPAs) for Resend, PostHog, Sentry; confirm Stripe DPA.
- Decide IP-address handling for `contact_submissions` (hash or expire vs. store raw).
- Periodic review of the retention jobs and privacy-policy accuracy.

> Contact for privacy/security inquiries is published on the in-app Privacy and Security pages.
