/**
 * Directional tones for financial values — design-system gain/loss semantics.
 *
 * Positive moves use the `gain` token (green), negatives use `loss` (red), and flat uses the
 * neutral `flat` token. These are the design system's dedicated financial-data colours, kept
 * separate from the brand accent so direction never reads as brand identity.
 *
 * ACCESSIBILITY: colour alone is not enough (red/green-colourblind users can't distinguish
 * direction), so every caller MUST also render a direction glyph (an arrow, ▲/▼, or a signed
 * +/−) — meaning never rides on colour alone. `gain`/`loss` here signal financial DIRECTION;
 * `success`/`error` remain reserved for UI operation status, which is not a directional signal.
 *
 */
export type Direction = 'up' | 'down' | 'flat'

/** Classify a numeric delta. Zero / null / non-finite is treated as flat. */
export function directionOf(n: number | null | undefined): Direction {
  if (n == null || !Number.isFinite(n) || n === 0) return 'flat'
  return n > 0 ? 'up' : 'down'
}

/** Muted financial direction ink. Always accompany it with a sign, glyph or direction word. */
export const directionText: Record<Direction, string> = {
  up: 'text-gain-text dark:text-gain-dark',
  down: 'text-loss-text dark:text-loss-dark',
  flat: 'text-flat-light dark:text-flat-dark',
}

/** Change text on the analysis figure surfaces (the metrics table's well, the KPI cards), held to APCA |Lc| >= 75 on
 *  both grounds in both themes (tailwind.config.js `gain.data`, `loss.data`). Flat takes the neutral ink a flat chip
 *  already uses in light (secondary) and the well's note ink in dark. The sign still carries direction. */
export const dataDirectionText: Record<Direction, string> = {
  up: 'text-gain-data dark:text-gain-data-dark',
  down: 'text-loss-data dark:text-loss-data-dark',
  flat: 'text-text-secondary-light dark:text-note-dark',
}

/** Neutral stone shell shared by every financial chip. Labels stay neutral;
 * DeltaChip applies directionText only to its glyph and figure. Borders are decorative. */
export const directionChip: Record<Direction, string> = {
  up: 'text-text-secondary-light bg-background-light border-border-light dark:text-text-secondary-dark dark:bg-background-dark dark:border-border-dark',
  down: 'text-text-secondary-light bg-background-light border-border-light dark:text-text-secondary-dark dark:bg-background-dark dark:border-border-dark',
  flat: 'text-text-secondary-light bg-background-light border-border-light dark:text-text-secondary-dark dark:bg-background-dark dark:border-border-dark',
}
