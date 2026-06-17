'use client'

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import { AlertCircle, KeyRound, Link2, Loader2, LogOut } from 'lucide-react'
import {
  getConnections,
  unlinkProvider,
  logoutAllSessions,
  type AuthConnection,
} from '@/features/auth/api/auth-api'
import { isApiError, getErrorMessage } from '@/lib/api/types'

const PROVIDER_LABELS: Record<string, string> = { google: 'Google', apple: 'Apple' }

function providerLabel(provider: string): string {
  return PROVIDER_LABELS[provider] ?? provider.charAt(0).toUpperCase() + provider.slice(1)
}

export default function ConnectedAccounts() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const [error, setError] = useState('')

  const { data, isLoading } = useQuery({
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
  })

  const providers: AuthConnection[] = data?.providers ?? []
  // The backend refuses to remove the last credential; mirror that in the UI to avoid a
  // pointless request and to explain why unlink is disabled.
  const credentialCount = (data?.has_password ? 1 : 0) + providers.length

  return (
    <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 p-6 mb-6">
      <div className="flex items-center gap-3 mb-2">
        <Link2 className="h-5 w-5 text-blue-600" />
        <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
          Connected accounts &amp; sessions
        </h2>
      </div>
      <p className="text-slate-600 dark:text-slate-400 mb-4">
        Manage how you sign in. You can&apos;t remove your only sign-in method.
      </p>

      {isLoading ? (
        <div className="flex items-center text-slate-500 dark:text-slate-400">
          <Loader2 className="h-4 w-4 mr-2 animate-spin" /> Loading…
        </div>
      ) : (
        <div className="space-y-3">
          {/* Password row */}
          <div className="flex items-center justify-between rounded-lg border border-slate-200 dark:border-slate-700 px-4 py-3">
            <div className="flex items-center gap-3">
              <KeyRound className="h-4 w-4 text-slate-500" />
              <span className="text-sm text-slate-900 dark:text-white">Password</span>
            </div>
            <span className="text-sm text-slate-500 dark:text-slate-400">
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
                className="flex items-center justify-between rounded-lg border border-slate-200 dark:border-slate-700 px-4 py-3"
              >
                <div>
                  <span className="text-sm font-medium text-slate-900 dark:text-white">
                    {providerLabel(p.provider)}
                  </span>
                  {p.provider_email && (
                    <span className="block text-xs text-slate-500 dark:text-slate-400">
                      {p.provider_email}
                    </span>
                  )}
                </div>
                <button
                  onClick={() => unlinkMutation.mutate(p.provider)}
                  disabled={isLast || pending}
                  title={isLast ? 'Set a password first so you keep a way to sign in' : undefined}
                  className="text-sm font-medium text-red-600 hover:text-red-700 dark:text-red-400 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {pending ? 'Unlinking…' : 'Unlink'}
                </button>
              </div>
            )
          })}

          {providers.length === 0 && (
            <p className="text-sm text-slate-500 dark:text-slate-400">
              No social sign-ins linked.
            </p>
          )}

          {error && (
            <div className="flex items-center text-sm text-red-600 dark:text-red-400">
              <AlertCircle className="h-4 w-4 mr-2" />
              {error}
            </div>
          )}

          {/* Sign out everywhere */}
          <div className="pt-2">
            <button
              onClick={() => logoutAllMutation.mutate()}
              disabled={logoutAllMutation.isPending}
              className="inline-flex items-center px-4 py-2 bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-900 dark:text-white rounded-lg transition-colors disabled:opacity-50"
            >
              {logoutAllMutation.isPending ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <LogOut className="h-4 w-4 mr-2" />
              )}
              Sign out of all devices
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
