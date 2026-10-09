/**
 * A ticker as a user or a link supplies one: 1-5 letters with an optional one-letter class suffix
 * (BRK-B), tested after trimming and uppercasing. It is a shape check only, not proof the company
 * exists: CompanySearch uses it to decide whether Enter may navigate before results arrive, and
 * /analysis?ticker= uses it to decide whether a linked ticker is worth resolving through the
 * company API at all.
 */
const TICKER_SHAPE = /^[A-Z]{1,5}(-[A-Z])?$/

/** The uppercased ticker when `raw` is ticker-shaped, else null. */
export function tickerShaped(raw: string | null | undefined): string | null {
  const ticker = (raw ?? '').trim().toUpperCase()
  return TICKER_SHAPE.test(ticker) ? ticker : null
}
