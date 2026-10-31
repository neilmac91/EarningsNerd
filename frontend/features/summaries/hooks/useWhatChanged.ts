'use client'

import { useEffect, useRef } from 'react'
import { hashKey, useQuery, useQueryClient } from '@tanstack/react-query'
import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import { getWhatChanged, type ChangeReport } from '@/features/summaries/api/summaries-api'
import { useRetainedFailure } from '@/hooks/useRetainedFailure'
import { queryKeys } from '@/lib/queryKeys'

export const WHAT_CHANGED_STALE_MS = 10 * 60 * 1000

/**
 * The change report as the viewer in front of it is served. The read differs by viewer: a Pro reader
 * gets every Item 1A wording change, everyone else the counts and the first items (the teaser), so
 * the key carries the signed-in reader's id (not /me's Pro flag, a mirror the entitlements can
 * outrun) and anonymous readers share one entry: the one the filing page seeds from its anonymous
 * server read. The seed is installed on that entry before /me settles, so the section is in the
 * first render for everyone; a signed-in reader's own entry starts empty and the seed stands in as
 * placeholder data while their read runs, so only the content swaps, in place. Should that read
 * fail, the seed stays as the report (placeholder data applies only while a read is pending), held
 * provisional, so the section keeps its place and no event is counted against the seed.
 *
 * A Pro reader whose access token has expired is served the teaser, not a 401 (the endpoint reads
 * the user optionally), so nothing in that response would trigger the client's token refresh. The
 * read waits for /me instead: /me refreshes the token, resolves the reader, and the read goes out
 * with the fresh token under the reader's own key. That holds for a cold /me and for a cached /me
 * being re-read on this mount alike (the read waits while /me is fetching). A cached /me still
 * fresh makes no request, so a token that expired since its last read goes out unrefreshed; a Pro
 * reader served the teaser then has /me re-read (which refreshes the token) and the report re-read,
 * once per entry, so a second teaser stands. A failed /me counts as anonymous, so the section never
 * waits on it.
 */
export function useWhatChanged(filingId: number, initialReport?: ChangeReport) {
  const queryClient = useQueryClient()
  const {
    data: currentUser,
    isError: authFailed,
    isFetching: meFetching,
  } = useQuery({
    queryKey: queryKeys.currentUser(),
    queryFn: getCurrentUserSafe,
    retry: false,
  })
  // undefined while /me is unresolved; null for anonymous and for a failed read; the reader's id.
  const viewer: number | null | undefined =
    currentUser === undefined ? (authFailed ? null : undefined) : (currentUser?.id ?? null)
  const settled = viewer !== undefined
  const key = queryKeys.whatChanged.byViewer(filingId, viewer ?? null)
  const query = useQuery({
    queryKey: key,
    queryFn: () => getWhatChanged(filingId),
    staleTime: WHAT_CHANGED_STALE_MS,
    // Not before /me resolved the reader, and not while /me is being re-read: that request is the
    // one that refreshes an expired token, and the read must carry the refreshed one.
    enabled: settled && !meFetching,
    // The anonymous entry (the key while /me is unresolved, and the anonymous reader's own) takes
    // the seed as its fresh data. A signed-in reader's entry starts empty, so the seed never holds
    // the teaser there for ten minutes.
    initialData: typeof viewer === 'number' ? undefined : initialReport,
    placeholderData: (previous) => previous ?? initialReport,
  })
  // A signed-in reader's own read failed: the seed stays on the page in its place.
  const fallback = query.data === undefined && query.isError ? initialReport : undefined
  const report = query.data ?? fallback
  // The report on the page is the anonymous seed standing in for a signed-in reader's own read.
  const provisional = !settled || query.isPlaceholderData || fallback !== undefined
  // A failed read held in place for the surfaces that show one (the Compare periods card), keyed by
  // this read's own key, as the rule-12 gate on useRetainedFailure callers requires.
  const failure = useRetainedFailure(query, key)

  // A Pro reader served the teaser (their own read, not the seed): the token /me last carried has
  // expired since. /me is re-read, which refreshes it, then the report; once per entry.
  const teaserForPro =
    typeof viewer === 'number' &&
    currentUser?.is_pro === true &&
    !query.isPlaceholderData &&
    query.data?.section_changes?.access === 'teaser'
  const keyHash = hashKey(key)
  const reconciled = useRef<string | null>(null)
  useEffect(() => {
    if (!teaserForPro || reconciled.current === keyHash) return
    reconciled.current = keyHash
    const own = queryKeys.whatChanged.byViewer(filingId, viewer ?? null)
    void queryClient
      .refetchQueries({ queryKey: queryKeys.currentUser() })
      .then(() => queryClient.refetchQueries({ queryKey: own }))
  }, [teaserForPro, keyHash, filingId, viewer, queryClient])

  return { query, key, viewer, settled, provisional, report, failure }
}
