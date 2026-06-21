import { getApiUrl } from '@/lib/api/client'

// Idle timeout for the SSE stream. Mirrors STREAM_TIMEOUT_MS in summaries-api.ts: any
// activity (token/progress/heartbeat) resets the clock; only true silence aborts.
const STREAM_TIMEOUT_MS = 120000

// --- Types (mirror the P1 backend contract) ---

export interface CopilotCitation {
  // Numeric for filing-text excerpts ([1], [2]); an "F#" string for tool-provided XBRL figures ([F1]).
  n: number | string
  excerpt: string
  section_ref: string | null
  verified: boolean
  fragment_url: string | null
}

export interface CopilotCompletion {
  answer: string
  citations: CopilotCitation[]
  grounded: number
  kind: 'answer' | 'not_disclosed'
  // 2-3 suggested next questions about this filing, rendered as tappable chips.
  followups: string[]
}

export interface CopilotTurn {
  role: 'user' | 'assistant'
  content: string
}

// A live "show the work" signal emitted as numeric (XBRL) tools run, e.g.
// { label: 'Looking up revenue', phase: 'start' } … { phase: 'done', ok: true }.
export interface CopilotActivity {
  label: string
  phase: 'start' | 'done'
  ok: boolean
}

export interface CopilotHandlers {
  onProgress?: (stage: string) => void
  onActivity?: (activity: CopilotActivity) => void
  onToken: (text: string) => void
  onNotDisclosed: (answer: string) => void
  onComplete: (completion: CopilotCompletion) => void
  onError: (message: string) => void
}

// The question hit a paywall/permission gate (403 / Pro-only / monthly cap). Used by the UI
// to swap the inline Retry button for an Upgrade link, since retrying can't help.
export const isCopilotPaywallError = (message: string): boolean => {
  const m = (message || '').toLowerCase()
  return (
    m.includes('pro feature') ||
    m.includes('upgrade to pro') ||
    m.includes('monthly limit') ||
    m.includes('monthly cap') ||
    m.includes('limit reached')
  )
}

const parseErrorDetail = async (response: Response, fallback: string): Promise<string> => {
  try {
    const data = await response.json()
    if (data?.detail) return typeof data.detail === 'string' ? data.detail : fallback
    if (data?.message) return typeof data.message === 'string' ? data.message : fallback
  } catch {
    // Non-JSON body — fall through to the status-based fallback.
  }
  return fallback
}

/**
 * Stream an answer for "Ask this Filing".
 *
 * Mirrors runStreamAttempt in summaries-api.ts (fetch POST + credentials:'include' +
 * AbortController with an idle resetTimeout, response.body.getReader() + TextDecoder, split on
 * '\n', parse `data:` lines, switch on data.type) — but deliberately simpler: no auto-retry.
 * HTTP errors and AbortError/network failures are surfaced via handlers.onError; the caller
 * shows an inline error bubble (with a Retry button, or an Upgrade link for paywall errors).
 */
export const askFilingStream = async (
  filingId: number,
  question: string,
  history: CopilotTurn[],
  handlers: CopilotHandlers,
  signal?: AbortSignal
): Promise<void> => {
  const apiUrl = getApiUrl()
  const url = `${apiUrl}/api/summaries/filing/${filingId}/ask-stream`

  const controller = new AbortController()
  const onAbort = () => controller.abort()
  // Bridge an externally-provided signal (component unmount / panel close) to our controller.
  if (signal) {
    if (signal.aborted) {
      controller.abort()
    } else {
      signal.addEventListener('abort', onAbort, { once: true })
    }
  }

  let timeoutId: ReturnType<typeof setTimeout> | null = null
  const resetTimeout = () => {
    if (timeoutId) clearTimeout(timeoutId)
    timeoutId = setTimeout(() => controller.abort(), STREAM_TIMEOUT_MS)
  }
  const clearTimeoutSafely = () => {
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
    }
  }

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ question, history }),
      signal: controller.signal,
    })

    if (!response.ok) {
      let errorMessage: string
      if (response.status === 401) {
        errorMessage = 'Sign in to use the Copilot.'
      } else if (response.status === 403) {
        errorMessage = await parseErrorDetail(response, 'This is a Pro feature.')
      } else if (response.status === 429) {
        // Surface the server detail (the monthly cap message) verbatim when present.
        errorMessage = await parseErrorDetail(response, 'Monthly limit reached. Please try again later.')
      } else if (response.status >= 500) {
        errorMessage = await parseErrorDetail(response, 'Server error. Please try again.')
      } else {
        errorMessage = await parseErrorDetail(response, `Request failed with status ${response.status}`)
      }
      handlers.onError(errorMessage)
      return
    }

    const reader = response.body?.getReader()
    if (!reader) {
      handlers.onError('No response stream available.')
      return
    }

    const decoder = new TextDecoder()
    let buffer = ''
    resetTimeout()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      resetTimeout()
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data:')) continue
        const payload = line.slice(line.indexOf(':') + 1).trim()
        if (!payload) continue
        let data: Record<string, unknown>
        try {
          data = JSON.parse(payload)
        } catch (e) {
          console.error('[copilot] failed to parse SSE data:', e)
          continue
        }

        switch (data.type) {
          case 'progress':
            handlers.onProgress?.(typeof data.stage === 'string' ? data.stage : 'reading')
            break
          case 'activity':
            handlers.onActivity?.({
              label: typeof data.label === 'string' ? data.label : '',
              phase: data.phase === 'done' ? 'done' : 'start',
              ok: data.ok !== false,
            })
            break
          case 'token':
            if (typeof data.text === 'string') handlers.onToken(data.text)
            break
          case 'not_disclosed':
            handlers.onNotDisclosed(typeof data.answer === 'string' ? data.answer : '')
            break
          case 'complete':
            handlers.onComplete({
              answer: typeof data.answer === 'string' ? data.answer : '',
              citations: Array.isArray(data.citations) ? (data.citations as CopilotCitation[]) : [],
              grounded: typeof data.grounded === 'number' ? data.grounded : 0,
              kind: data.kind === 'not_disclosed' ? 'not_disclosed' : 'answer',
              followups: Array.isArray(data.followups)
                ? (data.followups as unknown[]).filter((f): f is string => typeof f === 'string')
                : [],
            })
            break
          case 'error':
            handlers.onError(typeof data.message === 'string' ? data.message : 'Something went wrong.')
            break
          default:
            break
        }
      }
    }
  } catch (error: unknown) {
    const errObj = error as { name?: string; message?: string }
    if (errObj?.name === 'AbortError') {
      // Aborted because the caller closed the panel/unmounted: stay quiet. A timeout abort is
      // indistinguishable here, but the user has navigated away either way.
      return
    }
    handlers.onError(errObj?.message || 'Network error. Please check your connection and try again.')
  } finally {
    clearTimeoutSafely()
    // Drop the bridge listener on normal completion (the {once:true} only auto-removes if it fired).
    signal?.removeEventListener('abort', onAbort)
  }
}
