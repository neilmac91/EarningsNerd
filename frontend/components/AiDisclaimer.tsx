import type { ReactNode } from 'react'

/** The copilot per-answer line — one string for the DS reference footer (AskFilingAnswer) and
 *  the wired renderer (CopilotMessage), so the copy can't drift between them. */
export const SEC_EDGAR_NOT_ADVICE = 'Data sourced from SEC EDGAR. Not investment advice.'

/**
 * The point-of-consumption AI disclaimer (audit E1): one styled component so every AI surface
 * (analysis narrative, copilot answers, summaries) carries the same core sentence and the
 * surface-specific tail can't drift in styling. `lead` prints the shared core; `children`
 * carry the surface-specific clauses (citation semantics, past-performance caution, data
 * provenance). Pass `lead={false}` when a surface needs fully bespoke copy but the shared
 * styling/greppability.
 */
export default function AiDisclaimer({
  children,
  lead = true,
  className,
}: {
  children?: ReactNode
  lead?: boolean
  className?: string
}) {
  return (
    <p
      className={`text-xs text-text-tertiary-light dark:text-text-secondary-dark${className ? ` ${className}` : ''}`}
    >
      {lead && <>AI-generated. Informational only, not investment advice. </>}
      {children}
    </p>
  )
}
