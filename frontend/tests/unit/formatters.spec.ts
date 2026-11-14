import { formatMetricValue } from '@/features/summaries/lib/metricValue'
import { compactCurrencyCountUp, dataFaceDraws, fmtCurrency, fmtPercent, fmtShares, inSentence, isFigure, parseNumeric } from '@/lib/format'

describe('numeric formatters', () => {
  it('formats currency values compactly by default', () => {
    expect(fmtCurrency(12500)).toBe('$12.5K')
  })

  it('formats currency with explicit digits and standard notation', () => {
    expect(fmtCurrency('42.5', { digits: 2, compact: false })).toBe('$42.50')
  })

  it('prints a currency by its code where the data face lacks its sign, as the trend charts do (E203)', () => {
    // Geist Mono draws neither ₩ nor ₫, nor the narrow no-break space in XOF's "F CFA".
    expect([fmtCurrency(300.9e12, { currency: 'KRW' }), fmtCurrency(30e12, { currency: 'VND' }), fmtCurrency(2e9, { currency: 'XOF' })])
      .toEqual(['KRW\u00a0300.9T', 'VND\u00a030.0T', 'XOF\u00a02.0B'])
    expect(fmtCurrency(-1234.5, { currency: 'KRW', compact: false })).toBe('-KRW\u00a01,234.5')
    expect(compactCurrencyCountUp(22.8e12, 'KRW')(11.4e12)).toBe('KRW\u00a011.4T')
    // A sign the face draws stays a sign.
    expect([fmtCurrency(1e9, { currency: 'EUR' }), fmtCurrency(1e9, { currency: 'INR' }), fmtCurrency(1e9, { currency: 'JPY' })])
      .toEqual(['€1.0B', '₹1.0B', '¥1.0B'])
    // Over the ISO 4217 list, every glyph fmtCurrency prints, compact or not, either sign, is one the data face draws.
    const printed = Intl.supportedValuesOf('currency').flatMap((currency) => [1234.5, -1234.5, 0.5, 2.4e12].flatMap((value) =>
      [true, false].flatMap((compact) => [...fmtCurrency(value, { currency, compact })])))
    expect([...new Set(printed)].filter((glyph) => !dataFaceDraws(glyph))).toEqual([])
    expect(printed, 'the list is the one Intl prints from').toEqual(expect.arrayContaining(['€', '£', '¥', '₹', '₪', '₱', '\u00a0']))
  })

  it('formats percentages with sign handling', () => {
    expect(fmtPercent('0.157', { digits: 2, signed: true })).toBe('+0.16%')
    expect(fmtPercent('-0.031', { digits: 1, signed: true })).toBe('-0.0%')
  })

  it('scales a share count as a magnitude, and keeps a net figure\'s sign when asked', () => {
    expect(fmtShares(1_234_000)).toBe('1.2M')
    expect(fmtShares(-1_234_000)).toBe('1.2M')
    expect(fmtShares(-1_234_000, { signed: true })).toBe('\u22121.2M')
    expect(fmtShares(48_000, { signed: true })).toBe('+48.0K')
    expect(fmtShares(0, { signed: true })).toBe('0')
    expect(fmtShares(null)).toBe('')
  })

  it('reads a sentence-case metric label inside a sentence: its first word lower case unless an acronym', () => {
    const cases: Array<[string, string]> = [
      ['Revenue', 'revenue'], ['Net income', 'net income'], ['Operating cash flow', 'operating cash flow'],
      ['Noninterest income', 'noninterest income'], ["Shareholders' equity", "shareholders' equity"],
      ['Diluted EPS', 'diluted EPS'], ['EPS', 'EPS'],
      // The analysis dataset's own (trend_analysis/periods.py _CONCEPT_LABELS), which its report's notes read the same way.
      ['EPS (diluted)', 'EPS (diluted)'], ['EPS (basic)', 'EPS (basic)'], ['Cash & equivalents', 'cash & equivalents'],
      ['Long-term debt', 'long-term debt'],
    ]
    for (const [label, text] of cases) expect(inSentence(label)).toBe(text)
  })

  // The unit is the first segment, up to whitespace, - or /. & and . sit inside one, so R&D, SG&A and U.S. keep their
  // capitals; - and / end one, so a word joined to an acronym still goes lower case ('non-GAAP EPS'). A capital after
  // a segment's first letter marks an acronym too: YoY stays (the lower-case test alone gave 'yoY growth').
  it.each([
    ['R&D expense', 'R&D expense'], ['SG&A', 'SG&A'], ['U.S. revenue', 'U.S. revenue'],
    ['Non-GAAP EPS', 'non-GAAP EPS'], ['Debt-to-EBITDA', 'debt-to-EBITDA'], ['Price/EPS ratio', 'price/EPS ratio'],
    ['YoY growth', 'YoY growth'],
  ])('judges an acronym on the first segment, up to whitespace, - or /: %s reads %s', (label, text) => {
    expect(inSentence(label)).toBe(text)
  })
})

// A summary can write a figure's scale as a word, and the server writes a filed figure that way ("$416,161 million").
// Read as a bare number, "$81.6 billion" displayed as "$81.6".
describe('a served figure whose scale or unit is a word', () => {
  it('keeps its scale: a word or a two-letter form scales as the single letter does, in any case', () => {
    expect(parseNumeric('$81.6 billion')).toBe(81_600_000_000)
    expect(['$5.3bn', '$383.3 million', '4mn', '7 thousand', '1.5 TRILLION', '2tn'].map(parseNumeric)).toEqual([
      5_300_000_000, 383_300_000, 4_000_000, 7_000, 1_500_000_000_000, 2_000_000_000_000,
    ])
    expect(parseNumeric('($1.2 billion)')).toBe(-1_200_000_000)
    expect(parseNumeric('$391,035 million')).toBe(391_035_000_000)
    // The single letters read as they did.
    expect(['$1.2B', '5k', '3.4M', '2T'].map(parseNumeric)).toEqual([1_200_000_000, 5_000, 3_400_000, 2_000_000_000_000])
  })

  it('reads no number from a figure whose unit is not a scale, so the unit is never dropped', () => {
    for (const served of ['10x', '3 years', '250 bps', '12 percent', '81.6B USD', '$81.6 billion in revenue']) {
      expect(parseNumeric(served), served).toBeNull()
    }
  })

  it('displays as its single-letter form does when the scale is known, and as served when the unit is not a scale', () => {
    expect(formatMetricValue('$81.6 billion')).toBe('$81.6B')
    for (const [worded, letter] of [
      ['$5.3bn', '$5.3B'],
      ['$383.3 million', '$383.3M'],
      ['$391,035 million', '$391,035M'],
      ['1.2 trillion', '1.2T'],
      ['$7 thousand', '$7K'],
      ['($1.2 billion)', '($1.2B)'],
    ]) {
      expect(formatMetricValue(worded), worded).toBe(formatMetricValue(letter))
    }
    for (const served of ['10x', '3 years', '250 bps', '12 percent']) {
      expect(formatMetricValue(served), served).toBe(served)
    }
    // The figures a summary usually writes display as they did.
    expect(['$416,161M', '$7.46', '61.2%'].map(formatMetricValue)).toEqual(['$416.2B', '$7.46', '61.2%'])
  })

  it('counts a number with any unit as a figure, and words or a missing value as none', () => {
    expect(['$1.2B', '$81.6 billion', '10x', '3 years', 0].map(isFigure)).toEqual([true, true, true, true, true])
    expect(
      ['', '—', 'Not disclosed', 'Previously reported $987 before the reclassification', null, undefined, Number.NaN].map(isFigure),
    ).toEqual([false, false, false, false, false, false, false])
  })
})
