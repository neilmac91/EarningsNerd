'use client'

import { useEffect, useRef, useState } from 'react'
import type { UseQueryResult } from '@tanstack/react-query'

/**
 * A failed query stays failed, with its last error, while a Retry the user pressed runs. React Query
 * puts a query that has no data back to `pending` (`error: null`) the moment it refetches; reading
 * that as recovered unmounted the error UI (pricing's Notice, the dashboard's error card and plan
 * strip), and the focused Retry button in it, before the button's `loading` rendered, so focus fell to
 * <body>. Only that press holds the failure: any other refetch of an errored query (a new observer
 * mounting, window focus) shows the ordinary pending state, as before.
 */
export function useRetainedFailure(query: UseQueryResult<unknown>) {
  const { isError, error, isFetching, data, refetch } = query
  const [lastError, setLastError] = useState<unknown>(null)
  if (error && error !== lastError) setLastError(error)
  const [retrying, setRetrying] = useState(false)
  // The press's own fetch may not be visible yet on the render right after it, so the retry ends
  // only once a fetch has been seen and has finished.
  const sawFetch = useRef(false)
  useEffect(() => {
    if (!retrying) return
    if (isFetching) sawFetch.current = true
    else if (sawFetch.current) {
      sawFetch.current = false
      setRetrying(false)
    }
  }, [retrying, isFetching])
  const retry = () => {
    sawFetch.current = false
    setRetrying(true)
    void refetch()
  }
  const failed = isError || (retrying && data === undefined)
  return { failed, error: failed ? error ?? lastError : null, retry }
}
