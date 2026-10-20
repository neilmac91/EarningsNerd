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

  it('keeps every supplied generic-table cell, ragged row and source under distinct native table captions', () => {
    const evidence = { verified: true, excerpt: 'Expense over vesting', section_ref: 'Note 5', fragment_url: 'https://www.sec.gov/x.htm' }
    const tables: RenderedSection[] = [{
      id: 'notable-footnotes', title: 'Notable Footnotes', blocks: [
        { kind: 'table', headers: ['Item', 'Impact'], rows: [
          ['Stock awards', 'Expense over vesting', 'Extra supplied field'], ['Short row'], [], ['', ''],
        ], row_evidence: [evidence, null, evidence, null] },
        { kind: 'table', headers: [], rows: [['Unlabelled value', 'Second cell']] },
      ],
    }]
    render(<SummaryBlocks sections={tables} summary={summary} />)
    const first = screen.getByRole('table', { name: 'Notable Footnotes, table 1 of 2' })
    expect(within(first).getAllByRole('columnheader').map((cell) => cell.textContent)).toEqual(['Item', 'Impact'])
    expect(Array.from(first.querySelectorAll('tbody tr')).map((row) => row.children.length)).toEqual([3, 1, 1, 2])
    for (const text of ['Stock awards', 'Expense over vesting', 'Extra supplied field', 'Short row']) {
      expect(within(first).getByText(text, { exact: true })).toBeInTheDocument()
    }
    expect(within(first).getAllByRole('link', { name: /Source: Verified in filing/ })).toHaveLength(2)
    const second = screen.getByRole('table', { name: 'Notable Footnotes, table 2 of 2' })
    expect(within(second).queryAllByRole('columnheader')).toHaveLength(0)
    expect(within(second).getAllByRole('cell').map((cell) => cell.textContent)).toEqual(['Unlabelled value', 'Second cell'])
  })

  it('renders the risks section with its evidence + trace-to-source provenance', () => {
    render(<SummaryBlocks sections={sections} summary={summary} />)
    // An evidence row (critique P-03): the start of the excerpt heads it, one level under the
    // section's h2, with the device's marker on a located row (D-044), hidden from assistive tech so the
    // heading's name is its words alone, and the excerpt itself sits in a blockquote.
    const heading = screen.getByRole('heading', { level: 3, name: 'We are substantially dependent on TSMC for wafer supply' })
    expect(heading.textContent).toBe('We are substantially dependent on TSMC for wafer supply[1]')
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

  it('marks a quote whose evidence the server located (D-044): the marked block in the filing\'s face, no marker, no twin', () => {
    const evidence = (verified: boolean) => ({ excerpt: 'We expect double-digit growth.', section_ref: 'Item 7. MD&A', verified, fragment_url: 'https://www.sec.gov/x.htm' })
    const quotes: RenderedSection[] = [{
      id: 'forward-signals',
      title: 'Forward Signals',
      blocks: [
        { kind: 'quote', text: 'We expect double-digit growth.', speaker: 'CEO', evidence: evidence(true) },
        { kind: 'quote', text: 'Demand may soften.', speaker: 'CFO', evidence: evidence(false) },
        { kind: 'quote', text: 'Free cash flow is defined as operating cash flow less capital expenditures.', speaker: 'Filing statement' },
      ],
    }]
    const { container } = render(<SummaryBlocks sections={quotes} summary={summary} />)
    const [located, cited, plain] = Array.from(container.querySelectorAll('blockquote'))
    // Located: the marked block, in the filing's face on the primary ink; the speaker stays in the body face.
    expect(located.className.split(' ')).toEqual(expect.arrayContaining(['en-marked', 'font-editorial', 'text-text-primary-light']))
    expect(located.querySelector('cite')!.className.split(' ')).toContain('font-sans')
    // Cited or uncited: today's neutral hairline, the body face.
    for (const quote of [cited, plain]) {
      expect(quote.className.split(' ')).toEqual(expect.arrayContaining(['border-l-2', 'italic']))
      expect(quote.className).not.toMatch(/en-marked|font-editorial/)
    }
    // A quote block has no heading to carry a marker: no marker, no margin, no twin anywhere.
    expect(container.querySelector('[data-en-ref], .en-margin, .en-margin-mark')).toBeNull()
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

  it('renders tone as a neutral header Badge that names what it is, not a prose sentence', () => {
    const toneSections: RenderedSection[] = [
      {
        id: 'executive-assessment',
        title: 'Executive Assessment',
        tone: 'positive',
        blocks: [{ kind: 'paragraph', text: 'Record quarter driven by AI demand.' }],
      },
      {
        id: 'forward-signals',
        title: 'Forward Signals',
        tone: 'Cautious',
        blocks: [{ kind: 'paragraph', text: 'Guidance was held.' }],
      },
    ]
    render(<SummaryBlocks sections={toneSections} summary={summary} />)
    const classes = (el: HTMLElement) => el.className.split(/\s+/)
    for (const label of ['Management tone: positive', 'Management tone: cautious']) {
      const badge = screen.getByText(label).parentElement!
      // A tone is a reading, not a status: the neutral Badge's quiet ink and hairline, exactly, so neither
      // the brand nor a warning colour nor the gain or loss data colours (info, beat, miss) can stand in.
      expect(classes(badge)).toEqual(expect.arrayContaining(['border-border-light', 'bg-white', 'text-text-secondary-light', 'dark:text-text-secondary-dark']))
      expect(badge.className).not.toMatch(/brand|warning|info|gain|loss/)
      expect(badge.className).not.toContain('capitalize')
    }
    expect(screen.queryByText(/tone was/i)).not.toBeInTheDocument()
  })

  it('lets the tone badge move beneath its heading and wrap its label, never squeeze the heading or widen the page', () => {
    const toneSections: RenderedSection[] = [
      {
        id: 'executive-assessment',
        title: 'Executive Assessment',
        tone: 'cautious',
        blocks: [{ kind: 'paragraph', text: 'Margins narrowed.' }],
      },
    ]
    render(<SummaryBlocks sections={toneSections} summary={summary} />)
    const label = screen.getByText('Management tone: cautious')
    const badge = label.parentElement!
    const group = screen.getByRole('heading', { level: 2, name: 'Executive Assessment' }).parentElement!
    const row = group.parentElement!
    const classes = (el: HTMLElement) => el.className.split(/\s+/)
    // The founder's review (320px, and 390px at 200% text): a row that cannot wrap squeezed the heading
    // and pushed the page wider. The row wraps, the badge is its only other item (so only the badge moves
    // beneath), the badge may shrink to its container, and the label's own span lets its words wrap inside
    // the Badge (whose base recipe is nowrap).
    expect([...row.children]).toEqual([group, badge])
    expect(classes(row)).toContain('flex-wrap')
    expect(classes(row)).not.toContain('flex-nowrap')
    expect(classes(badge)).not.toContain('shrink-0')
    expect(classes(badge)).toContain('max-w-full')
    expect(classes(label)).toContain('whitespace-normal')
    expect(classes(label).filter((c) => /nowrap|shrink-0|truncate/.test(c))).toEqual([])
  })

  // The principal review of #1293: a wrapping row of index, heading and badge dropped a long heading beneath
  // its index on every section (a flex line places items at their whole width before shrinking them). The
  // index and the heading are one group that never wraps, on toned sections and plain ones alike.
  it('keeps every heading beside its index: the two are one group that never wraps', () => {
    const plainAndToned: RenderedSection[] = [
      { id: 'earnings-quality', title: 'Earnings Quality & Cash Conversion', blocks: [{ kind: 'paragraph', text: 'Cash tracked earnings.' }] },
      { id: 'forward-signals', title: 'Forward Signals', tone: 'positive', blocks: [{ kind: 'paragraph', text: 'Guidance was raised.' }] },
    ]
    render(<SummaryBlocks sections={plainAndToned} summary={summary} />)
    const classes = (el: HTMLElement) => el.className.split(/\s+/)
    const headings = screen.getAllByRole('heading', { level: 2 })
    expect(headings.map((h) => h.textContent)).toEqual(['Earnings Quality & Cash Conversion', 'Forward Signals'])
    headings.forEach((heading, i) => {
      const group = heading.parentElement!
      expect([...group.children].map((child) => child.textContent)).toEqual([String(i + 1).padStart(2, '0'), heading.textContent])
      expect(classes(group)).toEqual(expect.arrayContaining(['flex', 'min-w-0', 'items-baseline']))
      expect(classes(group).filter((c) => /wrap/.test(c))).toEqual([])
      expect(classes(heading)).toContain('min-w-0')
    })
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
            // Two spans that open with the same sentence: the second heading takes an occurrence number.
            { summary: 'Filing excerpt', supporting_evidence: 'Currency movements reduce reported revenue. The euro fell.' },
            { summary: 'Filing excerpt', supporting_evidence: 'Currency movements reduce reported revenue. The yen fell.' },
          ],
          _risk_source_projection: { version: 1, verified_count: 3, withheld_count: 0 },
        },
      },
    } as unknown as Summary
    render(<SummaryBlocks sections={riskSections} summary={untitled} />)
    const section = screen.getByRole('region', { name: 'Investment Risks & Concerns' })
    const headings = within(section).getAllByRole('heading', { level: 3 }).map((h) => h.textContent)
    expect(headings).toEqual([
      'Our suppliers are concentrated in Asia; a disruption would delay shipments',
      'Currency movements reduce reported revenue…',
      'Currency movements reduce reported revenue… (2)',
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
