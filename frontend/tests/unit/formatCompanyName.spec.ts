import { describe, expect, it } from 'vitest'
import { formatCompanyName } from '@/lib/formatCompanyName'

// The one casing rule (lib/formatCompanyName.ts): ALL-CAPS EDGAR names are title-cased per token
// with a small exceptions list; punctuation is never added or removed; already-cased names are
// returned untouched.
describe('formatCompanyName', () => {
  it.each([
    ['APPLE INC.', 'Apple Inc.'],
    ['MICROSOFT CORP', 'Microsoft Corp'],
    ['JPMORGAN CHASE & CO', 'JPMorgan Chase & Co'],
    ['3M CO', '3M Co'],
    ['AT&T INC.', 'AT&T Inc.'],
    ['NVIDIA CORP', 'NVIDIA Corp'],
  ])('title-cases the EDGAR form %s -> %s', (input, expected) => {
    expect(formatCompanyName(input)).toBe(expected)
  })

  // Live sec.gov company_tickers.json: ~1,300-1,600 of 10,412 titles are ALL CAPS except the legal
  // suffix. A cased suffix must not exempt the shouting body in front of it.
  it.each([
    ['ELI LILLY & Co', 'Eli Lilly & Co'],
    ['PROCTER & GAMBLE Co', 'Procter & Gamble Co'],
    ['NIKE, Inc.', 'NIKE, Inc.'], // NIKE is KEEP_UPPER: the company styles its own name that way
    ['CVS HEALTH Corp', 'CVS Health Corp'],
    ['RTX Corp', 'RTX Corp'],
    ['CARRIER GLOBAL Corp', 'Carrier Global Corp'],
    ['NEWMONT Corp /DE/', 'Newmont Corp /DE/'],
    ['NORTHERN TRUST Corp', 'Northern Trust Corp'],
  ])('cases the body when only the legal suffix is cased: %s -> %s', (input, expected) => {
    expect(formatCompanyName(input)).toBe(expected)
  })

  it('resolves initialisms and overrides through glued punctuation', () => {
    expect(formatCompanyName('INTERNATIONAL BUSINESS MACHINES CORP (IBM)')).toBe(
      'International Business Machines Corp (IBM)',
    )
    expect(formatCompanyName('JPMORGAN CHASE & CO.')).toBe('JPMorgan Chase & Co.')
    expect(formatCompanyName('(JPMORGAN) HOLDINGS')).toBe('(JPMorgan) Holdings')
    expect(formatCompanyName('IBM, LLC')).toBe('IBM, LLC')
    expect(formatCompanyName('AT&T, INC.')).toBe('AT&T, Inc.')
    expect(formatCompanyName('BANK OF AMERICA, N.A.')).toBe('Bank of America, N.A.')
  })

  it('leaves an already-cased name untouched', () => {
    expect(formatCompanyName('Alphabet Inc.')).toBe('Alphabet Inc.')
    expect(formatCompanyName('eBay Inc.')).toBe('eBay Inc.')
    expect(formatCompanyName('Nike, Inc.')).toBe('Nike, Inc.')
    expect(formatCompanyName('Alphabet Group Inc')).toBe('Alphabet Group Inc')
  })

  it('never adds punctuation: CORP stays CORP-shaped, INC. keeps its period', () => {
    expect(formatCompanyName('MICROSOFT CORP')).not.toContain('.')
    expect(formatCompanyName('APPLE INC.')).toMatch(/Inc\.$/)
  })

  it('keeps legal-form and brand initialisms upper-case', () => {
    expect(formatCompanyName('UNILEVER PLC')).toBe('Unilever PLC')
    expect(formatCompanyName('BLACKSTONE INC LLC')).toBe('Blackstone Inc LLC')
    expect(formatCompanyName('INTERNATIONAL BUSINESS MACHINES CORP')).toBe('International Business Machines Corp')
    expect(formatCompanyName('IBM')).toBe('IBM')
  })

  it('lower-cases connectives mid-name but not when they lead', () => {
    expect(formatCompanyName('BANK OF AMERICA CORP')).toBe('Bank of America Corp')
    expect(formatCompanyName('THE HOME DEPOT INC')).toBe('The Home Depot Inc')
  })

  it('cases hyphen, apostrophe and dotted segments individually', () => {
    expect(formatCompanyName('COCA-COLA CO')).toBe('Coca-Cola Co')
    expect(formatCompanyName("O'REILLY AUTOMOTIVE INC")).toBe("O'Reilly Automotive Inc")
    expect(formatCompanyName("KOHL'S CORP")).toBe("Kohl's Corp")
    expect(formatCompanyName("MCDONALD'S CORP")).toBe("McDonald's Corp")
    expect(formatCompanyName('U.S. BANCORP')).toBe('U.S. Bancorp')
  })

  it('applies brand overrides and preserves tokens with digits or ampersands', () => {
    expect(formatCompanyName('EBAY INC')).toBe('eBay Inc')
    expect(formatCompanyName('S&P GLOBAL INC')).toBe('S&P Global Inc')
    expect(formatCompanyName('A O SMITH CORP')).toBe('A O Smith Corp')
  })

  it('normalises whitespace and treats null/undefined/empty as empty string', () => {
    expect(formatCompanyName('  APPLE   INC. ')).toBe('Apple Inc.')
    expect(formatCompanyName('')).toBe('')
    expect(formatCompanyName(null)).toBe('')
    expect(formatCompanyName(undefined)).toBe('')
  })
})
