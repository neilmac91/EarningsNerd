'use client'

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, KeyRound, Loader2 } from 'lucide-react'
import { changePassword, getConnections } from '@/features/auth/api/auth-api'
import { isApiError, getErrorMessage } from '@/lib/api/types'

const MIN_LENGTH = 12

export default function ChangePasswordForm() {
  const queryClient = useQueryClient()
  // Shares the cache with ConnectedAccounts (same key) — one fetch, and invalidating it after a
  // successful set flips that component's "Password: Not set" → "Set".
  const { data: connections, isLoading: connectionsLoading } = useQuery({
    queryKey: ['auth-connections'],
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
      queryClient.invalidateQueries({ queryKey: ['auth-connections'] })
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

  const inputCls =
    'w-full max-w-md px-3 py-2 rounded-lg border border-border-light dark:border-border-dark bg-panel-light dark:bg-background-dark text-text-primary-light dark:text-text-primary-dark focus:ring-2 focus:ring-brand-light focus:border-transparent'

  // Wait for connections so we know whether to show the "Current password" field — otherwise it
  // would flash in for OAuth-only users (who default to hasPassword=true) before disappearing.
  if (connectionsLoading) {
    return (
      <div className="bg-panel-light dark:bg-panel-dark rounded-lg shadow-sm border border-border-light dark:border-border-dark p-6 mb-6 flex items-center justify-center min-h-[200px]">
        <Loader2 className="h-6 w-6 animate-spin text-brand-strong dark:text-brand-strong-dark" />
      </div>
    )
  }

  return (
    <div className="bg-panel-light dark:bg-panel-dark rounded-lg shadow-sm border border-border-light dark:border-border-dark p-6 mb-6">
      <div className="flex items-center gap-3 mb-2">
        <KeyRound className="h-5 w-5 text-brand-strong dark:text-brand-strong-dark" />
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
          submit()
        }}
      >
        {hasPassword && (
          <div>
            <label htmlFor="current_pw" className="block text-sm text-text-secondary-light dark:text-text-secondary-dark mb-1">
              Current password
            </label>
            <input
              id="current_pw"
              type="password"
              autoComplete="current-password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              className={inputCls}
            />
          </div>
        )}

        <div>
          <label htmlFor="new_pw" className="block text-sm text-text-secondary-light dark:text-text-secondary-dark mb-1">
            New password
          </label>
          <input
            id="new_pw"
            type="password"
            autoComplete="new-password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            className={inputCls}
          />
        </div>

        <div>
          <label htmlFor="confirm_pw" className="block text-sm text-text-secondary-light dark:text-text-secondary-dark mb-1">
            Confirm new password
          </label>
          <input
            id="confirm_pw"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            className={inputCls}
          />
        </div>

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={mutation.isPending || !next || !confirm || (hasPassword && !current)}
            className="inline-flex items-center px-4 py-2 bg-brand-strong hover:bg-brand-light text-white dark:bg-brand-dark dark:text-background-dark rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {mutation.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
            {hasPassword ? 'Update password' : 'Set password'}
          </button>
          {mutation.isSuccess && (
            <span className="inline-flex items-center text-sm text-success-light dark:text-success-dark">
              <CheckCircle2 className="h-4 w-4 mr-1" /> Password saved
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
    </div>
  )
}
