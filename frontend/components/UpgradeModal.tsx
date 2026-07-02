'use client'

import { createPortal } from 'react-dom'
import { useRouter } from 'next/navigation'
import { SparkleIcon, XIcon } from '@/lib/icons'

interface UpgradeModalProps {
  open: boolean
  onClose: () => void
  /** Short feature name, e.g. "PDF export" — used in the default copy. */
  feature?: string
  title?: string
  message?: string
}

/**
 * Contextual upgrade prompt. Render it when a user hits a Pro-gated action (export click,
 * monthly limit reached, 8-K toggle, …). Keeps paywall copy + the route-to-pricing action in one
 * place so every trigger looks and behaves consistently.
 */
export default function UpgradeModal({ open, onClose, feature, title, message }: UpgradeModalProps) {
  const router = useRouter()
  if (!open || typeof document === 'undefined') return null

  const heading = title ?? 'Upgrade to Pro'
  const body =
    message ??
    (feature
      ? `${feature} is a Pro feature. Upgrade for unlimited access, real-time alerts, 8-K coverage, comparisons and exports.`
      : 'Unlock unlimited summaries, real-time filing alerts, 8-K coverage, multi-year comparisons and exports.')

  // Portal to <body> so the fixed overlay is never clipped or mis-stacked by an ancestor's stacking
  // context (e.g. when opened from the embedded Copilot rail inside FilingWorkspace).
  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={heading}
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-md rounded-2xl border border-border-light bg-background-light p-6 shadow-xl dark:border-border-dark dark:bg-background-dark"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="absolute right-4 top-4 text-text-tertiary-light transition hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:text-text-primary-dark"
        >
          <XIcon className="h-5 w-5" />
        </button>

        <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-full bg-brand-strong/10 dark:bg-brand-dark/15 text-brand-strong dark:text-brand-strong-dark">
          <SparkleIcon className="h-5 w-5" />
        </div>

        <h2 className="text-xl font-bold text-text-primary-light dark:text-text-primary-dark">{heading}</h2>
        <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">{body}</p>

        <div className="mt-6 flex flex-col gap-2 sm:flex-row">
          <button
            type="button"
            onClick={() => router.push('/pricing')}
            className="flex-1 rounded-lg bg-brand text-white hover:bg-brand-strong active:bg-brand-emphasis dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark px-4 py-2.5 text-sm font-semibold transition active:scale-[0.99]"
          >
            See plans
          </button>
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-lg border border-border-light bg-transparent px-4 py-2.5 text-sm font-medium text-text-primary-light transition hover:bg-panel-light dark:border-border-dark dark:text-text-primary-dark dark:hover:bg-panel-dark"
          >
            Not now
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
