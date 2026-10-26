'use client'

import { queryKeys } from '@/lib/queryKeys'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { clsx } from 'clsx'
import Link from 'next/link'
import { CircleNotchIcon, LockSimpleIcon } from '@/lib/icons'
import {
  getNotificationPreferences,
  updateNotificationPreferences,
  NotificationPreferences,
  NotificationPreferencesUpdate,
} from '@/features/notifications/api/notifications-api'
import { Card } from '@/components/ui/Card'
import { SkeletonText } from '@/components/ui/Skeleton'
import { Switch } from '@/components/ui/Switch'

type BoolPref = 'notify_10k' | 'notify_10q' | 'notify_8k' | 'notify_20f' | 'notify_6k' | 'realtime'

function Toggle({
  checked,
  busy,
  disabled,
  onChange,
  label,
  description,
  locked,
}: {
  checked: boolean
  /** A save is in flight: aria-disabled + aria-busy + an early return, so the switch keeps focus. */
  busy: boolean
  /** Not available on this plan: native disabled (server-set; never flipped by this switch). */
  disabled?: boolean
  onChange: (next: boolean) => void
  label: string
  description: string
  locked?: boolean
}) {
  return (
    // The label column keeps 10rem beside the switch or the switch takes the next line, so at 200% text
    // on a phone it sits under the label instead of hanging past the card (and the column is not
    // crushed to a word a line). At the default size the row is unchanged.
    <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 py-3">
      <div className="grow basis-40">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-text-primary-light dark:text-text-primary-dark">{label}</span>
          {locked && (
            <Link
              href="/pricing"
              className="focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark inline-flex items-center gap-1 rounded-full bg-brand-strong px-2 py-0.5 text-xs font-semibold text-white dark:bg-brand-dark dark:text-background-dark"
            >
              <LockSimpleIcon className="h-3 w-3" />
              Pro
            </Link>
          )}
        </div>
        <p className="text-sm text-text-tertiary-light dark:text-text-tertiary-dark">{description}</p>
      </div>
      {/* Busy fades only the track; the shared switch's focus ring remains opaque.
          Plan-locked switches retain native disabled because their own press cannot flip that state. */}
      <Switch
        checked={checked}
        aria-label={label}
        disabled={disabled}
        aria-disabled={(busy && !disabled) || undefined}
        aria-busy={busy || undefined}
        onCheckedChange={(next) => {
          if (busy) return
          onChange(next)
        }}
        className={clsx(
          'mt-1 aria-disabled:cursor-not-allowed',
          checked
            ? 'aria-disabled:bg-brand-strong/50 dark:aria-disabled:bg-brand-dark/50'
            : 'aria-disabled:bg-border-light/50 dark:aria-disabled:bg-white/[0.075]',
        )}
      />
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
    <Card className="p-cap-6 mb-6">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">Filing alerts</h2>
        {mutation.isPending && <CircleNotchIcon className="h-4 w-4 animate-spin motion-reduce:animate-none text-text-tertiary-light dark:text-text-tertiary-dark" />}
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
        <PreferenceRows prefs={prefs} setBool={setBool} busy={mutation.isPending} />
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
  busy,
}: {
  prefs: NotificationPreferences
  setBool: (field: BoolPref) => (next: boolean) => void
  busy: boolean
}) {
  return (
    <div className="divide-y divide-border-light dark:divide-border-dark">
      <Toggle
        label="Annual reports (10-K)"
        description="Yearly comprehensive filings."
        checked={prefs.notify_10k}
        busy={busy}
        onChange={setBool('notify_10k')}
      />
      <Toggle
        label="Quarterly reports (10-Q)"
        description="Quarterly financial updates."
        checked={prefs.notify_10q}
        busy={busy}
        onChange={setBool('notify_10q')}
      />
      <Toggle
        label="Material events (8-K)"
        description="Current reports on material events."
        checked={prefs.notify_8k}
        busy={busy}
        disabled={!prefs.eightk_available}
        locked={!prefs.eightk_available}
        onChange={setBool('notify_8k')}
      />
      <Toggle
        label="Foreign annual reports (20-F)"
        description="Annual reports from foreign issuers (20-F / 40-F)."
        checked={prefs.notify_20f}
        busy={busy}
        onChange={setBool('notify_20f')}
      />
      <Toggle
        label="Foreign interim reports (6-K)"
        description="Interim updates from foreign issuers, delivered in your digest rather than in real time."
        checked={prefs.notify_6k}
        busy={busy}
        onChange={setBool('notify_6k')}
      />
      <Toggle
        label="Real-time alerts"
        description="An email from the hourly filing check, instead of the daily digest."
        checked={prefs.realtime}
        busy={busy}
        disabled={!prefs.realtime_available}
        locked={!prefs.realtime_available}
        onChange={setBool('realtime')}
      />

      {/* The daily digest job sends once a day for everyone and reads no frequency setting, so this row
          states the cadence instead of offering a choice no job honours. A choice comes back only with
          a reader in the backend (tests/unit/notificationPreferencesConsumed.spec.ts). The cadence is the
          row's value, set in the data face as the filing identity sets its facts, so it reads as a stated
          fact rather than a label that lost its control. Its row is the switches' row, so at 200% text the
          value sits under the description as a switch does. */}
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 py-3">
        <div className="grow basis-40">
          <span className="text-sm font-medium text-text-primary-light dark:text-text-primary-dark">Digest</span>
          <p className="text-sm text-text-tertiary-light dark:text-text-tertiary-dark">
            Alerts that aren&apos;t real-time arrive in one email a day.
          </p>
        </div>
        <span className="font-data text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">Daily</span>
      </div>
    </div>
  )
}
