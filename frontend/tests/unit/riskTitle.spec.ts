import { describe, expect, it } from 'vitest'
import { deriveRiskTitle, excerptHeadings, MAX_TITLE_CHARS } from '@/features/summaries/lib/riskTitle'

// Risk cards need distinct headings (five "Risk Factor" <h4>s is a heading list nobody can scan).
describe('deriveRiskTitle', () => {
  it('returns an authored title verbatim', () => {
    expect(deriveRiskTitle({ title: 'Supply concentration', summary: 'Anything else.' }, 0)).toBe('Supply concentration')
    expect(deriveRiskTitle({ title: '  Padded  ', summary: 'x' }, 0)).toBe('Padded')
  })

  it('derives the first clause of the summary when no title is present', () => {
    expect(
      deriveRiskTitle(
        { summary: 'Customer concentration remains high. Two customers were 40% of revenue.' },
        0,
      ),
    ).toBe('Customer concentration remains high')
    expect(deriveRiskTitle({ summary: 'FX headwinds persist; the euro weakened 8%.' }, 0)).toBe('FX headwinds persist')
    expect(deriveRiskTitle({ summary: 'Litigation exposure: a class action was certified.' }, 0)).toBe('Litigation exposure')
    expect(deriveRiskTitle({ summary: 'Debt maturities loom — $2B due in 2027.' }, 0)).toBe('Debt maturities loom')
  })

  it('does not split inside numbers or abbreviations', () => {
    expect(deriveRiskTitle({ summary: 'Margins fell 3.5% on U.S. tariffs. More text.' }, 0)).toBe(
      'Margins fell 3.5% on U.S. tariffs',
    )
    expect(deriveRiskTitle({ summary: 'Apple Inc. faces new tariff exposure. Details follow.' }, 0)).toBe(
      'Apple Inc. faces new tariff exposure',
    )
    expect(deriveRiskTitle({ summary: 'Margins compressed in Q1 vs. Q2 on mix. More.' }, 0)).toBe(
      'Margins compressed in Q1 vs. Q2 on mix',
    )
    expect(deriveRiskTitle({ summary: 'Concentration risks incl. supply chain remain. More.' }, 0)).toBe(
      'Concentration risks incl. supply chain remain',
    )
    expect(deriveRiskTitle({ summary: 'Sales fell approx. ten percent. More.' }, 0)).toBe(
      'Sales fell approx. ten percent',
    )
  })

  it('treats a period followed by a lowercase word or a comma as not ending the sentence', () => {
    expect(deriveRiskTitle({ summary: 'Costs rose 5 pct. year over year. More.' }, 0)).toBe(
      'Costs rose 5 pct. year over year',
    )
    expect(deriveRiskTitle({ summary: 'Acme Corp., a subsidiary, lost its license. More.' }, 0)).toBe(
      'Acme Corp., a subsidiary, lost its license',
    )
    // A capitalised next word after a plain period is still a sentence end.
    expect(deriveRiskTitle({ summary: 'Demand softened. Management cut guidance.' }, 0)).toBe('Demand softened')
  })

  it('falls back to the description when the summary is empty, and sentence-cases the result', () => {
    expect(deriveRiskTitle({ summary: '', description: 'regulatory scrutiny is increasing. Details follow.' }, 0)).toBe(
      'Regulatory scrutiny is increasing',
    )
  })

  it('keeps a punctuation-free summary whole', () => {
    expect(deriveRiskTitle({ summary: 'Dependence on a single foundry partner' }, 2)).toBe(
      'Dependence on a single foundry partner',
    )
  })

  it('caps a long clause on a word boundary with an ellipsis', () => {
    const long = 'The company depends on continued access to advanced semiconductor manufacturing capacity from a small number of foundry partners located in a single region'
    const title = deriveRiskTitle({ summary: long }, 0)
    expect(title.length).toBeLessThanOrEqual(MAX_TITLE_CHARS + 1)
    expect(title.endsWith('…')).toBe(true)
    // Cut on a word boundary: the character before the ellipsis is a full word's end, not a mid-word cut.
    expect(long.startsWith(title.slice(0, -1))).toBe(true)
    expect(long.charAt(title.length - 1)).toBe(' ')
  })

  it('falls back to an indexed "Risk n" when nothing usable remains', () => {
    expect(deriveRiskTitle({}, 0)).toBe('Risk 1')
    expect(deriveRiskTitle({ summary: '   ' }, 4)).toBe('Risk 5')
    expect(deriveRiskTitle({ summary: '...', description: '—' }, 1)).toBe('Risk 2')
  })

  it('collapses internal whitespace', () => {
    expect(deriveRiskTitle({ summary: 'Supply   chain\n disruption remains elevated.' }, 0)).toBe(
      'Supply chain disruption remains elevated',
    )
  })
})

// Source-first risk rows (2026-10 critique P-03): the server labels every projected risk "Filing
// excerpt", so each row is headed by its own verbatim excerpt's opening clause.
describe('excerptHeadings', () => {
  it('heads each excerpt with its opening clause', () => {
    expect(
      excerptHeadings([
        'Substantially all of the Company’s manufacturing is performed by outsourcing partners. More text.',
        'Currency movements reduce reported revenue; the euro weakened.',
      ]),
    ).toEqual([
      // Capped at MAX_TITLE_CHARS on a word boundary, like any derived title.
      'Substantially all of the Company’s manufacturing is performed by outsourcing…',
      'Currency movements reduce reported revenue',
    ])
  })

  it('drops the quote marks a verbatim span opens or closes with, never brackets', () => {
    expect(excerptHeadings(['“Supply chain constraints persisted through Q3.”'])).toEqual([
      'Supply chain constraints persisted through Q3',
    ])
    expect(excerptHeadings(['"Exposure to foreign exchange (FX)"'])).toEqual(['Exposure to foreign exchange (FX)'])
  })

  it('keeps every heading unique so the accessibility tree never repeats one', () => {
    expect(
      excerptHeadings(['Item 1A: first quote.', 'Item 1A: second quote.', 'Item 1A: third quote.']),
    ).toEqual(['Item 1A', 'Item 1A (2)', 'Item 1A (3)'])
  })

  it('stays unique when a clause itself ends in an occurrence number', () => {
    expect(excerptHeadings(['Foo bar (2). One.', 'Foo bar. Two.', 'Foo bar. Three.'])).toEqual([
      'Foo bar (2)',
      'Foo bar',
      'Foo bar (3)',
    ])
  })

  it('keeps the filing’s own casing: the heading is its words, not a recased copy', () => {
    expect(excerptHeadings(['iPhone net sales depend on new models. More.', 'eBay-style marketplaces compete.'])).toEqual([
      'iPhone net sales depend on new models',
      'eBay-style marketplaces compete',
    ])
  })

  it('falls back to the positional label for an excerpt with nothing to read', () => {
    expect(excerptHeadings(['…', 'Real text.'])).toEqual(['Risk 1', 'Real text'])
  })
})

