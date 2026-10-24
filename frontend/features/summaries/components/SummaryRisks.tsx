import React from 'react'
import { EnRef, MarkedCopy, cx, markedBlockInsetClass, markedRowInsetClass } from '@/components/ui'
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

const INK = 'text-text-primary-light dark:text-text-primary-dark'
const MUTED = 'text-text-secondary-light dark:text-text-secondary-dark'
const HAIRLINE = 'border-border-light dark:border-white/10'
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

/**
 * The risks section as a marked copy (D-044, after the evidence rows of the 2026-10 critique's P-03):
 * one hairline list inside the section, where each row is a heading, the excerpt and its provenance
 * chip. No stripe card, no trend glyph, no nested evidence box, nothing below the 12px floor but the
 * margin's twins. A long unbreakable token (a URL) wraps inside the row, in the heading and the excerpt.
 *
 * Every item reaching this component is an original filing span projected by the server; unmatched
 * and model-only risks are withheld there, and the server labels every projected risk "Filing
 * excerpt" rather than pass a model-written title through. So a row's heading is the opening words
 * of its own excerpt (excerptHeadings): the filing's words, unique per row. The tally under the list
 * counts what the server located and withheld; it never claims more than that scope.
 *
 * The brand device marks what the server located, and only that (D-044): a row whose excerpt it
 * located (`source_verified`, the chip's "Quote found in filing", D-028, D-058) carries a bracketed marker on
 * its heading, numbered in reading order among the located rows, the marker's twin sits in the margin
 * on the marker's line (MarkedCopy measures it), and the excerpt is a marked block in the filing's
 * face (`.en-marked`, Newsreader: the Source Voice Rule). One marker per row, so the twins never
 * overprint. A row whose excerpt is not located keeps the plain quotation (a 2px hairline, no fill)
 * and no marker, and a list with no located row draws no margin: the device means located.
 */
export function SummaryRisks({ risks, projection }: SummaryRisksProps) {
  const sourceFirst = projection?.version === 1
  const verified = sourceFirst && typeof projection.verified_count === 'number' ? projection.verified_count : 0
  const withheld = sourceFirst && typeof projection.withheld_count === 'number' ? projection.withheld_count : 0
  const withheldNote = withheld > 0
    ? ` ${plural(withheld, 'item', 'items')} withheld because the evidence could not be matched.`
    : ''

  // No excerpt to show: say which case it is (a summary from before excerpts were located, a projection
  // with no filing text to check against, or a run that located none) and send the reader to the
  // filing's own risk factors.
  if (!sourceFirst) {
    return <p className={`text-sm ${MUTED}`}>Risk excerpts are not available for this summary. Read the risk factors in the filing.</p>
  }
  if (verified === 0 && projection.source_available === false) {
    const unchecked = withheld > 0 ? ` ${plural(withheld, 'item', 'items')} withheld until they can be checked.` : ''
    return (
      <p className={`text-sm ${MUTED}`}>
        {`The filing text was not available to check risk excerpts against.${unchecked} Read the risk factors in the filing.`}
      </p>
    )
  }
  if (verified === 0) {
    return (
      <p className={`text-sm ${MUTED}`}>
        {`No risk excerpt was located in the filing text.${withheldNote} Read the risk factors in the filing.`}
      </p>
    )
  }

  const shown = risks.filter((risk) => risk.supporting_evidence?.trim())
  const headings = excerptHeadings(shown.map((risk) => risk.supporting_evidence))
  // The rows whose excerpt the server located, in reading order: a row's marker is its place among them.
  const located = shown.flatMap((risk, index) => (risk.source_verified === true ? [index] : []))
  const marked = located.length > 0
  const candidates = typeof projection.candidate_count === 'number' ? projection.candidate_count : verified + withheld
  const total = Math.max(candidates, verified)

  const list = (
    <ul role="list" className={`border-t ${HAIRLINE}`}>
      {shown.map((risk, index) => {
        const isLocated = risk.source_verified === true
        return (
          <li
            key={`${index}-${headings[index]}`}
            className={cx('flex flex-col gap-2 border-b py-4 [overflow-wrap:anywhere]', HAIRLINE, marked && markedRowInsetClass)}
          >
            <h3 className="text-sm font-semibold">
              {headings[index]}
              {isLocated && <EnRef label={`[${located.indexOf(index) + 1}]`} />}
            </h3>
            {isLocated ? (
              <blockquote className={cx('en-marked py-2.5 font-editorial text-base leading-relaxed', markedBlockInsetClass, INK)}>
                {risk.supporting_evidence}
              </blockquote>
            ) : (
              <blockquote className={`border-l-2 pl-3.5 text-sm leading-relaxed ${HAIRLINE} ${MUTED}`}>
                {risk.supporting_evidence}
              </blockquote>
            )}
            {(risk.source_url?.trim() || risk.source_section_ref?.trim()) && (
              <div>
                <SourceTrace
                  url={risk.source_url}
                  verified={isLocated}
                  sectionRef={risk.source_section_ref}
                  excerpt={risk.supporting_evidence}
                />
              </div>
            )}
          </li>
        )
      })}
    </ul>
  )

  return (
    <div className="space-y-3">
      <p className={`text-sm ${MUTED}`}>
        Excerpts are the filing’s own words; each heading is the start of its excerpt. Selected excerpts are not a
        complete risk inventory.
      </p>
      {shown.length > 0 && (marked ? <MarkedCopy>{list}</MarkedCopy> : list)}
      <p className={`font-data text-xs tabular-nums ${MUTED}`}>
        {`${verified} of ${plural(total, 'excerpt', 'excerpts')} located in the filing text`}
        {withheld > 0 && ` · ${withheld} withheld because the evidence could not be matched`}
      </p>
    </div>
  )
}
