/* =============================================================================
   Earnings calendar — ticker comparison (features/calendar/lib/tickers.ts)
   -----------------------------------------------------------------------------
   An event's ticker is Alpha Vantage's spelling of a share class (BRK.B); the
   alert list names the company's, which is SEC's (BRK-B). The backend's
   `index_membership_service.normalize_ticker` compares them in one form: trim,
   upper-case, dash to dot. This is the same function, so a bell keys on it.
============================================================================= */

export function canonicalTicker(raw: string): string {
  return raw.trim().toUpperCase().replace(/-/g, '.')
}
