import { existsSync, readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * The frontend routes some UI on the words of an error message: the paywall card instead of Retry, no
 * automatic retry for a permission or sign-in error, the verify-your-email event. Those words are written in the backend (an HTTPException
 * detail, a stream error) or in the frontend's own fallback for a status, so a copy edit on either side
 * can silently switch the UI off. Until an error code field replaces the matching (tasks/todo.md), this
 * gate holds both sides together (docs/brand/decisions-log.md D-031):
 *
 *  1. Every phrase a matcher in MATCHERS tests for occurs, case-insensitively, in a string literal of one
 *     of the files that write that message: the backend modules that raise it (read as Python source,
 *     comments and docstrings ignored, adjacent literals joined as Python joins them) or the frontend
 *     fallbacks beside it. A phrase nobody writes any more fails, unless UNSOURCED lists it with its
 *     reason (shrink-only, capped at its seed: UNSOURCED_MAX).
 *  2. Matching is confined to MATCHERS: any other `.includes('…')`, `.startsWith('…')`, `.endsWith('…')`, `.match(/…/)` or
 *     `/…/.test(…)` on a literal under features/<domain>/api or lib/api fails, unless NOT_MESSAGES lists
 *     it as a test on something other than an error message.
 */

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const REPO = path.resolve(FRONTEND, '..')

const BACKEND = {
  dependencies: 'backend/app/dependencies.py',
  admission: 'backend/app/services/summary_stages/admission.py',
  summaries: 'backend/app/routers/summaries.py',
  analysis: 'backend/app/routers/analysis.py',
  subscriptions: 'backend/app/routers/subscriptions.py',
}

interface Matcher {
  /** The frontend module and the function in it whose phrases are read; no function: every regex `.test()` in the module. */
  file: string
  fn?: string
  /** The files that write the messages it matches: repo-relative backend modules, frontend-relative fallbacks. */
  backend: string[]
  frontend: string[]
}

const MATCHERS: Matcher[] = [
  { file: 'features/summaries/api/summaries-api.ts', fn: 'isPaywallStreamError', backend: [BACKEND.admission, BACKEND.dependencies, BACKEND.summaries], frontend: [] },
  {
    file: 'features/summaries/api/summaries-api.ts',
    fn: 'isNonRetryableStreamError',
    // The summary stream's own sources only: auth.py's Apple configuration error never reaches this
    // stream, and useSummaryGeneration's guest message is set beside the stream, never matched.
    backend: [BACKEND.summaries, BACKEND.admission],
    frontend: ['features/summaries/api/summaries-api.ts'],
  },
  { file: 'features/filings/api/copilot-api.ts', fn: 'isCopilotPaywallError', backend: [BACKEND.dependencies, BACKEND.summaries], frontend: ['features/filings/api/copilot-api.ts'] },
  { file: 'features/analysis/api/analysis-api.ts', fn: 'isAnalysisPaywallError', backend: [BACKEND.dependencies, BACKEND.analysis], frontend: ['features/analysis/api/analysis-api.ts'] },
  { file: 'lib/api/client.ts', backend: [BACKEND.subscriptions], frontend: [] },
]

/** Phrases no file writes today, each with its reason. Shrink-only: delete the line when the phrase is
    written again or dropped from its matcher. */
const UNSOURCED: Record<string, string> = {
  'isCopilotPaywallError monthly cap':
    "no message says it: the Copilot cap's 429 says \"fair-use limit\" (routers/summaries.py), which this matcher does not read; the matcher's owner (brand-copilot, ASK-07) decides",
  'isNonRetryableStreamError sign in':
    'no message on the summary stream says it: its 401 reads "Authentication error occurred." (matched by "authentication"); the matcher\'s logic is E18\'s (an error code field), never the brand sweep\'s',
}
const UNSOURCED_MAX = 2

/** Literal tests in the api modules that read something other than an error message. */
const NOT_MESSAGES: Record<string, string> = {
  'features/analysis/api/analysis-api.ts startsWith data:': 'an SSE frame prefix',
  'features/filings/api/copilot-api.ts test ^f\\s*\\d+$': 'a citation id',
  'features/filings/api/copilot-api.ts startsWith XBRL': 'a section reference (two sites)',
  'features/filings/api/copilot-api.ts test ^f\\s*[1-9]\\d*$': 'a citation id',
  'features/filings/api/copilot-api.ts startsWith data:': 'an SSE frame prefix',
  'features/summaries/api/summaries-api.ts startsWith data: ': 'an SSE frame prefix',
  'lib/api/client.ts includes Network Error': "axios's own error message, not the backend's",
  'lib/api/client.ts includes ECONNREFUSED': "axios's own error code, not the backend's",
  'lib/api/client.ts includes timeout': "axios's own error message, not the backend's",
}

/** Every string literal in Python source, comments and docstrings skipped, with adjacent literals also
    joined (Python concatenates `"a " "b"` across whitespace, parentheses and line breaks). A docstring
    is a literal that opens the first statement of the module or of a `def` or `class` body: it
    documents the code, it is never a message. */
export function pythonStrings(src: string): string[] {
  const out: string[] = []
  let run = ''
  let runEnd = -1
  let i = 0
  // The logical line so far (code only, a literal read as ""), the last complete one (null at the
  // module's start) and the bracket depth, which joins physical lines into one logical line.
  let line = ''
  let previous: string | null = null
  let depth = 0
  while (i < src.length) {
    const c = src[i]
    if (c === '#') {
      while (i < src.length && src[i] !== '\n') i++
      continue
    }
    if (c === '\n' && depth === 0 && !line.endsWith('\\')) {
      if (line.trim()) previous = line.trim()
      line = ''
      i++
      continue
    }
    const prefix = /^[rRbBuUfF]{0,2}(?="|')/.exec(src.slice(i, i + 3))
    if (prefix && (i === 0 || !/\w/.test(src[i - 1]))) {
      const start = i
      const docstring = !line.trim() && (previous === null || /^(?:async\s+)?(?:def|class)\b[\s\S]*:$/.test(previous))
      i += prefix[0].length
      const quote = src.startsWith('"""', i) ? '"""' : src.startsWith("'''", i) ? "'''" : src[i]
      i += quote.length
      let text = ''
      while (i < src.length && !src.startsWith(quote, i)) {
        if (src[i] === '\\') {
          text += src.slice(i, i + 2)
          i += 2
        } else text += src[i++]
      }
      i += quote.length
      line += '""'
      if (docstring) {
        runEnd = -1
        continue
      }
      out.push(text)
      run = runEnd >= 0 && /^[\s()\\]*$/.test(src.slice(runEnd, start).replace(/#[^\n]*/g, '')) ? run + text : text
      runEnd = i
      if (run !== text) out.push(run)
      continue
    }
    if ('([{'.includes(c)) depth++
    else if (')]}'.includes(c)) depth = Math.max(0, depth - 1)
    line += c
    i++
  }
  return out
}

const parse = (file: string) => {
  const text = readFileSync(path.join(FRONTEND, file), 'utf8')
  return ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
}

const visit = (node: ts.Node, fn: (n: ts.Node) => void) => {
  fn(node)
  ts.forEachChild(node, (child) => visit(child, fn))
}

/** A literal test in frontend source: `x.includes('…')`, `x.startsWith('…')`, `x.match(/…/)`, `/…/.test(x)`. */
function literalTest(node: ts.Node): { kind: string; text: string; regex: boolean } | null {
  if (!ts.isCallExpression(node) || !ts.isPropertyAccessExpression(node.expression)) return null
  const method = node.expression.name.text
  const arg = node.arguments[0]
  if (['includes', 'startsWith', 'endsWith'].includes(method) && arg && ts.isStringLiteralLike(arg)) return { kind: method, text: arg.text, regex: false }
  if (['match', 'search'].includes(method) && arg && ts.isRegularExpressionLiteral(arg)) return { kind: method, text: regexSource(arg), regex: true }
  if (method === 'test' && ts.isRegularExpressionLiteral(node.expression.expression)) return { kind: 'test', text: regexSource(node.expression.expression), regex: true }
  return null
}

const regexSource = (re: ts.RegularExpressionLiteral) => re.text.slice(1, re.text.lastIndexOf('/'))

/** The function or const named `name` in a source file. */
function declaration(sf: ts.SourceFile, name: string): ts.Node | undefined {
  let found: ts.Node | undefined
  visit(sf, (n) => {
    if (!found && (ts.isFunctionDeclaration(n) || ts.isVariableDeclaration(n)) && n.name && ts.isIdentifier(n.name) && n.name.text === name) found = n
  })
  return found
}

/** The phrases a matcher tests for. */
function phrases(matcher: Matcher): Array<{ text: string; regex: boolean }> {
  const sf = parse(matcher.file)
  const scope = matcher.fn ? declaration(sf, matcher.fn) : sf
  if (!scope) throw new Error(`${matcher.file}: ${matcher.fn} is gone; update MATCHERS`)
  const out: Array<{ text: string; regex: boolean }> = []
  visit(scope, (n) => {
    const test = literalTest(n)
    // In a matcher function every literal test is a phrase (includes, startsWith, endsWith, a regex).
    if (test && (matcher.fn || test.kind === 'test')) out.push({ text: test.text, regex: test.regex })
  })
  return out
}

/** The string literals a frontend fallback module writes, its own literal tests excluded. */
function frontendStrings(file: string): string[] {
  const sf = parse(file)
  const out: string[] = []
  visit(sf, (n) => {
    if ((ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)) && !(n.parent && literalTest(n.parent))) out.push(n.text)
    if (ts.isTemplateExpression(n)) out.push([n.head.text, ...n.templateSpans.map((s) => s.literal.text)].join(' '))
  })
  return out
}

const sources = (matcher: Matcher) => [
  ...matcher.backend.map((file) => ({ file, strings: pythonStrings(readFileSync(path.join(REPO, file), 'utf8')) })),
  ...matcher.frontend.map((file) => ({ file, strings: frontendStrings(file) })),
]

const found = (phrase: { text: string; regex: boolean }, strings: string[]) =>
  strings.some((s) => (phrase.regex ? new RegExp(phrase.text, 'i').test(s) : s.toLowerCase().includes(phrase.text.toLowerCase())))

describe('the frontend routes UI only on words the code writes', () => {
  it('reads each matcher (a reader that finds nothing must not pass)', () => {
    for (const matcher of MATCHERS) expect(phrases(matcher).length, `${matcher.file} ${matcher.fn ?? 'regex tests'}`).toBeGreaterThan(0)
    expect(pythonStrings('x = ("a "  # note\n     f"b {y}")\n# "not a string"\n')).toEqual(['a ', 'b {y}', 'a b {y}'])
    // Docstrings document code, never a message; a literal that opens any other statement is kept.
    const docstrings = [
      '"""Module docstring: sign in."""',
      'class Gate(Base):',
      '    """Class docstring."""',
      '    async def check(',
      '        self, user: User,',
      '    ) -> None:',
      "        '''Method docstring.'''",
      '        raise HTTPException(status_code=401, detail="Please sign in.")',
      'def bare():',
      '    "Function docstring."',
      '"""A later bare literal is no docstring."""',
    ].join('\n')
    expect(pythonStrings(docstrings)).toEqual(['Please sign in.', 'A later bare literal is no docstring.'])
  })

  it('every phrase a matcher tests for is written by a file that raises the message', () => {
    const missing: string[] = []
    const unsourced = new Set<string>()
    for (const matcher of MATCHERS) {
      const files = sources(matcher)
      for (const phrase of phrases(matcher)) {
        const key = `${matcher.fn ?? matcher.file} ${phrase.text}`
        if (files.some(({ strings }) => found(phrase, strings))) continue
        if (key in UNSOURCED) unsourced.add(key)
        else missing.push(`${matcher.file} ${matcher.fn ?? ''} tests for "${phrase.text}", which none of ${files.map((f) => f.file).join(', ')} writes`)
      }
    }
    expect(missing, 'keep the phrase in the message (backend and frontend together), or change the matcher in the same PR').toEqual([])
    expect(Object.keys(UNSOURCED).length, 'UNSOURCED gained an entry').toBeLessThanOrEqual(UNSOURCED_MAX)
    expect(Object.keys(UNSOURCED).filter((key) => !unsourced.has(key)), 'written again or gone from its matcher: delete it from UNSOURCED').toEqual([])
  })

  it('no other literal test on an error message under features/<domain>/api or lib/api', () => {
    const files = ['lib/api/client.ts', ...readDirApi()]
    const tested = new Set<string>()
    const untabled: string[] = []
    for (const file of files) {
      const sf = parse(file)
      const inMatcher = (n: ts.Node) => MATCHERS.some((m) => m.file === file && m.fn && (() => {
        const decl = declaration(sf, m.fn!)
        return !!decl && n.pos >= decl.pos && n.end <= decl.end
      })())
      visit(sf, (n) => {
        const test = literalTest(n)
        if (!test || inMatcher(n)) return
        if (file === 'lib/api/client.ts' && test.kind === 'test') return // the verify-email matcher (MATCHERS)
        const key = `${file} ${test.kind} ${test.text}`
        if (key in NOT_MESSAGES) tested.add(key)
        else untabled.push(`${file}:${sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1} ${key}`)
      })
    }
    expect(untabled, 'route on a message through a MATCHERS function (with its sources), or list a non-message test in NOT_MESSAGES').toEqual([])
    expect(Object.keys(NOT_MESSAGES).filter((key) => !tested.has(key)), 'no longer in the code: delete it from NOT_MESSAGES').toEqual([])
  })
})

function readDirApi(): string[] {
  const out: string[] = []
  for (const domain of readdirSync(path.join(FRONTEND, 'features'))) {
    const dir = path.join(FRONTEND, 'features', domain, 'api')
    if (!existsSync(dir)) continue
    for (const entry of readdirSync(dir)) if (/\.tsx?$/.test(entry) && !/\.spec\./.test(entry)) out.push(`features/${domain}/api/${entry}`)
  }
  for (const entry of readdirSync(path.join(FRONTEND, 'lib/api'))) if (/\.tsx?$/.test(entry) && entry !== 'client.ts') out.push(`lib/api/${entry}`)
  return out
}
