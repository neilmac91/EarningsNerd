import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import PeriodPicker from '@/features/analysis/components/PeriodPicker'
import type { AnalysisCoverage } from '@/features/analysis/api/analysis-api'

const coverage: AnalysisCoverage = {
  ticker: 'TST', company_name: 'Test', supported: true, reason: null, syncing: false, synced_at: null,
  limits: { annual: 10, quarterly: 12 },
  annual: [{ key: 'FY2020', fiscal_year: 2020, period_end: '2020-12-31', has_core: false },
    { key: 'FY2021', fiscal_year: 2021, period_end: '2021-12-31', has_core: true }],
  quarterly: Array.from({ length: 16 }, (_, index) => {
    const fiscal_year = 2022 + Math.floor(index / 4)
    const fiscal_period = `Q${index % 4 + 1}` as 'Q1' | 'Q2' | 'Q3' | 'Q4'
    return { key: `${fiscal_year}${fiscal_period}`, fiscal_year, fiscal_period, period_end: `${fiscal_year}-12-31`, derived: fiscal_period === 'Q4' }
  }),
}

describe('PeriodPicker controls', () => {
  it('uses named range selects and presets without a button per coverage period', () => {
    const onRangeChange = vi.fn()
    render(<PeriodPicker coverage={coverage} mode="quarterly" range={{ start: '2023Q1', end: '2025Q4' }} onModeChange={vi.fn()} onRangeChange={onRangeChange} />)
    expect(screen.getAllByRole('combobox')).toHaveLength(2)
    expect(screen.getAllByRole('button')).toHaveLength(5)
    expect(screen.getByRole('button', { name: 'Last 12' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText(/12 quarters · Q1 2023 – Q4 2025 · 3 calculated Q4 columns/)).toBeInTheDocument()
    expect(within(screen.getByLabelText('From')).getByRole('option', { name: 'Q4 2023 †' })).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2022Q1' } })
    expect(onRangeChange).toHaveBeenLastCalledWith({ start: '2022Q1', end: '2024Q4' })
    fireEvent.click(screen.getByRole('button', { name: 'Last 4' }))
    expect(onRangeChange).toHaveBeenLastCalledWith({ start: '2025Q1', end: '2025Q4' })
  })

  it('keeps unavailable annual options visible and refuses a mode with no quarters', () => {
    const onModeChange = vi.fn()
    render(<PeriodPicker coverage={{ ...coverage, quarterly: [] }} mode="annual" range={{ start: 'FY2021', end: 'FY2021' }} onModeChange={onModeChange} onRangeChange={vi.fn()} />)
    expect(within(screen.getByLabelText('From')).getByRole('option', { name: 'FY2020 (insufficient data)' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Quarterly' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Quarterly' }))
    expect(onModeChange).not.toHaveBeenCalled()
  })
})
