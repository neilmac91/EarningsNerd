# EarningsNerd — Legal & Compliance Documents

> ⚠️ **All documents here are working templates, not legal advice.** They were drafted from the
> project's actual data flows and from researched public sources (Apple/Google developer docs, EU/UK
> GDPR, Swiss revFADP, EU consumer law). **Have a qualified Swiss/EU lawyer review them and complete
> the `[bracketed]` placeholders before publishing or relying on them.**

| Document | Purpose |
|---|---|
| [`PRIVACY_POLICY.md`](./PRIVACY_POLICY.md) | How we collect, use, share, and transfer personal data (revFADP + EU/UK GDPR + CCPA-aware). |
| [`COOKIE_POLICY.md`](./COOKIE_POLICY.md) | Cookies and local storage used, and consent. |
| [`TERMS_OF_SERVICE.md`](./TERMS_OF_SERVICE.md) | Terms for the website and direct (web) subscriptions. |
| [`APP_STORE_COMPLIANCE.md`](./APP_STORE_COMPLIANCE.md) | Apple App Store + Google Play submission checklist. |
| [`LAWYER_BRIEF.md`](./LAWYER_BRIEF.md) | Consolidated open-items register to brief an attorney (+ code issues found). |

Related: the source-code **[`LICENSE`](../../LICENSE)** (proprietary) and the app/subscription
**[End-User License Agreement](../EULA.md)**.

## Highest-priority items before launch
1. **DeepSeek (China) data transfer** for Copilot questions — disclosure, lawful mechanism, and
   consider sending no user personal data to the AI call. (Lawyer brief B2)
2. **Account deletion**: surface the in-app flow (Apple 5.1.1(v)) and build a **public web deletion
   URL** (Google).
3. **Sub-processor DPAs + SCCs**, and **EU/UK Art. 27 representatives**.
4. **Publish + link** the Privacy Policy in both store listings and in-app.
5. Complete all `[bracketed]` placeholders and get a **qualified-lawyer review**.
