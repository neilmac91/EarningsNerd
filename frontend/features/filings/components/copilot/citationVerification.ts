import type { CopilotCitation } from '@/features/filings/api/copilot-api'

export const SOURCE_MATCH_SCOPE =
  'A source match verifies every claim in the answer.'

/** Both source kinds are reindexed; model-supplied section labels cannot attest numeric provenance. */
export function citationVerificationLabel(citation: CopilotCitation): string {
  return citation.verified ? 'Source match found' : 'Cited'
}
