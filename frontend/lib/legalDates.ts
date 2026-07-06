/**
 * "Last updated" dates for the legal pages — pinned to each document's last CONTENT change
 * (from git history), NEVER render-time: a date that moves on every visit would defeat
 * change-notice enforceability (audit E1/F4). Update the matching key in the same commit as a
 * page's legal-text change. Kept per-document on purpose — the documents change independently.
 */
export const LEGAL_DATES = {
  terms: 'June 16, 2026',
  privacy: 'June 22, 2026',
  security: 'June 22, 2026',
} as const
