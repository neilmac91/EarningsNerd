import { getApiUrl } from '@/lib/api/client'
import { postStreamWithRefresh } from '@/lib/api/streamRefresh'

// Idle bound covers the initial POST, shared refresh, headers and stream reads.
// Received bytes reset it; candidate prose is held until an admitted completion.
const STREAM_TIMEOUT_MS = 120000

// --- Types (mirror the P1 backend contract) ---

export interface CopilotCitation {
  // The server numbers every citation, figure or passage, in one sequence ([1], [2]); an "F#" string ([F1]) is a
  // legacy id the marker matcher still tolerates, and never makes a citation a figure (isXbrlCitation).
  n: number | string
  excerpt: string
  section_ref: string | null
  verified: boolean
  fragment_url: string | null
  // A filed figure, as the server attests it (parseCompletion): set only when the citation carries the tool fact's own
  // payload (its `concept`, backend/app/services/copilot_tools.py fact_to_citation) and no `value_kind`, which the
  // server sends only for a figure it computed. The server rebuilds a quoted excerpt from its four fields, so a model
  // can write an "XBRL · …" section label but never this. Only it lets a citation read "Matches filing"
  // (citationVerification.ts).
  fact?: true
  // A figure the server computed from filed figures (a growth rate or a margin: `value_kind` "yoy_growth" or
  // "margin"), which the filing itself does not state: it reads "Calculated from filing", never "Matches filing".
  calculated?: true
}

// A figure citation: a filed XBRL fact or a figure the server calculated from filed ones, never a quoted
// filing-text excerpt. These read as hard data (figures, not prose), so the UI renders them as dense data
// rows and the viewer finds them by text, never as a located passage. The kind comes from the server's
// payload alone (`fact` or `calculated`, set by parseCompletion): a model can label an excerpt "XBRL · …" or
// write an "F#" marker, but cannot give it a concept (E179). Every Copilot consumer under features/filings reads
// the kind here; the landing demo (features/marketing/components/AskFilingDemo.tsx) applies the same rule inline.
export const isXbrlCitation = (c: CopilotCitation): boolean => c.fact === true || c.calculated === true

// The raw XBRL tag (e.g. "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax") from an
// XBRL citation's section_ref ("XBRL · <tag>"), or null if it isn't an XBRL citation. Strips the
// leading "XBRL" label and any separator chars rather than hard-coding the exact delimiter.
export const xbrlTag = (c: CopilotCitation): string | null => {
  const ref = c.section_ref
  if (!ref || !ref.toUpperCase().startsWith('XBRL')) return null
  const tag = ref.slice(4).replace(/^[\s·:.\-—|]+/, '').trim()
  return tag || null
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

export interface CopilotHandlers {
  onProgress?: (stage: string) => void
  onToken: (text: string) => void
  onNotDisclosed: (answer: string) => void
  onComplete: (completion: CopilotCompletion) => void
  onError: (message: string) => void
}

// A Pro account reached this month's question cap: the 429 the Copilot route raises says "fair-use
// limit" (backend/app/routers/summaries.py). Upgrading cannot help, so the plan card shows no button.
export const isCopilotFairUseLimit = (message: string): boolean =>
  (message || '').toLowerCase().includes('fair-use limit')

// The question hit a plan gate (403 Pro-only or a spent free allowance, or the Pro fair-use 429). Used
// by the UI to show the quiet plan card instead of the Retry button, since retrying can't help.
export const isCopilotPaywallError = (message: string): boolean => {
  const m = (message || '').toLowerCase()
  return (
    isCopilotFairUseLimit(m) ||
    m.includes('pro feature') ||
    m.includes('upgrade to pro') ||
    m.includes('monthly limit') ||
    m.includes('limit reached')
  )
}

const parseErrorDetail = async (response: Response, fallback: string): Promise<string> => {
  try {
    const data = await response.json()
    if (data?.detail) return typeof data.detail === 'string' ? data.detail : fallback
    if (data?.message) return typeof data.message === 'string' ? data.message : fallback
  } catch {
    // Non-JSON body: fall through to the status-based fallback.
  }
  return fallback
}

const PUBLICATION_ERROR = "I couldn't verify the cited evidence, so I couldn't provide this answer."
const STREAM_ERROR = 'The answer could not be completed. Please try again.'

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

// This is the network boundary, including responses from an older backend revision during a
// deployment. It admits a complete wire payload; it does not reverify source meaning in the UI.
const parseCompletion = (data: Record<string, unknown>): CopilotCompletion | null => {
  if (
    typeof data.answer !== 'string' || !data.answer.trim() ||
    (data.kind !== 'answer' && data.kind !== 'not_disclosed') ||
    typeof data.grounded !== 'number' || !Number.isSafeInteger(data.grounded) ||
    data.grounded < 0 ||
    !Array.isArray(data.citations) ||
    !Array.isArray(data.followups) || !data.followups.every((f) => typeof f === 'string')
  ) return null

  if (data.grounded !== data.citations.length) return null
  // Unmatched numeric brackets may be filing literals; only returned sources must be referenced.
  const referenced = new Set(Array.from(
    data.answer.matchAll(/\[(F?\s*\d+)\]/gi),
    (match) => match[1].replace(/\s/g, '').toUpperCase()
  ))
  const citations: CopilotCitation[] = []
  const markers = new Set<string>()
  for (const citation of data.citations) {
    if (!isRecord(citation)) return null
    const { n, excerpt, section_ref, verified, fragment_url, concept, value_kind } = citation
    const validMarker = typeof n === 'number'
      ? Number.isSafeInteger(n) && n > 0
      : typeof n === 'string' && /^f\s*[1-9]\d*$/i.test(n)
    if (
      !validMarker || typeof excerpt !== 'string' || !excerpt.trim() || verified !== true ||
      (section_ref !== null && typeof section_ref !== 'string') ||
      (fragment_url !== null && typeof fragment_url !== 'string')
    ) return null
    const marker = String(n).replace(/\s/g, '').toUpperCase()
    if (markers.has(marker) || !referenced.has(marker)) return null
    markers.add(marker)
    const normalizedN = typeof n === 'string' ? n.replace(/\s/g, '') : n as number
    // A tool fact carries its concept; a computed one also names its kind (value_kind). Any kind present, well formed
    // or not, reads as computed, the weaker claim: only a concept with no kind at all reads "Matches filing" (E179).
    const toolFact = typeof concept === 'string' && concept.trim() !== ''
    const calculated = toolFact && value_kind !== undefined && value_kind !== null
    citations.push({
      n: normalizedN, excerpt, section_ref, verified, fragment_url,
      ...(calculated ? { calculated: true as const } : toolFact ? { fact: true as const } : {}),
    })
  }
  if (data.kind === 'not_disclosed' && (
    citations.length !== 0 || data.grounded !== 0 ||
    data.followups.length < 2 || data.followups.length > 3 ||
    data.followups.some((question) => !question.trim())
  )) return null
  return { answer: data.answer, citations, grounded: data.grounded, kind: data.kind, followups: data.followups }
}

/** Publish only the first admitted completion; intermediate model prose never reaches the UI. */
export const askFilingStream = async (
  filingId: number,
  question: string,
  history: CopilotTurn[],
  handlers: CopilotHandlers,
  signal?: AbortSignal
): Promise<void> => {
  const url = `${getApiUrl()}/api/summaries/filing/${filingId}/ask-stream`
  const controller = new AbortController()
  let terminal = false
  let reader: ReadableStreamDefaultReader<Uint8Array> | undefined
  let timeoutId: ReturnType<typeof setTimeout> | undefined
  let wakeCancellation!: () => void
  const cancelled = new Promise<null>((resolve) => { wakeCancellation = () => resolve(null) })

  const finish = () => {
    if (terminal) return false
    terminal = true
    clearTimeout(timeoutId)
    wakeCancellation()
    controller.abort()
    return true
  }
  const fail = (message: string) => {
    if (finish()) handlers.onError(message)
  }
  const onAbort = () => { finish() } // Explicit caller cancellation is quiet.
  const resetTimeout = () => {
    clearTimeout(timeoutId)
    timeoutId = setTimeout(() => fail('The answer timed out. Please try again.'), STREAM_TIMEOUT_MS)
  }
  const cancelBody = (body: ReadableStream<Uint8Array> | null) => {
    void body?.cancel().catch(() => { /* The transport may already have aborted. */ })
  }

  signal?.addEventListener('abort', onAbort, { once: true })
  try {
    if (signal?.aborted) { finish(); return }
    resetTimeout()
    // Race our wait against cancellation without cancelling the shared refresh promise. A refresh
    // that resolves later must not replay this obsolete request or publish a late response.
    const pendingResponse = postStreamWithRefresh(() => {
      if (terminal) return Promise.reject(new DOMException('Request cancelled', 'AbortError'))
      return fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ question, history }),
        signal: controller.signal,
      })
    }).then((response) => {
      if (terminal) cancelBody(response.body)
      return response
    })
    const response = await Promise.race([pendingResponse, cancelled])
    if (!response || terminal) return

    if (!response.ok) {
      let message: string | null
      if (response.status === 401) message = 'Log in to ask this filing a question.'
      else if (response.status === 403 || response.status === 429) {
        // Preserve application-owned entitlement/rate-limit details and their existing upgrade UI.
        message = await Promise.race([
          parseErrorDetail(response, response.status === 403
            ? 'This is a Pro feature.' : 'Monthly limit reached. Please try again later.'),
          cancelled,
        ])
      } else message = STREAM_ERROR
      if (message !== null) fail(message)
      cancelBody(response.body)
      return
    }

    reader = response.body?.getReader()
    if (!reader) { fail(STREAM_ERROR); return }
    const decoder = new TextDecoder()
    let buffer = ''
    while (!terminal) {
      const chunk = await Promise.race([reader.read(), cancelled])
      if (!chunk || terminal) return
      if (chunk.done) { fail(STREAM_ERROR); return }
      resetTimeout()
      buffer += decoder.decode(chunk.value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (terminal) break
        if (!line.startsWith('data:')) continue
        const payload = line.slice(5).trim()
        if (!payload) continue
        let data: unknown
        try { data = JSON.parse(payload) } catch { fail(STREAM_ERROR); break }
        if (!isRecord(data)) { fail(STREAM_ERROR); break }
        switch (data.type) {
          case 'progress':
            handlers.onProgress?.('reading')
            break
          case 'token':
          case 'not_disclosed':
          case 'activity':
            // Intermediate events may contain candidate prose from an older backend. They are
            // liveness only; no token, reason, label or tool metadata is forwarded to the UI.
            break
          case 'complete': {
            const completion = parseCompletion(data)
            if (!completion) fail(PUBLICATION_ERROR)
            else if (finish()) handlers.onComplete(completion)
            break
          }
          case 'error':
            fail(STREAM_ERROR)
            break
          default:
            break
        }
      }
    }
  } catch {
    fail(STREAM_ERROR)
  } finally {
    clearTimeout(timeoutId)
    signal?.removeEventListener('abort', onAbort)
    if (reader) {
      // A stalled transport must not keep the caller pending while teardown waits for cancellation.
      void reader.cancel().catch(() => {}).finally(() => {
        try { reader?.releaseLock() } catch { /* A transport read may still be settling. */ }
      })
    }
  }
}
