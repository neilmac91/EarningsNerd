import { describe, expect, it } from 'vitest'
import { originalDocumentUrl } from '@/features/filings/lib/originalDocumentUrl'

/**
 * EN-01: "Open original" and the viewer's empty-state CTA land on the primary document
 * (`document_url`), with the EDGAR folder index (`sec_url`) as the fallback, both validated as
 * http(s) URLs and derived from the filing's own data.
 */
const FOLDER = 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/'
const DOCUMENT = `${FOLDER}aapl-20250927.htm`

describe('originalDocumentUrl', () => {
  it('prefers a valid document_url over sec_url', () => {
    expect(originalDocumentUrl({ document_url: DOCUMENT, sec_url: FOLDER })).toBe(DOCUMENT)
  })

  it('falls back to sec_url when document_url is missing, empty or not http(s)', () => {
    expect(originalDocumentUrl({ document_url: undefined, sec_url: FOLDER })).toBe(FOLDER)
    expect(originalDocumentUrl({ document_url: null, sec_url: FOLDER })).toBe(FOLDER)
    expect(originalDocumentUrl({ document_url: '', sec_url: FOLDER })).toBe(FOLDER)
    // The rejected scheme is the point of the case.
    expect(originalDocumentUrl({ document_url: 'javascript:alert(1)', sec_url: FOLDER })).toBe(FOLDER)
    expect(originalDocumentUrl({ document_url: 'ftp://example.com/x.htm', sec_url: FOLDER })).toBe(FOLDER)
  })

  it('is null when neither is a usable URL (no action is offered rather than a bad link)', () => {
    expect(originalDocumentUrl({ document_url: '', sec_url: '' })).toBeNull()
    expect(originalDocumentUrl({ document_url: null, sec_url: null })).toBeNull()
    expect(originalDocumentUrl({})).toBeNull()
    expect(originalDocumentUrl({ document_url: 'not a url', sec_url: 'data:text/html,x' })).toBeNull()
  })

  it('accepts plain http too (the validation is the scheme, not the host)', () => {
    expect(originalDocumentUrl({ document_url: 'http://localhost:8010/doc.htm', sec_url: FOLDER })).toBe('http://localhost:8010/doc.htm')
  })
})
