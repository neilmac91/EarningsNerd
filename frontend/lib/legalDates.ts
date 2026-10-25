/**
 * "Last updated" dates for the legal pages — pinned to each document's last CONTENT change
 * (from git history), NEVER render-time: a date that moves on every visit would defeat
 * change-notice enforceability (audit E1/F4). Update the matching key in the same commit as a
 * page's legal-text change. Kept per-document on purpose — the documents change independently.
 * A date is the day main's history gives the merge that ships the change, in the offset that
 * history records (`git log -1 --date=short --format=%cd <merge>`). GitHub stamps main's merges in
 * the founder's time zone, so a merge late in a UTC day can carry the next day's date. Whether a
 * date matches its merge is review-checked (tests/unit/legalTruth.spec.tsx, item 4).
 */
export const LEGAL_DATES = {
  terms: 'October 24, 2026',
  privacy: 'October 25, 2026',
  security: 'October 24, 2026',
} as const
