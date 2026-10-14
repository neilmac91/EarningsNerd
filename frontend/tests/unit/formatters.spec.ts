import { fmtCurrency, fmtPercent, fmtShares, ordinal, sentenceCase } from '@/lib/format'

describe('numeric formatters', () => {
  it('formats currency values compactly by default', () => {
    expect(fmtCurrency(12500)).toBe('$12.5K')
  })

  it('formats currency with explicit digits and standard notation', () => {
    expect(fmtCurrency('42.5', { digits: 2, compact: false })).toBe('$42.50')
  })

  it('formats percentages with sign handling', () => {
    expect(fmtPercent('0.157', { digits: 2, signed: true })).toBe('+0.16%')
    expect(fmtPercent('-0.031', { digits: 1, signed: true })).toBe('-0.0%')
  })

  it('reads ordinals in English: st, nd, rd, and th for the teens', () => {
    const cases: Array<[number, string]> = [
      [0, '0th'], [1, '1st'], [2, '2nd'], [3, '3rd'], [4, '4th'], [11, '11th'], [12, '12th'], [13, '13th'],
      [21, '21st'], [22, '22nd'], [23, '23rd'], [50, '50th'], [99, '99th'], [100, '100th'], [101, '101st'], [111, '111th'],
    ]
    for (const [n, text] of cases) expect(ordinal(n)).toBe(text)
  })

  it('scales a share count as a magnitude, and keeps a net figure\'s sign when asked', () => {
    expect(fmtShares(1_234_000)).toBe('1.2M')
    expect(fmtShares(-1_234_000)).toBe('1.2M')
    expect(fmtShares(-1_234_000, { signed: true })).toBe('\u22121.2M')
    expect(fmtShares(48_000, { signed: true })).toBe('+48.0K')
    expect(fmtShares(0, { signed: true })).toBe('0')
    expect(fmtShares(null)).toBe('')
  })

  it('puts a stored Title Case metric label in sentence case, keeping the first capital and acronyms', () => {
    const cases: Array<[string, string]> = [
      ['Revenue', 'Revenue'], ['Net Income', 'Net income'], ['Operating Cash Flow', 'Operating cash flow'],
      ['Non-Interest Income', 'Non-interest income'], ["Shareholders' Equity", "Shareholders' equity"],
      ['Diluted EPS', 'Diluted EPS'], ['EPS', 'EPS'],
    ]
    for (const [label, text] of cases) expect(sentenceCase(label)).toBe(text)
  })

  // The unit is the segment between whitespace, - and /. & and . sit inside one, so R&D, SG&A and U.S. keep their
  // single capitals (a letter-run rule gave 'R&d'); - and / end one, so an acronym joined to a word keeps its
  // capitals (a per-word rule gave 'Non-gaap EPS' and 'Debt-to-ebitda').
  it.each([
    ['R&D Expense', 'R&D expense'], ['SG&A', 'SG&A'], ['U.S. Revenue', 'U.S. revenue'],
    ['Non-GAAP EPS', 'Non-GAAP EPS'], ['Adjusted Non-GAAP Income', 'Adjusted non-GAAP income'],
    ['Debt-to-EBITDA', 'Debt-to-EBITDA'], ['Price/EPS Ratio', 'Price/EPS ratio'],
  ])('judges an acronym on the segment between whitespace, - and /: %s reads %s', (label, text) => {
    expect(sentenceCase(label)).toBe(text)
  })
})


