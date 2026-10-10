'use client'

/* =============================================================================
   Input — components/ui/Input.tsx  (Input / Textarea / Select)
   -----------------------------------------------------------------------------
   Field fill is the BRIGHTEST surface (white / dark glass) so it reads on both
   the cream page and an off-white card. Focus-visible = brand ring
   (shadow-ring-brand / shadow-ring-brand-dark); invalid fields swap to the
   error ring. States: default / hover / focus / disabled / loading (Input) /
   error — with aria-invalid + aria-describedby wired automatically.
   v2.2: Input grows a leading `icon` slot (explicit pl-11 inset — no px/pl
   conflict-order reliance; also inputClasses({ leadingIcon }) for raw fields),
   and Textarea grows variant="composer" (transparent auto-growing field for a
   focus-within shell — the chat composer, no double chrome).
   v3.2: inputClasses() grows `select` (a raw <select> takes the Select
   component's padding, so its chevron has room) and `autoWidth` (the field sizes
   to its content instead of filling its container). A raw field never takes a
   class on top that sets what the field already sets: cx does no tailwind-merge,
   so stylesheet order, not class order, decides (gate:
   tests/unit/inputClassesNoOverrides.spec.tsx).
   v3.3: inputClasses() grows `trailingIcon` (the 40px trailing inset for a control
   drawn at the field's right edge, the password reveal toggle), explicit sides
   per density like `select`.
   Assumes @tailwindcss/forms (already in the config plugins).
============================================================================= */

import {
  forwardRef,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from 'react'
import { cx } from './cx'

/** SSR-safe layout effect (same trick as hooks/useCountUp) — layout timing on
    the client so composer auto-grow never flashes; plain effect on the server. */
const useIsoLayoutEffect = typeof window !== 'undefined' ? useLayoutEffect : useEffect

/** The field's look without a width: inputClasses({ autoWidth }) picks the width explicitly. */
const FIELD_BASE = cx(
  'rounded-lg border text-sm transition-[border-color,box-shadow] duration-fast',
  'border-border-light bg-white text-text-primary-light placeholder:text-text-tertiary-light',
  'hover:border-flat-light',
  'focus:border-brand focus:shadow-ring-brand focus:outline-none',
  'disabled:cursor-not-allowed disabled:bg-background-light disabled:opacity-60 disabled:hover:border-border-light',
  // dark: muted copy uses `secondary`, never `tertiary` (fails AA on navy)
  'dark:border-border-dark dark:bg-white/5 dark:text-text-primary-dark dark:placeholder:text-text-secondary-dark',
  'dark:hover:border-flat-dark dark:focus:border-brand-dark dark:focus:shadow-ring-brand-dark',
  'dark:disabled:bg-white/5 dark:disabled:hover:border-border-dark',
)
const FIELD = cx('w-full', FIELD_BASE)

const INVALID = cx(
  'border-error-light focus:border-error-light focus:shadow-ring-error',
  'dark:border-error-dark dark:focus:border-error-dark dark:focus:shadow-ring-error',
)

const PAD = 'px-3.5 py-2.5'
/** Leading-icon inset — EXPLICIT sides. px-3.5 + a pl-11 override is Tailwind
    conflict-order-dependent (both are padding utilities; stylesheet order, not
    class order, wins) — the two search fields hand-rolled that gamble (v2.2). */
const PAD_ICON = 'py-2.5 pl-11 pr-3.5'

/** v3.1 — field density. `comfortable` (default) is the form field (42px: 10px padding, a 20px line,
    1px borders). `compact` is the TOOLBAR field (the filings index's year filter, beside a
    SegmentedControl) and the field inside a table row (the admin feedback status): 36px from sm
    up, while phones keep the standard 42px. Named `density`
    (DataTable's vocabulary), not `size` — `size` is a native <input>/<select> attribute. EXPLICIT
    sides per density, never an override on top of PAD: cx does no tailwind-merge, so two padding
    utilities resolve by stylesheet order, not class order. */
export type FieldDensity = 'comfortable' | 'compact'
const PAD_COMPACT = 'px-3.5 py-2.5 sm:h-9 sm:px-3 sm:py-1.5'
const PAD_ICON_COMPACT = 'py-2.5 pl-11 pr-3.5 sm:h-9 sm:py-1.5 sm:pl-10 sm:pr-3'
const SELECT_PAD = { comfortable: 'py-2.5 pl-3.5 pr-9', compact: 'py-2.5 pl-3.5 pr-9 sm:h-9 sm:py-1.5 sm:pl-3' } as const
/** v3.3 — trailing inset: pr-10 (40px) in both densities, as SELECT_PAD keeps pr-9, because the control does
    not move with density. EXPLICIT sides, never pr-10 on top of PAD: that pair resolves by stylesheet order
    (the padding plugin emits sides after axes), the conflict the leading inset already avoids. */
const PAD_TRAILING = 'py-2.5 pl-3.5 pr-10'
const PAD_ICON_TRAILING = 'py-2.5 pl-11 pr-10'
const PAD_TRAILING_COMPACT = 'py-2.5 pl-3.5 pr-10 sm:h-9 sm:py-1.5 sm:pl-3'
const PAD_ICON_TRAILING_COMPACT = 'py-2.5 pl-11 pr-10 sm:h-9 sm:py-1.5 sm:pl-10'
/** A field's padding by density and inset: one explicit literal each. */
const FIELD_PAD = {
  comfortable: { plain: PAD, leading: PAD_ICON, trailing: PAD_TRAILING, both: PAD_ICON_TRAILING },
  compact: { plain: PAD_COMPACT, leading: PAD_ICON_COMPACT, trailing: PAD_TRAILING_COMPACT, both: PAD_ICON_TRAILING_COMPACT },
} as const

interface InputClassesBase {
  /** Renders the error-ring treatment (mirrors what the `error` prop wires). */
  invalid?: boolean
  /** v3.1: `compact` = the 36px toolbar field from sm up (phones keep the standard 42px). */
  density?: FieldDensity
  /** v3.2: the field sizes to its content instead of filling its container: a select beside its
      label in a flex row, a toolbar filter, a table cell. Capped at its container (`max-w-full`)
      for options that come from data. Never `w-auto` on top of the default: the stylesheet emits
      `.w-full` after `.w-auto`, so that override loses. */
  autoWidth?: boolean
  className?: string
}

/** `select` sets the whole padding (its chevron holds the trailing side), so a select takes neither
    inset; `leadingIcon` and `trailingIcon` combine. */
export type InputClassesOptions = InputClassesBase &
  (
    | {
        /** Reserve the pl-11 leading-icon inset (you render the icon — absolute,
            left-3.5, centered, pointer-events-none, muted tone). */
        leadingIcon?: boolean
        /** v3.3: reserve the pr-10 (40px) trailing inset for a control you render at the field's right
            edge (the password reveal toggle). Sized for a glyph of at most 16px whose outer edge sits 12px
            in (`right-3`, or `right-0` with `pr-3`): it spans 12–28px from the edge and leaves 13px before
            the text. A larger glyph, or one set further in, runs into the text. */
        trailingIcon?: boolean
        select?: false
      }
    | {
        /** v3.2: a raw <select> takes the Select component's padding (SELECT_PAD, per density):
            its pr-9 clears the forms plugin's chevron, where PAD's 14px right inset lets a
            content-width select's text run under it. */
        select: true
        leadingIcon?: never
        trailingIcon?: never
      }
  )

/** Class-string factory — the full field treatment for raw <input>/<select>
    elements the component can't wrap (third-party pickers, combobox libs).
    Mirrors the kept repo Input's inputClasses export (7 importers), so the
    port is mechanical: `inputClasses` → `inputClasses()`. The components
    below compose the same pieces — one source of truth. */
export function inputClasses({
  invalid = false,
  leadingIcon = false,
  trailingIcon = false,
  select = false,
  density = 'comfortable',
  autoWidth = false,
  className,
}: InputClassesOptions = {}): string {
  const inset = leadingIcon ? (trailingIcon ? 'both' : 'leading') : trailingIcon ? 'trailing' : 'plain'
  const pad = select ? SELECT_PAD[density] : FIELD_PAD[density][inset]
  return cx(autoWidth ? cx('max-w-full', FIELD_BASE) : FIELD, pad, invalid && INVALID, className)
}

/** The field's `disabled:` look keyed to `aria-disabled`, for a field (a <select> here) that is
    unavailable while its own save runs but must keep keyboard focus: aria-disabled plus a guarded
    change handler, never native `disabled` (Chromium blurs a focused control that turns disabled).
    It fades the text ink, not the element: the native look's `opacity-60` would fade the focus ring
    this focusable state still shows. The hairline keeps its strength, since it carries the field's
    focus and invalid states. lessons/frontend-busy-controls-stay-focusable.md (e) */
export const fieldUnavailableClass = cx(
  'aria-disabled:cursor-not-allowed aria-disabled:bg-background-light aria-disabled:text-text-primary-light/60 aria-disabled:hover:border-border-light',
  'dark:aria-disabled:bg-white/5 dark:aria-disabled:text-text-primary-dark/60 dark:aria-disabled:hover:border-border-dark',
)

interface FieldExtras {
  label?: ReactNode
  hint?: ReactNode
  error?: ReactNode
}

function Shell({
  id,
  label,
  hint,
  error,
  children,
  className,
}: FieldExtras & { id: string; children: ReactNode; className?: string }) {
  return (
    <div className={cx('flex flex-col gap-1.5', className)}>
      {label ? (
        <label htmlFor={id} className="text-sm font-medium text-text-primary-light dark:text-text-primary-dark">
          {label}
        </label>
      ) : null}
      {children}
      {/* A boolean error means "invalid, no message": style the field, render
          no alert row (and wire no aria-describedby — see describedBy below). */}
      {error && typeof error !== 'boolean' ? (
        <p id={`${id}-error`} role="alert" className="text-xs font-medium text-error-light dark:text-error-dark">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="text-xs text-text-tertiary-light dark:text-text-secondary-dark">
          {hint}
        </p>
      ) : null}
    </div>
  )
}

function FieldSpinner() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-brand-strong motion-reduce:animate-none dark:text-brand-strong-dark"
    >
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.3" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}

/* ---------------------------------------------------------------- Input -- */

export interface InputProps extends InputHTMLAttributes<HTMLInputElement>, FieldExtras {
  /** Async lookup in flight (e.g. ticker validation) — trailing spinner + aria-busy. */
  loading?: boolean
  /** Leading glyph (16–18px — a Phosphor magnifier, a ticker mark). Swaps the
      left inset to the pl-11 icon padding; muted tone, pointer-events-none.
      The trailing slot stays reserved for the loading spinner. */
  icon?: ReactNode
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hint, error, loading, icon, className, id: idProp, ...rest },
  ref,
) {
  const autoId = useId()
  const id = idProp ?? autoId
  const describedBy = error && typeof error !== 'boolean' ? `${id}-error` : hint ? `${id}-hint` : undefined
  return (
    <Shell id={id} label={label} hint={hint} error={error} className={className}>
      <div className="relative">
        {icon ? (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-text-tertiary-light dark:text-text-secondary-dark"
          >
            {icon}
          </span>
        ) : null}
        <input
          ref={ref}
          id={id}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          aria-busy={loading || undefined}
          className={cx(
            FIELD,
            // Explicit per-side padding — no px/pl/pr conflict-order reliance.
            'py-2.5',
            icon ? 'pl-11' : 'pl-3.5',
            loading ? 'pr-10' : 'pr-3.5',
            error ? INVALID : undefined,
          )}
          {...rest}
        />
        {loading ? <FieldSpinner /> : null}
      </div>
    </Shell>
  )
})

/* ------------------------------------------------------------- Textarea -- */

/** Composer chrome — the transparent field for a focus-within shell. The SHELL
    (app-owned: send button, attachments) carries border + ring so there is no
    double chrome:

      <div className={cx(
        inputClasses({ className: 'flex items-end gap-2' }),
        'focus-within:border-brand focus-within:shadow-ring-brand',
        'dark:focus-within:border-brand-dark dark:focus-within:shadow-ring-brand-dark',
      )}>
        <Textarea variant="composer" aria-label="Ask this filing" placeholder="Ask this filing…" />
        <Button size="sm">Ask</Button>
      </div> */
const COMPOSER = cx(
  'w-full resize-none border-0 bg-transparent p-0 text-sm',
  'text-text-primary-light placeholder:text-text-tertiary-light',
  'focus:outline-none focus:ring-0 focus:shadow-none',
  'disabled:cursor-not-allowed disabled:opacity-60',
  'dark:text-text-primary-dark dark:placeholder:text-text-secondary-dark',
)

export type TextareaVariant = 'default' | 'composer'

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement>, FieldExtras {
  /** 'composer' = transparent, auto-growing field for a focus-within shell
      (chat composer) — no border/ring of its own, rows defaults to 1. */
  variant?: TextareaVariant
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, hint, error, className, id: idProp, rows, variant = 'default', onInput, ...rest },
  ref,
) {
  const autoId = useId()
  const id = idProp ?? autoId
  const describedBy = error && typeof error !== 'boolean' ? `${id}-error` : hint ? `${id}-hint` : undefined
  const composer = variant === 'composer'
  const innerRef = useRef<HTMLTextAreaElement | null>(null)

  const grow = () => {
    const el = innerRef.current
    if (!el) return
    el.style.height = 'auto'
    // A hidden composer (display:none pane — a closed workspace/sheet) measures
    // scrollHeight 0; pinning height:0px would leave the field invisible after
    // the pane opens (the effect only re-runs on value change). Keep natural
    // rows-based height until it's measurable.
    if (el.scrollHeight === 0) return
    el.style.height = `${el.scrollHeight}px`
  }
  // Controlled composers resize on value change; uncontrolled ones via onInput.
  useIsoLayoutEffect(() => {
    if (composer) grow()
  }, [composer, rest.value])

  return (
    <Shell id={id} label={label} hint={hint} error={error} className={className}>
      <textarea
        ref={(node) => {
          innerRef.current = node
          if (typeof ref === 'function') ref(node)
          else if (ref) ref.current = node
        }}
        id={id}
        rows={rows ?? (composer ? 1 : 4)}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        onInput={(e) => {
          if (composer) grow()
          onInput?.(e)
        }}
        className={composer ? COMPOSER : cx(FIELD, PAD, 'resize-y', error ? INVALID : undefined)}
        {...rest}
      />
    </Shell>
  )
})

/* --------------------------------------------------------------- Select -- */

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement>, FieldExtras {
  /** v3.1: `compact` = the 36px toolbar select from sm up (phones keep the standard 42px). */
  density?: FieldDensity
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, hint, error, className, id: idProp, density = 'comfortable', children, ...rest },
  ref,
) {
  const autoId = useId()
  const id = idProp ?? autoId
  const describedBy = error && typeof error !== 'boolean' ? `${id}-error` : hint ? `${id}-hint` : undefined
  return (
    <Shell id={id} label={label} hint={hint} error={error} className={className}>
      <select
        ref={ref}
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={cx(FIELD, SELECT_PAD[density], error ? INVALID : undefined)}
        {...rest}
      >
        {children}
      </select>
    </Shell>
  )
})
