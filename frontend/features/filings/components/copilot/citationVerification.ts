import type { CopilotCitation } from '@/features/filings/api/copilot-api'
import { FIGURE_LINKED, FIGURE_MATCHED, PASSAGE_FOUND, PASSAGE_LINKED } from '@/features/filings/lib/evidenceLabels'

export const SOURCE_MATCH_SCOPE =
  'A matched source does not check every claim in the answer.'

/** Both source kinds are reindexed; model-supplied section labels cannot attest numeric provenance, so the figure
 *  labels follow only the server's own fact payload (`fact`, admitted in copilot-api.ts), never an "XBRL · …" section
 *  label (which also styles the row, isXbrlCitation). The words are the product's one evidence vocabulary
 *  (lib/evidenceLabels): a figure matches the filing or is only linked, and a passage is a quote found in the filing or
 *  only its section. */
export function citationVerificationLabel(citation: CopilotCitation): string {
  const fact = citation.fact === true
  if (citation.verified) return fact ? FIGURE_MATCHED : PASSAGE_FOUND
  return fact ? FIGURE_LINKED : PASSAGE_LINKED
}
