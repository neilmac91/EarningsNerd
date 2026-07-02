import { clsx } from 'clsx'
import { forwardRef } from 'react'

/**
 * TODO(design-system-v2): this pre-v2 Input (inputClasses) was kept at cutover —
 * 8 importers rely on the exported class string. The v2 field set (Input/Textarea/
 * Select with label/hint/error wiring) ports in a follow-up, then gets exported
 * from components/ui/index.ts.
 *
 * Shared text-field styling for the EarningsNerd design system. Use `<Input>` for
 * `<input>`; for `<textarea>`/`<select>` apply `inputClasses` to the element's className.
 *
 * The fill is the BRIGHTEST surface (`bg-white` light / `bg-slate-900/60` dark) so the
 * field reads clearly whether it sits on the cream page or an off-white card — fixing
 * the "input fill == card fill" delineation gap (see frontend/DESIGN_SYSTEM.md §3).
 */
export const inputClasses =
  'w-full rounded-lg border border-border-light bg-white px-3 py-2 ' +
  'text-text-primary-light placeholder:text-text-tertiary-light transition-colors ' +
  'focus:border-brand-light focus:outline-none focus:ring-2 focus:ring-brand-light/40 ' +
  'disabled:opacity-50 disabled:cursor-not-allowed ' +
  'dark:border-white/10 dark:bg-slate-900/60 dark:text-text-primary-dark dark:placeholder:text-text-secondary-dark'

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input({ className, ...props }, ref) {
  return <input ref={ref} className={clsx(inputClasses, className)} {...props} />
})
