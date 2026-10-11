import { afterEach, describe, expect, it, vi } from 'vitest'
const boundary = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@/lib/api/client', () => ({ default: boundary }))
import { fetchFilingContent } from '@/features/filings/api/filing-content-api'
afterEach(() => vi.clearAllMocks())
describe('strict cached content identity', () => {
  it.each([undefined, null, '3', 4, 3.5])('rejects missing or mismatched wire ID %j before attribution', async (filing_id) => {
    boundary.get.mockResolvedValue({ data: { filing_id, has_content: true, markdown_content: 'A quote.' } })
    await expect(fetchFilingContent(3, true)).rejects.toThrow('identify the requested filing')
  })
  it('accepts the exact requested ID and retains legacy fallback for existing callers', async () => {
    boundary.get.mockResolvedValueOnce({ data: { filing_id: 3, has_content: true, markdown_content: 'A quote.' } })
    await expect(fetchFilingContent(3, true)).resolves.toMatchObject({ filingId: 3, markdownContent: 'A quote.' })
    boundary.get.mockResolvedValueOnce({ data: { has_content: true, markdown_content: 'Legacy quote.' } })
    await expect(fetchFilingContent(3)).resolves.toMatchObject({ filingId: 3, markdownContent: 'Legacy quote.' })
  })
})
