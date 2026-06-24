'use client'

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import { CheckCircleIcon, CircleNotchIcon, ShieldWarningIcon, TrashIcon, WarningCircleIcon } from '@/lib/icons'
import { getCurrentUserSafe, deleteUserAccount } from '@/features/auth/api/auth-api'
import { buttonVariants } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'

const CONFIRM_PHRASE = 'delete my account'

/**
 * Public web account-deletion page.
 *
 * Satisfies the Google Play account-deletion policy (a web URL where users can request deletion of
 * their account and associated data, reachable even without the app installed) and provides a
 * discoverable web entry point for the same flow Apple requires in-app. Signed-in users can delete
 * directly; everyone else gets a sign-in path and an email fallback.
 */
export default function DeleteAccountPage() {
  const queryClient = useQueryClient()
  const [confirmText, setConfirmText] = useState('')

  const deleteMutation = useMutation({
    mutationFn: deleteUserAccount,
    onSuccess: () => {
      queryClient.clear()
    },
  })

  // Once the account is deleted, stop querying the (now-gone) user so clearing the cache doesn't
  // fire an immediate redundant /api/auth/me request that would just 401.
  const { data: user, isLoading } = useQuery({
    queryKey: ['user'],
    queryFn: getCurrentUserSafe,
    retry: false,
    enabled: !deleteMutation.isSuccess,
  })

  const canDelete = confirmText.trim().toLowerCase() === CONFIRM_PHRASE && !deleteMutation.isPending

  return (
    <main className="mx-auto max-w-2xl px-4 py-12 sm:px-6 lg:px-8">
      <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Delete your account</h1>
      <p className="mt-3 text-slate-600 dark:text-slate-400">
        This permanently deletes your EarningsNerd account and the personal data associated with it.
        <strong className="font-semibold"> This action cannot be undone.</strong>
      </p>

      <section className="mt-6 rounded-lg border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">What gets deleted</h2>
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-600 dark:text-slate-400">
          <li>Your profile (name, email) and login credentials</li>
          <li>Your watchlists, saved summaries, notes, and search history</li>
          <li>Your notification preferences and usage records</li>
        </ul>
        <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">
          Some records may be retained where the law requires it (e.g. billing records for tax
          purposes). Deleting your account does <strong>not</strong> automatically cancel an active
          subscription billed through the Apple App Store or Google Play — cancel it in your Apple ID
          or Google Play settings. If you&apos;d like a copy of your data first, you can export it from
          your account settings before deleting.
        </p>
      </section>

      {/* Success */}
      {deleteMutation.isSuccess ? (
        <section className="mt-6 rounded-lg border border-green-200 bg-green-50 p-6 dark:border-green-900 dark:bg-green-950/30">
          <div className="flex items-start gap-3">
            <CheckCircleIcon className="mt-0.5 h-5 w-5 shrink-0 text-green-600 dark:text-green-400" />
            <div>
              <h2 className="font-semibold text-green-800 dark:text-green-300">
                Your account has been deleted
              </h2>
              <p className="mt-1 text-sm text-green-700 dark:text-green-400">
                Your account and associated personal data have been permanently deleted.
              </p>
              <Link href="/" className="mt-3 inline-block text-sm font-medium text-brand-strong hover:text-brand-light dark:text-brand-strong-dark">
                Return to home
              </Link>
            </div>
          </div>
        </section>
      ) : isLoading ? (
        <div className="mt-6 flex items-center gap-2 text-sm text-slate-500">
          <CircleNotchIcon className="h-4 w-4 animate-spin" /> Checking your sign-in status…
        </div>
      ) : user ? (
        /* Signed in — confirm + delete */
        <section className="mt-6 rounded-lg border border-red-200 bg-white p-6 shadow-sm dark:border-red-900 dark:bg-slate-800">
          <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
            Signed in as <strong className="text-text-primary-light dark:text-text-primary-dark">{user.email}</strong>.
            To confirm, type <strong>{CONFIRM_PHRASE}</strong> below.
          </p>
          <Input
            type="text"
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            placeholder={CONFIRM_PHRASE}
            aria-label={`Type "${CONFIRM_PHRASE}" to confirm`}
            autoComplete="off"
            className="mt-3 text-sm"
          />
          <button
            onClick={() => deleteMutation.mutate()}
            disabled={!canDelete}
            className="mt-4 inline-flex items-center rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {deleteMutation.isPending ? (
              <>
                <CircleNotchIcon className="mr-2 h-4 w-4 animate-spin" /> Deleting…
              </>
            ) : (
              <>
                <TrashIcon className="mr-2 h-4 w-4" /> Permanently delete my account
              </>
            )}
          </button>
          {deleteMutation.isError && (
            <div className="mt-4 flex items-center gap-2 text-sm text-red-600 dark:text-red-400">
              <WarningCircleIcon className="h-4 w-4" /> Deletion failed. Please try again or email{' '}
              <a href="mailto:privacy@earningsnerd.io" className="underline">privacy@earningsnerd.io</a>.
            </div>
          )}
        </section>
      ) : (
        /* Not signed in — sign-in CTA + email fallback */
        <section className="mt-6 rounded-lg border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <div className="flex items-start gap-3">
            <ShieldWarningIcon className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
            <div>
              <h2 className="font-semibold text-slate-900 dark:text-white">Sign in to delete your account</h2>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                For your security, you need to sign in before we can delete your account.
              </p>
              <Link
                href="/login?redirect=/delete-account"
                className={`${buttonVariants({ variant: 'primary' })} mt-3`}
              >
                Sign in to continue
              </Link>
              <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">
                Can&apos;t sign in? Email{' '}
                <a href="mailto:privacy@earningsnerd.io" className="underline">privacy@earningsnerd.io</a>{' '}
                from your account email address and we&apos;ll process your deletion request.
              </p>
            </div>
          </div>
        </section>
      )}
    </main>
  )
}
