import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { isPaywallStreamError } from '@/features/summaries/api/summaries-api'
import { STREAM_ERROR_COPY, streamErrorCopy } from '@/features/summaries/lib/streamErrorCopy'

/**
 * The summary stream's error sentences are written in the backend pipeline (summary_stages), which stays
 * untouched until the founder opens it, so the filing page maps each one to the product's words
 * (features/summaries/lib/streamErrorCopy.ts, brand sweep filing/F48). This gate holds the map to the
 * Python source:
 *
 *  1. Coverage: every sentence fetch.py, failure.py and admission.py stream as an error (a literal in an
 *     `{'type': 'error', 'message': …}` dict, or a literal assigned to the name such a dict sends), and
 *     every streamed message that carries an em-dash, has its line in STREAM_ERROR_COPY, keyed by the
 *     exact Python text (f-string fields as `{name}`). A reworded backend sentence fails until the map
 *     follows it, so the page never prints a sentence nobody mapped.
 *  2. No stale lines: every key is still written by a summary stage.
 *  3. Parity: the raw message, not the mapped one, decides the card. Exactly one admission.py error
 *     sentence opens the paywall card (the free monthly limit; Pro's fair-use pause never upsells), and it
 *     carries every phrase isPaywallStreamError routes on; every phrase isNonRetryableStreamError routes
 *     on is still written by the stream's writers (the backend modules, the client's own fallbacks).
 *  4. Voice: what the page shows has no em-dash, no exclamation mark, and reads as a sentence.
 */

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const REPO = path.resolve(FRONTEND, '..')
const STAGES = path.join(REPO, 'backend/app/services/summary_stages')
const STREAMED = ['fetch.py', 'failure.py', 'admission.py']
const EM_DASH = '—'

type Token = { kind: 'str' | 'name' | 'op'; text: string; line: number }

/** Python source as tokens: string literals (prefix and quotes dropped, escapes kept as written), names
    and single-character operators. Comments and whitespace are skipped. */
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
      i += prefix[0].length
      const quote = src.startsWith('"""', i) ? '"""' : src.startsWith("'''", i) ? "'''" : src[i]
      i += quote.length
      let text = ''
      while (i < src.length && !src.startsWith(quote, i)) {
        if (src[i] === '\n') line++
        if (src[i] === '\\') {
          text += src.slice(i, i + 2)
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

/** The messages one stage module streams: each error dict's message (a literal, or every literal assigned
    to the name it sends) and every other `'message': <literal>`. */
export function streamedMessages(src: string, file: string): Streamed[] {
  const toks = pythonTokens(src)
  const out: Streamed[] = []
  const assigned = (name: string) =>
    toks.flatMap((t, j) =>
      t.kind === 'name' && t.text === name && isOp(toks[j + 1], '=') && !isOp(toks[j + 2], '=') ? [literalAt(toks, j + 2)] : [],
    ).filter((lit): lit is { text: string; line: number } => lit !== null)
  toks.forEach((t, k) => {
    if (!isStr(t, 'message') || !isOp(toks[k + 1], ':')) return
    const bounds = dictAround(toks, k)
    const error = !!bounds && toks.slice(bounds[0], bounds[1]).some((u, j, all) => isStr(u, 'type') && isOp(all[j + 1], ':') && isStr(all[j + 2], 'error'))
    const literal = literalAt(toks, k + 2)
    if (literal) out.push({ file, line: literal.line, text: literal.text, error })
    else if (error && toks[k + 2]?.kind === 'name') {
      for (const lit of assigned(toks[k + 2].text)) out.push({ file, line: lit.line, text: lit.text, error })
    }
  })
  return out
}

const stageSource = (file: string) => readFileSync(path.join(STAGES, file), 'utf8')
const streamed = () => STREAMED.flatMap((file) => streamedMessages(stageSource(file), file))

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
  it('reads the stage modules (a reader that finds nothing must not pass)', () => {
    const errors = streamed().filter((m) => m.error)
    for (const file of STREAMED) expect(errors.some((m) => m.file === file), `${file} streams an error sentence`).toBe(true)
    expect(streamedMessages(`x = {'type': 'error', 'message': msg}\nmsg = ("a " f"{b}")  # 'c'\n`, 't.py')).toEqual([
      { file: 't.py', line: 2, text: 'a {b}', error: true },
    ])
  })

  it('maps every error sentence fetch.py, failure.py and admission.py stream, and every em-dash message', () => {
    const unmapped = streamed()
      .filter((m) => m.error || m.text.includes(EM_DASH))
      .filter((m) => !(m.text in STREAM_ERROR_COPY))
      .map((m) => `summary_stages/${m.file}:${m.line} ${m.text}`)
    expect(unmapped, 'add the sentence to STREAM_ERROR_COPY (features/summaries/lib/streamErrorCopy.ts), keyed by its exact Python text').toEqual([])
  })

  it('keeps no line for a sentence no summary stage writes any more', () => {
    const written = new Set<string>()
    for (const file of readdirSync(STAGES).filter((f) => f.endsWith('.py'))) {
      const toks = pythonTokens(stageSource(file))
      toks.forEach((_, k) => {
        const lit = literalAt(toks, k)
        if (lit) written.add(lit.text)
      })
    }
    expect(Object.keys(STREAM_ERROR_COPY).filter((key) => !written.has(key)), 'delete the stale line from STREAM_ERROR_COPY').toEqual([])
  })

  it('leaves the routing words in the sentences the matchers must catch', () => {
    const admission = streamed().filter((m) => m.file === 'admission.py' && m.error)
    const paywall = admission.filter((m) => isPaywallStreamError(m.text))
    expect(paywall.map((m) => m.text), 'exactly one admission.py error sentence opens the paywall card (the free monthly limit)').toHaveLength(1)
    for (const phrase of matcherPhrases('isPaywallStreamError')) {
      expect(paywall[0].text.toLowerCase(), `the paywall sentence carries "${phrase}"`).toContain(phrase)
    }
    for (const m of streamed().filter((s) => s.error && s.file !== 'admission.py')) {
      expect(isPaywallStreamError(m.text), `${m.file}:${m.line} must not open the paywall card`).toBe(false)
    }
    const writers = [
      ...['backend/app/routers/summaries.py', 'backend/app/services/summary_stages/admission.py'].flatMap((rel) =>
        pythonTokens(readFileSync(path.join(REPO, rel), 'utf8')).filter((t) => t.kind === 'str').map((t) => t.text),
      ),
      ...frontendStrings('features/summaries/api/summaries-api.ts').filter((s) => !/^[a-z ]+$/.test(s)),
      ...frontendStrings('features/summaries/hooks/useSummaryGeneration.ts'),
    ].map((s) => s.toLowerCase())
    for (const phrase of matcherPhrases('isNonRetryableStreamError')) {
      expect(writers.some((s) => s.includes(phrase)), `a stream writer still says "${phrase}"`).toBe(true)
    }
  })

  it('shows sentences in the product voice and passes an unmapped message through', () => {
    for (const shown of Object.values(STREAM_ERROR_COPY)) {
      expect(shown, 'no em-dash in what the page shows').not.toContain(EM_DASH)
      expect(shown).not.toContain('!')
      expect(shown).toMatch(/^[A-Z].*[.…]$/)
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
