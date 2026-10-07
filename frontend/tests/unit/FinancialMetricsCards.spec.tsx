import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, within } from '@testing-library/react'
import FinancialMetricsTable, { type FinancialMetric } from '@/features/summaries/components/FinancialMetricsTable'

/**
 * EN-03: below md each metric is one stacked card; at/above md the DataTable is unchanged. The two
 * presentations are switched by CSS alone (`md:hidden` / `hidden md:block`), which jsdom does not
 * apply (vitest css: false), so BOTH layouts are in the DOM here. These cases prove CONTENT PARITY:
 * every field the table renders is read the same way from both layouts (`factsOf`) and compared
 * with the served rows (`servedFacts`) — for the full fixture and for every data variant the
 * acceptance names. Whether the inactive layout is really gone from the accessibility tree and the
 * tab order, and whether long values wrap in a real layout engine, is proven in a browser by
 * tests/e2e/metrics-stacked-cards.spec.ts — a class-name assertion proves nothing about layout.
 */

const SEC = 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/'
const EVIDENCE = {
  fragment_url: `${SEC}aapl-20250927.htm#item8`,
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
    source_url: SEC,
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
    source_url: SEC,
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
const NO_COMPARATIVES: FinancialMetric[] = [
  { metric: 'Revenue', current_period: '$125,000', prior_period: '', commentary: 'Grew.' },
  { metric: 'Gross margin', current_period: '48%', prior_period: '', commentary: 'Held.' },
]
const NO_COMMENTARY: FinancialMetric[] = [
  { metric: 'Net income', current_period: '$112,010M', prior_period: '$93,736M', change_display: '+19.5%', change_direction: 'up', change_tone: 'gain', source_url: SEC, source_verified: true, xbrl_concept: 'Net income' },
]
const NO_EVIDENCE: FinancialMetric[] = [
  { metric: 'Net income', current_period: '$112,010M', prior_period: '$93,736M', change_display: '+19.5%', change_direction: 'up', change_tone: 'gain', commentary: 'Lower tax rate.' },
]
const NO_CHANGE: FinancialMetric[] = [{ metric: 'Revenue', current_period: '$100', prior_period: '$80' }]
/** A row without a prior value among rows that have one: the table shows an empty Prior cell. */
const MIXED_PRIOR: FinancialMetric[] = [
  { metric: 'Revenue', current_period: '$100', prior_period: '$80', change_display: '+25.0%', change_direction: 'up', change_tone: 'gain' },
  { metric: 'New metric', current_period: '$5', prior_period: '' },
]
// Long values that SURVIVE formatMetricValue: a leading non-numeric token makes parseNumeric null,
// so the string renders verbatim (a numeric '$1,234,567,890,123 (restated)' would compact to $1.2T
// and never exercise the wrap path). The change string also carries an unbreakable 60-char token.
// A second, ordinary row keeps the table in its comparatives shape (a prior that parses is what
// switches the Prior / Change columns on).
const UNBREAKABLE = 'x'.repeat(60)
const LONG: FinancialMetric[] = [
  {
    metric: 'Revenue from contracts with customers, excluding assessed taxes, continuing operations only',
    current_period: 'Restated to $1,234,567,890,123 after the discontinued-operations reclassification',
    prior_period: 'Previously reported $987,654,321,098 before the reclassification',
    change_display: `+25.0% (constant currency +23.4%, excluding the 53rd week) ${UNBREAKABLE}`,
    change_direction: 'up',
    change_tone: 'gain',
    commentary: 'A takeaway long enough to wrap several times on a phone. '.repeat(6).trim(),
    commentary_evidence: EVIDENCE,
  },
  { metric: 'Net income', current_period: '$112,010M', prior_period: '$93,736M', change_display: '+19.5%', change_direction: 'up', change_tone: 'gain', commentary: 'Lower tax rate.' },
]

const CAPTION_WITH = 'Financial highlights: current period, prior period, change, and investor takeaway per metric'
const CAPTION_WITHOUT = 'Financial highlights: current period and investor takeaway per metric'

const layout = (c: HTMLElement, which: 'cards' | 'table') => c.querySelector<HTMLElement>(`[data-metrics-layout="${which}"]`)!
const all = (root: Element, sel: string) => Array.from(root.querySelectorAll<HTMLElement>(sel))
const text = (e: Element | null | undefined) => (e?.textContent ?? '').replace(/\s+/g, ' ').trim()
const cardList = (c: HTMLElement) => all(layout(c, 'cards'), '[data-metric-card]')
const bodyRows = (c: HTMLElement) => all(layout(c, 'table'), 'tbody tr')

/** Everything the acceptance row says must be equal across layouts, read the same way in both. */
function factsOf(root: HTMLElement) {
  const isTable = root.dataset.metricsLayout === 'table'
  return {
    caption: isTable ? text(root.querySelector('caption')) : root.querySelector('ul')?.getAttribute('aria-label') ?? root.getAttribute('aria-label'),
    rows: isTable ? all(root, 'tbody tr').length : all(root, '[data-metric-card]').length,
    names: all(root, '[data-metric-field="name"]').map((e) => text(e.firstElementChild)),
    currents: all(root, '[data-metric-field="current"]').map(text),
    perAds: all(root, '[data-metric-field="per-ads"]').map(text),
    priors: all(root, '[data-metric-field="prior"]').map(text),
    changes: all(root, '[data-metric-field="change"]').map((e) => ({ text: text(e), direction: e.dataset.direction ?? null, tone: e.dataset.tone ?? null })),
    takeaways: all(root, '[data-metric-field="takeaway"]').map((e) => text(e.firstElementChild)),
    xbrlChips: all(root, '[data-metric-field="name"] [aria-label^="Source: "]').map((e) => e.getAttribute('aria-label')),
    takeawayChips: all(root, '[data-metric-field="takeaway"] [aria-label^="Source: "]').map((e) => e.getAttribute('aria-label')),
  }
}

/** The same facts, computed from the served rows — no client math anywhere in here either. */
const servedFacts = (rows: FinancialMetric[], hasComparatives: boolean) => ({
  caption: hasComparatives ? CAPTION_WITH : CAPTION_WITHOUT,
  rows: rows.length,
  names: rows.map((r) => r.metric),
  perAds: rows.filter((r) => r.per_ads).map(() => expect.stringContaining('per ADS')),
  priors: hasComparatives ? rows.map(() => expect.any(String)) : [],
  changes: hasComparatives
    ? rows.map((r) =>
        r.change_display
          ? { text: r.change_display, direction: r.change_direction ?? null, tone: r.change_tone ?? null }
          : { text: '—', direction: null, tone: null },
      )
    : [],
  takeaways: rows.map((r) => r.commentary || '-'),
  xbrlChips: rows.filter((r) => r.source_url).map((r) => (r.source_verified ? `Source: ${r.xbrl_concept ? `${r.xbrl_concept} · ` : ''}SEC XBRL` : 'Source: Cited')),
  takeawayChips: rows.filter((r) => r.commentary_evidence).map((r) => (r.commentary_evidence!.verified ? 'Source: Verified in filing' : 'Source: Cited')),
})

const TONE_TOKENS = /^(font-semibold|(dark:)?text-(gain|loss)-(text|dark)|(dark:)?text-flat-(light|dark))$/
const toneTokens = (e: Element) => (e.getAttribute('class') ?? '').split(/\s+/).filter((t) => TONE_TOKENS.test(t)).sort()
const tokens = (e: Element) => (e.getAttribute('class') ?? '').split(/\s+/).filter(Boolean)

describe('FinancialMetricsTable — stacked cards below md (EN-03): content parity', () => {
  it.each([
    ['the full fixture (verified + cited XBRL, evidence, per-ADS, up and down)', FULL, true],
    ['no comparatives (no prior / change anywhere, the short caption)', NO_COMPARATIVES, false],
    ['no commentary (the "-" placeholder, no chip)', NO_COMMENTARY, true],
    ['no evidence (a takeaway without a chip, nothing invented)', NO_EVIDENCE, true],
    ['no server change (the em dash, no percentage)', NO_CHANGE, true],
    ['a row without a prior among rows with one (the empty Prior cell, mirrored)', MIXED_PRIOR, true],
    ['long values (verbatim in both layouts)', LONG, true],
  ] as const)('%s: cards === table === served', (_name, rows, hasComparatives) => {
    const { container } = render(<FinancialMetricsTable metrics={[...rows]} bare />)
    const cards = factsOf(layout(container, 'cards'))
    const table = factsOf(layout(container, 'table'))
    expect(cards.rows).toBe(rows.length)
    expect(cards).toEqual(table)
    expect(table).toMatchObject(servedFacts([...rows], hasComparatives))
    expect(cards.currents).toHaveLength(rows.length)
    if (!hasComparatives) {
      expect(cards.priors).toEqual([])
      expect(cards.changes).toEqual([])
      expect(all(layout(container, 'table'), 'th')).toHaveLength(3)
      for (const which of ['cards', 'table'] as const) {
        expect(within(layout(container, which)).queryByText(/prior/i)).toBeNull()
        expect(within(layout(container, which)).queryByText(/change/i)).toBeNull()
      }
      for (const card of cardList(container)) expect(within(card).getAllByRole('term')).toHaveLength(1) // Current only
    }
    if (rows === NO_CHANGE) {
      expect(cards.changes).toEqual([{ text: '—', direction: null, tone: null }])
      expect(layout(container, 'cards')).not.toHaveTextContent('%')
    }
    if (rows === NO_EVIDENCE || rows === NO_COMMENTARY) {
      expect(cards.takeawayChips).toEqual([])
      expect(all(container, '[data-metric-field="takeaway"] a, [data-metric-field="takeaway"] button')).toHaveLength(0)
      expect(within(container).queryByText(/Verified in filing/)).toBeNull()
    }
    if (rows === MIXED_PRIOR) {
      // strict mirroring: the Prior group is rendered for every row, empty where the table's cell is
      expect(cards.priors).toEqual(['$80.0', ''])
      expect(cards.changes[1]).toEqual({ text: '—', direction: null, tone: null })
      for (const card of cardList(container)) expect(within(card).getAllByRole('term').map(text)).toEqual(['Current period', 'Prior period', 'Change'])
    }
  })

  it('a card is one <li> per served row, in order, each with the row’s name once and the caption naming the list', () => {
    const { container } = render(<FinancialMetricsTable metrics={FULL} bare />)
    const cards = cardList(container)
    expect(cards).toHaveLength(FULL.length)
    expect(cards.map((c) => text(c.querySelector('[data-metric-field="name"]')!.firstElementChild))).toEqual(FULL.map((r) => r.metric))
    for (const [i, c] of cards.entries()) expect(within(c).getAllByText(FULL[i].metric)).toHaveLength(1)
    expect(screen.getByRole('list', { name: CAPTION_WITH })).toBe(layout(container, 'cards'))
    expect(screen.getByRole('table', { name: CAPTION_WITH })).toBeInTheDocument()
  })

  it('the caption names the table and the list in the no-comparatives variant too', () => {
    render(<FinancialMetricsTable metrics={NO_COMPARATIVES} bare />)
    expect(screen.getByRole('table', { name: CAPTION_WITHOUT })).toBeInTheDocument()
    expect(screen.getByRole('list', { name: CAPTION_WITHOUT })).toBeInTheDocument()
    expect(screen.queryByText('Prior Period')).toBeNull()
    expect(screen.queryByText('Change')).toBeNull()
  })

  it('change tone and glyph come from the server: the card dd carries exactly the tone tokens the table td carries', () => {
    const rows: FinancialMetric[] = [
      // the numbers fall, the server says gain (a cost line): both layouts follow the server
      { metric: 'Cost of sales', current_period: '$80', prior_period: '$100', change_display: '-20.0%', change_direction: 'down', change_tone: 'gain' },
      { metric: 'Flat line', current_period: '$100', prior_period: '$100', change_display: '0.0%', change_direction: 'flat', change_tone: 'flat' },
      { metric: 'Loss line', current_period: '$90', prior_period: '$100', change_display: '-10.0%', change_direction: 'down', change_tone: 'loss' },
      { metric: 'No tone', current_period: '$90', prior_period: '$100', change_display: '-10.0%' },
    ]
    const { container } = render(<FinancialMetricsTable metrics={rows} bare />)
    const tds = all(layout(container, 'table'), '[data-metric-field="change"]').map((e) => e.closest('td')!)
    const dds = all(layout(container, 'cards'), '[data-metric-field="change"]').map((e) => e.closest('dd')!)
    expect(dds).toHaveLength(4)
    expect(dds.map(toneTokens)).toEqual(tds.map(toneTokens))
    expect(toneTokens(dds[0])).toEqual(['dark:text-gain-dark', 'font-semibold', 'text-gain-text'])
    expect(toneTokens(dds[1])).toEqual(['dark:text-flat-dark', 'text-flat-light'])
    expect(toneTokens(dds[2])).toEqual(['dark:text-loss-dark', 'font-semibold', 'text-loss-text'])
    expect(toneTokens(dds[3])).toEqual([])
    // the served direction and tone ride on the change element in both layouts, and the glyph is
    // decorative (the signed string carries direction for AT) — in both
    for (const which of ['cards', 'table'] as const) {
      const changes = all(layout(container, which), '[data-metric-field="change"]')
      expect(changes.map((e) => [e.dataset.direction, e.dataset.tone])).toEqual([['down', 'gain'], ['flat', 'flat'], ['down', 'loss'], [undefined, undefined]])
      for (const e of changes) {
        const svg = e.querySelector('svg')
        expect(svg, `${which}: the glyph rides with the string`).not.toBeNull()
        expect(svg!.getAttribute('aria-hidden')).toBe('true')
      }
    }
    // the table keeps its single-line inline-flex cell; the card's glyph rides inline so the string can wrap
    expect(tokens(all(layout(container, 'table'), '[data-metric-field="change"]')[0])).toContain('inline-flex')
    expect(tokens(all(layout(container, 'cards'), '[data-metric-field="change"]')[0])).not.toContain('inline-flex')
    expect(tokens(all(layout(container, 'cards'), '[data-metric-field="change"] svg')[0])).toContain('inline-block')
  })

  it('labels the figures with the table’s column vocabulary: visible short form, spoken full form, header-size eyebrows', () => {
    const { container } = render(<FinancialMetricsTable metrics={FULL} bare />)
    const cards = cardList(container)
    expect(cards).toHaveLength(FULL.length)
    for (const c of cards) {
      expect(within(c).getAllByRole('term').map(text)).toEqual(['Current period', 'Prior period', 'Change'])
      expect(all(c, 'dt .sr-only').map(text)).toEqual(['period', 'period'])
      for (const dt of all(c, 'dt')) {
        expect(tokens(dt)).toEqual(expect.arrayContaining(['text-xs', 'uppercase', 'tracking-eyebrow']))
      }
      for (const dd of all(c, 'dd')) {
        expect(tokens(dd)).toEqual(expect.arrayContaining(['font-data', 'text-sm', 'tabular-nums']))
      }
    }
  })

  it('never forces a card value, change line, name or takeaway onto one line or clips it (long values, an unbreakable token)', () => {
    const { container } = render(<FinancialMetricsTable metrics={LONG} bare />)
    const card = cardList(container)[0]
    expect(card).toBeDefined()
    for (const el of [card, ...all(card, '*')]) {
      if (el.closest('svg')) continue // the direction glyph is a fixed-size icon, not text
      expect(el.getAttribute('class') ?? '', el.tagName).not.toMatch(
        /\b(whitespace-nowrap|whitespace-pre|truncate|line-clamp-\d+|overflow-hidden|overflow-x-hidden|h-\d+(\.\d+)?|max-h-\S+)\b/,
      )
      expect(el.getAttribute('style')).toBeNull()
    }
    // the wrap contract is inherited from the card: overflow-wrap:anywhere also lowers a flex
    // item's min-content width, which break-words cannot — so even the unbreakable token breaks
    expect(tokens(card)).toContain('[overflow-wrap:anywhere]')
    for (const group of all(card, 'dl > div')) expect(tokens(group)).toContain('min-w-0')
    // the long strings render verbatim in BOTH layouts (the formatter left them alone)
    const c = factsOf(layout(container, 'cards'))
    expect(c.currents[0]).toBe(LONG[0].current_period)
    expect(c.priors[0]).toBe(LONG[0].prior_period)
    expect(c.changes[0].text).toBe(LONG[0].change_display)
    expect(c.names[0]).toBe(LONG[0].metric)
    expect(c.takeaways[0]).toBe(LONG[0].commentary)
    // and the md table keeps its single-line cells (unchanged at ≥768)
    for (const f of ['current', 'prior', 'change']) {
      expect(layout(container, 'table').querySelector(`[data-metric-field="${f}"]`)!.closest('.whitespace-nowrap')).not.toBeNull()
    }
  })

  it('renders the per-ADS annotation inside the table’s Current cell, and in the card on its own line under the figures', () => {
    const { container } = render(<FinancialMetricsTable metrics={FULL} bare />)
    const card = cardList(container)[2]
    const row = bodyRows(container)[2]
    expect(card).toBeDefined()
    expect(row).toBeDefined()
    const inCard = card.querySelector('[data-metric-field="per-ads"]')!
    const inRow = row.querySelector('[data-metric-field="per-ads"]')!
    expect(text(inCard)).toContain('≈ CNY 45.6 per ADS')
    expect(text(inRow)).toBe(text(inCard))
    expect(inCard.closest('dl')).toBeNull() // outside the Current / Prior / Change line
    expect(inCard.compareDocumentPosition(card.querySelector('dl')!) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy()
    expect(inRow.closest('td')).toBe(row.querySelectorAll('td')[1]) // the Current cell
    expect(within(card).getByText(/CNY 5.7 per ordinary share/)).toBeInTheDocument()
    // rows without the annotation carry none, in either layout
    expect(all(cardList(container)[0], '[data-metric-field="per-ads"]')).toHaveLength(0)
    expect(all(bodyRows(container)[0], '[data-metric-field="per-ads"]')).toHaveLength(0)
  })

  it('the md table is unchanged: five headers in order, the px-2 wrapper, numeric cells right-aligned in the data face', () => {
    const { container } = render(<FinancialMetricsTable metrics={FULL} bare />)
    const t = layout(container, 'table')
    expect(all(t, 'thead th').map(text)).toEqual(['Metric', 'Current Period', 'Prior Period', 'Change', 'Investor Takeaway'])
    expect(tokens(t.firstElementChild!)).toContain('px-2')
    expect(all(t, 'tbody tr:first-child td').slice(1, 4).map(tokens)).toSatisfy((cells: string[][]) =>
      cells.every((c) => c.includes('text-right') && c.includes('font-data') && c.includes('tabular-nums')),
    )
    expect(tokens(t.querySelector('[data-metric-field="name"]')!)).toEqual(expect.arrayContaining(['flex', 'flex-col', 'font-medium']))
    expect(tokens(t.querySelector('thead tr')!)).toContain('text-xs')
    expect(tokens(t.querySelector('table')!)).toContain('text-sm')
  })

  it('card type never drops below the table’s: text-sm on the list root, no smaller utility on a name, value or takeaway', () => {
    const { container } = render(<FinancialMetricsTable metrics={FULL} bare />)
    expect(tokens(layout(container, 'cards'))).toContain('text-sm')
    const card = cardList(container)[0]
    for (const sel of ['[data-metric-field="name"] > span', 'dd', '[data-metric-field="takeaway"] > span:first-child']) {
      for (const el of all(card, sel)) expect(tokens(el).filter((t) => /^text-(xs|data-xs|\[)/.test(t)), sel).toEqual([])
    }
  })

  it('carries no id in either layout — two instances side by side still leave the document’s ids unique', () => {
    const { container } = render(
      <>
        <FinancialMetricsTable metrics={FULL} bare />
        <FinancialMetricsTable metrics={FULL} bare />
      </>,
    )
    expect(all(container, '[data-metric-card]')).toHaveLength(FULL.length * 2)
    expect(all(container, 'tbody tr')).toHaveLength(FULL.length * 2)
    const ids = all(document.body, '[id]').map((e) => e.id)
    expect(ids).toEqual([]) // chip ids exist only while a popover is open
    expect(new Set(ids).size).toBe(ids.length)
    // nothing is hidden from AT by hand: the hiding is display:none at the breakpoint (browser spec)
    expect(all(container, '[aria-hidden="true"]').filter((e) => e.tagName.toLowerCase() !== 'svg')).toHaveLength(0)
  })

  it('switches the two layouts by the md breakpoint classes inside one wrapper, the list an explicit role="list"', () => {
    const { container } = render(<FinancialMetricsTable metrics={FULL} bare />)
    // one element for the parent's space-y: a hidden sibling must not earn the other layout a margin
    expect(container.children).toHaveLength(1)
    expect(container.firstElementChild!.children).toHaveLength(2)
    const cards = layout(container, 'cards')
    const table = layout(container, 'table')
    expect(cards).toHaveAttribute('role', 'list')
    expect(cards.tagName).toBe('UL')
    expect(tokens(cards)).toContain('md:hidden')
    expect(tokens(cards)).not.toContain('hidden')
    expect(tokens(table)).toEqual(expect.arrayContaining(['hidden', 'md:block']))
  })

  it('composes with bare and with the self-contained Card: notes once, title once, both layouts inside', () => {
    const bare = render(<FinancialMetricsTable metrics={FULL} notes="Figures in millions." bare />)
    expect(bare.getAllByText('Figures in millions.')).toHaveLength(1)
    expect(bare.queryByText('Financial Highlights')).toBeNull()
    expect(tokens(layout(bare.container, 'cards'))).not.toContain('px-5')
    expect(cardList(bare.container)).toHaveLength(3)
    expect(bodyRows(bare.container)).toHaveLength(3)
    bare.unmount()

    const card = render(<FinancialMetricsTable metrics={FULL} notes="Figures in millions." />)
    expect(card.getAllByText('Figures in millions.')).toHaveLength(1)
    expect(card.getByText('Financial Highlights')).toBeInTheDocument()
    expect(tokens(layout(card.container, 'cards'))).toEqual(expect.arrayContaining(['px-5', 'py-4']))
    expect(factsOf(layout(card.container, 'cards'))).toEqual(factsOf(layout(card.container, 'table')))
  })

  it('renders nothing for no rows', () => {
    const { container } = render(<FinancialMetricsTable metrics={[]} bare />)
    expect(container).toBeEmptyDOMElement()
  })
})

/**
 * Codex review of #1108: a source surface opened from one layout must not outlive it. Rotating a
 * phone across 768px hides the card list (CSS) while a card chip's sheet is open; the sheet used to
 * stay over the table and, closed, return focus to the display:none chip. Here the breakpoint is
 * modelled the way the browser reports it to SourceTrace: the hidden layout's elements have no client
 * rects, and the viewport fires `resize`.
 */
describe('FinancialMetricsTable — a breakpoint that hides an open chip (Codex review of #1108)', () => {
  let hidden: 'cards' | 'table' = 'table'
  const restore: Array<() => void> = []
  afterEach(() => {
    restore.splice(0).forEach((undo) => undo())
  })

  function setup(pointer: 'coarse' | 'fine', initiallyHidden: 'cards' | 'table') {
    hidden = initiallyHidden
    const mm = vi.spyOn(window, 'matchMedia').mockImplementation(
      (query: string) =>
        ({
          matches: query === '(pointer: coarse)' ? pointer === 'coarse' : false,
          media: query,
          addEventListener: () => {},
          removeEventListener: () => {},
          addListener: () => {},
          removeListener: () => {},
          onchange: null,
          dispatchEvent: () => false,
        }) as unknown as MediaQueryList,
    )
    const rects = vi.spyOn(HTMLElement.prototype, 'getClientRects').mockImplementation(function (this: HTMLElement) {
      return (this.closest(`[data-metrics-layout="${hidden}"]`) ? [] : [{}]) as unknown as DOMRectList
    })
    restore.push(() => mm.mockRestore(), () => rects.mockRestore())
    render(<FinancialMetricsTable metrics={FULL} />)
  }
  const inLayout = (layout: 'cards' | 'table') => within(document.querySelector<HTMLElement>(`[data-metrics-layout="${layout}"]`)!)
  const crossBreakpoint = (nowHidden: 'cards' | 'table') => {
    hidden = nowHidden
    act(() => {
      window.dispatchEvent(new Event('resize'))
    })
  }

  it('touch: a card chip’s sheet closes when the cards are hidden, and focus goes to the same chip in the table', () => {
    setup('coarse', 'table')
    const cardChip = inLayout('cards').getAllByRole('button', { name: 'Source: Verified in filing' })[0]
    act(() => cardChip.focus())
    fireEvent.click(cardChip)
    const sheet = screen.getByRole('dialog', { name: 'Source detail' })
    expect(sheet.contains(document.activeElement)).toBe(true)

    crossBreakpoint('cards') // rotated to landscape: the table is the layout shown
    expect(screen.queryByRole('dialog', { name: 'Source detail' })).toBeNull()
    expect(document.activeElement).toBe(inLayout('table').getAllByRole('button', { name: 'Source: Verified in filing' })[0])
  })

  it('keyboard: a table chip’s popover closes when the table is hidden, and focus goes to the same chip in its card', () => {
    setup('fine', 'cards')
    const tableChip = inLayout('table').getByRole('link', { name: 'Source: Revenue · SEC XBRL' })
    act(() => tableChip.focus())
    const tablePopover = screen.getByRole('group', { name: 'Source detail' })

    crossBreakpoint('table') // narrowed below md: the cards are the layout shown
    expect(tablePopover).not.toBeInTheDocument()
    expect(document.activeElement).toBe(inLayout('cards').getByRole('link', { name: 'Source: Revenue · SEC XBRL' }))
    // Focus on the twin opens the twin's own popover, as focus on any chip does: one surface, not two.
    expect(screen.getAllByRole('group', { name: 'Source detail' })).toHaveLength(1)
  })

  it('keyboard: when the browser blurs the hidden chip before any resize, focus still goes to its twin', () => {
    setup('fine', 'table')
    const cardChip = inLayout('cards').getByRole('link', { name: 'Source: Revenue · SEC XBRL' })
    act(() => cardChip.focus())
    hidden = 'cards' // the breakpoint flipped; Chromium's focus fixup blurs the chip in a task of its own
    act(() => cardChip.blur())
    expect(document.activeElement).toBe(inLayout('table').getByRole('link', { name: 'Source: Revenue · SEC XBRL' }))
    expect(screen.getAllByRole('group', { name: 'Source detail' })).toHaveLength(1)
  })

  it('a hover popover closes with its layout and moves no focus; a resize that keeps the chip shown keeps a sheet open', () => {
    setup('fine', 'cards')
    fireEvent.mouseEnter(inLayout('table').getByRole('link', { name: 'Source: Revenue · SEC XBRL' }))
    expect(screen.getByRole('group', { name: 'Source detail' })).toBeInTheDocument()
    crossBreakpoint('table')
    expect(screen.queryByRole('group', { name: 'Source detail' })).toBeNull()
    expect(document.activeElement).toBe(document.body)
  })

  it('touch: a ui/Modal raised above the sheet keeps focus when a rotation closes the sheet beneath it', () => {
    setup('coarse', 'table')
    fireEvent.click(inLayout('cards').getAllByRole('button', { name: 'Source: Verified in filing' })[0])
    expect(screen.getByRole('dialog', { name: 'Source detail' })).toBeInTheDocument()
    // An upper layer (the Feedback dialog, through ui/Modal's marker) opened over the sheet holds focus.
    const upper = document.createElement('div')
    upper.setAttribute('data-ui-modal', 'true')
    upper.innerHTML = '<button type="button">modal action</button>'
    document.body.appendChild(upper)
    restore.push(() => upper.remove())
    const inModal = within(upper).getByRole('button', { name: 'modal action' })
    act(() => inModal.focus())

    crossBreakpoint('cards') // rotated: the sheet's chip is hidden, so the sheet closes beneath the modal
    expect(screen.queryByRole('dialog', { name: 'Source detail' })).toBeNull()
    expect(document.activeElement).toBe(inModal)
  })

  it('touch: a resize that leaves the chip rendered (an on-screen keyboard, a small window change) keeps the sheet open', () => {
    setup('coarse', 'table')
    fireEvent.click(inLayout('cards').getAllByRole('button', { name: 'Source: Verified in filing' })[0])
    crossBreakpoint('table') // still a phone: the cards stay shown
    expect(screen.getByRole('dialog', { name: 'Source detail' })).toBeInTheDocument()
  })
})
