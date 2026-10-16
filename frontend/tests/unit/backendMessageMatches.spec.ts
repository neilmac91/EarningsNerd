import { existsSync, readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * The frontend routes some UI on the words of an error message: the paywall card instead of Retry, no
 * automatic retry for a permission or sign-in error, the verify-your-email event, the dashboard's sign-in
 * redirect. Those words are written in the backend (an
 * HTTPException detail, a stream error) or in the frontend's own fallback for a status, so a copy edit on
 * either side can silently switch the UI off. Until an error code field replaces the matching
 * (tasks/todo.md), this gate holds both sides together (docs/brand/decisions-log.md D-031):
 *
 *  1. Every phrase a matcher in MATCHERS tests for occurs, case-insensitively, in a string literal of one
 *     of the files that write that message: the backend modules that raise it (read as Python source,
 *     comments and docstrings ignored, adjacent literals joined as Python joins them) or a frontend file,
 *     listed only when the message is the frontend's own (a fallback for a status, such as those in
 *     lib/api/client.ts or summaries-api.ts). A phrase nobody writes fails, unless UNSOURCED lists it
 *     with its reason (shrink-only; its size equals UNSOURCED_MAX, which moved with the scan's reach on
 *     the day the scan reached a site and only falls after).
 *  2. Matching is confined to MATCHERS. The scan reads `.includes('…')`, `.startsWith('…')`,
 *     `.endsWith('…')`, `.match(/…/)`, `.search(/…/)` and `/…/.test(…)` on a literal in two passes:
 *     every such test in the api modules (lib/api/client.ts, the rest of lib/api and features/<domain>/api),
 *     and, across app, components, features, hooks and lib, every such test whose receiver (the argument
 *     of a regex `.test`) names an error or a message: its identifiers, once a trailing `.toLowerCase()`
 *     or `.trim()` is stripped and each is split at camelCase and non-letter boundaries, include one of
 *     MESSAGE_WORDS (err, error, message, msg, detail, reason). A test found outside a MATCHERS function
 *     fails unless NOT_MESSAGES lists it as a test on something other than a message the code writes.
 *     The limits, outside the api modules: a message held under another name (`text`, `m`, `body`) is
 *     not read; MESSAGE_WORDS are whole words, so a plural receiver (`errors`, `messages`, `reasons`,
 *     `fieldErrors`) is not read, nor a bracket-keyed one (`obj['message']`, whose key is a string, not
 *     an identifier); and only the six literal tests above are read, so an equality test (`===`), an
 *     `indexOf` and a test whose argument is a constant (`msg.includes(PHRASE)`) are outside the scan.
 *     The third review (at 0930834d) parsed every module under those roots and found no message test
 *     in any of these shapes: the equality tests on an error-named receiver compare codes
 *     (`data?.error === 'already_registered'`, `err.name === 'AbortError'`), not message words.
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
    // The summary stream's own sources only. Its 401 comes from get_current_user (routers/auth.py),
    // "Could not validate credentials", which summaries-api.ts surfaces as the detail in place of its
    // fallback ("Sign in again to generate this summary.", the source of "sign in"); the matcher never sees
    // a 401, which comes back retryable: false by status. auth.py's other messages (sign-in configuration, login) never reach
    // the stream, and useSummaryGeneration's guest message is set beside the stream, never matched.
    backend: [BACKEND.summaries, BACKEND.admission],
    frontend: ['features/summaries/api/summaries-api.ts'],
  },
  { file: 'features/filings/api/copilot-api.ts', fn: 'isCopilotPaywallError', backend: [BACKEND.dependencies, BACKEND.summaries], frontend: ['features/filings/api/copilot-api.ts'] },
  { file: 'features/analysis/api/analysis-api.ts', fn: 'isAnalysisPaywallError', backend: [BACKEND.dependencies, BACKEND.analysis], frontend: ['features/analysis/api/analysis-api.ts'] },
  { file: 'lib/api/client.ts', backend: [BACKEND.subscriptions], frontend: [] },
  // Reached by the tree-wide pass (a test on error.message). An error boundary sees what a render throws:
  // no dashboard query throws to it (no throwOnError, no suspense query), and the 401 a signed-in request
  // gets reads get_current_user's "Could not validate credentials" (routers/auth.py), which none of its
  // phrases match. No source is listed: auth.py's and lib/api/client.ts's route paths ("/api/auth/…")
  // would pass "auth" on a URL, not a message.
  { file: 'app/dashboard/error.tsx', fn: 'DashboardError', backend: [], frontend: [] },
]

/** Phrases no file writes today, each with its reason. Shrink-only: delete the line when the phrase is
    written again or dropped from its matcher, and lower UNSOURCED_MAX in the same commit. */
const DASHBOARD_UNSOURCED =
  "no message that reaches the dashboard's error boundary says it (see MATCHERS); the redirect's logic is E31's (a status or an error code), never the brand sweep's"
const UNSOURCED: Record<string, string> = {
  'isCopilotPaywallError monthly cap':
    "no message says it: the Copilot cap's 429 says \"fair-use limit\" (routers/summaries.py), which this matcher does not read; the matcher's owner (brand-copilot, ASK-07) decides",
  'DashboardError 401': DASHBOARD_UNSOURCED,
  'DashboardError Unauthorized': DASHBOARD_UNSOURCED,
  'DashboardError authentication': DASHBOARD_UNSOURCED,
  'DashboardError auth': DASHBOARD_UNSOURCED,
}
/** Seeded at 2 when the api modules were scanned; raised to 7 when the scan reached app/dashboard/error.tsx
    and ContactForm.tsx (2026-10-13); lowered to 6 when #1303 read the contact form's rate limit from the status
    (2026-10-15), so ContactForm.tsx tests no message word; lowered to 5 when #1293's 401 fallback wrote
    "Sign in again to generate this summary." (2026-10-16), so "sign in" has a source. It only falls after. */
const UNSOURCED_MAX = 5

/** Literal tests the scan reads that test something other than a message the code writes. */
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
  'features/summaries/hooks/useSummaryGeneration.ts includes timeout': "axios's own error message (\"timeout of …ms exceeded\"), not the backend's: the test lib/api/client.ts makes",
}

const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']
/** A receiver named with one of these words holds an error or a message. */
const MESSAGE_WORDS = new Set(['err', 'error', 'message', 'msg', 'detail', 'reason'])
/** Calls that change a message's case or spacing, not what it is: stripped before the receiver is named. */
const CASE_CALLS = new Set(['toLowerCase', 'toUpperCase', 'toLocaleLowerCase', 'toLocaleUpperCase', 'trim', 'trimStart', 'trimEnd'])

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
  return ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
}

const visit = (node: ts.Node, fn: (n: ts.Node) => void) => {
  fn(node)
  ts.forEachChild(node, (child) => visit(child, fn))
}

/** A literal test in frontend source: `x.includes('…')`, `x.startsWith('…')`, `x.match(/…/)`, `/…/.test(x)`,
    with the expression it reads (`x`; absent for a `.test()` with no argument). */
function literalTest(node: ts.Node): { kind: string; text: string; regex: boolean; subject?: ts.Expression } | null {
  if (!ts.isCallExpression(node) || !ts.isPropertyAccessExpression(node.expression)) return null
  const method = node.expression.name.text
  const arg = node.arguments[0]
  const receiver = node.expression.expression
  if (['includes', 'startsWith', 'endsWith'].includes(method) && arg && ts.isStringLiteralLike(arg)) return { kind: method, text: arg.text, regex: false, subject: receiver }
  if (['match', 'search'].includes(method) && arg && ts.isRegularExpressionLiteral(arg)) return { kind: method, text: regexSource(arg), regex: true, subject: receiver }
  if (method === 'test' && ts.isRegularExpressionLiteral(receiver)) return { kind: 'test', text: regexSource(receiver), regex: true, subject: arg }
  return null
}

/** The words an expression is named with: its identifiers, after trailing case and trim calls are
    stripped, split at camelCase and non-letter boundaries and lower-cased (`errorMessage` gives error
    and message; `document.referrer` gives document and referrer). */
export function receiverWords(expr: ts.Expression): string[] {
  let e = expr
  while (ts.isCallExpression(e) && ts.isPropertyAccessExpression(e.expression) && CASE_CALLS.has(e.expression.name.text) && !e.arguments.length) e = e.expression.expression
  const words: string[] = []
  visit(e, (n) => {
    if (ts.isIdentifier(n) || ts.isPrivateIdentifier(n)) {
      for (const part of n.text.split(/[^A-Za-z]+/)) words.push(...(part.match(/[A-Z]?[a-z]+|[A-Z]+(?![a-z])/g) ?? []).map((w) => w.toLowerCase()))
    }
  })
  return words
}

/** The literal tests a source reads that name an error or a message (the tree-wide pass). */
export function messageTests(sf: ts.SourceFile): Array<{ node: ts.Node; kind: string; text: string }> {
  const out: Array<{ node: ts.Node; kind: string; text: string }> = []
  visit(sf, (n) => {
    const test = literalTest(n)
    if (test?.subject && receiverWords(test.subject).some((w) => MESSAGE_WORDS.has(w))) out.push({ node: n, kind: test.kind, text: test.text })
  })
  return out
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
        else missing.push(`${matcher.file} ${matcher.fn ?? ''} tests for "${phrase.text}", which ${files.length ? `none of ${files.map((f) => f.file).join(', ')} writes` : 'no listed source writes'}`)
      }
    }
    expect(missing, 'keep the phrase in the message (backend and frontend together), or change the matcher in the same PR').toEqual([])
    // Equality, not a ceiling: a PR that shrinks the list lowers the cap in the same commit.
    expect(Object.keys(UNSOURCED).length, 'UNSOURCED changed size: move UNSOURCED_MAX with it in the same commit').toBe(UNSOURCED_MAX)
    expect(Object.keys(UNSOURCED).filter((key) => !unsourced.has(key)), 'written again or gone from its matcher: delete it from UNSOURCED').toEqual([])
  })

  it('the tree-wide pass reads a test on an error or a message, and nothing else', () => {
    const probe = ts.createSourceFile('probe.tsx', [
      "const a = error.message.includes('read: message receiver')",
      "const b = errorMessage.includes('read: camelCase receiver')",
      "const c = err?.message?.toLowerCase().trim().includes('read: case calls stripped')",
      "const d = /read: regex test argument/.test(backendDetail)",
      "const e = String(reason).startsWith('read: wrapped receiver')",
      "const f = pathname.startsWith('/not: a path')",
      "const g = items.includes('not: an array')",
      "const h = document.referrer.includes('not: referrer')",
      "const i = 'error text'.includes('not: a literal receiver')",
    ].join('\n'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
    expect(messageTests(probe).map((t) => t.text)).toEqual([
      'read: message receiver', 'read: camelCase receiver', 'read: case calls stripped', 'read: regex test argument', 'read: wrapped receiver',
    ])
  })

  it('no other literal test on an error message: all of the api modules, and every message receiver tree-wide', () => {
    const api = ['lib/api/client.ts', ...readDirApi()]
    const tree = SCAN_DIRS.flatMap((dir) => walk(dir)).filter((file) => !api.includes(file))
    const tested = new Set<string>()
    const untabled: string[] = []
    const check = (file: string, sf: ts.SourceFile, n: ts.Node, kind: string, text: string) => {
      const inMatcher = MATCHERS.some((m) => {
        if (m.file !== file || !m.fn) return false
        const decl = declaration(sf, m.fn)
        return !!decl && n.pos >= decl.pos && n.end <= decl.end
      })
      if (inMatcher) return
      if (file === 'lib/api/client.ts' && kind === 'test') return // the verify-email matcher (MATCHERS)
      const key = `${file} ${kind} ${text}`
      if (key in NOT_MESSAGES) tested.add(key)
      else untabled.push(`${file}:${sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1} ${key}`)
    }
    for (const file of api) {
      const sf = parse(file)
      visit(sf, (n) => {
        const test = literalTest(n)
        if (test) check(file, sf, n, test.kind, test.text)
      })
    }
    expect(tree.length, 'the tree-wide pass found no files').toBeGreaterThan(100)
    for (const file of tree) {
      const sf = parse(file)
      for (const { node, kind, text } of messageTests(sf)) check(file, sf, node, kind, text)
    }
    expect(untabled, 'route on a message through a MATCHERS function (with its sources), or list a non-message test in NOT_MESSAGES').toEqual([])
    expect(Object.keys(NOT_MESSAGES).filter((key) => !tested.has(key)), 'no longer in the code: delete it from NOT_MESSAGES').toEqual([])
  }, 30_000) // it parses every source under the scan's directories; the default 5s times out on a loaded box
})

/** Frontend-relative .ts and .tsx sources under a directory, specs and declarations skipped. */
function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(path.join(FRONTEND, dir), { withFileTypes: true })) {
    const rel = `${dir}/${entry.name}`
    if (entry.isDirectory()) walk(rel, out)
    else if (/\.tsx?$/.test(entry.name) && !/\.(spec|test)\.tsx?$|\.d\.ts$/.test(entry.name)) out.push(rel)
  }
  return out
}

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
