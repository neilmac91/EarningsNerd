// The evidence vocabulary: one plain label per state the server sets, product-wide (the founder's review of the
// landing page's evidence row, 2026-10-22; tasks/evidence-row-ux-plan-2026-10-22.md §3.2). No acronym sits in a
// label and nothing reads "verified" without saying what was checked: a figure is matched to the filing's data or
// only linked, and a quote is found in the filing word for word or only pointed at its section.

/** A figure the server compared with the filing's data and found equal, or replaced with the filed figure. */
export const FIGURE_MATCHED = 'Matches filing'
/** Any other figure: per-share figures, ratios, segment lines and labels the check does not map. */
export const FIGURE_LINKED = 'Linked, not checked'
/** A passage the server located in the filing text. */
export const PASSAGE_FOUND = 'Quote found in filing'
/** A passage the server could not locate: the chip points at its section only. */
export const PASSAGE_LINKED = 'Section linked'

export const PASSAGE_FOUND_NOTE = 'Found in the filing, word for word.'
export const PASSAGE_LINKED_NOTE = 'We link to the section. We couldn’t find these words in it.'
export const FIGURE_LINKED_NOTE = 'We link to where this figure is reported, but we don’t check it.'
export const TAKEAWAY_PASSAGE_NOTE = 'The passage cited for this takeaway is in the filing, word for word.'
export const TAKEAWAY_WITHHELD_NOTE = 'Its takeaway quoted the replaced figure, so it is not shown.'

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
