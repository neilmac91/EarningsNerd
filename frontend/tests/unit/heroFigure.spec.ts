import { describe, expect, it } from 'vitest'
import { heroFigure } from '@/lib/serverApi'

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
