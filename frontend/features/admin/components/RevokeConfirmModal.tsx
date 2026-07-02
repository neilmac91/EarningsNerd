'use client'

import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { CircleNotchIcon, ProhibitIcon, XIcon } from '@/lib/icons'

interface RevokeConfirmModalProps {
  /** The email (or "this invite") being revoked — used in the consequence copy. */
  email: string | null
  isPending: boolean
  onConfirm: () => void
  onClose: () => void
}

/**
 * Confirmation dialog for revoking an invite. Follows the EmailVerificationModal portal
 * conventions: Escape closes, click-outside closes, and focus returns to the element that
 * opened it. Rendered through a portal so it escapes the table's stacking/overflow context.
 */
export default function RevokeConfirmModal({
  email,
  isPending,
  onConfirm,
  onClose,
}: RevokeConfirmModalProps) {
  const confirmRef = useRef<HTMLButtonElement>(null)
  const previouslyFocused = useRef<HTMLElement | null>(null)

  useEffect(() => {
    previouslyFocused.current = document.activeElement as HTMLElement | null
    // Default focus to the (destructive) confirm button so keyboard users can act/escape.
    confirmRef.current?.focus()
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
      aria-labelledby="revoke-modal-title"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-border-light bg-panel-light p-6 shadow-xl dark:border-white/10 dark:bg-panel-dark dark:shadow-none"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between">
          <div className="flex h-11 w-11 items-center justify-center rounded-full bg-error-light/10 dark:bg-error-dark/15">
            <ProhibitIcon className="h-5 w-5 text-error-light dark:text-error-dark" />
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded p-1 text-text-tertiary-light transition-colors hover:bg-black/5 dark:text-text-secondary-dark dark:hover:bg-white/5"
          >
            <XIcon className="h-5 w-5" />
          </button>
        </div>

        <h2
          id="revoke-modal-title"
          className="mt-4 text-lg font-bold text-text-primary-light dark:text-text-primary-dark"
        >
          Revoke invite
        </h2>
        <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
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

        <div className="mt-6 flex flex-col gap-2 sm:flex-row-reverse">
          <button
            ref={confirmRef}
            type="button"
            onClick={onConfirm}
            disabled={isPending}
            className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg bg-error-light px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-error-emphasis disabled:opacity-50 dark:bg-error-dark"
          >
            {isPending && <CircleNotchIcon className="h-4 w-4 animate-spin" />}
            Revoke invite
          </button>
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg border border-border-light bg-transparent px-4 py-2.5 text-sm font-medium text-text-primary-light transition hover:bg-black/5 disabled:opacity-50 dark:border-white/10 dark:text-text-primary-dark dark:hover:bg-white/5"
          >
            Keep invite
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
