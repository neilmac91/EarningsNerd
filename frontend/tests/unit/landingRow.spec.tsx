import { render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/analytics', () => ({ default: { homepageSectionViewed: vi.fn() } }))

import LandingRow from '@/features/marketing/components/LandingRow'

/**
 * The landing's ruled row (D-045; features/marketing/components/LandingRow.tsx), the one shape every section after
 * the hero takes (tests/unit/landing-sections-mounted.spec.ts holds the page to it): a section named by its h2, a
 * label column holding the number, the title and the one line, and the content beside it. The number is the
 * `landing-row` counter in CSS (app/page.tsx resets it on <main>), so a self-omitting section takes none;
 * tests/e2e/home-page-unauthenticated.spec.ts reads the painted numbers on the built page (01, 02, … with no gap).
 * The columns open at 64rem at the reader's text size, over a one-column base.
 */
describe('LandingRow', () => {
  it('is a section named by its h2, with the number, the title and the line in the label column beside the content', () => {
    render(
      <LandingRow id="pricing" title="Pricing" line="Summaries are generated once per filing and shared." impression="pricing">
        <p>The content</p>
      </LandingRow>,
    )
    const section = screen.getByRole('region', { name: 'Pricing' })
    expect(section.id).toBe('pricing')
    expect(section).toHaveClass('[counter-increment:landing-row]')
    const heading = within(section).getByRole('heading', { level: 2, name: 'Pricing' })
    expect(heading.id).toBe('pricing-h')

    const label = heading.parentElement!
    const number = label.querySelector('[data-landing-row-number]')!
    expect(number).toHaveAttribute('aria-hidden', 'true')
    expect(number).toHaveClass('before:content-[counter(landing-row,decimal-leading-zero)]', 'font-data', 'tabular-nums')
    // Number, title, line: in that order, in the label column.
    expect([...label.children].map((child) => child.tagName)).toEqual(['SPAN', 'H2', 'P'])
    expect(label.lastElementChild).toHaveTextContent('Summaries are generated once per filing and shared.')

    // The rule and the two columns: a hairline across the row, one column below 64rem, the 14rem label column above it.
    const grid = label.parentElement!
    expect(grid).toHaveClass('border-t', 'grid-cols-1', '[@media(min-width:64rem)]:grid-cols-[14rem_minmax(0,1fr)]')
    expect(grid.lastElementChild).toHaveTextContent('The content')
  })

  it('leaves the line out when a section has none', () => {
    render(
      <LandingRow id="claims" title="What a summary does" impression="measured_claims">
        <p>The content</p>
      </LandingRow>,
    )
    const heading = screen.getByRole('heading', { level: 2, name: 'What a summary does' })
    expect([...heading.parentElement!.children].map((child) => child.tagName)).toEqual(['SPAN', 'H2'])
  })
})
