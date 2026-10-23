'use client'

import { useId, type ReactNode } from 'react'
import { MinusIcon, TrendDownIcon, TrendUpIcon } from '@/lib/icons'
import { parseNumeric } from '@/lib/format'
import { directionText, type Direction } from '@/lib/financialTone'
import { MetricSourceLink } from '@/features/filings/components/MetricSourceLink'
import { SourceTrace } from '@/features/filings/components/SourceTrace'
import { PerAdsNote } from '@/features/summaries/components/PerAdsNote'
import { formatMetricValue, isMissing } from '@/features/summaries/lib/metricValue'
import { TAKEAWAY_PASSAGE_NOTE, type FigureEvidence } from '@/features/filings/lib/evidenceLabels'
import { Card, CardHeader, CardTitle, CardFooter, DataTable, MissingValue, cx, type Column, type CellTone } from '@/components/ui'
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
  // The figure check (backend provenance_service.build_metric_source): each compared period's filed amount in
  // words, the summary's own text for a period the server replaced with the filed figure, and a takeaway withheld
  // because it quoted a replaced figure.
  source_filed?: FigureEvidence['filed']
  source_replaced?: FigureEvidence['replaced']
  commentary_withheld?: 'figure_replaced' | null
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

/** A figure column's heading: the period itself ("FY2025") over the date it ends ("to Sep 27, 2025"). */
export interface PeriodHeading {
  label: string
  detail?: string
}

interface FinancialMetricsTableProps {
  metrics?: FinancialMetric[]
  /** Footer note; a node lets a caller emphasise a phrase (the landing page's evidence card). */
  notes?: ReactNode
  // Embed mode (T2.4): render just the table (+ notes) without the wrapping Card / "Financial
  // Highlights" header, because the structured page's section Card already supplies that title.
  // Default false preserves the self-contained card for the standalone/legacy call sites.
  bare?: boolean
  /** The figure columns' periods; without them the headings read "Current period" and "Prior period". */
  periods?: { current: PeriodHeading; prior: PeriodHeading }
  /** Says how the Change column is computed: its heading takes a dagger and the note follows the footer's. */
  changeNote?: string
  /** The accessible name of the table and of the phone cards' list, in place of the generic one. */
  caption?: string
  /** Where the cards give way to the table: at the md viewport (the default), or at the component's own width of
   *  52rem (`container`), for a caller whose column stays narrow on a desktop screen (the landing page's evidence row). */
  layoutBy?: 'viewport' | 'container'
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
      sectionRef={row.source_section_ref}
      filed={row.source_filed}
      replaced={row.source_replaced}
      takeawayWithheld={row.commentary_withheld === 'figure_replaced'}
      layoutTwin={twin}
    />
  </div>
)

const currentField = (row: FinancialMetric): ReactNode => (
  <span data-metric-field="current" className="text-text-primary-light dark:text-text-primary-dark">
    {formatMetricValue(row.current_period) || <MissingValue />}
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
    {formatMetricValue(row.prior_period) || <MissingValue />}
  </span>
)

const changeIcon = (direction: FinancialMetric['change_direction']) =>
  direction === 'up' ? TrendUpIcon : direction === 'down' ? TrendDownIcon : MinusIcon

/**
 * The server-computed change, verbatim, with its direction glyph. Default = the md table's cell
 * (inline-flex; its column wrapper adds `whitespace-nowrap`, as before), where the figure sits in a box
 * `figureCh` characters wide, the column's longest change in the data face: the glyphs then share one
 * left edge and the figures one right edge, however long each is. `flow` = the card's wrapping inline
 * text: the glyph rides inline there because an inline-flex text item has min-width:auto and could
 * never break a long change string.
 */
const changeField = (row: FinancialMetric, flow = false, figureCh = 0): ReactNode => {
  // Server-computed string only — no client-side delta math (single-source gate). With none served, or the token
  // alone, the change is MissingValue, read as "unavailable".
  if (isMissing(row.change_display)) {
    return (
      <span data-metric-field="change" className="text-text-tertiary-light dark:text-text-secondary-dark">
        <MissingValue />
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
      <span className="text-right" style={figureCh > 0 ? { minWidth: `${figureCh}ch` } : undefined}>
        {row.change_display}
      </span>
    </span>
  )
}

const takeawayField = (row: FinancialMetric, twin?: string): ReactNode => (
  <div data-metric-field="takeaway" className="flex flex-col gap-1">
    {/* A row the summary wrote no takeaway for: the missing-value element, read as "no takeaway" (E145), and no chip,
        whose panel would cite a passage for a takeaway the row does not have. */}
    <span className="text-text-secondary-light dark:text-text-secondary-dark">
      {isMissing(row.commentary) ? <MissingValue label="no takeaway" /> : row.commentary}
    </span>
    {row.commentary_evidence && !isMissing(row.commentary) && (
      <SourceTrace
        url={row.commentary_evidence.fragment_url}
        verified={row.commentary_evidence.verified}
        sectionRef={row.commentary_evidence.section_ref}
        excerpt={row.commentary_evidence.verified ? row.commentary_evidence.excerpt : null}
        // A takeaway is a sentence the summary wrote, so the panel says what was checked: the passage it
        // cites, not the takeaway itself. Unverified evidence keeps the panel's own "Section linked" line.
        note={row.commentary_evidence.verified ? TAKEAWAY_PASSAGE_NOTE : null}
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
// A card's year groups: one floor in rem, capped at the row, so the next group starts at the same offset in every card.
const GROUP = 'min-w-[min(5rem,100%)]'

/** A figure column's md heading: the period in the header's register, the date it ends on a quieter line. */
const periodHeader = (period: PeriodHeading | undefined, fallback: string): ReactNode =>
  period ? (
    <>
      {period.label}
      {period.detail && <span className="block whitespace-nowrap font-normal normal-case tracking-normal">{period.detail}</span>}
    </>
  ) : (
    fallback
  )

/** "Change", with the dagger that points at the footer's note on how the column is computed. */
const changeHeader = (marked: boolean): ReactNode =>
  marked ? (
    <>
      Change<span aria-hidden="true">†</span>
      <span className="sr-only">, calculated</span>
    </>
  ) : (
    'Change'
  )

export default function FinancialMetricsTable({
  metrics,
  notes,
  bare = false,
  periods,
  changeNote,
  caption: label,
  layoutBy = 'viewport',
}: FinancialMetricsTableProps) {
  const twinBase = useId()
  if (!metrics || metrics.length === 0) {
    return null
  }
  // Every chip renders twice, once per layout; `layoutTwin` pairs the two copies so a source sheet or
  // popover opened from one closes, with focus moving to the other, when a breakpoint hides its
  // layout (a phone rotated across 768px). Per instance, so two tables on a page never pair.
  const twin = (row: FinancialMetric, field: 'name' | 'takeaway') => `${twinBase}${metrics.indexOf(row)}-${field}`

  const hasComparatives = metrics.some((metric) => parseNumeric(metric.prior_period) !== null)
  const caption =
    label ??
    (hasComparatives
      ? 'Financial highlights: current period, prior period, change, and investor takeaway per metric'
      : 'Financial highlights: current period and investor takeaway per metric')
  // The width of the change figures' box (changeField): the column's longest served change, in characters.
  const changeCh = Math.max(0, ...metrics.map((row) => (isMissing(row.change_display) ? 0 : row.change_display!.trim().length)))

  // md and up: the DataTable. The metric name is each row's header, so a screen reader announces a figure with its
  // metric and its period; cells align to the top, so a figure sits on its metric's line rather than between the name
  // and its chip, and headings to the bottom, so a two-line period heading shares the rule with one-line ones; the
  // takeaway column's inset keeps the last figure from running into the first word of prose.
  const columns: Column<FinancialMetric>[] = [
    // The chip keeps one line beside long takeaways, so the column is as wide as its longest chip and no wider (the
    // chip's panel is portalled to the body, so the rule reaches the chip alone).
    {
      key: 'metric',
      header: 'Metric',
      rowHeader: true,
      render: (row) => (
        <div className="[&_a]:whitespace-nowrap [&_button]:whitespace-nowrap">{nameField(row, twin(row, 'name'))}</div>
      ),
    },
    {
      key: 'current_period',
      header: periodHeader(periods?.current, 'Current Period'),
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
            header: periodHeader(periods?.prior, 'Prior Period'),
            align: 'right',
            numeric: true,
            render: (row) => <span className="whitespace-nowrap">{priorField(row)}</span>,
          },
          {
            key: 'change',
            header: changeHeader(!!changeNote),
            align: 'right',
            numeric: true,
            tone: (row) => row.change_tone ?? undefined,
            render: (row) => <span className="whitespace-nowrap">{changeField(row, false, changeCh)}</span>,
          },
        ] satisfies Column<FinancialMetric>[])
      : []),
    { key: 'commentary', header: 'Investor Takeaway', className: 'pl-8', render: (row) => takeawayField(row, twin(row, 'takeaway')) },
  ]

  // Two presentations of the same rows, switched by CSS alone (`md` = 768px, the documented
  // breakpoint): below md the five-column table squeezed the takeaway to ~115px and left ~400px-tall
  // near-empty rows, so each metric is one stacked card there; at/above md the DataTable. The
  // inactive layout is display:none — out of the accessibility tree and the tab
  // order (the SummaryBlocks section nav uses the same idiom) — and neither layout carries an id of
  // its own (SourceTrace's useId ids are per instance and exist only on an open panel), so the
  // duplicate is inert. A JS media query would render one layout on the server for every viewer and
  // flip after hydration; CSS keeps SSR deterministic and the switch exact (no mixed state).
  // `layoutBy="container"` moves the same switch to the component's own width: the table's figure columns, with
  // one-line chips and dates, take about 33rem, so below 52rem of its own the takeaway shrinks to the ribbon the
  // cards exist to avoid (the landing page's content column is 42rem at 1024px). In rem, so it moves with the
  // reader's text size; SourceTrace's twin hand-off reads which chip is rendered, not a breakpoint.
  const byContainer = layoutBy === 'container'
  const table = (
    <div data-metrics-layout="table" className={byContainer ? 'hidden [@container(min-width:52rem)]:block' : 'hidden md:block'}>
      <DataTable
        columns={columns}
        rows={metrics}
        rowKey={(row, index) => `${row.metric}-${index}`}
        caption={caption}
        verticalAlign="top"
        className="px-2"
      />
    </div>
  )

  // Below md: one card per metric — every cell of the row in reading order. Name + figure chip; the
  // figures as a <dl> under the table's column names (visible "Current / Prior / Change", or the
  // periods' own labels, with an sr-only "period" after the generic ones so AT hears the headers'
  // words; the short labels are what keep the three groups on one line at 390px, and the groups wrap
  // as units — never clip — for longer values; the first two hold at least 5rem, never more than the
  // row, so the groups start at the same offsets in every card while they fit); the ADR
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
      className={cx('space-y-3 text-sm', byContainer ? '[@container(min-width:52rem)]:hidden' : 'md:hidden', !bare && 'px-cap-5 py-4')}
    >
      {metrics.map((row, index) => (
        <li
          key={`${row.metric}-${index}`}
          data-metric-card
          className="min-w-0 rounded-lg border border-border-light bg-white p-3 [overflow-wrap:anywhere] dark:border-white/10 dark:bg-white/5"
        >
          {nameField(row, twin(row, 'name'))}
          <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-2">
            <div className={GROUP}>
              <dt className={EYEBROW}>
                {periods ? periods.current.label : <>Current<span className="sr-only"> period</span></>}
              </dt>
              <dd className={FIGURE}>{currentField(row)}</dd>
            </div>
            {hasComparatives && (
              <>
                <div className={GROUP}>
                  <dt className={EYEBROW}>
                    {periods ? periods.prior.label : <>Prior<span className="sr-only"> period</span></>}
                  </dt>
                  <dd className={FIGURE}>{priorField(row)}</dd>
                </div>
                <div className="min-w-0">
                  <dt className={EYEBROW}>{changeHeader(!!changeNote)}</dt>
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

  // One element for the parent: a SummaryBlocks section body spaces its children with `space-y-4`,
  // whose selector (`> :not([hidden]) ~ :not([hidden])`) reads sibling order, not display — a bare
  // fragment would hand the desktop table a 16px top margin it never had when the (CSS-hidden)
  // card list precedes it, and the phone list one when the table precedes it.
  const layouts = (
    <div className={byContainer ? '[container-type:inline-size]' : undefined}>
      {cards}
      {table}
    </div>
  )

  // The footer: the caller's notes, then the Change column's dagger note.
  const footer =
    notes || changeNote ? (
      <>
        {notes}
        {notes && changeNote ? ' ' : null}
        {changeNote && (
          <>
            <span aria-hidden="true">† </span>
            {changeNote}
          </>
        )}
      </>
    ) : null

  // Embedded in a structured-page section Card — no wrapping Card / header (that would double the
  // "Financial Highlights" title). Notes render ONCE, after both presentations, as a plain
  // trailing paragraph instead of a footer.
  if (bare) {
    return (
      <>
        {layouts}
        {footer && (
          <p className="mt-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">{footer}</p>
        )}
      </>
    )
  }

  return (
    <Card className="overflow-hidden">
      <CardHeader>
        {/* Sentence case, as every card title: the summary's own section heading is the backend's schema
            title ("Financial Highlights", summary_sections.py), which this standalone card does not show. */}
        <CardTitle>Financial highlights</CardTitle>
      </CardHeader>
      {layouts}
      {footer && (
        <CardFooter>
          <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">{footer}</p>
        </CardFooter>
      )}
    </Card>
  )
}
