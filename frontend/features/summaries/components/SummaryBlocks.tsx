'use client'

import { useMemo, type ReactNode } from 'react'
import { Badge } from '@/components/ui'
import FinancialMetricsTable from '@/features/summaries/components/FinancialMetricsTable'
import { Callout } from '@/features/summaries/components/Callout'
import { SummaryRisks } from '@/features/summaries/components/SummaryRisks'
import { SourceTrace } from '@/features/filings/components/SourceTrace'
import { WHAT_CHANGED_ID, WhatChanged } from '@/features/filings/components/WhatChanged'
import { useSectionArrival } from '@/features/summaries/hooks/useSectionArrival'
import { SectionEmpty } from './SectionEmpty'
import { normalizeRisk } from '@/lib/formatters'
import type { RiskFactor } from '@/types/summary'
import type { BlockEvidence, ChangeReport, RenderedBlock, RenderedSection, Summary } from '@/features/summaries/api/summaries-api'
import { parseNumeric } from '@/lib/format'

// A block/row citation → the shared Trace-to-Source chip (T4). Renders nothing when there's nothing to
// trace (SourceTrace's own guard), so an unenriched or uncited block is unaffected. The excerpt is shown
// only when verified — an unverified model excerpt isn't presented as if it were confirmed filing text.
function EvidenceChip({ evidence }: { evidence?: BlockEvidence | null }) {
  if (!evidence) return null
  return (
    <SourceTrace
      url={evidence.fragment_url}
      verified={evidence.verified}
      sectionRef={evidence.section_ref}
      excerpt={evidence.verified ? evidence.excerpt : null}
    />
  )
}

// The risks section is special-cased so its per-risk Trace-to-Source chips survive (the generic
// block only carries string rows). Match on the backend's explicit `role` (an intentional contract),
// falling back to the title slug for any payload that predates the role field.
const RISKS_SECTION_ID = 'investment-risks-concerns'
const isRisksSection = (section: RenderedSection): boolean =>
  section.role === 'risks' || section.id === RISKS_SECTION_ID

// tone -> Badge variant (T1.2 treatment). neutral/unknown render nothing: tone is a schema field
// name, not user copy.
const TONE_VARIANT: Record<string, 'brand' | 'warning'> = {
  positive: 'brand',
  cautious: 'warning',
}

const INK = 'text-text-primary-light dark:text-text-primary-dark'
const MUTED = 'text-text-secondary-light dark:text-text-secondary-dark'
const HAIRLINE = 'border-border-light dark:border-white/10'

/** "01", "02", … — the data-face index a section shares with its table-of-contents entry. */
const sectionIndex = (i: number) => String(i + 1).padStart(2, '0')

interface PageSection {
  id: string
  title: string
  tone?: string
  body: ReactNode
}

interface SummaryBlocksProps {
  sections: RenderedSection[]
  /** The full summary — read only for the risks section's enriched provenance (source traces). */
  summary: Summary
  /** The period-over-period change report; rendered as section 02 territory when it has changes. */
  whatChanged?: ChangeReport | null
}

/**
 * The single web surface for a filing summary (T2): renders the backend's `rendered_sections`
 * projection — the SAME Section/Block list that feeds the PDF and CSV — as one scrolling page with an
 * indexed table of contents. Replaces the ReactMarkdown card, the tabbed SummarySections, and the
 * standalone metrics table, so a number has exactly one home on the page.
 *
 * "Quiet ledger" (2026-10 critique, P-05 / P-07): hierarchy comes from type, not containers. Each
 * section is a 20/28 heading with a data-face index ("01") that matches its table-of-contents entry,
 * set straight on the page with no card; hairlines live inside the content (tables, evidence rows),
 * not around it. The change report, when the filing has one, is the section right after the first
 * metrics section. Subheadings are 14/600 headings, never uppercase eyebrows (eyebrows are for
 * metric labels only).
 */
export function SummaryBlocks({ sections, summary, whatChanged }: SummaryBlocksProps) {
  // Enriched, placeholder-filtered risks (with source_url/verified) for the risks special-case.
  const risks = useMemo<RiskFactor[]>(() => {
    const sections = summary.raw_summary?.sections as { risks?: unknown; risk_factors?: unknown } | undefined
    const raw = sections?.risks ?? sections?.risk_factors
    if (!Array.isArray(raw)) return []
    return raw.map((r) => normalizeRisk(r)).filter((r): r is RiskFactor => Boolean(r))
  }, [summary.raw_summary])
  const riskOwner = summary.raw_summary?.risk_source_context_version
  const riskProjection = riskOwner === 1 ? (
    summary.raw_summary?.sections as {
      _risk_source_projection?: {
        version?: number
        verified_count?: number
        withheld_count?: number
        candidate_count?: number
        source_available?: boolean
      }
    } | undefined
  )?._risk_source_projection : undefined
  const withChanges = Boolean(whatChanged?.has_changes) && !(sections ?? []).some((section) => section.id === WHAT_CHANGED_ID)
  useSectionArrival([...(sections ?? []).map((section) => section.id), ...(withChanges ? [WHAT_CHANGED_ID] : [])].join(' '))

  if (!sections?.length) {
    return <SectionEmpty label="summary" />
  }

  const pageSections: PageSection[] = sections.map((section) => ({
    id: section.id,
    title: section.title,
    tone: section.tone,
    body: isRisksSection(section) ? (
      <SummaryRisks risks={risks} projection={riskProjection} />
    ) : (
      section.blocks.map((block, i) => <BlockView key={i} block={block} />)
    ),
  }))
  if (whatChanged && withChanges) {
    const metricsAt = sections.findIndex((section) => section.blocks.some((block) => block.kind === 'metrics'))
    pageSections.splice(metricsAt === -1 ? 1 : metricsAt + 1, 0, {
      id: WHAT_CHANGED_ID,
      title: 'What changed',
      body: <WhatChanged report={whatChanged} bare />,
    })
  }

  return (
    <div className="lg:grid lg:grid-cols-[10rem_minmax(0,1fr)] lg:gap-8">
      {/* Sticky table of contents, widescreen only (it would crowd a reflowed reading column), on the
          reading side of the page: each entry carries its section's index. */}
      <aside className="hidden lg:block">
        <nav aria-label="Summary sections" className="sticky top-24">
          <p className={`mb-3 text-xs font-medium ${MUTED}`}>On this page</p>
          <ol role="list" className="space-y-1">
            {pageSections.map((section, i) => (
              <li key={section.id}>
                <a
                  href={`#${section.id}`}
                  className={`flex gap-2.5 rounded py-1 text-sm transition-colors duration-fast hover:text-text-primary-light focus-visible:outline-none focus-visible:shadow-ring-brand dark:hover:text-text-primary-dark dark:focus-visible:shadow-ring-brand-dark ${MUTED}`}
                >
                  <span aria-hidden="true" className="font-data text-xs leading-5 text-brand-strong dark:text-brand-strong-dark">
                    {sectionIndex(i)}
                  </span>
                  <span className="min-w-0">{section.title}</span>
                </a>
              </li>
            ))}
          </ol>
        </nav>
      </aside>

      <div className="min-w-0">
        {/* Outside the spaced stack: Tailwind 3's space-y margins every child after a sibling without
            the hidden attribute, so this display:none-at-lg nav pushed section 01 44px below the TOC
            on wide screens. Its own bottom margin keeps the phone gap. */}
        <MobileSectionNav sections={pageSections} />
        <div className="space-y-11">
          {pageSections.map((section, i) => {
            const toneVariant = section.tone ? TONE_VARIANT[section.tone.toLowerCase()] : undefined
            return (
              <section
                key={section.id}
                id={section.id}
                aria-labelledby={`${section.id}-heading`}
                className="scroll-mt-32 lg:scroll-mt-24"
              >
                <div className="flex items-baseline gap-3">
                  <span aria-hidden="true" className={`font-data text-xs tabular-nums ${MUTED}`}>
                    {sectionIndex(i)}
                  </span>
                  <h2 id={`${section.id}-heading`} className="min-w-0 text-xl font-semibold">
                    {section.title}
                  </h2>
                  {toneVariant && (
                    <Badge variant={toneVariant} className="shrink-0 self-center capitalize">
                      {section.tone}
                    </Badge>
                  )}
                </div>
                <div className="mt-4 space-y-4">{section.body}</div>
              </section>
            )
          })}
        </div>
      </div>
    </div>
  )
}

/**
 * Compact jump-nav for narrow layouts, where the sticky TOC aside is hidden: a horizontally
 * scrolling strip of anchor chips pinned under the site header. Plain anchors (not a <select>
 * that navigates onChange) so arrow-key browsing never triggers an unexpected jump, and every
 * chip is reachable by Tab with the brand focus ring. The two navs never coexist in the
 * accessibility tree (each is display:none at the other breakpoint), so their labels can differ.
 */
function MobileSectionNav({ sections }: { sections: PageSection[] }) {
  return (
    <nav
      aria-label="Jump to section"
      className="sticky top-16 z-sticky -mx-4 mb-11 border-b border-border-light bg-background-light/95 px-4 backdrop-blur-xl sm:-mx-6 sm:px-6 lg:hidden dark:border-border-dark dark:bg-background-dark/95"
    >
      <ul className="flex gap-2 overflow-x-auto py-2 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {sections.map((section, i) => (
          <li key={section.id} className="shrink-0">
            <a
              href={`#${section.id}`}
              className="inline-flex min-h-9 items-center gap-1.5 whitespace-nowrap rounded-full border border-border-light bg-panel-light px-3 text-xs font-medium text-text-secondary-light shadow-e1 transition-colors hover:bg-brand-weak hover:text-brand-strong focus-visible:outline-none focus-visible:shadow-ring-brand dark:border-white/10 dark:bg-panel-dark dark:text-text-secondary-dark dark:shadow-none dark:hover:bg-white/5 dark:hover:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark"
            >
              <span aria-hidden="true" className="font-data text-brand-strong dark:text-brand-strong-dark">
                {sectionIndex(i)}
              </span>
              {section.title}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  )
}

/** One Block.kind → one renderer. The backend already strips field-name scaffolding, so text
    blocks render as plain prose (no ReactMarkdown needed). Unknown kinds render nothing. */
function BlockView({ block }: { block: RenderedBlock }) {
  switch (block.kind) {
    case 'paragraph':
      return block.text ? (
        // Justified body copy with hyphenation at ≥sm only, matching the .markdown-body prose treatment
        // (T1.7; v3 Q3 keeps phone-width panes ragged-right). Body ink: the summary is the document.
        <p className={`leading-relaxed sm:text-justify sm:[hyphens:auto] ${INK}`}>
          {block.text}
        </p>
      ) : null

    case 'subheading':
      // A 14/600 heading under the section's h2, in sentence register: never an uppercase eyebrow.
      return block.text ? <h3 className="text-sm font-semibold">{block.text}</h3> : null

    case 'quote':
      return block.text ? (
        <blockquote className={`border-l-2 pl-3.5 italic ${HAIRLINE} ${MUTED}`}>
          <p>“{block.text}”</p>
          {(block.speaker || block.evidence) && (
            <div className="mt-1 flex items-center gap-2">
              {block.speaker && (
                <cite className="block text-sm not-italic text-text-tertiary-light dark:text-text-secondary-dark">
                  — {block.speaker}
                </cite>
              )}
              <EvidenceChip evidence={block.evidence} />
            </div>
          )}
        </blockquote>
      ) : null

    case 'bullets':
      return block.items && block.items.length > 0 ? (
        <div>
          {block.text && (
            <p className={`mb-1 font-semibold ${INK}`}>{block.text}</p>
          )}
          <ul className={`list-disc space-y-1 pl-5 ${INK}`}>
            {block.items.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null

    case 'table':
      return (
        <GenericTable
          headers={block.headers ?? []}
          rows={block.rows ?? []}
          rowEvidence={block.row_evidence}
        />
      )

    case 'metrics':
      // The metrics rows carry the server-computed deltas (rule-12 single source) + provenance, so
      // FinancialMetricsTable renders identically to the old standalone table — just without its own
      // header (the section heading supplies the "Financial Highlights" title).
      return <FinancialMetricsTable metrics={block.metric_rows} bare />

    case 'callout': {
      const flagged = /flag|risk|concern|caution|warn/i.test(block.label ?? '')
      return block.text ? (
        <Callout label={block.label} tone={flagged ? 'caution' : 'neutral'}>
          {block.text}
        </Callout>
      ) : null
    }

    default:
      return null
  }
}

// No letters except one trailing K/M/B/T scale: "$391.0B", "-3.2%", "(12.4)" — not "$2.1B goodwill …".
const WHOLE_FIGURE = /^\P{L}*[KMBT]?$/iu

/** A plain string-cell table (segments, footnotes) on reader-table manners: hairline rows with no
    outer frame, no header fill, eyebrow header, and numeric COLUMNS detected via parseNumeric and
    rendered right-aligned in the data face (segment-revenue grids were left-aligned prose). The
    outer cells sit flush with the section's text edge. Horizontal scroll keeps wide grids from
    pushing the page sideways. When `rowEvidence` is present (T4 — footnotes), a per-row
    Trace-to-Source chip is appended under the row's last cell. */
function GenericTable({ headers, rows, rowEvidence }: {
  headers: string[]
  rows: string[][]
  rowEvidence?: (BlockEvidence | null)[]
}) {
  if (rows.length === 0) return null
  const hasRowEvidence = rowEvidence?.some(Boolean) ?? false
  const colCount = Math.max(headers.length, ...rows.map((r) => r.length))
  // Numeric column = every non-empty cell is a whole figure ($391.0B, 61.2%, (12.4), —). parseNumeric
  // reads a leading number, so a cell must also carry no letters beyond one scale suffix: commentary
  // that merely opens with a figure ("41% operating margin — …") stays wrapping prose.
  const numericCol = Array.from({ length: colCount }, (_, c) => {
    const cells = rows.map((r) => (r[c] ?? '').trim())
    return cells.some((v) => v !== '') &&
      cells.every((v) => v === '' || v === '—' || v === '-' || (WHOLE_FIGURE.test(v) && parseNumeric(v) !== null))
  })
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full border-collapse">
        {headers.length > 0 && (
          <thead>
            <tr className={`border-b ${HAIRLINE}`}>
              {headers.map((header, i) => (
                <th key={i} scope="col"
                  className={`px-3 py-2 text-xs font-semibold uppercase tracking-eyebrow text-text-tertiary-light first:pl-0 last:pr-0 dark:text-text-secondary-dark ${numericCol[i] ? 'text-right' : 'text-left'}`}>
                  {header}
                </th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {rows.map((row, r) => {
            const ev = rowEvidence?.[r]
            const last = row.length - 1
            // Top-align only cited tables (footnotes), so a chip sits at the top of a tall row; a plain
            // table (segments) keeps its default vertical alignment.
            const cellAlign = hasRowEvidence ? ' align-top' : ''
            return (
              // Every row closes with a hairline (the header row carries its own), so the ledger ends
              // on a rule and no two lines double up.
              <tr key={r} className={`border-b ${HAIRLINE}`}>
                {row.map((cell, c) => (
                  <td key={c}
                    className={`px-3 py-2.5 text-sm first:pl-0 last:pr-0 ${MUTED}${cellAlign}${numericCol[c] ? ' text-right font-data tabular-nums whitespace-nowrap' : ''}`}>
                    {cell}
                    {c === last && ev && (
                      <span className="mt-1 block"><EvidenceChip evidence={ev} /></span>
                    )}
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
