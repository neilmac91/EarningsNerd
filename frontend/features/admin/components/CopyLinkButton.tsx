'use client'

import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { CheckIcon, CopyIcon } from '@/lib/icons'

interface CopyLinkButtonProps {
  /** The invite link written to the clipboard. */
  link: string
  /**
   * The status line of the dialog the button sits in, which says a press there (the resend dialog's). The page's toast
   * region lies outside an aria-modal dialog, which hides it from VoiceOver, so from inside one a toast is never heard
   * (chief design on #1793). Without it, a press is said in the toast region.
   */
  onStatus?: (message: string) => void
}

/**
 * Small copy-to-clipboard button, shared across the admin invite surfaces (the bulk results, the resend dialog). It
 * keeps its words, so its name is what it shows (WCAG 2.5.3), and says a press where a screen reader hears it (4.1.3):
 * in the bulk summary through the toast region, "Invite link copied", as the summary's own send does, and in the resend
 * dialog in the dialog's status line (`onStatus`), its icon turning to a check for a moment beside it. Words that
 * flashed to say it was copied renamed the button, and inside a live region (the bulk summary's) were heard on top of
 * any confirmation: one confirmation is heard in each place (chief design on #1789, #1791 and #1793). The flash timer
 * is cleared on unmount so we never setState on an unmounted node.
 */
export default function CopyLinkButton({ link, onStatus }: CopyLinkButtonProps) {
  const [copied, setCopied] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current)
  }, [])

  const handleCopy = async () => {
    // Emptied first, so a second press that says the same is said again.
    onStatus?.('')
    try {
      await navigator.clipboard.writeText(link)
      if (onStatus) onStatus('Invite link copied.')
      else toast.success('Invite link copied')
      setCopied(true)
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
      if (onStatus) onStatus('Could not copy the link.')
      else toast.error('Could not copy the link.')
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark inline-flex items-center gap-1 rounded-lg border border-border-light bg-panel-light px-2 py-1 text-xs font-medium text-text-secondary-light transition-colors hover:bg-brand-weak dark:border-white/10 dark:bg-panel-dark dark:text-text-secondary-dark dark:hover:bg-white/5"
    >
      {copied ? <CheckIcon className="h-3.5 w-3.5" /> : <CopyIcon className="h-3.5 w-3.5" />}
      Copy link
    </button>
  )
}
