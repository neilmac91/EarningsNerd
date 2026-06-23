'use client'

import { useState } from 'react'
import { EyeIcon, EyeSlashIcon } from '@/lib/icons'
import { Input } from '@/components/ui/Input'

type PasswordFieldProps = {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  autoComplete?: 'current-password' | 'new-password'
  required?: boolean
  minLength?: number
  hint?: string
  /** Render a strength meter below the field (used on reset/register). */
  showStrength?: boolean
  /** Optional element rendered to the right of the label (e.g. "Forgot password?"). */
  labelAction?: React.ReactNode
  autoFocus?: boolean
}

const STRENGTH_LABELS = ['Too short', 'Weak', 'Fair', 'Good', 'Strong']
const STRENGTH_COLORS = [
  'bg-red-500',
  'bg-orange-500',
  'bg-yellow-500',
  'bg-brand-strong',
  'bg-brand-light',
]

function scorePassword(pw: string): number {
  if (!pw) return 0
  let score = 0
  if (pw.length >= 8) score++
  if (pw.length >= 12) score++
  if (/\d/.test(pw) && /[a-zA-Z]/.test(pw)) score++
  if (/[^a-zA-Z0-9]/.test(pw)) score++
  return Math.min(score, 4)
}

export default function PasswordField({
  id,
  label,
  value,
  onChange,
  autoComplete = 'current-password',
  required,
  minLength,
  hint,
  showStrength,
  labelAction,
  autoFocus,
}: PasswordFieldProps) {
  const [show, setShow] = useState(false)
  const score = showStrength ? scorePassword(value) : 0

  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <label
          htmlFor={id}
          className="block text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark"
        >
          {label}
        </label>
        {labelAction}
      </div>

      <div className="relative">
        <Input
          type={show ? 'text' : 'password'}
          id={id}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          required={required}
          minLength={minLength}
          autoComplete={autoComplete}
          autoFocus={autoFocus}
          className="pr-10"
        />
        <button
          type="button"
          onClick={() => setShow((s) => !s)}
          aria-label={show ? 'Hide password' : 'Show password'}
          className="absolute inset-y-0 right-0 flex items-center pr-3 text-text-tertiary-light transition-colors hover:text-text-secondary-light dark:text-text-tertiary-dark dark:hover:text-text-secondary-dark focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-light"
        >
          {show ? <EyeSlashIcon className="h-4 w-4" /> : <EyeIcon className="h-4 w-4" />}
        </button>
      </div>

      {showStrength && value.length > 0 && (
        <div className="mt-2" aria-live="polite">
          <div className="flex gap-1" aria-hidden="true">
            {[0, 1, 2, 3].map((i) => (
              <div
                key={i}
                className={`h-1 flex-1 rounded-full transition-colors ${
                  i < score ? STRENGTH_COLORS[score] : 'bg-border-light dark:bg-border-dark'
                }`}
              />
            ))}
          </div>
          <p className="mt-1 text-xs text-text-tertiary-light dark:text-text-tertiary-dark">
            {STRENGTH_LABELS[score]}
          </p>
        </div>
      )}

      {hint && (
        <p className="mt-2 text-xs text-text-tertiary-light dark:text-text-tertiary-dark">{hint}</p>
      )}
    </div>
  )
}
