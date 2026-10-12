# EarningsNerd privacy policy — implementation review

Reviewed **12 October 2026**. This is a working review companion, not a separate customer privacy notice or a statement of full legal compliance.

The proposed website policy lives in [frontend/app/privacy/page.tsx](../../frontend/app/privacy/page.tsx); related controls are described in [the security page source](../../frontend/app/security/page.tsx). Those files are the maintained copy for the website routes. The changes in draft PR #1121 remain unmerged and undeployed. Final local lint/type checking, 1,991 frontend tests, build, Ruff/Bandit and 7,075 backend tests pass. Revised-page/Cookie settings browser checks remain pending while the Mac is locked; earlier email/preview results do not establish the new rendering.

## What the 12 October correction describes

- Neil operates EarningsNerd as an individual and receives privacy requests at **privacy@earningsnerd.io**. No entity, full name, address, jurisdiction, DPO or representative is added here.
- AI requests include filing material and financial context. Copilot also sends typed questions and recent conversation text without automatic removal of personal information. Account-linked usage telemetry is a separate flow.
- The configured provider is DeepSeek. Its published policy describes China processing/storage. The backend runs in the United States. Resend dispatches email from Ireland, while its region documentation says account metadata, logs and API records are stored in the United States. These facts are not a complete inventory of every provider destination.
- Optional PostHog browser choices are separate from server operational metrics, error reporting and cookieless Vercel traffic measurements. Do Not Track supplies initial optional-browser preferences only when no saved choice exists; saved preferences take precedence.
- Search history/contact records older than 365 days qualify for scheduled cleanup. The cleanup excludes inactivity-based account deletion, waitlist/referral records, usage, audit and billing data. Account deletion is not universal instant erasure: billing/audit records and provider copies can remain.
- Security copy describes verified application controls and removes unsupported universal endpoint-authentication, uptime, infrastructure and deletion claims. It does not certify the product or its providers.

## Remaining review items

1. **Controller identity/contact disclosure:** the site retains Neil-only wording under the founder's instruction. The identity/contact disclosure gap remains unresolved; do not fill it with invented details or treat a working role email as complete compliance.
2. **Provider arrangements:** verify each actual recipient, processing destination, accepted agreement and applicable transfer arrangement. Do not assert executed DPAs/SCCs or lawful safeguards without evidence. This review did not accept terms, change providers or establish every provider's retention/training settings.
3. **Retention:** confirm category-specific billing, audit, usage, waitlist, provider-log and backup periods or meaningful deletion criteria. Scheduled cleanup code is not proof of every production purge outcome. No single seven-year tax deadline, universal 90-day log limit or 12-month backup limit is claimed.
4. **Legal scope:** assess applicable jurisdictions, processing grounds and any representative duties from actual operations. No country of establishment, representative appointment or blanket GDPR/FADP/CCPA compliance is inferred.
5. **Verification/release:** complete the changed-page and Cookie Settings browser checks, then update their results separately; final local frontend/backend gates pass. No merge, deployment, data deletion or account change is authorised by this document.

## Primary references

- [GDPR, Articles 13–14](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32016R0679): identity/contact, purposes/grounds, retention and transfer disclosures where applicable.
- [FDPIC information duties](https://www.edoeb.admin.ch/en/duty-to-provide-information): transparent current processing, recipients and destination-country/protection information.
- [EDPB transparency guidance](https://www.edpb.europa.eu/system/files/documents/2023-09/wp260rev01_en.pdf): meaningful category-specific retention information or criteria.
- [DeepSeek privacy policy](https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html) and [Resend regions/data residency](https://resend.com/docs/dashboard/domains/regions): vendor statements, not proof of account-specific contract acceptance.
- [Swiss accounting guidance](https://www.kmu.admin.ch/en/electronic-bookkeeping): ten-year retention for relevant accounting records if those duties apply; it is not a blanket period for all customer data, and establishment is not assumed.
