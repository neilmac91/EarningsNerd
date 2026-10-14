import { describe, expect, it } from 'vitest'
import {
  compareParagraphs,
  MAX_COMPARISON_CHARACTERS,
  MAX_COMPARISON_PARAGRAPHS,
} from '@/features/filing-redlines/lib/compareParagraphs'

describe('compareParagraphs', () => {
  it('counts unchanged paragraphs without inventing additions or removals', () => {
    const text = 'Revenue increased.\n\nDemand remained stable.'
    expect(compareParagraphs(text, text)).toEqual({ added: [], removed: [], unchangedCount: 2 })
  })

  it('ignores whitespace and paragraph moves, including CRLF blank lines', () => {
    expect(compareParagraphs(
      ' Revenue\t increased.\n\nDemand\u00a0remained\n stable. ',
      'Demand remained stable.\r\n \t\r\n\r\nRevenue increased.',
    )).toEqual({ added: [], removed: [], unchangedCount: 2 })
  })

  it('preserves unmatched source text and source order on each side', () => {
    expect(compareParagraphs(
      'First  old\nparagraph.\n\nStable.\n\nSecond\told paragraph.',
      'First\tnew paragraph.\n\nStable.\n\nSecond\u00a0new\r\nparagraph.',
    )).toEqual({
      added: ['First\tnew paragraph.', 'Second\u00a0new\r\nparagraph.'],
      removed: ['First  old\nparagraph.', 'Second\told paragraph.'],
      unchangedCount: 1,
    })
  })

  it('counts duplicate occurrences instead of treating paragraphs as a set', () => {
    expect(compareParagraphs(
      'Repeated.\n\nRepeated.\n\nOther.',
      'Other.\n\nOther.\n\nRepeated.',
    )).toEqual({ added: ['Other.'], removed: ['Repeated.'], unchangedCount: 2 })
  })

  it('matches duplicate occurrences in source order after whitespace normalization', () => {
    expect(compareParagraphs(
      'Same  words.\n\nSame\twords.\n\nSame\nwords.',
      'Same words.',
    )).toEqual({ added: [], removed: ['Same\twords.', 'Same\nwords.'], unchangedCount: 1 })
  })

  it.each([
    ['Revenue was $10 million.', 'Revenue was $11 million.'],
    ['Revenue increased.', 'Revenue increased?'],
    ['Risk remained.', 'risk remained.'],
  ])('retains number, punctuation and case changes: %s', (earlier, current) => {
    expect(compareParagraphs(earlier, current)).toEqual({
      added: [current], removed: [earlier], unchangedCount: 0,
    })
  })

  it('returns markup literally without interpreting or stripping HTML', () => {
    const current = '<script>alert("fictional")</script>\n<img src=x onerror="alert(1)">'
    expect(compareParagraphs('Plain earlier text.', current)).toEqual({
      added: [current], removed: ['Plain earlier text.'], unchangedCount: 0,
    })
  })

  it.each(['', ' \t\r\n\r\n\u00a0'])('rejects empty input on either side: %j', (blank) => {
    expect(() => compareParagraphs(blank, 'Current.')).toThrow(/Earlier filing text is empty/)
    expect(() => compareParagraphs('Earlier.', blank)).toThrow(/Current filing text is empty/)
  })

  it('accepts the character limit exactly and rejects either side above it', () => {
    const atLimit = 'x'.repeat(MAX_COMPARISON_CHARACTERS)
    expect(compareParagraphs(atLimit, atLimit)).toEqual({ added: [], removed: [], unchangedCount: 1 })
    expect(() => compareParagraphs(`${atLimit}x`, 'Current.')).toThrow(/Earlier filing text exceeds the 120,000-character/)
    expect(() => compareParagraphs('Earlier.', `${atLimit}x`)).toThrow(/Current filing text exceeds the 120,000-character/)
  })

  it('accepts the paragraph limit exactly and rejects either side above it without truncating', () => {
    const atLimit = Array.from({ length: MAX_COMPARISON_PARAGRAPHS }, (_, index) => `Paragraph ${index}.`).join('\n\n')
    expect(compareParagraphs(atLimit, atLimit)).toEqual({ added: [], removed: [], unchangedCount: MAX_COMPARISON_PARAGRAPHS })
    expect(() => compareParagraphs(`${atLimit}\n\nOverflow.`, 'Current.')).toThrow(/Earlier filing text exceeds the 400-paragraph/)
    expect(() => compareParagraphs('Earlier.', `${atLimit}\n\nOverflow.`)).toThrow(/Current filing text exceeds the 400-paragraph/)
  })
})
