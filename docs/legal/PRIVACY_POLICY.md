# Privacy notice — source review

Reviewed **24 October 2026**. The maintained customer notice is [the privacy page](../../frontend/app/privacy/page.tsx); [the security page](../../frontend/app/security/page.tsx) describes application controls. This companion records source facts and review needs, rather than defining a separate notice or certifying compliance. Release status and deployed behaviour must be checked against the final release revision.

## Current data facts

- Account, waitlist, support and product activity records support sign-in, access, subscriptions, saved features and correspondence.
- The configured AI provider is DeepSeek. Requests include filing material and financial context; Copilot also sends typed questions and recent conversation text. These inputs are not automatically stripped of personal information. Account-linked usage/cost telemetry is separate.
- Hosting, payments, email, diagnostics and optional browser analytics use service providers. Social sign-in, bot checks, password screening and externally delivered company images add recipients where used. Provider names, purposes and relevant transfer information should reflect actual configuration.
- Optional PostHog and Vercel browser analytics stay off until allowed through Cookie settings. Session recording is disabled. Choices can be withdrawn there. Version 3 re-asks for older analytics allows while preserving valid older refusals. A withdrawal applies immediately in the current tab even if saving fails; the interface explains that persistence limitation. Requests already dispatched cannot be recalled, and withdrawal does not erase previously received provider data. Do Not Track does not change these choices. The browser switches do not disable account events, separate server operational metrics or security/error reporting; the privacy and security pages use the shared account-events disclosure.
- Search/contact records older than 365 days qualify for scheduled cleanup. Inactivity-based account deletion, waitlist/referrals, audit, usage and billing records are outside that purge. Account deletion removes the records handled by its application process; retained billing/audit records and provider copies can remain. The export feature does not cover every provider's records.
- Current source configures telemetry sanitization and disables both PostHog session recording and Sentry replay. These controls do not establish that all collection is anonymous or erase historical records. See [retention/deletion review](../DATA_RETENTION_POLICY.md) and [cookie review](COOKIE_POLICY.md), with the transport and cross-tab limits in [Browser consent](../BROWSER_CONSENT.md).

## Review before release

Confirm responsible-operator identification and contact information, applicable jurisdictions, processing grounds and any representative requirements from actual operations. A brand name or role address does not itself establish that these duties are satisfied. Do not invent an entity, address, jurisdiction or officer.

Verify recipient/destination coverage, accepted provider agreements, applicable transfer arrangements and any retention/training terms before making assurances about them. DeepSeek's published policy describes China processing/storage. Backend hosting is in the United States. Resend's EU sending region does not establish EU-only account-data storage. Provider statements are not proof of account-specific terms or safeguards.

Establish meaningful periods or deletion criteria for retained billing, audit, usage, waitlist, correspondence, provider logs and backups. Scheduled cleanup code does not prove every production purge outcome; sending a provider deletion event does not confirm erasure. Do not publish universal retention periods, instant-erasure promises or unsupported security guarantees.

Validate the final changed notice, Cookie settings controls and release revision. Earlier checks and preview results apply to their recorded revisions; this document neither changes live processing nor authorises deployment.

## Primary references

- [GDPR Articles 13–14](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32016R0679) and [FDPIC information duties](https://www.edoeb.admin.ch/en/duty-to-provide-information): applicable identification, processing, recipient and transfer disclosures.
- [EDPB transparency guidance](https://www.edpb.europa.eu/system/files/documents/2023-09/wp260rev01_en.pdf): meaningful retention information and accessible explanations.
- [DeepSeek privacy policy](https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html) and [Resend regions/data residency](https://resend.com/docs/dashboard/domains/regions): vendor statements requiring account-specific review.
