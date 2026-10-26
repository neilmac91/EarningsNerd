'use client'

import { useSyncExternalStore } from 'react'
import { formatInstant, formatLocalDate } from '@/lib/format'

/** Nothing to subscribe to: the source date asks only whether it renders in the browser. */
const noSubscription = () => () => {}

/**
 * A run's source date, the one way the analysis page prints it ("October 24, 2026"): the data notes' "Source data as
 * of …" and the results header's "data as of …". `data_as_of` is an instant, the source data's sync time, so it prints
 * as the day it falls on in the reader's zone. The server (the landing renders its demo there) and the hydrating render
 * cannot know that zone, so they print the day the API writes, iso_z's UTC day, which every zone renders alike; React
 * renders again right after hydrating, with the reader's day (useTodayEasternIso's pattern, E136). Suppressing the
 * mismatch kept the server's day instead. An absent or unreadable value gives '' and the caller says so in words.
 * Gate: tests/unit/analysis-source-date.spec.tsx, on both surfaces.
 */
export function useSourceDate(dataAsOf: string | null | undefined): string {
  const inBrowser = useSyncExternalStore(noSubscription, () => true, () => false)
  return inBrowser ? formatInstant(dataAsOf, 'MMMM d, yyyy') : formatLocalDate(dataAsOf, 'MMMM d, yyyy')
}
