'use client'

import { useRef } from 'react'
import { ProhibitIcon } from '@/lib/icons'
import { Button, Modal, ModalBody, ModalFooter, ModalHeader } from '@/components/ui'

interface RevokeConfirmModalProps {
  /** The email (or "this invite") being revoked — used in the consequence copy. */
  email: string | null
  isPending: boolean
  onConfirm: () => void
  onClose: () => void
}

/**
 * Confirmation dialog for revoking an invite. Follows the EmailVerificationModal
 * conventions: Escape closes, click-outside closes, and focus returns to the element that
 * opened it — all supplied by ui/Modal (v3, DS-04), which also portals to <body> so the
 * dialog escapes the table's stacking/overflow context. The destructive action is a
 * variant="destructive" <Button>; the dialog stays dismissible.
 */
export default function RevokeConfirmModal({
  email,
  isPending,
  onConfirm,
  onClose,
}: RevokeConfirmModalProps) {
  // Default focus to the (destructive) confirm button so keyboard users can act/escape.
  const confirmRef = useRef<HTMLButtonElement>(null)

  return (
    <Modal open onClose={onClose} labelledBy="revoke-modal-title" size="md" initialFocusRef={confirmRef}>
      <ModalHeader id="revoke-modal-title" onClose={onClose} icon={<ProhibitIcon className="h-5 w-5" />} tone="error">
        Revoke invite
      </ModalHeader>
      <ModalBody>
        <p className="text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
          {email ? (
            <>
              The invite link for{' '}
              <span className="font-medium text-text-primary-light dark:text-text-primary-dark">
                {email}
              </span>{' '}
              will stop working immediately and can&apos;t be undone. You can always send a fresh
              invite later.
            </>
          ) : (
            <>
              This invite link will stop working immediately and can&apos;t be undone. You can
              always send a fresh invite later.
            </>
          )}
        </p>
      </ModalBody>
      <ModalFooter>
        <Button variant="secondary" onClick={onClose} disabled={isPending} className="w-full sm:w-auto">
          Keep invite
        </Button>
        <Button
          ref={confirmRef}
          variant="destructive"
          onClick={onConfirm}
          loading={isPending}
          className="w-full sm:w-auto"
        >
          Revoke invite
        </Button>
      </ModalFooter>
    </Modal>
  )
}
