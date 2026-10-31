// The evidence vocabulary: one plain label per state the server sets, product-wide (the founder's review of the
// landing page's evidence row, 2026-10-22; tasks/evidence-row-ux-plan-2026-10-22.md §3.2). No acronym sits in a
// label and nothing reads "verified" without saying what was checked: a figure is matched to the filing's data or
// only linked, and a quote is found in the filing word for word or only pointed at its section (or, when it names
// none, at the filing).

/** A figure the server compared with the filing's data and found equal, or replaced with the filed figure. */
export const FIGURE_MATCHED = 'Matches filing'
/** Any other figure: per-share figures, ratios, segment lines and labels the check does not map. */
export const FIGURE_LINKED = 'Linked, not checked'
/** A figure the server computed from figures it read in the filing's data (a Copilot growth rate or margin): the
 *  filing does not state it, so it never reads as matched. */
export const FIGURE_CALCULATED = 'Calculated from filing'
/** A passage the server located in the filing text. */
export const PASSAGE_FOUND = 'Quote found in filing'
/** A passage the server could not locate: the chip points at its section only. */
export const PASSAGE_LINKED = 'Section linked'
/** A passage the server could not locate that names no section, so the chip links to the filing alone. */
export const PASSAGE_NOT_FOUND = 'Quote not found'

export const PASSAGE_FOUND_NOTE = 'Found in the filing, word for word.'
export const PASSAGE_LINKED_NOTE = 'We link to the section. We couldn’t find these words in it.'
export const PASSAGE_NOT_FOUND_NOTE = 'We link to the filing. We couldn’t find these words in it.'
export const FIGURE_LINKED_NOTE = 'We link to where this figure is reported, but we don’t check it.'
export const TAKEAWAY_PASSAGE_NOTE = 'The passage cited for this takeaway is in the filing, word for word.'
export const TAKEAWAY_WITHHELD_NOTE = 'Its takeaway was written before the correction, so it is withheld.'
/** The takeaway cell of a row whose takeaway the server withheld (commentary_withheld: 'figure_replaced'): the summary
 *  wrote one, so the cell says why it is not shown rather than reading as "no takeaway". The exports print the same
 *  words (backend/app/services/summary_sections.py TAKEAWAY_WITHHELD). */
export const TAKEAWAY_WITHHELD = 'Withheld: written before the figure was corrected.'

/** A passage's chip label: found word for word, or not found and linked to the section it names, or to the filing. */
export const passageLabel = (found: boolean, section: string | null | undefined): string =>
  found ? PASSAGE_FOUND : section?.trim() ? PASSAGE_LINKED : PASSAGE_NOT_FOUND

/** A passage's panel status line, on the same three states as its label. */
export const passageNote = (found: boolean, section: string | null | undefined): string =>
  found ? PASSAGE_FOUND_NOTE : section?.trim() ? PASSAGE_LINKED_NOTE : PASSAGE_NOT_FOUND_NOTE

/** The panel's link: a text-fragment URL lands on the passage itself, any other on the document. */
export const sourceLinkLabel = (url: string): string =>
  url.includes('#:~:text=') ? 'Open the passage on SEC.gov' : 'Open the filing on SEC.gov'

export type FiguredPeriod = 'current_period' | 'prior_period'
const PERIODS: FiguredPeriod[] = ['current_period', 'prior_period']

/** A row's figure fields as the server sends them: each compared period's filed amount in words, and the summary's
 *  own text for each period the server replaced with the filed figure (provenance_service._swap_in_filed_figures). */
export interface FigureEvidence {
  verified: boolean
  filed?: Partial<Record<FiguredPeriod, string>> | null
  replaced?: Partial<Record<FiguredPeriod, string | null>> | null
  takeawayWithheld?: boolean
}

const joined = (items: string[]) => items.join(' and ')

/** The figure panel's one status line. */
export function figureNote({ verified, filed, replaced, takeawayWithheld = false }: FigureEvidence): string {
  if (!verified) return FIGURE_LINKED_NOTE
  const swapped = PERIODS.filter((period) => typeof replaced?.[period] === 'string')
  if (swapped.length > 0) {
    const filedText = swapped.map((period) => filed?.[period]).filter((text): text is string => !!text)
    const plural = swapped.length > 1
    return [
      filedText.length > 0 ? `Shown as the company filed it: ${joined(filedText)}.` : 'Shown as the company filed it.',
      `The summary’s ${plural ? 'figures' : 'figure'}, ${joined(swapped.map((period) => replaced![period]!))}, ${plural ? 'were' : 'was'} replaced.`,
      takeawayWithheld ? TAKEAWAY_WITHHELD_NOTE : null,
    ].filter(Boolean).join(' ')
  }
  const shown = PERIODS.map((period) => filed?.[period]).filter((text): text is string => !!text)
  return shown.length > 0
    ? `Matches the ${shown.length > 1 ? 'figures' : 'figure'} the company filed: ${joined(shown)}.`
    : 'Matches the figure the company filed.'
}
