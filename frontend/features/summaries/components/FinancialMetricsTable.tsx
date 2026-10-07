'use client'

import { useId, type ReactNode } from 'react'
import { MinusIcon, TrendDownIcon, TrendUpIcon } from '@/lib/icons'
import { fmtCurrency, fmtPercent, fmtScale, parseNumeric } from '@/lib/format'
import { directionText, type Direction } from '@/lib/financialTone'
import { MetricSourceLink } from '@/features/filings/components/MetricSourceLink'
import { SourceTrace } from '@/features/filings/components/SourceTrace'
import { PerAdsNote } from '@/features/summaries/components/PerAdsNote'
import { Card, CardHeader, CardTitle, CardFooter, DataTable, cx, type Column, type CellTone } from '@/components/ui'
import type { PerAdsValue } from '@/types/summary'
import type { BlockEvidence } from '@/features/summaries/api/summaries-api'

// A type alias (not an interface) so it satisfies DataTable's
// `T extends Record<string, unknown>` constraint via the implied index signature.
export type FinancialMetric = {
  metric: string
  current_period: string
  prior_period: string
  commentary?: string
  source_url?: string | null
  source_verified?: boolean | null
  source_section_ref?: string | null
  xbrl_concept?: string | null
  per_ads?: PerAdsValue | null
  // Change is computed server-side by metric_delta_service (one policy; ppts for margins). The
  // client renders this string verbatim and does NO delta math (rule 12 single-source gate).
  change_display?: string | null
  change_direction?: 'up' | 'down' | 'flat' | null
  change_tone?: CellTone | null
  // T4: server-verified citation for the Investor-Takeaway (`commentary`) — a text-anchored deep link,
  // distinct from the XBRL number provenance above (MetricSourceLink).
  commentary_evidence?: BlockEvidence | null
}

interface FinancialMetricsTableProps {
  metrics?: FinancialMetric[]
  /** Footer note; a node lets a caller emphasise a phrase (the landing page's evidence card). */
  notes?: ReactNode
  // Embed mode (T2.4): render just the table (+ notes) without the wrapping Card / "Financial
  // Highlights" header, because the structured page's section Card already supplies that title.
  // Default false preserves the self-contained card for the standalone/legacy call sites.
  bare?: boolean
}

const formatMetricValue = (value: string): string => {
  if (!value) {
    return ''
  }

  const numeric = parseNumeric(value)
  if (numeric === null) {
    return value
  }

  if (value.includes('%')) {
    return fmtPercent(numeric)
  }

  if (value.includes('$')) {
    return fmtCurrency(numeric)
  }

  return fmtScale(numeric, { digits: 2 })
}

/* -------------------------------------------------------------------------------------------------
 * EN-03: one renderer per field, shared by the md table's cells and the phone cards below.
 *
 * Parity is structural — a field cannot appear in one presentation and not the other. Each renderer
 * marks ONE element with `data-metric-field` (name | current | per-ads | prior | change | takeaway):
 * the anchor that the render spec (tests/unit/FinancialMetricsCards.spec.tsx), the browser spec
 * (tests/e2e/metrics-stacked-cards.spec.ts) and the critique harness (tasks/critique-env-2026-10-04/
 * jobs-en03.json) count the same way in whichever layout is active. Keep the anchors. The change
 * element also echoes the server's direction and tone as data attributes — verbatim, no client
 * delta math (rule-12 single-source gate). Layout-only wrappers (the table's `whitespace-nowrap`,
 * the card's `<dd>`) stay OUTSIDE the shared element, so "unchanged at md+" and "never nowrap in a
 * card" are properties of the wrappers, not of the content.
 * ----------------------------------------------------------------------------------------------- */

const nameField = (row: FinancialMetric, twin?: string): ReactNode => (
  <div data-metric-field="name" className="flex flex-col font-medium text-text-primary-light dark:text-text-primary-dark">
    <span>{row.metric}</span>
    <MetricSourceLink
      url={row.source_url}
      verified={row.source_verified}
      concept={row.xbrl_concept}
      sectionRef={row.source_section_ref}
      layoutTwin={twin}
    />
  </div>
)

const currentField = (row: FinancialMetric): ReactNode => (
  <span data-metric-field="current" className="text-text-primary-light dark:text-text-primary-dark">
    {formatMetricValue(row.current_period)}
  </span>
)

/** The ADR annotation (ratio != 1 ADRs only): inside the Current cell in the table, its own line
 *  under the figures in a card, so the Current / Prior / Change line is never widened by it. */
const perAdsField = (row: FinancialMetric): ReactNode =>
  row.per_ads ? (
    <span data-metric-field="per-ads" className="block">
      <PerAdsNote perAds={row.per_ads} />
    </span>
  ) : null

const priorField = (row: FinancialMetric): ReactNode => (
  <span data-metric-field="prior" className="text-text-secondary-light dark:text-text-secondary-dark">
    {formatMetricValue(row.prior_period)}
  </span>
)

const changeIcon = (direction: FinancialMetric['change_direction']) =>
  direction === 'up' ? TrendUpIcon : direction === 'down' ? TrendDownIcon : MinusIcon

/**
 * The server-computed change, verbatim, with its direction glyph. Default = the md table's cell
 * (inline-flex; its column wrapper adds `whitespace-nowrap`, as before). `flow` = the card's wrapping
 * inline text: the glyph rides inline there because an inline-flex text item has min-width:auto and
 * could never break a long change string.
 */
const changeField = (row: FinancialMetric, flow = false): ReactNode => {
  // Server-computed string only — no client-side delta math (single-source gate).
  if (!row.change_display) {
    return (
      <span data-metric-field="change" className="text-text-tertiary-light dark:text-text-secondary-dark">
        —
      </span>
    )
  }
  const Icon = changeIcon(row.change_direction)
  const served = {
    'data-metric-field': 'change',
    'data-direction': row.change_direction ?? undefined,
    'data-tone': row.change_tone ?? undefined,
  }
  // Direction never rides on colour alone (financialTone rule): the glyph carries it visually and
  // the signed string carries it for assistive tech, so the glyph itself is decorative.
  if (flow) {
    return (
      <span {...served}>
        <Icon className="mr-1 inline-block h-4 w-4 align-text-bottom" aria-hidden="true" />
        {row.change_display}
      </span>
    )
  }
  return (
    <span {...served} className="inline-flex items-center gap-1">
      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
      {row.change_display}
    </span>
  )
}

const takeawayField = (row: FinancialMetric, twin?: string): ReactNode => (
  <div data-metric-field="takeaway" className="flex flex-col gap-1">
    <span className="text-text-secondary-light dark:text-text-secondary-dark">{row.commentary || '-'}</span>
    {row.commentary_evidence && (
      <SourceTrace
        url={row.commentary_evidence.fragment_url}
        verified={row.commentary_evidence.verified}
        sectionRef={row.commentary_evidence.section_ref}
        excerpt={row.commentary_evidence.verified ? row.commentary_evidence.excerpt : null}
        layoutTwin={twin}
      />
    )}
  </div>
)

// The md table colours its Change cell through DataTable's tone map (keyed by the server's
// change_tone). The card routes the SAME server tone through lib/financialTone.directionText — the
// delta-text recipe DESIGN_SYSTEM §4 names — plus the table's bold-for-a-move rule; the render spec
// pins the card's dd and the table's td to identical tone tokens so the two cannot drift.
const TONE_DIRECTION: Record<CellTone, Direction> = { gain: 'up', loss: 'down', flat: 'flat' }
const changeToneClass = (tone: CellTone): string => cx(directionText[TONE_DIRECTION[tone]], tone !== 'flat' && 'font-semibold')

// Card labels = the table's header register (DataTable's thead recipe: 12px uppercase eyebrow).
const EYEBROW = 'text-xs font-semibold uppercase tracking-eyebrow text-text-tertiary-light dark:text-text-secondary-dark'
// Card figures = the table's numeric-cell recipe (data face + tabular-nums at the table's text-sm).
const FIGURE = 'font-data text-sm tabular-nums'

export default function FinancialMetricsTable({ metrics, notes, bare = false }: FinancialMetricsTableProps) {
  const twinBase = useId()
  if (!metrics || metrics.length === 0) {
    return null
  }
  // Every chip renders twice, once per layout; `layoutTwin` pairs the two copies so a source sheet or
  // popover opened from one closes, with focus moving to the other, when a breakpoint hides its
  // layout (a phone rotated across 768px). Per instance, so two tables on a page never pair.
  const twin = (row: FinancialMetric, field: 'name' | 'takeaway') => `${twinBase}${metrics.indexOf(row)}-${field}`

  const hasComparatives = metrics.some((metric) => parseNumeric(metric.prior_period) !== null)
  const caption = hasComparatives
    ? 'Financial highlights: current period, prior period, change, and investor takeaway per metric'
    : 'Financial highlights: current period and investor takeaway per metric'

  // md and up: the DataTable exactly as before. Only the cell bodies moved into the shared
  // renderers; the nowrap wrappers, alignment, numeric face and tone column are the table's own.
  const columns: Column<FinancialMetric>[] = [
    { key: 'metric', header: 'Metric', render: (row) => nameField(row, twin(row, 'name')) },
    {
      key: 'current_period',
      header: 'Current Period',
      align: 'right',
      numeric: true,
      render: (row) => (
        <span className="whitespace-nowrap">
          {currentField(row)}
          {perAdsField(row)}
        </span>
      ),
    },
    ...(hasComparatives
      ? ([
          {
            key: 'prior_period',
            header: 'Prior Period',
            align: 'right',
            numeric: true,
            render: (row) => <span className="whitespace-nowrap">{priorField(row)}</span>,
          },
          {
            key: 'change',
            header: 'Change',
            align: 'right',
            numeric: true,
            tone: (row) => row.change_tone ?? undefined,
            render: (row) => <span className="whitespace-nowrap">{changeField(row)}</span>,
          },
        ] satisfies Column<FinancialMetric>[])
      : []),
    { key: 'commentary', header: 'Investor Takeaway', render: (row) => takeawayField(row, twin(row, 'takeaway')) },
  ]

  // Two presentations of the same rows, switched by CSS alone (`md` = 768px, the documented
  // breakpoint): below md the five-column table squeezed the takeaway to ~115px and left ~400px-tall
  // near-empty rows, so each metric is one stacked card there; at/above md the DataTable is
  // unchanged. The inactive layout is display:none — out of the accessibility tree and the tab
  // order (the SummaryBlocks section nav uses the same idiom) — and neither layout carries an id of
  // its own (SourceTrace's useId ids are per instance and exist only on an open panel), so the
  // duplicate is inert. A JS media query would render one layout on the server for every viewer and
  // flip after hydration; CSS keeps SSR deterministic and the switch exact (no mixed state).
  const table = (
    <div data-metrics-layout="table" className="hidden md:block">
      <DataTable
        columns={columns}
        rows={metrics}
        rowKey={(row, index) => `${row.metric}-${index}`}
        caption={caption}
        className="px-2"
      />
    </div>
  )

  // Below md: one card per metric — every cell of the row in reading order. Name + XBRL chip; the
  // figures as a <dl> under the table's column names (visible "Current / Prior / Change" with an
  // sr-only "period" so AT hears the headers' words; the short labels are what keep the three groups
  // on one line at 390px, and the groups wrap as units — never clip — for longer values); the ADR
  // annotation as its own line; the takeaway and its chip. Type never drops below the table's:
  // text-sm figures and prose, text-xs labels, chips as they are. `overflow-wrap: anywhere` on the
  // card (inherited by every text line) breaks even an unbreakable token inside its box, unlike
  // `break-words`, which cannot lower a flex item's min-content width; no nowrap, truncate,
  // line-clamp or fixed height anywhere in a card. The tile is the in-panel sub-surface
  // (HeroExample / TraceToSourceDemo: white + hairline, dark white/5, no shadow). role="list" is
  // explicit — WebKit drops list semantics, and with them the aria-label, from a `list-style: none`
  // list — and the list is named by the very caption that names the table.
  const cards = (
    <ul
      role="list"
      aria-label={caption}
      data-metrics-layout="cards"
      className={cx('space-y-3 text-sm md:hidden', !bare && 'px-5 py-4')}
    >
      {metrics.map((row, index) => (
        <li
          key={`${row.metric}-${index}`}
          data-metric-card
          className="min-w-0 rounded-lg border border-border-light bg-white p-3 [overflow-wrap:anywhere] dark:border-white/10 dark:bg-white/5"
        >
          {nameField(row, twin(row, 'name'))}
          <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-2">
            <div className="min-w-0">
              <dt className={EYEBROW}>
                Current<span className="sr-only"> period</span>
              </dt>
              <dd className={FIGURE}>{currentField(row)}</dd>
            </div>
            {hasComparatives && (
              <>
                <div className="min-w-0">
                  <dt className={EYEBROW}>
                    Prior<span className="sr-only"> period</span>
                  </dt>
                  <dd className={FIGURE}>{priorField(row)}</dd>
                </div>
                <div className="min-w-0">
                  <dt className={EYEBROW}>Change</dt>
                  <dd className={cx(FIGURE, row.change_tone && changeToneClass(row.change_tone))}>{changeField(row, true)}</dd>
                </div>
              </>
            )}
          </dl>
          {row.per_ads && <div className="mt-1">{perAdsField(row)}</div>}
          <div className="mt-3">{takeawayField(row, twin(row, 'takeaway'))}</div>
        </li>
      ))}
    </ul>
  )

  // One element for the parent: SummaryBlocks' CardBody spaces its children with `space-y-4`,
  // whose selector (`> :not([hidden]) ~ :not([hidden])`) reads sibling order, not display — a bare
  // fragment would hand the desktop table a 16px top margin it never had when the (CSS-hidden)
  // card list precedes it, and the phone list one when the table precedes it.
  const layouts = (
    <div>
      {cards}
      {table}
    </div>
  )

  // Embedded in a structured-page section Card — no wrapping Card / header (that would double the
  // "Financial Highlights" title). Notes render ONCE, after both presentations, as a plain
  // trailing paragraph instead of a footer.
  if (bare) {
    return (
      <>
        {layouts}
        {notes && (
          <p className="mt-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">{notes}</p>
        )}
      </>
    )
  }

  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <CardTitle>Financial Highlights</CardTitle>
      </CardHeader>
      {layouts}
      {notes && (
        <CardFooter>
          <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">{notes}</p>
        </CardFooter>
      )}
    </Card>
  )
}
