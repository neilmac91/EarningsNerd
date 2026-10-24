import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchExampleData, heroFigure } from '@/lib/serverApi'

vi.mock('@/lib/featureFlags', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/featureFlags')>()),
  EXAMPLE_FILING_ID: '3',
}))

// The hero reads the summary's normalized facts, which read-time enrichment rewrites when it swaps in the filed
// figure (provenance_service._refresh_normalized). The server writes that figure whole, so the hero compacts it as the
// table does rather than show fifteen digits beside the summary's own "$416.2B".
describe('heroFigure', () => {
  it('compacts a figure the server wrote whole, keeping its currency', () => {
    expect(heroFigure('$133,050,000,000')).toBe('$133.1B')
    expect(heroFigure('EUR 30,600,000,000')).toBe('EUR 30.6B')
    expect(heroFigure('EUR -1,250,000,000')).toBe('-EUR 1.3B')
  })

  it('shows the summary’s own figures as written', () => {
    for (const written of ['$416.2B', '$416,161M', '€32.7B', '$7.46', '46.2%', 'Not disclosed']) {
      expect(heroFigure(written)).toBe(written)
    }
  })
})

describe('the live hero’s figures', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('compacts a filed figure the summary payload carries, beside one the summary wrote', async () => {
    const folder = 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/'
    vi.stubGlobal('fetch', vi.fn(async (url: string) => ({
      ok: true,
      json: async () => url.endsWith('/api/filings/3')
        ? { id: 3, company: { ticker: 'AAPL', name: 'Apple Inc.' }, filing_type: '10-K', filing_date: '2025-10-31', sec_url: folder, document_url: `${folder}aapl-20250927.htm` }
        : {
          business_overview: 'Net sales rose on iPhone and Services.',
          financial_highlights: {
            normalized: {
              metrics: [
                { metric: 'Total net sales', currentPeriod: '$416,161,000,000', deltaPercent: 6.4 },
                { metric: 'Net income', currentPeriod: '$112.0B', deltaPercent: 19.5 },
              ],
            },
          },
        },
    })))
    const example = await fetchExampleData()
    expect(example?.metrics.map(({ label, value }) => `${label} ${value}`)).toEqual(['Revenue $416.2B', 'Net income $112.0B'])
  })
})
