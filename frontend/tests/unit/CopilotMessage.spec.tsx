import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'

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
import {
  isCopilotFairUseLimit,
  isCopilotPaywallError,
  type CopilotCitation,
} from '@/features/filings/api/copilot-api'

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

  it('shows the "Section linked" label (not "Verified") for an unverified citation', () => {
    const unverified: CopilotCitation = { ...verifiedCitation, verified: false }
    render(<CopilotMessage message={doneMessage({ citations: [unverified] })} />)
    expect(screen.getAllByText('Section linked').length).toBeGreaterThan(0)
    expect(screen.queryByText('Verified')).not.toBeInTheDocument()
    expect(screen.queryByText('Quote found in filing')).not.toBeInTheDocument()
  })

  it('renders an inline chip for a tool-figure marker, numbered by the backend like any other citation', () => {
    // The backend's unified citation-resolution pass assigns every citation (text or XBRL fact
    // alike) a plain sequential int — the "F#" shape only ever existed as an internal marker
    // between the model and the tool, never on the wire. Only `section_ref` distinguishes an XBRL
    // fact for styling purposes now.
    const factCitation: CopilotCitation = {
      n: 9,
      excerpt: 'Revenue = $391.04B USD (FY2024)',
      section_ref: 'XBRL · us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
      verified: true,
      fragment_url: 'https://www.sec.gov/filing',
    }
    const msg = doneMessage({ content: 'Revenue was $391.0B [9].', citations: [factCitation] })
    render(<CopilotMessage message={msg} />)
    const chip = screen.getByRole('link', { name: /citation 9/i })
    expect(chip).toHaveTextContent('[9]')
    expect(chip).toHaveAttribute('href', 'https://www.sec.gov/filing')
    expect(chip).toHaveAttribute('data-citation-kind', 'xbrl')
  })

  it('renders a chip for a lowercase / spaced marker ([f 1]) matched against a legacy "F1" citation id', () => {
    // Defensive: the frontend matcher still tolerates an "F#"-shaped id/marker (case + whitespace
    // insensitive) even though the backend no longer emits one, so an older cached/replayed
    // payload still renders correctly.
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

  it('scopes every matched source without trusting model section labels or losing chips', () => {
    const excerpt: CopilotCitation = { ...verifiedCitation, n: 3,
      excerpt: 'Total net sales416,161 391,035 383,285',
      section_ref: 'Item 8 — Consolidated Statements of Operations' }
    const fact: CopilotCitation = { n: 1, excerpt: 'Revenue = $416.16B USD (FY2025/FY)',
      section_ref: 'XBRL · us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
      verified: true, fragment_url: 'https://www.sec.gov/filing', fact: true }
    const labelledText: CopilotCitation = { ...excerpt, n: 4, section_ref: 'XBRL · model-labelled excerpt' }
    render(<CopilotMessage message={doneMessage({
      content: 'Total net sales were $416,161 million [1]. The statement presents sales and gross margin [3]. Another source [4].',
      citations: [fact, excerpt, labelledText], grounded: 3,
    })} />)
    // A matched fact reads "Matches filing", a matched passage "Quote found in filing" (citationVerificationLabel). Only
    // the server's fact payload (`fact`) makes a figure: [4], an excerpt the model labelled "XBRL · …", is still a quote.
    expect(screen.getAllByText('Matches filing')).toHaveLength(1)
    expect(screen.getAllByText('Quote found in filing')).toHaveLength(2)
    expect(screen.queryByText('Numeric source verified')).not.toBeInTheDocument()
    expect(screen.queryByText('Excerpt found in filing')).not.toBeInTheDocument()
    expect(screen.getByText(/does not check every claim in the answer/)).toBeInTheDocument()
    expect(screen.getAllByText(excerpt.excerpt)).toHaveLength(2)
    expect(screen.getByText('3 matched sources')).toBeInTheDocument()
    // The count is said once (ASK-14): no second "citations · source checks" tally beside it.
    expect(screen.queryByText(/source checks|\d+ citations?\b/i)).not.toBeInTheDocument()
    const textChip = screen.getByRole('link', { name: /citation 3:/i })
    expect(textChip).toHaveAttribute('href', excerpt.fragment_url)
    fireEvent.focus(textChip)
    const textPopover = screen.getByRole('group', { name: /citation 3:/i })
    expect(within(textPopover).getByText('Quote found in filing')).toBeInTheDocument()
    expect(within(textPopover).queryByText('Numeric source verified')).not.toBeInTheDocument()
    expect(within(textPopover).getByText(excerpt.excerpt)).toBeInTheDocument()
    fireEvent.focus(screen.getByRole('link', { name: /citation 1:/i }))
    const factPopover = screen.getByRole('group', { name: /citation 1:/i })
    expect(within(factPopover).getByText('Matches filing')).toBeInTheDocument()
    expect(within(factPopover).getByText(/does not check every claim/)).toBeInTheDocument()
    fireEvent.focus(screen.getByRole('link', { name: /citation 4:/i }))
    const labelledPopover = screen.getByRole('group', { name: /citation 4:/i })
    expect(within(labelledPopover).getByText('Quote found in filing')).toBeInTheDocument()
    expect(within(labelledPopover).queryByText('Matches filing')).not.toBeInTheDocument()
    expect(within(labelledPopover).getByText(/does not check every claim/)).toBeInTheDocument()
    expect(within(labelledPopover).queryByText('Numeric source verified')).not.toBeInTheDocument()
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
})

describe('CopilotMessage not-disclosed redirect', () => {
  const notDisclosed = (overrides: Partial<CopilotMessageData> = {}): CopilotMessageData => ({
    id: 'nd1',
    role: 'assistant',
    content: 'The filing does not disclose the CEO’s total compensation.',
    kind: 'not_disclosed',
    status: 'done',
    ...overrides,
  })

  it('points to the right filing type + the company’s filings for a 10-Q', () => {
    render(<CopilotMessage message={notDisclosed()} ticker="AAPL" filingType="10-Q" />)
    // 10-Q → nudge toward the 10-K for annual-only details.
    expect(
      screen.getByText(
        'Full risk factors and the business overview usually live in the company’s 10-K. Executive pay is usually in its proxy statement.',
      ),
    ).toBeInTheDocument()
    const link = screen.getByRole('link', { name: /browse AAPL’s other filings/i })
    expect(link).toHaveAttribute('href', '/company/AAPL')
  })

  it('omits the redirect link when the ticker is unknown', () => {
    render(<CopilotMessage message={notDisclosed()} ticker={null} filingType="10-K" />)
    expect(screen.getByText(/most recent 10-Q/i)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /other filings/i })).not.toBeInTheDocument()
  })

  it('offers follow-up chips on a dead end so the user has a next step', () => {
    const onFollowup = vi.fn()
    render(
      <CopilotMessage
        message={notDisclosed({ followups: ['How did annual gross margin trend?'] })}
        ticker="TSLA"
        filingType="10-K"
        onFollowup={onFollowup}
        showFollowups
      />,
    )
    expect(screen.getByText('Ask next')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /annual gross margin/i }))
    expect(onFollowup).toHaveBeenCalledWith('How did annual gross margin trend?')
  })
})

describe('CopilotMessage XBRL fact sources', () => {
  const fact: CopilotCitation = {
    n: 1,
    excerpt: 'Revenue = $391.04B USD (FY2024)',
    section_ref: 'XBRL · us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
    verified: true,
    fragment_url: null,
  }

  it('renders an XBRL fact as a dense data row (figure value + source tag)', () => {
    render(
      <CopilotMessage
        message={doneMessage({ content: 'Revenue was $391.0B [1].', citations: [fact] })}
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

describe('CopilotMessage source-check badges', () => {
  // A badge carries a verification claim, so it is 12px (text-xs, never data-xs; DESIGN_SYSTEM.md §3), and at an
  // enlarged text size it wraps its words inside the card (max-w-full, never shrink-0; #1326).
  it('both badges keep their 12px and stay inside the card at any text size', () => {
    const cited: CopilotCitation = { n: 2, excerpt: 'Services net sales increased', section_ref: 'Item 7', verified: false, fragment_url: null }
    render(
      <CopilotMessage
        message={doneMessage({ content: 'Revenue grew [1] and Services grew [2].', citations: [verifiedCitation, cited] })}
      />,
    )
    for (const badge of [screen.getByText('Quote found in filing'), screen.getByText('Section linked')]) {
      const classes = (badge.getAttribute('class') ?? '').split(/\s+/)
      expect(classes, badge.textContent ?? '').toEqual(expect.arrayContaining(['max-w-full', 'text-xs']))
      expect(classes, badge.textContent ?? '').not.toContain('shrink-0')
    }
  })
})

describe('CopilotMessage reading state', () => {
  it('shows only a calm "Reading the filing…" indicator while grounding — no tool activity', () => {
    const reading = doneMessage({
      status: 'reading',
      content: '',
      citations: undefined,
      grounded: undefined,
      kind: undefined,
    })
    render(<CopilotMessage message={reading} />)
    // The single calm indicator is the entire reading-state UI.
    expect(screen.getByText(/Reading the filing/)).toBeInTheDocument()
    // The assistant's background tool activity is never surfaced to the user.
    expect(screen.queryByText(/Looking up/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Computing/i)).not.toBeInTheDocument()
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

/**
 * statusTintsOnlyForStatus: a plan gate (a spent free allowance, a Pro-only 403, the Pro fair-use 429) is
 * a plan fact, not a failure. It renders in the quiet answer card, role="status", with no status-palette
 * token anywhere in it (error, warning, success, info, loss or gain: a "limit reached" card that turns amber
 * regresses as surely as one that turns red); the error tint and role="alert" stay for real failures
 * (DESIGN_SYSTEM.md "Ask answer"; ASK-10). The sentences are the backend's own (backend/app/dependencies.py,
 * routers/summaries.py).
 */
describe('statusTintsOnlyForStatus: the Copilot plan card', () => {
  const TASTE_SPENT = "You've used your 3 free Copilot questions. Upgrade to Pro to access this feature."
  const FAIR_USE =
    "You've reached this month's fair-use limit of 1000 Copilot questions. It resets at the start of next month."
  const errorMessage = (error: string): CopilotMessageData => ({ id: 'e1', role: 'assistant', content: '', status: 'error', error })
  /** The class tokens in a subtree that paint with one of the given status inks, through any variant prefix. */
  const tokensOf = (root: HTMLElement, palette: string) =>
    [root, ...Array.from(root.querySelectorAll<HTMLElement>('*'))]
      .flatMap((el) => (el.getAttribute('class') ?? '').split(/\s+/))
      .filter((token) =>
        new RegExp(String.raw`(?:^|:)(?:text|bg|border|ring|shadow|outline|divide|fill|stroke|decoration|from|via|to)-(?:${palette})\b`).test(token),
      )
  const statusTokens = (root: HTMLElement) => tokensOf(root, 'error|warning|success|info|loss|gain')
  const errorTokens = (root: HTMLElement) => tokensOf(root, 'error')

  it('classifies the backend sentences: the fair-use 429 is a plan gate with no upgrade', () => {
    expect(isCopilotPaywallError(TASTE_SPENT)).toBe(true)
    expect(isCopilotFairUseLimit(TASTE_SPENT)).toBe(false)
    expect(isCopilotPaywallError(FAIR_USE)).toBe(true)
    expect(isCopilotFairUseLimit(FAIR_USE)).toBe(true)
    expect(isCopilotPaywallError('The answer could not be completed. Please try again.')).toBe(false)
  })

  it('a spent allowance is the quiet card with the server sentence and Upgrade to Pro', () => {
    const onUpgrade = vi.fn()
    render(<CopilotMessage message={errorMessage(TASTE_SPENT)} isPaywallError onUpgrade={onUpgrade} onRetry={vi.fn()} />)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    const card = screen.getByRole('status')
    expect(card).toHaveTextContent(TASTE_SPENT)
    expect(statusTokens(card)).toEqual([])
    fireEvent.click(within(card).getByRole('button', { name: 'Upgrade to Pro' }))
    expect(onUpgrade).toHaveBeenCalledTimes(1)
    expect(within(card).queryByRole('button', { name: /try again/i })).not.toBeInTheDocument()
  })

  it('the Pro fair-use cap is the same quiet card, with no button (upgrading cannot lift it)', () => {
    render(<CopilotMessage message={errorMessage(FAIR_USE)} isPaywallError onUpgrade={vi.fn()} onRetry={vi.fn()} />)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    const card = screen.getByRole('status')
    expect(card).toHaveTextContent(FAIR_USE)
    expect(statusTokens(card)).toEqual([])
    expect(within(card).queryByRole('button')).not.toBeInTheDocument()
  })

  // A status region announces text added to it, never text it was created with. The rail turns the reading card into
  // the plan card in place, so the sentence must land in a region that already existed: the reading card itself.
  it('the plan card is announced: its sentence lands in the status region the reading card already was', () => {
    const reading: CopilotMessageData = { id: 'e1', role: 'assistant', content: '', status: 'reading' }
    const { rerender } = render(<CopilotMessage message={reading} onUpgrade={vi.fn()} onRetry={vi.fn()} />)
    const region = screen.getByRole('status')
    expect(region).toHaveTextContent(/Reading the filing/)
    rerender(<CopilotMessage message={errorMessage(TASTE_SPENT)} isPaywallError onUpgrade={vi.fn()} onRetry={vi.fn()} />)
    expect(screen.getByRole('status')).toBe(region)
    expect(region).toHaveTextContent(TASTE_SPENT)
  })

  it('a real failure keeps the error tint, role="alert" and Retry', () => {
    render(<CopilotMessage message={errorMessage('The answer could not be completed. Please try again.')} onRetry={vi.fn()} />)
    const bubble = screen.getByRole('alert')
    expect(errorTokens(bubble).length).toBeGreaterThan(0)
    expect(within(bubble).getByRole('button', { name: /try again/i })).toBeInTheDocument()
  })
})
