'use client'

import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Loader2, User as UserIcon } from 'lucide-react'
import { getCurrentUser, updateProfile } from '@/features/auth/api/auth-api'
import { isApiError, getErrorMessage } from '@/lib/api/types'

export default function ProfileForm() {
  const queryClient = useQueryClient()
  const { data: user } = useQuery({ queryKey: ['user'], queryFn: getCurrentUser, retry: false })

  const [name, setName] = useState('')
  // Seed the input once the user loads (and whenever the canonical value changes).
  useEffect(() => {
    setName(user?.full_name ?? '')
  }, [user?.full_name])

  const mutation = useMutation({
    mutationFn: () => updateProfile(name.trim() || null),
    onSuccess: (updated) => {
      queryClient.setQueryData(['user'], updated)
      queryClient.invalidateQueries({ queryKey: ['current-user'] })
    },
  })

  const dirty = (user?.full_name ?? '') !== name.trim()

  return (
    <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 p-6 mb-6">
      <div className="flex items-center gap-3 mb-4">
        <UserIcon className="h-5 w-5 text-blue-600" />
        <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Profile</h2>
      </div>

      <div className="space-y-4">
        <div>
          <label className="text-sm text-slate-600 dark:text-slate-400">Email</label>
          <p className="text-slate-900 dark:text-white font-medium">{user?.email ?? '—'}</p>
        </div>

        <div>
          <label htmlFor="full_name" className="block text-sm text-slate-600 dark:text-slate-400 mb-1">
            Display name
          </label>
          <input
            id="full_name"
            type="text"
            value={name}
            maxLength={100}
            onChange={(e) => setName(e.target.value)}
            placeholder="Your name"
            className="w-full max-w-md px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => mutation.mutate()}
            disabled={!dirty || mutation.isPending}
            className="inline-flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {mutation.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
            Save changes
          </button>
          {mutation.isSuccess && !dirty && (
            <span className="inline-flex items-center text-sm text-green-600 dark:text-green-400">
              <CheckCircle2 className="h-4 w-4 mr-1" /> Saved
            </span>
          )}
        </div>

        {mutation.isError && (
          <p className="text-sm text-red-600 dark:text-red-400">
            {isApiError(mutation.error) ? getErrorMessage(mutation.error) : 'Could not save your profile.'}
          </p>
        )}
      </div>
    </div>
  )
}
