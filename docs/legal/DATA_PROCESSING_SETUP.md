# EarningsNerd — Data Processing Setup (DPAs, SCCs & Representatives)

**Prepared: [DATE]**

> ⚠️ **Not legal advice.** A practical action guide for putting the required data-processing
> agreements and representatives in place. Links and exact steps change — verify each on the
> provider's current site, and have counsel confirm before you rely on this for compliance.

This is the **recommended approach** for two open items from the Lawyer Brief: **(B1)** Data
Processing Agreements + Standard Contractual Clauses with each sub-processor, and **(B4)** EU/UK
Art. 27 representatives. The good news: most of this is **click-to-accept**, not custom contracts.

## Part 1 — Sub-processor DPAs / SCCs

For each service that processes personal data on your behalf, you need a **Data Processing Agreement
(DPA)**. For data leaving Switzerland/the EEA to a non-adequate country, the DPA must include
**Standard Contractual Clauses (SCCs)** (use the **Swiss-adapted EU SCCs** for Swiss-law transfers).
Most providers below include SCCs in their DPA by default.

| Sub-processor | How to put a DPA in place | Notes |
|---|---|---|
| **Google Cloud** (hosting + DB) | Cloud Data Processing Addendum is **auto-incorporated** into the Cloud terms; review at cloud.google.com/terms/data-processing-addendum | Includes SCCs; US (DPF-certified) |
| **Stripe** (payments) | Stripe's DPA is part of the Services Agreement; review at stripe.com/legal/dpa | Stripe is also an independent controller for payments |
| **Vercel** (hosting/analytics) | Accept the DPA at vercel.com/legal/dpa (self-serve; sign in Vercel dashboard if a signature flow is offered) | Includes SCCs |
| **PostHog** (analytics) | Accept/download DPA at posthog.com/dpa | Consider the **EU Cloud** region to reduce US transfer |
| **Sentry** (errors) | DPA at sentry.io/legal/dpa/ | Configure PII scrubbing (see Lawyer Brief F4) |
| **Resend** (email) | DPA at resend.com/legal/dpa | Recipient email/name only |
| **Cloudflare** (Turnstile) | DPA at cloudflare.com/cloudflare-customer-dpa/ | Token + IP |
| **DeepSeek** (AI) | **Request a DPA + SCCs directly** from the provider; if none is available, this strengthens the case to **switch the AI endpoint** to a DPF/EU provider | **China — highest priority; see Part 4** |
| **Apple / Google** (sign-in, app stores) | Covered by the Apple Developer Program License Agreement / Google Play DDA you already accept | Re-confirm the data-protection addenda |

**Action:** work down this list, accept/sign each DPA from the account owner login, and **save a PDF
of each** in a `legal/dpas/` folder (off-repo, e.g. your password manager or Drive). Keep a simple
list of "provider · DPA accepted on · SCCs yes/no · region."

## Part 2 — EU & UK Art. 27 representatives

As a **Switzerland-based** controller offering subscriptions to EU/EEA and UK users, you likely need:
- an **EU representative** (GDPR Art. 27), and
- a **UK representative** (UK GDPR Art. 27).

**Recommended approach:** use a **"representative-as-a-service"** provider rather than appointing an
individual — it's inexpensive and turnkey. Well-known options include **Prighter**, **DataRep**, and
**IT Governance/GDPR-Rep.eu**. Typical steps:
1. Choose a provider that covers **both EU and UK** (most do, as a bundle).
2. Sign up; they give you an **EU address + UK address** and a contact channel for data subjects and
   authorities.
3. **Publish the representative's name + address in your Privacy Policy** (the template has a
   placeholder in Section 1) and in your data-subject-request contact info.
4. Forward any data-subject/authority contact they receive to your `privacy@earningsnerd.io`.

**Cost:** typically on the order of low hundreds of CHF/year for the bundle. **Have counsel confirm**
whether the Art. 27 "occasional/low-risk" exemption applies before paying — but for an ongoing
worldwide subscription product it usually does **not**.

## Part 3 — Keep a minimal Record of Processing (ROPA)

Even though the Swiss <250-employee exemption may apply, keep a one-page record (also useful for
EU/UK Art. 30). It should list, per processing activity: purpose, data categories, data subjects,
recipients/sub-processors (Part 1), retention, and transfer destinations + safeguards (Part 4). A
simple spreadsheet is fine.

## Part 4 — International transfer specifics

- **USA** (Google Cloud, Vercel, Stripe, PostHog, Sentry, Resend, Apple, Google, Cloudflare): rely on
  each recipient's **Data Privacy Framework** certification where available, otherwise the **SCCs** in
  its DPA. Name the **United States** in the Privacy Policy (already done).
- **China — DeepSeek** (Copilot questions): **no adequacy decision, no framework.** Either obtain
  **SCCs/data-protection clauses** from DeepSeek **and** do a transfer-impact assessment, **or** the
  cleaner path — **switch `OPENAI_BASE_URL` to a DeepSeek-equivalent provider in the US (DPF) or EU**
  for the Copilot path. This is the single highest-priority transfer item. (See Lawyer Brief B2.)

## Action checklist

- [ ] Accept/sign each sub-processor **DPA** (Part 1); archive the PDFs.
- [ ] Decide the **DeepSeek** path: DPA+SCCs+TIA, or switch provider jurisdiction.
- [ ] Engage an **EU + UK Art. 27 representative** (Part 2) and fill the Privacy Policy placeholder.
- [ ] Write the one-page **ROPA** (Part 3).
- [ ] Have **counsel review** the transfer mechanisms and the Art. 27 necessity.
