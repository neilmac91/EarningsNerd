import { execFileSync } from 'node:child_process'
import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { bindingResolver } from './astBindings'
import { pythonTokens, type Token } from './pythonTokens'
import { isNonRetryableStreamError, isPaywallStreamError } from '@/features/summaries/api/summaries-api'
import { STREAM_ERROR_COPY, streamErrorCopy } from '@/features/summaries/lib/streamErrorCopy'

/**
 * The summary stream's error sentences are written in the backend pipeline (summary_stages, and the
 * payload messages services/ai/summary_finalize.py writes for generation.py and finalize.py to stream),
 * whose em-dash sentences took the product's words with E217's functional change there (F35, D-046, E92); the
 * filing page maps each sentence to the product's words (features/summaries/lib/streamErrorCopy.ts, brand sweep
 * filing/F48), a sentence already in them to itself.
 * This gate reads every module under summary_stages plus ai/summary_finalize.py, read only, and holds the
 * map to that Python source:
 *
 *  1. Coverage: every message those modules stream as an error has its line in STREAM_ERROR_COPY, keyed
 *     by the exact Python text (escapes decoded, `\N{EM DASH}` and the other names in UNICODE_NAMES
 *     included, f-string fields as `{name}`), and so does every streamed message that carries an em-dash.
 *     A message is a literal in a `'message': …` dict value (alone, or as the fallback of `x or <literal>`
 *     or `.get('message', <literal>)`), a literal assigned to a name such a value sends (in any streamed
 *     dict, an error or a progress one, and through a subscript of a list the name is assigned from:
 *     `heartbeat_message = SUMMARIZE_MESSAGES[i]` reads that list), or a literal assigned to a `.message`
 *     attribute (summary_finalize's `run.message`, an error when the nearest `status = …` before it is
 *     'error'). A dict is an error when it carries `'type': 'error'` or `'status': 'error'`. A message the
 *     reader cannot key by its text (a literal formatted with `%` or `.format()`, a `\N{…}` name it does
 *     not know) fails the reader. A reworded backend sentence fails until the map follows it, so the page
 *     never prints a sentence nobody mapped. Out of reach (planted as a gap in the self-check): a `status`
 *     set after its `.message`, read as the status before it.
 *  2. No stale lines: every key is still written by one of those modules, or is an answer the stream
 *     endpoint gives before it streams (ENDPOINT, below: the route's own HTTPExceptions and rate-limit
 *     detail, and its account check's), whose JSON detail the reader shows as the error.
 *  3. Parity: the raw message, not the mapped one, decides the card. Exactly one admission.py error
 *     sentence opens the paywall card (the free monthly limit; Pro's fair-use pause never upsells), and it
 *     carries every phrase isPaywallStreamError routes on. Every phrase isNonRetryableStreamError routes
 *     on is still written somewhere a stream error's text can come from (routers/summaries.py, the stage
 *     modules, the endpoint's answers, the client's own fallbacks, the matchers' own `.includes` literals
 *     never counted): a dead-phrase check, not a proof that a stream error carries it. A 401 is never retried
 *     automatically whatever its text (the reader sets retryable only for a 5xx). The proof, sentence by
 *     sentence, for every answer no retry can change: Pro's fair-use pause, read in admission.py's own words
 *     from the error it streams in the block under `if user_is_unlimited:` (the billing-unlimited caller its
 *     usage gate blocked), and every 403 the endpoint answers with (a plan or account gate: a Free reader's
 *     force regeneration of a summary the page shows, an inactive account) must match
 *     isNonRetryableStreamError, so the stream never retries them and the card offers no Retry; the
 *     endpoint's 401 (a retry after a refresh or a sign-in can help), its 404 (kept retryable since round 3)
 *     and its 429 must not, and a status the table does not classify fails. A reworded sentence fails here
 *     until the matcher follows it.
 *  4. Voice: what the page shows has no em-dash, no exclamation mark, and reads as a sentence, a line of the map
 *     or an endpoint answer the map passes through as the backend wrote it (the account check's, since E45); a
 *     key's only fields are bare `{name}` ones, the only kind streamErrorCopy matches.
 *  5. The hidden em-dash: no-em-dash-copy.spec.ts reads a file's raw text for the character, so a dash
 *     spelled any other way passes it: a char code (`String.fromCharCode(0x2014)`, `fromCodePoint`, any
 *     radix, a const or arithmetic resolved to its value), an escape (`'\u2014'`, `` `\u{2014}` ``) or a
 *     JSX entity (`&mdash;`, `&#8212;`, `&#x2014;`, in JSX text or an attribute string). App source (every
 *     tracked script under app, components, features, hooks and lib) spells it no such way: streamErrorCopy.ts
 *     did, by char code, for the backend's em-dash keys, until the backend took the voice (E92). Out of reach: a
 *     code computed at run time from a value the file does not state.
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
    literal fallback (`x or <literal>`, `.get('message', <literal>)`); a `.get(` key is not a message. A
    literal formatted with `%` or `.format()` cannot be keyed by its text, so it fails the reader. */
function messageLiterals(toks: Token[], k: number, end: number): Literal[] {
  const out: Literal[] = []
  for (let i = k; i < end; i++) {
    if (toks[i].kind !== 'str' || toks[i - 1]?.kind === 'str') continue
    const isGetKey = isOp(toks[i - 1], '(') && toks[i - 2]?.kind === 'name' && toks[i - 2].text === 'get'
    if (isGetKey) continue
    let text = ''
    const line = toks[i].line
    let j = i
    for (; toks[j]?.kind === 'str'; j++) text += toks[j].text
    const percent = isOp(toks[j], '%') && !isOp(toks[j + 1], '=')
    const format = isOp(toks[j], '.') && toks[j + 1]?.kind === 'name' && toks[j + 1].text === 'format' && isOp(toks[j + 2], '(')
    if (percent || format) throw new Error(`line ${line}: a message formatted with ${percent ? '%' : '.format()'} cannot be keyed by its text: write it as an f-string`)
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
  // The literals assigned to a name; an assignment of a subscript (`m = MESSAGES[i % n]`) reads the list the
  // subscripted name is assigned in turn.
  const assigned = (name: string, seen = new Set<string>()): Literal[] => {
    if (seen.has(name)) return []
    seen.add(name)
    return toks.flatMap((t, j) => {
      if (t.kind !== 'name' || t.text !== name || isOp(toks[j - 1], '.') || !isOp(toks[j + 1], '=') || isOp(toks[j + 2], '=')) return []
      const subscripted = toks[j + 2]?.kind === 'name' && isOp(toks[j + 3], '[') ? assigned(toks[j + 2].text, seen) : []
      return [...messageLiterals(toks, j + 2, expressionEnd(toks, j + 2, t.line)), ...subscripted]
    })
  }
  toks.forEach((t, k) => {
    if (!isStr(t, 'message') || !isOp(toks[k + 1], ':')) return
    const bounds = dictAround(toks, k)
    const error =
      !!bounds &&
      toks.slice(bounds[0], bounds[1]).some((u, j, all) => ERROR_KEYS.some((key) => isStr(u, key)) && isOp(all[j + 1], ':') && isStr(all[j + 2], 'error'))
    const end = expressionEnd(toks, k + 2)
    for (const lit of messageLiterals(toks, k + 2, end)) out.push({ file, line: lit.line, text: lit.text, error })
    for (const name of sentNames(toks, k + 2, end)) {
      for (const lit of assigned(name)) out.push({ file, line: lit.line, text: lit.text, error })
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

/** The functions whose errors the stream endpoint answers with before it streams: the route, and the account
    check it depends on. runStreamAttempt shows a 4xx's JSON detail as the card's raw message. */
const ENDPOINT = [
  { file: 'backend/app/routers/summaries.py', fn: 'generate_summary_stream' },
  { file: 'backend/app/routers/auth.py', fn: 'get_current_user' },
]

interface Raised { file: string; line: number; status: number; text: string }

/** The index of the bracket that closes the one at `open`. */
function closing(toks: Token[], open: number): number {
  let depth = 0
  for (let i = open; i < toks.length; i++) {
    if (toks[i].kind === 'op' && OPENERS.includes(toks[i].text)) depth++
    else if (toks[i].kind === 'op' && CLOSERS.includes(toks[i].text) && --depth === 0) return i
  }
  return toks.length
}

/** A status written as digits (each digit is its own token) or as `status.HTTP_<code>_…`, or null. */
function statusAt(toks: Token[], k: number): number | null {
  if (toks[k]?.kind === 'name' && toks[k].text === 'status' && isOp(toks[k + 1], '.')) {
    const code = /^HTTP_(\d{3})_/.exec(toks[k + 2]?.text ?? '')
    return code ? Number(code[1]) : null
  }
  let digits = ''
  for (let i = k; toks[i]?.kind === 'op' && /^\d$/.test(toks[i].text); i++) digits += toks[i].text
  return digits ? Number(digits) : null
}

/** The errors one function of a Python module raises: each `HTTPException(...)` in its body (its status as digits
    or `status.HTTP_<code>_…`, its detail a literal, adjacent literals joined), raised there or held in a name, and
    each `enforce_rate_limit(...)`'s `error_detail` (a 429). The body ends at the first line after the `def` indented
    no deeper than it (a signature's closing bracket aside). A detail the reader cannot key by its text fails it. */
export function raisedErrors(src: string, file: string, fn: string): Raised[] {
  const lines = src.split('\n')
  const at = lines.findIndex((line) => new RegExp(`^\\s*(?:async\\s+)?def ${fn}\\(`).test(line))
  if (at < 0) throw new Error(`${file}: ${fn} is gone; update this spec`)
  const indent = lines[at].search(/\S/)
  let end = lines.length
  for (let i = at + 1; i < lines.length; i++) {
    const text = lines[i].trim()
    if (!text || text.startsWith('#') || /^[)\]]/.test(text)) continue
    if (lines[i].search(/\S/) <= indent) {
      end = i
      break
    }
  }
  const toks = pythonTokens(lines.slice(at, end).join('\n'))
  const out: Raised[] = []
  toks.forEach((t, k) => {
    const limit = t.text === 'enforce_rate_limit'
    if (t.kind !== 'name' || !(limit || t.text === 'HTTPException') || !isOp(toks[k + 1], '(')) return
    let status: number | null = limit ? 429 : null
    let text: string | null = null
    const close = closing(toks, k + 1)
    for (let i = k + 2; i < close; i++) {
      if (toks[i].kind !== 'name' || !isOp(toks[i + 1], '=') || isOp(toks[i + 2], '=')) continue
      if (!limit && toks[i].text === 'status_code') status = statusAt(toks, i + 2)
      if (toks[i].text === (limit ? 'error_detail' : 'detail')) {
        const lit = literalAt(toks, i + 2)
        if (!lit) throw new Error(`${file}:${at + toks[i].line} ${fn}: a detail the reader cannot key by its text`)
        text = lit.text
      }
    }
    if (status === null || text === null) throw new Error(`${file}:${at + t.line} ${fn}: an error with no status or detail the reader can read`)
    out.push({ file, line: at + t.line, status, text })
  })
  return out
}

const endpointErrors = () => ENDPOINT.flatMap(({ file, fn }) => raisedErrors(readFileSync(path.join(REPO, file), 'utf8'), file, fn))

/** The error sentences a module streams inside the block under its first `if <condition>:` line, the block
    read by indentation (blank and comment lines inside it skipped), or null when no such line exists. */
export function errorsUnder(src: string, file: string, condition: string): Streamed[] | null {
  const lines = src.split('\n')
  const header = new RegExp(`^(\\s*)if ${condition}\\s*:\\s*(?:#.*)?$`)
  const at = lines.findIndex((line) => header.test(line))
  if (at < 0) return null
  const indent = header.exec(lines[at])![1].length
  let last = at
  for (let i = at + 1; i < lines.length; i++) {
    const text = lines[i].trim()
    if (!text || text.startsWith('#')) continue
    if (lines[i].search(/\S/) <= indent) break
    last = i
  }
  return streamedMessages(src, file).filter((m) => m.error && m.line > at + 1 && m.line <= last + 1)
}

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

/** The matchers whose own `.includes('…')` literals are what the parity leg checks, never a writer of them. */
const MATCHERS = ['isPaywallStreamError', 'isNonRetryableStreamError']

/** Every string a frontend module writes (template parts joined), outside the matchers' own declarations. */
export function frontendStrings(source: string, file = 'probe.ts'): string[] {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
  const out: string[] = []
  const visit = (node: ts.Node) => {
    if ((ts.isVariableDeclaration(node) || ts.isFunctionDeclaration(node)) && node.name && ts.isIdentifier(node.name) && MATCHERS.includes(node.name.text)) return
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) out.push(node.text)
    if (ts.isTemplateExpression(node)) out.push([node.head.text, ...node.templateSpans.map((s) => s.literal.text)].join(' '))
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out
}
const frontendFile = (rel: string) => frontendStrings(readFileSync(path.join(FRONTEND, rel), 'utf8'), rel)

const EM_DASH_CODE = 0x2014
const DASH_ENTITY = /&mdash;|&#0*8212;|&#x0*2014;/i

/** Each displayed em-dash a file spells other than as the character itself: by char code (any radix, a
    same-file const or arithmetic resolved), by escape in a string or a template, or by a JSX entity. */
export function hiddenDashes(source: string, file: string): string[] {
  const kind = /\.tsx$/.test(file) ? ts.ScriptKind.TSX : /\.jsx$/.test(file) ? ts.ScriptKind.JSX : /\.[cm]?js$/.test(file) ? ts.ScriptKind.JS : ts.ScriptKind.TS
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, kind)
  const resolve = bindingResolver(sf)
  const out: string[] = []
  const at = (node: ts.Node, what: string) => out.push(`${file}:${sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1} ${what}`)
  const numberOf = (expr: ts.Expression, seen = new Set<ts.Node>()): number | null => {
    let e = expr
    while (ts.isParenthesizedExpression(e) || ts.isAsExpression(e) || ts.isNonNullExpression(e)) e = e.expression
    if (ts.isNumericLiteral(e)) return Number(e.text)
    if (ts.isPrefixUnaryExpression(e) && e.operator === ts.SyntaxKind.MinusToken) {
      const n = numberOf(e.operand, seen)
      return n === null ? null : -n
    }
    if (ts.isBinaryExpression(e)) {
      const [a, b] = [numberOf(e.left, seen), numberOf(e.right, seen)]
      if (a === null || b === null) return null
      switch (e.operatorToken.kind) {
        case ts.SyntaxKind.PlusToken: return a + b
        case ts.SyntaxKind.MinusToken: return a - b
        case ts.SyntaxKind.AsteriskToken: return a * b
        case ts.SyntaxKind.BarToken: return a | b
        default: return null
      }
    }
    if (ts.isIdentifier(e)) {
      const binding = resolve(e)
      const held = binding && ts.isVariableDeclaration(binding.decl) && binding.decl.parent.flags & ts.NodeFlags.Const ? binding.init : undefined
      if (held && !seen.has(binding!.decl)) return numberOf(held, new Set([...seen, binding!.decl]))
    }
    return null
  }
  const visit = (node: ts.Node) => {
    if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression) && /^from(?:CharCode|CodePoint)$/.test(node.expression.name.text)) {
      if (node.arguments.some((arg) => numberOf(arg) === EM_DASH_CODE)) at(node, 'a char code')
    }
    if ((ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isTemplateHead(node) || ts.isTemplateMiddle(node) || ts.isTemplateTail(node))) {
      const raw = node.getText(sf)
      if (node.text.includes(EM_DASH) && !raw.includes(EM_DASH)) at(node, 'an escape')
      else if (DASH_ENTITY.test(raw) && ts.isJsxAttribute(node.parent)) at(node, 'an entity')
    }
    if (ts.isJsxText(node) && DASH_ENTITY.test(node.text)) at(node, 'an entity')
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
      `BEATS = ["Reading \\N{EM DASH} still", 'Checking']`,
      `beat = BEATS[n % len(BEATS)]`,
      `yield {'type': 'progress', 'message': beat}`,
    ].join('\n')
    expect(streamedMessages(probe, 't.py')).toEqual([
      { file: 't.py', line: 2, text: 'a {b}', error: true },
      { file: 't.py', line: 3, text: `We've stopped ${EM_DASH} retry`, error: true },
      { file: 't.py', line: 4, text: 'Default error', error: true },
      { file: 't.py', line: 6, text: 'Extraction failed.', error: true },
      { file: 't.py', line: 11, text: 'Working...', error: false },
      { file: 't.py', line: 12, text: `Reading ${EM_DASH} still`, error: false },
      { file: 't.py', line: 12, text: 'Checking', error: false },
      { file: 't.py', line: 8, text: 'Some loaded.', error: false },
      { file: 't.py', line: 10, text: 'Nothing usable.', error: true },
    ])
    // What the reader cannot key fails it, rather than read as text.
    expect(() => streamedMessages(`x = {'type': 'error', 'message': 'Failed: %s' % reason}`, 'f.py')).toThrow(/formatted with %/)
    expect(() => streamedMessages(`x = {'type': 'error', 'message': 'Failed: {}'.format(reason)}`, 'f.py')).toThrow(/formatted with \.format/)
    expect(() => streamedMessages(`x = {'type': 'error', 'message': 'A \\N{SNOWMAN}'}`, 'f.py')).toThrow(/does not know/)
    // A gap the header names: a status set after its message reads as the status before it.
    expect(streamedMessages('run.status = "complete"\nrun.message = "Late."\nrun.status = "error"', 'g.py')).toEqual([
      { file: 'g.py', line: 2, text: 'Late.', error: false },
    ])
  })

  it('maps every error sentence the stage modules and summary_finalize.py stream, and every em-dash message', () => {
    const unmapped = streamed()
      .filter((m) => m.error || m.text.includes(EM_DASH))
      .filter((m) => !(m.text in STREAM_ERROR_COPY))
      .map((m) => `${m.file}:${m.line} ${m.text}`)
    expect(unmapped, 'add the sentence to STREAM_ERROR_COPY (features/summaries/lib/streamErrorCopy.ts), keyed by its exact Python text').toEqual([])
  })

  it('keeps no line for a sentence no stage module writes and the endpoint no longer answers with', () => {
    const written = new Set<string>()
    for (const file of SOURCES) {
      const toks = pythonTokens(source(file))
      toks.forEach((_, k) => {
        const lit = literalAt(toks, k)
        if (lit) written.add(lit.text)
      })
    }
    for (const answer of endpointErrors()) written.add(answer.text)
    expect(Object.keys(STREAM_ERROR_COPY).filter((key) => !written.has(key)), 'delete the stale line from STREAM_ERROR_COPY').toEqual([])
  })

  it("reads every error an endpoint function raises, in each form, and nothing after it (a self-check on planted forms)", () => {
    const probe = [
      'async def stream(',
      '    filing_id: int,',
      '):',
      '    enforce_rate_limit(request, LIMITER, key, error_detail="Too many requests.", include_client_ip=False)',
      '    if not filing:',
      '        raise HTTPException(status_code=404, detail="Filing gone")',
      '    denied = HTTPException(',
      '        status_code=status.HTTP_403_FORBIDDEN,',
      '        detail=("A Pro " "feature."),',
      '        headers={"X": "y"},',
      '    )',
      '    try:',
      '        raise denied',
      '    except (ValueError, HTTPException):',
      '        raise',
      '',
      'def after():',
      '    raise HTTPException(status_code=500, detail="Not read")',
    ].join('\n')
    expect(raisedErrors(probe, 'p.py', 'stream')).toEqual([
      { file: 'p.py', line: 4, status: 429, text: 'Too many requests.' },
      { file: 'p.py', line: 6, status: 404, text: 'Filing gone' },
      { file: 'p.py', line: 7, status: 403, text: 'A Pro feature.' },
    ])
    expect(() => raisedErrors('def f():\n    raise HTTPException(status_code=403, detail=reason)', 'q.py', 'f')).toThrow(/cannot key/)
    expect(() => raisedErrors('def f():\n    raise HTTPException(detail="No status")', 'q.py', 'f')).toThrow(/no status/)
    expect(() => raisedErrors('def g():\n    pass', 'q.py', 'f')).toThrow(/is gone/)
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
      ...endpointErrors().map((answer) => answer.text),
      ...frontendFile('features/summaries/api/summaries-api.ts'),
      ...frontendFile('features/summaries/hooks/useSummaryGeneration.ts'),
    ].map((s) => s.toLowerCase())
    for (const phrase of matcherPhrases('isNonRetryableStreamError')) {
      expect(writers.some((s) => s.includes(phrase)), `"${phrase}" is still written where a stream error's text can come from`).toBe(true)
    }
    // A matcher's own phrase is never its writer, whatever its spelling.
    const matcher = "const isNonRetryableStreamError = (m: string) => m.includes('sign-in') || m.includes(\"o'clock 9\")\nconst s = 'Sign in again.'"
    expect(frontendStrings(matcher)).toEqual(['Sign in again.'])
  })

  it("holds Pro's fair-use pause, in admission.py's own words, to the matcher that stops every retry", () => {
    // The block read, planted: the error inside the block counts (its literals joined, a blank and a comment line
    // inside skipped), the one after the block's dedent does not, and a condition no line tests reads as null.
    const probe = [
      'async def admit(run):',
      '    if can_generate:',
      '        return',
      '    if user_is_unlimited:  # Pro',
      '        logger.warning("capped")',
      '',
      '        # the pause',
      '        yield {"type": "error", "message": ("A paused " "run.")}',
      '        return',
      '    yield {"type": "error", "message": "After the block."}',
    ].join('\n')
    expect(errorsUnder(probe, 'p.py', 'user_is_unlimited')).toEqual([{ file: 'p.py', line: 8, text: 'A paused run.', error: true }])
    expect(errorsUnder(probe, 'p.py', 'user_is_pro')).toBeNull()
    const file = 'summary_stages/admission.py'
    const pause = errorsUnder(source(file), file, 'user_is_unlimited')
    expect(pause, `${file} no longer tests \`if user_is_unlimited:\`: find where it streams Pro's fair-use pause and read that`).not.toBeNull()
    expect(pause!.map((m) => m.text), `${file} streams one fair-use pause`).toHaveLength(1)
    expect(
      isNonRetryableStreamError(pause![0].text),
      `${file}:${pause![0].line} "${pause![0].text}" no longer matches isNonRetryableStreamError: move its phrase ` +
        '(features/summaries/api/summaries-api.ts) to the new words, or the stream retries the pause and its card offers a Retry',
    ).toBe(true)
  })

  it('holds every 403 the stream endpoint answers with, in its own words, to that matcher, and keeps a Retry for the rest', () => {
    // What a retry can do about each status the endpoint answers with before it streams. A 403 is a plan or account
    // gate (a Free reader's force regeneration of a summary the page shows, an inactive account): it holds whatever
    // the reader retries. A 401 can lift after a refresh or a sign-in (with the session gone, a press starts no
    // run and says to sign in), the 404 is kept retryable since round 3 (only a row deleted mid-run reaches it), and
    // a 429 lifts after a moment.
    const NO_RETRY_HELPS = new Set([403])
    const A_RETRY_CAN_HELP = new Set([401, 404, 429])
    const answers = endpointErrors()
    for (const { file } of ENDPOINT) {
      expect(answers.some((answer) => answer.file === file && answer.status === 403), `${file} answers with a 403 the reader reads`).toBe(true)
    }
    const unclassified = answers.filter((answer) => !NO_RETRY_HELPS.has(answer.status) && !A_RETRY_CAN_HELP.has(answer.status))
    expect(unclassified.map((answer) => `${answer.file}:${answer.line} ${answer.status}`), 'say here whether a retry can help this status').toEqual([])
    const misread = answers
      .filter((answer) => isNonRetryableStreamError(answer.text) !== NO_RETRY_HELPS.has(answer.status))
      .map((answer) => `${answer.file}:${answer.line} ${answer.status} "${answer.text}"`)
    expect(
      misread,
      'a 403 must match isNonRetryableStreamError (features/summaries/api/summaries-api.ts) in its own words, or its card ' +
        'offers a Retry that repeats it; a 401, 404 or 429 must not',
    ).toEqual([])
  })

  it('prints every answer the stream endpoint gives in the product voice, mapped or passed through', () => {
    // STREAM_ERROR_COPY's lines are held to the voice below; an answer the map does not hold reaches the card as the
    // backend wrote it (the account check's since E45), so its own words are held here, read from the Python.
    const offVoice = endpointErrors()
      .map((answer) => ({ answer, shown: streamErrorCopy(answer.text) }))
      .filter(({ shown }) => shown.includes(EM_DASH) || shown.includes('!') || !/^[A-Z].*[.…]$/.test(shown))
      .map(({ answer, shown }) => `${answer.file}:${answer.line} ${answer.status} "${shown}"`)
    expect(
      offVoice,
      'what the card prints for an endpoint answer reads as a sentence, with no em-dash and no exclamation mark: ' +
        'reword the backend detail, or map it in STREAM_ERROR_COPY',
    ).toEqual([])
  })

  it('spells a displayed em-dash only as the character', () => {
    const users = execFileSync('git', ['ls-files', 'app', 'components', 'features', 'hooks', 'lib'], { cwd: FRONTEND, encoding: 'utf8' })
      .split('\n')
      .filter((rel) => /\.(?:[cm]?js|jsx|ts|tsx)$/.test(rel) && !/\.d\.ts$/.test(rel))
    expect(users.length, 'the walk found the app').toBeGreaterThan(300)
    // By file and spelling, not line: the one allowed site may move within its file.
    const found = users.flatMap((rel) => hiddenDashes(readFileSync(path.join(FRONTEND, rel), 'utf8'), rel)).map((site) => site.replace(/:\d+ /, ' '))
    expect(found, 'spell no displayed em-dash any way but the character; no-em-dash-copy.spec.ts cannot see the others').toEqual([])
    // Each spelling, planted; a code computed from a value the file does not state is out of reach.
    const spellings: Record<string, string> = {
      'a hex char code': 'const d = String.fromCharCode(0x2014)',
      'an upper-case hex char code': 'const d = String.fromCharCode(0X2014)',
      'a decimal char code': 'const d = String.fromCharCode(8212)',
      'an octal code point': 'const d = String.fromCodePoint(0o20024)',
      'a char code held in a const': 'const EM = 0x2014\nconst d = String.fromCharCode(EM)',
      'a char code from arithmetic': 'const d = String.fromCharCode(0x2000 + 20)',
      'a char code among others': "const d = String.fromCharCode(32, 0x2014, 32)",
      'a unicode escape': "const d = 'a \\u2014 b'",
      'a code point escape in a template': 'const d = `a \\u{2014} b`',
      'an entity in JSX text': 'const d = <p>a &mdash; b</p>',
      'a decimal entity in JSX text': 'const d = <p>a &#8212; b</p>',
      'a hex entity in an attribute': 'const d = <p title="a &#x2014; b">x</p>',
    }
    expect(Object.entries(spellings).filter(([, code]) => hiddenDashes(code, 'p.tsx').length !== 1).map(([name]) => name), 'a spelling the leg missed').toEqual([])
    const lookAlikes: Record<string, string> = {
      'a letter from a code': 'const d = String.fromCharCode(97 + (n - 1) % 26)',
      'an en dash code': 'const d = String.fromCharCode(0x2013)',
      'a regex literal with the escape': 'const SOURCE_DASH = /\\s*\\u2014\\s*/g',
      'an en dash entity': 'const d = <p>2019&ndash;2024</p>',
    }
    expect(Object.entries(lookAlikes).filter(([, code]) => hiddenDashes(code, 'p.tsx').length !== 0).map(([name]) => name), 'a look-alike the leg flagged').toEqual([])
    expect(hiddenDashes('const d = String.fromCharCode(code)', 'p.tsx'), 'a gap: a code the file does not state').toEqual([])
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
    expect(streamErrorCopy("We couldn't generate this summary just now. Please try again shortly.")).toBe(
      'We could not generate this summary. Try again shortly.',
    )
    expect(streamErrorCopy('We could not generate this summary. Try again shortly.')).toBe(
      'We could not generate this summary. Try again shortly.',
    )
    expect(streamErrorCopy('The filing could not be summarized right now.')).toBe('The filing could not be summarized right now.')
    expect(streamErrorCopy(null)).toBe('')
  })
})
