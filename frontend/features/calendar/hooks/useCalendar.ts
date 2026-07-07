'use client'

/* =============================================================================
   Earnings calendar — hooks (features/calendar/hooks/useCalendar.ts)
   -----------------------------------------------------------------------------
   - useCalendarRange: the range query (react-query), keyed on from/to.
   - useViewer: session + plan + current alert subscriptions. The FREE cap is a
     visible product surface (strategy §3.7) so the count is loaded eagerly;
     nothing about the PRO cap exists client-side, by design.
   - useEarningsAlerts: optimistic per-company toggle with honest rollback.
     FREE at-cap enables short-circuit to the upsell (the cap is public and
     deliberate). PRO is NEVER pre-empted: the request is always sent and
     whatever 403 the API returns is rendered verbatim.
============================================================================= */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { hasActiveSession } from '@/lib/api/session'
import { getUsage } from '@/features/subscriptions/api/subscriptions-api'
import { queryKeys } from '@/lib/queryKeys'
import {
  getCalendar,
  getEarningsAlertTickers,
  enableEarningsAlert,
  disableEarningsAlert,
  EarningsAlertError,
  EARNINGS_ALERT_LIMIT_CODE,
  type CalendarRangeResult,
} from '../api/calendar-api'

export const FREE_ALERT_LIMIT = 3

export function useCalendarRange(from: string, to: string) {
  return useQuery<CalendarRangeResult>({
    queryKey: queryKeys.calendar(from, to),
    queryFn: () => getCalendar(from, to),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  })
}

export interface CalendarViewer {
  signedIn: boolean
  isPro: boolean
  alertTickers: Set<string>
  alertCount: number
}

export function useViewer(): CalendarViewer {
  const signedIn = typeof window !== 'undefined' && hasActiveSession()
  const usage = useQuery({ queryKey: queryKeys.usage(), queryFn: getUsage, enabled: signedIn, staleTime: 60_000 })
  const alerts = useQuery({
    queryKey: queryKeys.earningsAlertTickers(),
    queryFn: getEarningsAlertTickers,
    enabled: signedIn,
    staleTime: 60_000,
  })
  const alertTickers = useMemo(() => new Set(alerts.data ?? []), [alerts.data])
  return {
    signedIn,
    isPro: usage.data?.is_pro ?? false,
    alertTickers,
    alertCount: alertTickers.size,
  }
}

export type BlockedKind = 'signin' | 'upsell' | 'error'

export interface BlockedState {
  kind: BlockedKind
  ticker: string
  /** For 'error': the API's message, rendered verbatim. */
  message: string
  /** Bell rect at click time — anchors the popover. */
  anchor: DOMRect
  /** Element to restore focus to on dismiss. */
  trigger: HTMLElement | null
}

export interface EarningsAlertsApi {
  isOn: (ticker: string) => boolean
  isPending: (ticker: string) => boolean
  toggle: (ticker: string, el: HTMLElement) => void
  blocked: BlockedState | null
  clearBlocked: () => void
}

export function useEarningsAlerts(viewer: CalendarViewer): EarningsAlertsApi {
  const queryClient = useQueryClient()
  const [optimistic, setOptimistic] = useState<Record<string, boolean>>({})
  const [pending, setPending] = useState<Record<string, boolean>>({})
  const [blocked, setBlocked] = useState<BlockedState | null>(null)
  const viewerRef = useRef(viewer)
  // Keep the latest viewer in a ref so toggle()/currentCount() (invoked from
  // event handlers, after commit) read fresh state without re-subscribing.
  // Written in an effect, not during render, per react-hooks/refs.
  useEffect(() => {
    viewerRef.current = viewer
  })

  const isOn = useCallback(
    (ticker: string) => optimistic[ticker] ?? viewer.alertTickers.has(ticker),
    [optimistic, viewer.alertTickers],
  )

  const currentCount = useCallback(() => {
    const v = viewerRef.current
    const base = new Set(v.alertTickers)
    for (const [t, on] of Object.entries(optimistic)) {
      if (on) base.add(t)
      else base.delete(t)
    }
    return base.size
  }, [optimistic])

  const mutation = useMutation({
    mutationFn: async ({ ticker, enabling }: { ticker: string; enabling: boolean }) => {
      if (enabling) await enableEarningsAlert(ticker)
      else await disableEarningsAlert(ticker)
    },
    onSettled: (_data, _err, vars) => {
      setPending((p) => {
        const next = { ...p }
        delete next[vars.ticker]
        return next
      })
      queryClient.invalidateQueries({ queryKey: queryKeys.earningsAlertTickers() })
    },
    onError: (err, vars, _ctx) => {
      // Roll the optimistic flip back before surfacing anything.
      setOptimistic((o) => ({ ...o, [vars.ticker]: !vars.enabling }))
      const anchor = vars as unknown as { anchor?: DOMRect; trigger?: HTMLElement }
      const rect = anchor.anchor ?? new DOMRect(window.innerWidth / 2, window.innerHeight / 2, 0, 0)
      if (err instanceof EarningsAlertError && err.code === EARNINGS_ALERT_LIMIT_CODE) {
        setBlocked({ kind: 'upsell', ticker: vars.ticker, message: err.message, anchor: rect, trigger: anchor.trigger ?? null })
      } else {
        const message = err instanceof Error ? err.message : 'Could not update the alert. Try again.'
        setBlocked({ kind: 'error', ticker: vars.ticker, message, anchor: rect, trigger: anchor.trigger ?? null })
      }
    },
  })

  const toggle = useCallback(
    (ticker: string, el: HTMLElement) => {
      const v = viewerRef.current
      const rect = el.getBoundingClientRect()
      if (!v.signedIn) {
        setBlocked({ kind: 'signin', ticker, message: '', anchor: rect, trigger: el })
        return
      }
      if (pending[ticker]) return
      const enabling = !isOn(ticker)
      // FREE cap: a deliberate, visible conversion surface — surface the upsell
      // instead of sending a doomed request. (PRO deliberately has no such check.)
      if (enabling && !v.isPro && currentCount() >= FREE_ALERT_LIMIT) {
        setBlocked({
          kind: 'upsell',
          ticker,
          message: `Free includes earnings alerts for ${FREE_ALERT_LIMIT} companies. Upgrade to Pro for more.`,
          anchor: rect,
          trigger: el,
        })
        return
      }
      setPending((p) => ({ ...p, [ticker]: true }))
      setOptimistic((o) => ({ ...o, [ticker]: enabling }))
      mutation.mutate({ ticker, enabling, anchor: rect, trigger: el } as never)
    },
    [currentCount, isOn, mutation, pending],
  )

  return {
    isOn,
    isPending: (t) => !!pending[t],
    toggle,
    blocked,
    clearBlocked: () => setBlocked(null),
  }
}
