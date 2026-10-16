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
   destructive uses shadow-ring-error / shadow-ring-error-dark.
   States: default / hover / active / focus-visible / disabled / loading.
   Loading is NOT the disabled look — it keeps the resting fill, shows a
   spinner, sets aria-busy, and refuses activation until the work settles.
   reserveLoadingText keeps a longer loading label's room at rest, so the
   swap never resizes the button (RetryButton's "Trying again…").
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
  'inline-flex select-none items-center justify-center gap-2 font-semibold',
  'transition-colors duration-fast',
  'focus-visible:outline-none',
)

const SIZE: Record<ButtonSize, string> = {
  // Radius snaps to 12 (rounded-lg) at EVERY size — buttons + inputs are 12 on the 4/8/12/16/24 scale.
  sm: 'gap-1.5 rounded-lg px-3 text-xs',
  md: 'rounded-lg px-4 text-sm',
  lg: 'rounded-lg px-5 text-base',
  // Icon-only square. A first-class size, NOT a zero-padding className override on `sm`: cx
  // does no tailwind-merge, so two conflicting padding utilities in one class attribute resolve
  // by STYLESHEET order and the size's px-3 wins — which crushed 20px glyphs to a 6px content
  // box (the AAPL "tiny icons" bug; gate: tests/unit/button-icon-size-gate.spec.ts).
  'icon-sm': 'w-8 rounded-lg p-0 text-xs',
}

const HEIGHT: Record<ButtonSize, string> = { sm: 'h-8', md: 'h-10', lg: 'h-12', 'icon-sm': 'h-8' }
const WRAP_SIZE = { sm: 'min-h-8 py-1.5', md: 'min-h-10 py-2', lg: 'min-h-12 py-2.5' }
// Below a 24rem viewport a labelled button takes the wrap state on its own: a media query's rem is the
// browser's text size, so that is 384px at the default size (a 390px phone keeps one line) and 768px
// under a 200% text setting (a 390px phone wraps the label instead of scrolling the page sideways).
// The wrapped lines centre on tight leading. Written as an arbitrary variant: Tailwind drops
// `max-[24rem]:` because the screens are in px. Gate: tests/e2e/reflow-200.spec.ts.
// Each class is written out whole: Tailwind generates only the class names it finds in the source.
const NARROW_WRAP = '[@media(max-width:24rem)]:h-auto [@media(max-width:24rem)]:whitespace-normal [@media(max-width:24rem)]:text-center [@media(max-width:24rem)]:leading-tight'
const NARROW_MIN_H: Record<Exclude<ButtonSize, 'icon-sm'>, string> = {
  sm: '[@media(max-width:24rem)]:min-h-8',
  md: '[@media(max-width:24rem)]:min-h-10',
  lg: '[@media(max-width:24rem)]:min-h-12',
}
const NARROW_PY: Record<Exclude<ButtonSize, 'icon-sm'>, string> = {
  sm: '[@media(max-width:24rem)]:py-1.5',
  md: '[@media(max-width:24rem)]:py-2',
  lg: '[@media(max-width:24rem)]:py-2.5',
}
/** The narrow state, keeping a caller's own min-h and py. The media block sits after every base
    utility in the stylesheet, so the size's narrow min-h would otherwise beat a caller's min-h-11 and
    shrink a 44px touch target to the size's height on a 360px or 375px phone at the default text size. */
function wrapWhenNarrow(size: Exclude<ButtonSize, 'icon-sm'>, className?: string): string {
  const own = (utility: string) => new RegExp(`(^|\\s)${utility}`).test(className ?? '')
  return cx(NARROW_WRAP, !own('min-h-') && NARROW_MIN_H[size], !own('py-') && NARROW_PY[size])
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
    'disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent disabled:active:bg-transparent',
    'dark:border-brand-border-dark dark:text-brand-strong-dark dark:hover:bg-brand-weak-dark dark:active:bg-brand-border-dark',
    'dark:focus-visible:shadow-ring-brand-dark dark:disabled:hover:bg-transparent dark:disabled:active:bg-transparent',
  ),
  ghost: cx(
    'bg-transparent text-brand-strong',
    'hover:bg-brand-weak',
    'active:bg-brand-border/60',
    'focus-visible:shadow-ring-brand',
    'disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent disabled:active:bg-transparent',
    'dark:text-brand-strong-dark dark:hover:bg-brand-weak-dark dark:active:bg-brand-border-dark',
    'dark:focus-visible:shadow-ring-brand-dark dark:disabled:hover:bg-transparent dark:disabled:active:bg-transparent',
  ),
  destructive: cx(
    'bg-error-light text-white shadow-e1',
    'hover:bg-error-emphasis',
    'active:bg-error-emphasis active:shadow-none',
    'focus-visible:shadow-ring-error',
    'disabled:cursor-not-allowed disabled:bg-error-light/40 disabled:shadow-none',
    'dark:hover:bg-error-emphasis dark:disabled:bg-error-light/40 dark:focus-visible:shadow-ring-error-dark',
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
  /** Let a text label wrap, preserving the size's minimum height. Icon sizes stay square. */
  wrap?: boolean
  className?: string
}

/** Class-string factory — the full button treatment WITHOUT the <button>
    element, for things styled as buttons that aren't buttons: <Link>s, <a>s,
    summary triggers. Mirrors the kept repo Button's buttonVariants() export
    (3 importers), so the port needs no invention:

      <Link href="/pricing" className={buttonVariants({ variant: 'secondary', size: 'sm' })}>

    <Button> itself composes this same factory — one source of truth. */
export function buttonVariants({ variant = 'primary', size = 'md', wrap = false, className }: ButtonVariantsOptions = {}): string {
  return cx(BASE, SIZE[size],
    size === 'icon-sm' ? cx(HEIGHT[size], 'whitespace-nowrap')
      : wrap ? cx(WRAP_SIZE[size], 'whitespace-normal')
      : cx(HEIGHT[size], 'whitespace-nowrap', wrapWhenNarrow(size, className)),
    VARIANT[resolveVariant(variant)], className)
}

/** The primary variant's `disabled:` look keyed to `aria-disabled`, for a primary <Button> that is
    unavailable but must keep keyboard focus: aria-disabled plus the caller's own guard, never native
    `disabled` (Chromium blurs a focused control that turns disabled). Apply it only while the button
    is unavailable: `loading` also sets aria-disabled and keeps the resting look by design.
    shadow-none would also erase the light focus ring this focusable state can show, so that ring is
    restored (dark's ring out-specifies it). lessons/frontend-busy-controls-stay-focusable.md */
export const primaryUnavailableClass = cx(
  'aria-disabled:cursor-not-allowed aria-disabled:bg-brand/45 aria-disabled:text-white/80 aria-disabled:shadow-none',
  'aria-disabled:focus-visible:shadow-ring-brand dark:aria-disabled:bg-brand-dark/35 dark:aria-disabled:text-background-dark/60',
)

/** The secondary variant's `disabled:` look keyed to `aria-disabled`, for a secondary <Button> that is
    unavailable but must keep keyboard focus: aria-disabled plus the caller's own guard, never native
    `disabled`. Apply it only while the button is unavailable, never while `loading`. It fades the
    label and the hairline, not the element: the native `opacity-50` would fade the focus ring with
    them below the 3:1 focus floor held by tests/unit/siteChromeFocusRing.spec.ts. Dark's hairline is
    brand-weak-dark (0.14), exactly half of brand-border-dark (0.28): `/50` on that rgba token would
    REPLACE its alpha with 0.5, not halve it. Dark repeats the transparent fill because dark:hover: and
    dark:active: out-specify a bare aria-disabled:. lessons/frontend-busy-controls-stay-focusable.md (e) */
export const secondaryUnavailableClass = cx(
  'aria-disabled:cursor-not-allowed aria-disabled:bg-transparent aria-disabled:border-brand-border/50 aria-disabled:text-brand-strong/50',
  'dark:aria-disabled:bg-transparent dark:aria-disabled:border-brand-weak-dark dark:aria-disabled:text-brand-strong-dark/50',
)

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
  /** Let a text label wrap, preserving the size's minimum height. Icon sizes stay square. */
  wrap?: boolean
  loading?: boolean
  /** Optional label swap while loading, e.g. "Generating…" */
  loadingText?: string
  /** A loading label to keep room for at rest, for a swap to a label longer than the resting one (RetryButton's
      "Trying again…"): the content is laid out in one cell over an invisible, aria-hidden copy of the loading
      state (the spinner's box and this label), so the larger of the two sizes the button in every state and
      neither the spinner nor the label swap resizes it or moves what is around it. What shows still follows
      `loading` and `loadingText`. */
  reserveLoadingText?: string
  leftIcon?: ReactNode
  rightIcon?: ReactNode
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', wrap = false, loading = false, loadingText, reserveLoadingText, leftIcon, rightIcon, className, children, onClick, type = 'button', ...rest },
  ref,
) {
  const handleClick = (e: MouseEvent<HTMLButtonElement>) => {
    if (loading) {
      e.preventDefault()
      return
    }
    onClick?.(e)
  }

  const content = (
    <>
      {loading ? <Spinner className={SPINNER_SIZE[size]} /> : leftIcon}
      {loading && loadingText ? loadingText : children}
      {!loading && rightIcon}
    </>
  )

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
      // className goes through buttonVariants so the narrow state can see a caller's own min-h or py.
      className={cx(buttonVariants({ variant, size, wrap, className }), loading && 'cursor-progress')}
      {...rest}
    >
      {reserveLoadingText === undefined ? (
        content
      ) : (
        // One grid cell: what shows, over the loading state laid out invisibly (hidden from assistive tech, its
        // spinner a still box of the spinner's size). Both rows take the button's own gap and centring, and the
        // narrow state's wrapping reaches them as inherited text styles, so each state fills the same cell.
        <span className="grid place-items-center [gap:inherit]">
          <span className="col-start-1 row-start-1 inline-flex items-center [gap:inherit]">{content}</span>
          <span aria-hidden="true" className="invisible col-start-1 row-start-1 inline-flex items-center [gap:inherit]">
            <span className={cx('inline-block shrink-0', SPINNER_SIZE[size])} />
            {reserveLoadingText}
          </span>
        </span>
      )}
    </button>
  )
})
