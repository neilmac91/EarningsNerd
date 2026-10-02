'use client'

import { PaperPlaneTiltIcon } from '@/lib/icons'
import { Button, Modal, ModalBody, ModalFooter, ModalHeader } from '@/components/ui'
import CopyLinkButton from '@/features/admin/components/CopyLinkButton'
import ShareInvite from '@/features/admin/components/ShareInvite'

interface ResendShareModalProps {
  /** The freshly-minted invite link. */
  link: string
  /** The email the new invite is bound to (null for a link-only invite). */
  email: string | null
  onClose: () => void
}

/**
 * Post-resend dialog surfacing the fresh invite link for sharing. Mirrors the
 * RevokeConfirmModal conventions: Escape closes, click-outside closes, and focus
 * returns to the element that opened it — all supplied by ui/Modal (v3, DS-04), which
 * also portals to <body> so the dialog escapes the table's stacking/overflow context.
 */
export default function ResendShareModal({ link, email, onClose }: ResendShareModalProps) {
  return (
    <Modal open onClose={onClose} labelledBy="resend-share-modal-title" size="md">
      <ModalHeader
        id="resend-share-modal-title"
        onClose={onClose}
        icon={<PaperPlaneTiltIcon className="h-5 w-5" />}
        tone="success"
      >
        Invite re-sent. Share the new link
      </ModalHeader>
      <ModalBody>
        <p className="text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
          {email ? (
            <>
              A fresh single-use link for{' '}
              <span className="font-medium text-text-primary-light dark:text-text-primary-dark">
                {email}
              </span>{' '}
              is ready. The previous link no longer works.
            </>
          ) : (
            <>A fresh single-use link is ready. The previous link no longer works.</>
          )}
        </p>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <CopyLinkButton link={link} />
          <ShareInvite link={link} email={email} />
        </div>
      </ModalBody>
      <ModalFooter>
        <Button variant="secondary" onClick={onClose} className="w-full">
          Done
        </Button>
      </ModalFooter>
    </Modal>
  )
}
