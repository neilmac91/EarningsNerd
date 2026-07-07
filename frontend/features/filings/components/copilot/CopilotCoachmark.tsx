'use client'

import type { CSSProperties } from 'react'
import { SparkleIcon, XIcon } from '@/lib/icons'
import { Button } from '@/components/ui'

interface CopilotCoachmarkProps {
  /** Opens the Copilot rail (also marks the coachmark seen via the parent's `open` effect). */
  onTry: () => void
  /** Dismisses + persists "seen" so it never shows again. */
  onDismiss: () => void
  /** Anchors the card above the launcher (safe-area aware). */
  style?: CSSProperties
}

/**
 * One-time, contextual nudge anchored above the "Ask this Filing" launcher, shown the first time a
 * user reaches a filing summary (NN/g: a coachmark earns its place only to signal a genuinely new /
 * non-obvious affordance, fired at a contextual moment — not a launch-time tour). Purely
 * presentational: the parent owns the once-only / persisted visibility. Entrance motion is gated
 * behind `motion-safe` so it's silent under prefers-reduced-motion (WCAG 2.3.3).
 */
export default function CopilotCoachmark({ onTry, onDismiss, style }: CopilotCoachmarkProps) {
  return (
    <div
      role="status"
      style={style}
      className="fixed z-40 w-[min(20rem,calc(100vw-2.5rem))] rounded-2xl border border-border-light bg-panel-light p-3.5 shadow-e4 ring-1 ring-black/5 dark:border-white/10 dark:bg-panel-dark dark:shadow-none dark:ring-white/10 motion-safe:animate-fade-up"
    >
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss"
        className="absolute right-2 top-2 rounded-lg p-1 text-text-secondary-light hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:text-text-primary-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
      >
        <XIcon className="h-4 w-4" />
      </button>
      <div className="flex items-start gap-2 pr-5">
        <SparkleIcon className="mt-0.5 h-4 w-4 shrink-0 text-brand-strong dark:text-brand-strong-dark" aria-hidden="true" />
        <div>
          <p className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">
            New: ask this filing anything
          </p>
          <p className="mt-0.5 text-xs text-text-secondary-light dark:text-text-secondary-dark">
            Get plain-English answers, each cited to the exact filing text.
          </p>
          <Button size="sm" className="mt-2" onClick={onTry} leftIcon={<SparkleIcon className="h-3.5 w-3.5" aria-hidden="true" />}>
            Try it
          </Button>
        </div>
      </div>
    </div>
  )
}
