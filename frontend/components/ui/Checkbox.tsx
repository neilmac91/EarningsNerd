/* =============================================================================
   Checkbox — components/ui/Checkbox.tsx
   -----------------------------------------------------------------------------
   The one checkbox recipe (the consent dialog's categories, the admin invites
   page's "Email invites"). A native <input type="checkbox"> styled by the
   forms plugin, which draws a white check on the checked fill. Every value is
   a token, and each state clears the 3:1 floor for a control's parts (WCAG
   1.4.11):
     - checked, light: brand-strong #3C6650, 6.3:1 on panel; white check 6.6:1.
     - checked, dark:  brand-fill-dark #569272, 4.0:1 on panel-dark; white check
                       3.7:1. brand-strong (the old dark fill) is 2.2:1 there,
                       and brand-dark under a white check is 2.4:1.
     - unchecked: the flat ink as the box's edge, 4.6:1 on panel, 5.8:1 on
                  panel-dark (the hairline border tokens are 1.2:1 and 1.4:1).
   The checked fill is stated per theme (`checked:bg-*`): the plugin paints it
   with `[type='checkbox']:checked`, which a `dark:bg-panel-dark` outranks, so
   a dark ground without its own checked fill draws a checked box as empty.
   Focus-visible = brand ring; the plugin's own ring is taken off. `size` is
   the box: 'sm' 16px beside body text, 'md' 20px beside a card title; a
   wrapper sets it, so the field's className stays one static recipe.
   The props are named, not spread, and there is no className: the app-wide
   field gate (siteChromeFocusRing.spec.ts) reads the field's classes as
   written, and a spread could replace them.
   tests/unit/checkboxRecipe.spec.tsx holds the contrast and that no page
   hand-rolls a checkbox again.
============================================================================= */

import { forwardRef, type ChangeEventHandler } from 'react'
import { cx } from './cx'

export interface CheckboxProps {
  checked?: boolean
  defaultChecked?: boolean
  onChange?: ChangeEventHandler<HTMLInputElement>
  disabled?: boolean
  id?: string
  name?: string
  'aria-label'?: string
  'aria-labelledby'?: string
  'aria-describedby'?: string
  size?: 'sm' | 'md'
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(function Checkbox(
  {
    checked,
    defaultChecked,
    onChange,
    disabled,
    id,
    name,
    'aria-label': ariaLabel,
    'aria-labelledby': ariaLabelledBy,
    'aria-describedby': ariaDescribedBy,
    size = 'md',
  },
  ref,
) {
  return (
    <span className={cx('inline-flex flex-none', size === 'sm' ? 'h-4 w-4' : 'h-5 w-5')}>
      <input
        ref={ref}
        type="checkbox"
        id={id}
        name={name}
        checked={checked}
        defaultChecked={defaultChecked}
        onChange={onChange}
        disabled={disabled}
        aria-label={ariaLabel}
        aria-labelledby={ariaLabelledBy}
        aria-describedby={ariaDescribedBy}
        className={cx(
          'h-full w-full rounded border border-flat-light bg-panel-light text-brand-strong checked:border-transparent checked:bg-brand-strong',
          'dark:border-flat-dark dark:bg-panel-dark dark:text-brand-fill-dark dark:checked:border-transparent dark:checked:bg-brand-fill-dark',
          'focus:ring-0 focus:ring-offset-0 focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
          'disabled:cursor-not-allowed disabled:opacity-50',
        )}
      />
    </span>
  )
})
