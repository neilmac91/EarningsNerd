'use client'

import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircleIcon, UserIcon } from '@/lib/icons'
import { getCurrentUserSafe, updateProfile } from '@/features/auth/api/auth-api'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import { Button, primaryUnavailableClass } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Card } from '@/components/ui/Card'
import { queryKeys } from '@/lib/queryKeys'

export default function ProfileForm() {
  const queryClient = useQueryClient()
  const { data: user } = useQuery({ queryKey: queryKeys.currentUser(), queryFn: getCurrentUserSafe, retry: false })

  const [name, setName] = useState('')
  // Seed the input once the user loads (and whenever the canonical value changes).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- seeds the input from server-loaded user data; deliberate sync of the canonical full_name into editable form state
    setName(user?.full_name ?? '')
  }, [user?.full_name])

  const mutation = useMutation({
    mutationFn: () => updateProfile(name.trim() || null),
    onSuccess: () => {
      // A profile mutation may finish after logout/login. Let the fenced /me query resolve
      // the current identity instead of publishing the mutation's earlier account response.
      // Returned so Save stays `loading` until the refetched name makes the form clean; otherwise
      // the focused, still-dirty button turns active in between and a second Enter re-sends.
      return queryClient.invalidateQueries({ queryKey: queryKeys.currentUser() })
    },
  })

  const dirty = (user?.full_name ?? '') !== name.trim()

  return (
    <Card className="p-6 mb-6">
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
          {/* aria-disabled + an early return, never native `disabled`: Save holds focus while its
              request is in flight AND when the refetched name makes the form clean (!dirty) right
              after a save. A focused button that turns disabled is blurred to <body> in Chromium. */}
          <Button
            type="button"
            onClick={() => {
              if (!dirty) return
              mutation.mutate()
            }}
            loading={mutation.isPending}
            aria-disabled={!dirty || mutation.isPending || undefined}
            className={!dirty && !mutation.isPending ? primaryUnavailableClass : undefined}
          >
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
    </Card>
  )
}
