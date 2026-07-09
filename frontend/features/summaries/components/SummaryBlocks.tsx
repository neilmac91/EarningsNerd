'use client'

import { useMemo } from 'react'
import { Badge, Card, CardHeader, CardTitle, CardBody } from '@/components/ui'
import FinancialMetricsTable from '@/features/summaries/components/FinancialMetricsTable'
import { SummaryBlock } from '@/features/summaries/components/SummaryBlock'
import { SummaryRisks } from '@/features/summaries/components/SummaryRisks'
import { SourceTrace } from '@/features/filings/components/SourceTrace'
import { SectionEmpty } from './SectionEmpty'
import { normalizeRisk, isPlaceholderText } from '@/lib/formatters'
import type { RiskFactor } from '@/types/summary'
import type { BlockEvidence, RenderedBlock, RenderedSection, Summary } from '@/features/summaries/api/summaries-api'

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

interface SummaryBlocksProps {
  sections: RenderedSection[]
  /** The full summary — read only for the risks section's enriched provenance (source traces). */
  summary: Summary
}

/**
 * The single web surface for a filing summary (T2): renders the backend's `rendered_sections`
 * projection — the SAME Section/Block list that feeds the PDF and CSV — as one scrolling page of
 * per-section Cards with a sticky table of contents. Replaces the ReactMarkdown card, the tabbed
 * SummarySections, and the standalone metrics table, so a number has exactly one home on the page.
 */
export function SummaryBlocks({ sections, summary }: SummaryBlocksProps) {
  // Enriched, placeholder-filtered risks (with source_url/verified) for the risks special-case.
  const risks = useMemo<RiskFactor[]>(() => {
    const raw = (summary.raw_summary?.sections as { risk_factors?: unknown } | undefined)?.risk_factors
    if (!Array.isArray(raw)) return []
    return raw
      .map((r) => normalizeRisk(r))
      .filter((r): r is RiskFactor => {
        // Parity with the retired tabbed page: drop risks whose evidence (or description) is
        // placeholder filler — the backend's block filtering is bypassed on this direct-read path.
        if (!r || !r.supporting_evidence || isPlaceholderText(r.supporting_evidence)) return false
        if (r.description && isPlaceholderText(r.description)) return false
        return true
      })
  }, [summary.raw_summary])

  if (!sections?.length) {
    return <SectionEmpty label="summary" />
  }

  return (
    <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_13rem] lg:gap-8">
      <div className="space-y-6">
        {sections.map((section) => {
          const toneVariant = section.tone ? TONE_VARIANT[section.tone.toLowerCase()] : undefined
          return (
            <Card as="section" key={section.id} id={section.id} className="scroll-mt-24 overflow-hidden">
              <CardHeader className="flex items-center justify-between gap-2">
                <CardTitle>{section.title}</CardTitle>
                {toneVariant && (
                  <Badge variant={toneVariant} className="shrink-0 capitalize">
                    {section.tone}
                  </Badge>
                )}
              </CardHeader>
              <CardBody className="space-y-4">
                {isRisksSection(section) ? (
                  <SummaryRisks risks={risks} />
                ) : (
                  section.blocks.map((block, i) => <BlockView key={i} block={block} />)
                )}
              </CardBody>
            </Card>
          )
        })}
      </div>

      {/* Sticky in-page table of contents — anchor links to each section (widescreen only, so it
          never crowds the reading column on narrow/reflowed layouts). */}
      <aside className="hidden lg:block">
        <nav aria-label="Summary sections" className="sticky top-24 self-start">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-tertiary-light dark:text-text-secondary-dark">
            On this page
          </p>
          <ul className="space-y-1 border-l border-border-light dark:border-border-dark">
            {sections.map((section) => (
              <li key={section.id}>
                <a
                  href={`#${section.id}`}
                  className="-ml-px block border-l border-transparent py-1 pl-3 text-sm text-text-secondary-light transition-colors hover:border-brand-border hover:text-brand-strong dark:text-text-secondary-dark dark:hover:text-brand-strong-dark"
                >
                  {section.title}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      </aside>
    </div>
  )
}

/** One Block.kind → one renderer. The backend already strips field-name scaffolding, so text
    blocks render as plain prose (no ReactMarkdown needed). Unknown kinds render nothing. */
function BlockView({ block }: { block: RenderedBlock }) {
  switch (block.kind) {
    case 'paragraph':
      return block.text ? (
        // Justified body copy with hyphenation, matching the .markdown-body prose treatment (T1.7).
        <p className="text-justify leading-relaxed text-text-secondary-light [hyphens:auto] dark:text-text-secondary-dark">
          {block.text}
        </p>
      ) : null

    case 'subheading':
      return block.text ? (
        <h4 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary-light dark:text-text-secondary-dark">
          {block.text}
        </h4>
      ) : null

    case 'quote':
      return block.text ? (
        <blockquote className="border-l-4 border-brand-border pl-4 italic text-text-secondary-light dark:border-brand-border-dark dark:text-text-secondary-dark">
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
            <p className="mb-1 font-semibold text-text-primary-light dark:text-text-primary-dark">{block.text}</p>
          )}
          <ul className="list-disc space-y-1 pl-5 text-text-secondary-light dark:text-text-secondary-dark">
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
      // header (the section Card supplies the "Financial Highlights" title).
      return <FinancialMetricsTable metrics={block.metric_rows} bare />

    case 'callout': {
      const flagged = /flag|risk|concern|caution|warn/i.test(block.label ?? '')
      return block.text ? (
        <SummaryBlock type={flagged ? 'bearish' : 'neutral'} title={block.label || undefined}>
          {block.text}
        </SummaryBlock>
      ) : null
    }

    default:
      return null
  }
}

/** A plain string-cell table (segments, footnotes) styled with design-system tokens and horizontal
    scroll so wide grids never push the page sideways. When `rowEvidence` is present (T4 — footnotes),
    a per-row Trace-to-Source chip is appended under the row's last cell. */
function GenericTable({
  headers,
  rows,
  rowEvidence,
}: {
  headers: string[]
  rows: string[][]
  rowEvidence?: (BlockEvidence | null)[]
}) {
  if (rows.length === 0) return null
  const hasRowEvidence = rowEvidence?.some(Boolean) ?? false
  return (
    <div className="overflow-x-auto rounded-xl border border-border-light dark:border-border-dark">
      <table className="min-w-full divide-y divide-border-light dark:divide-border-dark">
        {headers.length > 0 && (
          <thead className="bg-background-light dark:bg-background-dark">
            <tr>
              {headers.map((header, i) => (
                <th
                  key={i}
                  className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider text-text-tertiary-light dark:text-text-secondary-dark"
                >
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
              <tr key={r}>
                {row.map((cell, c) => (
                  <td
                    key={c}
                    className={`border-t border-border-light px-4 py-3 text-sm text-text-secondary-light dark:border-border-dark dark:text-text-secondary-dark${cellAlign}`}
                  >
                    {cell}
                    {c === last && ev && (
                      <span className="mt-1 block">
                        <EvidenceChip evidence={ev} />
                      </span>
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
