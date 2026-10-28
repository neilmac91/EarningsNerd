import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { CanceledError, type InternalAxiosRequestConfig } from 'axios'
import { QueryClient } from '@tanstack/react-query'
import { bindingResolver } from './astBindings'

// The refresh is mocked so each case decides when it answers; the cookies it carries and sets are modelled below.
vi.mock('@/lib/api/refresh', () => ({ refreshAccessToken: vi.fn() }))

import api, { ensureRefreshed } from '@/lib/api/client'
import { refreshAccessToken } from '@/lib/api/refresh'
import { postStreamWithRefresh } from '@/lib/api/streamRefresh'
import { LOGIN_REFRESH_WAIT_MS, login } from '@/features/auth/api/auth-api'
import { acceptLoginAndResetAccount } from '@/features/auth/lib/accountQueryState'
import { clearSessionActive, getExplicitSessionGeneration, hasActiveSession, markSessionActive, subscribeSessionLoss } from '@/lib/api/session'

/**
 * E29 (4): a silent refresh's answer sets the session cookies, and one sent with the previous session's cookies that
 * answers after a login's answer sets them over the new login's, so the browser is signed in as the previous account
 * while the tab shows the new one. The generation fences stop its replay and its cache writes, not its cookies. So a
 * login lets the refresh in flight answer first, or cancels it at its limit, as a logout does (E133), and holds every
 * refresh a 401 asks for until its own request has answered: sent after that answer, a refresh carries whatever cookies
 * are current. The cases model the browser's cookies (`cookies`): a request carries the ones of the moment it is sent,
 * a refresh's answer sets again the session it was sent with, and a login that took sets its own. A refresh another tab
 * started is out of this tab's reach, and of these cases.
 */

type Session = 'A' | 'B'
type LoginOutcome = 'took' | 'failed'

const refreshMock = vi.mocked(refreshAccessToken)
const originalAdapter = api.defaults.adapter
const EMAIL = 'b@example.test'
const PASSWORD = 'test-only-password'
// The browser's session cookies: whose session they hold, and whether its access token is still good. A, the reader
// signed in before the login, starts with an access token that has expired.
let cookies: { session: Session; fresh: boolean }
// What reached the server, in order, and as whom; and when each login and refresh answered.
const events: string[] = []
// Each login's answer, in the order the logins are sent; a login with none takes at once.
const loginAnswers: Promise<LoginOutcome>[] = []
// Every answer a case holds, let go after it, so that no refresh or login outlives its case in the client's state.
const held: (() => void)[] = []

function hold<T>(fallback: T) {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((yes) => { resolve = yes })
  held.push(() => resolve(fallback))
  return { promise, resolve }
}
const settle = () => new Promise((resolve) => setTimeout(resolve, 0))
const ok = (config: InternalAxiosRequestConfig, data: unknown) => ({ data, status: 200, statusText: 'OK', headers: {}, config })
const unauthorized = (config: InternalAxiosRequestConfig, detail: string) => Object.assign(new Error('Request failed with status code 401'), {
  config, isAxiosError: true, response: { status: 401, statusText: 'Unauthorized', data: { detail }, headers: {}, config },
})

/** The refresh, answering once `answer` settles: sent with the cookies of the moment, its answer sets that session's
 * again, with a fresh access token. Cancelled first, it fails, and its answer is dropped, its cookies with it, as the
 * browser drops a cancelled request's. */
function refreshAnswersWhen(answer: Promise<void>) {
  refreshMock.mockImplementation((_url, signal) => {
    const sentWith = cookies.session
    events.push(`refresh sent with ${sentWith}`)
    return new Promise<void>((resolve, reject) => {
      signal?.addEventListener('abort', () => reject(new CanceledError()))
      void answer.then(() => {
        if (signal?.aborted) return
        cookies = { session: sentWith, fresh: true }
        events.push(`refresh answered for ${sentWith}`)
        resolve()
      })
    })
  })
}

/** A login whose request is out, and a read sent meanwhile, whose expired access token answers 401. */
async function readingWhileTheLoginIsOut() {
  const loginAnswer = hold<LoginOutcome>('failed')
  loginAnswers.push(loginAnswer.promise)
  const signingIn = login(EMAIL, PASSWORD)
  await settle()
  const reading = api.get('/api/watchlist/').catch((error: unknown) => error)
  await settle()
  return { loginAnswer, signingIn, reading }
}

beforeEach(() => {
  cookies = { session: 'A', fresh: false }
  events.length = 0
  refreshMock.mockReset()
  refreshAnswersWhen(Promise.resolve())
  clearSessionActive()
  markSessionActive()
  api.defaults.adapter = async (config) => {
    if (config.url === '/api/auth/login') {
      events.push(`${config.method} ${config.url}`)
      const outcome = await (loginAnswers.shift() ?? 'took')
      events.push(`login ${outcome}`)
      if (outcome === 'failed') throw unauthorized(config, 'Incorrect email or password')
      cookies = { session: 'B', fresh: true }
      return ok(config, { ok: true })
    }
    events.push(`${config.method} ${config.url} as ${cookies.session}`)
    if (!cookies.fresh) throw unauthorized(config, 'Token expired')
    return ok(config, { reader: cookies.session })
  }
})

afterEach(async () => {
  // First, before anything waits: with the session ended, no refresh a case left waiting can start after it.
  clearSessionActive()
  vi.useRealTimers()
  for (const letGo of held.splice(0)) letGo()
  loginAnswers.length = 0
  await settle()
  api.defaults.adapter = originalAdapter
})

describe('a login waits for the refresh in flight', () => {
  it('sends the login only once the refresh in flight has answered, and a refresh asked for meanwhile joins that one', async () => {
    const answer = hold<void>(undefined)
    refreshAnswersWhen(answer.promise)
    const refreshing = ensureRefreshed()
    const signingIn = login(EMAIL, PASSWORD)
    const joined = ensureRefreshed()
    await settle()
    expect(events).toEqual(['refresh sent with A'])

    answer.resolve()
    await Promise.all([refreshing, joined, signingIn])
    expect(refreshMock).toHaveBeenCalledTimes(1)
    expect(events).toEqual(['refresh sent with A', 'refresh answered for A', 'post /api/auth/login', 'login took'])
    expect(cookies).toEqual({ session: 'B', fresh: true })
  })

  it('cancels a refresh still unanswered at the limit, then sends the login', async () => {
    vi.useFakeTimers()
    const answer = hold<void>(undefined)
    refreshAnswersWhen(answer.promise)
    const refreshing = ensureRefreshed().catch((error: unknown) => error)
    const signal = refreshMock.mock.calls[0][1] as AbortSignal
    const signingIn = login(EMAIL, PASSWORD)
    await vi.advanceTimersByTimeAsync(LOGIN_REFRESH_WAIT_MS - 1)
    expect(events).toEqual(['refresh sent with A'])
    expect(signal.aborted).toBe(false)

    await vi.advanceTimersByTimeAsync(1)
    expect(signal.aborted).toBe(true)
    await signingIn
    // Its answer comes after all, and is dropped: cancelled, it cannot set A's cookies over the login's.
    answer.resolve()
    expect(await refreshing).toBeInstanceOf(CanceledError)
    expect(events).toEqual(['refresh sent with A', 'post /api/auth/login', 'login took'])
    expect(cookies).toEqual({ session: 'B', fresh: true })
  })
})

describe('a refresh asked for while a login is under way', () => {
  it('is held from the moment the login starts, before the login has waited on anything', async () => {
    const answer = hold<void>(undefined)
    refreshAnswersWhen(answer.promise)
    const signingIn = login(EMAIL, PASSWORD)
    // A 401's, landing as the login starts.
    const refreshing = ensureRefreshed()
    expect(refreshMock).not.toHaveBeenCalled()

    await signingIn
    answer.resolve()
    await refreshing
    expect(events).toEqual(['post /api/auth/login', 'login took', 'refresh sent with B', 'refresh answered for B'])
    expect(cookies).toEqual({ session: 'B', fresh: true })
  })

  it('is not sent for a 401 that lands while the login is out, until the login has answered', async () => {
    const { loginAnswer, signingIn, reading } = await readingWhileTheLoginIsOut()
    expect(events).toEqual(['post /api/auth/login', 'get /api/watchlist/ as A'])
    expect(refreshMock).not.toHaveBeenCalled()
    // A login is no logout: the session still reads as active, so the 401 is held, not taken for a lost session.
    expect(hasActiveSession()).toBe(true)

    loginAnswer.resolve('failed')
    await expect(signingIn).rejects.toMatchObject({ status: 401 })
    await reading
    expect(events.slice(0, 4)).toEqual(['post /api/auth/login', 'get /api/watchlist/ as A', 'login failed', 'refresh sent with A'])
  })

  it('renews the previous session after a login that failed, and the request replays', async () => {
    const lost = vi.fn()
    const unsubscribe = subscribeSessionLoss(lost)
    try {
      const { loginAnswer, signingIn, reading } = await readingWhileTheLoginIsOut()
      loginAnswer.resolve('failed')
      await expect(signingIn).rejects.toMatchObject({ status: 401 })
      expect(await reading).toMatchObject({ status: 200, data: { reader: 'A' } })
      expect(events).toEqual([
        'post /api/auth/login', 'get /api/watchlist/ as A', 'login failed',
        'refresh sent with A', 'refresh answered for A', 'get /api/watchlist/ as A',
      ])
      expect(cookies).toEqual({ session: 'A', fresh: true })
      expect(hasActiveSession()).toBe(true)
      expect(lost).not.toHaveBeenCalled()
    } finally {
      unsubscribe()
    }
  })

  it('sends nothing as the previous account, and brings it nothing, after a login that took and was accepted', async () => {
    const lost = vi.fn()
    const unsubscribe = subscribeSessionLoss(lost)
    try {
      const explicitGeneration = getExplicitSessionGeneration()
      const { loginAnswer, signingIn, reading } = await readingWhileTheLoginIsOut()
      loginAnswer.resolve('took')
      await signingIn
      // app/login/page.tsx's order: the login is accepted in the turn its answer resumes in.
      acceptLoginAndResetAccount(new QueryClient(), explicitGeneration)
      // The request aborts, or its refresh goes out with the new session's cookies and its replay is fenced: nothing
      // reaches the server as A once the login has answered, and nothing comes back to the request.
      expect(await reading).toMatchObject({ name: 'ApiError', status: 401 })
      expect(events.slice(events.indexOf('login took')).filter((event) => event.endsWith(' A'))).toEqual([])
      expect(events.filter((event) => event.startsWith('get '))).toEqual(['get /api/watchlist/ as A'])
      expect(cookies.session).toBe('B')
      expect(hasActiveSession()).toBe(true)
      expect(lost).not.toHaveBeenCalled()
    } finally {
      unsubscribe()
    }
  })

  it('is held for the stream readers too, which ask ensureRefreshed for theirs (postStreamWithRefresh)', async () => {
    const loginAnswer = hold<LoginOutcome>('failed')
    loginAnswers.push(loginAnswer.promise)
    const signingIn = login(EMAIL, PASSWORD)
    await settle()
    const post = vi.fn(async () => {
      events.push(`stream as ${cookies.session}`)
      return { status: cookies.fresh ? 200 : 401, ok: cookies.fresh } as Response
    })
    const streaming = postStreamWithRefresh(post)
    await settle()
    expect(refreshMock).not.toHaveBeenCalled()

    loginAnswer.resolve('failed')
    await expect(signingIn).rejects.toMatchObject({ status: 401 })
    expect((await streaming).status).toBe(200)
    expect(events).toEqual([
      'post /api/auth/login', 'stream as A', 'login failed', 'refresh sent with A', 'refresh answered for A', 'stream as A',
    ])
  })

  it('stays held while a later login is out, after an earlier one has answered', async () => {
    const first = hold<LoginOutcome>('failed')
    const second = hold<LoginOutcome>('failed')
    loginAnswers.push(first.promise, second.promise)
    const one = login(EMAIL, PASSWORD)
    const two = login(EMAIL, PASSWORD)
    await settle()
    first.resolve('failed')
    await expect(one).rejects.toMatchObject({ status: 401 })
    const refreshing = ensureRefreshed()
    await settle()
    expect(refreshMock).not.toHaveBeenCalled()

    second.resolve('took')
    await two
    await refreshing
    expect(events).toEqual([
      'post /api/auth/login', 'post /api/auth/login', 'login failed', 'login took', 'refresh sent with B', 'refresh answered for B',
    ])
  })

  it('is sent at once after the login has answered: nothing stays held', async () => {
    loginAnswers.push(Promise.resolve<LoginOutcome>('failed'))
    await expect(login(EMAIL, PASSWORD)).rejects.toMatchObject({ status: 401 })
    const refreshing = ensureRefreshed().catch((error: unknown) => error)
    expect(refreshMock).toHaveBeenCalledTimes(1)
    await refreshing
    expect(cookies).toEqual({ session: 'A', fresh: true })
  })
})

/**
 * Gate (CLAUDE.md rule 12): every request to the password login goes through withoutRefreshBeside, so none runs beside
 * a silent refresh. What it reads: every tracked file under frontend/ (`git ls-files`) of each JS and TS extension, in
 * every directory but tests/. A literal (a string, or a template's text) that names the path /api/auth/login must sit
 * inside a function handed inline, as the second argument, to a call of `withoutRefreshBeside` imported by that name
 * from lib/api/client. Its one exemption is lib/api/client.ts's NO_REFRESH_PATHS, a list of paths, not a request.
 * Refused though the rule may hold: the path held in a const, the helper renamed on import or read off a namespace, and
 * a send declared apart and handed over by name. Out of its reach (planted as gaps): a path assembled at run time, and
 * a literal inside the send but in a function it never calls.
 */
const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SOURCE = /\.(?:[cm]?[jt]s|[jt]sx)$/
const LOGIN_PATH = /\/api\/auth\/login(?![\w-])/
const CLIENT = 'lib/api/client.ts'

const scriptKind = (file: string): ts.ScriptKind =>
  file.endsWith('.tsx') ? ts.ScriptKind.TSX : file.endsWith('.jsx') ? ts.ScriptKind.JSX : /\.[cm]?js$/.test(file) ? ts.ScriptKind.JS : ts.ScriptKind.TS

/** Where a module names the login path: the lines outside a send handed to the helper, and how often inside one or
 * in the exempt list. */
function loginPaths(source: string, file: string): { outside: number[]; inside: number; exempt: number } {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, scriptKind(file))
  const resolve = bindingResolver(sf)
  const fromClient = (specifier: string) =>
    specifier === '@/lib/api/client' || (specifier.startsWith('.') && path.posix.join(path.posix.dirname(file), specifier) === 'lib/api/client')
  const imported = sf.statements.some((statement) =>
    ts.isImportDeclaration(statement) && ts.isStringLiteral(statement.moduleSpecifier) && fromClient(statement.moduleSpecifier.text) &&
    !!statement.importClause?.namedBindings && ts.isNamedImports(statement.importClause.namedBindings) &&
    statement.importClause.namedBindings.elements.some((element) => !element.propertyName && element.name.text === 'withoutRefreshBeside'))
  const sendOfTheHelper = (node: ts.Node): boolean =>
    (ts.isArrowFunction(node) || ts.isFunctionExpression(node)) && ts.isCallExpression(node.parent) && node.parent.arguments[1] === node &&
    ts.isIdentifier(node.parent.expression) && node.parent.expression.text === 'withoutRefreshBeside' && imported && !resolve(node.parent.expression)
  const exempt = (node: ts.Node): boolean =>
    file === CLIENT && ts.isArrayLiteralExpression(node.parent) && ts.isVariableDeclaration(node.parent.parent) &&
    ts.isIdentifier(node.parent.parent.name) && node.parent.parent.name.text === 'NO_REFRESH_PATHS'
  const found = { outside: [] as number[], inside: 0, exempt: 0 }
  const visit = (node: ts.Node): void => {
    const texts = ts.isStringLiteralLike(node) ? [node.text]
      : ts.isTemplateExpression(node) ? [node.head.text, ...node.templateSpans.map((span) => span.literal.text)] : []
    if (texts.some((text) => LOGIN_PATH.test(text))) {
      let inside = false
      for (let at: ts.Node | undefined = node.parent; at && !inside; at = at.parent) inside = sendOfTheHelper(at)
      if (exempt(node)) found.exempt += 1
      else if (inside) found.inside += 1
      else found.outside.push(sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1)
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return found
}

const API = "import api from '@/lib/api/client'\n"
const HELPER = "import { withoutRefreshBeside } from '@/lib/api/client'\n"
const FORMS: { form: string; source: string; file?: string; outside: number; inside: number; exempt?: number; gap?: true }[] = [
  { form: 'posted in the send, an arrow', source: `${API}${HELPER}export const login = () => withoutRefreshBeside(1, () => api.post('/api/auth/login', {}))`, outside: 0, inside: 1 },
  { form: 'posted in the send, a function expression', source: `${API}${HELPER}export const login = () => withoutRefreshBeside(1, function () { return api.post('/api/auth/login', {}) })`, outside: 0, inside: 1 },
  { form: 'the helper imported by a relative path', file: 'lib/api/auth.ts', source: "import api, { withoutRefreshBeside } from './client'\nexport const login = () => withoutRefreshBeside(1, () => api.post('/api/auth/login', {}))", outside: 0, inside: 1 },
  { form: 'posted directly', source: `${API}export const login = () => api.post('/api/auth/login', {})`, outside: 1, inside: 0 },
  { form: 'a template literal', source: `${API}export const login = () => api.post(\`/api/auth/login\`, {})`, outside: 1, inside: 0 },
  { form: 'a template with a base before the path', source: "export const login = (base: string) => fetch(`${base}/api/auth/login`, { method: 'POST' })", outside: 1, inside: 0 },
  { form: 'a query after the path', source: `${API}export const login = () => api.post('/api/auth/login?remember=1', {})`, outside: 1, inside: 0 },
  { form: 'a form that posts to it', file: 'app/fixture.tsx', source: 'export const Form = () => <form action="/api/auth/login" method="post" />', outside: 1, inside: 0 },
  { form: 'the path in a const, posted in the send', source: `${API}${HELPER}const LOGIN = '/api/auth/login'\nexport const login = () => withoutRefreshBeside(1, () => api.post(LOGIN, {}))`, outside: 1, inside: 0 },
  { form: 'a send declared apart, handed over by name', source: `${API}${HELPER}const send = () => api.post('/api/auth/login', {})\nexport const login = () => withoutRefreshBeside(1, send)`, outside: 1, inside: 0 },
  { form: 'the path in the first argument', source: `${API}${HELPER}export const login = () => withoutRefreshBeside((() => api.post('/api/auth/login', {})) as never, () => api.post('/x'))`, outside: 1, inside: 0 },
  { form: 'the helper not imported', source: `${API}export const login = () => withoutRefreshBeside(1, () => api.post('/api/auth/login', {}))`, outside: 1, inside: 0 },
  { form: 'the helper imported from another module', source: `${API}import { withoutRefreshBeside } from '@/lib/other'\nexport const login = () => withoutRefreshBeside(1, () => api.post('/api/auth/login', {}))`, outside: 1, inside: 0 },
  { form: 'the helper renamed on import', source: `${API}import { withoutRefreshBeside as hold } from '@/lib/api/client'\nexport const login = () => hold(1, () => api.post('/api/auth/login', {}))`, outside: 1, inside: 0 },
  { form: 'the helper read off a namespace', source: `${API}import * as client from '@/lib/api/client'\nexport const login = () => client.withoutRefreshBeside(1, () => api.post('/api/auth/login', {}))`, outside: 1, inside: 0 },
  { form: 'the helper shadowed by a local of its name', source: `${API}const withoutRefreshBeside = (_ms: number, send: () => unknown) => send()\nexport const login = () => withoutRefreshBeside(1, () => api.post('/api/auth/login', {}))`, outside: 1, inside: 0 },
  { form: 'the helper shadowed by a parameter', source: `${API}${HELPER}export const login = (withoutRefreshBeside: (ms: number, send: () => unknown) => unknown) => withoutRefreshBeside(1, () => api.post('/api/auth/login', {}))`, outside: 1, inside: 0 },
  { form: "lib/api/client.ts's NO_REFRESH_PATHS", file: CLIENT, source: "const NO_REFRESH_PATHS = ['/api/auth/refresh', '/api/auth/login']", outside: 0, inside: 0, exempt: 1 },
  { form: 'a list of that name elsewhere', source: "const NO_REFRESH_PATHS = ['/api/auth/login']", outside: 1, inside: 0 },
  // Look-alikes, which pass.
  { form: 'a longer path that starts with it', source: `${API}export const history = () => api.get('/api/auth/login-history')`, outside: 0, inside: 0 },
  { form: 'another auth path', source: `${API}export const logout = () => api.post('/api/auth/logout')`, outside: 0, inside: 0 },
  { form: 'the path in a comment', source: `${API}// the login posts to /api/auth/login\nexport const x = 1`, outside: 0, inside: 0 },
  // Out of its reach.
  { form: 'the path assembled at run time', source: `${API}export const login = () => api.post('/api/auth/' + 'login', {})`, outside: 0, inside: 0, gap: true },
  { form: 'the last segment substituted into a template', source: `${API}export const login = () => api.post(\`/api/auth/\${'login'}\`, {})`, outside: 0, inside: 0, gap: true },
  { form: 'in the send, in a function it never calls', source: `${API}${HELPER}export const login = () => withoutRefreshBeside(1, () => { const later = () => api.post('/api/auth/login', {}); void later; return api.post('/x') })`, outside: 0, inside: 1, gap: true },
]

describe('every request to the password login goes through withoutRefreshBeside', () => {
  it('scores each planted form', () => {
    const scored = FORMS.map(({ form, source, file = 'features/fixture.ts', outside, inside, exempt = 0 }) => {
      const got = loginPaths(source, file)
      return { form, expected: { outside, inside, exempt }, got: { outside: got.outside.length, inside: got.inside, exempt: got.exempt } }
    })
    expect(scored.filter(({ expected, got }) => JSON.stringify(expected) !== JSON.stringify(got))).toEqual([])
  })

  it('finds no other in the tree, and reads the login\'s own post and the exemption\'s one site', () => {
    const listed = execFileSync('git', ['ls-files', '-z'], { cwd: FRONTEND, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 }).split('\0').filter(Boolean)
    const files = listed.filter((file) => SOURCE.test(file) && !file.startsWith('tests/'))
    // Anchored to the tree: a listing that matched nothing would pass every check below.
    expect(files.length).toBeGreaterThan(300)
    const readings = files.map((file) => ({ file, ...loginPaths(readFileSync(path.join(FRONTEND, file), 'utf8'), file) }))
    expect(readings.flatMap(({ file, outside }) => outside.map((line) => `${file}:${line}`))).toEqual([])
    expect(readings.filter(({ inside }) => inside > 0).map(({ file, inside }) => [file, inside])).toEqual([['features/auth/api/auth-api.ts', 1]])
    expect(readings.filter(({ exempt }) => exempt > 0).map(({ file, exempt }) => [file, exempt])).toEqual([[CLIENT, 1]])
  })
})
