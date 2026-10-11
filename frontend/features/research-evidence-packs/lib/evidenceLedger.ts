import type { Filing } from '@/features/filings/api/filings-api'
import type { FilingContent } from '@/features/filings/api/filing-content-api'
import { originalDocumentUrl } from '@/features/filings/lib/originalDocumentUrl'

export interface SourceIdentity {
  readonly filingId: number
  readonly companyId: number
  readonly companyName: string
  readonly ticker: string
  readonly form: string
  readonly accession: string
  readonly reportDate: string
  readonly filedDate: string
  readonly originalUrl: string | null
  readonly fictional: boolean
}
export interface SourceDocument {
  readonly identity: SourceIdentity
  readonly paragraphs: readonly string[]
}
export interface SourceSnapshot extends SourceIdentity {
  readonly quote: string
  readonly paragraph: number
  readonly capturedAt: string
}
export interface ReviewRecord {
  readonly decision: 'reviewed' | 'accepted' | 'kept'
  readonly note: string
  readonly interpretation: string
  readonly candidate: SourceSnapshot | null
  readonly reviewedAt: string
}
export interface EvidenceEntry {
  readonly id: number
  readonly revisions: readonly SourceSnapshot[]
  readonly interpretation: string
  readonly status: 'unreviewed' | 'review-needed' | 'reviewed'
  readonly proposal: SourceSnapshot | null
  readonly reviews: readonly ReviewRecord[]
}

export function parseFilingId(value: string): number | null {
  const id = Number(value)
  return /^[1-9]\d*$/.test(value.trim()) && Number.isSafeInteger(id) ? id : null
}

function calendarDate(value: unknown): string | null {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}(?:T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d{1,6})?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)?)?$/.test(value)) return null
  const day = value.slice(0, 10)
  const date = new Date(`${day}T00:00:00Z`)
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === day ? day : null
}

/** Only the cached filing APIs supply real source identities. No pasted or imported verification. */
export function sourceIdentity(filing: Filing, expectedId: number): SourceIdentity {
  const reportDate = calendarDate(filing?.report_date)
  const filedDate = calendarDate(filing?.filing_date)
  if (filing?.id !== expectedId || !Number.isSafeInteger(filing.company?.id) || filing.company!.id <= 0 ||
      typeof filing.company?.name !== 'string' || !filing.company.name.trim() ||
      typeof filing.company?.ticker !== 'string' || !filing.company.ticker.trim() ||
      !['10-K', '10-Q'].includes(filing.filing_type) ||
      typeof filing.accession_number !== 'string' || !/^\d{10}-\d{2}-\d{6}$/.test(filing.accession_number) ||
      !reportDate || !filedDate || reportDate > filedDate) {
    throw new Error('The filing needs matching identity, an original 10-K or 10-Q, accession and valid dates.')
  }
  const originalUrl = originalDocumentUrl(filing)
  let url: URL
  try { url = new URL(originalUrl ?? '') } catch { throw new Error('A valid SEC original link is required.') }
  if (url.protocol !== 'https:' || !['www.sec.gov', 'sec.gov'].includes(url.hostname) ||
      !new RegExp(`^/Archives/edgar/data/\\d+/${filing.accession_number.replace(/-/g, '')}/`).test(url.pathname) || url.username || url.password || url.port) {
    throw new Error('A valid SEC original link is required.')
  }
  return Object.freeze({ filingId: expectedId, companyId: filing.company!.id,
    companyName: filing.company!.name, ticker: filing.company!.ticker, form: filing.filing_type,
    accession: filing.accession_number, reportDate, filedDate, originalUrl: url.href, fictional: false })
}

export function sourceDocument(identity: SourceIdentity, content: FilingContent): SourceDocument {
  if (content.filingId !== identity.filingId) throw new Error('The returned text does not match the selected filing.')
  if (!content.hasContent || typeof content.markdownContent !== 'string' || !content.markdownContent.trim()) {
    throw new Error('Cached text is unavailable. No quote or source comparison can be created.')
  }
  if (content.markdownContent.length > 120_000) throw new Error('This prototype accepts at most 120,000 characters per filing; nothing was truncated.')
  const paragraphs = content.markdownContent.split(/\r?\n\s*\r?\n/).map((text) => text.trim()).filter(Boolean)
  if (paragraphs.length > 400) throw new Error('This prototype accepts at most 400 paragraphs; nothing was truncated.')
  return Object.freeze({ identity, paragraphs: Object.freeze(paragraphs) })
}

export function captureSource(document: SourceDocument, paragraph: number, capturedAt: string): SourceSnapshot {
  const quote = document.paragraphs[paragraph]
  if (!Number.isInteger(paragraph) || !quote) throw new Error('Select a paragraph from the loaded filing.')
  return Object.freeze({ ...document.identity, quote, paragraph: paragraph + 1, capturedAt })
}

export function createEntry(id: number, source: SourceSnapshot): EvidenceEntry {
  return { id, revisions: [source], interpretation: '', status: 'unreviewed', proposal: null, reviews: [] }
}

export function updateInterpretation(entry: EvidenceEntry, interpretation: string): EvidenceEntry {
  if (entry.interpretation === interpretation) return entry
  return { ...entry, interpretation, status: entry.proposal ? 'review-needed' : 'unreviewed' }
}

export function proposeSource(entry: EvidenceEntry, candidate: SourceSnapshot): EvidenceEntry {
  const current = entry.revisions[entry.revisions.length - 1]
  if (current.companyId !== candidate.companyId || current.form !== candidate.form ||
      current.fictional !== candidate.fictional || current.accession === candidate.accession ||
      current.reportDate >= candidate.reportDate || current.filedDate >= candidate.filedDate) {
    throw new Error('Choose a later filing of the same company and form. Fictional and real sources cannot be mixed.')
  }
  return { ...entry, proposal: candidate, status: 'review-needed' }
}

export function recordReview(entry: EvidenceEntry, decision: ReviewRecord['decision'], note: string, reviewedAt: string): EvidenceEntry {
  if (!note.trim()) throw new Error('Add a review note explaining your decision.')
  if ((decision === 'reviewed') !== (entry.proposal === null)) throw new Error('Review the proposed source explicitly before proceeding.')
  const record: ReviewRecord = { decision, note: note.trim(), interpretation: entry.interpretation, candidate: entry.proposal, reviewedAt }
  return { ...entry, revisions: decision === 'accepted' ? [...entry.revisions, entry.proposal!] : entry.revisions,
    proposal: null, status: 'reviewed', reviews: [...entry.reviews, record] }
}

/** Escape untrusted text as text, not active HTML, links, images or document structure. */
function markdownText(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/([\\`*_{}\[\]()#!|+\-.])/g, '\\$1')
}
function sourceMarkdown(source: SourceSnapshot): string {
  return [
    `${markdownText(source.companyName)} (${markdownText(source.ticker)}) · ${source.form} · period ${source.reportDate} · filed ${source.filedDate}`,
    `Accession: ${markdownText(source.accession)} · cached paragraph ${source.paragraph} · captured ${source.capturedAt}`,
    source.fictional ? '**FICTIONAL EXAMPLE — invented source, not an SEC filing.**' : `Original: <${source.originalUrl}>`,
    source.quote.split('\n').map((line) => `> ${markdownText(line)}`).join('\n'),
  ].join('\n\n')
}
export function exportEvidence(entries: readonly EvidenceEntry[], format: 'json' | 'markdown', exportedAt: string): string {
  const disclosure = 'Local prototype. User review records a decision, not verified truth or investment advice. Cached text coverage is unverified. A quote match does not establish that an interpretation is supported. Recheck sources before reuse.'
  if (format === 'json') return JSON.stringify({ schemaVersion: 1, exportedAt, disclosure, entries }, null, 2)
  return ['# Research evidence pack', `Exported: ${exportedAt}`, disclosure, ...entries.map((entry) => [
    `## Evidence ${entry.id} — ${entry.status}`, `### My interpretation\n\n${entry.interpretation.split('\n').map((line) => markdownText(line)).join('  \n') || '(No interpretation recorded)'}`,
    ...entry.revisions.map((source, index) => `### Source revision ${index + 1}\n\n${sourceMarkdown(source)}`),
    ...(entry.proposal ? [`### Pending source proposal — review needed\n\n${sourceMarkdown(entry.proposal)}`] : []),
    ...entry.reviews.map((review) => `### Review: ${review.decision} · ${review.reviewedAt}\n\n${markdownText(review.note)}\n\nInterpretation at review: ${markdownText(review.interpretation)}${review.candidate ? `\n\nCandidate considered:\n\n${sourceMarkdown(review.candidate)}` : ''}`),
  ].join('\n\n'))].join('\n\n') + '\n'
}
