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
 * v3 (DS-02): chip LABELS are text, not graphics — light-mode chip text moved off the
 * 600-level graphic values (#16A34A on its tint was 3.0:1, #DC2626 was 3.9:1) onto the
 * 700-level text tokens: gain.text on gain.soft = 4.57:1, loss.text on loss.soft = 5.30:1.
 * The 600s remain as the chips' BORDER tints (graphic, 3:1 floor). Flat chip text uses the
 * secondary ink in light (flat.light inside its own tint was 3.9:1).
 */
export type Direction = 'up' | 'down' | 'flat'

/** Classify a numeric delta. Zero / null / non-finite is treated as flat. */
export function directionOf(n: number | null | undefined): Direction {
  if (n == null || !Number.isFinite(n) || n === 0) return 'flat'
  return n > 0 ? 'up' : 'down'
}

/** Text-only tone — inline figures, deltas, signal headlines. Theme-aware.
 *  Light uses the 700-level gain.text/loss.text: the 600-level gain/loss values are
 *  graphic/chip-border-only (3:1 non-text floor) and fail AA as text on cream. */
export const directionText: Record<Direction, string> = {
  up: 'text-gain-text dark:text-gain-dark',
  down: 'text-loss-text dark:text-loss-dark',
  flat: 'text-flat-light dark:text-flat-dark',
}

/**
 * Text tone for components that sit on a *permanently dark* surface regardless of the global
 * theme (e.g. the hero, the "market movers" rail, the search dropdown). These use the
 * dark-tuned gain/loss shades unconditionally — `directionText`'s light-mode values would have
 * poor contrast on a dark background when the global `.dark` class is absent.
 */
export const directionTextOnDark: Record<Direction, string> = {
  up: 'text-gain-dark',
  down: 'text-loss-dark',
  flat: 'text-flat-dark',
}

/** Full pill/chip tone — text + a subtle tinted background + border.
 *  Label ink = the 700-level TEXT tokens (AA inside the tint); the 600s stay on the
 *  border only. Matches Badge's beat/miss recipe — the two primitives now agree. */
export const directionChip: Record<Direction, string> = {
  up: 'text-gain-text bg-gain-soft border-gain-light/20 dark:text-gain-dark dark:bg-gain-soft-dark dark:border-gain-dark/20',
  down: 'text-loss-text bg-loss-soft border-loss-light/20 dark:text-loss-dark dark:bg-loss-soft-dark dark:border-loss-dark/20',
  flat: 'text-text-secondary-light bg-flat-light/10 border-flat-light/20 dark:text-flat-dark dark:bg-flat-dark/10 dark:border-flat-dark/20',
}

/** Hex tones for chart contexts (Recharts needs concrete colours, not classes).
 *  GRAPHIC values (lines, bars, dots) — never render these as text; use the
 *  chartTheme(dark).gainText/lossText pair for on-chart labels. */
export const directionHex: Record<Direction, string> = {
  up: '#16A34A', // gain (green-600) — positive / up
  down: '#DC2626', // loss (red-600) — negative / down
  flat: '#6B7280', // flat (gray-500) — neutral
}
