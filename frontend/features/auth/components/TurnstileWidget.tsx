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

/** How long a load may take before the widget says it did not load: a stalled request fires no event at all. */
const SCRIPT_LOAD_TIMEOUT_MS = 15_000

/**
 * Loads Cloudflare's script, or waits on the load in flight. The turnstile-script query is its one caller, so it
 * runs once a page, and again on the notice's Try again. A load fails on the element's error, on a load that leaves
 * no Turnstile global (a content blocker can answer with an empty stand-in) and after SCRIPT_LOAD_TIMEOUT_MS. A
 * failed load removes its element: it fires no second event, so a later call that waited on it would wait with no
 * end, as every call after a failure once did (a kept rejection answered them all for the page's life). A removed
 * element that loads late still sets the global, which the next call then finds.
 */
function loadTurnstileScript(): Promise<void> {
  if (typeof window === 'undefined' || window.turnstile) return Promise.resolve()
  return new Promise<void>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(
      'script[src^="https://challenges.cloudflare.com/turnstile"]',
    )
    const script = existing ?? document.createElement('script')
    let timer: ReturnType<typeof setTimeout> | undefined
    const settle = (failure?: string) => {
      clearTimeout(timer)
      if (!failure) {
        resolve()
        return
      }
      script.remove()
      reject(new Error(failure))
    }
    timer = setTimeout(() => settle('Turnstile took too long to load'), SCRIPT_LOAD_TIMEOUT_MS)
    script.addEventListener(
      'load',
      () => settle(window.turnstile ? undefined : 'Turnstile loaded without its global'),
      { once: true },
    )
    script.addEventListener('error', () => settle('Turnstile failed to load'), { once: true })
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
 * blocker, a lost connection, a request that stalls), the widget says so in place, with a Try again that loads it
 * afresh (E152).
 */
export default function TurnstileWidget({ onToken, className }: TurnstileWidgetProps) {
  if (!TURNSTILE_SITE_KEY) return null
  return <TurnstileChallenge onToken={onToken} className={className} />
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
    // Offline too: the default mode would pause the load, with no element and no notice until the connection came
    // back. Offline, the load fails into the notice, and a reconnect loads it again on its own, which this mode
    // turns off unless asked (query-core defaults refetchOnReconnect to networkMode !== 'always').
    networkMode: 'always',
    refetchOnReconnect: true,
  })
  const failure = useRetainedFailure(script, queryKeys.turnstileScript())
  const loaded = script.isSuccess

  useEffect(() => {
    const turnstile = window.turnstile
    if (!loaded || !containerRef.current || !turnstile) return
    let widgetId: string
    try {
      widgetId = turnstile.render(containerRef.current, {
        sitekey: TURNSTILE_SITE_KEY,
        callback: (token: string) => onTokenRef.current(token),
        'error-callback': () => onTokenRef.current(''),
        'expired-callback': () => onTokenRef.current(''),
      })
    } catch {
      // A render that throws leaves no widget and no token, never an error boundary in place of the whole form.
      return
    }
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
        // form's own notices do, until a Notice sets its own alignment (E120).
        className="text-left"
        title="The security check didn't load"
        // The domain may break only at its dots: under 200% text at 320px it is wider than the notice's text.
        description={
          <>
            This form needs Cloudflare&apos;s check before it can send. Allow challenges.<wbr />cloudflare.<wbr />com
            in your content blocker, or check your connection, then try again.
          </>
        }
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
