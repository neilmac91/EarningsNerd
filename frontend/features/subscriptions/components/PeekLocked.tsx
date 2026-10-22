'use client'

import { useState, type ReactNode } from 'react'
import { LockSimpleIcon } from '@/lib/icons'
import UpgradeModal from './UpgradeModal'

interface PeekLockedProps {
  children: ReactNode
  /** Feature name for the upgrade prompt, e.g. "8-K alerts". */
  feature?: string
  /** Short pill text shown over the locked content. Defaults to "Pro". */
  pill?: string
  /** Override the click behaviour (default opens the UpgradeModal). */
  onUpgradeClick?: () => void
}

// An `inert` prop renders under only one of the two Reacts this component meets: the App Router's React 19 reads it
// as a boolean, dropping `''`, and the React 18 the unit tests run drops `true`. So the preview takes the attribute
// from its node, the same under both, until the move to React 19 (E21) makes it a prop.
function makeInert(node: HTMLDivElement | null) {
  node?.setAttribute('inert', '')
}

/**
 * "Peek" paywall: show a real (but non-interactive, blurred) preview of a Pro feature with a
 * lock overlay and an upgrade CTA. Lets free users *see* the value before paying — the conversion
 * pattern from the value thesis. Wrap any gated UI:
 *
 *   <PeekLocked feature="Real-time alerts"><AlertsPanel /></PeekLocked>
 */
export default function PeekLocked({ children, feature, pill = 'Pro', onUpgradeClick }: PeekLockedProps) {
  const [modalOpen, setModalOpen] = useState(false)
  const handleClick = onUpgradeClick ?? (() => setModalOpen(true))

  return (
    <div className="relative overflow-hidden rounded-xl">
      {/* The preview: blurred + dimmed + inert so it can't be interacted with. aria-hidden and
          pointer-events-none leave its controls in the tab order, ahead of the upgrade button; inert
          takes them out. */}
      <div ref={makeInert} aria-hidden className="pointer-events-none select-none blur-sm opacity-60">
        {children}
      </div>

      <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-background-light/40 dark:bg-background-dark/40">
        <span className="inline-flex items-center gap-1 rounded-full bg-brand text-white hover:bg-brand-strong active:bg-brand-emphasis dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark px-3 py-1 text-xs font-semibold">
          <LockSimpleIcon className="h-3 w-3" />
          {pill}
        </span>
        <button
          type="button"
          onClick={handleClick}
          className="rounded-lg bg-brand text-white hover:bg-brand-strong active:bg-brand-emphasis dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark px-4 py-2 text-sm font-semibold shadow-e2 transition active:scale-[0.99]"
        >
          Upgrade to Pro
        </button>
      </div>

      {onUpgradeClick ? null : (
        <UpgradeModal open={modalOpen} onClose={() => setModalOpen(false)} feature={feature} />
      )}
    </div>
  )
}
