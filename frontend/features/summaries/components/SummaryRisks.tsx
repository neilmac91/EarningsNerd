import React from 'react'
import { SourceTrace } from '@/features/filings/components/SourceTrace'
import { excerptHeadings } from '@/features/summaries/lib/riskTitle'
import type { RiskFactor } from '@/types/summary'

interface SummaryRisksProps {
  risks: RiskFactor[]
  projection?: {
    version?: number
    verified_count?: number
    withheld_count?: number
    candidate_count?: number
    source_available?: boolean
  }
}

const MUTED = 'text-text-secondary-light dark:text-text-secondary-dark'
const HAIRLINE = 'border-border-light dark:border-white/10'
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

/**
 * The risks section as evidence rows (2026-10 critique P-03): one hairline list inside the section,
 * where each row is a heading, the excerpt in blockquote manners (2px hairline, no fill, no radius)
 * and its provenance chip. No stripe card, no trend glyph, no nested evidence box, nothing below the
 * 12px floor.
 *
 * Every item reaching this component is an original filing span projected by the server; unmatched
 * and model-only risks are withheld there, and the server labels every projected risk "Filing
 * excerpt" rather than pass a model-written title through. So a row's heading is the opening clause
 * of its own excerpt (excerptHeadings): the filing's words, unique per row. The tally under the list
 * counts what the server located and withheld; it never claims more than that scope.
 */
export function SummaryRisks({ risks, projection }: SummaryRisksProps) {
  const sourceFirst = projection?.version === 1
  const verified = sourceFirst && typeof projection.verified_count === 'number' ? projection.verified_count : 0
  const withheld = sourceFirst && typeof projection.withheld_count === 'number' ? projection.withheld_count : 0
  const withheldNote = withheld > 0
    ? ` ${plural(withheld, 'item', 'items')} withheld because the evidence could not be matched.`
    : ''

  if (!sourceFirst || verified === 0) {
    return (
      <p className={`text-sm ${MUTED}`}>
        {`Source-verified risk excerpts are unavailable. Review the filing.${withheldNote} Selected excerpts are not a complete risk inventory.`}
      </p>
    )
  }

  const shown = risks.filter((risk) => risk.supporting_evidence?.trim())
  const headings = excerptHeadings(shown.map((risk) => risk.supporting_evidence))
  const candidates = typeof projection.candidate_count === 'number' ? projection.candidate_count : verified + withheld
  const total = Math.max(candidates, verified)

  return (
    <div className="space-y-3">
      <p className={`text-sm ${MUTED}`}>
        Excerpts are the filing’s own words; each heading is its excerpt’s opening clause. Selected excerpts are not a
        complete risk inventory.
      </p>
      {shown.length > 0 && (
        <ul role="list" className={`border-t ${HAIRLINE}`}>
          {shown.map((risk, index) => (
            <li key={`${index}-${headings[index]}`} className={`flex flex-col gap-2 border-b py-4 ${HAIRLINE}`}>
              <h3 className="text-sm font-semibold">{headings[index]}</h3>
              <blockquote className={`border-l-2 pl-3.5 text-sm leading-relaxed ${HAIRLINE} ${MUTED}`}>
                {risk.supporting_evidence}
              </blockquote>
              {(risk.source_url?.trim() || risk.source_section_ref?.trim()) && (
                <div>
                  <SourceTrace
                    url={risk.source_url}
                    verified={risk.source_verified === true}
                    sectionRef={risk.source_section_ref}
                    excerpt={risk.supporting_evidence}
                  />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      <p className={`font-data text-xs tabular-nums ${MUTED}`}>
        {`${verified} of ${plural(total, 'excerpt', 'excerpts')} located in the filing text`}
        {withheld > 0 && ` · ${withheld} withheld because the evidence could not be matched`}
      </p>
    </div>
  )
}
