'use client'

import { useState } from 'react'
import { LinkIcon, PaperPlaneTiltIcon } from '@/lib/icons'
import { Button, Modal, ModalBody, ModalFooter, ModalHeader, cx } from '@/components/ui'
import CopyLinkButton from '@/features/admin/components/CopyLinkButton'
import ShareInvite from '@/features/admin/components/ShareInvite'

interface ResendShareModalProps {
  /** The freshly-minted invite link. */
  link: string
  /** The email the new invite is bound to (null for a link-only invite). */
  email: string | null
  /** The API's `emailed` flag: the backend emails a bound invite best-effort, and never a link-only one. */
  emailed: boolean
  onClose: () => void
}

/**
 * Post-resend dialog surfacing the fresh invite link for sharing. Mirrors the
 * RevokeConfirmModal conventions: Escape closes, click-outside closes, and focus
 * returns to the element that opened it — all supplied by ui/Modal (v3, DS-04), which
 * also portals to <body> so the dialog escapes the table's stacking/overflow context.
 *
 * A press of Copy link, or a share sheet that could not open, is said in the dialog's own status line under the row:
 * the page's toast region lies outside the dialog, and aria-modal hides it from VoiceOver, so a toast from in here is
 * never heard there (chief design on #1793). The share options say their own copies in a line of theirs.
 *
 * A press empties the line first (''), so a repeat press is said again. Until the press says its words the line keeps
 * the words it last said, invisible and hidden from the accessibility tree, so it holds its room: emptied, it took its
 * words and its margin with it, and the centred dialog shrank and grew back for a frame, the pressed button with it
 * (chief design on #1793). A share that ends with nothing to say empties it for good (null), room and all.
 */
export default function ResendShareModal({ link, email, emailed, onClose }: ResendShareModalProps) {
  const [status, setStatus] = useState<string | null>(null)
  // The words the line last said, kept as a render-time update of state (React's "storing information from previous
  // renders"), so they are there in the render that empties the line, and dropped with it for good.
  const [held, setHeld] = useState('')
  if (status && status !== held) setHeld(status)
  if (status === null && held) setHeld('')
  return (
    <Modal open onClose={onClose} labelledBy="resend-share-modal-title" size="md">
      <ModalHeader
        id="resend-share-modal-title"
        onClose={onClose}
        icon={emailed ? <PaperPlaneTiltIcon className="h-5 w-5" /> : <LinkIcon className="h-5 w-5" />}
        tone="success"
      >
        {emailed ? 'Invite re-sent' : 'New invite link ready'}
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
              {emailed && <> We emailed it to {email}.</>}
            </>
          ) : (
            <>A fresh single-use link is ready. The previous link no longer works.</>
          )}
        </p>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <CopyLinkButton link={link} onStatus={setStatus} />
          <ShareInvite link={link} email={email} onStatus={setStatus} />
        </div>
        {/* Always in place, so the line is a live region before a press fills it; empty before a first press, it takes no
            room. */}
        <p
          role="status"
          className={cx('text-sm text-text-secondary-light dark:text-text-secondary-dark', held && 'mt-3')}
        >
          {status || (held && <span aria-hidden="true" className="invisible">{held}</span>)}
        </p>
      </ModalBody>
      <ModalFooter>
        <Button variant="secondary" onClick={onClose} className="w-full">
          Done
        </Button>
      </ModalFooter>
    </Modal>
  )
}
