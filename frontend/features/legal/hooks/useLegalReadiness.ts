'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { getLegalReadiness, type LegalReadiness } from '../api/legal-api'

/** An error replaces earlier readiness. A late response from an older request cannot reopen a surface. */
export function useLegalReadiness() {
  const [readiness, setReadiness] = useState<LegalReadiness | null>(null)
  const [loading, setLoading] = useState(true)
  const sequence = useRef(0)
  const controller = useRef<AbortController | null>(null)

  const recheck = useCallback((): Promise<LegalReadiness | null> => {
    const request = ++sequence.current
    controller.current?.abort()
    const next = new AbortController()
    controller.current = next
    return getLegalReadiness(next.signal).then((result) => {
      if (request !== sequence.current || next.signal.aborted) return null
      setReadiness(result)
      return result
    }).catch(() => {
      if (request === sequence.current && !next.signal.aborted) setReadiness(null)
      return null
    }).finally(() => {
      if (request === sequence.current && !next.signal.aborted) setLoading(false)
    })
  }, [])

  useEffect(() => {
    void recheck()
    return () => {
      sequence.current += 1
      controller.current?.abort()
    }
  }, [recheck])

  return { readiness, loading, recheck }
}
