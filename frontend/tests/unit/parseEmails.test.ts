import { describe, it, expect } from 'vitest'

import { parseEmails, classifyEmail } from '@/features/admin/lib/parseEmails'

describe('classifyEmail', () => {
  it('accepts normal addresses', () => {
    expect(classifyEmail('alice@example.com')).toBe(true)
    expect(classifyEmail('a.b+tag@sub.example.co.uk')).toBe(true)
  })

  it('is case- and whitespace-insensitive', () => {
    expect(classifyEmail('  ALICE@Example.COM  ')).toBe(true)
  })

  it('rejects malformed addresses', () => {
    expect(classifyEmail('notanemail')).toBe(false)
    expect(classifyEmail('missing@tld')).toBe(false)
    expect(classifyEmail('@example.com')).toBe(false)
    expect(classifyEmail('a@b.c')).toBe(false) // TLD < 2 chars
    expect(classifyEmail('has space@example.com')).toBe(false)
    expect(classifyEmail('trailing@example.com.')).toBe(false)
    expect(classifyEmail('')).toBe(false)
  })
})

describe('parseEmails', () => {
  it('splits on commas, spaces, semicolons, tabs and newlines', () => {
    const raw = 'a@x.com, b@x.com;c@x.com\nd@x.com\te@x.com f@x.com'
    const { valid, invalid } = parseEmails(raw)
    expect(valid).toEqual(['a@x.com', 'b@x.com', 'c@x.com', 'd@x.com', 'e@x.com', 'f@x.com'])
    expect(invalid).toEqual([])
  })

  it('trims surrounding whitespace from each token', () => {
    const { valid } = parseEmails('   alice@example.com   ,   bob@example.com  ')
    expect(valid).toEqual(['alice@example.com', 'bob@example.com'])
  })

  it('lowercases every address', () => {
    const { valid } = parseEmails('Alice@Example.COM, BOB@EXAMPLE.COM')
    expect(valid).toEqual(['alice@example.com', 'bob@example.com'])
  })

  it('dedupes on the normalized (trimmed + lowercased) form, keeping first-seen order', () => {
    const { valid } = parseEmails('alice@example.com, ALICE@example.com,  alice@example.com ')
    expect(valid).toEqual(['alice@example.com'])
  })

  it('partitions invalid tokens into the invalid list', () => {
    const { valid, invalid } = parseEmails('good@example.com, nope, also-bad@')
    expect(valid).toEqual(['good@example.com'])
    expect(invalid).toEqual(['nope', 'also-bad@'])
  })

  it('dedupes invalid tokens too', () => {
    const { invalid } = parseEmails('nope, nope, NOPE')
    expect(invalid).toEqual(['nope'])
  })

  it('drops empty tokens from leading/trailing/repeated delimiters', () => {
    const { valid, invalid } = parseEmails(',,  ,\n,a@x.com,;')
    expect(valid).toEqual(['a@x.com'])
    expect(invalid).toEqual([])
  })

  it('returns empty lists for an empty or whitespace-only input', () => {
    expect(parseEmails('')).toEqual({ valid: [], invalid: [] })
    expect(parseEmails('   \n\t ')).toEqual({ valid: [], invalid: [] })
  })

  it('is deterministic for the same input', () => {
    const input = 'b@x.com, a@x.com, b@x.com, junk'
    expect(parseEmails(input)).toEqual(parseEmails(input))
  })
})
