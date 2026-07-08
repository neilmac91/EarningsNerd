'use client'

import { useMemo } from 'react'
import { Card, CardHeader, CardTitle, CardBody } from '@/components/ui'
import FinancialMetricsTable from '@/features/summaries/components/FinancialMetricsTable'
import { SummaryBlock } from '@/features/summaries/components/SummaryBlock'
import { SummaryRisks } from '@/features/summaries/components/SummaryRisks'
import { SectionEmpty } from './SectionEmpty'
import { normalizeRisk } from '@/lib/formatters'
import type { RiskFactor } from '@/types/summary'
import type { RenderedBlock, RenderedSection, Summary } from '@/features/summaries/api/summaries-api'

// Slug of the "Investment Risks & Concerns" section (backend _slugify). The risks section is
// special-cased below so its per-risk Trace-to-Source chips survive (the generic block only carries
// string rows); everything else renders from the Section/Block projection verbatim.
const RISKS_SECTION_ID = 'investment-risks-concerns'

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
      .filter((r): r is RiskFactor => Boolean(r && r.supporting_evidence))
  }, [summary.raw_summary])

  if (!sections?.length) {
    return <SectionEmpty label="summary" />
  }

  return (
    <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_13rem] lg:gap-8">
      <div className="space-y-6">
        {sections.map((section) => (
          <Card as="section" key={section.id} id={section.id} className="scroll-mt-24 overflow-hidden">
            <CardHeader>
              <CardTitle>{section.title}</CardTitle>
            </CardHeader>
            <CardBody className="space-y-4">
              {section.id === RISKS_SECTION_ID ? (
                <SummaryRisks risks={risks} />
              ) : (
                section.blocks.map((block, i) => <BlockView key={i} block={block} />)
              )}
            </CardBody>
          </Card>
        ))}
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
          {block.speaker && (
            <cite className="mt-1 block text-sm not-italic text-text-tertiary-light dark:text-text-secondary-dark">
              — {block.speaker}
            </cite>
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
      return <GenericTable headers={block.headers ?? []} rows={block.rows ?? []} />

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
    scroll so wide grids never push the page sideways. */
function GenericTable({ headers, rows }: { headers: string[]; rows: string[][] }) {
  if (rows.length === 0) return null
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-border-light rounded-lg border border-border-light dark:divide-border-dark dark:border-border-dark">
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
          {rows.map((row, r) => (
            <tr key={r}>
              {row.map((cell, c) => (
                <td
                  key={c}
                  className="border-t border-border-light px-4 py-3 text-sm text-text-secondary-light dark:border-border-dark dark:text-text-secondary-dark"
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
