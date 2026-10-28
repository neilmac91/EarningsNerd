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
import { LOGIN_REFRESH_WAIT_MS, login, logout } from '@/features/auth/api/auth-api'
import { acceptLoginAndResetAccount } from '@/features/auth/lib/accountQueryState'
import { advanceSessionGeneration, clearSessionActive, getExplicitSessionGeneration, hasActiveSession, markSessionActive, subscribeSessionLoss } from '@/lib/api/session'

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
// What reached the server, in order, and as whom; and when each login, logout and refresh answered.
const events: string[] = []
// Each login's answer, in the order the logins are sent; a login with none takes at once. And each logout's, alike.
const loginAnswers: Promise<LoginOutcome>[] = []
const logoutAnswers: Promise<void>[] = []
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
    if (config.url === '/api/auth/logout') {
      events.push(`${config.method} ${config.url}`)
      await logoutAnswers.shift()
      events.push('logout answered')
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
  logoutAnswers.length = 0
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

  it('sends one refresh for every 401 held behind a login that failed, and every request replays', async () => {
    const loginAnswer = hold<LoginOutcome>('failed')
    loginAnswers.push(loginAnswer.promise)
    const signingIn = login(EMAIL, PASSWORD)
    await settle()
    const reads = ['/api/watchlist/', '/api/notifications/'].map((url) => api.get(url).catch((error: unknown) => error))
    await settle()
    expect(refreshMock).not.toHaveBeenCalled()

    loginAnswer.resolve('failed')
    await expect(signingIn).rejects.toMatchObject({ status: 401 })
    expect(await Promise.all(reads)).toMatchObject([{ status: 200, data: { reader: 'A' } }, { status: 200, data: { reader: 'A' } }])
    // Held, they share one refresh, as concurrent 401s do: two on the single-use rotating token would undo each other.
    expect(refreshMock).toHaveBeenCalledTimes(1)
    expect(events).toEqual([
      'post /api/auth/login', 'get /api/watchlist/ as A', 'get /api/notifications/ as A', 'login failed',
      'refresh sent with A', 'refresh answered for A', 'get /api/watchlist/ as A', 'get /api/notifications/ as A',
    ])
  })

  it('sends nothing once a logout has started, for a refresh held behind a login', async () => {
    const logoutAnswer = hold<void>(undefined)
    logoutAnswers.push(logoutAnswer.promise)
    const { loginAnswer, signingIn, reading } = await readingWhileTheLoginIsOut()
    // The logout starts while the 401's refresh is held, and the session reads as inactive until it settles.
    const loggingOut = logout()
    await settle()
    expect(hasActiveSession()).toBe(false)

    loginAnswer.resolve('failed')
    await expect(signingIn).rejects.toMatchObject({ status: 401 })
    // The held refresh finds the session ended: a refresh sent now would set the cookies the logout's answer clears.
    expect(await reading).toMatchObject({ name: 'ApiError', status: 401 })
    logoutAnswer.resolve()
    await loggingOut
    expect(refreshMock).not.toHaveBeenCalled()
    expect(events).toEqual(['post /api/auth/login', 'get /api/watchlist/ as A', 'post /api/auth/logout', 'login failed', 'logout answered'])
  })

  it('sends nothing once the account has changed under it, for a refresh held behind a login', async () => {
    const { loginAnswer, signingIn, reading } = await readingWhileTheLoginIsOut()
    // Another tab signed in as the second account (the browser's cookies are its own now), and its sign-in reaches this
    // tab through /me while the refresh is held, moving the session generation (accountQueryState's watchReader): the
    // held 401 belongs to the account the tab showed before.
    cookies = { session: 'B', fresh: true }
    advanceSessionGeneration('session-loss')
    loginAnswer.resolve('failed')
    await expect(signingIn).rejects.toMatchObject({ status: 401 })
    // The held refresh finds another generation: sent now, it would renew the account the tab no longer shows.
    expect(await reading).toMatchObject({ name: 'ApiError', status: 401 })
    expect(refreshMock).not.toHaveBeenCalled()
    expect(events).toEqual(['post /api/auth/login', 'get /api/watchlist/ as A', 'login failed'])
  })

  it('sends nothing as the previous account, and brings it nothing, after a login that took and was accepted', async () => {
    const lost = vi.fn()
    const unsubscribe = subscribeSessionLoss(lost)
    try {
      // A refresh answers only once the login has answered and been accepted: one sent before the login's answer, with
      // A's cookies, would set them over B's.
      const refreshAnswer = hold<void>(undefined)
      refreshAnswersWhen(refreshAnswer.promise)
      const explicitGeneration = getExplicitSessionGeneration()
      const { loginAnswer, signingIn, reading } = await readingWhileTheLoginIsOut()
      loginAnswer.resolve('took')
      await signingIn
      // app/login/page.tsx's order: the login is accepted in the turn its answer resumes in.
      acceptLoginAndResetAccount(new QueryClient(), explicitGeneration)
      refreshAnswer.resolve()
      // The held refresh woke before the acceptance and went out with B's cookies, and the acceptance fences its replay
      // (woken after it, the refresh would abort): nothing reaches the server as A once the login has answered, and
      // nothing comes back to the request.
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
 * Gate (CLAUDE.md rule 12), both ends of the hold. The login: every request to the password login goes through
 * withoutRefreshBeside, so none runs beside a silent refresh. A literal (a string, or a template's text) that names
 * /api/auth/login is an argument of the call returned (its expression body, or a `return` of its own, through `await`
 * and parentheses) by a function handed inline, as the second argument, to a call of `withoutRefreshBeside` imported by
 * that name from lib/api/client, so the helper's promise is that request's. The refresh: none starts outside
 * ensureRefreshed, which holds it behind a login. lib/api/refresh, whose refreshAccessToken posts to /api/auth/refresh,
 * is imported or exported anywhere only by lib/api/client.ts, by that one name, whose one use of it is one call in
 * ensureRefreshed, and no other literal names that path; client.ts's NO_REFRESH_PATHS, a list of paths and not a
 * request, is pinned for both paths to its one site. What it reads: every tracked file under frontend/ (`git ls-files`)
 * of each JS and TS extension, in every directory but tests/, in one walk per file. Refused though the rule may hold:
 * the path held in a const, the helper renamed on import or read off a namespace, a send declared apart, a send that
 * awaits the post and returns its answer, and any import of the refresh module but client.ts's, a type-only one
 * included. lib/api/refresh.ts's own uses of refreshAccessToken are read too (its name resolves to the declaration
 * there, not to an import), so a keep-alive inside it that calls refreshAccessToken is refused. Out of its reach
 * (planted as gaps): a path assembled at run time; a send that returns a call of an async local helper which posts
 * without returning the post; and, inside refreshAccessToken itself, a second post of its own path (a timer it sets
 * there), which reads as the one path where it stands.
 */
const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SOURCE = /\.(?:[cm]?[jt]s|[jt]sx)$/
const LOGIN_PATH = /\/api\/auth\/login(?![\w-])/
const REFRESH_PATH = /\/api\/auth\/refresh(?![\w-])/
const CLIENT = 'lib/api/client.ts'
const REFRESH_MODULE = 'lib/api/refresh'
// The refresh's sites, all of them: anything else, anywhere, is a refresh that could start outside ensureRefreshed.
const REFRESH_SITES: Record<string, string[]> = {
  [CLIENT]: ['call of refreshAccessToken in ensureRefreshed', 'import { refreshAccessToken } from lib/api/refresh', 'path in NO_REFRESH_PATHS'],
  'lib/api/refresh.ts': ['path in refreshAccessToken'],
}

const scriptKind = (file: string): ts.ScriptKind =>
  file.endsWith('.tsx') ? ts.ScriptKind.TSX : file.endsWith('.jsx') ? ts.ScriptKind.JSX : /\.[cm]?js$/.test(file) ? ts.ScriptKind.JS : ts.ScriptKind.TS
/** The module a specifier names from `file`, `@/` and relative alike, without its script extension. */
const moduleOf = (specifier: string, file: string): string | undefined =>
  (specifier.startsWith('@/') ? path.posix.normalize(specifier.slice(2)) : specifier.startsWith('.') ? path.posix.join(path.posix.dirname(file), specifier) : undefined)
    ?.replace(SOURCE, '')
/** A value without the wrappers it passes through unchanged here: parentheses, `await`, `as`, `satisfies` and `!`. */
const unwrap = (node: ts.Expression): ts.Expression =>
  ts.isParenthesizedExpression(node) || ts.isAwaitExpression(node) || ts.isAsExpression(node) || ts.isSatisfiesExpression(node) || ts.isNonNullExpression(node)
    ? unwrap(node.expression) : node
/** What a function returns: its expression body, or each `return` of its own (a nested function's are its own). */
function returnedBy(fn: ts.ArrowFunction | ts.FunctionExpression): ts.Expression[] {
  if (!ts.isBlock(fn.body)) return [unwrap(fn.body)]
  const found: ts.Expression[] = []
  const walk = (node: ts.Node): void => {
    if (ts.isReturnStatement(node) && node.expression) found.push(unwrap(node.expression))
    if (!ts.isFunctionLike(node)) ts.forEachChild(node, walk)
  }
  ts.forEachChild(fn.body, walk)
  return found
}
/** Where a node stands: the named function that holds it, else the variable, else the module. */
function holder(node: ts.Node): string {
  let variable: string | undefined
  for (let at = node.parent; at; at = at.parent) {
    if ((ts.isFunctionDeclaration(at) || ts.isMethodDeclaration(at)) && at.name) return at.name.getText()
    if ((ts.isArrowFunction(at) || ts.isFunctionExpression(at)) && ts.isVariableDeclaration(at.parent) && ts.isIdentifier(at.parent.name)) return at.parent.name.text
    if (!variable && ts.isVariableDeclaration(at) && ts.isIdentifier(at.name)) variable = at.name.text
  }
  return variable ?? 'module'
}

interface Reading {
  /** Lines of the literals naming the login path outside a send's returned call. */
  outside: number[]
  /** How many are inside one, and in NO_REFRESH_PATHS. */
  inside: number
  exempt: number
  /** The refresh's sites, sorted. */
  refresh: string[]
}

/** One walk over a module for both ends of the hold. */
function read(source: string, file: string): Reading {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, scriptKind(file))
  const resolve = bindingResolver(sf)
  const named = (statement: ts.Statement, module: string): ts.ImportSpecifier[] =>
    ts.isImportDeclaration(statement) && ts.isStringLiteral(statement.moduleSpecifier) && moduleOf(statement.moduleSpecifier.text, file) === module &&
    statement.importClause?.namedBindings && ts.isNamedImports(statement.importClause.namedBindings) ? [...statement.importClause.namedBindings.elements] : []
  const helperImported = sf.statements.some((statement) =>
    named(statement, 'lib/api/client').some((element) => !element.propertyName && element.name.text === 'withoutRefreshBeside'))
  // The local names refreshAccessToken is imported under.
  const refreshNames = new Set(sf.statements.flatMap((statement) => named(statement, REFRESH_MODULE))
    .filter((element) => (element.propertyName ?? element.name).text === 'refreshAccessToken').map((element) => element.name.text))
  const sendOfTheHelper = (node: ts.Node): node is ts.ArrowFunction | ts.FunctionExpression =>
    (ts.isArrowFunction(node) || ts.isFunctionExpression(node)) && ts.isCallExpression(node.parent) && node.parent.arguments[1] === node &&
    ts.isIdentifier(node.parent.expression) && node.parent.expression.text === 'withoutRefreshBeside' && helperImported && !resolve(node.parent.expression)
  // The literal is an argument of the call a send of the helper returns.
  const sentByTheHelper = (literal: ts.Node): boolean => {
    const call = literal.parent
    if (!ts.isCallExpression(call) || !call.arguments.some((argument) => argument === literal)) return false
    let fn: ts.Node | undefined = call.parent
    while (fn && !ts.isFunctionLike(fn)) fn = fn.parent
    return !!fn && sendOfTheHelper(fn) && returnedBy(fn).includes(call)
  }
  const inNoRefreshPaths = (node: ts.Node): boolean =>
    file === CLIENT && ts.isArrayLiteralExpression(node.parent) && ts.isVariableDeclaration(node.parent.parent) &&
    ts.isIdentifier(node.parent.parent.name) && node.parent.parent.name.text === 'NO_REFRESH_PATHS'
  const found: Reading = { outside: [], inside: 0, exempt: 0, refresh: [] }
  const refreshModule = (specifier: ts.Node | undefined): boolean =>
    !!specifier && ts.isStringLiteralLike(specifier) && moduleOf(specifier.text, file) === REFRESH_MODULE
  const clause = (text: string | undefined) => (text ?? '*').replace(/\s+/g, ' ')
  const visit = (node: ts.Node): void => {
    const texts = ts.isStringLiteralLike(node) ? [node.text]
      : ts.isTemplateExpression(node) ? [node.head.text, ...node.templateSpans.map((span) => span.literal.text)] : []
    if (texts.some((text) => LOGIN_PATH.test(text))) {
      if (inNoRefreshPaths(node)) found.exempt += 1
      else if (sentByTheHelper(node)) found.inside += 1
      else found.outside.push(sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1)
    }
    if (texts.some((text) => REFRESH_PATH.test(text))) found.refresh.push(`path in ${holder(node)}`)
    if (ts.isImportDeclaration(node) && refreshModule(node.moduleSpecifier)) found.refresh.push(`import ${clause(node.importClause?.getText(sf))} from ${REFRESH_MODULE}`)
    if (ts.isExportDeclaration(node) && refreshModule(node.moduleSpecifier)) found.refresh.push(`export ${clause(node.exportClause?.getText(sf))} from ${REFRESH_MODULE}`)
    if (ts.isImportEqualsDeclaration(node) && ts.isExternalModuleReference(node.moduleReference) && refreshModule(node.moduleReference.expression)) {
      found.refresh.push(`import ${node.name.text} = require of ${REFRESH_MODULE}`)
    }
    if (ts.isCallExpression(node) && refreshModule(node.arguments[0])) {
      if (node.expression.kind === ts.SyntaxKind.ImportKeyword) found.refresh.push(`dynamic import of ${REFRESH_MODULE}`)
      else if (ts.isIdentifier(node.expression) && node.expression.text === 'require') found.refresh.push(`require of ${REFRESH_MODULE}`)
    }
    // A use of the imported refreshAccessToken: not its import, not a property's name, not a local of the same name.
    if (ts.isIdentifier(node) && refreshNames.has(node.text) && !ts.isImportSpecifier(node.parent) && !resolve(node) &&
      !((ts.isPropertyAccessExpression(node.parent) || ts.isPropertyAssignment(node.parent)) && node.parent.name === node)) {
      const called = ts.isCallExpression(node.parent) && node.parent.expression === node
      found.refresh.push(`${called ? 'call of' : 'reference to'} ${node.text} in ${holder(node)}`)
    }
    // In the module that declares it, every use of refreshAccessToken but its declaration's own name: there the name
    // resolves to the declaration, not to an import, so the rule above does not see it, and a keep-alive there would
    // skip the hold, the shared refresh and a logout's wait.
    if (file === `${REFRESH_MODULE}.ts` && ts.isIdentifier(node) && node.text === 'refreshAccessToken' &&
      !((ts.isFunctionDeclaration(node.parent) || ts.isVariableDeclaration(node.parent)) && node.parent.name === node) &&
      !((ts.isPropertyAccessExpression(node.parent) || ts.isPropertyAssignment(node.parent)) && node.parent.name === node)) {
      const called = ts.isCallExpression(node.parent) && node.parent.expression === node
      found.refresh.push(`${called ? 'call of' : 'reference to'} refreshAccessToken in ${holder(node)}`)
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  found.refresh.sort()
  return found
}

const API = "import api from '@/lib/api/client'\n"
const HELPER = "import { withoutRefreshBeside } from '@/lib/api/client'\n"
const LOGIN_FORMS: { form: string; source: string; file?: string; outside: number; inside: number; exempt?: number; gap?: true }[] = [
  { form: 'posted in the send, an arrow', source: `${API}${HELPER}export const login = () => withoutRefreshBeside(1, () => api.post('/api/auth/login', {}))`, outside: 0, inside: 1 },
  { form: 'posted in the send, a function expression', source: `${API}${HELPER}export const login = () => withoutRefreshBeside(1, function () { return api.post('/api/auth/login', {}) })`, outside: 0, inside: 1 },
  { form: 'returned through await', source: `${API}${HELPER}export const login = () => withoutRefreshBeside(1, async () => await api.post('/api/auth/login', {}))`, outside: 0, inside: 1 },
  { form: 'the helper imported by a relative path', file: 'lib/api/auth.ts', source: "import api, { withoutRefreshBeside } from './client'\nexport const login = () => withoutRefreshBeside(1, () => api.post('/api/auth/login', {}))", outside: 0, inside: 1 },
  { form: 'posted directly', source: `${API}export const login = () => api.post('/api/auth/login', {})`, outside: 1, inside: 0 },
  { form: 'a template literal', source: `${API}export const login = () => api.post(\`/api/auth/login\`, {})`, outside: 1, inside: 0 },
  { form: 'a template with a base before the path', source: "export const login = (base: string) => fetch(`${base}/api/auth/login`, { method: 'POST' })", outside: 1, inside: 0 },
  { form: 'a query after the path', source: `${API}export const login = () => api.post('/api/auth/login?remember=1', {})`, outside: 1, inside: 0 },
  { form: 'a form that posts to it', file: 'app/fixture.tsx', source: 'export const Form = () => <form action="/api/auth/login" method="post" />', outside: 1, inside: 0 },
  { form: 'posted in the send, but not returned', source: `${API}${HELPER}export const login = () => withoutRefreshBeside(1, () => { void api.post('/api/auth/login', {}); return Promise.resolve() })`, outside: 1, inside: 0 },
  { form: 'posted beside the promise the send returns', source: `${API}${HELPER}export const login = () => withoutRefreshBeside(1, () => (api.post('/api/auth/login', {}), Promise.resolve()))`, outside: 1, inside: 0 },
  { form: 'in the send, in a function it never calls', source: `${API}${HELPER}export const login = () => withoutRefreshBeside(1, () => { const later = () => api.post('/api/auth/login', {}); void later; return api.post('/x') })`, outside: 1, inside: 0 },
  { form: 'awaited in the send, its answer returned', source: `${API}${HELPER}export const login = () => withoutRefreshBeside(1, async () => { const answer = await api.post('/api/auth/login', {}); return answer })`, outside: 1, inside: 0 },
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
  { form: 'the post behind a local helper that does not return it', source: `${API}${HELPER}const fire = async (url: string) => { void api.post(url, {}) }\nexport const login = () => withoutRefreshBeside(10, () => fire('/api/auth/login'))`, outside: 0, inside: 1, gap: true },
]

// A client with the refresh's sanctioned sites, and a body for each form.
const client = (body: string, head = "import { refreshAccessToken } from './refresh'\n") =>
  `${head}const NO_REFRESH_PATHS = ['/api/auth/refresh', '/api/auth/login']\n${body}`
const ENSURE = 'export function ensureRefreshed() { return refreshAccessToken(getApiUrl()) }\n'
const KEEP_ALIVE = 'features/session/keepAlive.ts'
const REFRESH_TS = "import axios from 'axios'\n"
  + 'export async function refreshAccessToken(baseUrl: string, signal?: AbortSignal): Promise<void> {\n'
  + '  await axios.post(`${baseUrl}/api/auth/refresh`, {}, { withCredentials: true, signal })\n}\n'
const REFRESH_FORMS: { form: string; source: string; file: string; sites: string[]; flag: boolean; gap?: true }[] = [
  { form: 'the client: one call, in ensureRefreshed', file: CLIENT, source: client(ENSURE), sites: REFRESH_SITES[CLIENT], flag: false },
  { form: 'refresh.ts posting to its path', file: 'lib/api/refresh.ts', source: "import axios from 'axios'\nexport async function refreshAccessToken(baseUrl: string) { await axios.post(`${baseUrl}/api/auth/refresh`, {}) }", sites: REFRESH_SITES['lib/api/refresh.ts'], flag: false },
  { form: 'a second call in ensureRefreshed', file: CLIENT, source: client('export function ensureRefreshed() { if (gate) return gate.then(() => refreshAccessToken(getApiUrl())); return refreshAccessToken(getApiUrl()) }'), sites: ['call of refreshAccessToken in ensureRefreshed', ...REFRESH_SITES[CLIENT]], flag: true },
  { form: 'a call outside ensureRefreshed', file: CLIENT, source: client(`${ENSURE}export function keepAlive() { return refreshAccessToken(getApiUrl()) }`), sites: ['call of refreshAccessToken in keepAlive', ...REFRESH_SITES[CLIENT]], flag: true },
  { form: 'handed over as a value', file: CLIENT, source: client(`${ENSURE}setInterval(refreshAccessToken, 60_000)`), sites: ['call of refreshAccessToken in ensureRefreshed', 'import { refreshAccessToken } from lib/api/refresh', 'path in NO_REFRESH_PATHS', 'reference to refreshAccessToken in module'], flag: true },
  { form: 'exported on from the client', file: CLIENT, source: client(`${ENSURE}export { refreshAccessToken }`), sites: ['call of refreshAccessToken in ensureRefreshed', 'import { refreshAccessToken } from lib/api/refresh', 'path in NO_REFRESH_PATHS', 'reference to refreshAccessToken in module'], flag: true },
  { form: 'renamed on import', file: CLIENT, source: client('export function ensureRefreshed() { return renew(getApiUrl()) }', "import { refreshAccessToken as renew } from './refresh'\n"), sites: ['call of renew in ensureRefreshed', 'import { refreshAccessToken as renew } from lib/api/refresh', 'path in NO_REFRESH_PATHS'], flag: true },
  { form: 'a keep-alive module importing it', file: KEEP_ALIVE, source: "import { refreshAccessToken } from '@/lib/api/refresh'\nexport const keepAlive = () => setInterval(() => refreshAccessToken(''), 60_000)", sites: ['call of refreshAccessToken in keepAlive', 'import { refreshAccessToken } from lib/api/refresh'], flag: true },
  { form: 'imported by a relative path from lib/api', file: 'lib/api/keepAlive.ts', source: "import { refreshAccessToken } from './refresh.ts'\nexport const keepAlive = () => refreshAccessToken('')", sites: ['call of refreshAccessToken in keepAlive', 'import { refreshAccessToken } from lib/api/refresh'], flag: true },
  { form: 'a type-only import', file: KEEP_ALIVE, source: "import type { refreshAccessToken } from '@/lib/api/refresh'\nexport type Renew = typeof refreshAccessToken", sites: ['import type { refreshAccessToken } from lib/api/refresh', 'reference to refreshAccessToken in module'], flag: true },
  { form: 'a namespace import', file: KEEP_ALIVE, source: "import * as refresh from '@/lib/api/refresh'\nexport const keepAlive = () => refresh.refreshAccessToken('')", sites: ['import * as refresh from lib/api/refresh'], flag: true },
  { form: 'a re-export', file: 'lib/api/index.ts', source: "export { refreshAccessToken } from './refresh'", sites: ['export { refreshAccessToken } from lib/api/refresh'], flag: true },
  { form: 'a re-export of everything', file: 'lib/api/index.ts', source: "export * from './refresh'", sites: ['export * from lib/api/refresh'], flag: true },
  { form: 'a dynamic import', file: KEEP_ALIVE, source: "export const keepAlive = () => import('@/lib/api/refresh').then((m) => m.refreshAccessToken(''))", sites: ['dynamic import of lib/api/refresh'], flag: true },
  { form: 'a require', file: 'scripts/keepAlive.cjs', source: "const { refreshAccessToken } = require('../lib/api/refresh')\nrefreshAccessToken('')", sites: ['require of lib/api/refresh'], flag: true },
  { form: 'its own post to the path', file: KEEP_ALIVE, source: "import axios from 'axios'\nexport const keepAlive = (base: string) => axios.post(`${base}/api/auth/refresh`, {}, { withCredentials: true })", sites: ['path in keepAlive'], flag: true },
  { form: 'a fetch to the path', file: KEEP_ALIVE, source: "void fetch('/api/auth/refresh', { method: 'POST', credentials: 'include' })", sites: ['path in module'], flag: true },
  { form: 'the path in a const', file: KEEP_ALIVE, source: "export const REFRESH = '/api/auth/refresh'", sites: ['path in REFRESH'], flag: true },
  { form: 'NO_REFRESH_PATHS elsewhere', file: KEEP_ALIVE, source: "const NO_REFRESH_PATHS = ['/api/auth/refresh']", sites: ['path in NO_REFRESH_PATHS'], flag: true },
  // Look-alikes, which pass.
  { form: 'a longer path that starts with it', file: KEEP_ALIVE, source: "export const STATUS = '/api/auth/refresh-status'", sites: [], flag: false },
  { form: 'another module named refresh', file: KEEP_ALIVE, source: "import { refresh } from '@/features/filings/api/refresh'\nexport const go = () => refresh()", sites: [], flag: false },
  { form: 'a local of the same name, not the import', file: KEEP_ALIVE, source: 'const refreshAccessToken = () => undefined\nexport const go = () => refreshAccessToken()', sites: [], flag: false },
  { form: 'the path in a comment', file: KEEP_ALIVE, source: '// a refresh posts to /api/auth/refresh\nexport const x = 1', sites: [], flag: false },
  { form: 'refresh.ts as it stands, its own path and nothing else', file: 'lib/api/refresh.ts', source: REFRESH_TS, sites: ['path in refreshAccessToken'], flag: false },
  { form: 'a keep-alive inside refresh.ts itself', file: 'lib/api/refresh.ts', source: `${REFRESH_TS}if (typeof window !== 'undefined') setInterval(() => void refreshAccessToken(''), 25 * 60_000)\n`, sites: ['call of refreshAccessToken in module', 'path in refreshAccessToken'], flag: true },
  { form: 'imported by an @/ path with a ./ segment', file: KEEP_ALIVE, source: "import { refreshAccessToken } from '@/lib/api/./refresh'\nexport const keepAlive = () => refreshAccessToken('')", sites: ['call of refreshAccessToken in keepAlive', 'import { refreshAccessToken } from lib/api/refresh'], flag: true },
  // Out of its reach.
  { form: 'the path assembled at run time', file: KEEP_ALIVE, source: "export const keepAlive = () => fetch('/api/auth/' + 'refresh', { method: 'POST' })", sites: [], flag: false, gap: true },
  { form: 'a timer inside refreshAccessToken posting its own path again', file: 'lib/api/refresh.ts', source: "import axios from 'axios'\n"
    + 'export async function refreshAccessToken(baseUrl: string): Promise<void> {\n  const url = `${baseUrl}/api/auth/refresh`\n'
    + '  setInterval(() => void axios.post(url, {}, { withCredentials: true }), 25 * 60_000)\n  await axios.post(url, {}, { withCredentials: true })\n}\n',
    sites: ['path in refreshAccessToken'], flag: false, gap: true },
]

describe('both ends of the hold stay in the client: the login through withoutRefreshBeside, the refresh in ensureRefreshed', () => {
  it('scores each planted form', () => {
    const loginScores = LOGIN_FORMS.map(({ form, source, file = 'features/fixture.ts', outside, inside, exempt = 0 }) => {
      const got = read(source, file)
      return { form, expected: { outside, inside, exempt }, got: { outside: got.outside.length, inside: got.inside, exempt: got.exempt } }
    })
    expect(loginScores.filter(({ expected, got }) => JSON.stringify(expected) !== JSON.stringify(got))).toEqual([])
    const refreshScores = REFRESH_FORMS.map(({ form, source, file, sites, flag }) => {
      const got = read(source, file).refresh
      const flagged = JSON.stringify(got) !== JSON.stringify([...(REFRESH_SITES[file] ?? [])].sort())
      return { form, expected: { sites: [...sites].sort(), flag }, got: { sites: got, flag: flagged } }
    })
    expect(refreshScores.filter(({ expected, got }) => JSON.stringify(expected) !== JSON.stringify(got))).toEqual([])
  })

  it('finds no other in the tree, and reads the login\'s own post and the refresh\'s sites where they are', () => {
    const listed = execFileSync('git', ['ls-files', '-z'], { cwd: FRONTEND, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 }).split('\0').filter(Boolean)
    const files = listed.filter((file) => SOURCE.test(file) && !file.startsWith('tests/'))
    // Anchored to the tree: a listing that matched nothing would pass every check below.
    expect(files.length).toBeGreaterThan(300)
    const readings = files.map((file) => ({ file, ...read(readFileSync(path.join(FRONTEND, file), 'utf8'), file) }))
    expect(readings.flatMap(({ file, outside }) => outside.map((line) => `${file}:${line}`))).toEqual([])
    expect(readings.filter(({ inside }) => inside > 0).map(({ file, inside }) => [file, inside])).toEqual([['features/auth/api/auth-api.ts', 1]])
    expect(readings.filter(({ exempt }) => exempt > 0).map(({ file, exempt }) => [file, exempt])).toEqual([[CLIENT, 1]])
    expect(Object.fromEntries(readings.filter(({ refresh }) => refresh.length > 0).map(({ file, refresh }) => [file, refresh])))
      .toEqual(Object.fromEntries(Object.entries(REFRESH_SITES).map(([file, sites]) => [file, [...sites].sort()])))
  })
})
