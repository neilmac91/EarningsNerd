import { captureSource, createEntry, type SourceDocument } from '../lib/evidenceLedger'

const identity = { filingId: 1, companyId: 1, companyName: 'Harbor Vale Instruments', ticker: 'FICTIONAL', form: '10-K', accession: 'FICTIONAL-2025', reportDate: '2024-12-31', filedDate: '2025-02-10', originalUrl: null, fictional: true }
export const earlierExample: SourceDocument = {
  identity,
  paragraphs: ['Our three largest customers accounted for 42% of revenue during the year.', 'We manufacture precision sensors for industrial customers.'],
}
export const laterExample: SourceDocument = {
  identity: { ...identity, filingId: 2, accession: 'FICTIONAL-2026', reportDate: '2025-12-31', filedDate: '2026-02-10' },
  paragraphs: ['Our three largest customers accounted for 57% of revenue during the year.', 'We manufacture precision sensors for industrial customers.'],
}
export function exampleLedger() {
  return [{ ...createEntry(1, captureSource(earlierExample, 0, '2026-10-11T00:00:00.000Z')),
    interpretation: 'Customer concentration is a question to revisit next quarter.' }]
}
