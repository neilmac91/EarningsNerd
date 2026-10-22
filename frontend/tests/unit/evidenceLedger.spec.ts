import { describe, expect, it } from 'vitest'
import type { Filing } from '@/features/filings/api/filings-api'
import { earlierExample, laterExample } from '@/features/research-evidence-packs/data/fictionalExample'
import { captureSource, createEntry, exportEvidence, parseFilingId, proposeSource, recordReview, sourceDocument, sourceIdentity, updateInterpretation } from '@/features/research-evidence-packs/lib/evidenceLedger'

const now = '2026-10-11T12:00:00.000Z'
const earlier = captureSource(earlierExample, 0, now)
const later = captureSource(laterExample, 0, now)
const initial = createEntry(1, earlier)
/** A snapshot as the JSON export writes it: EDGAR's conformed name in `companyName`, and no other name key. */
const asServed = ({ conformedName, ...snapshot }: typeof earlier) => ({ ...snapshot, companyName: conformedName })
const filing: Filing = { id: 3, filing_type: '10-K', accession_number: '0000000123-26-000001', report_date: '2025-12-31T00:00:00+00:00', filing_date: '2026-02-10T00:00:00.123456Z', company: { id: 123, name: 'Test Company', ticker: 'TEST' }, document_url: 'https://www.sec.gov/Archives/edgar/data/123/000000012326000001/original.htm', sec_url: '' }

describe('source capture boundary', () => {
  it.each(['', '0', '-1', '1.2', '2e1', '9007199254740992'])('refuses invalid filing IDs %j', (value) => expect(parseFilingId(value)).toBeNull())
  it('accepts API dates and freezes an identity tied to its requested accession', () => {
    const identity = sourceIdentity(filing, 3)
    expect(identity.reportDate).toBe('2025-12-31')
    expect(identity.filedDate).toBe('2026-02-10')
    expect(Object.isFrozen(identity)).toBe(true)
  })
  it.each([
    { id: 4 }, { company: undefined }, { filing_type: '10-K/A' }, { accession_number: 'invalid' },
    { report_date: '2025-02-30' }, { report_date: '2025-12-31T00:99:00Z' }, { filing_date: '2024-01-01' },
    { document_url: 'javascript:alert(1)' }, { document_url: 'https://evil.test/Archives/edgar/data/123/000000012326000001/a.htm' },
    { document_url: 'https://www.sec.gov/Archives/edgar/data/123/000000012325000001/a.htm' },
  ])('rejects untrusted identity patch %j', (patch) => expect(() => sourceIdentity({ ...filing, ...patch }, 3)).toThrow())
  it('names the company in its display casing where the filing enters, so the pack and its export print it so (E146)', () => {
    const identity = sourceIdentity({ ...filing, company: { id: 123, name: 'SAMPLE INDUSTRIES A INC', ticker: 'TEST' } }, 3)
    expect(identity.companyName).toBe('Sample Industries A Inc')
    const document = sourceDocument(identity, { filingId: 3, hasContent: true, markdownContent: 'First paragraph.' })
    const markdown = exportEvidence([createEntry(1, captureSource(document, 0, now))], 'markdown', now)
    expect(markdown).toContain('Sample Industries A Inc (TEST)')
    expect(markdown).not.toContain('SAMPLE INDUSTRIES')
  })
  it("keeps EDGAR's conformed name, as served, in the JSON export, the record a reader downloads (chief design on #1491)", () => {
    const company = { id: 123, name: 'SAMPLE INDUSTRIES A INC', ticker: 'TEST' }
    const identity = sourceIdentity({ ...filing, company }, 3)
    expect(identity.conformedName).toBe('SAMPLE INDUSTRIES A INC')
    const laterFiling: Filing = { ...filing, id: 4, company, accession_number: '0000000123-27-000001', report_date: '2026-12-31', filing_date: '2027-02-10',
      document_url: 'https://www.sec.gov/Archives/edgar/data/123/000000012327000001/original.htm' }
    const document = sourceDocument(identity, { filingId: 3, hasContent: true, markdownContent: 'First paragraph.' })
    const laterDocument = sourceDocument(sourceIdentity(laterFiling, 4), { filingId: 4, hasContent: true, markdownContent: 'Later paragraph.' })
    const proposed = proposeSource(createEntry(1, captureSource(document, 0, now)), captureSource(laterDocument, 0, now))
    const json = JSON.parse(exportEvidence([recordReview(proposed, 'kept', 'Kept the first paragraph.', now)], 'json', now)) as {
      entries: { revisions: Record<string, unknown>[]; proposal: null; reviews: { candidate: Record<string, unknown> }[] }[]
    }
    const [entry] = json.entries
    for (const snapshot of [...entry.revisions, entry.reviews[0].candidate]) {
      expect(snapshot.companyName).toBe('SAMPLE INDUSTRIES A INC')
      expect(snapshot).not.toHaveProperty('conformedName')
    }
  })
  it('captures an exact selected paragraph without accepting substituted or missing text', () => {
    const identity = sourceIdentity(filing, 3)
    const document = sourceDocument(identity, { filingId: 3, hasContent: true, markdownContent: 'First paragraph.\n\n  Second <script> text.\nStill second.  ' })
    expect(captureSource(document, 1, now)).toMatchObject({ quote: 'Second <script> text.\nStill second.', paragraph: 2, accession: filing.accession_number })
    expect(() => captureSource(document, 2, now)).toThrow('Select a paragraph')
    expect(() => sourceDocument(identity, { filingId: 4, hasContent: true, markdownContent: 'Wrong filing' })).toThrow('does not match')
    expect(() => sourceDocument(identity, { filingId: 3, hasContent: false, markdownContent: null })).toThrow('unavailable')
  })
  it('abstains at document bounds without truncating', () => {
    const identity = sourceIdentity(filing, 3)
    for (const markdownContent of ['x'.repeat(120_001), Array(401).fill('Paragraph').join('\n\n')]) {
      expect(() => sourceDocument(identity, { filingId: 3, hasContent: true, markdownContent })).toThrow('nothing was truncated')
    }
  })
})

describe('review ledger', () => {
  it('appends a revision only on an explicit noted acceptance and preserves the prior evidence', () => {
    const edited = updateInterpretation(initial, 'Revisit concentration.')
    const proposed = proposeSource(edited, later)
    expect(proposed.revisions).toEqual([earlier])
    expect(proposed.status).toBe('review-needed')
    expect(() => recordReview(proposed, 'accepted', '  ', now)).toThrow('review note')
    const accepted = recordReview(proposed, 'accepted', 'Read both excerpts; concentration rose.', now)
    expect(accepted.revisions).toEqual([earlier, later])
    expect(initial.revisions).toEqual([earlier])
    expect(accepted.reviews[0]).toMatchObject({ interpretation: 'Revisit concentration.', candidate: later })
    expect(accepted.status).toBe('reviewed')
  })
  it('keeps the prior source with the rejected candidate and reason in decision history', () => {
    const kept = recordReview(proposeSource(initial, later), 'kept', 'Use this as dated historical evidence.', now)
    expect(kept.revisions).toEqual([earlier])
    expect(kept.proposal).toBeNull()
    expect(kept.reviews[0].candidate).toEqual(later)
  })
  it('interpretation edits reopen review while leaving the recorded interpretation intact', () => {
    const reviewed = recordReview(updateInterpretation(initial, 'Original interpretation'), 'reviewed', 'Checked original.', now)
    const edited = updateInterpretation(reviewed, 'New interpretation')
    expect(edited.status).toBe('unreviewed')
    expect(edited.reviews[0].interpretation).toBe('Original interpretation')
    expect(updateInterpretation(proposeSource(edited, later), 'Further edit').status).toBe('review-needed')
  })
  it.each([{ companyId: 999 }, { form: '10-Q' }, { fictional: false }, { accession: earlier.accession }, { reportDate: earlier.reportDate }, { filedDate: earlier.filedDate }])('rejects incomparable proposal %j', (patch) => {
    expect(() => proposeSource(initial, { ...later, ...patch })).toThrow('same company and form')
  })
  it('does not allow generic review to skip a pending source decision', () => {
    expect(() => recordReview(proposeSource(initial, later), 'reviewed', 'Checked', now)).toThrow('explicitly')
    expect(() => recordReview(initial, 'accepted', 'Checked', now)).toThrow('explicitly')
  })
  it('exports pending proposals, revisions, notes and review states without active Markdown or HTML', () => {
    const text = '<img src=x onerror=alert(1)>\n# forged\n[click](javascript:alert(1))'
    const entry = updateInterpretation(recordReview(proposeSource(initial, later), 'kept', text, now), text)
    const markdown = exportEvidence([entry], 'markdown', now)
    expect(markdown).toContain('&lt;img')
    expect(markdown).toContain('\\# forged')
    expect(markdown).toContain('\\[click\\]\\(javascript:alert\\(1\\)\\)')
    expect(markdown).not.toContain('<img')
    expect(markdown).toContain('FICTIONAL EXAMPLE')
    expect(markdown).toContain('FICTIONAL\\-0000\\-0002')
    expect(JSON.parse(exportEvidence([proposeSource(entry, later)], 'json', now))).toMatchObject({ schemaVersion: 1, entries: [{ status: 'review-needed', proposal: asServed(later), revisions: [asServed(earlier)], reviews: [{ note: text }] }] })
  })
})
