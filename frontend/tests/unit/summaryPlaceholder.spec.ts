import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  SUMMARY_PLACEHOLDER_TOKENS,
  isSummaryPlaceholder,
  isSummaryReady,
} from '@/features/summaries/lib/summaryPlaceholder'

const REPO = path.join(__dirname, '../../..')

describe('summary placeholder', () => {
  it('mirrors the backend tokens, so search and the company page agree on "summary ready"', () => {
    const source = fs.readFileSync(path.join(REPO, 'backend/app/services/summary_placeholders.py'), 'utf8')
    const tuple = source.match(/^SUMMARY_PLACEHOLDER_TOKENS = \(([\s\S]*?)^\)/m)?.[1]
    expect(tuple, 'SUMMARY_PLACEHOLDER_TOKENS tuple').toBeDefined()
    const backend = [...tuple!.matchAll(/"([^"]*)"/g)].map((m) => m[1])
    expect([...SUMMARY_PLACEHOLDER_TOKENS]).toEqual(backend)
  })

  it('matches a token anywhere, in any case', () => {
    expect(isSummaryPlaceholder('Generating summary...')).toBe(true)
    expect(isSummaryPlaceholder('## Note\nSummary temporarily unavailable. Please retry.')).toBe(true)
    expect(isSummaryPlaceholder('This feature REQUIRES OPENAI API KEY')).toBe(true)
    expect(isSummaryPlaceholder('Apple designs devices.')).toBe(false)
    expect(isSummaryPlaceholder(null)).toBe(false)
  })

  it('calls a summary ready only when its body is real analysis', () => {
    expect(isSummaryReady({ business_overview: 'Apple designs devices.' })).toBe(true)
    expect(isSummaryReady({ business_overview: 'Generating summary...' })).toBe(false)
    expect(isSummaryReady({ business_overview: '   ' })).toBe(false)
    expect(isSummaryReady({ business_overview: null })).toBe(false)
    expect(isSummaryReady(null)).toBe(false)
  })
})
