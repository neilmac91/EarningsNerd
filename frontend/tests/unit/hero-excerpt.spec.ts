import { describe, it, expect } from 'vitest'
import { toExcerpt } from '@/lib/serverApi'

// The homepage hero (serverApi.fetchExampleData) regex-strips the stored business_overview and is
// coupled to its LEADING shape. T2 changed that shape (derived markdown now leads "## Executive
// Assessment", new block order, GFM tables), so this pins that the excerpt still leads with the
// headline sentence — not a section heading or tone meta-commentary — closing the last untested
// consumer of business_overview. A future reordering of the exec section that broke the hero would
// now fail here instead of shipping green.
describe('toExcerpt (homepage hero shape)', () => {
  it('leads with the headline sentence of the derived summary markdown', () => {
    const derived = [
      '## Executive Assessment',
      '',
      'Revenue surged 85% to $81.6B on data-center demand.',
      '',
      '- Gross margin expanded to 74.9%',
      '',
      '## Financial Highlights',
      '',
      '| Metric | Current Period | Prior Period |',
      '| --- | --- | --- |',
      '| Revenue | $81.6B | $44.1B |',
    ].join('\n')

    const excerpt = toExcerpt(derived)

    expect(excerpt.startsWith('Revenue surged 85% to $81.6B on data-center demand.')).toBe(true)
    // No section-heading text and no tone meta-commentary leaks into the front-page hero.
    expect(excerpt).not.toMatch(/Executive Assessment|Financial Highlights/)
    expect(excerpt.toLowerCase()).not.toContain('tone was')
  })
})
