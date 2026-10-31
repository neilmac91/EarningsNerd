import { compactCurrencyCountUp, dataFaceDraws, fmtCurrency, fmtPercent, fmtShares, inSentence } from '@/lib/format'

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
      ['EPS (diluted)', 'EPS (diluted)'], ['Cash & equivalents', 'cash & equivalents'], ['Long-term debt', 'long-term debt'],
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


