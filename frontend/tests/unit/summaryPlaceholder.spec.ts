import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  SUMMARY_FALLBACK_MESSAGE,
  SUMMARY_PLACEHOLDER_TOKENS,
  isSummaryFailure,
  isSummaryPlaceholder,
  isSummaryReady,
} from '@/features/summaries/lib/summaryPlaceholder'

const REPO = path.join(__dirname, '../../..')

describe('summary placeholder', () => {
  it('mirrors the backend tokens, so both sides call the same bodies filler', () => {
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
})

describe('a stored summary that failed', () => {
  it('is the filing page error card: a writer error, the fallback body, or nothing left to show', () => {
    expect(isSummaryFailure({ business_overview: 'Apple designs devices.', raw_summary: { writer_error: 'timeout' } })).toBe(true)
    expect(isSummaryFailure({ business_overview: `## Executive Summary\n\n${SUMMARY_FALLBACK_MESSAGE}` })).toBe(true)
    expect(isSummaryFailure({ business_overview: '*Auto-generated from structured data*\n\n## Executive Summary\n' })).toBe(true)
    expect(isSummaryFailure({ business_overview: '## Executive Summary\n\nApple designs devices.', raw_summary: {} })).toBe(false)
  })
})

describe('summary ready', () => {
  it('means the filing page will show the body', () => {
    expect(isSummaryReady({ business_overview: 'Apple designs devices.' })).toBe(true)
    expect(isSummaryReady({ business_overview: 'Generating summary...' })).toBe(false)
    expect(isSummaryReady({ business_overview: SUMMARY_FALLBACK_MESSAGE })).toBe(false)
    expect(isSummaryReady({ business_overview: 'Apple designs devices.', raw_summary: { writer_error: 'timeout' } })).toBe(false)
    expect(isSummaryReady({ business_overview: '   ' })).toBe(false)
    expect(isSummaryReady({ business_overview: null })).toBe(false)
    expect(isSummaryReady(null)).toBe(false)
  })
})
