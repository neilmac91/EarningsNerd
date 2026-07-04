'use client'

/* =============================================================================
   Switch — components/ui/Switch.tsx
   -----------------------------------------------------------------------------
   A binary toggle: brand-filled track when on, quiet neutral track when off,
   white knob that slides. The DS home for the hand-rolled `role="switch"`
   buttons (pricing billing cycle, notification preferences). Controlled only —
   pass `checked` + `onCheckedChange`. Focus-visible = brand ring; the knob
   slide respects prefers-reduced-motion.
============================================================================= */

import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { cx } from './cx'

export interface SwitchProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'onChange'> {
  checked: boolean
  onCheckedChange?: (checked: boolean) => void
}

export const Switch = forwardRef<HTMLButtonElement, SwitchProps>(function Switch(
  { checked, onCheckedChange, disabled, className, onClick, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={(e) => {
        onClick?.(e)
        if (!disabled) onCheckedChange?.(!checked)
      }}
      className={cx(
        'relative inline-flex h-6 w-11 flex-none items-center rounded-full transition-colors duration-fast',
        'focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
        'disabled:cursor-not-allowed disabled:opacity-50',
        checked ? 'bg-brand-strong dark:bg-brand-dark' : 'bg-border-light dark:bg-white/15',
        className,
      )}
      {...rest}
    >
      <span
        aria-hidden="true"
        className={cx(
          'inline-block h-4 w-4 rounded-full bg-white shadow-e1 transition-transform duration-fast motion-reduce:transition-none',
          checked ? 'translate-x-6' : 'translate-x-1',
        )}
      />
    </button>
  )
})
