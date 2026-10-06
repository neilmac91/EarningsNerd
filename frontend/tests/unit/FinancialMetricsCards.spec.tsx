import { describe, expect, it } from 'vitest'
import { render, within } from '@testing-library/react'
import FinancialMetricsTable, { type FinancialMetric } from '@/features/summaries/components/FinancialMetricsTable'

/**
 * EN-03: below md each metric is one stacked card; at/above md the DataTable is unchanged. The two
 * presentations are switched by CSS alone (`md:hidden` / `hidden md:block`), which jsdom does not
 * apply (vitest css: false), so BOTH layouts are in the DOM here: these cases prove the card
 * layout carries every cell the table carries, for the same rows, in every data variant. Whether
 * the inactive layout is really gone from the accessibility tree and the tab order, and whether
 * long values wrap in a real layout engine, is proven in a browser by
 * tests/e2e/metrics-stacked-cards.spec.ts — a class-name assertion proves nothing about layout.
 */

const EVIDENCE = {
  fragment_url: 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm#item8',
  verified: true,
  section_ref: 'Item 8. Financial Statements',
  excerpt: 'Total net sales increased 6% or $25.1 billion during 2025 compared to 2024.',
}

const PER_ADS = {
  value: 45.6,
  ordinary_per_ads: 8,
  currency: 'CNY',
  as_of: '2026-06-28',
  source: 'Alibaba 20-F cover / deposit agreement — 1 ADS = 8 ordinary shares',
  arithmetic: 'CNY 5.7 per ordinary share × 8 = CNY 45.6 per ADS',
}

/** Three rows that between them exercise every cell kind the table can show. */
const FULL: FinancialMetric[] = [
  {
    metric: 'Total net sales',
    current_period: '$416,161M',
    prior_period: '$391,035M',
    change_display: '+6.4%',
    change_direction: 'up',
    change_tone: 'gain',
    commentary: 'Revenue grew across every segment, led by Services.',
    source_url: 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/',
    source_verified: true,
    xbrl_concept: 'Revenue',
    source_section_ref: 'Consolidated Statements of Operations',
    commentary_evidence: EVIDENCE,
  },
  {
    metric: 'Operating margin',
    current_period: '31.9%',
    prior_period: '31.5%',
    change_display: '+0.4 ppts',
    change_direction: 'up',
    change_tone: 'gain',
    commentary: 'Margin held despite tariff costs.',
    source_url: 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/',
    source_verified: false,
  },
  {
    metric: 'Diluted EPS (per ordinary share)',
    current_period: 'CN¥5.70',
    prior_period: 'CN¥6.10',
    change_display: '-6.6%',
    change_direction: 'down',
    change_tone: 'loss',
    per_ads: PER_ADS,
    // no commentary, no evidence, no source url
  },
]

const cardsOf = (container: HTMLElement) => container.querySelector('[data-metric-cards]') as HTMLElement
const tableOf = (container: HTMLElement) => container.querySelector('[data-metric-table] table') as HTMLElement
const cardList = (container: HTMLElement) => Array.from(container.querySelectorAll<HTMLElement>('[data-metric-card]'))
const bodyRows = (container: HTMLElement) => Array.from(tableOf(container).querySelectorAll<HTMLElement>('tbody tr'))
const chipsIn = (root: HTMLElement) => within(root).queryAllByText(/Verified in filing|SEC XBRL|^Cited$/)

describe('FinancialMetricsTable — stacked cards below md (EN-03)', () => {
  it('renders one card per row beside the table, with the same name, values, change, takeaway and provenance', () => {
    const { container } = render(<FinancialMetricsTable metrics={FULL} bare />)
    const cards = cardList(container)
    const rows = bodyRows(container)
    expect(cards).toHaveLength(FULL.length)
    expect(rows).toHaveLength(FULL.length)

    for (const [i, metric] of FULL.entries()) {
      const card = within(cards[i])
      const row = within(rows[i])
      // metric name (once per layout)
      expect(card.getByText(metric.metric)).toBeInTheDocument()
      expect(row.getByText(metric.metric)).toBeInTheDocument()
      // the same formatted figures, through the one formatter
      const current = row.getAllByText(/\$416\.2B|31\.9%|CN¥5\.70/)[0]?.textContent
      expect(card.getByText(current!.replace(/≈.*$/, '').trim(), { exact: false })).toBeInTheDocument()
      // takeaway: the commentary, or the documented "-" placeholder, in both
      expect(card.getByText(metric.commentary ?? '-')).toBeInTheDocument()
      expect(row.getByText(metric.commentary ?? '-')).toBeInTheDocument()
      // server change string verbatim in both (no client math anywhere)
      expect(card.getByText(metric.change_display!)).toBeInTheDocument()
      expect(row.getByText(metric.change_display!)).toBeInTheDocument()
      // provenance chips: the same count per row in each layout
      expect(chipsIn(cards[i])).toHaveLength(chipsIn(rows[i]).length)
    }
    // XBRL chips: verified "SEC XBRL" and the honest "Cited" fallback, once per layout each
    expect(within(cardsOf(container)).getAllByText(/SEC XBRL/)).toHaveLength(1)
    expect(within(tableOf(container)).getAllByText(/SEC XBRL/)).toHaveLength(1)
    expect(within(cardsOf(container)).getAllByText(/^Cited$/)).toHaveLength(1)
    expect(within(tableOf(container)).getAllByText(/^Cited$/)).toHaveLength(1)
    // takeaway evidence chip: once per layout (only the first row carries evidence)
    expect(within(cardsOf(container)).getAllByText(/Verified in filing/)).toHaveLength(1)
    expect(within(tableOf(container)).getAllByText(/Verified in filing/)).toHaveLength(1)
    // per-ADS annotation in both
    expect(within(cardsOf(container)).getByText(/≈ CNY 45.6 per ADS/)).toBeInTheDocument()
    expect(within(tableOf(container)).getByText(/≈ CNY 45.6 per ADS/)).toBeInTheDocument()
  })

  it('exposes the table caption as the card list’s accessible name, in both caption variants', () => {
    const withComparatives = render(<FinancialMetricsTable metrics={FULL} bare />)
    const caption = tableOf(withComparatives.container).querySelector('caption')!.textContent
    expect(caption).toMatch(/prior period, change/)
    expect(cardsOf(withComparatives.container)).toHaveAttribute('aria-label', caption!)
    withComparatives.unmount()

    const noComparatives = render(
      <FinancialMetricsTable metrics={[{ metric: 'Revenue', current_period: '$125,000', prior_period: '', commentary: 'Grew.' }]} bare />,
    )
    const caption2 = tableOf(noComparatives.container).querySelector('caption')!.textContent
    expect(caption2).toBe('Financial highlights: current period and investor takeaway per metric')
    expect(cardsOf(noComparatives.container)).toHaveAttribute('aria-label', caption2!)
  })

  it('labels the figures with the table’s column names, only where the table has those columns', () => {
    const { container } = render(<FinancialMetricsTable metrics={FULL} bare />)
    for (const card of cardList(container)) {
      expect(within(card).getByText('Current period')).toBeInTheDocument()
      expect(within(card).getByText('Prior period')).toBeInTheDocument()
      expect(within(card).getByText('Change')).toBeInTheDocument()
    }
  })

  it('without comparatives: no prior or change label, cell or chip in either layout', () => {
    const { container } = render(
      <FinancialMetricsTable
        metrics={[
          { metric: 'Revenue', current_period: '$125,000', prior_period: '', commentary: 'Grew.' },
          { metric: 'Gross margin', current_period: '48%', prior_period: '', commentary: 'Held.' },
        ]}
        bare
      />,
    )
    expect(within(container).queryByText(/prior period/i)).not.toBeInTheDocument()
    expect(within(container).queryByText(/change/i)).not.toBeInTheDocument()
    expect(container.querySelectorAll('th')).toHaveLength(3)
    for (const card of cardList(container)) {
      expect(within(card).getAllByRole('term')).toHaveLength(1) // Current period only
      expect(within(card).queryByText('—')).not.toBeInTheDocument()
    }
  })

  it('without a server change: the em dash and no percentage, in both layouts (delta single-source)', () => {
    const { container } = render(
      <FinancialMetricsTable metrics={[{ metric: 'Revenue', current_period: '$100', prior_period: '$80' }]} bare />,
    )
    expect(within(cardsOf(container)).getByText('—')).toBeInTheDocument()
    expect(within(tableOf(container)).getByText('—')).toBeInTheDocument()
    expect(cardsOf(container)).not.toHaveTextContent('%')
  })

  it('without commentary or evidence: the "-" placeholder and no chip, nothing invented', () => {
    const { container } = render(
      <FinancialMetricsTable metrics={[{ metric: 'Net income', current_period: '$112,010M', prior_period: '$93,736M', change_display: '+19.5%', change_direction: 'up', change_tone: 'gain' }]} bare />,
    )
    expect(within(cardsOf(container)).getByText('-')).toBeInTheDocument()
    expect(within(tableOf(container)).getByText('-')).toBeInTheDocument()
    expect(chipsIn(cardsOf(container))).toHaveLength(0)
    expect(chipsIn(tableOf(container))).toHaveLength(0)
    expect(container.querySelectorAll('a, button')).toHaveLength(0)
  })

  it('takes tone from change_tone and the glyph from change_direction, never from the numbers', () => {
    // The numbers fall, the server says gain: the card follows the server (one policy, server-side).
    const { container } = render(
      <FinancialMetricsTable
        metrics={[
          { metric: 'Cost of sales', current_period: '$80', prior_period: '$100', change_display: '-20.0%', change_direction: 'down', change_tone: 'gain' },
          { metric: 'Flat line', current_period: '$100', prior_period: '$100', change_display: '0.0%', change_direction: 'flat', change_tone: 'flat' },
        ]}
        bare
      />,
    )
    const [gainCard, flatCard] = cardList(container)
    const gainChange = within(gainCard).getByText('-20.0%').closest('dd')!
    expect(gainChange.className).toMatch(/text-gain-text/)
    expect(gainChange.className).not.toMatch(/text-loss-text/)
    expect(gainChange.querySelector('svg')).not.toBeNull() // the direction glyph rides with the string
    const flatChange = within(flatCard).getByText('0.0%').closest('dd')!
    expect(flatChange.className).toMatch(/text-flat-light/)
    expect(flatChange.className).not.toMatch(/font-semibold/)
  })

  it('never forces a card value, change or takeaway onto one line or clips it', () => {
    const long: FinancialMetric[] = [
      {
        metric: 'Revenue from contracts with customers, excluding assessed taxes, continuing operations',
        current_period: '$1,234,567,890,123 (restated, see Note 2)',
        prior_period: '$987,654,321,098 (as previously reported)',
        change_display: '+25.0% (constant currency +23.4%)',
        change_direction: 'up',
        change_tone: 'gain',
        commentary: 'A takeaway long enough to wrap several times on a phone. '.repeat(6),
      },
    ]
    const { container } = render(<FinancialMetricsTable metrics={long} bare />)
    const card = cardList(container)[0]
    // every text-bearing element of the card is free of single-line / clipping utilities
    for (const el of Array.from(card.querySelectorAll('*'))) {
      if (el.closest('svg')) continue // the direction glyph is a fixed-size icon, not text
      const cls = el.getAttribute('class') ?? ''
      expect(cls, `${el.tagName}: ${cls}`).not.toMatch(/whitespace-nowrap|truncate|line-clamp|overflow-hidden|\bh-\d|max-h-/)
    }
    for (const dd of Array.from(card.querySelectorAll('dd'))) expect(dd.className).toMatch(/break-words/)
    // the same strings in both layouts: the figures through the one formatter, the change verbatim
    const cells = bodyRows(container)[0].querySelectorAll('td')
    const [current, prior, change] = Array.from(card.querySelectorAll('dd')).map((dd) => dd.textContent)
    expect(current).toBe(cells[1].textContent)
    expect(prior).toBe(cells[2].textContent)
    expect(change).toBe(cells[3].textContent)
    expect(change).toBe(long[0].change_display)
    expect(card.querySelector('p')!.textContent).toBe(long[0].commentary)
  })

  it('card type never drops below the table’s: values and takeaway text-sm, labels the table’s header size', () => {
    const { container } = render(<FinancialMetricsTable metrics={FULL} bare />)
    const card = cardList(container)[0]
    for (const dd of Array.from(card.querySelectorAll('dd'))) expect(dd.className).toMatch(/\btext-sm\b/)
    expect(within(card).getByText(FULL[0].commentary!).className).toMatch(/\btext-sm\b/)
    for (const dt of Array.from(card.querySelectorAll('dt'))) expect(dt.className).toMatch(/\btext-xs\b/)
    expect(tableOf(container).querySelector('thead tr')!.className).toMatch(/\btext-xs\b/)
    expect(tableOf(container).className).toMatch(/\btext-sm\b/)
  })

  it('carries no duplicate ids across the two layouts', () => {
    const { container } = render(<FinancialMetricsTable metrics={FULL} bare />)
    const ids = Array.from(container.querySelectorAll('[id]')).map((el) => el.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('switches the two layouts by the md breakpoint classes (the browser spec proves the hiding)', () => {
    const { container } = render(<FinancialMetricsTable metrics={FULL} bare />)
    const tokens = (el: Element) => (el.getAttribute('class') ?? '').split(/\s+/)
    expect(tokens(cardsOf(container))).toContain('md:hidden')
    expect(tokens(cardsOf(container))).not.toContain('hidden')
    const tableWrap = container.querySelector('[data-metric-table]')!
    expect(tokens(tableWrap)).toContain('hidden')
    expect(tokens(tableWrap)).toContain('md:block')
  })

  it('renders the notes once in each mode and both layouts inside the self-contained card', () => {
    const bare = render(<FinancialMetricsTable metrics={FULL} notes="Figures in millions." bare />)
    expect(bare.getAllByText('Figures in millions.')).toHaveLength(1)
    expect(cardList(bare.container)).toHaveLength(3)
    expect(bodyRows(bare.container)).toHaveLength(3)
    bare.unmount()

    const card = render(<FinancialMetricsTable metrics={FULL} notes="Figures in millions." />)
    expect(card.getAllByText('Figures in millions.')).toHaveLength(1)
    expect(card.getByText('Financial Highlights')).toBeInTheDocument()
    expect(cardList(card.container)).toHaveLength(3)
    expect(bodyRows(card.container)).toHaveLength(3)
  })

  it('renders nothing for no rows', () => {
    const { container } = render(<FinancialMetricsTable metrics={[]} bare />)
    expect(container).toBeEmptyDOMElement()
  })
})
