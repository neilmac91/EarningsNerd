/**
 * The summary stream's error sentences, as the filing page shows them.
 *
 * The backend writes these sentences in the generation pipeline (backend/app/services/summary_stages, and
 * services/ai/summary_finalize.py for the payload messages generation.py and finalize.py stream), which
 * stays untouched until the founder opens it (tasks/todo.md), so several still carry an em-dash
 * or a lowercase "please" the product voice does not use. The page maps each one here instead of
 * printing it. Only what the reader sees changes: the raw message is still what decides the card
 * (isPaywallStreamError) and the retry, automatic or offered (isNonRetryableStreamError), so no matcher reads
 * this map.
 *
 * Keys are the backend's text exactly, as Python writes it; a `{name}` in a key is an f-string field and
 * matches any value, which the displayed sentence may reuse. A key spells the backend's em-dash through
 * EM_DASH: a key is matched and replaced, never shown, and no-em-dash-copy.spec.ts reads literals, so
 * the dash stays out of the literals that are copy (the spec below holds every displayed sentence to it,
 * and allows the char-code dash in this file only). tests/unit/streamErrorCopy.spec.ts reads every module
 * under summary_stages plus ai/summary_finalize.py: every error sentence they stream (and every message
 * carrying an em-dash) has a line here, every line here is still written by one of them, and the words
 * the two matchers route on still occur in the sentences that must trigger them.
 */
const EM_DASH = String.fromCharCode(0x2014)

export const STREAM_ERROR_COPY: Readonly<Record<string, string>> = {
  // fetch.py: a 6-K's exhibits could not be fetched from EDGAR.
  [`Unable to retrieve this 6-K at the moment ${EM_DASH} please try again shortly.`]:
    'We could not retrieve this 6-K from SEC EDGAR. Try again shortly.',
  // fetch.py (the filing could not be fetched), failure.py (any other failure) and summary_finalize.py
  // (the model returned no covered section; generation.py and finalize.py stream it) write the same
  // sentence, so it maps to the one sentence true of all three.
  [`Unable to retrieve this filing at the moment ${EM_DASH} please try again shortly.`]:
    'We could not generate this summary. Try again shortly.',
  // failure.py: the run passed its deadline.
  'Summary generation timed out. Please try again.': 'The summary timed out before it finished. Try again.',
  // generation.py and finalize.py: the writer returned an error with no message of its own.
  'Error generating summary': 'We could not generate this summary. Try again shortly.',
  // summary_finalize.py (extraction_failure): the structured extraction or the provider failed;
  // generation.py and finalize.py stream it.
  "We couldn't generate this summary just now. Please try again shortly.": 'We could not generate this summary. Try again shortly.',
  // admission.py: the filing id is unknown.
  'Filing not found': 'This filing could not be found.',
  // admission.py: Pro's fair-use ceiling. Never an upsell (a Pro user is not paywalled), and never a retry: the
  // ceiling holds until the month turns, so the stream does not retry it and its card offers no Retry.
  "We've temporarily paused new summary generation on your account due to unusually high recent volume. Please try again later or contact support.":
    "Your account has reached this month's limit on new summaries. It resets next month; contact support if you need more.",
  // admission.py: the free monthly limit. The paywall card writes its own copy for this one; the line
  // keeps the map whole.
  "You've reached your monthly limit of {limit} summaries. Upgrade to Pro for unlimited summaries.":
    "You've used this month's {limit} free summaries. Upgrade to Pro for unlimited summaries.",
  // admission.py: a progress line (this run joins one already in flight), shown only if a run ends on it.
  [`Another request is already generating this analysis ${EM_DASH} joining it...`]:
    'This summary is already being generated. Joining that run…',
}

const escapeRegExp = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/** Each key as a whole-message pattern: its `{name}` fields match any value. */
const PATTERNS: Array<{ pattern: RegExp; fields: string[]; shown: string }> = Object.entries(STREAM_ERROR_COPY).map(
  ([key, shown]) => {
    const fields: string[] = []
    const source = key
      .split(/(\{\w+\})/)
      .map((part) => {
        const field = /^\{(\w+)\}$/.exec(part)
        if (!field) return escapeRegExp(part)
        fields.push(field[1])
        return '(.+?)'
      })
      .join('')
    return { pattern: new RegExp(`^${source}$`), fields, shown }
  },
)

/** The sentence the page shows for a stream error: its mapped line, or the message itself when unmapped. */
export function streamErrorCopy(message: string | null | undefined): string {
  const text = (message ?? '').trim()
  for (const { pattern, fields, shown } of PATTERNS) {
    const match = pattern.exec(text)
    if (match) return fields.reduce((out, name, i) => out.replace(`{${name}}`, match[i + 1]), shown)
  }
  return text
}
