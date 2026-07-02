'use client'

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import { CircleNotchIcon, KeyIcon, LinkIcon, SignOutIcon, WarningCircleIcon } from '@/lib/icons'
import {
  getConnections,
  unlinkProvider,
  logoutAllSessions,
  type AuthConnection,
} from '@/features/auth/api/auth-api'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { SkeletonText } from '@/components/ui/Skeleton'

const PROVIDER_LABELS: Record<string, string> = { google: 'Google', apple: 'Apple' }

function providerLabel(provider: string): string {
  return PROVIDER_LABELS[provider] ?? provider.charAt(0).toUpperCase() + provider.slice(1)
}

export default function ConnectedAccounts() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const [error, setError] = useState('')

  const { data, isLoading, isError, error: queryError } = useQuery({
    queryKey: ['auth-connections'],
    queryFn: getConnections,
    retry: false,
  })

  const unlinkMutation = useMutation({
    mutationFn: (provider: string) => unlinkProvider(provider),
    onSuccess: () => {
      setError('')
      queryClient.invalidateQueries({ queryKey: ['auth-connections'] })
    },
    onError: (err: unknown) => {
      setError(
        isApiError(err) ? getErrorMessage(err) : 'Could not unlink that sign-in method.',
      )
    },
  })

  const logoutAllMutation = useMutation({
    mutationFn: logoutAllSessions,
    onSuccess: () => {
      queryClient.clear()
      router.push('/login')
    },
    onError: (err: unknown) => {
      setError(
        isApiError(err) ? getErrorMessage(err) : 'Could not sign out of all devices.',
      )
    },
  })

  const providers: AuthConnection[] = data?.providers ?? []
  // The backend refuses to remove the last credential; mirror that in the UI to avoid a
  // pointless request and to explain why unlink is disabled.
  const credentialCount = (data?.has_password ? 1 : 0) + providers.length

  return (
    <Card className="p-6 mb-6">
      <div className="flex items-center gap-3 mb-2">
        <LinkIcon className="h-5 w-5 text-brand-strong dark:text-brand-strong-dark" />
        <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">
          Connected accounts &amp; sessions
        </h2>
      </div>
      <p className="text-text-secondary-light dark:text-text-secondary-dark mb-4">
        Manage how you sign in. You can&apos;t remove your only sign-in method.
      </p>

      {isLoading ? (
        <SkeletonText lines={2} />
      ) : isError ? (
        <div className="flex items-center text-sm text-error-light dark:text-error-dark">
          <WarningCircleIcon className="h-4 w-4 mr-2" />
          {isApiError(queryError) ? getErrorMessage(queryError) : 'Failed to load connected accounts.'}
        </div>
      ) : (
        <div className="space-y-3">
          {/* Password row */}
          <div className="flex items-center justify-between rounded-lg border border-border-light dark:border-border-dark px-4 py-3">
            <div className="flex items-center gap-3">
              <KeyIcon className="h-4 w-4 text-text-tertiary-light dark:text-text-secondary-dark" />
              <span className="text-sm text-text-primary-light dark:text-text-primary-dark">Password</span>
            </div>
            <span className="text-sm text-text-tertiary-light dark:text-text-secondary-dark">
              {data?.has_password ? 'Set' : 'Not set'}
            </span>
          </div>

          {/* Linked providers */}
          {providers.map((p) => {
            const isLast = credentialCount <= 1
            const pending = unlinkMutation.isPending && unlinkMutation.variables === p.provider
            return (
              <div
                key={p.provider}
                className="flex items-center justify-between rounded-lg border border-border-light dark:border-border-dark px-4 py-3"
              >
                <div>
                  <span className="text-sm font-medium text-text-primary-light dark:text-text-primary-dark">
                    {providerLabel(p.provider)}
                  </span>
                  {p.provider_email && (
                    <span className="block text-xs text-text-tertiary-light dark:text-text-secondary-dark">
                      {p.provider_email}
                    </span>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => unlinkMutation.mutate(p.provider)}
                  disabled={isLast || pending}
                  title={isLast ? 'Set a password first so you keep a way to sign in' : undefined}
                  className="text-sm font-medium text-error-light underline-offset-4 hover:underline dark:text-error-dark disabled:opacity-40 disabled:cursor-not-allowed disabled:no-underline"
                >
                  {pending ? 'Unlinking…' : 'Unlink'}
                </button>
              </div>
            )
          })}

          {providers.length === 0 && (
            <p className="text-sm text-text-tertiary-light dark:text-text-secondary-dark">
              No social sign-ins linked.
            </p>
          )}

          {error && (
            <div className="flex items-center text-sm text-error-light dark:text-error-dark">
              <WarningCircleIcon className="h-4 w-4 mr-2" />
              {error}
            </div>
          )}

          {/* Sign out everywhere */}
          <div className="pt-2">
            <Button
              variant="secondary"
              onClick={() => logoutAllMutation.mutate()}
              disabled={logoutAllMutation.isPending}
            >
              {logoutAllMutation.isPending ? (
                <CircleNotchIcon className="h-4 w-4 animate-spin" />
              ) : (
                <SignOutIcon className="h-4 w-4" />
              )}
              Sign out of all devices
            </Button>
          </div>
        </div>
      )}
    </Card>
  )
}
