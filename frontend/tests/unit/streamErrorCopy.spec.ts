import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { isPaywallStreamError } from '@/features/summaries/api/summaries-api'
import { STREAM_ERROR_COPY, streamErrorCopy } from '@/features/summaries/lib/streamErrorCopy'

/**
 * The summary stream's error sentences are written in the backend pipeline (summary_stages, and the
 * payload messages services/ai/summary_finalize.py writes for generation.py and finalize.py to stream),
 * which stays untouched until the founder opens it, so the filing page maps each one to the product's
 * words (features/summaries/lib/streamErrorCopy.ts, brand sweep filing/F48). This gate reads every module
 * under summary_stages plus ai/summary_finalize.py, read only, and holds the map to that Python source:
 *
 *  1. Coverage: every message those modules stream as an error has its line in STREAM_ERROR_COPY, keyed
 *     by the exact Python text (escapes decoded, f-string fields as `{name}`), and so does every streamed
 *     message that carries an em-dash. A message is a literal in a `'message': …` dict value (alone, or
 *     as the fallback of `x or <literal>` or `.get('message', <literal>)`), a literal assigned to the
 *     name such a value sends, or a literal assigned to a `.message` attribute (summary_finalize's
 *     `run.message`, an error when the nearest `status = …` before it is 'error'). A dict is an error
 *     when it carries `'type': 'error'` or `'status': 'error'`. A reworded backend sentence fails until
 *     the map follows it, so the page never prints a sentence nobody mapped.
 *  2. No stale lines: every key is still written by one of those modules.
 *  3. Parity: the raw message, not the mapped one, decides the card. Exactly one admission.py error
 *     sentence opens the paywall card (the free monthly limit; Pro's fair-use pause never upsells), and it
 *     carries every phrase isPaywallStreamError routes on. Every phrase isNonRetryableStreamError routes
 *     on is still written somewhere a stream error's text can come from (routers/summaries.py, the stage
 *     modules, the client's own fallbacks): a dead-phrase check, not a proof that a stream error carries
 *     it. A 401 is never retried whatever its text (the reader sets retryable only for a 5xx).
 *  4. Voice: what the page shows has no em-dash, no exclamation mark, and reads as a sentence; a key's
 *     only fields are bare `{name}` ones, the only kind streamErrorCopy matches.
 *  5. The computed em-dash: `String.fromCharCode(0x2014)` (or 8212) builds a dash no-em-dash-copy.spec.ts
 *     cannot see, so app source may use it only in streamErrorCopy.ts, whose keys are matched, never shown.
 */

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const REPO = path.resolve(FRONTEND, '..')
const SERVICES = path.join(REPO, 'backend/app/services')
/** Every module under summary_stages, plus the module that writes the payload messages two of them stream. */
const SOURCES = [
  ...readdirSync(path.join(SERVICES, 'summary_stages'))
    .filter((f) => f.endsWith('.py'))
    .map((f) => `summary_stages/${f}`),
  'ai/summary_finalize.py',
]
/** The modules known to stream an error today: a reader that finds none in one of them is broken. */
const ERROR_WRITERS = [
  'summary_stages/fetch.py',
  'summary_stages/failure.py',
  'summary_stages/admission.py',
  'summary_stages/generation.py',
  'summary_stages/finalize.py',
  'ai/summary_finalize.py',
]
const EM_DASH = '—'

type Token = { kind: 'str' | 'name' | 'op'; text: string; line: number }

const ESCAPES: Record<string, string> = { n: '\n', t: '\t', r: '\r', '\\': '\\', "'": "'", '"': '"', '\n': '' }

/** Python source as tokens: string literals (prefix and quotes dropped; escapes decoded as Python decodes
    them, unless the literal is raw; an f-string's `{{` and `}}` read as single braces), names and
    single-character operators. Comments and whitespace are skipped. */
export function pythonTokens(src: string): Token[] {
  const out: Token[] = []
  let i = 0
  let line = 1
  while (i < src.length) {
    const c = src[i]
    if (c === '\n') line++
    if (c === '#') {
      while (i < src.length && src[i] !== '\n') i++
      continue
    }
    if (/\s/.test(c)) {
      i++
      continue
    }
    const prefix = /^[rRbBuUfF]{0,2}(?=["'])/.exec(src.slice(i, i + 3))
    if (prefix && (i === 0 || !/\w/.test(src[i - 1]))) {
      const start = line
      const raw = /r/i.test(prefix[0])
      const fString = /f/i.test(prefix[0])
      i += prefix[0].length
      const quote = src.startsWith('"""', i) ? '"""' : src.startsWith("'''", i) ? "'''" : src[i]
      i += quote.length
      let text = ''
      while (i < src.length && !src.startsWith(quote, i)) {
        if (src[i] === '\n') line++
        if (src[i] === '\\') {
          const next = src[i + 1]
          const hex = /^(?:x([0-9a-fA-F]{2})|u([0-9a-fA-F]{4})|U([0-9a-fA-F]{8}))/.exec(src.slice(i + 1, i + 10))
          if (raw) text += src.slice(i, i + 2)
          else if (hex) {
            text += String.fromCodePoint(parseInt(hex[1] ?? hex[2] ?? hex[3], 16))
            i += 1 + hex[0].length
            continue
          } else text += next in ESCAPES ? ESCAPES[next] : src.slice(i, i + 2)
          if (next === '\n') line++
          i += 2
        } else if (fString && (src.startsWith('{{', i) || src.startsWith('}}', i))) {
          text += src[i]
          i += 2
        } else text += src[i++]
      }
      i += quote.length
      out.push({ kind: 'str', text, line: start })
      continue
    }
    if (/[A-Za-z_]/.test(c)) {
      let j = i
      while (j < src.length && /\w/.test(src[j])) j++
      out.push({ kind: 'name', text: src.slice(i, j), line })
      i = j
      continue
    }
    out.push({ kind: 'op', text: c, line })
    i++
  }
  return out
}

/** The literal at `k` (adjacent literals joined as Python joins them, inside optional parentheses), or null. */
function literalAt(toks: Token[], k: number): { text: string; line: number } | null {
  let i = k
  let open = 0
  while (toks[i]?.kind === 'op' && toks[i].text === '(') {
    open++
    i++
  }
  if (toks[i]?.kind !== 'str') return null
  const line = toks[i].line
  let text = ''
  while (toks[i]?.kind === 'str') text += toks[i++].text
  for (let n = 0; n < open; n++) if (toks[i++]?.text !== ')') return null
  return { text, line }
}

const isStr = (t: Token | undefined, text: string) => t?.kind === 'str' && t.text === text
const isOp = (t: Token | undefined, text: string) => t?.kind === 'op' && t.text === text

/** The tokens of the dict literal around `k`: from its `{` to its matching `}`. */
function dictAround(toks: Token[], k: number): [number, number] | null {
  let depth = 0
  let start = -1
  for (let i = k; i >= 0; i--) {
    if (isOp(toks[i], '}') || isOp(toks[i], ')') || isOp(toks[i], ']')) depth++
    if (isOp(toks[i], '{') || isOp(toks[i], '(') || isOp(toks[i], '[')) {
      if (depth === 0) {
        if (!isOp(toks[i], '{')) return null
        start = i
        break
      }
      depth--
    }
  }
  if (start < 0) return null
  depth = 0
  for (let i = start; i < toks.length; i++) {
    if (isOp(toks[i], '{') || isOp(toks[i], '(') || isOp(toks[i], '[')) depth++
    if (isOp(toks[i], '}') || isOp(toks[i], ')') || isOp(toks[i], ']')) depth--
    if (depth === 0) return [start, i]
  }
  return null
}

interface Streamed { file: string; line: number; text: string; error: boolean }
type Literal = { text: string; line: number }

const OPENERS = ['(', '[', '{']
const CLOSERS = [')', ']', '}']

/** The end (exclusive) of the expression starting at `k`: the first depth-0 `,` `:` or closer, or, when
    `line` is given, the first depth-0 token on a later line (the end of an assignment's statement). */
function expressionEnd(toks: Token[], k: number, line?: number): number {
  let depth = 0
  for (let i = k; i < toks.length; i++) {
    const t = toks[i]
    if (depth === 0 && line !== undefined && t.line > line && i > k) return i
    if (t.kind === 'op' && OPENERS.includes(t.text)) depth++
    else if (t.kind === 'op' && CLOSERS.includes(t.text)) {
      if (depth === 0) return i
      depth--
    } else if (depth === 0 && t.kind === 'op' && (t.text === ',' || t.text === ':')) return i
  }
  return toks.length
}

/** The message literals in the expression toks[k, end): the value itself when it is a literal, and every
    literal fallback (`x or <literal>`, `.get('message', <literal>)`); a `.get(` key is not a message. */
function messageLiterals(toks: Token[], k: number, end: number): Literal[] {
  const out: Literal[] = []
  for (let i = k; i < end; i++) {
    if (toks[i].kind !== 'str' || toks[i - 1]?.kind === 'str') continue
    const isGetKey = isOp(toks[i - 1], '(') && toks[i - 2]?.kind === 'name' && toks[i - 2].text === 'get'
    if (isGetKey) continue
    let text = ''
    const line = toks[i].line
    for (let j = i; toks[j]?.kind === 'str'; j++) text += toks[j].text
    out.push({ text, line })
  }
  return out
}

/** The names the expression toks[k, end) may send as is: its first token, and each operand after `or`. */
function sentNames(toks: Token[], k: number, end: number): string[] {
  const names: string[] = []
  for (let i = k; i < end; i++) {
    const operand = i === k || (toks[i - 1]?.kind === 'name' && toks[i - 1].text === 'or')
    if (operand && toks[i].kind === 'name' && !isOp(toks[i + 1], '.') && !isOp(toks[i + 1], '(') && !isOp(toks[i + 1], '[')) {
      names.push(toks[i].text)
    }
  }
  return names
}

const ERROR_KEYS = ['type', 'status']

/** The messages one module streams: each `'message': …` dict value's literals (and, in an error dict,
    the literals assigned to a name it sends), and every literal assigned to a `.message` attribute. */
export function streamedMessages(src: string, file: string): Streamed[] {
  const toks = pythonTokens(src)
  const out: Streamed[] = []
  const assigned = (name: string): Literal[] =>
    toks.flatMap((t, j) => {
      if (t.kind !== 'name' || t.text !== name || isOp(toks[j - 1], '.') || !isOp(toks[j + 1], '=') || isOp(toks[j + 2], '=')) return []
      return messageLiterals(toks, j + 2, expressionEnd(toks, j + 2, t.line))
    })
  toks.forEach((t, k) => {
    if (!isStr(t, 'message') || !isOp(toks[k + 1], ':')) return
    const bounds = dictAround(toks, k)
    const error =
      !!bounds &&
      toks.slice(bounds[0], bounds[1]).some((u, j, all) => ERROR_KEYS.some((key) => isStr(u, key)) && isOp(all[j + 1], ':') && isStr(all[j + 2], 'error'))
    const end = expressionEnd(toks, k + 2)
    for (const lit of messageLiterals(toks, k + 2, end)) out.push({ file, line: lit.line, text: lit.text, error })
    if (error) {
      for (const name of sentNames(toks, k + 2, end)) {
        for (const lit of assigned(name)) out.push({ file, line: lit.line, text: lit.text, error })
      }
    }
  })
  // `run.message = <literal>` (or `+=`): the payload message the stage streams. Its kind is the nearest
  // `status = <literal>` before it, in source order.
  toks.forEach((t, k) => {
    if (t.kind !== 'name' || t.text !== 'message' || !isOp(toks[k - 1], '.')) return
    const eq = isOp(toks[k + 1], '=') && !isOp(toks[k + 2], '=') ? k + 2 : isOp(toks[k + 1], '+') && isOp(toks[k + 2], '=') ? k + 3 : -1
    if (eq < 0) return
    let status = ''
    for (let i = k - 1; i >= 0; i--) {
      if (toks[i].kind === 'name' && toks[i].text === 'status' && isOp(toks[i + 1], '=') && !isOp(toks[i + 2], '=')) {
        status = toks[i + 2]?.kind === 'str' ? toks[i + 2].text : ''
        break
      }
    }
    for (const lit of messageLiterals(toks, eq, expressionEnd(toks, eq, t.line))) out.push({ file, line: lit.line, text: lit.text, error: status === 'error' })
  })
  return out
}

const source = (file: string) => readFileSync(path.join(SERVICES, file), 'utf8')
const streamed = () => SOURCES.flatMap((file) => streamedMessages(source(file), file))

/** The phrases a matcher in summaries-api.ts tests for (its `.includes('…')` calls). */
function matcherPhrases(fn: string): string[] {
  const file = path.join(FRONTEND, 'features/summaries/api/summaries-api.ts')
  const sf = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
  const phrases: string[] = []
  let found = false
  const visit = (node: ts.Node, inside: boolean) => {
    const here = inside || (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.name.text === fn)
    if (here && !inside) found = true
    if (
      here &&
      ts.isCallExpression(node) &&
      ts.isPropertyAccessExpression(node.expression) &&
      node.expression.name.text === 'includes' &&
      node.arguments[0] &&
      ts.isStringLiteralLike(node.arguments[0])
    ) phrases.push(node.arguments[0].text)
    ts.forEachChild(node, (child) => visit(child, here))
  }
  visit(sf, false)
  if (!found) throw new Error(`summaries-api.ts: ${fn} is gone; update this spec`)
  // A matcher rewritten without `.includes('…')` calls would leave nothing to check: fail instead.
  if (phrases.length === 0) throw new Error(`summaries-api.ts: ${fn} no longer calls .includes('…'); update this spec`)
  return phrases
}

/** Every string a frontend module writes (template parts joined). */
function frontendStrings(rel: string): string[] {
  const file = path.join(FRONTEND, rel)
  const sf = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
  const out: string[] = []
  const visit = (node: ts.Node) => {
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) out.push(node.text)
    if (ts.isTemplateExpression(node)) out.push([node.head.text, ...node.templateSpans.map((s) => s.literal.text)].join(' '))
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out
}

describe('the summary stream error sentences the filing page maps', () => {
  it('reads every stage module and summary_finalize.py (a reader that finds nothing must not pass)', () => {
    expect(SOURCES.length, 'summary_stages is read whole').toBeGreaterThanOrEqual(8)
    const errors = streamed().filter((m) => m.error)
    for (const file of ERROR_WRITERS) expect(errors.some((m) => m.file === file), `${file} streams an error sentence`).toBe(true)
    // The shapes the reader must see, each in one probe module.
    const probe = [
      `x = {'type': 'error', 'message': msg}`,
      `msg = ("a " f"{b}")  # 'c'`,
      `y = {'type': 'error', 'message': other or 'We\\'ve stopped \\u2014 retry', 'id': 1}`,
      `err = run.payload.get("message", "Default error")`,
      `yield {"type": "error", "message": err}`,
      `def fail(): return {"status": "error", "message": "Extraction failed."}`,
      `run.status = "partial"`,
      `run.message = "Some loaded."`,
      `run.status = "error"`,
      `run.message = "Nothing usable."`,
      `z = {'type': 'progress', 'message': 'Working...'}`,
    ].join('\n')
    expect(streamedMessages(probe, 't.py')).toEqual([
      { file: 't.py', line: 2, text: 'a {b}', error: true },
      { file: 't.py', line: 3, text: `We've stopped ${EM_DASH} retry`, error: true },
      { file: 't.py', line: 4, text: 'Default error', error: true },
      { file: 't.py', line: 6, text: 'Extraction failed.', error: true },
      { file: 't.py', line: 11, text: 'Working...', error: false },
      { file: 't.py', line: 8, text: 'Some loaded.', error: false },
      { file: 't.py', line: 10, text: 'Nothing usable.', error: true },
    ])
  })

  it('maps every error sentence the stage modules and summary_finalize.py stream, and every em-dash message', () => {
    const unmapped = streamed()
      .filter((m) => m.error || m.text.includes(EM_DASH))
      .filter((m) => !(m.text in STREAM_ERROR_COPY))
      .map((m) => `${m.file}:${m.line} ${m.text}`)
    expect(unmapped, 'add the sentence to STREAM_ERROR_COPY (features/summaries/lib/streamErrorCopy.ts), keyed by its exact Python text').toEqual([])
  })

  it('keeps no line for a sentence no stage module writes any more', () => {
    const written = new Set<string>()
    for (const file of SOURCES) {
      const toks = pythonTokens(source(file))
      toks.forEach((_, k) => {
        const lit = literalAt(toks, k)
        if (lit) written.add(lit.text)
      })
    }
    expect(Object.keys(STREAM_ERROR_COPY).filter((key) => !written.has(key)), 'delete the stale line from STREAM_ERROR_COPY').toEqual([])
  })

  it('leaves the routing words in the sentences the matchers must catch', () => {
    const admission = streamed().filter((m) => m.file === 'summary_stages/admission.py' && m.error)
    const paywall = admission.filter((m) => isPaywallStreamError(m.text))
    expect(paywall.map((m) => m.text), 'exactly one admission.py error sentence opens the paywall card (the free monthly limit)').toHaveLength(1)
    for (const phrase of matcherPhrases('isPaywallStreamError')) {
      expect(paywall[0].text.toLowerCase(), `the paywall sentence carries "${phrase}"`).toContain(phrase)
    }
    for (const m of streamed().filter((s) => s.error && s.file !== 'summary_stages/admission.py')) {
      expect(isPaywallStreamError(m.text), `${m.file}:${m.line} must not open the paywall card`).toBe(false)
    }
    const writers = [
      ...['backend/app/routers/summaries.py', ...SOURCES.map((file) => `backend/app/services/${file}`)].flatMap((rel) =>
        pythonTokens(readFileSync(path.join(REPO, rel), 'utf8')).filter((t) => t.kind === 'str').map((t) => t.text),
      ),
      ...frontendStrings('features/summaries/api/summaries-api.ts').filter((s) => !/^[a-z ]+$/.test(s)),
      ...frontendStrings('features/summaries/hooks/useSummaryGeneration.ts'),
    ].map((s) => s.toLowerCase())
    for (const phrase of matcherPhrases('isNonRetryableStreamError')) {
      expect(writers.some((s) => s.includes(phrase)), `"${phrase}" is still written where a stream error's text can come from`).toBe(true)
    }
  })

  it('builds an em-dash from a char code only in streamErrorCopy.ts, whose keys are never shown', () => {
    const COMPUTED_DASH = /\bfrom(?:CharCode|CodePoint)\(\s*(?:0x2014|8212)\s*\)/
    const files: string[] = []
    const walk = (dir: string) => {
      for (const entry of readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name)
        if (entry.isDirectory()) {
          if (entry.name !== 'node_modules') walk(full)
        } else if (/\.(ts|tsx)$/.test(entry.name)) files.push(full)
      }
    }
    for (const root of ['app', 'components', 'features', 'hooks', 'lib']) walk(path.join(FRONTEND, root))
    const users = files.filter((file) => COMPUTED_DASH.test(readFileSync(file, 'utf8'))).map((file) => path.relative(FRONTEND, file))
    expect(users, 'spell no displayed em-dash through a char code; no-em-dash-copy.spec.ts cannot see it').toEqual([
      'features/summaries/lib/streamErrorCopy.ts',
    ])
  })

  it('shows sentences in the product voice and passes an unmapped message through', () => {
    for (const [key, shown] of Object.entries(STREAM_ERROR_COPY)) {
      expect(shown, 'no em-dash in what the page shows').not.toContain(EM_DASH)
      expect(shown).not.toContain('!')
      expect(shown).toMatch(/^[A-Z].*[.…]$/)
      expect(key, 'a key field is a bare {name}: a format spec or an expression never matches at runtime').not.toMatch(/\{(?!\w+\})/)
    }
    expect(streamErrorCopy("You've reached your monthly limit of 5 summaries. Upgrade to Pro for unlimited summaries.")).toBe(
      "You've used this month's 5 free summaries. Upgrade to Pro for unlimited summaries.",
    )
    expect(streamErrorCopy(`Unable to retrieve this filing at the moment ${EM_DASH} please try again shortly.`)).toBe(
      'We could not generate this summary. Try again shortly.',
    )
    expect(streamErrorCopy('The filing could not be summarized right now.')).toBe('The filing could not be summarized right now.')
    expect(streamErrorCopy(null)).toBe('')
  })
})
