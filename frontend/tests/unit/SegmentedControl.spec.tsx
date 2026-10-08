import React, { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { SegmentedControl, type SegmentedControlSize, type SegmentedOption } from '@/components/ui/SegmentedControl'

const FORMS: SegmentedOption<string>[] = [
  { value: 'all', label: 'All' },
  { value: '10-K', label: '10-K', mono: true },
  { value: '10-Q', label: '10-Q', mono: true },
]

function Harness({
  onChange = () => {},
  ...rest
}: {
  onChange?: (value: string) => void
  fullWidth?: boolean
  size?: SegmentedControlSize
}) {
  const [value, setValue] = useState('all')
  return (
    <SegmentedControl
      label="Filter by form"
      options={FORMS}
      value={value}
      onChange={(next) => {
        setValue(next)
        onChange(next)
      }}
      {...rest}
    />
  )
}

describe('SegmentedControl', () => {
  it('is a labelled group of pressed buttons, and only a change of option calls onChange', () => {
    const onChange = vi.fn()
    render(<Harness onChange={onChange} />)
    expect(screen.getByRole('group', { name: 'Filter by form' })).toBeInTheDocument()
    const all = screen.getByRole('button', { name: 'All' })
    const tenK = screen.getByRole('button', { name: '10-K' })
    expect(all).toHaveAttribute('aria-pressed', 'true')
    expect(tenK).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(all)
    expect(onChange).not.toHaveBeenCalled()
    fireEvent.click(tenK)
    expect(onChange).toHaveBeenCalledWith('10-K')
    expect(tenK).toHaveAttribute('aria-pressed', 'true')
    expect(all).toHaveAttribute('aria-pressed', 'false')
  })

  it('sets code labels in the data face and sizes adaptive segments 36px below sm, 26px from sm', () => {
    render(<Harness size="adaptive" />)
    expect(screen.getByRole('button', { name: '10-K' }).className).toContain('font-data')
    expect(screen.getByRole('button', { name: 'All' }).className).not.toContain('font-data')
    const segment = screen.getByRole('button', { name: 'All' }).className
    expect(segment).toContain('h-9')
    expect(segment).toContain('sm:h-[26px]')
  })

  // A 10-K/10-Q filer with amendments offers six options (All, 10-K, 10-Q, 10-K/A, 10-Q/A, …); a 320px card
  // holds four in one row. A full-width group wraps below sm so no filter is clipped or scrolled out of reach
  // (Codex review on #1133); from sm it is one auto-width row, as the calendar's Week/Month switch always is.
  it('a full-width group stretches and wraps its segments below sm, and is one auto-width row from sm', () => {
    render(<Harness fullWidth />)
    const group = screen.getByRole('group', { name: 'Filter by form' }).className
    for (const cls of ['w-full', 'flex-wrap', 'sm:w-auto', 'sm:flex-nowrap']) expect(group).toContain(cls)
    expect(screen.getByRole('button', { name: 'All' }).className).toContain('flex-1')
  })

  it('a default group never wraps', () => {
    render(<Harness />)
    expect(screen.getByRole('group', { name: 'Filter by form' }).className).not.toContain('flex-wrap')
  })
})
