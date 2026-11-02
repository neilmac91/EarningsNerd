'use client'

import { queryKeys } from '@/lib/queryKeys'
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { CheckCircleIcon } from '@/lib/icons'
import { changePassword, getConnections, type CurrentUser } from '@/features/auth/api/auth-api'
import { STEP_TOAST_DURATION_MS } from '@/features/auth/lib/accountQueryState'
import { ApiError } from '@/lib/api/client'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import { Button, primaryUnavailableClass } from '@/components/ui/Button'
import { cx } from '@/components/ui/cx'
import { Input } from '@/components/ui/Input'
import { Card } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { PASSWORD_MIN_LENGTH } from '@/lib/passwordRules'

/** What the form tells the reader when the route refused the change for another account (E29 (6)): another tab logged
 * this browser in to that account, so changing its password is not what this tab asked for, and nothing changed. The
 * tab then reads /me and shows that account, whose form replaces this one, so a toast says it, as the logout of every
 * session's refusal does (LOGGED_IN_AS_ANOTHER_MESSAGE, E157 (2)). */
export const PASSWORD_NOT_CHANGED_OTHER_ACCOUNT_MESSAGE =
  "This browser is now logged in to another account, so we didn't change your password. Log in to the account you meant, then try again."

export default function ChangePasswordForm() {
  const queryClient = useQueryClient()
  // Shares the cache with ConnectedAccounts (same key) — one fetch, and invalidating it after a
  // successful set flips that component's "Password: Not set" → "Set".
  const { data: connections, isLoading: connectionsLoading } = useQuery({
    queryKey: queryKeys.authConnections(),
    queryFn: getConnections,
    retry: false,
  })
  const hasPassword = connections?.has_password ?? true

  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [clientError, setClientError] = useState('')

  const clearFields = () => {
    setCurrent('')
    setNext('')
    setConfirm('')
    setClientError('')
  }

  const mutation = useMutation({
    // It names the account this tab shows as the change is asked for, and the route refuses another's (E29 (6)).
    mutationFn: () =>
      changePassword(
        hasPassword ? current : null,
        next,
        queryClient.getQueryData<CurrentUser | null>(queryKeys.currentUser())?.id,
      ),
    onSuccess: () => {
      clearFields()
      queryClient.invalidateQueries({ queryKey: queryKeys.authConnections() })
    },
    onError: (err: unknown) => {
      if (!(err instanceof ApiError && err.status === 409)) return
      // The browser's session is another account's: what was typed here was meant for the account this tab showed, so
      // none of it stays to be posted for the one a read of /me moves this tab to.
      clearFields()
      toast.error(PASSWORD_NOT_CHANGED_OTHER_ACCOUNT_MESSAGE, { duration: STEP_TOAST_DURATION_MS })
      void queryClient.invalidateQueries({ queryKey: queryKeys.currentUser() })
      void queryClient.invalidateQueries({ queryKey: queryKeys.authConnections() })
    },
  })
  // The 409's toast gave the reader its step; an error line would say it again under the other account's form.
  const refusedForAnotherAccount = mutation.error instanceof ApiError && mutation.error.status === 409

  const submit = () => {
    setClientError('')
    if (next.length < PASSWORD_MIN_LENGTH) {
      setClientError(`New password must be at least ${PASSWORD_MIN_LENGTH} characters.`)
      return
    }
    if (next !== confirm) {
      setClientError('New password and confirmation do not match.')
      return
    }
    mutation.mutate()
  }

  const incomplete = !next || !confirm || (hasPassword && !current)

  // Wait for connections so we know whether to show the "Current password" field — otherwise it
  // would flash in for OAuth-only users (who default to hasPassword=true) before disappearing.
  if (connectionsLoading) {
    return (
      <Card className="p-cap-6 mb-6">
        {/* Form-shaped bones (heading + two fields) hold the same footprint the
            spinner card reserved via min-h, so resolve doesn't shift content. */}
        <div role="status" aria-label="Loading password form" className="min-h-[200px] space-y-4">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-11 max-w-md" />
          <Skeleton className="h-11 max-w-md" />
          <span className="sr-only">Loading…</span>
        </div>
      </Card>
    )
  }

  return (
    <Card className="p-cap-6 mb-6">
      <div className="flex items-center gap-3 mb-2">
        <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">
          {hasPassword ? 'Change password' : 'Set a password'}
        </h2>
      </div>
      <p className="text-text-secondary-light dark:text-text-secondary-dark mb-4">
        {hasPassword
          ? 'Update the password you use to log in with email.'
          : 'Set a password to log in with email, in addition to your linked social accounts.'}
      </p>

      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          // The submit button is aria-disabled, not natively disabled, so implicit submission (Enter
          // in a field) still lands here — refuse it while saving or incomplete, as `disabled` did.
          if (mutation.isPending || incomplete) return
          submit()
        }}
      >
        {hasPassword && (
          <div>
            <label htmlFor="current_pw" className="block text-sm text-text-secondary-light dark:text-text-secondary-dark mb-1">
              Current password
            </label>
            <Input
              id="current_pw"
              type="password"
              autoComplete="current-password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              className="max-w-md"
            />
          </div>
        )}

        <div>
          <label htmlFor="new_pw" className="block text-sm text-text-secondary-light dark:text-text-secondary-dark mb-1">
            New password
          </label>
          <Input
            id="new_pw"
            type="password"
            autoComplete="new-password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            className="max-w-md"
          />
        </div>

        <div>
          <label htmlFor="confirm_pw" className="block text-sm text-text-secondary-light dark:text-text-secondary-dark mb-1">
            Confirm new password
          </label>
          <Input
            id="confirm_pw"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            className="max-w-md"
          />
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* aria-disabled, never native `disabled`: the button holds focus while its request is in
              flight AND when a successful save clears the fields (incomplete) right after. A focused
              button that turns disabled is blurred to <body> in Chromium. */}
          <Button
            type="submit"
            wrap
            loading={mutation.isPending}
            aria-disabled={mutation.isPending || incomplete || undefined}
            className={cx('max-w-full', incomplete && !mutation.isPending && primaryUnavailableClass)}
          >
            {hasPassword ? 'Update password' : 'Set password'}
          </Button>
          {mutation.isSuccess && (
            <span className="inline-flex items-center text-sm text-success-light dark:text-success-dark">
              <CheckCircleIcon className="h-4 w-4 mr-1" /> Password saved
            </span>
          )}
        </div>

        {(clientError || (mutation.isError && !refusedForAnotherAccount)) && (
          <p className="text-sm text-error-light dark:text-error-dark">
            {clientError ||
              (isApiError(mutation.error) ? getErrorMessage(mutation.error) : 'Could not update your password.')}
          </p>
        )}
      </form>
    </Card>
  )
}
