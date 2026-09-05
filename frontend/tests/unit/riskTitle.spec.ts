import { describe, expect, it } from 'vitest'
import { deriveRiskTitle, MAX_TITLE_CHARS } from '@/features/summaries/lib/riskTitle'

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
