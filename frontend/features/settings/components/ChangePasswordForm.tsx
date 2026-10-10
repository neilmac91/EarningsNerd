'use client'

import { queryKeys } from '@/lib/queryKeys'
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircleIcon, KeyIcon } from '@/lib/icons'
import { changePassword, getConnections } from '@/features/auth/api/auth-api'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import { Button, primaryUnavailableClass } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Card } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'

const MIN_LENGTH = 12

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

  const mutation = useMutation({
    mutationFn: () => changePassword(hasPassword ? current : null, next),
    onSuccess: () => {
      setCurrent('')
      setNext('')
      setConfirm('')
      setClientError('')
      queryClient.invalidateQueries({ queryKey: queryKeys.authConnections() })
    },
  })

  const submit = () => {
    setClientError('')
    if (next.length < MIN_LENGTH) {
      setClientError(`New password must be at least ${MIN_LENGTH} characters.`)
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
      <Card className="p-6 mb-6">
        {/* Form-shaped bones (heading + two fields) hold the same footprint the
            spinner card reserved via min-h, so resolve doesn't shift content. */}
        <div role="status" aria-label="Loading password form" className="min-h-[200px] space-y-4">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-10 max-w-md" />
          <Skeleton className="h-10 max-w-md" />
          <span className="sr-only">Loading…</span>
        </div>
      </Card>
    )
  }

  return (
    <Card className="p-6 mb-6">
      <div className="flex items-center gap-3 mb-2">
        <KeyIcon className="h-5 w-5 text-brand-strong dark:text-brand-strong-dark" />
        <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">
          {hasPassword ? 'Change password' : 'Set a password'}
        </h2>
      </div>
      <p className="text-text-secondary-light dark:text-text-secondary-dark mb-4">
        {hasPassword
          ? 'Update the password you use to sign in with email.'
          : 'Set a password to sign in with email, in addition to your linked social accounts.'}
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

        <div className="flex items-center gap-3">
          {/* aria-disabled, never native `disabled`: the button holds focus while its request is in
              flight AND when a successful save clears the fields (incomplete) right after. A focused
              button that turns disabled is blurred to <body> in Chromium. */}
          <Button
            type="submit"
            loading={mutation.isPending}
            aria-disabled={mutation.isPending || incomplete || undefined}
            className={incomplete && !mutation.isPending ? primaryUnavailableClass : undefined}
          >
            {hasPassword ? 'Update password' : 'Set password'}
          </Button>
          {mutation.isSuccess && (
            <span className="inline-flex items-center text-sm text-success-light dark:text-success-dark">
              <CheckCircleIcon className="h-4 w-4 mr-1" /> Password saved
            </span>
          )}
        </div>

        {(clientError || mutation.isError) && (
          <p className="text-sm text-error-light dark:text-error-dark">
            {clientError ||
              (isApiError(mutation.error) ? getErrorMessage(mutation.error) : 'Could not update your password.')}
          </p>
        )}
      </form>
    </Card>
  )
}
