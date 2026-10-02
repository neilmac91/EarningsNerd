'use client'

import { useRouter } from 'next/navigation'
import { LightningIcon } from '@/lib/icons'
import { Button, Modal, ModalBody, ModalFooter, ModalHeader } from '@/components/ui'

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
 *
 * v3 (DS-04): rebuilt on ui/Modal — the old hand-rolled shell had no focus trap, no Escape
 * handling, a close ✕ without a focus ring, a one-off black/50 scrim, and sat at z-50
 * (BELOW the z-60 popovers). Modal supplies trap/Escape/focus-return/scroll-lock and the
 * overlay + z-modal tokens; actions are real <Button>s. Icon: Lightning — sparkle is reserved
 * for AI-generated-content markers (icon-split rule), and a paywall is commerce, not AI.
 */
export default function UpgradeModal({ open, onClose, feature, title, message }: UpgradeModalProps) {
  const router = useRouter()

  const heading = title ?? 'Upgrade to Pro'
  const body =
    message ??
    (feature
      ? `${feature} is a Pro feature. Pro includes unlimited summaries, hourly filing alerts, 8-K alerts, Multi-Period Analysis, and exports.`
      : 'Pro includes unlimited summaries, hourly filing alerts, 8-K alerts, Multi-Period Analysis, and exports.')

  return (
    <Modal open={open} onClose={onClose} labelledBy="upgrade-modal-title" size="md">
      <ModalHeader id="upgrade-modal-title" onClose={onClose} icon={<LightningIcon className="h-5 w-5" />}>
        {heading}
      </ModalHeader>
      <ModalBody>
        <p className="text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">{body}</p>
      </ModalBody>
      <ModalFooter>
        <Button variant="secondary" onClick={onClose} className="w-full sm:w-auto">
          Not now
        </Button>
        <Button onClick={() => router.push('/pricing')} className="w-full sm:w-auto">
          See plans
        </Button>
      </ModalFooter>
    </Modal>
  )
}
