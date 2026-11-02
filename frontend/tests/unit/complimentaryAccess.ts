/**
 * PB-02: what may never describe a complimentary private-beta grant's access. Nothing expires on a grant's review date
 * (docs/ops/complimentary-access.md, "End date"), so the surfaces that name the access, Settings › Billing and the
 * dashboard's plan card, say nothing of an end, a renewal, an expiry, a trial, a price or a date: an end or renewal word,
 * a trial or cancellation, "end date", a dollar sign or a year. Read by BillingPanel.spec.tsx and
 * busyControls.dashboard.spec.tsx over each surface's text.
 */
export const COMPLIMENTARY_END_CLAIM = /\b(?:ends?|ending|ended|expir\w*|until|renew\w*|trial|cancel\w*)\b|end date|\$|\b(?:19|20)\d{2}\b/i
