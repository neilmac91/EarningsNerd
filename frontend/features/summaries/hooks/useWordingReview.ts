'use client'

import { useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getWordingReview,
  setWordingLabel,
  type WordingLabel,
  type WordingReviewState,
} from '@/features/summaries/api/summaries-api'
import { useRetainedFailure } from '@/hooks/useRetainedFailure'
import { getSessionGeneration, isSessionGenerationCurrent } from '@/lib/api/session'
import { queryKeys } from '@/lib/queryKeys'

export const WORDING_REVIEW_STALE_MS = 60 * 1000

export interface UseWordingReviewOptions {
  /** Read only with the full change list in front of a signed-in reader (Pro). */
  enabled: boolean
  /** A label the server accepted. */
  onLabeled?: (itemId: string, label: WordingLabel | null) => void
  /** The label that completed the queue: the server has just frozen the receipt. */
  onCompleted?: (state: WordingReviewState) => void
}

function recount(labels: Record<string, WordingLabel>, total: number): WordingReviewState['counts'] {
  const values = Object.values(labels)
  const reviewed = values.filter((label) => label === 'reviewed').length
  return { reviewed, follow_up: values.length - reviewed, unlabeled: Math.max(total - values.length, 0) }
}

/**
 * The signed-in Pro reader's review of a filing's wording changes: the labels they have set, the
 * progress and, once every change is labelled, the frozen receipt. A label is applied to the cache
 * at once (the row flips as the key is pressed) and replaced by the server's state when it answers,
 * or rolled back when it does not. Labels are sent one at a time per review (the mutation's scope),
 * so each answer lands in press order and never over a later press. The server alone decides
 * completion: the receipt and the completion time never come from the client, and the completion
 * event fires on the transition the server reports (`completed_now`), so it counts once however
 * the answers land. A label that settles after the reader logged out or another account signed in
 * (the session generation moved on) writes nothing back: `resetAccountQueries` removes the family,
 * and a late answer must not repopulate it for the next account. A failed read is held for the
 * error UI (`failure`, with RetryButton); a read that finds nothing to review (`unavailable`: the
 * comparison the block shows is gone, or the feature is off) has the block re-read against the
 * live state.
 */
export function useWordingReview(filingId: number, { enabled, onLabeled, onCompleted }: UseWordingReviewOptions) {
  const queryClient = useQueryClient()
  const key = queryKeys.wordingReview.byFiling(filingId)
  const query = useQuery({
    queryKey: key,
    queryFn: () => getWordingReview(filingId),
    enabled,
    staleTime: WORDING_REVIEW_STALE_MS,
  })
  const failure = useRetainedFailure(query, key)
  const data = query.data
  const unavailable = data?.status === 'unavailable'
  useEffect(() => {
    // The block in front of the reader is the older read (its entry stays fresh for ten minutes).
    if (unavailable) void queryClient.invalidateQueries({ queryKey: queryKeys.whatChanged.all() })
  }, [unavailable, queryClient])
  const mutation = useMutation({
    mutationFn: ({ itemId, label }: { itemId: string; label: WordingLabel | null }) => setWordingLabel(filingId, itemId, label),
    scope: { id: `wording-review-${filingId}` },
    onMutate: async ({ itemId, label }) => {
      // The account the label belongs to: an answer that lands after the generation moved on is
      // another account's problem no longer, and is not written into its cache.
      const generation = getSessionGeneration()
      await queryClient.cancelQueries({ queryKey: key })
      const previous = queryClient.getQueryData<WordingReviewState>(key)
      if (previous && previous.status === 'ok') {
        const labels = { ...previous.labels }
        if (label === null) delete labels[itemId]
        else labels[itemId] = label
        // Each write names its registry key in place: the account-query ownership gate
        // (tests/unit/accountQueryState.spec.tsx) inventories every cache writer by that text.
        queryClient.setQueryData<WordingReviewState>(queryKeys.wordingReview.byFiling(filingId), {
          ...previous,
          labels,
          counts: recount(labels, previous.items_total),
        })
      }
      return { previous, generation }
    },
    onError: (_error, _variables, context) => {
      if (!context || !isSessionGenerationCurrent(context.generation)) return
      if (context.previous) queryClient.setQueryData(queryKeys.wordingReview.byFiling(filingId), context.previous)
    },
    onSuccess: (state, { itemId, label }, context) => {
      if (!context || !isSessionGenerationCurrent(context.generation)) return
      queryClient.setQueryData(queryKeys.wordingReview.byFiling(filingId), state)
      onLabeled?.(itemId, label)
      if (state.completed_now) onCompleted?.(state)
    },
  })
  return {
    query,
    key,
    /** The review while it is readable; undefined before the read settles, when it failed or found nothing. */
    state: data && data.status === 'ok' ? data : undefined,
    /** The read failed (held through its retries): show the error UI with a RetryButton over it. */
    failure,
    /** The server has nothing to review for this filing. */
    unavailable,
    setLabel: (itemId: string, label: WordingLabel | null) => mutation.mutate({ itemId, label }),
    saving: mutation.isPending,
  }
}
