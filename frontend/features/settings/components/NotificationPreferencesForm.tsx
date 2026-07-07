'use client'

import { queryKeys } from '@/lib/queryKeys'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { clsx } from 'clsx'
import Link from 'next/link'
import { BellIcon, CircleNotchIcon, LockSimpleIcon } from '@/lib/icons'
import {
  getNotificationPreferences,
  updateNotificationPreferences,
  NotificationPreferences,
  NotificationPreferencesUpdate,
} from '@/features/notifications/api/notifications-api'
import { inputClasses } from '@/components/ui/Input'
import { Card } from '@/components/ui/Card'
import { SkeletonText } from '@/components/ui/Skeleton'

type BoolPref = 'notify_10k' | 'notify_10q' | 'notify_8k' | 'notify_20f' | 'notify_6k' | 'realtime'

function Toggle({
  checked,
  disabled,
  onChange,
  label,
  description,
  locked,
}: {
  checked: boolean
  disabled?: boolean
  onChange: (next: boolean) => void
  label: string
  description: string
  locked?: boolean
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-3">
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-text-primary-light dark:text-text-primary-dark">{label}</span>
          {locked && (
            <Link
              href="/pricing"
              className="inline-flex items-center gap-1 rounded-full bg-brand-strong px-2 py-0.5 text-xs font-semibold text-white dark:bg-brand-dark dark:text-background-dark"
            >
              <LockSimpleIcon className="h-3 w-3" />
              Pro
            </Link>
          )}
        </div>
        <p className="text-sm text-text-tertiary-light dark:text-text-secondary-dark">{description}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`relative mt-1 inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
          checked ? 'bg-brand-strong dark:bg-brand-dark' : 'bg-border-light dark:bg-border-dark'
        }`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
            checked ? 'translate-x-6' : 'translate-x-1'
          }`}
        />
      </button>
    </div>
  )
}

export default function NotificationPreferencesForm() {
  const queryClient = useQueryClient()

  const { data: prefs, isLoading, isError } = useQuery({
    queryKey: queryKeys.notificationPreferences(),
    queryFn: getNotificationPreferences,
    retry: false,
  })

  const mutation = useMutation({
    mutationFn: updateNotificationPreferences,
    onSuccess: (updated) => {
      // The server returns the coerced/effective prefs — trust them as the source of truth.
      queryClient.setQueryData(queryKeys.notificationPreferences(), updated)
    },
  })

  const save = (update: NotificationPreferencesUpdate) => mutation.mutate(update)
  const setBool = (field: BoolPref) => (next: boolean) => save({ [field]: next })

  return (
    <Card className="p-6 mb-6">
      <div className="flex items-center justify-between mb-2">
        <h2 className="flex items-center gap-2 text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">
          <BellIcon className="h-5 w-5 text-brand-strong dark:text-brand-strong-dark" />
          Filing Alerts
        </h2>
        {mutation.isPending && <CircleNotchIcon className="h-4 w-4 animate-spin text-text-tertiary-light dark:text-text-secondary-dark" />}
      </div>
      <p className="text-text-secondary-light dark:text-text-secondary-dark mb-4">
        Get notified when companies on your watchlist file with the SEC.
      </p>

      {isLoading ? (
        <SkeletonText lines={4} className="py-2" />
      ) : isError || !prefs ? (
        <p className="text-sm text-error-light dark:text-error-dark">
          Couldn&apos;t load your alert preferences. Please refresh.
        </p>
      ) : (
        <PreferenceRows prefs={prefs} setBool={setBool} save={save} disabled={mutation.isPending} />
      )}

      {mutation.isError && (
        <p className="mt-3 text-sm text-error-light dark:text-error-dark">
          Couldn&apos;t save that change. Please try again.
        </p>
      )}
    </Card>
  )
}

function PreferenceRows({
  prefs,
  setBool,
  save,
  disabled,
}: {
  prefs: NotificationPreferences
  setBool: (field: BoolPref) => (next: boolean) => void
  save: (update: NotificationPreferencesUpdate) => void
  disabled: boolean
}) {
  return (
    <div className="divide-y divide-border-light dark:divide-border-dark">
      <Toggle
        label="Annual reports (10-K)"
        description="Yearly comprehensive filings."
        checked={prefs.notify_10k}
        disabled={disabled}
        onChange={setBool('notify_10k')}
      />
      <Toggle
        label="Quarterly reports (10-Q)"
        description="Quarterly financial updates."
        checked={prefs.notify_10q}
        disabled={disabled}
        onChange={setBool('notify_10q')}
      />
      <Toggle
        label="Material events (8-K)"
        description="Breaking corporate events as they're filed."
        checked={prefs.notify_8k}
        disabled={disabled || !prefs.eightk_available}
        locked={!prefs.eightk_available}
        onChange={setBool('notify_8k')}
      />
      <Toggle
        label="Foreign annual reports (20-F)"
        description="Annual reports from foreign issuers (20-F / 40-F)."
        checked={prefs.notify_20f}
        disabled={disabled}
        onChange={setBool('notify_20f')}
      />
      <Toggle
        label="Foreign interim reports (6-K)"
        description="Interim updates from foreign issuers, delivered in your digest rather than in real time."
        checked={prefs.notify_6k}
        disabled={disabled}
        onChange={setBool('notify_6k')}
      />
      <Toggle
        label="Real-time alerts"
        description="Get alerted the moment a filing lands, instead of in the daily digest."
        checked={prefs.realtime}
        disabled={disabled || !prefs.realtime_available}
        locked={!prefs.realtime_available}
        onChange={setBool('realtime')}
      />

      <div className="flex items-center justify-between gap-4 py-3">
        <div className="flex-1">
          <span className="text-sm font-medium text-text-primary-light dark:text-text-primary-dark">Digest frequency</span>
          <p className="text-sm text-text-tertiary-light dark:text-text-secondary-dark">
            How often to batch non-real-time alerts.
          </p>
        </div>
        <select
          value={prefs.digest}
          disabled={disabled}
          onChange={(e) => save({ digest: e.target.value })}
          className={clsx(inputClasses(), 'w-auto py-1.5 text-sm')}
        >
          <option value="immediate">Immediate</option>
          <option value="daily">Daily</option>
          <option value="weekly">Weekly</option>
        </select>
      </div>
    </div>
  )
}
