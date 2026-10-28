'use client'

import { useState } from 'react'
import { CONTACT_ADDRESSES, contactMailto } from '@/lib/contactAddresses'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import { CircleNotchIcon, ShieldWarningIcon, TrashIcon } from '@/lib/icons'
import { getCurrentUserSafe, deleteUserAccount } from '@/features/auth/api/auth-api'
import AddressText from '@/features/auth/components/AddressText'
import { Button, Card, Input, Notice, buttonVariants } from '@/components/ui'
import { queryKeys } from '@/lib/queryKeys'

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
    queryKey: queryKeys.currentUser(),
    queryFn: getCurrentUserSafe,
    retry: false,
    enabled: !deleteMutation.isSuccess,
  })

  // Gate on the confirmation phrase only — the Button's `loading` state (below) already refuses
  // activation while the mutation is pending, so folding `isPending` into `disabled` here would just
  // swap the DS loading look for the dimmed disabled look.
  const canDelete = confirmText.trim().toLowerCase() === CONFIRM_PHRASE

  return (
    // The gutter gives way under enlarged text as the legal pages' does (lib/legalPageLayout.ts): narrower than 13em of
    // the layout's query container, a phone under 200% text, it is px-2, 16px a side where px-4 doubled to 32px, so the
    // signed-in card keeps room for its destructive button (E231).
    <main className="mx-auto max-w-2xl px-4 py-12 sm:px-6 lg:px-8 [@container(max-width:13em)]:px-2">
      <h1 className="text-3xl font-semibold text-text-primary-light dark:text-text-primary-dark">Delete your account</h1>
      <p className="mt-3 text-text-secondary-light dark:text-text-secondary-dark">
        This permanently deletes your EarningsNerd account and its associated application records.
        <strong className="font-semibold"> This action cannot be undone.</strong>
      </p>

      <Card as="section" className="mt-6 p-cap-6">
        <h2 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">What gets deleted</h2>
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-text-secondary-light dark:text-text-secondary-dark">
          <li>Your profile (name, email) and login credentials</li>
          <li>Your watchlists, saved summaries, notes, and search history</li>
          <li>Your notification preferences and usage records</li>
        </ul>
        <p className="mt-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">
          Billing, audit and provider records and backup copies can remain, as explained in the{' '}
          <Link href="/privacy" className="text-brand-strong underline dark:text-brand-strong-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">Privacy Policy</Link>. Deleting your account does <strong>not</strong> automatically cancel an active
          subscription billed through the Apple App Store or Google Play. Cancel it in your Apple ID
          or Google Play settings. If you&apos;d like a copy of your data first, you can export it from
          your account settings before deleting.
        </p>
      </Card>

      {/* Success */}
      {deleteMutation.isSuccess ? (
        <Notice
          variant="success"
          className="mt-6"
          title="Your account has been deleted"
          description={
            <>
              Your account and associated application records have been deleted. Some billing, audit and provider records can remain, as explained in the Privacy Policy.
              <Link href="/" className="mt-3 inline-block font-medium text-brand-strong hover:text-brand-emphasis dark:text-brand-strong-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">
                Return to home
              </Link>
            </>
          }
        />
      ) : isLoading ? (
        <div className="mt-6 flex items-center gap-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
          <CircleNotchIcon className="h-4 w-4 animate-spin motion-reduce:animate-none" /> Checking whether you are logged in…
        </div>
      ) : user ? (
        /* Signed in — confirm + delete. Danger emphasis via ring (not a border override): cx is a
           plain class join, so a className `border-error-*` would clash nondeterministically with
           Card's own hairline. */
        <Card as="section" className="mt-6 p-cap-6 ring-1 ring-inset ring-error-light/30 dark:ring-error-dark/30">
          {/* An address has no break opportunity, so under 200% text it ran past the card and the page scrolled
              sideways; it breaks after its @ (AddressText), and break-words breaks a part only where it is longer
              than the line. */}
          <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
            Logged in as <strong className="break-words text-text-primary-light dark:text-text-primary-dark"><AddressText address={user.email} /></strong>.
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
          {/* reserveLoadingText lays the label out in Button's wrapping row (E231): where the label's longest word
              cannot sit beside the trash icon, a phone under 200% text, the icon goes above the label at its own 32px,
              not squeezed beside it. "Deleting…" is shorter than the label, so nothing extra is reserved. */}
          <Button
            variant="destructive"
            onClick={() => deleteMutation.mutate()}
            disabled={!canDelete}
            loading={deleteMutation.isPending}
            loadingText="Deleting…"
            reserveLoadingText="Deleting…"
            leftIcon={<TrashIcon className="h-4 w-4" />}
            className="mt-4"
          >
            Permanently delete my account
          </Button>
          {deleteMutation.isError && (
            <Notice
              variant="error"
              className="mt-4"
              title="Deletion failed"
              description={
                <>
                  Please try again or email{' '}
                  <a href={contactMailto('privacy')} className="underline focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">{CONTACT_ADDRESSES.privacy}</a>.
                </>
              }
            />
          )}
        </Card>
      ) : (
        /* Not signed in — sign-in CTA + email fallback */
        <Card as="section" className="mt-6 p-cap-6">
          <div className="flex items-start gap-3">
            <ShieldWarningIcon className="mt-0.5 h-5 w-5 shrink-0 text-warning-light dark:text-warning-dark" />
            <div>
              <h2 className="font-semibold text-text-primary-light dark:text-text-primary-dark">Log in to delete your account</h2>
              <p className="mt-1 text-sm text-text-secondary-light dark:text-text-secondary-dark">
                For your security, you need to log in before we can delete your account.
              </p>
              <Link
                href="/login?redirect=/delete-account"
                className={buttonVariants({ variant: 'primary', className: 'mt-3' })}
              >
                Log in to continue
              </Link>
              <p className="mt-4 text-sm text-text-secondary-light dark:text-text-secondary-dark">
                Can&apos;t log in? Email{' '}
                <a href={contactMailto('privacy')} className="underline focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">{CONTACT_ADDRESSES.privacy}</a>{' '}
                from your account email address and we&apos;ll process your deletion request.
              </p>
            </div>
          </div>
        </Card>
      )}
    </main>
  )
}
