/* =============================================================================
   Earnings calendar — ticker spellings (features/calendar/lib/tickers.ts)
   -----------------------------------------------------------------------------
   An event's ticker is Alpha Vantage's spelling of a share class (BRK.B); the
   alert list names the company's, which is SEC's (BRK-B). The backend's
   `index_membership_service.normalize_ticker` compares them in one form: trim,
   upper-case, dash to dot. `canonicalTicker` is the same function, so a bell
   keys on it. The company page binds a ticker by exact match on SEC's
   spelling, so a link to it goes the other way: trim, upper-case, dot to dash
   (`secTicker`).
============================================================================= */

export function canonicalTicker(raw: string): string {
  return raw.trim().toUpperCase().replace(/-/g, '.')
}

export function secTicker(raw: string): string {
  return raw.trim().toUpperCase().replace(/\./g, '-')
}
