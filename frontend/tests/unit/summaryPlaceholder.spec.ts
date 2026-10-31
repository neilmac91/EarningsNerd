import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  IN_PROGRESS_MARKER,
  SUMMARY_FALLBACK_MESSAGE,
  SUMMARY_PLACEHOLDER_TOKENS,
  isFailureFiller,
  isSummaryFailure,
  isSummaryReady,
} from '@/features/summaries/lib/summaryPlaceholder'

const REPO = path.join(__dirname, '../../..')
const API_KEY_ROW = 'Summary generation requires OpenAI API key. Please configure OPENAI_API_KEY in your .env file.'

describe('the readiness rule mirrors the backend', () => {
  const source = fs.readFileSync(path.join(REPO, 'backend/app/services/summary_placeholders.py'), 'utf8')

  it('has the same placeholder tokens', () => {
    const tuple = source.match(/^SUMMARY_PLACEHOLDER_TOKENS = \(([\s\S]*?)^\)/m)?.[1]
    expect(tuple, 'SUMMARY_PLACEHOLDER_TOKENS tuple').toBeDefined()
    const backend = [...tuple!.matchAll(/"([^"]*)"/g)].map((m) => m[1])
    expect([...SUMMARY_PLACEHOLDER_TOKENS]).toEqual(backend)
  })

  it('has the same case-sensitive in-progress marker', () => {
    expect(source.match(/^IN_PROGRESS_MARKER = "([^"]*)"$/m)?.[1]).toBe(IN_PROGRESS_MARKER)
  })
})

describe('failure filler', () => {
  it('carries a failure token anywhere, in any case', () => {
    expect(isFailureFiller('## Note\nSummary temporarily unavailable. Please retry.')).toBe(true)
    expect(isFailureFiller('This feature REQUIRES OPENAI API KEY')).toBe(true)
    expect(isFailureFiller('Apple designs devices.')).toBe(false)
    expect(isFailureFiller(null)).toBe(false)
  })

  it('leaves the in-progress marker and prose about generating summaries alone', () => {
    expect(isFailureFiller('Generating summary...')).toBe(false)
    expect(isFailureFiller('A real partial overview about generating summary reports.')).toBe(false)
  })
})

describe('a stored summary that failed', () => {
  it('is the filing page error card: filler, a writer error, the fallback body, or nothing left to show', () => {
    expect(isSummaryFailure({ business_overview: API_KEY_ROW })).toBe(true)
    expect(isSummaryFailure({ business_overview: 'Apple designs devices.', raw_summary: { writer_error: 'timeout' } })).toBe(true)
    expect(isSummaryFailure({ business_overview: `## Executive Summary\n\n${SUMMARY_FALLBACK_MESSAGE}` })).toBe(true)
    expect(isSummaryFailure({ business_overview: '*Auto-generated from structured data*\n\n## Executive Summary\n' })).toBe(true)
    expect(isSummaryFailure({ business_overview: '## Executive Summary\n\nApple designs devices.', raw_summary: {} })).toBe(false)
  })
})

describe('summary ready', () => {
  it('means the filing page will show the body', () => {
    expect(isSummaryReady({ business_overview: 'Apple designs devices.' })).toBe(true)
    expect(isSummaryReady({ business_overview: 'A real partial overview about generating summary reports.' })).toBe(true)
    expect(isSummaryReady({ business_overview: 'Generating summary...' })).toBe(false)
    expect(isSummaryReady({ business_overview: SUMMARY_FALLBACK_MESSAGE })).toBe(false)
    expect(isSummaryReady({ business_overview: API_KEY_ROW })).toBe(false)
    expect(isSummaryReady({ business_overview: 'Apple designs devices.', raw_summary: { writer_error: 'timeout' } })).toBe(false)
    expect(isSummaryReady({ business_overview: '   ' })).toBe(false)
    expect(isSummaryReady({ business_overview: null })).toBe(false)
    expect(isSummaryReady(null)).toBe(false)
  })
})
