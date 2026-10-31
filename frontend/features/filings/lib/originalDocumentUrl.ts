const isHttpUrl = (u: string | null | undefined): u is string =>
  !!u && (u.startsWith('https://') || u.startsWith('http://'))

/**
 * The original document to open for a filing: `document_url` (the primary .htm) when it is an
 * http(s) URL, else `sec_url` (the EDGAR folder index), else null. Every "Open original" and
 * "Open the original on SEC.gov" action on the filing page derives its target from this, from the
 * filing's own data, never from a hard-coded sample (EN-01, the accepted "point 'open original' at
 * the document" decision). Chip-specific deep links (`source_url`, `fragment_url`) are untouched.
 */
export const originalDocumentUrl = (filing: { document_url?: string | null; sec_url?: string | null }): string | null =>
  isHttpUrl(filing.document_url) ? filing.document_url : isHttpUrl(filing.sec_url) ? filing.sec_url : null
