'use client'

import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircleIcon, CircleNotchIcon, UserIcon } from '@/lib/icons'
import { getCurrentUser, updateProfile } from '@/features/auth/api/auth-api'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'

export default function ProfileForm() {
  const queryClient = useQueryClient()
  const { data: user } = useQuery({ queryKey: ['user'], queryFn: getCurrentUser, retry: false })

  const [name, setName] = useState('')
  // Seed the input once the user loads (and whenever the canonical value changes).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- seeds the input from server-loaded user data; deliberate sync of the canonical full_name into editable form state
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
    <div className="bg-panel-light dark:bg-panel-dark rounded-lg shadow-sm border border-border-light dark:border-border-dark p-6 mb-6">
      <div className="flex items-center gap-3 mb-4">
        <UserIcon className="h-5 w-5 text-brand-strong dark:text-brand-strong-dark" />
        <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">Profile</h2>
      </div>

      <div className="space-y-4">
        <div>
          <label className="text-sm text-text-secondary-light dark:text-text-secondary-dark">Email</label>
          <p className="text-text-primary-light dark:text-text-primary-dark font-medium">{user?.email ?? '—'}</p>
        </div>

        <div>
          <label htmlFor="full_name" className="block text-sm text-text-secondary-light dark:text-text-secondary-dark mb-1">
            Display name
          </label>
          <Input
            id="full_name"
            type="text"
            value={name}
            maxLength={100}
            onChange={(e) => setName(e.target.value)}
            placeholder="Your name"
            className="max-w-md"
          />
        </div>

        <div className="flex items-center gap-3">
          <Button
            type="button"
            onClick={() => mutation.mutate()}
            disabled={!dirty || mutation.isPending}
          >
            {mutation.isPending ? <CircleNotchIcon className="h-4 w-4 animate-spin" /> : null}
            Save changes
          </Button>
          {mutation.isSuccess && !dirty && (
            <span className="inline-flex items-center text-sm text-success-light dark:text-success-dark">
              <CheckCircleIcon className="h-4 w-4 mr-1" /> Saved
            </span>
          )}
        </div>

        {mutation.isError && (
          <p className="text-sm text-error-light dark:text-error-dark">
            {isApiError(mutation.error) ? getErrorMessage(mutation.error) : 'Could not save your profile.'}
          </p>
        )}
      </div>
    </div>
  )
}
