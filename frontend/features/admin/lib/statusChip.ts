/**
 * The admin status chip recipe, in one place (DESIGN_SYSTEM.md §4 "Status chip"): InviteStatusBadge and
 * FeedbackStatusBadge map a status to a tone and render STATUS_CHIP plus that tone's ink, with an icon
 * and a label (never color alone). tests/unit/statusChipContrast.spec.ts measures every tone here in
 * both themes on the table row at rest and under its hover tint, and holds both badges to this recipe.
 *
 * #1289 adds success and error status variants to ui/Badge. The later of #1289 and #1309 to land moves
 * this base onto Badge's status variants and deletes this module.
 */
export type StatusChipTone = 'info' | 'success' | 'warning' | 'neutral'

/**
 * The status ink on the quiet ground: white with a hairline in light, the bare hairline in dark. Dark
 * carries no fill on purpose: Badge's quiet dark:bg-white/5 under the row's own white/5 hover tint
 * drops info-dark to 4.26:1 on a hovered row; with no fill it holds 4.97:1 there.
 */
export const STATUS_CHIP =
  'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium border-border-light bg-white dark:border-border-dark dark:bg-transparent'

/** Each tone's label ink, light then dark. */
export const STATUS_CHIP_INK: Record<StatusChipTone, string> = {
  info: 'text-info-text dark:text-info-dark',
  success: 'text-success-light dark:text-success-dark',
  warning: 'text-warning-light dark:text-warning-dark',
  neutral: 'text-text-tertiary-light dark:text-text-secondary-dark',
}
