/**
 * Calm directional tones for financial values.
 *
 * The brand reserves saturated red/green — it's the "casino" anti-pattern (Plan D3,
 * "calm signal, never casino"), and a colour-only signal is also an accessibility failure
 * (red/green-colourblind users can't tell direction). So positives use the mint accent and
 * negatives a muted slate, and every caller MUST also render a direction glyph (an arrow,
 * ▲/▼, or a signed +/−) so meaning never rides on colour alone. Saturated red stays
 * reserved for genuine error states, which are not directional signals.
 */
export type Direction = 'up' | 'down' | 'flat'

/** Classify a numeric delta. Zero / null / non-finite is treated as flat. */
export function directionOf(n: number | null | undefined): Direction {
  if (n == null || !Number.isFinite(n) || n === 0) return 'flat'
  return n > 0 ? 'up' : 'down'
}

/** Text-only tone — inline figures, deltas, signal headlines. Theme-aware. */
export const directionText: Record<Direction, string> = {
  up: 'text-mint-600 dark:text-mint-400',
  down: 'text-slate-500 dark:text-slate-400',
  flat: 'text-slate-400 dark:text-slate-500',
}

/**
 * Text tone for components that sit on a *permanently dark* surface regardless of the global
 * theme (e.g. the hero, the "market movers" rail, the search dropdown). These use the light
 * (400) shades unconditionally — `directionText`'s light-mode values (mint-600/slate-500) would
 * have poor contrast on a dark background when the global `.dark` class is absent.
 */
export const directionTextOnDark: Record<Direction, string> = {
  up: 'text-mint-400',
  down: 'text-slate-400',
  flat: 'text-slate-400',
}

/** Full pill/chip tone — text + a subtle tinted background + border. */
export const directionChip: Record<Direction, string> = {
  up: 'text-mint-700 bg-mint-500/10 border-mint-500/20 dark:text-mint-300 dark:border-mint-400/20',
  down: 'text-slate-600 bg-slate-500/10 border-slate-400/20 dark:text-slate-300 dark:border-slate-400/20',
  flat: 'text-slate-500 bg-slate-500/5 border-slate-300/30 dark:text-slate-400 dark:border-slate-600/30',
}

/** Hex tones for chart contexts (Recharts needs concrete colours, not classes). */
export const directionHex: Record<Direction, string> = {
  up: '#10B981', // mint-500 — the brand accent
  down: '#64748B', // slate-500 — muted, never alarm-red
  flat: '#94A3B8', // slate-400
}
