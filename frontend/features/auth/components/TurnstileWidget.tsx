'use client'

import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Notice, cx } from '@/components/ui'
import { RetryButton, useRetainedFailure } from '@/hooks/useRetainedFailure'
import { TURNSTILE_SITE_KEY } from '@/lib/featureFlags'
import { queryKeys } from '@/lib/queryKeys'

// Minimal typing for the Cloudflare Turnstile global (explicit-render API).
interface TurnstileApi {
  render: (el: HTMLElement, opts: Record<string, unknown>) => string
  reset: (id?: string) => void
  remove: (id?: string) => void
}

declare global {
  interface Window {
    turnstile?: TurnstileApi
  }
}

const SCRIPT_SRC =
  'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'

/**
 * Loads Cloudflare's script, or waits on the load in flight. The turnstile-script query is its one caller, so it
 * runs once a page, and again on the notice's Try again. A load that fails removes its element: a failed element
 * fires no second event, so a later call that waited on it would wait with no end, as every call after a failure
 * once did (a kept rejection answered them all for the page's life).
 */
function loadTurnstileScript(): Promise<void> {
  if (typeof window === 'undefined' || window.turnstile) return Promise.resolve()
  return new Promise<void>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(
      'script[src^="https://challenges.cloudflare.com/turnstile"]',
    )
    const script = existing ?? document.createElement('script')
    script.addEventListener('load', () => resolve(), { once: true })
    script.addEventListener(
      'error',
      () => {
        script.remove()
        reject(new Error('Turnstile failed to load'))
      },
      { once: true },
    )
    if (existing) return
    script.src = SCRIPT_SRC
    script.async = true
    script.defer = true
    document.head.appendChild(script)
  })
}

interface TurnstileWidgetProps {
  /** Called with the verification token on success, or '' on expiry/error. */
  onToken: (token: string) => void
  className?: string
}

/**
 * Renders the Cloudflare Turnstile widget when NEXT_PUBLIC_TURNSTILE_SITE_KEY is configured; renders nothing
 * otherwise. A form that waits for its token (TURNSTILE_ENABLED) cannot send without one: the backend refuses a
 * missing token and fails open only when siteverify is unreachable. So when the script cannot load (a content
 * blocker, a lost connection), the widget says so in place, with a Try again that loads it afresh (E152).
 */
export default function TurnstileWidget(props: TurnstileWidgetProps) {
  if (!TURNSTILE_SITE_KEY) return null
  return <TurnstileChallenge {...props} />
}

function TurnstileChallenge({ onToken, className }: TurnstileWidgetProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const onTokenRef = useRef(onToken)
  // eslint-disable-next-line react-hooks/refs -- deliberate latch: keep the latest onToken callback for the Turnstile widget's stable render-once effect without re-registering it
  onTokenRef.current = onToken

  // The script's load is a query, so its failure is a Retry like any failed read's (RetryButton over
  // useRetainedFailure, DESIGN_SYSTEM.md §4): the notice stays up, its Retry busy, until a load succeeds.
  const script = useQuery({
    queryKey: queryKeys.turnstileScript(),
    queryFn: async () => {
      await loadTurnstileScript()
      return true
    },
    // A script loads once a page, so a load never goes stale; a failure waits for the reader's Try again, so the
    // notice shows at once rather than after the default retries.
    staleTime: Infinity,
    retry: false,
  })
  const failure = useRetainedFailure(script, queryKeys.turnstileScript())
  const loaded = script.isSuccess

  useEffect(() => {
    const turnstile = window.turnstile
    if (!loaded || !containerRef.current || !turnstile) return
    const widgetId = turnstile.render(containerRef.current, {
      sitekey: TURNSTILE_SITE_KEY,
      callback: (token: string) => onTokenRef.current(token),
      'error-callback': () => onTokenRef.current(''),
      'expired-callback': () => onTokenRef.current(''),
    })
    return () => {
      try {
        turnstile.remove(widgetId)
      } catch {
        // ignore teardown errors
      }
    }
  }, [loaded])

  if (failure.failed) {
    return (
      <Notice
        variant="error"
        // Its text keeps to the start in a column that centres it (the waitlist page below lg), as the waitlist
        // form's own notices do.
        className="text-left"
        title="The security check didn't load"
        description="This form needs Cloudflare's check before it can send. Allow challenges.cloudflare.com in any content blocker, or check your connection, then try again."
        action={<RetryButton size="sm" failures={[failure]} focusTarget={containerRef} />}
      />
    )
  }
  // The Retry's focus target, out of the Tab order: when a Try again loads the script, the notice leaves with its
  // Retry, and focus comes here, where the check renders, rather than falling to <body>.
  return (
    <div
      ref={containerRef}
      role="group"
      aria-label="Security check"
      tabIndex={-1}
      className={cx(className, 'outline-none')}
    />
  )
}
