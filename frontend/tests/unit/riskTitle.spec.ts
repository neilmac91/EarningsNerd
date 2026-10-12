import { describe, expect, it } from 'vitest'
import { excerptHeadings } from '@/features/summaries/lib/riskTitle'

// Source-first risk rows (2026-10 critique P-03, founder option b): the server labels every projected
// risk "Filing excerpt", so each row is headed by deriveRiskHeadline of its own verbatim excerpt. The
// cut itself is pinned in riskHeadline.spec.ts; these pin what excerptHeadings adds around it: one
// enclosing quote pair, the filing's whitespace, the positional fallback and uniqueness.
describe('excerptHeadings', () => {
  it('drops one enclosing pair of quote marks, and only a pair with no other such mark inside', () => {
    expect(
      excerptHeadings([
        '“Supply chain constraints persisted through Q3.”',
        '"Exposure to foreign exchange (FX) remains high."',
        '‘Demand for our products weakened in the quarter.’',
      ]),
    ).toEqual([
      'Supply chain constraints persisted through Q3',
      'Exposure to foreign exchange (FX) remains high',
      'Demand for our products weakened in the quarter',
    ])
    // A mark inside, or no matching close: every byte stays.
    expect(
      excerptHeadings(['“Supply constraints persisted” and “demand weakened”', '“Supply chain constraints persisted through Q3.']),
    ).toEqual(['“Supply constraints persisted” and “demand weakened”', '“Supply chain constraints persisted through Q3.'])
  })

  it('keeps the filing’s whitespace: a no-break space stays one', () => {
    expect(excerptHeadings(['Tax years ended September 27, 2025 remain under audit.'])).toEqual([
      'Tax years ended September 27, 2025 remain under audit',
    ])
  })

  it('falls back to the positional "Risk n" for an excerpt with nothing to read', () => {
    expect(excerptHeadings(['…', 'Tariffs could hurt margins.'])).toEqual(['Risk 1', 'Tariffs could hurt margins'])
  })

  it('keeps every heading unique so the accessibility tree never repeats one', () => {
    // Two spans whose first 100 characters match cut to the same heading.
    const shared =
      'The Company depends on continued access to advanced semiconductor manufacturing capacity from a small number of foundry partners'
    expect(excerptHeadings([`${shared} in Asia.`, `${shared} in Europe.`, `${shared} in America.`])).toEqual([
      'The Company depends on continued access to advanced semiconductor manufacturing capacity…',
      'The Company depends on continued access to advanced semiconductor manufacturing capacity… (2)',
      'The Company depends on continued access to advanced semiconductor manufacturing capacity… (3)',
    ])
    // The first free occurrence number, when a heading itself ends in one.
    expect(
      excerptHeadings(['Tariffs could hurt margins (2)', 'Tariffs could hurt margins.', 'Tariffs could hurt margins.']),
    ).toEqual(['Tariffs could hurt margins (2)', 'Tariffs could hurt margins', 'Tariffs could hurt margins (3)'])
  })
})
