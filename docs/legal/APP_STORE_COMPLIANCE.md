# EarningsNerd — App Store & Google Play Compliance Checklist

**Prepared: [DATE] · Status: pre-submission working checklist**

> ⚠️ **Not legal advice.** A working checklist compiled from Apple and Google developer
> documentation, tailored to EarningsNerd's stack (first-party PostHog analytics, user accounts, and
> the Copilot flow that sends **user-typed questions to a China-based AI provider, DeepSeek**). Items
> needing counsel are flagged. Re-verify against the current Apple/Google docs before submission, as
> their requirements change.

**The single highest-risk item across both stores** is disclosing and lawfully handling the
**Copilot → DeepSeek (China)** transfer of user-typed content. It must be reflected in your privacy
declarations on both stores and in the Privacy Policy, and likely needs a prominent in-app
disclosure + consent. **Get legal review on this specifically.**

---

## Apple App Store

### App Privacy Details ("Privacy Nutrition Labels") — Guideline 5.1.1
- [ ] Complete the **App Privacy** questionnaire in App Store Connect for every data type collected,
      including: **User Content** (Copilot questions, saved notes), **Identifiers** (user ID),
      **Usage Data / Diagnostics** (PostHog, Sentry), **Contact Info** (email), **Purchases**.
- [ ] Bucket each type correctly as **Linked to You** (you have accounts) and ensure **none is
      mis-flagged as "Used to Track You"** — you do not do cross-app advertising or sell to data
      brokers.
- [ ] Reflect the **DeepSeek transfer** of Copilot questions in your declarations.

### App Tracking Transparency (ATT) — Guideline 5.1.2
- [ ] Confirm you **do not access the IDFA** and PostHog stays **first-party** (not combined with
      other companies' data for ads, not shared with brokers) → **no ATT prompt required**.
- [ ] If you ever add an advertising/attribution SDK, implement `requestTrackingAuthorization` + a
      purpose string before any tracking.

### Account Deletion — Guideline 5.1.1(v)
- [ ] Provide **in-app** account + data deletion (you already have `DELETE /api/users/me`; surface it
      clearly in account settings). Must be **full deletion**, not deactivation.
- [ ] Ensure guest/auto-created accounts are deletable; avoid undue friction (confirmation/reauth is
      fine). A web link may **supplement** but not replace the in-app flow.
- [ ] **Fix the deletion cookie bug** (clears `auth_token` instead of `earningsnerd_access_token`
      **and** `earningsnerd_refresh_token`) — see the Lawyer brief, item F1.

### Privacy Policy link — Guideline 5.1.1(i)
- [ ] Add the Privacy Policy URL in **both** the App Store Connect metadata field **and** in-app.
- [ ] Ensure the policy states third-party recipients provide **equal or greater** data protection —
      this directly implicates the **DeepSeek** disclosure. **Lawyer review.**

### Subscriptions — Guideline 3.1.2
- [ ] In-app + App Store metadata disclose: title, length, **price per period**, that payment is
      charged to the Apple ID, **auto-renewal/cancel** terms, and **functional links to the Privacy
      Policy and EULA/Terms** (see `docs/EULA.md`).

---

## Google Play

### Data Safety form (App content page)
- [ ] Declare **collection** and **sharing** for all data types (Personal info, App activity incl.
      in-app search and user content, Device IDs, Diagnostics, Purchases).
- [ ] Declare the **Copilot → DeepSeek transfer as "data shared"** (sending user content to a
      third-party provider is sharing).
- [ ] Declare **encrypted in transit = Yes** (HTTPS) and **users can request deletion = Yes**.

### Account deletion (two paths required)
- [ ] **In-app** account + data deletion.
- [ ] **Public web URL** for account + data deletion, submitted in the Data safety form, that **works
      for users without the app installed**. *(You'll need to build this web deletion page/flow.)*

### Privacy policy + User Data policy
- [ ] Privacy Policy linked in **both** the Play Console field **and** in-app.
- [ ] Provide a **prominent in-app disclosure + affirmative consent** before sending Copilot
      questions to DeepSeek (likely outside users' reasonable expectation). **Lawyer review.**

### Subscriptions
- [ ] Clearly disclose offer terms, cost, billing frequency, and auto-renewal on the plan-selection
      screen; provide in-app cancellation (and on the website if you sell there too).

---

## Cross-cutting (regulatory)

- [ ] **DeepSeek / China transfer (highest priority):** confirm the lawful transfer mechanism
      (SCCs/exception), the disclosure, and the in-app consent UX. Consider **privacy-by-design**:
      send no user personal data to the AI call. **Lawyer.** (See Lawyer brief B2.)
- [ ] **EU cookie consent:** prior opt-in for non-essential/analytics cookies, granular, no
      pre-ticked boxes, withdrawable; back it with the **[Cookie Policy](./COOKIE_POLICY.md)**. (Your
      banner already gates PostHog on consent — good.)
- [ ] **CCPA/CPRA:** likely out of scope pre-launch (below the ~$26.6M revenue / 100k-consumer /
      50%-revenue-from-sharing thresholds); **document the assessment** and re-check at scale.
      **Lawyer confirm.**
- [ ] **Build the public web account-deletion page** (required by Google; also a good supplement for
      Apple).

---

### Key references
- Apple App Privacy Details: https://developer.apple.com/app-store/app-privacy-details/
- Apple ATT / User Privacy & Data Use: https://developer.apple.com/app-store/user-privacy-and-data-use/
- Apple Review Guidelines (3.1.2, 5.1.1, 5.1.2): https://developer.apple.com/app-store/review/guidelines/
- Apple account deletion: https://developer.apple.com/support/offering-account-deletion-in-your-app/
- Google Play Data safety: https://support.google.com/googleplay/android-developer/answer/10787469
- Google Play account deletion: https://support.google.com/googleplay/android-developer/answer/13327111
- Google Play User Data policy: https://support.google.com/googleplay/android-developer/answer/10144311
- CCPA (CA AG): https://oag.ca.gov/privacy/ccpa · CPPA: https://cppa.ca.gov/faq.html
- EDPB cookie-consent guidance: https://www.edpb.europa.eu/

*Research only — not legal advice.*
