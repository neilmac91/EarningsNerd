'use client'

import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { CheckIcon, CopyIcon } from '@/lib/icons'

interface CopyLinkButtonProps {
  /** The invite link written to the clipboard. */
  link: string
}

/**
 * Small copy-to-clipboard button, shared across the admin invite surfaces (the bulk results, the resend dialog). It
 * keeps its words, so its name is what it shows (WCAG 2.5.3), and confirms through the toast region, "Invite link
 * copied", as the share panel's Copy message does (4.1.3), its icon turning to a check for a moment beside it. Words
 * that flashed to say it was copied renamed the button, and inside a live region (the bulk summary's) were heard on
 * top of any confirmation: one confirmation is heard in each place (chief design on #1789 and #1791). The flash timer
 * is cleared on unmount so we never setState on an unmounted node.
 */
export default function CopyLinkButton({ link }: CopyLinkButtonProps) {
  const [copied, setCopied] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current)
  }, [])

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(link)
      toast.success('Invite link copied')
      setCopied(true)
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
      toast.error('Could not copy the link.')
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
