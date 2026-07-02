/* =============================================================================
   Input — components/ui/Input.tsx  (Input / Textarea / Select)
   -----------------------------------------------------------------------------
   Field fill is the BRIGHTEST surface (white / dark glass) so it reads on both
   the cream page and an off-white card. Focus-visible = brand ring
   (shadow-ring-brand / shadow-ring-brand-dark); invalid fields swap to the
   error ring. States: default / hover / focus / disabled / loading (Input) /
   error — with aria-invalid + aria-describedby wired automatically.
   Assumes @tailwindcss/forms (already in the config plugins).
============================================================================= */

import {
  forwardRef,
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from 'react'
import { cx } from './cx'

const FIELD = cx(
  'w-full rounded-lg border text-sm transition-[border-color,box-shadow] duration-fast',
  'border-border-light bg-white text-text-primary-light placeholder:text-text-tertiary-light',
  'hover:border-flat-light',
  'focus:border-brand focus:shadow-ring-brand focus:outline-none',
  'disabled:cursor-not-allowed disabled:bg-background-light disabled:opacity-60 disabled:hover:border-border-light',
  // dark: muted copy uses `secondary`, never `tertiary` (fails AA on navy)
  'dark:border-border-dark dark:bg-white/5 dark:text-text-primary-dark dark:placeholder:text-text-secondary-dark',
  'dark:hover:border-flat-dark dark:focus:border-brand-dark dark:focus:shadow-ring-brand-dark',
  'dark:disabled:bg-white/5 dark:disabled:hover:border-border-dark',
)

const INVALID = cx(
  'border-error-light focus:border-error-light focus:shadow-ring-error',
  'dark:border-error-dark dark:focus:border-error-dark dark:focus:shadow-ring-error',
)

const PAD = 'px-3.5 py-2.5'

export interface InputClassesOptions {
  /** Renders the error-ring treatment (mirrors what the `error` prop wires). */
  invalid?: boolean
  className?: string
}

/** Class-string factory — the full field treatment for raw <input>/<select>
    elements the component can't wrap (third-party pickers, combobox libs).
    Mirrors the kept repo Input's inputClasses export (7 importers), so the
    port is mechanical: `inputClasses` → `inputClasses()`. The components
    below compose the same pieces — one source of truth. */
export function inputClasses({ invalid = false, className }: InputClassesOptions = {}): string {
  return cx(FIELD, PAD, invalid && INVALID, className)
}

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
      {/* A boolean error means "invalid, no message" — render no alert (an empty
          role="alert" announces nothing useful and shifts layout). */}
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
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hint, error, loading, className, id: idProp, ...rest },
  ref,
) {
  const autoId = useId()
  const id = idProp ?? autoId
  const describedBy = error && typeof error !== 'boolean' ? `${id}-error` : hint ? `${id}-hint` : undefined
  return (
    <Shell id={id} label={label} hint={hint} error={error} className={className}>
      <div className="relative">
        <input
          ref={ref}
          id={id}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          aria-busy={loading || undefined}
          className={cx(FIELD, PAD, Boolean(error) && INVALID, Boolean(loading) && 'pr-10')}
          {...rest}
        />
        {loading ? <FieldSpinner /> : null}
      </div>
    </Shell>
  )
})

/* ------------------------------------------------------------- Textarea -- */

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement>, FieldExtras {}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, hint, error, className, id: idProp, rows = 4, ...rest },
  ref,
) {
  const autoId = useId()
  const id = idProp ?? autoId
  const describedBy = error && typeof error !== 'boolean' ? `${id}-error` : hint ? `${id}-hint` : undefined
  return (
    <Shell id={id} label={label} hint={hint} error={error} className={className}>
      <textarea
        ref={ref}
        id={id}
        rows={rows}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={cx(FIELD, PAD, 'resize-y', Boolean(error) && INVALID)}
        {...rest}
      />
    </Shell>
  )
})

/* --------------------------------------------------------------- Select -- */

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement>, FieldExtras {}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, hint, error, className, id: idProp, children, ...rest },
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
        className={cx(FIELD, PAD, 'pr-9', Boolean(error) && INVALID)}
        {...rest}
      >
        {children}
      </select>
    </Shell>
  )
})
