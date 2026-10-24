import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import TraceToSourceDemo from '@/features/marketing/components/TraceToSourceDemo'
import { SAMPLE_TRACE } from '@/features/marketing/lib/landing-samples'
import { sourceTraceChipClass } from '@/features/filings/lib/sourceTraceChip'

const CHIP = 'Source: Quote found in filing'

describe('TraceToSourceDemo (landing evidence section)', () => {
  it('renders the live takeaway with its located passage open and a link to that passage', () => {
    render(<TraceToSourceDemo trace={SAMPLE_TRACE} />)
    expect(screen.getByText(SAMPLE_TRACE.claim, { exact: false })).toBeInTheDocument()
    expect(screen.getByText(SAMPLE_TRACE.metric)).toBeInTheDocument()

    const trigger = screen.getByRole('button', { name: CHIP })
    expect(trigger).toHaveAttribute('aria-expanded', 'true')

    const panel = screen.getByRole('group', { name: 'Source detail' })
    expect(panel.id).not.toBe('')
    expect(trigger).toHaveAttribute('aria-controls', panel.id)
    expect(panel).toHaveTextContent(SAMPLE_TRACE.excerpt)
    // The status line says what was checked: the words, found word for word.
    expect(panel).toHaveTextContent('Found in the filing, word for word.')
    expect(panel).not.toHaveTextContent(/verified/i)

    // Its label, then a visually hidden " (opens in a new tab)"; jsdom's name drops that tail's leading space.
    const link = screen.getByRole('link', { name: /^Open the passage on SEC\.gov ?\(opens in a new tab\)$/ })
    expect(link).toHaveAttribute('href', SAMPLE_TRACE.url)
    expect(SAMPLE_TRACE.url).toContain('#:~:text=')
  })

  it('claims nothing its passage does not say: every figure in the sentence is in the quote', () => {
    // The founder's review (2026-10-22): the old demo put "Verified in filing" after "13.5% to $109.2B", which the quoted
    // passage did not contain, so the label read as checking figures nobody had checked.
    const figures = SAMPLE_TRACE.claim.match(/\$?\d[\d,.]*%?/g) ?? []
    for (const figure of figures) expect(SAMPLE_TRACE.excerpt, figure).toContain(figure)
  })

  it('names no section it was not given: an inherited one is the table’s, not the passage’s', () => {
    // The live example labelled this Item 7 sentence "Item 8. Financial Statements" by inheriting the table's section.
    expect(SAMPLE_TRACE.sectionRef).not.toBe('Item 8. Financial Statements')
  })

  it('wears the product chip at rest: no selected tint (that belongs to the research pane)', () => {
    render(<TraceToSourceDemo trace={SAMPLE_TRACE} />)
    const trigger = screen.getByRole('button', { name: CHIP })
    expect(trigger.className).toBe(sourceTraceChipClass())
    expect(trigger.className).not.toContain('bg-brand-weak')
  })

  it('toggles the panel closed and open again from the chip, as its instruction says', () => {
    render(<TraceToSourceDemo trace={SAMPLE_TRACE} />)
    expect(screen.getByText(/The label opens the passage/)).toBeInTheDocument()
    const trigger = screen.getByRole('button', { name: CHIP })

    fireEvent.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('group', { name: 'Source detail' })).toBeNull()

    fireEvent.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('group', { name: 'Source detail' })).toBeInTheDocument()
  })
})
