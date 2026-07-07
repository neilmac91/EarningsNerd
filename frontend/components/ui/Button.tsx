'use client'

/* =============================================================================
   Button — components/ui/Button.tsx
   -----------------------------------------------------------------------------
   Styled ONLY from the Sage tokens in tailwind.config.js. Accent wiring:
     - primary:     brand.DEFAULT fill + white label; hover ONE stop darker
                    (brand.strong), active brand.emphasis.
                    dark: FLIPS to a navy-ink label on brand.dark — white on
                    brand.fill-dark is 3.7:1 (fails AA). Hover BRIGHTENS to
                    brand.strong-dark (dark-mode rule), active presses to
                    brand.fill-dark. Every dark state ≥ 5:1.
     - secondary:   brand.strong text + brand.border hairline on transparent;
                    hover tints with brand.weak (never opacity — that darkens).
     - ghost:       brand.strong text on transparent, same tint hover.
     - destructive: error fill + white label; hover error.emphasis.
   Focus-visible = shadow-ring-brand (light) / shadow-ring-brand-dark (navy);
   destructive uses shadow-ring-error.
   States: default / hover / active / focus-visible / disabled / loading.
   Loading is NOT the disabled look — it keeps the resting fill, shows a
   spinner, sets aria-busy, and refuses activation until the work settles.
============================================================================= */

import { forwardRef, type ButtonHTMLAttributes, type MouseEvent, type ReactNode } from 'react'
import { cx } from './cx'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'tertiary' | 'destructive'
export type ButtonSize = 'sm' | 'md' | 'lg' | 'icon-sm'

/** 'tertiary' is the kept pre-v2 name for the ghost treatment — accepted as a
    deprecated alias so the port is mechanical (3 call sites). New code: 'ghost'. */
function resolveVariant(variant: ButtonVariant): Exclude<ButtonVariant, 'tertiary'> {
  return variant === 'tertiary' ? 'ghost' : variant
}

const BASE = cx(
  'inline-flex select-none items-center justify-center gap-2 whitespace-nowrap font-semibold',
  'transition-colors duration-fast',
  'focus-visible:outline-none',
)

const SIZE: Record<ButtonSize, string> = {
  // Radius snaps to 12 (rounded-lg) at EVERY size — buttons + inputs are 12 on the 4/8/12/16/24 scale.
  sm: 'h-8 gap-1.5 rounded-lg px-3 text-xs',
  md: 'h-10 rounded-lg px-4 text-sm',
  lg: 'h-12 rounded-lg px-5 text-base',
  // Icon-only square. A first-class size, NOT a zero-padding className override on `sm`: cx
  // does no tailwind-merge, so two conflicting padding utilities in one class attribute resolve
  // by STYLESHEET order and the size's px-3 wins — which crushed 20px glyphs to a 6px content
  // box (the AAPL "tiny icons" bug; gate: tests/unit/button-icon-size-gate.spec.ts).
  'icon-sm': 'h-8 w-8 rounded-lg p-0 text-xs',
}

const VARIANT: Record<Exclude<ButtonVariant, 'tertiary'>, string> = {
  primary: cx(
    'bg-brand text-white shadow-e1',
    'hover:bg-brand-strong',
    'active:bg-brand-emphasis active:shadow-none',
    'focus-visible:shadow-ring-brand',
    'disabled:cursor-not-allowed disabled:bg-brand/45 disabled:text-white/80 disabled:shadow-none',
    'dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark dark:active:bg-brand-fill-dark',
    'dark:focus-visible:shadow-ring-brand-dark dark:disabled:bg-brand-dark/35 dark:disabled:text-background-dark/60',
  ),
  secondary: cx(
    'border border-brand-border bg-transparent text-brand-strong',
    'hover:bg-brand-weak',
    'active:bg-brand-border/60',
    'focus-visible:shadow-ring-brand',
    'disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent',
    'dark:border-brand-border-dark dark:text-brand-strong-dark dark:hover:bg-brand-weak-dark dark:active:bg-brand-border-dark',
    'dark:focus-visible:shadow-ring-brand-dark',
  ),
  ghost: cx(
    'bg-transparent text-brand-strong',
    'hover:bg-brand-weak',
    'active:bg-brand-border/60',
    'focus-visible:shadow-ring-brand',
    'disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent',
    'dark:text-brand-strong-dark dark:hover:bg-brand-weak-dark dark:active:bg-brand-border-dark',
    'dark:focus-visible:shadow-ring-brand-dark',
  ),
  destructive: cx(
    'bg-error-light text-white shadow-e1',
    'hover:bg-error-emphasis',
    'active:bg-error-emphasis active:shadow-none',
    'focus-visible:shadow-ring-error',
    'disabled:cursor-not-allowed disabled:bg-error-light/40 disabled:shadow-none',
    'dark:hover:bg-error-emphasis',
  ),
}

const SPINNER_SIZE: Record<ButtonSize, string> = {
  sm: 'h-3 w-3',
  md: 'h-4 w-4',
  lg: 'h-4.5 w-4.5',
  'icon-sm': 'h-4 w-4',
}

export interface ButtonVariantsOptions {
  variant?: ButtonVariant
  size?: ButtonSize
  className?: string
}

/** Class-string factory — the full button treatment WITHOUT the <button>
    element, for things styled as buttons that aren't buttons: <Link>s, <a>s,
    summary triggers. Mirrors the kept repo Button's buttonVariants() export
    (3 importers), so the port needs no invention:

      <Link href="/pricing" className={buttonVariants({ variant: 'secondary', size: 'sm' })}>

    <Button> itself composes this same factory — one source of truth. */
export function buttonVariants({ variant = 'primary', size = 'md', className }: ButtonVariantsOptions = {}): string {
  return cx(BASE, SIZE[size], VARIANT[resolveVariant(variant)], className)
}

function Spinner({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className={cx('animate-spin motion-reduce:animate-none', className)}
    >
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.3" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  /** Optional label swap while loading, e.g. "Generating…" */
  loadingText?: string
  leftIcon?: ReactNode
  rightIcon?: ReactNode
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', loading = false, loadingText, leftIcon, rightIcon, className, children, onClick, type = 'button', ...rest },
  ref,
) {
  const handleClick = (e: MouseEvent<HTMLButtonElement>) => {
    if (loading) {
      e.preventDefault()
      return
    }
    onClick?.(e)
  }

  return (
    <button
      ref={ref}
      // Default type='button' (the pre-v2 primitive's contract): a typeless
      // <Button> inside a form must never become an implicit submit. Pass
      // type="submit" explicitly where submission is intended.
      type={type}
      onClick={handleClick}
      aria-busy={loading || undefined}
      aria-disabled={loading || undefined}
      className={cx(buttonVariants({ variant, size }), loading && 'cursor-progress', className)}
      {...rest}
    >
      {loading ? <Spinner className={SPINNER_SIZE[size]} /> : leftIcon}
      {loading && loadingText ? loadingText : children}
      {!loading && rightIcon}
    </button>
  )
})
