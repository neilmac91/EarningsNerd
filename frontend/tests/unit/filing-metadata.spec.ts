import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Filing } from '@/features/filings/api/filings-api'
import type { Summary } from '@/features/summaries/api/summaries-api'

/**
 * The filing page's metadata follows what the page shows (the shared readiness rule): a summary body
 * is indexable and gives the description, while placeholder filler or a stored failure, which the page
 * shows as its error card, keeps the page out of the index and never lends its text to the snippet.
 */

const server = vi.hoisted(() => ({ fetchFilingServer: vi.fn(), fetchFilingSummaryServer: vi.fn() }))
vi.mock('@/lib/serverApi', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/serverApi')>()),
  fetchFilingServer: server.fetchFilingServer,
  fetchFilingSummaryServer: server.fetchFilingSummaryServer,
}))
vi.mock('@/app/filing/[id]/page-client', () => ({ default: () => null }))

const FILING = {
  id: 42,
  filing_type: '10-K',
  filing_date: '2025-10-31T00:00:00+00:00',
  company: { id: 1, ticker: 'AAPL', name: 'Apple Inc.' },
} as Filing

async function metadataFor(stored: Partial<Summary> & { raw_summary?: unknown }) {
  server.fetchFilingServer.mockResolvedValue({ status: 'ok', data: FILING })
  server.fetchFilingSummaryServer.mockResolvedValue({ status: 'ok', data: { id: 9, filing_id: 42, ...stored } })
  const { generateMetadata } = await import('@/app/filing/[id]/page')
  return generateMetadata({ params: Promise.resolve({ id: '42' }) })
}

afterEach(() => {
  vi.clearAllMocks()
})

describe('filing page metadata', () => {
  it.each([
    ['a summary the page shows', 'Apple designs devices and services.'],
    ['prose that mentions generating summaries', 'Apple reworked its revenue-generating summary reports.'],
  ])('indexes %s, and describes the page with its opening', async (_, body) => {
    const meta = await metadataFor({ business_overview: body })
    expect(meta.robots).toBeUndefined()
    expect(meta.description).toContain(body)
  })

  it.each([
    ['placeholder filler', { business_overview: 'Summary generation requires OpenAI API key. Please configure OPENAI_API_KEY in your .env file.' }],
    ['a stored failure', { business_overview: 'Apple designs devices and services.', raw_summary: { writer_error: 'timeout' } }],
    ['a run in progress', { business_overview: 'Generating summary...' }],
  ])('keeps %s out of the index and out of the description', async (_, stored) => {
    const meta = await metadataFor(stored)
    expect(meta.robots).toEqual({ index: false, follow: true })
    expect(meta.description).toContain('Read the AI summary')
    expect(meta.description).not.toMatch(/OPENAI_API_KEY|Apple designs|Generating summary/)
  })
})
