import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import PeriodPicker, { type PeriodRange } from '@/features/analysis/components/PeriodPicker'
import { SegmentedControl } from '@/components/ui'
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
    for (const button of within(screen.getByRole('group', { name: 'Recent period presets' })).getAllByRole('button')) {
      expect(button).not.toHaveAttribute('aria-pressed')
      expect(button).not.toHaveClass('rounded-full', 'bg-brand-weak')
    }
    expect(screen.getByText('Q1 2023 – Q4 2025 · 12 quarters')).toBeInTheDocument()
    expect(screen.getByText(/† Fourth-quarter flows are calculated from annual totals\. Fiscal quarters\./)).toBeInTheDocument()
    expect(screen.getByLabelText('From')).toHaveClass('font-data', 'tabular-nums')
    expect(within(screen.getByLabelText('From')).getByRole('option', { name: 'Q4 2023 †' })).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2022Q1' } })
    expect(onRangeChange).toHaveBeenLastCalledWith({ start: '2022Q1', end: '2024Q4' })
    fireEvent.click(screen.getByRole('button', { name: 'Last 4' }))
    expect(onRangeChange).toHaveBeenLastCalledWith({ start: '2025Q1', end: '2025Q4' })
  })

  it.each([
    { available: 3, labels: ['Last 3'] },
    { available: 6, labels: ['Last 4', 'Last 6'] },
  ])('labels presets with their actual windows when only $available quarters are available', ({ available, labels }) => {
    const quarterly = coverage.quarterly.slice(0, available)
    const range = { start: quarterly[0].key, end: quarterly.at(-1)!.key }
    const onRangeChange = vi.fn()
    render(<PeriodPicker coverage={{ ...coverage, quarterly }} mode="quarterly" range={range} onModeChange={vi.fn()} onRangeChange={onRangeChange} />)
    const presets = screen.getByRole('group', { name: 'Recent period presets' })
    expect(within(presets).getAllByRole('button').map((button) => button.textContent)).toEqual(labels)
    const completeWindow = within(presets).getByRole('button', { name: `Last ${available}` })
    expect(completeWindow).not.toHaveAttribute('aria-pressed')
    expect(screen.getByText(new RegExp(` · ${available} quarters$`))).toBeInTheDocument()
    fireEvent.click(completeWindow)
    expect(onRangeChange).toHaveBeenCalledWith(range)
  })

  it('keeps unavailable annual options visible and explains a focusable unavailable mode', async () => {
    const user = userEvent.setup()
    const onModeChange = vi.fn()
    const onRangeChange = vi.fn()
    render(<PeriodPicker coverage={{ ...coverage, quarterly: [] }} mode="annual" range={{ start: 'FY2021', end: 'FY2021' }} onModeChange={onModeChange} onRangeChange={onRangeChange} />)
    expect(within(screen.getByLabelText('From')).getByRole('option', { name: 'FY2020 (insufficient data)' })).toBeDisabled()
    const presets = screen.getByRole('group', { name: 'Recent period presets' })
    expect(within(presets).getAllByRole('button')).toHaveLength(1)
    expect(within(presets).getByRole('button', { name: 'Last 1' })).not.toHaveAttribute('aria-pressed')
    expect(screen.getByText('FY2021 – FY2021 · 1 year')).toBeInTheDocument()
    fireEvent.click(within(presets).getByRole('button', { name: 'Last 1' }))
    expect(onRangeChange).toHaveBeenCalledWith({ start: 'FY2021', end: 'FY2021' })
    const quarterly = screen.getByRole('button', { name: 'Quarterly' })
    expect(quarterly).not.toBeDisabled()
    expect(quarterly).toHaveAttribute('aria-disabled', 'true')
    expect(quarterly).toHaveAccessibleDescription("Quarterly data isn't available for this company.")
    screen.getByRole('button', { name: 'Annual' }).focus()
    await user.tab()
    expect(quarterly).toHaveFocus()
    await user.keyboard('{Enter} ')
    fireEvent.click(quarterly)
    expect(onModeChange).not.toHaveBeenCalled()
  })

  it('preserves a controlled unavailable selection until the reader chooses an available mode', async () => {
    const user = userEvent.setup()
    const onModeChange = vi.fn()
    const unavailableAnnual = { ...coverage, annual: coverage.annual.map((period) => ({ ...period, has_core: false })) }
    function ControlledPicker() {
      const [mode, setMode] = useState<'annual' | 'quarterly'>('annual')
      return <PeriodPicker coverage={unavailableAnnual} mode={mode} range={null} onModeChange={(next) => { onModeChange(next); setMode(next) }} onRangeChange={vi.fn()} />
    }
    render(<ControlledPicker />)
    const annual = screen.getByRole('button', { name: 'Annual' })
    const quarterly = screen.getByRole('button', { name: 'Quarterly' })
    expect(annual).toHaveAttribute('aria-pressed', 'true')
    expect(annual).toHaveAttribute('aria-disabled', 'true')
    expect(annual).not.toBeDisabled()
    expect(annual).toHaveClass('bg-brand', 'text-white', 'dark:bg-brand-dark', 'dark:text-background-dark')
    expect(annual).toHaveAccessibleDescription("Annual data isn't available for this company.")
    expect(quarterly).toHaveAttribute('aria-pressed', 'false')
    expect(screen.queryByRole('group', { name: 'Recent period presets' })).not.toBeInTheDocument()
    expect(onModeChange).not.toHaveBeenCalled()
    annual.focus()
    await user.keyboard('{Enter} ')
    fireEvent.click(annual)
    expect(annual).toHaveFocus()
    expect(onModeChange).not.toHaveBeenCalled()
    await user.tab()
    expect(quarterly).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(onModeChange).toHaveBeenCalledExactlyOnceWith('quarterly')
    expect(quarterly).toHaveAttribute('aria-pressed', 'true')
    expect(annual).toHaveAttribute('aria-pressed', 'false')
    expect(annual).not.toHaveClass('bg-brand')
  })

  it('retains native disabled semantics for other segmented-control callers', () => {
    render(<SegmentedControl label="Other view" value="one" onChange={vi.fn()} options={[{ value: 'one', label: 'One' }, { value: 'two', label: 'Two', disabled: true }]} />)
    expect(screen.getByRole('button', { name: 'Two' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Two' })).not.toHaveAttribute('aria-disabled')
  })

  it('announces a moved endpoint for caps and crossings, then clears the message on an ordinary edit or preset', () => {
    function ControlledPicker() {
      const [range, setRange] = useState<PeriodRange>({ start: '2023Q1', end: '2025Q4' })
      return <PeriodPicker coverage={coverage} mode="quarterly" range={range} onModeChange={vi.fn()} onRangeChange={setRange} />
    }
    render(<ControlledPicker />)
    const status = screen.getByRole('status')
    expect(status).toBeEmptyDOMElement()
    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2022Q1' } })
    expect(screen.getByLabelText('To')).toHaveValue('2024Q4')
    expect(status).toHaveTextContent('To moved to Q4 2024 to keep at most 12 quarters.')
    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2025Q3' } })
    expect(status).toHaveTextContent('To moved to Q3 2025 to keep the range ordered.')
    fireEvent.change(screen.getByLabelText('To'), { target: { value: '2023Q3' } })
    expect(status).toHaveTextContent('From moved to Q3 2023 to keep the range ordered.')
    fireEvent.change(screen.getByLabelText('To'), { target: { value: '2023Q4' } })
    expect(status).toBeEmptyDOMElement()
    fireEvent.change(screen.getByLabelText('To'), { target: { value: '2022Q1' } })
    expect(status).not.toBeEmptyDOMElement()
    fireEvent.click(screen.getByRole('button', { name: 'Last 4' }))
    expect(status).toBeEmptyDOMElement()
  })
})
