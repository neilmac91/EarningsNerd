'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { getInvitedCohortAvailable } from '../api/auth-api'

/**
 * Whether the invited-cohort exception is open, for an invitee's register page (`getInvitedCohortAvailable`). It reads
 * on mount when `enabled`, and again on each `recheck`, whose promise is the fresh answer. It fails closed: a failed
 * read closes it, and an answer that a later request or an unmount has superseded neither opens it nor counts as open.
 */
export function useInvitedCohort(enabled: boolean) {
  const [available, setAvailable] = useState(false)
  const [loading, setLoading] = useState(enabled)
  const sequence = useRef(0)
  const controller = useRef<AbortController | null>(null)

  const recheck = useCallback((): Promise<boolean> => {
    if (!enabled) return Promise.resolve(false)
    const request = ++sequence.current
    controller.current?.abort()
    const next = new AbortController()
    controller.current = next
    // Started inside a promise, so even a read that throws as it starts answers closed.
    return Promise.resolve().then(() => getInvitedCohortAvailable(next.signal)).then((open) => {
      if (request !== sequence.current || next.signal.aborted) return false
      setAvailable(open)
      return open
    }).catch(() => {
      if (request === sequence.current && !next.signal.aborted) setAvailable(false)
      return false
    }).finally(() => {
      if (request === sequence.current && !next.signal.aborted) setLoading(false)
    })
  }, [enabled])

  useEffect(() => {
    if (!enabled) return
    void recheck()
    return () => {
      sequence.current += 1
      controller.current?.abort()
    }
  }, [enabled, recheck])

  return { available, loading, recheck }
}
