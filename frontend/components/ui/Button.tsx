import { clsx } from 'clsx'
import { forwardRef } from 'react'

/**
 * TODO(design-system-v2): this pre-v2 Button (buttonVariants + primary/secondary/
 * tertiary) was kept at cutover — 20+ importers rely on its API. The v2 spec adds
 * ghost/destructive/loading and the dark navy-ink primary recipe; port in a
 * follow-up, then export it from components/ui/index.ts.
 *
 * Shared button styling for the EarningsNerd design system. Use `<Button>` for real
 * `<button>` elements; for `<Link>`/`<a>` that should look like a button, apply
 * `buttonVariants({ variant })` to its className.
 *
 * Variants (see frontend/DESIGN_SYSTEM.md §3):
 * - primary   — solid sage/slate brand. The main action.
 * - secondary — panel fill + hairline + soft elevation; lifts off the page without
 *               competing with primary (brightens on hover, never darkens).
 * - tertiary  — bordered/ghost; lightest, clearly subordinate.
 */
export type ButtonVariant = 'primary' | 'secondary' | 'tertiary'
export type ButtonSize = 'sm' | 'md'

const BASE =
  'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all ' +
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-light ' +
  'disabled:opacity-50 disabled:cursor-not-allowed'

const SIZES: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-sm',
}

const VARIANTS: Record<ButtonVariant, string> = {
  primary:
    'bg-brand-strong text-white hover:bg-brand-light dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark',
  secondary:
    'border border-border-light bg-panel-light text-text-primary-light shadow-e1 hover:bg-brand-weak hover:shadow-e2 ' +
    'dark:border-white/10 dark:bg-panel-dark dark:text-text-primary-dark dark:shadow-none dark:hover:bg-white/5',
  tertiary:
    'border border-border-light bg-transparent text-text-secondary-light hover:bg-brand-weak hover:text-text-primary-light ' +
    'dark:border-white/10 dark:text-text-secondary-dark dark:hover:bg-white/5 dark:hover:text-text-primary-dark',
}

export function buttonVariants(
  { variant = 'primary', size = 'md' }: { variant?: ButtonVariant; size?: ButtonSize } = {},
): string {
  return clsx(BASE, SIZES[size], VARIANTS[variant])
}

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', type = 'button', className, ...props },
  ref,
) {
  return <button ref={ref} type={type} className={clsx(buttonVariants({ variant, size }), className)} {...props} />
})
