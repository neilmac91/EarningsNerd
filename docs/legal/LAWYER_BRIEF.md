# EarningsNerd — Legal & Compliance Open-Items Register (Brief for Counsel)

**Prepared: [DATE] · for: a qualified Swiss/EU lawyer (with tech/consumer/data-protection and, ideally, US securities experience)**

> ⚠️ **Not legal advice.** This is a non-lawyer compilation, assembled from the codebase and from
> documented public sources, to help you brief an attorney efficiently and to track launch-blocking
> work. It flags issues and questions; it does not resolve them. Priorities are the author's
> estimate.

## How to use this

Hand this register, plus the documents in `docs/legal/` and `docs/EULA.md` + `LICENSE`, to your
lawyer. Items are grouped by area with a rough **priority**: 🔴 launch-blocking, 🟠 important,
🟡 follow-up.

---

## A. Entity, ownership & IP

| # | Item | Priority |
|---|---|---|
| A1 | **Entity formation.** You currently operate as a **private individual**, which means **personal liability** for the business. Advise on forming a Swiss **GmbH/AG** (timing, cost, liability shield) before scaling worldwide B2C. | 🟠 |
| A2 | **Copyright assignment to the company.** The `LICENSE` reserves rights to "successors and assigns," but a future transfer to your company needs a **separate written assignment agreement** (Art. 16 CopA). Moral rights stay with you. | 🟠 |
| A3 | **Prior "MIT" exposure.** The repo's README previously said "MIT" (one word, no `LICENSE` file, no copyright line) while public. Assess whether any enforceable open-source grant was made and the exposure for any version already copied/forked. A permissive grant, once made, is hard to revoke for copies already taken; the new proprietary license is prospective. Repo is now **private**. | 🟡 |
| A4 | **Trademark.** "EarningsNerd"/"EarningsNerd.io" are reserved in the license but **not registered**. Consider Swiss/EU/US trademark filings. | 🟡 |
| A5 | **Open-source dependency compliance.** The app bundles many OSS packages (FastAPI, Next.js, edgartools, etc.). "All rights reserved" covers only your code; you must comply with each dependency's license. Consider an SBOM / license-compliance review. | 🟡 |

## B. Data protection (revFADP + EU/UK GDPR + CCPA)

| # | Item | Priority |
|---|---|---|
| B1 | **Sub-processor DPAs + SCCs.** Put Data Processing Agreements and, for non-adequate destinations, **Standard Contractual Clauses** in place with: Google Cloud, Vercel, Stripe, Resend, PostHog, Sentry, Cloudflare, **DeepSeek**, (and Apple/Google for sign-in). | 🔴 |
| B2 | **China transfer (DeepSeek).** Copilot sends **user-typed questions** to a China-based AI provider. No adequacy decision; requires SCCs/data-protection clauses or a statutory exception, plus likely a **transfer impact assessment**. **Strongly consider privacy-by-design: send no user personal data to the AI call** (only public filing text), which may remove the issue. Confirm the **live production `OPENAI_BASE_URL`**. | 🔴 |
| B3 | **US transfers.** Name the **USA** as a destination (already done in the Privacy Policy) and rely on **Data Privacy Framework** certification and/or **Swiss-adapted EU SCCs** per sub-processor. | 🟠 |
| B4 | **EU & UK Art. 27 representatives.** As a Switzerland-based controller offering subscriptions to EU/UK users, you likely need an **EU representative** and a **UK representative** (the "occasional/low-risk" exemption probably doesn't apply to a worldwide subscription SaaS). | 🟠 |
| B5 | **Record of Processing (ROPA).** The Swiss <250-employee exemption is risk-conditional; keep a minimal ROPA anyway (also relevant to EU/UK Art. 30). | 🟡 |
| B6 | **Breach-notification readiness.** Be ready to notify the **FDPIC** (and EU/UK authorities) of qualifying breaches. | 🟡 |
| B7 | **CCPA/CPRA applicability.** Likely below the thresholds pre-scale, but confirm and add the required "notice at collection" if/when in scope. | 🟡 |
| B8 | **Audit-log retention period.** No retention policy exists in code; decide and document one (referenced as a placeholder in the Privacy Policy). | 🟠 |
| B9 | **Privacy Policy must be published and linked** in-app and in both store listings (Apple 5.1.1(i), Google), and account deletion must be available in-app (Apple 5.1.1(v)) and via a **web URL** (Google). See the app-store checklist. | 🔴 |

## C. Consumer & commercial law

| # | Item | Priority |
|---|---|---|
| C1 | **Per-market consumer law.** Validate the EULA/ToS against **EU/EEA** (CRD 2011/83, DCD 2019/770, UCTD 93/13, forthcoming digital-fairness/"cancel button" rules), **UK** (CRA 2015 + DMCC subscription rules), and other key markets. Non-waivable rights vary; disclaimers must yield to them. | 🟠 |
| C2 | **Withdrawal-right / immediate-performance** handling for **direct (Stripe) sales** (the app stores handle their own). | 🟠 |
| C3 | **Refund policy** for direct sales (the EULA defers app-store refunds to Apple/Google). | 🟡 |

## D. Tax

| # | Item | Priority |
|---|---|---|
| D1 | **VAT/GST registration.** App stores often remit VAT as deemed supplier, but **not universally**; **direct (Stripe) sales make you the merchant of record**, triggering your own VAT obligations (Swiss VAT thresholds; EU **OSS/IOSS**; possible US sales-tax exposure). Confirm where you must register. | 🟠 |

## E. Securities / "investment advice" perimeter

| # | Item | Priority |
|---|---|---|
| E1 | **Investment-advice disclaimer.** EarningsNerd analyses SEC filings. Confirm wording that avoids implying **regulated investment advice** in the **US (SEC/FINRA)**, **EU (MiFID II)**, and **Switzerland (FinSA/FinIA)**. The current disclaimer (EULA §9, ToS §8) is a starting point. | 🟠 |

## F. Code/product issues found during the data inventory (engineering, not legal)

These don't need a lawyer but affect compliance accuracy and should be fixed:

| # | Item | Priority |
|---|---|---|
| F1 | **Account-deletion clears the wrong cookie.** `DELETE /api/users/me` clears a cookie named `auth_token`, but the access cookie is `earningsnerd_access_token` — so it isn't actively cleared on deletion. | 🟠 |
| F2 | **Contact-form IP hash uses a weak default salt** (`"default-salt-change-in-production"`) and a different scheme than the `SECRET_KEY`-peppered hashing used elsewhere. Set a strong `IP_HASH_SALT` in production (or unify on the peppered scheme). | 🟠 |
| F3 | **No audit-log retention/purge** — logs appear retained indefinitely. Implement retention per B8. | 🟡 |
| F4 | **Sentry captures console logs** (`enableLogs: true`), which may incidentally include identifiers in error payloads. Review scrubbing / PII filtering. | 🟡 |
| F5 | **Rate limiting is per-process**, not shared across Cloud Run instances — don't overstate it as a global control. | 🟡 |

*(I can open a separate engineering PR for F1–F5 if you'd like — just say so.)*

## G. Placeholders to complete across the legal documents

Before publishing, fill the `[bracketed]` placeholders in: `LICENSE`, `docs/EULA.md`,
`docs/legal/PRIVACY_POLICY.md`, `docs/legal/COOKIE_POLICY.md`, `docs/legal/TERMS_OF_SERVICE.md` —
notably the **effective date**, **full Swiss postal address**, **EU/UK representative** details (if
appointed), and the **audit-log retention period**. Confirm the `@earningsnerd.io` mailboxes are live.

---

### Sources behind this register
Apple custom-EULA minimum terms & subscription rules; Google Play policies; EU CRD/DCD/UCTD; Swiss
revFADP (FADP SR 235.1) incl. Art. 19(4) country-naming and the FDPIC cross-border guidance; UK GDPR
/ ICO; Swiss CopA (Art. 2/6/16). Full citations are in the project's research notes. **All subject to
qualified-lawyer confirmation.**
