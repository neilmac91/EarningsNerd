import { describe, it, expect, vi, beforeEach } from 'vitest'

// Deliberately a plain function, NOT vi.fn() (the peers/fundamentals spec convention):
// under vitest 4, an error thrown/rejected from a vi.fn-mocked client is re-reported by the
// mock's result tracking and fails the test even when the caller handles it — which breaks
// the error-propagation test below. A plain impl holder sidesteps the tracking entirely.
let getImpl: (...args: unknown[]) => unknown = () => {
  throw new Error('getImpl not set')
}
vi.mock('@/lib/api/client', () => ({
  default: { get: (...args: unknown[]) => getImpl(...args) },
  ApiError: class ApiError extends Error {},
}))

import { fetchFilingContent } from '@/features/filings/api/filing-content-api'

describe('fetchFilingContent', () => {
  beforeEach(() => {
    getImpl = () => {
      throw new Error('getImpl not set')
    }
  })

  it('maps the snake_case API response to the client shape', async () => {
    const calls: unknown[] = []
    getImpl = (...args: unknown[]) => {
      calls.push(args[0])
      return Promise.resolve({
        data: { filing_id: 7, has_content: true, markdown_content: '# Item 7\n\nText.' },
      })
    }
    const c = await fetchFilingContent(7)
    expect(calls).toEqual(['/api/filings/7/content'])
    expect(c).toEqual({ filingId: 7, hasContent: true, markdownContent: '# Item 7\n\nText.' })
  })

  it('represents the no-content case (markdown null)', async () => {
    getImpl = () =>
      Promise.resolve({ data: { filing_id: 7, has_content: false, markdown_content: null } })
    const c = await fetchFilingContent(7)
    expect(c.hasContent).toBe(false)
    expect(c.markdownContent).toBeNull()
  })

  it('propagates the client error on a non-2xx response', async () => {
    getImpl = () => Promise.reject(new Error('Request failed with status 404'))
    await expect(fetchFilingContent(7)).rejects.toThrow(/404/)
  })
})
