'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import { Bell, Loader2, Lock } from 'lucide-react'
import {
  getNotificationPreferences,
  updateNotificationPreferences,
  NotificationPreferences,
  NotificationPreferencesUpdate,
} from '@/features/notifications/api/notifications-api'

type BoolPref = 'notify_10k' | 'notify_10q' | 'notify_8k' | 'realtime'

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
          <span className="text-sm font-medium text-slate-900 dark:text-white">{label}</span>
          {locked && (
            <Link
              href="/pricing"
              className="inline-flex items-center gap-1 rounded-full bg-mint-100 px-2 py-0.5 text-[11px] font-semibold text-mint-800 dark:bg-mint-900/30 dark:text-mint-300"
            >
              <Lock className="h-3 w-3" />
              Pro
            </Link>
          )}
        </div>
        <p className="text-sm text-slate-500 dark:text-slate-400">{description}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`relative mt-1 inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
          checked ? 'bg-mint-500' : 'bg-slate-300 dark:bg-slate-600'
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
    queryKey: ['notification-preferences'],
    queryFn: getNotificationPreferences,
    retry: false,
  })

  const mutation = useMutation({
    mutationFn: updateNotificationPreferences,
    onSuccess: (updated) => {
      // The server returns the coerced/effective prefs — trust them as the source of truth.
      queryClient.setQueryData(['notification-preferences'], updated)
    },
  })

  const save = (update: NotificationPreferencesUpdate) => mutation.mutate(update)
  const setBool = (field: BoolPref) => (next: boolean) => save({ [field]: next })

  return (
    <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 p-6 mb-6">
      <div className="flex items-center justify-between mb-2">
        <h2 className="flex items-center gap-2 text-xl font-semibold text-slate-900 dark:text-white">
          <Bell className="h-5 w-5 text-mint-600 dark:text-mint-400" />
          Filing Alerts
        </h2>
        {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin text-slate-400" />}
      </div>
      <p className="text-slate-600 dark:text-slate-400 mb-4">
        Get notified when companies on your watchlist file with the SEC.
      </p>

      {isLoading ? (
        <div className="flex justify-center py-6">
          <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
        </div>
      ) : isError || !prefs ? (
        <p className="text-sm text-red-600 dark:text-red-400">
          Couldn&apos;t load your alert preferences. Please refresh.
        </p>
      ) : (
        <PreferenceRows prefs={prefs} setBool={setBool} save={save} disabled={mutation.isPending} />
      )}

      {mutation.isError && (
        <p className="mt-3 text-sm text-red-600 dark:text-red-400">
          Couldn&apos;t save that change. Please try again.
        </p>
      )}
    </div>
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
    <div className="divide-y divide-slate-100 dark:divide-slate-700">
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
        label="Real-time alerts"
        description="Get alerted the moment a filing lands, instead of in the daily digest."
        checked={prefs.realtime}
        disabled={disabled || !prefs.realtime_available}
        locked={!prefs.realtime_available}
        onChange={setBool('realtime')}
      />

      <div className="flex items-center justify-between gap-4 py-3">
        <div className="flex-1">
          <span className="text-sm font-medium text-slate-900 dark:text-white">Digest frequency</span>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            How often to batch non-real-time alerts.
          </p>
        </div>
        <select
          value={prefs.digest}
          disabled={disabled}
          onChange={(e) => save({ digest: e.target.value })}
          className="rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-1.5 text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-mint-500 focus:border-transparent disabled:opacity-50"
        >
          <option value="immediate">Immediate</option>
          <option value="daily">Daily</option>
          <option value="weekly">Weekly</option>
        </select>
      </div>
    </div>
  )
}
