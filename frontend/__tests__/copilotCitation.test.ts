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
  it('detects XBRL facts by F-marker or XBRL section_ref, and ignores prose citations', () => {
    expect(isXbrlCitation({ ...base, n: 'F1' })).toBe(true)
    expect(isXbrlCitation({ ...base, n: 'f 2' })).toBe(true) // tolerant of casing/spacing
    expect(isXbrlCitation({ ...base, section_ref: 'XBRL · us-gaap:Revenue' })).toBe(true)
    expect(isXbrlCitation({ ...base, n: 1, section_ref: 'Item 7 — MD&A' })).toBe(false)
    expect(isXbrlCitation({ ...base, n: 2, section_ref: null })).toBe(false)
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
