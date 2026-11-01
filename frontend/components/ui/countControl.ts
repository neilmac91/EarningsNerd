// The count control's class recipe, in a module without 'use client' so server components can call it too
// (lessons/frontend-client-exports-need-next-build.md).

/**
 * The count control (D-030; frontend/DESIGN_SYSTEM.md, Count control): a link or control whose label carries a count,
 * a date, an index name or a price rests in the secondary ink as one text run and turns sage only under the pointer,
 * keyboard focus drawing the brand ring. It is the one source of that recipe: compose it beside the site's own shape
 * (size, padding, width, a border), and never rebuild it by hand (gate: brandCopyRules.spec.ts rule 2).
 * - `button`: the brand tint under the pointer and the pressed fill, as a ui Button's.
 * - `link`: an underline under the pointer.
 * - `inline`: a link set among lines of text, which keeps its underline at rest, since its ink no longer marks it.
 * - `summary`: a disclosure's summary, which turns sage under the pointer alone in light.
 * In dark the label's step from the secondary ink #D1D5DB to the accent text ink #AEDCC2 is 1.03:1 (D-071), fainter than
 * the secondary-to-primary step DESIGN_SYSTEM.md §2 refuses, so every kind carries a cue dark shows besides the ink:
 * the tint, the underline, an inline link's underline resting in the tertiary ink and turning sage, and a summary's
 * underline under the pointer (gate: themePairs.spec.ts, the faint dark hover).
 */
export type CountControlKind = 'button' | 'link' | 'inline' | 'summary'

const INK = [
  'text-text-secondary-light transition-colors duration-fast hover:text-brand-strong',
  'focus-visible:outline-none focus-visible:shadow-ring-brand',
  'dark:text-text-secondary-dark dark:hover:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark',
].join(' ')

const KIND: Record<CountControlKind, string> = {
  button: 'hover:bg-brand-weak active:bg-brand-border/60 dark:hover:bg-brand-weak-dark dark:active:bg-brand-border-dark',
  link: 'underline-offset-4 hover:underline',
  inline: 'underline dark:decoration-text-tertiary-dark dark:hover:decoration-current',
  summary: 'underline-offset-4 dark:hover:underline',
}

export const countControlClass = (kind: CountControlKind): string => `${INK} ${KIND[kind]}`
