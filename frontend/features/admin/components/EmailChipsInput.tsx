'use client'

import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import { clsx } from 'clsx'
import { WarningCircleIcon, XIcon } from '@/lib/icons'
import { inputClasses } from '@/components/ui/Input'
import { parseEmails, classifyEmail } from '@/features/admin/lib/parseEmails'

export interface EmailChipsBreakdown {
  /** Valid emails that are NOT already invited — the ones the parent should actually send. */
  toInvite: string[]
  invalid: string[]
  alreadyInvited: string[]
}

interface EmailChipsInputProps {
  /** Lowercased emails that already have a pending invite (matched case-insensitively). */
  alreadyInvited: string[]
  /** Fired whenever the chip set changes, with the current breakdown. */
  onChange: (breakdown: EmailChipsBreakdown) => void
  disabled?: boolean
}

type ChipKind = 'valid' | 'invalid' | 'invited'

interface Chip {
  email: string
  kind: ChipKind
}

/**
 * A textarea-style field that tokenizes pasted/typed emails into removable chips. Tokenizing
 * happens on Enter, comma, blur, and paste — never on every keystroke, so typing an address
 * isn't fought by premature chipping. Crucially the draft input is NEVER cleared on a parse
 * error: an admin who pastes a messy block keeps everything visible and editable.
 *
 * Chips are colored by state: valid (brand), invalid (error border + icon, aria-invalid),
 * already-invited (muted). The parent receives only valid, not-already-invited emails to send.
 */
export default function EmailChipsInput({
  alreadyInvited,
  onChange,
  disabled,
}: EmailChipsInputProps) {
  const [emails, setEmails] = useState<string[]>([])
  const [draft, setDraft] = useState('')
  const fieldId = useId()

  const invitedSet = useMemo(
    () => new Set(alreadyInvited.map((e) => e.trim().toLowerCase())),
    [alreadyInvited],
  )

  const chips: Chip[] = useMemo(
    () =>
      emails.map((email) => {
        // `emails` holds already-tokenized single addresses, so a direct regex check is enough
        // (no need to re-split via parseEmails).
        if (!classifyEmail(email)) return { email, kind: 'invalid' as const }
        if (invitedSet.has(email)) return { email, kind: 'invited' as const }
        return { email, kind: 'valid' as const }
      }),
    [emails, invitedSet],
  )

  // Emit the breakdown to the parent whenever the chip set OR the already-invited set changes.
  // Doing this in an effect (rather than inside the setState updater) keeps the parent's
  // setState out of the child's render phase, avoiding cross-component update warnings.
  const onChangeRef = useRef(onChange)
  // eslint-disable-next-line react-hooks/refs -- deliberate latest-ref pattern: keep the ref pointing at the current onChange so the emit effect calls it without re-subscribing
  onChangeRef.current = onChange
  useEffect(() => {
    const toInvite: string[] = []
    const invalid: string[] = []
    const alreadyInvitedOut: string[] = []
    for (const email of emails) {
      if (!classifyEmail(email)) invalid.push(email)
      else if (invitedSet.has(email)) alreadyInvitedOut.push(email)
      else toInvite.push(email)
    }
    onChangeRef.current({ toInvite, invalid, alreadyInvited: alreadyInvitedOut })
  }, [emails, invitedSet])

  // Merge the parsed tokens (valid + invalid both become chips so the admin sees typos) into
  // the existing set, deduped on the normalized value. The change is emitted via the effect.
  const commit = useCallback((raw: string) => {
    const parsed = parseEmails(raw)
    const incoming = [...parsed.valid, ...parsed.invalid]
    if (incoming.length === 0) return
    setEmails((prev) => {
      const seen = new Set(prev)
      const next = [...prev]
      for (const e of incoming) {
        if (!seen.has(e)) {
          seen.add(e)
          next.push(e)
        }
      }
      return next
    })
    setDraft('')
  }, [])

  const removeChip = useCallback((email: string) => {
    setEmails((prev) => prev.filter((e) => e !== email))
  }, [])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      commit(draft)
    } else if (e.key === 'Backspace' && draft === '' && emails.length > 0) {
      // Convenience: backspace on an empty draft pops the last chip back into the draft.
      const last = emails[emails.length - 1]
      e.preventDefault()
      setEmails((prev) => prev.slice(0, -1))
      setDraft(last)
    }
  }

  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const text = e.clipboardData.getData('text')
    if (/[\s,;]/.test(text)) {
      e.preventDefault()
      commit(`${draft} ${text}`)
    }
  }

  const chipClasses = (kind: ChipKind): string => {
    switch (kind) {
      case 'invalid':
        return 'border-error-light/40 bg-error-light/10 text-error-light dark:border-error-dark/40 dark:bg-error-dark/15 dark:text-error-dark'
      case 'invited':
        return 'border-border-light bg-black/[0.04] text-text-tertiary-light dark:border-white/10 dark:bg-white/5 dark:text-text-secondary-dark'
      default:
        return 'border-brand-border bg-brand-strong/10 text-brand-strong dark:border-brand-dark/40 dark:bg-brand-dark/15 dark:text-brand-strong-dark'
    }
  }

  return (
    <div>
      <label
        htmlFor={fieldId}
        className="mb-2 block text-sm font-medium text-text-primary-light dark:text-text-primary-dark"
      >
        Email addresses
      </label>

      {chips.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-2">
          {chips.map((chip) => (
            <span
              key={chip.email}
              aria-invalid={chip.kind === 'invalid' || undefined}
              className={clsx(
                'inline-flex max-w-full items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium',
                chipClasses(chip.kind),
              )}
            >
              {chip.kind === 'invalid' && <WarningCircleIcon className="h-3.5 w-3.5 flex-shrink-0" />}
              <span className="truncate">{chip.email}</span>
              {chip.kind === 'invited' && (
                <span className="text-[10px] uppercase tracking-wide opacity-70">invited</span>
              )}
              <button
                type="button"
                onClick={() => removeChip(chip.email)}
                disabled={disabled}
                aria-label={`Remove ${chip.email}`}
                className="ml-0.5 rounded-full p-0.5 transition-colors hover:bg-black/10 disabled:opacity-50 dark:hover:bg-white/10"
              >
                <XIcon className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      <textarea
        id={fieldId}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        onBlur={() => commit(draft)}
        disabled={disabled}
        rows={3}
        placeholder="alice@example.com, bob@example.com (paste or type, Enter to add)"
        className={clsx(inputClasses(), 'resize-y')}
      />
      <p className="mt-1.5 text-xs text-text-tertiary-light dark:text-text-secondary-dark">
        Separate addresses with commas, spaces, or new lines. Press Enter to add.
      </p>
    </div>
  )
}
