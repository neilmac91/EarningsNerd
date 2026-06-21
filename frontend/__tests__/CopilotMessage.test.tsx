import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

// Mirror the existing AskCopilotRail test's mock for next/link (CopilotMessage uses it in the
// error/paywall branch).
import React from 'react'
import { vi } from 'vitest'

vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

import CopilotMessage, {
  type CopilotMessageData,
} from '@/features/filings/components/copilot/CopilotMessage'
import type { CopilotCitation } from '@/features/filings/api/copilot-api'

const verifiedCitation: CopilotCitation = {
  n: 1,
  excerpt: 'Revenue increased to $94.0B',
  section_ref: 'Item 7 — MD&A',
  verified: true,
  fragment_url: 'https://www.sec.gov/x#:~:text=Revenue',
}

function doneMessage(overrides: Partial<CopilotMessageData> = {}): CopilotMessageData {
  return {
    id: 'm1',
    role: 'assistant',
    content: 'Revenue grew strongly [1].',
    citations: [verifiedCitation],
    grounded: 1,
    kind: 'answer',
    status: 'done',
    ...overrides,
  }
}

describe('CopilotMessage citation chips', () => {
  it('renders a chip for [1] as an anchor to the fragment_url', () => {
    render(<CopilotMessage message={doneMessage()} />)
    // The inline chip is the anchor whose accessible name is "Citation 1: ...".
    const chip = screen.getByRole('link', { name: /citation 1: item 7 — md&a/i })
    expect(chip).toHaveAttribute('href', 'https://www.sec.gov/x#:~:text=Revenue')
    expect(chip).toHaveAttribute('target', '_blank')
    expect(chip).toHaveTextContent('[1]')
  })

  it('shows the verbatim excerpt text', () => {
    render(<CopilotMessage message={doneMessage()} />)
    // Appears in both the chip popover and the Sources list.
    expect(screen.getAllByText('Revenue increased to $94.0B').length).toBeGreaterThan(0)
  })

  it('shows the "Cited" label (not "Verified") for an unverified citation', () => {
    const unverified: CopilotCitation = { ...verifiedCitation, verified: false }
    render(<CopilotMessage message={doneMessage({ citations: [unverified] })} />)
    expect(screen.getAllByText('Cited').length).toBeGreaterThan(0)
    expect(screen.queryByText('Verified')).not.toBeInTheDocument()
    expect(screen.queryByText('Verified in filing')).not.toBeInTheDocument()
  })

  it('renders an inline chip for a tool-figure [F1] marker', () => {
    const factCitation: CopilotCitation = {
      n: 'F1',
      excerpt: 'Revenue = $391.04B USD (FY2024)',
      section_ref: 'XBRL · us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
      verified: true,
      fragment_url: 'https://www.sec.gov/filing',
    }
    const msg = doneMessage({ content: 'Revenue was $391.0B [F1].', citations: [factCitation] })
    render(<CopilotMessage message={msg} />)
    const chip = screen.getByRole('link', { name: /citation f1/i })
    expect(chip).toHaveTextContent('[F1]')
    expect(chip).toHaveAttribute('href', 'https://www.sec.gov/filing')
  })

  it('renders a chip for a lowercase / spaced marker ([f 1]) and normalizes its display', () => {
    const factCitation: CopilotCitation = {
      n: 'F1',
      excerpt: 'Revenue = $391.04B USD (FY2024)',
      section_ref: 'XBRL · us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
      verified: true,
      fragment_url: 'https://www.sec.gov/filing',
    }
    const msg = doneMessage({ content: 'Revenue was $391.0B [f 1].', citations: [factCitation] })
    render(<CopilotMessage message={msg} />)
    const chip = screen.getByRole('link', { name: /citation f1/i })
    expect(chip).toHaveTextContent('[F1]') // normalized to the canonical marker
  })

  it('leaves an unmatched [2] as plain text (no chip / no anchor)', () => {
    const msg = doneMessage({ content: 'A claim with no citation [2].' })
    render(<CopilotMessage message={msg} />)
    // The literal marker survives somewhere in the prose.
    expect(screen.getByText(/\[2\]/)).toBeInTheDocument()
    // And there is no citation chip / anchor for [2].
    expect(screen.queryByRole('link', { name: /citation 2/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /citation 2/i })).not.toBeInTheDocument()
  })

  it('does not inject chips while streaming (markers stay plain text)', () => {
    const streaming = doneMessage({ status: 'streaming', content: 'Revenue grew [1]', citations: undefined })
    render(<CopilotMessage message={streaming} />)
    expect(screen.getByText(/\[1\]/)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /citation 1/i })).not.toBeInTheDocument()
  })
})

describe('CopilotMessage XBRL fact sources', () => {
  const fact: CopilotCitation = {
    n: 'F1',
    excerpt: 'Revenue = $391.04B USD (FY2024)',
    section_ref: 'XBRL · us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
    verified: true,
    fragment_url: null,
  }

  it('renders an XBRL fact as a dense data row (figure value + source tag)', () => {
    render(
      <CopilotMessage
        message={doneMessage({ content: 'Revenue was $391.0B [F1].', citations: [fact] })}
      />,
    )
    // The figure is surfaced as the row value (not the prose-excerpt treatment)...
    expect(screen.getByText('Revenue = $391.04B USD (FY2024)')).toBeInTheDocument()
    // ...and the raw XBRL tag is shown as the source beneath it.
    expect(
      screen.getByText('us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'),
    ).toBeInTheDocument()
  })
})

describe('CopilotMessage activity ticker', () => {
  it('shows in-progress and completed steps while reading', () => {
    const reading = doneMessage({
      status: 'reading',
      content: '',
      citations: undefined,
      grounded: undefined,
      kind: undefined,
      steps: [
        { label: 'Looking up revenue', done: true, ok: true },
        { label: 'Computing gross margin', done: false, ok: true },
      ],
    })
    render(<CopilotMessage message={reading} />)
    expect(screen.getByText('Looking up revenue')).toBeInTheDocument()
    // In-progress step shows an ellipsis affordance.
    expect(screen.getByText(/Computing gross margin/)).toBeInTheDocument()
    // The generic "Reading the filing…" line is replaced by the work ticker.
    expect(screen.queryByText(/Reading the filing/)).not.toBeInTheDocument()
  })

  it('hides the ticker once the answer is done', () => {
    const done = doneMessage({
      steps: [{ label: 'Looking up revenue', done: true, ok: true }],
    })
    render(<CopilotMessage message={done} />)
    expect(screen.queryByText('Looking up revenue')).not.toBeInTheDocument()
  })
})

describe('CopilotMessage follow-up chips', () => {
  it('renders follow-ups and calls onFollowup when one is tapped', () => {
    const onFollowup = vi.fn()
    const msg = doneMessage({ followups: ['How did margins trend?', 'What are the top risks?'] })
    render(<CopilotMessage message={msg} showFollowups onFollowup={onFollowup} />)

    expect(screen.getByText('Ask next')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /how did margins trend/i }))
    expect(onFollowup).toHaveBeenCalledWith('How did margins trend?')
  })

  it('does not render follow-ups unless showFollowups is set', () => {
    const msg = doneMessage({ followups: ['Q?'] })
    render(<CopilotMessage message={msg} showFollowups={false} onFollowup={() => {}} />)
    expect(screen.queryByText('Ask next')).not.toBeInTheDocument()
  })
})
