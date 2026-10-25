export interface FeedbackTextPart {
  text: string
  href?: string
}

// Ordinary line breaks and spaces separate pasted URLs. Other controls stay in the candidate
// so validation rejects them instead of URL() silently removing them. This is plain text,
// not a Markdown parser: delimiters and all other characters remain in the rendered message.
const CANDIDATE = /https?:\/\/[^\p{Z}\r\n<>"'`]+/giu
const START_BOUNDARY = /[\p{Z}\r\n([<{"'`]/u
const CONTROL = /[\p{Cc}\p{Cf}]/u
const CLOSING = { ')': '(', ']': '[', '}': '{' } as const

function withoutProseEnding(candidate: string): string {
  let end = candidate.length
  while (end > 0) {
    const last = candidate[end - 1]
    if (/[.,!?;:]/u.test(last)) {
      end -= 1
      continue
    }
    const opener = CLOSING[last as keyof typeof CLOSING]
    if (!opener) break
    const text = candidate.slice(0, end)
    if (text.split(last).length <= text.split(opener).length) break
    end -= 1
  }
  return candidate.slice(0, end)
}

function webHref(candidate: string): string | undefined {
  // URL() repairs backslashes and missing authorities; feedback must not make those look valid.
  const authority = candidate.match(/^https?:\/\/([^/?#]+)/iu)?.[1]
  if (CONTROL.test(candidate) || candidate.includes('\\') || !authority || authority.includes('@')) return
  try {
    const url = new URL(candidate)
    if ((url.protocol !== 'https:' && url.protocol !== 'http:') || url.username || url.password) return
    return url.href
  } catch {
    return
  }
}

/** Linkify explicit web URLs without changing, interpreting or fetching the submitted text. */
export function feedbackTextParts(message: string): FeedbackTextPart[] {
  const parts: FeedbackTextPart[] = []
  let cursor = 0
  for (const match of message.matchAll(CANDIDATE)) {
    const start = match.index
    if (start > 0 && !START_BOUNDARY.test(message[start - 1])) continue
    const text = withoutProseEnding(match[0])
    const href = webHref(text)
    if (!href) continue
    if (start > cursor) parts.push({ text: message.slice(cursor, start) })
    parts.push({ text, href })
    cursor = start + text.length
  }
  if (cursor < message.length) parts.push({ text: message.slice(cursor) })
  return parts
}
