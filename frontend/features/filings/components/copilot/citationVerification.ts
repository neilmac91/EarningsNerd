import type { CopilotCitation } from '@/features/filings/api/copilot-api'
import { FIGURE_CALCULATED, FIGURE_LINKED, FIGURE_MATCHED, passageLabel } from '@/features/filings/lib/evidenceLabels'

export const SOURCE_MATCH_SCOPE =
  'A matched source does not check every claim in the answer.'

/** Both source kinds are reindexed; model-supplied section labels cannot attest numeric provenance, so the figure
 *  labels follow only the server's own fact payload (`fact` and `calculated`, admitted in copilot-api.ts), never an
 *  "XBRL · …" section label (which still styles the row, isXbrlCitation). The words are the product's one evidence
 *  vocabulary (lib/evidenceLabels): a filed figure matches the filing, a computed one is calculated from it, either is
 *  only linked when unchecked, and a passage is a quote found in the filing or only its section (or the filing, when it
 *  names none). */
export function citationVerificationLabel(citation: CopilotCitation): string {
  if (citation.calculated === true) return citation.verified ? FIGURE_CALCULATED : FIGURE_LINKED
  if (citation.fact === true) return citation.verified ? FIGURE_MATCHED : FIGURE_LINKED
  return passageLabel(citation.verified, citation.section_ref)
}
