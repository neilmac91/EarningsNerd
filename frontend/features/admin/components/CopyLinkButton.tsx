'use client'

import { useEffect, useRef, useState } from 'react'
import { CopyIcon } from '@/lib/icons'

interface CopyLinkButtonProps {
  /** The text written to the clipboard. */
  link: string
  /** Idle label (default "Copy link"). */
  label?: string
  /** Flash label shown briefly after a successful copy (default "Copied"). */
  copiedLabel?: string
  /** Accessible label override; falls back to the idle `label`. */
  ariaLabel?: string
}

/**
 * Small copy-to-clipboard button with a transient "Copied" flash. Shared across the admin
 * invite surfaces (bulk results, resend dialog, share menu). The flash timer is cleared on
 * unmount so we never setState on an unmounted node.
 */
export default function CopyLinkButton({
  link,
  label = 'Copy link',
  copiedLabel = 'Copied',
  ariaLabel,
}: CopyLinkButtonProps) {
  const [copied, setCopied] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current)
  }, [])

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(link)
      setCopied(true)
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label={ariaLabel ?? label}
      className="inline-flex items-center gap-1 rounded-md border border-border-light bg-panel-light px-2 py-1 text-xs font-medium text-text-secondary-light transition-colors hover:bg-brand-weak dark:border-white/10 dark:bg-panel-dark dark:text-text-secondary-dark dark:hover:bg-white/5"
    >
      <CopyIcon className="h-3.5 w-3.5" />
      {copied ? copiedLabel : label}
    </button>
  )
}
