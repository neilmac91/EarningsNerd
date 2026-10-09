import { describe, expect, it } from 'vitest'
import {
  RISK_HEADLINE_ELLIPSIS,
  RISK_HEADLINE_MAX_CHARS,
  deriveRiskHeadline,
  riskHeadlineFallback,
} from '@/features/summaries/lib/riskHeadline'

// A risk card's heading is a verbatim prefix of its own verified filing excerpt (founder option b):
// never the model's label, never rewritten. These pin the rule on the real spans it was designed
// against and on the edge cases a naive first-clause cut gets wrong.

/** The four source-verified risk spans of the production filing-3 summary (Apple FY2025 10-K). */
const FILING_3: Array<[string, string]> = [
  [
    'Tariffs and other measures that are applied to the Company’s products or their components can have a material adverse impact on the Company’s business, results of operations and financial condition, including impacting the Company’s supply chain, the availability of rare earths and other raw materials and components, pricing and gross margin.',
    'Tariffs and other measures that are applied to the Company’s products or their components…',
  ],
  [
    // A first-comma cut ends inside the country list ("... primarily in China mainland").
    'Substantially all of the Company’s hardware products are manufactured by outsourcing partners that are located primarily in China mainland, India, Japan, South Korea, Taiwan and Vietnam.',
    'Substantially all of the Company’s hardware products are manufactured by outsourcing partners…',
  ],
  [
    // A first-comma cut ends on the leading date ("As of September 27"). The filing's own no-break
    // space after "September" is kept: verbatim means byte for byte, not normalised.
    'As of September\u00a027, 2025, the total amount of gross unrecognized tax benefits was $23.2 billion, of which $10.6 billion, if recognized, would impact the Company’s effective tax rate.',
    'As of September\u00a027, 2025, the total amount of gross unrecognized tax benefits was $23.2 billion…',
  ],
  [
    // A first-comma cut ends on the leading qualifier ("Regardless of the merit of particular claims").
    'Regardless of the merit of particular claims, defending against litigation or responding to government investigations can be expensive, time-consuming and disruptive to the Company’s operations.',
    'Regardless of the merit of particular claims, defending against litigation or responding…',
  ],
]

/** Risk spans from the backend's retained-output fixtures (reconciliation_directions, tax_rate_comparison). */
const BACKEND_FIXTURES: Array<[string, string]> = [
  [
    'Inventory purchase obligations as of June 30, 2026 were approximately $63.1 million.',
    'Inventory purchase obligations as of June 30, 2026 were approximately $63.1 million',
  ],
  [
    'Tariffs have increased our product costs, negatively impacting gross margin for the three months ended June 30, 2026.',
    'Tariffs have increased our product costs, negatively impacting gross margin for the three months…',
  ],
  [
    // The cap falls after "on July 7"; the headline never ends inside a date.
    'Plaintiffs filed an appeal from that dismissal and oral argument in the appeal took place on July 7, 2026. The appeal is now under submission.',
    'Plaintiffs filed an appeal from that dismissal and oral argument in the appeal took place…',
  ],
  [
    'On June 23, 2026, CBP issued a withhold release order (“WRO”) against certain garments produced by our Jordanian manufacturing partner. That manufacturer accounted for approximately one-third of our production.',
    'On June 23, 2026, CBP issued a withhold release order (“WRO”) against certain garments produced…',
  ],
]

/** Risk spans from the committed eval baselines that exercise one rule each. */
const EVAL_SPANS: Array<[string, string, string]> = [
  [
    'a figure is never split from its unit',
    'On August 2, 2024, the Tax Court entered a decision reflecting additional federal income tax of $2.7 billion for the 2007 through 2009 tax years. With applicable interest, the total liability for the 2007 through 2009 tax years resulting from the Tax Court’s decision is $6.0 billion.',
    'On August 2, 2024, the Tax Court entered a decision reflecting additional federal income tax…',
  ],
  [
    'a capitalised name is never split',
    'We are highly dependent on the services of Elon Musk, Technoking of Tesla and our Chief Executive Officer. Although Mr. Musk spends significant time with Tesla and is highly active in our management, he does not devote his full time and attention to Tesla.',
    'We are highly dependent on the services of Elon Musk, Technoking of Tesla…',
  ],
  [
    'a short first sentence is the whole headline',
    'Tax years 2019-2022 are under audit. Tax years 2023-2026 are open but not under audit. All other tax years are closed.',
    'Tax years 2019-2022 are under audit',
  ],
  [
    'a colon lead-in keeps its lead-in word and takes an ellipsis',
    'Higher interest rates could also result in: •fewer originations of commercial and residential real estate loans •losses on underwriting exposures or increases in client-specific downgrades •higher funding costs.',
    'Higher interest rates could also result in…',
  ],
  [
    'a span that starts mid-sentence keeps its own casing',
    'the EU’s AI Act may increase costs or impact the provision or operation of our AI models and services in the European market.',
    'the EU’s AI Act may increase costs or impact the provision or operation of our AI models…',
  ],
  [
    'an abbreviation period is not a sentence end',
    'As previously disclosed, in September 2025 and November 2025, fires at a Novelis Inc. plant in New York disrupted operations at the facility. Novelis is a major aluminum supplier to Ford.',
    'As previously disclosed, in September 2025 and November 2025, fires at a Novelis Inc. plant…',
  ],
]

const REAL = [...FILING_3, ...BACKEND_FIXTURES, ...EVAL_SPANS.map(([, excerpt, headline]) => [excerpt, headline] as [string, string])]

/** The headline without its ellipsis must open the excerpt exactly. */
const isVerbatimPrefix = (excerpt: string, headline: string): boolean =>
  excerpt.trim().startsWith(headline.endsWith(RISK_HEADLINE_ELLIPSIS) ? headline.slice(0, -1) : headline)

describe('deriveRiskHeadline', () => {
  it.each(FILING_3)('titles the production filing-3 span %#', (excerpt, headline) => {
    expect(deriveRiskHeadline(excerpt, 0)).toBe(headline)
  })

  it.each(BACKEND_FIXTURES)('titles the backend fixture span %#', (excerpt, headline) => {
    expect(deriveRiskHeadline(excerpt, 0)).toBe(headline)
  })

  it.each(EVAL_SPANS)('%s', (_rule, excerpt, headline) => {
    expect(deriveRiskHeadline(excerpt, 0)).toBe(headline)
  })

  it('is a verbatim prefix of every real span, within the cap, and deterministic', () => {
    for (const [excerpt] of REAL) {
      const headline = deriveRiskHeadline(excerpt, 3)
      expect(isVerbatimPrefix(excerpt, headline), headline).toBe(true)
      expect(headline.length).toBeLessThanOrEqual(RISK_HEADLINE_MAX_CHARS + RISK_HEADLINE_ELLIPSIS.length)
      expect(deriveRiskHeadline(excerpt, 3)).toBe(headline)
    }
  })

  it('falls back to the positional title when the excerpt is missing or too short', () => {
    expect(deriveRiskHeadline(undefined, 0)).toBe('Filing excerpt 1')
    expect(deriveRiskHeadline(null, 1)).toBe('Filing excerpt 2')
    expect(deriveRiskHeadline('', 2)).toBe('Filing excerpt 3')
    expect(deriveRiskHeadline('   \n ', 3)).toBe('Filing excerpt 4')
    expect(deriveRiskHeadline('Tariffs.', 4)).toBe('Filing excerpt 5')
    expect(deriveRiskHeadline('Supply risk', 5)).toBe('Filing excerpt 6')
    expect(deriveRiskHeadline('… — ;', 6)).toBe('Filing excerpt 7')
    expect(riskHeadlineFallback(7)).toBe('Filing excerpt 8')
  })

  it('keeps a short excerpt whole, with or without punctuation', () => {
    expect(deriveRiskHeadline('Margins may compress', 0)).toBe('Margins may compress')
    expect(deriveRiskHeadline('Dependence on a single foundry partner', 0)).toBe('Dependence on a single foundry partner')
    expect(deriveRiskHeadline('We face credit risks.', 0)).toBe('We face credit risks')
  })

  it('skips a first sentence too short to title the card rather than ending on it', () => {
    expect(deriveRiskHeadline('Risks. Tariffs could hurt margins this year.', 0)).toBe('Risks. Tariffs could hurt margins this year')
    expect(deriveRiskHeadline('Demand softened! Management cut guidance.', 0)).toBe('Demand softened! Management cut guidance')
    expect(deriveRiskHeadline('Could tariffs rise again? Management expects so.', 0)).toBe('Could tariffs rise again?')
  })

  it('cuts at the first strong clause boundary only when it leaves a meaningful clause', () => {
    expect(deriveRiskHeadline('Supply is concentrated in one region; a disruption there would halt production.', 0)).toBe(
      'Supply is concentrated in one region',
    )
    expect(deriveRiskHeadline('Revenue concentration remains high – two customers accounted for 40% of net sales.', 0)).toBe(
      'Revenue concentration remains high',
    )
    // "Item 1A" is too short to be the clause: the sentence stays whole, its quotation closed.
    expect(deriveRiskHeadline('Item 1A: “substantially dependent on TSMC.”', 0)).toBe('Item 1A: “substantially dependent on TSMC.”')
    // A pair of dashes is a parenthetical: the later dash is not a clause boundary.
    expect(deriveRiskHeadline('Supply chain constraints — particularly in memory — persisted through the quarter.', 0)).toBe(
      'Supply chain constraints — particularly in memory — persisted through the quarter',
    )
  })

  it('does not end a sentence inside a number, an initialism or an abbreviation', () => {
    expect(deriveRiskHeadline('Margins fell 3.5% on U.S. tariffs. More text.', 0)).toBe('Margins fell 3.5% on U.S. tariffs')
    expect(deriveRiskHeadline('Apple Inc. faces new tariff exposure. Details follow.', 0)).toBe('Apple Inc. faces new tariff exposure')
    expect(deriveRiskHeadline('Under ASU No. 2023-07 the Company discloses significant segment expenses. More.', 0)).toBe(
      'Under ASU No. 2023-07 the Company discloses significant segment expenses',
    )
    expect(deriveRiskHeadline('Acme Corp., a subsidiary, lost its license. More.', 0)).toBe('Acme Corp., a subsidiary, lost its license')
  })

  it('caps a long clause on a word boundary, never on a function word, with an ellipsis', () => {
    const long =
      'The Company depends on continued access to advanced semiconductor manufacturing capacity from a small number of foundry partners located in a single region'
    const headline = deriveRiskHeadline(long, 0)
    expect(headline).toBe('The Company depends on continued access to advanced semiconductor manufacturing capacity…')
    expect(isVerbatimPrefix(long, headline)).toBe(true)
    // The character after the cut is a space: a whole word, not a mid-word cut.
    expect(long.charAt(headline.length - 1)).toBe(' ')
  })

  it('does not leave a parenthesis or a quotation open', () => {
    expect(
      deriveRiskHeadline(
        'The Company relies on a single contract manufacturer for its flagship devices (the “Manufacturer”, which assembles substantially all units) and on a small number of suppliers.',
        0,
      ),
    ).toBe('The Company relies on a single contract manufacturer for its flagship devices…')
  })

  it('keeps the excerpt’s own whitespace and casing (verbatim, not normalised)', () => {
    expect(deriveRiskHeadline('Supply chain\nconstraints persisted through Q3. More.', 0)).toBe('Supply chain\nconstraints persisted through Q3')
    expect(deriveRiskHeadline('  We Experience Significant Fluctuations in Our Operating Results.  ', 0)).toBe(
      'We Experience Significant Fluctuations in Our Operating Results',
    )
  })

  it('cuts one unbreakable token at the cap', () => {
    const token = 'A'.repeat(150)
    expect(deriveRiskHeadline(`${token} b c`, 0)).toBe(`${'A'.repeat(RISK_HEADLINE_MAX_CHARS)}${RISK_HEADLINE_ELLIPSIS}`)
  })
})
