import { isXbrlCitation, type CopilotCitation } from '@/features/filings/api/copilot-api'

export const EXCERPT_MATCH_SCOPE =
  'This confirms the quoted passage appears in the filing; it does not verify every claim in the answer.'

/** Describe the existing source check, never semantic support for the surrounding answer. */
export function citationVerificationLabel(citation: CopilotCitation): string {
  if (!citation.verified) return 'Cited'
  return isXbrlCitation(citation) ? 'Numeric source verified' : 'Excerpt found in filing'
}
