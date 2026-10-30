import { describe, it, expect } from 'vitest'
import {
  isXbrlCitation,
  xbrlTag,
  type CopilotCitation,
} from '@/features/filings/api/copilot-api'

const base: CopilotCitation = {
  n: 1,
  excerpt: '',
  section_ref: null,
  verified: false,
  fragment_url: null,
}

describe('isXbrlCitation', () => {
  it('reads a figure from the fact or calculated payload alone, whatever the label or marker says', () => {
    expect(isXbrlCitation({ ...base, section_ref: 'XBRL · us-gaap:Revenue', fact: true })).toBe(true)
    expect(isXbrlCitation({ ...base, section_ref: 'XBRL · us-gaap:Revenue', calculated: true })).toBe(true)
    // The payload decides even under a passage's label or none.
    expect(isXbrlCitation({ ...base, section_ref: 'Item 7 — MD&A', fact: true })).toBe(true)
    expect(isXbrlCitation({ ...base, section_ref: null, calculated: true })).toBe(true)
  })

  it('keeps a citation with no payload a passage, an "XBRL · …" label or an "F#" marker included (E179)', () => {
    // A model can label an excerpt "XBRL · …" or write [F1]; neither is the server's numerical proof.
    expect(isXbrlCitation({ ...base, section_ref: 'XBRL · us-gaap:Revenue' })).toBe(false)
    expect(isXbrlCitation({ ...base, n: 'F1', section_ref: 'XBRL · us-gaap:Revenue' })).toBe(false)
    expect(isXbrlCitation({ ...base, n: 'f 2' })).toBe(false)
    expect(isXbrlCitation({ ...base, n: 1, section_ref: 'Item 7 — MD&A' })).toBe(false)
    expect(isXbrlCitation({ ...base, n: 2, section_ref: null })).toBe(false)
  })

  it('fails safe on a malformed payload: only the literal true marks a figure', () => {
    for (const value of ['true', 1, {}, null, false]) {
      const malformed = { ...base, section_ref: 'XBRL · us-gaap:Revenue', fact: value, calculated: value } as unknown as CopilotCitation
      expect(isXbrlCitation(malformed)).toBe(false)
    }
  })
})

describe('xbrlTag', () => {
  it('extracts the raw tag from an XBRL section_ref', () => {
    expect(xbrlTag({ ...base, section_ref: 'XBRL · us-gaap:Revenue' })).toBe('us-gaap:Revenue')
    // tolerant of a missing/odd separator
    expect(xbrlTag({ ...base, section_ref: 'XBRL  us-gaap:GrossProfit' })).toBe('us-gaap:GrossProfit')
  })

  it('returns null for non-XBRL, empty, or tag-less refs', () => {
    expect(xbrlTag({ ...base, section_ref: 'Item 7 — MD&A' })).toBeNull()
    expect(xbrlTag({ ...base, section_ref: null })).toBeNull()
    expect(xbrlTag({ ...base, section_ref: 'XBRL · ' })).toBeNull()
  })
})
