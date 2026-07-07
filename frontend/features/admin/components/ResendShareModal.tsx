'use client'

import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { PaperPlaneTiltIcon, XIcon } from '@/lib/icons'
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
 * RevokeConfirmModal portal conventions: Escape closes, click-outside closes, and focus
 * returns to the element that opened it. Rendered through a portal so it escapes the table's
 * stacking/overflow context.
 */
export default function ResendShareModal({ link, email, onClose }: ResendShareModalProps) {
  const closeRef = useRef<HTMLButtonElement>(null)
  const previouslyFocused = useRef<HTMLElement | null>(null)

  useEffect(() => {
    previouslyFocused.current = document.activeElement as HTMLElement | null
    closeRef.current?.focus()
    return () => {
      previouslyFocused.current?.focus?.()
    }
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  if (typeof document === 'undefined') return null

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="resend-share-modal-title"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-border-light bg-panel-light p-6 shadow-e4 dark:border-white/10 dark:bg-panel-dark dark:shadow-none"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between">
          <div className="flex h-11 w-11 items-center justify-center rounded-full bg-success-light/10 dark:bg-success-dark/15">
            <PaperPlaneTiltIcon className="h-5 w-5 text-success-light dark:text-success-dark" />
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded p-1 text-text-tertiary-light transition-colors hover:bg-black/5 dark:text-text-secondary-dark dark:hover:bg-white/5"
          >
            <XIcon className="h-5 w-5" />
          </button>
        </div>

        <h2
          id="resend-share-modal-title"
          className="mt-4 text-lg font-semibold text-text-primary-light dark:text-text-primary-dark"
        >
          Invite re-sent. Share the new link
        </h2>
        <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
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

        <div className="mt-6">
          <button
            type="button"
            onClick={onClose}
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border-light bg-transparent px-4 py-2.5 text-sm font-medium text-text-primary-light transition hover:bg-black/5 dark:border-white/10 dark:text-text-primary-dark dark:hover:bg-white/5"
          >
            Done
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
