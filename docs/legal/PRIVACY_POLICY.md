# EarningsNerd — Privacy Policy

**Last updated: [DATE] · Version 1.0**

> ⚠️ **Template — not legal advice.** This policy was drafted from the project's actual data flows and
> from research into the Swiss revFADP, EU/UK GDPR, and app-store requirements. It **must be reviewed
> by a qualified data-protection lawyer** and the **`[bracketed]` placeholders completed** (effective
> date, full address, and any EU/UK representative) before you publish or rely on it. Verify the
> sub-processor list and the AI-provider destination against your live production configuration.

This Privacy Policy explains how **EarningsNerd** ("**we**", "**us**") collects, uses, and shares
personal data when you use our website and mobile/web application and related services (the
"**Service**"). It is written to meet the Swiss Federal Act on Data Protection (**revFADP**), the
EU and UK **GDPR**, and, where applicable, the California **CCPA/CPRA**.

## 1. Who we are (data controller)

The data controller is:

> **[Neil Mac Aogain]**
> **[Street address]**
> **[Postal code, City], Switzerland**
> Privacy contact: **privacy@earningsnerd.io**

We are a Switzerland-based controller. Because we offer the Service to users in the EU/EEA and the
UK, an **EU representative (GDPR Art. 27)** and a **UK representative (UK GDPR Art. 27)** may be
required; **[to be appointed — see open items]**.

## 2. The personal data we collect

We collect only what we need to run the Service:

| Category | Examples | Source |
|---|---|---|
| **Identity & contact** | Email address; optional full name | You (registration, waitlist, contact form); OAuth provider |
| **Account & authentication** | Hashed password; OAuth provider identifiers (Google/Apple — Apple may be a private-relay email); login timestamps; email-verification and password-reset tokens (stored only as hashes) | You; OAuth provider |
| **Subscription & billing** | Your Stripe customer and subscription IDs, plan, status, and renewal dates. **We do not store your card number** — all card data is handled by Stripe. | You (via Stripe checkout) |
| **Usage & content you create** | Search queries; saved summaries and your notes; watchlists; notification preferences; "Ask this Filing" (Copilot) questions you type | You |
| **Usage metering** | Counts of summaries/questions generated (for quota and abuse prevention) | Automatic |
| **Device & technical** | IP address (**stored only in hashed form**); browser/User-Agent; for anonymous visitors, a transient IP used briefly for rate-limiting and bot defense | Automatic |
| **Support & marketing** | Contact-form and waitlist messages; referral information | You |
| **Audit & security logs** | Records of security-relevant actions (login, export, deletion, subscription changes), with hashed IP and User-Agent | Automatic |

We **do not** intentionally collect special-category data, and the Service is **not directed to
children** (see Section 11). Company/SEC filing data processed by the Service is public information,
not your personal data.

## 3. Why we use your data, and our legal bases

| Purpose | Legal basis (EU/UK GDPR) |
|---|---|
| Provide the Service, your account, summaries, and Copilot answers | Performance of a **contract** (Art. 6(1)(b)) |
| Process subscriptions and payments | Performance of a **contract** |
| Authenticate you and keep accounts and data secure (hashing, bot defense, breached-password screening, rate limiting, audit logs) | **Legitimate interests** (Art. 6(1)(f)) and **legal obligation** (Art. 6(1)(c)) |
| Send service/transactional emails (verification, password reset, filing alerts you opt into) | **Contract** / your **consent** for optional alerts |
| Product analytics (PostHog) and optional session recording | Your **consent** (Art. 6(1)(a)) — set via the cookie banner |
| Diagnose errors and improve reliability (Sentry) | **Legitimate interests** |
| Marketing/waitlist communications | Your **consent** |

Under the **Swiss revFADP**, a private controller may process personal data without first
identifying a "legal basis"; we nonetheless process lawfully, in good faith, proportionately, and
for the purposes described here, and we obtain consent where required (e.g., analytics cookies).

## 4. Cookies and similar technologies

We use strictly necessary cookies (for login/session) and, **with your consent**, analytics
cookies. Non-essential analytics do **not** load until you accept them in our cookie banner. Full
details — names, providers, purposes, and durations — are in our **[Cookie Policy](./COOKIE_POLICY.md)**.

## 5. Who we share your data with (sub-processors)

We do not sell your personal data. We share it only with service providers ("sub-processors") that
help us run the Service, under appropriate contractual protections:

| Sub-processor | Purpose | Personal data involved | Location |
|---|---|---|---|
| **Google Cloud** (Cloud Run, Cloud SQL) | Application hosting and primary database | All stored account data | USA (us-west1) |
| **Vercel** | Frontend hosting + privacy-friendly analytics | Technical/usage data | USA |
| **Stripe** | Payments and subscriptions | Billing identifiers; card data handled by Stripe | USA |
| **Resend** | Transactional & alert email | Your email address and name | USA |
| **PostHog** | Product analytics (consent-gated) | User/device identifiers; for guests, a hashed/derived IP-based id | USA |
| **Sentry** | Error and performance monitoring | Diagnostic data that may incidentally include identifiers | USA |
| **Cloudflare (Turnstile)** | Bot defense | A challenge token and IP address | USA / global |
| **DeepSeek** (default AI provider) | Generating summaries and Copilot answers | Public SEC filing text; **and, for Copilot, the questions you type** (no account identifiers are sent) | **People's Republic of China** |
| **Google / Apple** | Optional social sign-in | Authentication identifiers | USA |
| **Have I Been Pwned** | Breached-password screening | Only the first five characters of a password hash (k-anonymity) | USA / global |

Market-data and SEC sources we query (Finnhub, FMP, Stocktwits, EarningsWhispers, SEC EDGAR) receive
only tickers/identifiers, **not your personal data**.

> **Note on the AI provider:** the default provider is **DeepSeek (China)**. For summaries, only
> public filing text is sent. For "Ask this Filing," the **questions you type** are sent (without your
> name, email, or account ID). Avoid typing personal or confidential information into Copilot. The
> provider is configurable, so the actual destination depends on our production configuration.

## 6. International data transfers

Your personal data is processed **outside Switzerland and the EU/EEA**, namely in the **United
States** (the sub-processors above) and, for the AI features, potentially the **People's Republic of
China** (DeepSeek). Where we transfer personal data abroad we rely on:

- **United States:** the **Swiss–U.S. / EU–U.S. Data Privacy Framework** for certified recipients,
  and/or **Standard Contractual Clauses** (the FDPIC-recognised, Swiss-adapted EU SCCs) for others.
- **China (DeepSeek):** there is no adequacy decision; we rely on **Standard Contractual Clauses /
  data-protection clauses or a statutory exception**, and we minimise what is sent (no account
  identifiers). **[Confirm the safeguard in place with counsel; consider keeping all user personal
  data out of the AI call.]**

You can request details of the safeguards by emailing **privacy@earningsnerd.io**.

## 7. How long we keep your data

- **Account data:** for as long as your account is active, then deleted on account closure (see
  Section 8), subject to the exceptions below.
- **Billing records:** we retain certain Stripe records for up to **~7 years** to meet accounting/tax
  obligations, even after account deletion.
- **Authentication tokens:** short-lived (access tokens ~30 minutes; refresh tokens ~30 days, then
  rotated/expired).
- **Security/audit logs:** retained for **[retention period — to be set, e.g. 12–24 months]**.
- **Caches:** transient (hours).

## 8. Your rights

Depending on where you live, you have rights to: **access** your data; **rectify** inaccurate data;
**erase** ("right to be forgotten"); **restrict** or **object to** processing; **data portability**;
and to **withdraw consent** at any time (e.g., analytics). You also have the right to **lodge a
complaint** with a supervisory authority (Section 12).

You can exercise the main rights directly in the app:

- **Export** your data: from **Account → Settings** (or `GET /api/users/export`).
- **Delete** your account and data: from **Account → Settings** (or `DELETE /api/users/me`). This is
  also how you satisfy app-store account-deletion requirements.

For any other request, email **privacy@earningsnerd.io**. We respond within the timeframes required
by applicable law (generally one month).

## 9. Automated processing and AI

We use AI to **generate summaries and answer questions about SEC filings**. This is informational
content generation, **not** a solely-automated decision producing legal or similarly significant
effects about you, and it is **not investment advice** (see our Terms/EULA). AI output may contain
errors; verify against primary sources.

## 10. How we protect your data

Security measures include: password hashing (bcrypt), hashing of stored IP addresses and refresh
tokens, breached-password screening, bot defense, rate limiting, encrypted transport (HTTPS), and
access controls. No method is perfectly secure, but we work to protect your data and will notify the
**FDPIC** and affected users of qualifying breaches as required by law.

## 11. Children

The Service is intended for adults and is **not directed to children under 16** (or the minimum age
in your jurisdiction). We do not knowingly collect their data; contact us if you believe a child has
provided personal data.

## 12. Supervisory authorities

- **Switzerland:** Federal Data Protection and Information Commissioner (**FDPIC/EDÖB**) — edoeb.admin.ch
- **EU/EEA:** your local Data Protection Authority
- **UK:** Information Commissioner's Office (**ICO**) — ico.org.uk

## 13. Changes

We may update this policy; we will post the new version with an updated date and, for material
changes, notify you by reasonable means.

## 14. Contact

Questions or requests: **privacy@earningsnerd.io** (or the postal address in Section 1).

---

### Open items to complete (require your input / a lawyer)

1. Fill placeholders: effective date and full Swiss address.
2. **Confirm the live AI-provider destination** (DeepSeek/China vs other) and the transfer safeguard
   in place; strongly consider keeping all user personal data out of the AI call (privacy-by-design).
3. **EU and UK Art. 27 representatives** — assess whether required and appoint if so.
4. Decide and document a **security/audit-log retention period**.
5. Put in place **Data Processing Agreements + SCCs** with each sub-processor (Google Cloud, Vercel,
   Stripe, Resend, PostHog, Sentry, Cloudflare, DeepSeek) and keep a minimal **record of processing**.
6. Lawyer review for CCPA applicability and final wording.
