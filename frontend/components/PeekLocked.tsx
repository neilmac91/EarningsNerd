'use client'

import { useState, type ReactNode } from 'react'
import { Lock } from 'lucide-react'
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
      {/* The preview: blurred + dimmed + inert so it can't be interacted with. */}
      <div aria-hidden className="pointer-events-none select-none blur-sm opacity-60">
        {children}
      </div>

      <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-background-light/40 dark:bg-background-dark/40">
        <span className="inline-flex items-center gap-1 rounded-full bg-brand-strong text-white hover:bg-brand-light dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark focus-visible:outline-brand-light px-3 py-1 text-xs font-semibold">
          <Lock className="h-3 w-3" />
          {pill}
        </span>
        <button
          type="button"
          onClick={handleClick}
          className="rounded-lg bg-brand-strong text-white hover:bg-brand-light dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark focus-visible:outline-brand-light px-4 py-2 text-sm font-semibold shadow transition-all active:scale-[0.99]"
        >
          Upgrade to unlock
        </button>
      </div>

      {onUpgradeClick ? null : (
        <UpgradeModal open={modalOpen} onClose={() => setModalOpen(false)} feature={feature} />
      )}
    </div>
  )
}
