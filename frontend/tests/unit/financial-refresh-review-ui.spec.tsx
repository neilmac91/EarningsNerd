import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FinancialRefreshReview } from '@/features/financial-refresh-review/components/FinancialRefreshReview'
import { currentValuesCsv, buildReceipt } from '@/features/financial-refresh-review/lib/refreshReview'
import { FICTIONAL_ROWS } from '@/features/financial-refresh-review/data/fictionalExample'

const h = vi.hoisted(() => ({ download: vi.fn() }))
vi.mock('@/lib/downloadBlob', () => ({ downloadBlob: h.download }))
function readBlob(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsText(blob)
  })
}

describe('Financial refresh review workflow', () => {
  beforeEach(() => h.download.mockClear())
  it('labels fictional evidence and offers no acceptance for missing or incompatible figures', () => {
    render(<FinancialRefreshReview />)
    expect(screen.getByText(/Harbor Components is fictional/)).toHaveTextContent('No SEC data is loaded')
    expect(screen.getByRole('article', { name: 'Operating expenses' })).toHaveTextContent('EUR')
    expect(within(screen.getByRole('article', { name: 'Cash' })).queryByRole('button', { name: /Accept/ })).not.toBeInTheDocument()
    expect(within(screen.getByRole('article', { name: 'Operating expenses' })).queryByRole('button', { name: /Accept/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add period for Net income' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })
  it('accepts and keeps by keyboard, exports the actual review, and resets', async () => {
    const user = userEvent.setup()
    render(<FinancialRefreshReview />)
    const accept = screen.getByRole('button', { name: 'Accept value for Revenue' })
    accept.focus()
    await user.keyboard('{Enter}')
    expect(accept).toHaveFocus()
    expect(accept).toHaveAttribute('aria-pressed', 'true')
    await user.click(screen.getByRole('button', { name: 'Keep baseline for Cash' }))
    await user.click(screen.getByRole('button', { name: 'Export current values CSV' }))
    expect(h.download.mock.calls[0][1]).toBe('fictional-financial-values.csv')
    expect(await readBlob(h.download.mock.calls[0][0])).toBe(currentValuesCsv(FICTIONAL_ROWS, 'existing-periods', { revenue: 'accept', cash: 'keep' }))
    await user.click(screen.getByRole('button', { name: 'Export decision receipt JSON' }))
    expect(JSON.parse(await readBlob(h.download.mock.calls[1][0]))).toEqual(buildReceipt(FICTIONAL_ROWS, 'existing-periods', { revenue: 'accept', cash: 'keep' }))
    await user.click(screen.getByRole('button', { name: 'Reset decisions' }))
    expect(accept).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByText('0 accepted · 0 kept · 6 unresolved')).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'Revenue' })).toHaveTextContent('In current export: 2024-12-31: 125,000,000 USD (SAMPLE-2024-ANNUAL)')
  })
  it('clears old decisions on scope changes and preserves the old period on additions', async () => {
    const user = userEvent.setup()
    render(<FinancialRefreshReview />)
    await user.click(screen.getByRole('button', { name: 'Accept value for Revenue' }))
    await user.click(screen.getByRole('button', { name: 'Include new periods' }))
    expect(screen.getByText('0 accepted · 0 kept · 6 unresolved')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Add period for Net income' }))
    expect(screen.getByRole('article', { name: 'Net income' })).toHaveTextContent('2024-12-31: 14,000,000 USD (SAMPLE-2024-ANNUAL); 2025-12-31: 17,000,000 USD (SAMPLE-2025-ANNUAL)')
    await user.click(screen.getByRole('button', { name: 'Existing periods' }))
    expect(screen.getByText('0 accepted · 0 kept · 6 unresolved')).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'Net income' })).toHaveTextContent('In current export: 2024-12-31: 14,000,000 USD (SAMPLE-2024-ANNUAL)')
  })
})
