import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { SummaryBlocks } from '@/features/summaries/components/SummaryBlocks'
import type { ChangeReport, RenderedSection, Summary } from '@/features/summaries/api/summaries-api'

// The single structured web surface (T2): one renderer per Block.kind, a sticky TOC whose anchors
// match every Section.id, the metrics section rendered from server-computed deltas, and the risks
// section rendered with its Trace-to-Source provenance — with NO field-name scaffolding leaking.
const sections: RenderedSection[] = [
  {
    id: 'executive-assessment',
    title: 'Executive Assessment',
    blocks: [
      { kind: 'paragraph', text: 'Revenue surged on data-center demand.' },
      { kind: 'bullets', text: 'Highlights', items: ['Revenue up 85% YoY', 'Gross margin expanded'] },
    ],
  },
  {
    id: 'financial-highlights',
    title: 'Financial Highlights',
    blocks: [
      {
        kind: 'metrics',
        headers: ['Metric', 'Current Period', 'Prior Period', 'Change', 'Investor Takeaway'],
        rows: [['Revenue', '$81.6B', '$44.1B', '+85.0%', 'Data-center growth.']],
        metric_rows: [
          {
            metric: 'Revenue',
            current_period: '$81.6B',
            prior_period: '$44.1B',
            commentary: 'Data-center growth.',
            change_display: '+85.0%',
            change_direction: 'up',
            change_tone: 'gain',
          },
        ],
      },
    ],
  },
  {
    id: 'management-strategy-execution',
    title: 'Management Strategy & Execution',
    blocks: [{ kind: 'quote', text: 'We see unprecedented demand.', speaker: 'CEO' }],
  },
  {
    id: 'business-segment-analysis',
    title: 'Business Segment Analysis',
    blocks: [
      {
        kind: 'table',
        headers: ['Segment', 'Revenue', 'Change', 'Commentary'],
        rows: [['Data Center', '$60B', '+120%', 'AI buildout']],
      },
    ],
  },
  {
    id: 'forward-outlook-investment-implications',
    title: 'Forward Outlook & Investment Implications',
    blocks: [{ kind: 'callout', label: 'Red flag', text: 'Receivables outpaced sales.' }],
  },
  {
    id: 'investment-risks-concerns',
    title: 'Investment Risks & Concerns',
    blocks: [
      {
        kind: 'table',
        headers: ['#', 'Risk', 'Supporting Evidence'],
        rows: [['1', 'Supply concentration', 'Item 1A']],
      },
    ],
  },
]

const summary = {
  business_overview: 'x',
  raw_summary: {
    risk_source_context_version: 1,
    sections: {
      risks: [
        {
          summary: 'Filing excerpt',
          supporting_evidence: 'We are substantially dependent on TSMC for wafer supply.',
          source_url: 'https://www.sec.gov/Archives/edgar/data/1/2/3',
          source_verified: true,
          source_section_ref: 'Filing excerpt',
        },
      ],
      _risk_source_projection: { version: 1, verified_count: 1, withheld_count: 0 },
    },
  },
} as unknown as Summary

describe('SummaryBlocks', () => {
  it('dispatches each block kind to its renderer', () => {
    render(<SummaryBlocks sections={sections} summary={summary} />)

    // paragraph + bullets
    expect(screen.getByText('Revenue surged on data-center demand.')).toBeInTheDocument()
    expect(screen.getByText('Revenue up 85% YoY')).toBeInTheDocument()
    // metrics → FinancialMetricsTable: server-computed change chip rendered verbatim (no client math).
    // The rows render twice — the md table and the phone cards are both in the DOM, switched by CSS
    // that jsdom does not apply (vitest css: false) — so each string is found in both layouts.
    expect(screen.getAllByText('+85.0%')).toHaveLength(2)
    expect(screen.getAllByText('Data-center growth.')).toHaveLength(2)
    // quote + speaker
    expect(screen.getByText(/We see unprecedented demand/)).toBeInTheDocument()
    expect(screen.getByText(/CEO/)).toBeInTheDocument()
    // generic table (segments)
    expect(screen.getByText('Data Center')).toBeInTheDocument()
    // callout
    expect(screen.getByText('Receivables outpaced sales.')).toBeInTheDocument()
  })

  it('sets whole-figure columns in the data face and keeps commentary that opens with a figure as prose', () => {
    const segments: RenderedSection[] = [
      {
        id: 'business-segment-analysis',
        title: 'Business Segment Analysis',
        blocks: [
          {
            kind: 'table',
            headers: ['Segment', 'Revenue', 'Revenue Change', 'Commentary'],
            // Older retained summaries prefix segment commentary with a machine margin.
            rows: [
              ['iPhone', '$46.2B', '+6.1%', '41% operating margin — higher net sales of iPhone'],
              ['Services', '$26.6B', '-', '$1.2B of the increase came from advertising'],
            ],
          },
        ],
      },
    ]
    render(<SummaryBlocks sections={segments} summary={summary} />)
    expect(screen.getByRole('columnheader', { name: 'Revenue' })).toHaveClass('text-right')
    expect(screen.getByText('$46.2B')).toHaveClass('text-right', 'font-data', 'whitespace-nowrap')
    expect(screen.getByText('+6.1%')).toHaveClass('text-right')
    expect(screen.getByRole('columnheader', { name: 'Commentary' })).toHaveClass('text-left')
    expect(screen.getByText(/41% operating margin/)).not.toHaveClass('text-right')
    expect(screen.getByText(/41% operating margin/)).not.toHaveClass('whitespace-nowrap')
  })

  it('builds a table of contents whose anchors match every section id', () => {
    const { container } = render(<SummaryBlocks sections={sections} summary={summary} />)
    for (const section of sections) {
      expect(container.querySelector(`a[href="#${section.id}"]`)).not.toBeNull()
      // The section itself is an anchor target with the matching id.
      expect(container.querySelector(`#${section.id}`)).not.toBeNull()
    }
  })

  it('renders the risks section with its evidence + trace-to-source provenance', () => {
    render(<SummaryBlocks sections={sections} summary={summary} />)
    // An evidence row (critique P-03): the excerpt's opening clause heads it, one level under the
    // section's h2, and the excerpt itself sits in a blockquote.
    expect(
      screen.getByRole('heading', { level: 3, name: 'We are substantially dependent on TSMC for wafer supply' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/substantially dependent on TSMC/, { selector: 'blockquote' })).toBeInTheDocument()
    // source_verified: true → the shared SourceTrace renders the "Verified in filing" affordance.
    expect(screen.getByText(/Verified in filing/i)).toBeInTheDocument()
  })

  it('leaks no field-name scaffolding', () => {
    render(<SummaryBlocks sections={sections} summary={summary} />)
    for (const leak of [/Headline:/, /Key Points:/, /Tone:/, /Source Section Ref:/, /Guidance:/]) {
      expect(screen.queryByText(leak)).not.toBeInTheDocument()
    }
  })

  it('renders Trace-to-Source chips on cited quotes, footnotes, and metric takeaways (T4)', () => {
    const verified = (ref: string) => ({
      excerpt: 'a verbatim line from the filing',
      section_ref: ref,
      verified: true,
      fragment_url: `https://www.sec.gov/x.htm#:~:text=${encodeURIComponent(ref)}`,
    })
    const cited: RenderedSection[] = [
      {
        id: 'forward-signals',
        title: 'Forward Signals',
        blocks: [{ kind: 'quote', text: 'We expect double-digit growth.', speaker: 'CEO', evidence: verified('Item 7. MD&A') }],
      },
      {
        id: 'results-that-matter',
        title: 'Results That Matter',
        blocks: [
          {
            kind: 'metrics',
            headers: ['Metric', 'Current Period', 'Investor Takeaway'],
            rows: [['Revenue', '$81.6B', 'Services strength']],
            metric_rows: [
              { metric: 'Revenue', current_period: '$81.6B', prior_period: '', commentary: 'Services strength', commentary_evidence: verified('Item 8') },
            ],
          },
        ],
      },
      {
        id: 'notable-footnotes',
        title: 'Notable Footnotes',
        blocks: [
          {
            kind: 'table',
            headers: ['Item', 'Impact'],
            rows: [['SBC', 'Expense over vesting'], ['Litigation', 'Contingent']],
            // First footnote verified; second uncited (null) → no chip.
            row_evidence: [verified('Note 5'), null],
          },
        ],
      },
    ]
    render(<SummaryBlocks sections={cited} summary={summary} />)
    // One chip each for the quote, the metric takeaway, and the first (only cited) footnote. The
    // metric takeaway's chip also renders in the phone-card layout, which jsdom cannot hide
    // (vitest css: false); count it once by leaving the card copies out.
    const chips = screen.getAllByText(/Verified in filing/i).filter((el) => !el.closest('[data-metrics-layout="cards"]'))
    expect(chips).toHaveLength(3)
  })

  it('shows an empty state when there are no sections', () => {
    render(<SummaryBlocks sections={[]} summary={summary} />)
    expect(screen.getByText(/No summary found/i)).toBeInTheDocument()
  })

  it('renders tone as a header Badge, not a prose sentence', () => {
    const toneSections: RenderedSection[] = [
      {
        id: 'executive-assessment',
        title: 'Executive Assessment',
        tone: 'positive',
        blocks: [{ kind: 'paragraph', text: 'Record quarter driven by AI demand.' }],
      },
    ]
    render(<SummaryBlocks sections={toneSections} summary={summary} />)
    expect(screen.getByText('positive')).toBeInTheDocument()
    expect(screen.queryByText(/tone was/i)).not.toBeInTheDocument()
  })

  it('renders a compact mobile jump-nav whose anchors mirror the desktop TOC', () => {
    render(<SummaryBlocks sections={sections} summary={summary} />)
    const mobileNav = screen.getByRole('navigation', { name: 'Jump to section' })
    const desktopNav = screen.getByRole('navigation', { name: 'Summary sections' })
    for (const section of sections) {
      expect(mobileNav.querySelector(`a[href="#${section.id}"]`)).not.toBeNull()
      expect(desktopNav.querySelector(`a[href="#${section.id}"]`)).not.toBeNull()
    }
    // Chips are real anchors (keyboard-reachable, no onChange navigation), one per section.
    expect(mobileNav.querySelectorAll('a')).toHaveLength(sections.length)
  })

  it('keeps the phone nav out of the sections\' spaced stack, so section 01 lines up with the TOC', () => {
    // Tailwind 3's space-y margins every child after a sibling without the hidden attribute, and the
    // nav is only display:none at lg, so inside the stack it pushed section 01 down by the gap.
    render(<SummaryBlocks sections={sections} summary={summary} />)
    const first = document.getElementById(sections[0].id) as HTMLElement
    const stack = first.parentElement as HTMLElement
    expect(stack.className).toMatch(/(^|\s)space-y-11(\s|$)/)
    expect(stack.firstElementChild).toBe(first)
    const phoneNav = screen.getByRole('navigation', { name: 'Jump to section' })
    expect(stack.contains(phoneNav)).toBe(false)
    // Out of the stack, the nav carries the stack's gap itself, so phones keep the space above 01.
    expect(phoneNav.className).toMatch(/(^|\s)mb-11(\s|$)/)
  })

  it('heads each risk with its own excerpt, never a model-authored label', () => {
    const riskSections: RenderedSection[] = [
      { id: 'investment-risks-concerns', role: 'risks', title: 'Investment Risks & Concerns', blocks: [] },
    ]
    const untitled = {
      business_overview: 'x',
      raw_summary: {
        risk_source_context_version: 1,
        sections: {
          risks: [
            // A model title that slipped through is never shown: the heading is the filing's words.
            {
              summary: 'Filing excerpt',
              title: 'Customer concentration',
              supporting_evidence: 'Our suppliers are concentrated in Asia; a disruption would delay shipments.',
            },
            { summary: 'Filing excerpt', supporting_evidence: 'Currency movements reduce reported revenue.' },
            { summary: 'Filing excerpt', supporting_evidence: 'Currency movements reduce reported revenue: the euro fell.' },
          ],
          _risk_source_projection: { version: 1, verified_count: 3, withheld_count: 0 },
        },
      },
    } as unknown as Summary
    render(<SummaryBlocks sections={riskSections} summary={untitled} />)
    const section = screen.getByRole('region', { name: 'Investment Risks & Concerns' })
    const headings = within(section).getAllByRole('heading', { level: 3 }).map((h) => h.textContent)
    expect(headings).toEqual([
      'Our suppliers are concentrated in Asia',
      'Currency movements reduce reported revenue',
      'Currency movements reduce reported revenue (2)',
    ])
    expect(screen.queryByText(/Customer concentration|FX headwinds|Filing excerpt \d/)).not.toBeInTheDocument()
    // No stripe card and no trend glyph: the rows are one hairline list.
    expect(section.querySelector('svg')).toBeNull()
    expect(screen.getByText('3 of 3 excerpts located in the filing text')).toBeInTheDocument()
  })

  it('matches the risks section by role and renders only owner-projected excerpts', () => {
    const riskSections: RenderedSection[] = [
      { id: 'investment-risks-concerns', role: 'risks', title: 'Investment Risks & Concerns', blocks: [] },
    ]
    const withPlaceholder = {
      business_overview: 'x',
      raw_summary: {
        risk_source_context_version: 1,
        sections: {
          risks: [
            { summary: 'Filing excerpt', supporting_evidence: 'Item 1A: verbatim quote.' },
          ],
          _risk_source_projection: { version: 1, verified_count: 1, withheld_count: 1 },
        },
      },
    } as unknown as Summary
    render(<SummaryBlocks sections={riskSections} summary={withPlaceholder} />)
    expect(screen.getByText('Item 1A: verbatim quote.')).toBeInTheDocument()
    expect(
      screen.getByText('1 of 2 excerpts located in the filing text · 1 withheld because the evidence could not be matched'),
    ).toBeInTheDocument()
    expect(screen.queryByText('Vague.')).not.toBeInTheDocument()
  })

  // ---- 2026-10 critique: the quiet ledger (P-05, P-07, P-08) ----

  it('titles every section as an h2 with the index its table-of-contents entry carries', () => {
    render(<SummaryBlocks sections={sections} summary={summary} />)
    const toc = screen.getByRole('navigation', { name: 'Summary sections' })
    const entries = within(toc).getAllByRole('link')
    expect(entries).toHaveLength(sections.length)
    sections.forEach((section, i) => {
      const index = String(i + 1).padStart(2, '0')
      expect(entries[i]).toHaveTextContent(`${index}${section.title}`)
      const region = screen.getByRole('region', { name: section.title })
      expect(region.id).toBe(section.id)
      expect(within(region).getByRole('heading', { level: 2, name: section.title })).toHaveClass('text-xl')
      expect(region).toHaveTextContent(new RegExp(`^${index}`))
    })
    // On this page is a sentence-case label, not an uppercase eyebrow.
    expect(within(toc).getByText('On this page')).not.toHaveClass('uppercase')
  })

  it('sets the sections on the page, with no card around them', () => {
    const { container } = render(<SummaryBlocks sections={sections} summary={summary} />)
    for (const section of container.querySelectorAll('section')) {
      expect(section.className).not.toMatch(/\b(bg-panel|shadow-e|rounded)/)
    }
  })

  it('renders subheadings as 14/600 headings, never uppercase eyebrows', () => {
    const withSub: RenderedSection[] = [
      { id: 'risk-factors', title: 'Risk factors', blocks: [{ kind: 'subheading', text: 'Supply chain' }] },
    ]
    render(<SummaryBlocks sections={withSub} summary={summary} />)
    const sub = screen.getByRole('heading', { level: 3, name: 'Supply chain' })
    expect(sub).toHaveClass('text-sm', 'font-semibold')
    expect(sub).not.toHaveClass('uppercase')
  })

  it('renders a callout as an inset well whose tone lives in the label word', () => {
    render(<SummaryBlocks sections={sections} summary={summary} />)
    const label = screen.getByText('Red flag')
    expect(label).toHaveClass('text-warning-light')
    const well = label.parentElement!
    expect(well.className).toContain('rounded')
    expect(well.className).not.toMatch(/border-l-\d|shadow-e/)
    expect(well).toHaveTextContent('Receivables outpaced sales.')
  })

  it('adds What changed as the section after the metrics, numbered and listed like the rest', () => {
    const report: ChangeReport = {
      has_prior: true,
      comparison_basis: 'Year over year',
      prior_filing: { filing_id: 7, filing_type: '10-K', filing_date: '2021-10-29', period_end_date: '2021-09-25' },
      metrics: {
        headline: 'Revenue up 7.8%',
        items: [
          { metric: 'revenue', label: 'Revenue', direction: 'up', pct: 7.8, current: 394_328e6, prior: 365_817e6, display: '+7.8%', tone: 'gain' },
        ],
        data_quality: 'ok',
      },
      risks: null,
      key_changes: null,
      has_changes: true,
    }
    render(<SummaryBlocks sections={sections} summary={summary} whatChanged={report} />)
    const toc = screen.getByRole('navigation', { name: 'Summary sections' })
    const titles = within(toc).getAllByRole('link').map((a) => a.textContent)
    // financial-highlights (02) carries the metrics, so What changed is 03.
    expect(titles.slice(0, 4)).toEqual([
      '01Executive Assessment',
      '02Financial Highlights',
      '03What changed',
      '04Management Strategy & Execution',
    ])
    const region = screen.getByRole('region', { name: 'What changed' })
    expect(region.id).toBe('what-changed')
    // Bare: the section's h2 is the only "What changed" heading; no card of its own inside.
    expect(within(region).getAllByRole('heading', { name: 'What changed' })).toHaveLength(1)
    expect(region.querySelector('section')).toBeNull()
    expect(within(region).getByRole('link', { name: /Prior 10-K/ })).toHaveAttribute('href', '/filing/7')
  })

  it('omits What changed when the report has nothing to show', () => {
    const empty: ChangeReport = {
      has_prior: false, comparison_basis: null, prior_filing: null, metrics: null, risks: null, key_changes: null, has_changes: false,
    }
    render(<SummaryBlocks sections={sections} summary={summary} whatChanged={empty} />)
    expect(screen.queryByRole('region', { name: 'What changed' })).toBeNull()
    expect(within(screen.getByRole('navigation', { name: 'Summary sections' })).getAllByRole('link')).toHaveLength(sections.length)
  })

  describe('arriving at a named section', () => {
    // The company page's Compare periods card links to /filing/{id}#what-changed; the change report
    // renders after the browser's own jump to the fragment has found nothing.
    const REPORT: ChangeReport = {
      has_prior: true,
      comparison_basis: 'Year over year',
      prior_filing: { filing_id: 7, filing_type: '10-K', filing_date: '2021-10-29', period_end_date: '2021-09-25' },
      metrics: {
        headline: 'Revenue up 7.8%',
        items: [
          { metric: 'revenue', label: 'Revenue', direction: 'up', pct: 7.8, current: 394_328e6, prior: 365_817e6, display: '+7.8%', tone: 'gain' },
        ],
        data_quality: 'ok',
      },
      risks: null,
      key_changes: null,
      has_changes: true,
    }
    // jsdom has no scrollIntoView; record which element each call scrolls to.
    const scrolledTo = () => vi.mocked(Element.prototype.scrollIntoView).mock.contexts.map((el) => (el as Element).id)
    const jsdomScrollIntoView = Element.prototype.scrollIntoView

    afterEach(() => {
      window.history.replaceState(null, '', window.location.pathname)
      Element.prototype.scrollIntoView = jsdomScrollIntoView
    })

    function arriveWith(hash: string) {
      window.history.replaceState(null, '', hash || window.location.pathname)
      Element.prototype.scrollIntoView = vi.fn()
    }

    it('lands on the section once it renders, and only once', () => {
      arriveWith('#what-changed')
      const { rerender } = render(<SummaryBlocks sections={sections} summary={summary} whatChanged={null} />)
      // The report has not arrived: there is nothing to land on yet, so the page stays put.
      expect(scrolledTo()).toEqual([])
      rerender(<SummaryBlocks sections={sections} summary={summary} whatChanged={REPORT} />)
      expect(scrolledTo()).toEqual(['what-changed'])
      expect(document.getElementById('what-changed')).toHaveAttribute('aria-labelledby')
      // A later section change never moves the reader again.
      rerender(<SummaryBlocks sections={sections.slice(0, 3)} summary={summary} whatChanged={REPORT} />)
      rerender(<SummaryBlocks sections={sections} summary={summary} whatChanged={REPORT} />)
      expect(scrolledTo()).toEqual(['what-changed'])
    })

    it('lands on a section that renders with the page', () => {
      arriveWith('#financial-highlights')
      render(<SummaryBlocks sections={sections} summary={summary} whatChanged={REPORT} />)
      expect(scrolledTo()).toEqual(['financial-highlights'])
    })

    it('stays put for a page opened without one, even when a fragment is set later', () => {
      arriveWith('')
      const { rerender } = render(<SummaryBlocks sections={sections} summary={summary} whatChanged={null} />)
      // A table-of-contents click sets the fragment; the report arriving after it must not jump the page.
      window.history.replaceState(null, '', '#what-changed')
      rerender(<SummaryBlocks sections={sections} summary={summary} whatChanged={REPORT} />)
      expect(scrolledTo()).toEqual([])
    })

    it('ignores a fragment that names no section', () => {
      arriveWith('#main-content')
      render(<SummaryBlocks sections={sections} summary={summary} whatChanged={REPORT} />)
      expect(scrolledTo()).toEqual([])
    })
  })
})
