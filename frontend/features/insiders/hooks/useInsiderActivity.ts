'use client'

import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import { getInsiderActivity, type InsiderActivityResponse } from '@/features/insiders/api/insiders-api'
import { useRetainedFailure } from '@/hooks/useRetainedFailure'
import { ApiError } from '@/lib/api/client'
import { queryKeys } from '@/lib/queryKeys'

/** A scan under way says when asking again can show more (`scan.retry_after_seconds`). A surface asks again then, never
 *  sooner than this floor, and for at most POLL_LIMIT_MS from its mount, so a scan that is slow or paused does not keep
 *  a page open asking for good (ADR 0009, decision 7). */
const POLL_FLOOR_MS = 5_000
const POLL_LIMIT_MS = 3 * 60_000

/** 401 (signed out), 403 (not a beta account) and 404 (the endpoint switched off, or a company it does not know): the
 *  answer is not for this reader here, so a surface shows no error for it. */
export const isInsiderRefusal = (error: unknown): boolean =>
  error instanceof ApiError && [401, 403, 404].includes(error.status)

/**
 * One company's stored insider (Form 4) activity over a window, for the surfaces that show it: the company page's
 * card and the company's insider page (ADR 0009). Both read through this hook and the same query key, so the page
 * opens from the card's answer.
 *
 * Only a beta account asks: the reader comes from the page's own read of /me (the same query, so no request of its
 * own), and signed out, still loading or not beta the hook asks nothing. A foreign private issuer files no Form 4s,
 * so it is never asked about either; while that is unknown (`isFpi` undefined) the query waits.
 *
 * A scan under way is followed by polling at the interval the answer gives, for three minutes from the mount,
 * whatever the window and whether the first answer came from a request or from the cache. The component that calls
 * the hook is keyed by ticker (the insider page's panel; the company page's card), so another company is
 * another mount and starts its own three minutes. After them `stopped` is true and the surface says how to see more.
 */
export function useInsiderActivity(ticker: string, windowDays: number, isFpi: boolean | undefined) {
  const { data: currentUser } = useQuery({
    queryKey: queryKeys.currentUser(),
    queryFn: getCurrentUserSafe,
    retry: false,
  })
  const isBeta = currentUser?.is_beta === true
  const [startedAt] = useState(() => Date.now())
  const insidersKey = queryKeys.insiders.byWindow(ticker, windowDays)
  const query = useQuery<InsiderActivityResponse>({
    queryKey: insidersKey,
    queryFn: () => getInsiderActivity(ticker, windowDays),
    enabled: !!ticker && isFpi === false && isBeta,
    // A failed read waits for the reader's Try again.
    retry: false,
    // The endpoint answers from the stored scan, at once; a scan under way is followed by the polling below.
    staleTime: 5 * 60 * 1000,
    refetchInterval: (q) => {
      const wait = q.state.data?.scan.retry_after_seconds
      if (q.state.status === 'error' || wait == null) return false
      const delay = Math.max(wait * 1000, POLL_FLOOR_MS)
      return Date.now() + delay - startedAt <= POLL_LIMIT_MS ? delay : false
    },
  })
  const { data } = query
  const failure = useRetainedFailure(query, insidersKey)
  // The three minutes are up: from then the surface asks nothing more by itself, and says so.
  const [stopped, setStopped] = useState(false)
  const pending = data?.scan.retry_after_seconds != null && !failure.failed
  useEffect(() => {
    if (!pending) return
    const timer = setTimeout(() => setStopped(true), Math.max(0, startedAt + POLL_LIMIT_MS - Date.now()))
    return () => clearTimeout(timer)
  }, [pending, startedAt])
  const refused = failure.failed && isInsiderRefusal(failure.error)

  return {
    /** The reader's account state: undefined while /me is still loading, null signed out. */
    currentUser,
    isBeta,
    query,
    data,
    failure,
    /** The failure is a refusal (401, 403, 404), not something a retry helps. */
    refused,
    stopped,
    /** There is something to show: an answer, or a failure a retry can help. False while the first answer is out
     *  and for a refusal, so a surface that waits for it never shows a card to a reader the endpoint refuses. */
    hasContent: !!data || (failure.failed && !refused),
  }
}

/** The net signal of a window's summary: its direction, and its size as dollars where every trade has a value, else
 *  as shares. The sign is the buy/sell signal; the words and a glyph carry it beside the colour. */
export function insiderSignal(summary: InsiderActivityResponse['summary'] | undefined) {
  const value = summary ? (summary.net_value ?? summary.net_shares) : 0
  const isValue = !!summary && summary.net_value !== null
  const direction: 'buy' | 'sell' | 'flat' = value > 0 ? 'buy' : value < 0 ? 'sell' : 'flat'
  return { value, isValue, direction }
}
