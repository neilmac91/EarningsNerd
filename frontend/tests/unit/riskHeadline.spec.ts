import { describe, expect, it } from 'vitest'
import {
  RISK_HEADLINE_ELLIPSIS,
  RISK_HEADLINE_MAX_CHARS,
  deriveRiskHeadline,
  riskHeadlineFallback,
} from '@/features/summaries/lib/riskHeadline'
import filing3Risks from '../e2e/fixtures/filing-3-risks.json'

// A risk row's heading is a verbatim prefix of its own verified filing excerpt (founder option b):
// never the model's label, never rewritten. These pin the rule on the real spans it was designed
// against and on the edge cases a naive first-clause cut gets wrong. This file is the one place the
// exact headlines are pinned; riskTitle.spec pins what excerptHeadings adds (quote pair, uniqueness)
// and the render spec checks the rows against excerptHeadings.

/**
 * The four source-verified risk spans of the production filing-3 summary (Apple FY2025 10-K), read
 * from the fixture copied out of the cached payload (lessons/test-verbatim-fixtures-keep-the-source-bytes.md).
 */
const FILING_3_HEADLINES = [
  'Tariffs and other measures that are applied to the Company’s products or their components…',
  // A first-comma cut ends inside the country list ("... primarily in China mainland").
  'Substantially all of the Company’s hardware products are manufactured by outsourcing partners…',
  // A first-comma cut ends on the leading date ("As of September 27"). The filing's own no-break
  // space after "September" is kept: verbatim means byte for byte, not normalised.
  'As of September 27, 2025, the total amount of gross unrecognized tax benefits was $23.2 billion…',
  // A first-comma cut ends on the leading qualifier ("Regardless of the merit of particular claims").
  'Regardless of the merit of particular claims, defending against litigation or responding…',
]
const FILING_3: Array<[string, string]> = filing3Risks.map((risk, i) => [risk.supporting_evidence, FILING_3_HEADLINES[i]])

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
    'a short first sentence is the whole headline, and the ellipsis says the excerpt goes on',
    'Tax years 2019-2022 are under audit. Tax years 2023-2026 are open but not under audit. All other tax years are closed.',
    'Tax years 2019-2022 are under audit…',
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

const withoutEllipsis = (headline: string): string =>
  headline.endsWith(RISK_HEADLINE_ELLIPSIS) ? headline.slice(0, -RISK_HEADLINE_ELLIPSIS.length) : headline

/** The headline without its ellipsis must open the excerpt exactly. */
const isVerbatimPrefix = (excerpt: string, headline: string): boolean => excerpt.trim().startsWith(withoutEllipsis(headline))

describe('deriveRiskHeadline', () => {
  it('reads the four production spans from the copied fixture', () => {
    expect(FILING_3).toHaveLength(4)
  })

  it.each(FILING_3)('titles the production filing-3 span %#', (excerpt, headline) => {
    expect(deriveRiskHeadline(excerpt, 0)).toBe(headline)
  })

  it.each(BACKEND_FIXTURES)('titles the backend fixture span %#', (excerpt, headline) => {
    expect(deriveRiskHeadline(excerpt, 0)).toBe(headline)
  })

  it.each(EVAL_SPANS)('%s', (_rule, excerpt, headline) => {
    expect(deriveRiskHeadline(excerpt, 0)).toBe(headline)
  })

  it('is a verbatim prefix of every real span, within the cap, ellipsed exactly when the excerpt goes on, and deterministic', () => {
    for (const [excerpt] of REAL) {
      const headline = deriveRiskHeadline(excerpt, 3)
      expect(isVerbatimPrefix(excerpt, headline), headline).toBe(true)
      expect(headline.length).toBeLessThanOrEqual(RISK_HEADLINE_MAX_CHARS + RISK_HEADLINE_ELLIPSIS.length)
      const rest = excerpt.trim().slice(withoutEllipsis(headline).length)
      expect(headline.endsWith(RISK_HEADLINE_ELLIPSIS), headline).toBe(/[^\s.]/.test(rest))
      expect(deriveRiskHeadline(excerpt, 3)).toBe(headline)
    }
  })

  it('falls back to the positional title when the excerpt is missing or too short', () => {
    expect(deriveRiskHeadline(undefined, 0)).toBe('Risk 1')
    expect(deriveRiskHeadline(null, 1)).toBe('Risk 2')
    expect(deriveRiskHeadline('', 2)).toBe('Risk 3')
    expect(deriveRiskHeadline('   \n ', 3)).toBe('Risk 4')
    expect(deriveRiskHeadline('Tariffs.', 4)).toBe('Risk 5')
    expect(deriveRiskHeadline('Supply risk', 5)).toBe('Risk 6')
    expect(deriveRiskHeadline('… — ;', 6)).toBe('Risk 7')
    expect(riskHeadlineFallback(7)).toBe('Risk 8')
  })

  it('keeps a short excerpt whole, with or without punctuation', () => {
    expect(deriveRiskHeadline('Margins may compress', 0)).toBe('Margins may compress')
    expect(deriveRiskHeadline('Dependence on a single foundry partner', 0)).toBe('Dependence on a single foundry partner')
    expect(deriveRiskHeadline('We face credit risks.', 0)).toBe('We face credit risks')
  })

  it('drops a whole ASCII ellipsis at a sentence break, as it drops a period', () => {
    expect(deriveRiskHeadline('Our suppliers may fail... Production could stop if they do.', 0)).toBe('Our suppliers may fail…')
    // A period before the ellipsis, and the spaced form legal text uses, go whole too.
    expect(deriveRiskHeadline('Our suppliers may fail.... Production could stop if they do.', 0)).toBe('Our suppliers may fail…')
    expect(deriveRiskHeadline('Our suppliers may fail . . . Production could stop if they do.', 0)).toBe('Our suppliers may fail…')
    expect(deriveRiskHeadline('Our suppliers may fail...', 0)).toBe('Our suppliers may fail')
    // Inside a closing quotation it stays, with the quote.
    expect(deriveRiskHeadline('Our supplier warned that “production may stop...” Other risks follow below.', 0)).toBe(
      'Our supplier warned that “production may stop...”…',
    )
  })

  it('skips a first sentence too short to head the row rather than ending on it', () => {
    expect(deriveRiskHeadline('Risks. Tariffs could hurt margins this year.', 0)).toBe('Risks. Tariffs could hurt margins this year')
    expect(deriveRiskHeadline('Demand softened! Management cut guidance.', 0)).toBe('Demand softened! Management cut guidance')
    expect(deriveRiskHeadline('Could tariffs rise again? Management expects so.', 0)).toBe('Could tariffs rise again?…')
  })

  it('never cuts a sentence that fits, so a turn or hedge after a ";" stays in the heading', () => {
    expect(deriveRiskHeadline('We maintain insurance coverage; however, such coverage may not be adequate to cover all losses.', 0)).toBe(
      'We maintain insurance coverage; however, such coverage may not be adequate to cover all losses',
    )
    expect(deriveRiskHeadline('Item 1A: “substantially dependent on TSMC.”', 0)).toBe('Item 1A: “substantially dependent on TSMC.”')
    // A sentence that ends inside straight quotes ends there too, keeping its closing quote.
    expect(deriveRiskHeadline("The filing states 'We face material risks.' More details follow.", 0)).toBe(
      "The filing states 'We face material risks.'…",
    )
    // The next sentence may open with a quote mark and a currency sign before its first figure.
    expect(deriveRiskHeadline("Liquidity may be constrained. '$5 per unit' fees could reduce demand materially.", 0)).toBe(
      'Liquidity may be constrained…',
    )
    expect(deriveRiskHeadline('Liquidity may be constrained. “$5 per unit” fees could reduce demand materially.', 0)).toBe(
      'Liquidity may be constrained…',
    )
    // Or with any capital letter, not only an ASCII one.
    expect(deriveRiskHeadline('Liquidity may be constrained. Élan could terminate the agreement and halt our production.', 0)).toBe(
      'Liquidity may be constrained…',
    )
  })

  it('cuts a long sentence at its first ";" or ":" when the clause before it can stand as a heading', () => {
    expect(
      deriveRiskHeadline(
        'Supply of the Company’s most advanced components is concentrated in a single region; a disruption there, whether from natural disaster or conflict, would halt production.',
        0,
      ),
    ).toBe('Supply of the Company’s most advanced components is concentrated in a single region…')
    expect(
      deriveRiskHeadline(
        'Our revenue depends on a small number of customers and their purchasing cycles: a loss of any one of them would materially reduce revenue.',
        0,
      ),
    ).toBe('Our revenue depends on a small number of customers and their purchasing cycles…')
    // A span that stops on its own lead-in colon reads as cut.
    expect(deriveRiskHeadline('The Company faces risks related to:', 0)).toBe('The Company faces risks related to…')
  })

  it('does not cut at a ";" or ":" after a leading date or qualifier, before a turn, or inside a bracket', () => {
    expect(
      deriveRiskHeadline(
        'As of December 31, 2025: the Company had $4.1 billion of debt outstanding, of which $1.2 billion matures within the next twelve months.',
        0,
      ),
    ).toBe('As of December 31, 2025: the Company had $4.1 billion of debt outstanding, of which $1.2 billion…')
    expect(
      deriveRiskHeadline(
        'In the third quarter: revenue declined 20% due to a fire at our largest facility, which halted production at the site for six weeks.',
        0,
      ),
    ).toBe('In the third quarter: revenue declined 20% due to a fire at our largest facility, which halted…')
    expect(
      deriveRiskHeadline(
        'The Company believes its reserves for these matters are adequate; however, actual losses could materially exceed the amounts accrued.',
        0,
      ),
    ).toBe('The Company believes its reserves for these matters are adequate; however, actual losses…')
    expect(
      deriveRiskHeadline(
        'The Company (and its subsidiaries; collectively, the “Group”) faces significant competition in every market in which it operates.',
        0,
      ),
    ).toBe('The Company (and its subsidiaries; collectively, the “Group”) faces significant competition in every…')
  })

  it('never cuts at a dash: a range or an aside stays whole', () => {
    expect(deriveRiskHeadline('The tax years 2019 – 2022 remain under examination by the IRS and other taxing authorities.', 0)).toBe(
      'The tax years 2019 – 2022 remain under examination by the IRS and other taxing authorities',
    )
    expect(deriveRiskHeadline('Our federal tax returns for 2019—2022 remain open to examination by the Internal Revenue Service.', 0)).toBe(
      'Our federal tax returns for 2019—2022 remain open to examination by the Internal Revenue Service',
    )
    expect(deriveRiskHeadline('Our supply chain constraints — particularly in memory — persisted through the quarter.', 0)).toBe(
      'Our supply chain constraints — particularly in memory — persisted through the quarter',
    )
    // The NVIDIA-shaped aside, its lead-in short enough that a dash cut would have reached it.
    expect(
      deriveRiskHeadline(
        'Increased scrutiny from customs and other authorities—particularly with regard to China—could materially affect our supply chain.',
        0,
      ),
    ).toBe('Increased scrutiny from customs and other authorities—particularly with regard to China—could…')
    expect(
      deriveRiskHeadline(
        'We do not expect the outcome of these proceedings to be material — but an unfavorable ruling could require us to pay substantial damages.',
        0,
      ),
    ).toBe('We do not expect the outcome of these proceedings to be material — but an unfavorable ruling…')
  })

  it('does not end a sentence inside a number, an initialism or an abbreviation', () => {
    expect(deriveRiskHeadline('Margins fell 3.5% on U.S. tariffs. More text.', 0)).toBe('Margins fell 3.5% on U.S. tariffs…')
    expect(deriveRiskHeadline('Sales to the U.S. Government declined 20% in fiscal 2025.', 0)).toBe(
      'Sales to the U.S. Government declined 20% in fiscal 2025',
    )
    expect(deriveRiskHeadline('The Company relies on J.P. Morgan Chase Bank, N.A. as its sole depositary for these accounts.', 0)).toBe(
      'The Company relies on J.P. Morgan Chase Bank, N.A. as its sole depositary for these accounts',
    )
    expect(deriveRiskHeadline('Apple Inc. faces new tariff exposure. Details follow.', 0)).toBe('Apple Inc. faces new tariff exposure…')
    // A company suffix before a capitalised word does end the sentence, and keeps its period.
    expect(deriveRiskHeadline('Our sole supplier is Acme Inc. Production may stop if the supplier fails.', 0)).toBe(
      'Our sole supplier is Acme Inc.…',
    )
    expect(deriveRiskHeadline('Our sole supplier is Acme Co. Production may stop if the supplier fails.', 0)).toBe(
      'Our sole supplier is Acme Co.…',
    )
    // A name suffix ends a sentence the same way and keeps its period.
    expect(deriveRiskHeadline('Our chief executive officer is John Smith Jr. His departure could disrupt our operations.', 0)).toBe(
      'Our chief executive officer is John Smith Jr.…',
    )
    // Unless "Sr." means Senior, before a title or an instrument.
    expect(deriveRiskHeadline('The departure of our Sr. Vice President of Sales could disrupt key customer relationships.', 0)).toBe(
      'The departure of our Sr. Vice President of Sales could disrupt key customer relationships',
    )
    expect(deriveRiskHeadline('We must repay the 5.25% Sr. Notes due 2030 at maturity or refinance them on worse terms.', 0)).toBe(
      'We must repay the 5.25% Sr. Notes due 2030 at maturity or refinance them on worse terms',
    )
    // Unless the capitalised word carries on the company's name.
    expect(deriveRiskHeadline('We buy cells from Contemporary Amperex Technology Co. Limited (CATL). We have no contract.', 0)).toBe(
      'We buy cells from Contemporary Amperex Technology Co. Limited (CATL)…',
    )
    // A parenthetical after a suffix keeps the sentence going: a defined-term alias, or a ticker after
    // any company suffix ("Acme Inc. (NASDAQ: ACME) and it may…"). "N.V." and "S.A." never end one.
    for (const name of [
      'Acme Inc. ("Acme")',
      'Acme Inc. (“Acme”)',
      'Acme Inc. (NASDAQ: ACME)',
      'Acme Corp. (NYSE: ACME)',
      'Acme Ltd. (LSE: ACME)',
      'Acme Co. (ACME)',
      'Acme N.V. (ACME)',
      'Acme S.A. (ACME)',
    ]) {
      expect(
        deriveRiskHeadline(`Our sole supplier is ${name} and it may terminate our agreement without notice, which could disrupt our production and harm results.`, 0),
      ).toBe(`Our sole supplier is ${name} and it may terminate our agreement without notice…`)
    }
    expect(deriveRiskHeadline('Under ASU No. 2023-07 the Company discloses significant segment expenses. More.', 0)).toBe(
      'Under ASU No. 2023-07 the Company discloses significant segment expenses…',
    )
    expect(deriveRiskHeadline('Acme Corp., a subsidiary, lost its license. More.', 0)).toBe('Acme Corp., a subsidiary, lost its license…')
    expect(deriveRiskHeadline('Margins compressed in Q1 vs. Q2 on mix. More.', 0)).toBe('Margins compressed in Q1 vs. Q2 on mix…')
    expect(deriveRiskHeadline('Shipments fell approx. 10% in the quarter. More.', 0)).toBe('Shipments fell approx. 10% in the quarter…')
    expect(deriveRiskHeadline('Revenue from key customers, incl. Apple and Dell, declined. More.', 0)).toBe(
      'Revenue from key customers, incl. Apple and Dell, declined…',
    )
    expect(deriveRiskHeadline('The FDA issued a warning letter in Sept. 2025 regarding our manufacturing facility.', 0)).toBe(
      'The FDA issued a warning letter in Sept. 2025 regarding our manufacturing facility',
    )
    // A period before a lower-case word does not end a sentence, listed abbreviation or not.
    expect(deriveRiskHeadline('Sales fell 4 pct. year over year on weaker demand. More.', 0)).toBe('Sales fell 4 pct. year over year on weaker demand…')
  })

  it('caps a long clause on a word boundary, never on a function word, with an ellipsis', () => {
    const long =
      'The Company depends on continued access to advanced semiconductor manufacturing capacity from a small number of foundry partners located in a single region'
    const headline = deriveRiskHeadline(long, 0)
    expect(headline).toBe('The Company depends on continued access to advanced semiconductor manufacturing capacity…')
    expect(isVerbatimPrefix(long, headline)).toBe(true)
    // The character after the cut is a space: a whole word, not a mid-word cut.
    expect(long.charAt(headline.length - 1)).toBe(' ')
    // A subject pronoun waits for its verb, so the cap backs up past it.
    expect(
      deriveRiskHeadline('Our chief executive maintains relationships with suppliers, customers, distributors, and she may leave without adequate succession plans.', 0),
    ).toBe('Our chief executive maintains relationships with suppliers, customers, distributors…')
  })

  it('never splits a figure from its unit or label at the cap', () => {
    const cases: Array<[string, string]> = [
      // A two-word unit: never "200 basis…" or a bare "2…" before "percentage points"; nor the
      // "approximately" that qualifies the figure.
      [
        'Our borrowing costs could increase and reduce consolidated earnings by approximately 200 basis points next year.',
        'Our borrowing costs could increase and reduce consolidated earnings…',
      ],
      [
        'Our borrowing costs could increase and reduce our consolidated gross margin by approximately 2 percentage points next year.',
        'Our borrowing costs could increase and reduce our consolidated gross margin…',
      ],
      // A comparative waiting for "than" or "so", and the "even" before it: never "more…".
      [
        'Our union contracts cover a large part of the workforce, and a single union now represents more than 3,200 employees at our largest sites.',
        'Our union contracts cover a large part of the workforce, and a single union now represents…',
      ],
      // A figure before the noun it counts: never "3,200…" before "employees".
      [
        'Our operations depend on a unionised workforce, and a single union now represents a total of 3,200 employees at our largest manufacturing sites.',
        'Our operations depend on a unionised workforce, and a single union now represents a total…',
      ],
      // A count with a trailing "+" is a figure too: never "3,200+…" before "employees".
      [
        'Our operations depend on a unionised workforce, and a single union represents approximately 3,200+ employees at our largest sites.',
        'Our operations depend on a unionised workforce, and a single union represents…',
      ],
      // A figure before "per", and the "up to" before it: never "$5…" nor "prices up…".
      [
        'The Board approved a dividend and the Company expects to repurchase additional shares at prices up to $5 per share during the year.',
        'The Board approved a dividend and the Company expects to repurchase additional shares at prices…',
      ],
      // A currency code or a label before its figure: never "EUR…" or "Item…".
      [
        'The Company has significant exposure to foreign currency movements, including its liabilities of EUR 2.5 billion due in the next year.',
        'The Company has significant exposure to foreign currency movements, including its liabilities…',
      ],
      [
        'Risks related to our indebtedness and our ability to comply with our covenants are described further under Item 1A of this report.',
        'Risks related to our indebtedness and our ability to comply with our covenants are described further…',
      ],
    ]
    for (const [excerpt, headline] of cases) expect(deriveRiskHeadline(excerpt, 0)).toBe(headline)
    // Only a bare figure counts: a token that merely ends in digits (a URL) is not cut away.
    expect(
      deriveRiskHeadline('Risk disclosures are posted at investor.example.com/secfilings/annualreports/form10k/riskfactors2025 every quarter.', 0),
    ).toBe('Risk disclosures are posted at investor.example.com/secfilings/annualreports/form10k/riskfactors2025…')
    // A unit written with a capital stays with its figure too ("100 MW").
    expect(
      deriveRiskHeadline(
        'Our data centers depend on uninterrupted access to contracted renewable energy capacity totaling 100 MW during periods of peak demand.',
        0,
      ),
    ).toBe('Our data centers depend on uninterrupted access to contracted renewable energy capacity totaling…')
    // A count's scale word stays with its noun, in figures or in words ("3.2 million | employees",
    // "roughly two | million"); a money amount reads whole before an adverb ("$337 million | mainly").
    for (const tail of ['approximately 3.2 million employees and contractors worldwide.', 'roughly two million independent contractors located worldwide.']) {
      expect(
        deriveRiskHeadline(`Our business depends on the continued availability and productivity of ${tail}`, 0),
      ).toBe('Our business depends on the continued availability and productivity…')
    }
    expect(
      deriveRiskHeadline(
        'For the year ended December 31, 2025, we had a consolidated loss on foreign currency of $337 million mainly related to foreign exchange losses from our Argentine subsidiaries.',
        0,
      ),
    ).toBe('For the year ended December 31, 2025, we had a consolidated loss on foreign currency of $337 million…')
  })

  it('never splits a day-first date ("27 September 2025") at the cap', () => {
    // "27" ends at character 100 and "September" runs past it: the cut moves back to a whole phrase.
    expect(
      deriveRiskHeadline(
        'Our income tax returns in several foreign jurisdictions remain open and subject to review through 27 September 2025 by the local tax authorities.',
        0,
      ),
    ).toBe('Our income tax returns in several foreign jurisdictions remain open and subject to review…')
  })

  it('ends on the last content word when every cut would split a name (an all-caps run)', () => {
    expect(
      deriveRiskHeadline(
        'WE MAY NOT BE ABLE TO COMPETE SUCCESSFULLY AGAINST CURRENT AND FUTURE COMPETITORS IN THE MARKETS OF THE UNITED STATES AND EUROPE',
        0,
      ),
    ).toBe('WE MAY NOT BE ABLE TO COMPETE SUCCESSFULLY AGAINST CURRENT AND FUTURE COMPETITORS IN THE MARKETS…')
  })

  it('does not leave a bracket or a quotation open', () => {
    expect(
      deriveRiskHeadline(
        'The Company relies on a single contract manufacturer for its flagship devices (the “Manufacturer”, which assembles substantially all units) and on a small number of suppliers.',
        0,
      ),
    ).toBe('The Company relies on a single contract manufacturer for its flagship devices…')
    // A parenthetical that opens in the first words and closes past the cap leaves no prefix that
    // closes it: the row keeps its positional heading rather than stopping inside the bracket.
    expect(
      deriveRiskHeadline(
        'The Company (including all of its subsidiaries in North America, South America, Africa, Europe and Asia) faces significant competition in every market it serves.',
        0,
      ),
    ).toBe('Risk 1')
    // Square brackets and curly single quotes count too; an apostrophe between letters ("customer’s")
    // is not a closing quote.
    expect(
      deriveRiskHeadline(
        'The Company [including all of its subsidiaries in North America, South America, Africa, Europe and Asia] faces significant competition in every market it serves.',
        0,
      ),
    ).toBe('Risk 1')
    expect(
      deriveRiskHeadline(
        'Our largest customer has described its supply arrangements with us as ‘subject to annual renegotiation at the customer’s sole discretion’ in each of the last three years.',
        0,
      ),
    ).toBe('Our largest customer has described its supply arrangements with us…')
    // A plural possessive before the quotation ("customers’") does not close it either.
    expect(
      deriveRiskHeadline(
        'Our customers’ agreements describe these supply arrangements as ‘subject to annual renegotiation at the customer’s sole discretion’ in each of the last three years.',
        0,
      ),
    ).toBe('Our customers’ agreements describe these supply arrangements…')
    // Straight single quotes are read the same way; "Company's" stays an apostrophe.
    expect(
      deriveRiskHeadline(
        "Our largest customer describes these supply arrangements as 'subject to annual renegotiation and termination without notice' in each year.",
        0,
      ),
    ).toBe('Our largest customer describes these supply arrangements…')
    // A straight quote opens before a figure or currency sign as well as before a letter.
    expect(
      deriveRiskHeadline(
        "Our largest customer agreement describes the fee as '$5 per unit subject to annual escalation and quarterly adjustment' in each contract year.",
        0,
      ),
    ).toBe('Our largest customer agreement describes the fee…')
    // A sentence break inside a quotation is the quoted sentence's, not the excerpt's.
    expect(
      deriveRiskHeadline('Our supplier warned that “production may stop. Delays could persist.” Other risks follow below.', 0),
    ).toBe('Our supplier warned that “production may stop. Delays could persist.”…')
    // A quote after a plural closes the quotation before punctuation; only before a word does it read as
    // a possessive ("customers’ agreements").
    expect(
      deriveRiskHeadline(
        "The phrase 'material risks', as used in our customer agreements, permits termination without notice and could materially disrupt our operations.",
        0,
      ),
    ).toBe("The phrase 'material risks', as used in our customer agreements, permits termination without notice…")
    // Brackets are read in order: a fragment's stray closer early on does not cancel one opened later.
    for (const [open, close] of [['(', ')'], ['[', ']'], ['“', '”'], ['"', '"']]) {
      expect(
        deriveRiskHeadline(
          `Our obligations${close} and our reliance on a single contract manufacturer ${open}which assembles substantially all of our flagship units in two facilities${close} expose us to supply disruption.`,
          0,
        ),
      ).toBe(`Our obligations${close} and our reliance on a single contract manufacturer…`)
    }
  })

  it('keeps the excerpt’s own whitespace and casing (verbatim, not normalised)', () => {
    expect(deriveRiskHeadline('Supply chain\nconstraints persisted through Q3. More.', 0)).toBe('Supply chain\nconstraints persisted through Q3…')
    expect(deriveRiskHeadline('  We Experience Significant Fluctuations in Our Operating Results.  ', 0)).toBe(
      'We Experience Significant Fluctuations in Our Operating Results',
    )
  })

  it('keeps the positional title when fewer than four whole words fit under the cap', () => {
    expect(deriveRiskHeadline(`${'A'.repeat(150)} b c`, 2)).toBe('Risk 3')
    expect(
      deriveRiskHeadline(
        'See https://www.example.com/investor-relations/annual-reports/2025/form-10-k-risk-factors-supplement-and-exhibits for more detail on these risks.',
        0,
      ),
    ).toBe('Risk 1')
  })
})
