import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { isConfirmedGuest } from '@/features/auth/lib/confirmedGuest'
import { bindingReferences, bindingResolver } from './astBindings'

/**
 * Gate (CLAUDE.md rule 12): a page leaves for /login only for a confirmed guest, a current-user read settled on null
 * (isConfirmedGuest, features/auth/lib/confirmedGuest.ts). A guard that read `!isLoading && !user` left while a logout
 * whose request failed was still reading /me, since the reset's null is a settled `success` (logoutAndResetAccount),
 * and it left on a read that failed (offline, a 5xx), which cannot tell.
 *
 * What it reads: every tracked file under frontend/ (`git ls-files`) of each JS and TS extension, every directory but
 * tests/. A redirect is a call of push, replace, redirect, permanentRedirect or assign (on any object, or bare), or an
 * assignment to `location`, `.location` or a location's `.href`, whose target is /login: a string or template that
 * starts `/login` (its query or fragment after it, an origin before it), loginHrefWithRedirect(…), `new URL('/login',
 * …)`, either side of a condition or a fallback, a same-file const holding one, or a URL object the code points at
 * /login (`url.pathname = '/login'`). A string's replace, with its replacement, is not a redirect. Each redirect asks
 * isConfirmedGuest (in the branch an `if`, a `?:` or an `&&` takes when it holds, directly, through a same-file const
 * or as one side of an `&&`), or is exempt below with its reason, by file and by where it sits: the innermost call
 * argument (`setTimeout#1`), JSX attribute, object property or named function around it. An exemption that no longer
 * names a redirect fails, as does a redirect that two would cover.
 *
 * Out of reach, planted below as gaps: a target passed in as a parameter or returned by a function other than
 * loginHrefWithRedirect (a navigation wrapper with another name is the same gap), a target assembled by
 * concatenation, a target held in a const another module exports (`router.push(LOGIN_PATH)`) or in an object's
 * property (`router.push(ROUTES.login)`, the object imported or the file's own; no module holds /login either way
 * today), and isConfirmedGuest asked of a read other than the current user's (review-checked).
 */

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SOURCE = /\.(?:[cm]?[jt]s|[jt]sx)$/
const PREDICATE = 'isConfirmedGuest'

/** The redirects to /login that do not ask the predicate, by file and where they sit, and why each may leave. */
const EXEMPT: { file: string; at: string; why: string }[] = [
  {
    file: 'app/dashboard/page.tsx', at: 'logoutAndResetAccount#3',
    why: "the dashboard's logout continuation: it runs only once the logout took (logoutCallSitesGate.spec.ts)",
  },
  {
    file: 'features/settings/components/ConnectedAccounts.tsx', at: 'onSuccess',
    why: 'a logout of every session that succeeded: this browser is logged out with the others',
  },
  {
    file: 'app/reset-password/page.tsx', at: 'setTimeout#1',
    why: 'a password reset that succeeded, which ends every session: the reader logs in with the new password',
  },
  {
    file: 'app/dashboard/error.tsx', at: 'useEffect#1',
    why: "the dashboard's error boundary: a render error whose message names auth, not the current-user read",
  },
  { file: 'app/dashboard/error.tsx', at: 'onClick', why: "the error boundary's Log in button: the reader's own press" },
  {
    file: 'middleware.ts', at: 'function middleware',
    why: 'the edge guard: it reads the session presence cookie before any page renders, not the current-user read',
  },
]

export interface LoginRedirect {
  line: number
  /** Where it sits: the innermost call argument (`name#n`), JSX attribute, object property or named function around it. */
  at: string
  /** Whether it is taken only when isConfirmedGuest holds. */
  asks: boolean
}

const scriptKind = (file: string): ts.ScriptKind =>
  file.endsWith('.tsx') ? ts.ScriptKind.TSX : file.endsWith('.jsx') ? ts.ScriptKind.JSX : /\.[cm]?js$/.test(file) ? ts.ScriptKind.JS : ts.ScriptKind.TS
const unwrap = (node: ts.Expression): ts.Expression =>
  ts.isParenthesizedExpression(node) || ts.isAsExpression(node) || ts.isSatisfiesExpression(node) || ts.isNonNullExpression(node) ? unwrap(node.expression) : node
const nameOf = (callee: ts.Expression): string | undefined => {
  const at = unwrap(callee)
  return ts.isIdentifier(at) ? at.text : ts.isPropertyAccessExpression(at) ? at.name.text : undefined
}
const isFunction = (node: ts.Node) => ts.isArrowFunction(node) || ts.isFunctionExpression(node)
const isConst = (decl: ts.Node) => ts.isVariableDeclaration(decl) && ts.isVariableDeclarationList(decl.parent) && (decl.parent.flags & ts.NodeFlags.Const) !== 0

const REDIRECTS = new Set(['push', 'replace', 'redirect', 'permanentRedirect', 'assign'])
/** A /login URL: the path itself, its query or fragment after it, an origin before it. */
const LOGIN = /^(?:[a-z][a-z0-9+.-]*:\/\/[^/?#]*)?\/login(?:[?#][\s\S]*)?$/i
const LOGIN_HEAD = /^\/login(?:[?#]|$)/

/** Every redirect to /login in one module, read as the header says. */
export function readLoginRedirects(source: string, file: string): LoginRedirect[] {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, scriptKind(file))
  const resolve = bindingResolver(sf)
  const references = bindingReferences(sf, resolve)
  const found: LoginRedirect[] = []

  const isLoginTarget = (expr: ts.Expression | undefined, seen = new Set<ts.Node>()): boolean => {
    if (!expr || seen.has(expr)) return false
    seen.add(expr)
    const at = unwrap(expr)
    if (ts.isStringLiteralLike(at)) return LOGIN.test(at.text)
    if (ts.isTemplateExpression(at)) {
      return LOGIN_HEAD.test(at.head.text) || (at.head.text === '' && LOGIN_HEAD.test(at.templateSpans[0].literal.text))
    }
    if (ts.isCallExpression(at)) return nameOf(at.expression) === 'loginHrefWithRedirect'
    if (ts.isNewExpression(at)) return nameOf(at.expression) === 'URL' && isLoginTarget(at.arguments?.[0], seen)
    if (ts.isConditionalExpression(at)) return isLoginTarget(at.whenTrue, seen) || isLoginTarget(at.whenFalse, seen)
    if (ts.isBinaryExpression(at) && [ts.SyntaxKind.QuestionQuestionToken, ts.SyntaxKind.BarBarToken, ts.SyntaxKind.AmpersandAmpersandToken].includes(at.operatorToken.kind)) {
      return isLoginTarget(at.left, seen) || isLoginTarget(at.right, seen)
    }
    if (!ts.isIdentifier(at)) return false
    const binding = resolve(at)
    if (!binding) return false
    if (binding.init && isLoginTarget(binding.init, seen)) return true
    // A URL the code points at /login after making it: `url.pathname = '/login'`, `url.href = '/login'`.
    return references(binding.decl).some((ref) => {
      const access = ref.parent
      if (!ts.isPropertyAccessExpression(access) || access.expression !== ref || !['pathname', 'href'].includes(access.name.text)) return false
      const assignment = access.parent
      return ts.isBinaryExpression(assignment) && assignment.left === access && assignment.operatorToken.kind === ts.SyntaxKind.EqualsToken &&
        isLoginTarget(assignment.right, seen)
    })
  }

  const asksPredicate = (expr: ts.Expression, seen = new Set<ts.Node>()): boolean => {
    if (seen.has(expr)) return false
    seen.add(expr)
    const at = unwrap(expr)
    if (ts.isCallExpression(at)) return nameOf(at.expression) === PREDICATE && ts.isIdentifier(unwrap(at.expression))
    if (ts.isBinaryExpression(at) && at.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken) {
      return asksPredicate(at.left, seen) || asksPredicate(at.right, seen)
    }
    if (!ts.isIdentifier(at)) return false
    const binding = resolve(at)
    return binding?.init !== undefined && isConst(binding.decl) && asksPredicate(binding.init, seen)
  }
  /** Whether the redirect is taken only when the predicate holds: in an `if`'s then-branch, a `?:`'s true side, or an `&&`'s right. */
  const asks = (redirect: ts.Node): boolean => {
    for (let at = redirect; at.parent; at = at.parent) {
      const parent = at.parent
      if (ts.isIfStatement(parent) && parent.thenStatement === at && asksPredicate(parent.expression)) return true
      if (ts.isConditionalExpression(parent) && parent.whenTrue === at && asksPredicate(parent.condition)) return true
      if (ts.isBinaryExpression(parent) && parent.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken && parent.right === at && asksPredicate(parent.left)) {
        return true
      }
    }
    return false
  }
  const where = (redirect: ts.Node): string => {
    for (let at = redirect; at.parent; at = at.parent) {
      const parent = at.parent
      if ((ts.isCallExpression(parent) || ts.isNewExpression(parent)) && parent.arguments?.some((arg) => arg === at)) {
        return `${nameOf(parent.expression) ?? '(call)'}#${parent.arguments.indexOf(at as ts.Expression) + 1}`
      }
      if (ts.isJsxExpression(parent) && ts.isJsxAttribute(parent.parent)) return parent.parent.name.getText(sf)
      if (ts.isPropertyAssignment(parent) && parent.initializer === at) return parent.name.getText(sf)
      if (ts.isMethodDeclaration(parent) && parent.body === at) return parent.name.getText(sf)
      if (ts.isFunctionDeclaration(parent) && parent.name) return `function ${parent.name.text}`
      if (ts.isVariableDeclaration(parent) && parent.initializer === at && ts.isIdentifier(parent.name) && isFunction(unwrap(at as ts.Expression))) {
        return `const ${parent.name.text}`
      }
    }
    return '(module)'
  }
  const add = (redirect: ts.Node) => found.push({ line: sf.getLineAndCharacterOfPosition(redirect.getStart(sf)).line + 1, at: where(redirect), asks: asks(redirect) })

  const visit = (node: ts.Node): void => {
    if (ts.isCallExpression(node) && REDIRECTS.has(nameOf(node.expression) ?? '') && isLoginTarget(node.arguments[0])) {
      const replacement = node.arguments[1]
      const stringReplace = nameOf(node.expression) === 'replace' && replacement !== undefined &&
        (ts.isStringLiteralLike(replacement) || ts.isTemplateExpression(replacement) || isFunction(replacement))
      if (!stringReplace) add(node)
    }
    if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.EqualsToken && isLoginTarget(node.right)) {
      const left = unwrap(node.left)
      const isLocation = (expr: ts.Expression) => {
        const at = unwrap(expr)
        return (ts.isIdentifier(at) && at.text === 'location') || (ts.isPropertyAccessExpression(at) && at.name.text === 'location')
      }
      if (isLocation(left) || (ts.isPropertyAccessExpression(left) && left.name.text === 'href' && isLocation(left.expression))) add(node)
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return found
}

const READ = 'const userQuery = useQuery({ queryKey: queryKeys.currentUser(), queryFn: getCurrentUserSafe })\n'
const effect = (body: string) => `export function Guard({ router }) {\n  ${READ}  useEffect(() => {\n    ${body}\n  }, [])\n}\n`
const redirectsIn = (source: string, file = 'app/fixture.tsx') => readLoginRedirects(source, file).map(({ at, asks }) => ({ at, asks }))

/** Each form: the redirects the gate must find in it. A gap is a form the rule forbids that the gate passes (see the header). */
const FORMS: { form: string; source: string; file?: string; redirects: { at: string; asks: boolean }[]; gap?: true }[] = [
  // Guards that ask the predicate.
  { form: 'an if on the predicate', source: effect("if (isConfirmedGuest(userQuery)) router.push('/login')"), redirects: [{ at: 'useEffect#1', asks: true }] },
  { form: 'a const holding the predicate', source: `export function Guard({ router }) {\n  ${READ}  const guest = isConfirmedGuest(userQuery)\n  useEffect(() => { if (guest) router.replace('/login') }, [guest])\n}\n`, redirects: [{ at: 'useEffect#1', asks: true }] },
  { form: 'the predicate as one side of an &&', source: effect("if (isConfirmedGuest(userQuery) && !leaving) { router.push('/login?redirect=/dashboard') }"), redirects: [{ at: 'useEffect#1', asks: true }] },
  { form: 'an && taken on the predicate', source: effect("isConfirmedGuest(userQuery) && router.push('/login')"), redirects: [{ at: 'useEffect#1', asks: true }] },
  { form: 'a ?: taken on the predicate', source: effect("isConfirmedGuest(userQuery) ? router.replace('/login') : undefined"), redirects: [{ at: 'useEffect#1', asks: true }] },

  // Redirects that do not ask it.
  { form: "the old guard, a null that is not settled", source: effect("if (!isLoading && !user) router.push('/login')"), redirects: [{ at: 'useEffect#1', asks: false }] },
  { form: 'the predicate negated', source: effect("if (!isConfirmedGuest(userQuery)) router.push('/login')"), redirects: [{ at: 'useEffect#1', asks: false }] },
  { form: "the redirect in the predicate's else", source: effect("if (isConfirmedGuest(userQuery)) {} else router.push('/login')"), redirects: [{ at: 'useEffect#1', asks: false }] },
  { form: 'the predicate on one side of an ||', source: effect("if (isConfirmedGuest(userQuery) || userQuery.isError) router.push('/login')"), redirects: [{ at: 'useEffect#1', asks: false }] },
  { form: 'replace', source: effect("router.replace('/login')"), redirects: [{ at: 'useEffect#1', asks: false }] },
  { form: "next/navigation's redirect, in a server component", source: "export default async function Page() {\n  if (!(await session())) redirect('/login')\n}\n", redirects: [{ at: 'function Page', asks: false }] },
  { form: 'permanentRedirect with a query', source: "export const go = () => permanentRedirect('/login?from=admin')\n", redirects: [{ at: 'const go', asks: false }] },
  { form: "a location's assign", source: "export const go = () => window.location.assign('/login')\n", redirects: [{ at: 'const go', asks: false }] },
  { form: "a location's href set", source: "export function go() { window.location.href = '/login' }\n", redirects: [{ at: 'function go', asks: false }] },
  { form: 'the location set', source: "export function go() { location = '/login#top' }\n", redirects: [{ at: 'function go', asks: false }] },
  { form: "a location's replace, to a template", source: 'export function go(path) { location.replace(`/login?redirect=${path}`) }\n', redirects: [{ at: 'function go', asks: false }] },
  { form: 'an origin before the path', source: 'export function go(router) { router.push(`${origin}/login`) }\n', redirects: [{ at: 'function go', asks: false }] },
  { form: 'an absolute URL', source: "export function go(router) { router.push('https://earningsnerd.io/login') }\n", redirects: [{ at: 'function go', asks: false }] },
  { form: 'loginHrefWithRedirect', source: 'export function go(router, path) { router.push(loginHrefWithRedirect(path)) }\n', redirects: [{ at: 'function go', asks: false }] },
  { form: 'a const target', source: "const target = '/login'\nexport function go(router) { router.push(target) }\n", redirects: [{ at: 'function go', asks: false }] },
  { form: 'either side of a condition', source: "export function go(router, out) { router.push(out ? '/login' : '/') }\n", redirects: [{ at: 'function go', asks: false }] },
  { form: 'a URL the code points at /login', file: 'middleware.ts', source: "export function middleware(request) {\n  const url = request.nextUrl.clone()\n  url.pathname = '/login'\n  return NextResponse.redirect(url)\n}\n", redirects: [{ at: 'function middleware', asks: false }] },
  { form: 'new URL', source: "export function middleware(request) { return NextResponse.redirect(new URL('/login', request.url)) }\n", redirects: [{ at: 'function middleware', asks: false }] },
  { form: 'a continuation, by where it sits', source: "export const go = () => logoutAndResetAccount(qc, logout, (ok) => { if (!ok) return; router.push('/login') })\n", redirects: [{ at: 'logoutAndResetAccount#3', asks: false }] },
  { form: 'a JSX handler, by where it sits', file: 'app/fixture.jsx', source: "export const B = ({ router }) => <button onClick={() => router.push('/login')}>Log in</button>\n", redirects: [{ at: 'onClick', asks: false }] },
  { form: 'a timer, by where it sits, in an .mjs file', file: 'scripts/fixture.mjs', source: "setTimeout(() => router.push('/login'), 3000)\n", redirects: [{ at: 'setTimeout#1', asks: false }] },

  // Not redirects to /login.
  {
    form: 'a link, another path, an API path, a list and a string replace',
    source: `export const L = () => <Link href="/login">Log in</Link>
export function f(router, s) {
  router.push('/loginhelp'); router.push('/dashboard'); fetch('/api/auth/login'); const routes = ['/login']
  return s.replace('/login', '')
}
`,
    redirects: [],
  },

  // Out of reach (the header names each): the gate passes them.
  { form: 'a target passed in as a parameter', source: "function go(router, to) { router.push(to) }\nexport const out = (router) => go(router, '/login')\n", redirects: [], gap: true },
  { form: 'a target assembled by concatenation', source: "export function go(router) { router.push('/log' + 'in') }\n", redirects: [], gap: true },
  { form: 'a target held in a const another module exports', source: "import { LOGIN_PATH } from '@/lib/routes'\nexport function go(router) { router.push(LOGIN_PATH) }\n", redirects: [], gap: true },
  { form: "a target held in an imported object's property", source: "import { ROUTES } from '@/lib/routes'\nexport function go(router) { router.push(ROUTES.login) }\n", redirects: [], gap: true },
  { form: "a target held in the file's own object's property", source: "const ROUTES = { login: '/login' }\nexport function go(router) { router.replace(ROUTES.login) }\n", redirects: [], gap: true },
  { form: 'the predicate asked of another read', source: effect("if (isConfirmedGuest(otherQuery)) router.push('/login')"), redirects: [{ at: 'useEffect#1', asks: true }], gap: true },
]

const listed = execFileSync('git', ['ls-files', '-z'], { cwd: FRONTEND, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 }).split('\0').filter(Boolean)
const files = listed.filter((file) => SOURCE.test(file) && !file.startsWith('tests/'))
const found = files.flatMap((file) => readLoginRedirects(readFileSync(path.join(FRONTEND, file), 'utf8'), file).map((redirect) => ({ file, ...redirect })))

describe('a page leaves for /login only for a confirmed guest', () => {
  it('reads every tracked source file, of every JS and TS extension, in every directory but tests/', () => {
    expect(files.length).toBeGreaterThan(300)
    expect(files).toEqual(expect.arrayContaining(['middleware.ts', 'next.config.js', 'eslint.config.mjs', 'app/admin/layout.tsx']))
    // The guards that ask, as well as the exemptions: a reader that found nothing would pass the checks below.
    expect(found.filter(({ asks }) => asks).map(({ file }) => file).sort()).toEqual([
      'app/admin/layout.tsx', 'app/dashboard/page.tsx', 'app/dashboard/settings/page.tsx', 'app/dashboard/watchlist/page.tsx',
    ])
  })

  it('scores each planted form', () => {
    const scored = FORMS.map(({ form, source, file, redirects }) => ({ form, expected: redirects, got: redirectsIn(source, file) }))
    expect(scored.filter(({ expected, got }) => JSON.stringify(expected) !== JSON.stringify(got))).toEqual([])
  })

  it('each redirect asks isConfirmedGuest, or is exempt with its reason, and each exemption names one redirect', () => {
    const exempt = EXEMPT.map(({ file, at }) => `${file} ${at}`).sort()
    const unasked = found.filter(({ asks }) => !asks).map(({ file, at }) => `${file} ${at}`).sort()
    expect(
      unasked,
      'a redirect to /login asks isConfirmedGuest(<the current-user read>) or joins EXEMPT with its reason ' +
        '(tests/unit/loginRedirectsAskConfirmedGuest.spec.ts)',
    ).toEqual(exempt)
  })

  it('isConfirmedGuest holds only for a read that settled on null', () => {
    const read = (data: unknown, fetchStatus: 'idle' | 'fetching' | 'paused', isError: boolean) => isConfirmedGuest({ data, fetchStatus, isError })
    expect(read(null, 'idle', false)).toBe(true)
    // A null still being read (a logout whose request failed reads /me), or paused offline.
    expect(read(null, 'fetching', false)).toBe(false)
    expect(read(null, 'paused', false)).toBe(false)
    // A read that failed cannot tell, nor can one that has not answered, and a user is no guest.
    expect(read(null, 'idle', true)).toBe(false)
    expect(read(undefined, 'idle', false)).toBe(false)
    expect(read({ id: 7 }, 'idle', false)).toBe(false)
  })
})
