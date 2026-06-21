import { describe, it, expect, vi, afterEach } from 'vitest'

vi.mock('@/lib/api/client', () => ({ getApiUrl: () => 'http://api.test' }))

import { fetchFilingContent } from '@/features/filings/api/filing-content-api'

describe('fetchFilingContent', () => {
  afterEach(() => vi.restoreAllMocks())

  it('maps the snake_case API response to the client shape', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ filing_id: 7, has_content: true, markdown_content: '# Item 7\n\nText.' }),
      }),
    )
    const c = await fetchFilingContent(7)
    expect(c).toEqual({ filingId: 7, hasContent: true, markdownContent: '# Item 7\n\nText.' })
  })

  it('represents the no-content case (markdown null)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ filing_id: 7, has_content: false, markdown_content: null }),
      }),
    )
    const c = await fetchFilingContent(7)
    expect(c.hasContent).toBe(false)
    expect(c.markdownContent).toBeNull()
  })

  it('throws on a non-ok response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404 }))
    await expect(fetchFilingContent(7)).rejects.toThrow(/404/)
  })
})
