import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { bindingReferences, bindingResolver, type Binding } from './astBindings'
import { lazyImport } from './importWalk'

/**
 * Gate (CLAUDE.md rule 12): a logout that did not take never navigates. `logoutAndResetAccount`
 * (features/auth/lib/accountQueryState.ts) settles every logout a control starts: when the request fails and /me still
 * answers with the reader, or cannot be read, it tells the reader, calls the continuation with `false` and rejects. A
 * control that navigated then would leave a reader who is still signed in believing they are not, on a shared
 * computer above all. So every call of it is inventoried here, its continuation is an inline, synchronous function that
 * opens with `if (!succeeded) return` (the continuation shares a turn with the helper's ownership check), and what
 * runs when it rejects goes nowhere.
 *
 * What it reads: every tracked file under frontend/ (`git ls-files`) of each JS and TS extension (.ts .tsx .js .jsx
 * .mjs .cjs .mts .cts), every directory but tests/, parsed by its extension. Each occurrence of the name outside its
 * own declaration is either a plain named import (`import { logoutAndResetAccount } from …`) or the callee of a call.
 * Anything else is refused, since a call through it would escape the inventory: an import that renames it, a
 * namespace or default import of its module, a re-export of it (renamed or not, `export *` included), a dynamic
 * import or a require of its module, the name used as a value (a const alias, a property of a namespace, an argument)
 * or as a string (`m['logoutAndResetAccount']`), and a declaration of the name elsewhere.
 *
 * Each call takes one of two shapes, and anything else is refused (`no catch`):
 * - A handler: `await logoutAndResetAccount(…)` as a statement inside a try with a catch. Nothing in the handler
 *   navigates outside the continuation (its catch, its finally, the statements after it), nor any same-file function
 *   it names there. Its promise goes nowhere: it is inline in a JSX attribute, or a const (`useCallback` included) or a
 *   function declaration whose every use is a JSX attribute or a call whose result is discarded (`void handle()`).
 * - A mutation: the whole body of `mutationFn` in an inline `useMutation({…})` options object, whose `onError` and
 *   `onSettled` navigate nowhere (an inline function, or a same-file one), with no `throwOnError` and no spread. Its
 *   result is a const read only as `.mutate()` with no options, or for its state: `mutateAsync`, `mutate(v, options)`,
 *   a destructured result or the result passed on is refused.
 * Navigation is a call of push, replace, back, forward, refresh, assign, reload, redirect or permanentRedirect (on any
 * object, so an array's push in such a handler is refused too; a string's replace, with its replacement, is not), and
 * an assignment to `location`, `.location`, `.href` or `.pathname`.
 *
 * Out of reach, planted below as gaps: navigation through a function imported from another module, or through state
 * an effect acts on; a dynamic import whose specifier is computed; and a component that chains the promise of a
 * handler handed to it as a prop.
 */

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const NAME = 'logoutAndResetAccount'
const DEFINITION = 'features/auth/lib/accountQueryState.ts'
/** Its module under any specifier that names it: `@/features/auth/lib/accountQueryState`, `./accountQueryState.ts`. */
const MODULE = /(?:^|\/)accountQueryState(?:\.[cm]?[jt]sx?)?$/
/** Every JS and TS extension. */
const SOURCE = /\.(?:[cm]?[jt]s|[jt]sx)$/

/** Each call of the helper, by file: the control it settles. */
const INVENTORY: Record<string, string> = {
  'app/dashboard/page.tsx': "the dashboard's Log out, through its logout mutation",
  'components/Header.tsx': "the site header's mobile menu",
  'features/auth/components/UserMenu.tsx': "the site header's account menu",
}

type Problem =
  | 'renamed import' | 'namespace' | 're-export' | 'dynamic import' | 'require' | 'reference' | 'string' | 'declaration'
  | 'continuation' | 'no catch' | 'navigates on failure' | 'escapes'

/** The files the gate reads, from a `git ls-files` listing of frontend/. */
export const scannedFiles = (listed: string[]): string[] => listed.filter((file) => SOURCE.test(file) && !file.startsWith('tests/'))

const scriptKind = (file: string): ts.ScriptKind =>
  file.endsWith('.tsx') ? ts.ScriptKind.TSX : file.endsWith('.jsx') ? ts.ScriptKind.JSX : /\.[cm]?js$/.test(file) ? ts.ScriptKind.JS : ts.ScriptKind.TS

const NAVIGATORS = new Set(['push', 'replace', 'back', 'forward', 'refresh', 'assign', 'reload', 'redirect', 'permanentRedirect'])
const LOCATION_PARTS = new Set(['location', 'href', 'pathname'])

const unwrap = (node: ts.Expression): ts.Expression =>
  ts.isParenthesizedExpression(node) || ts.isAsExpression(node) || ts.isSatisfiesExpression(node) || ts.isNonNullExpression(node) ? unwrap(node.expression) : node
/** The outermost node a value reaches through parentheses and type assertions. */
const outermost = (node: ts.Node): ts.Node => {
  let at = node
  while (ts.isParenthesizedExpression(at.parent) || ts.isAsExpression(at.parent) || ts.isSatisfiesExpression(at.parent) || ts.isNonNullExpression(at.parent)) at = at.parent
  return at
}
const calleeName = (call: ts.CallExpression): string | undefined => {
  const callee = unwrap(call.expression)
  return ts.isIdentifier(callee) ? callee.text : ts.isPropertyAccessExpression(callee) ? callee.name.text : undefined
}
const isFunction = (node: ts.Node): node is ts.ArrowFunction | ts.FunctionExpression | ts.FunctionDeclaration =>
  ts.isArrowFunction(node) || ts.isFunctionExpression(node) || ts.isFunctionDeclaration(node)
const innermostFunction = (node: ts.Node): ts.SignatureDeclaration | undefined => {
  for (let at = node.parent; at; at = at.parent) if (ts.isFunctionLike(at)) return at
  return undefined
}
const isConst = (decl: ts.VariableDeclaration) => ts.isVariableDeclarationList(decl.parent) && (decl.parent.flags & ts.NodeFlags.Const) !== 0

function isNavigation(node: ts.Node): boolean {
  if (ts.isCallExpression(node)) {
    const name = calleeName(node)
    if (!name || !NAVIGATORS.has(name)) return false
    const replacement = node.arguments[1]
    // A string's replace: a pattern, then the replacement or a function that makes it.
    return !(name === 'replace' && replacement && (ts.isStringLiteralLike(replacement) || ts.isTemplateExpression(replacement) || isFunction(replacement)))
  }
  if (ts.isBinaryExpression(node) && node.operatorToken.kind >= ts.SyntaxKind.FirstAssignment && node.operatorToken.kind <= ts.SyntaxKind.LastAssignment) {
    const left = unwrap(node.left)
    return (ts.isIdentifier(left) && left.text === 'location') || (ts.isPropertyAccessExpression(left) && LOCATION_PARTS.has(left.name.text))
  }
  return false
}

/** Whether a continuation is an inline, synchronous function that opens with `if (!<its parameter>) return`. */
function returnsAtOnceOnFailure(continuation: ts.Expression): boolean {
  if (!ts.isArrowFunction(continuation) && !ts.isFunctionExpression(continuation)) return false
  if (continuation.asteriskToken || continuation.modifiers?.some((m) => m.kind === ts.SyntaxKind.AsyncKeyword)) return false
  const parameter = continuation.parameters[0]?.name
  if (!parameter || !ts.isIdentifier(parameter) || !ts.isBlock(continuation.body)) return false
  const first = continuation.body.statements[0]
  if (!first || !ts.isIfStatement(first) || first.elseStatement) return false
  const condition = unwrap(first.expression)
  if (!ts.isPrefixUnaryExpression(condition) || condition.operator !== ts.SyntaxKind.ExclamationToken) return false
  const operand = unwrap(condition.operand)
  if (!ts.isIdentifier(operand) || operand.text !== parameter.text) return false
  const then = first.thenStatement
  const exit = ts.isBlock(then) && then.statements.length === 1 ? then.statements[0] : then
  return ts.isReturnStatement(exit) && exit.expression === undefined
}

export interface LogoutCallReading {
  /** The line of each call of the helper. */
  calls: number[]
  problems: { line: number; problem: Problem }[]
}

/** Every occurrence of the helper in one module, and what is wrong with each, read as the header says. */
export function readLogoutCalls(source: string, file: string): LogoutCallReading {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, scriptKind(file))
  const resolve = bindingResolver(sf)
  const references = bindingReferences(sf, resolve)
  const line = (node: ts.Node) => sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
  const calls: number[] = []
  const problems: LogoutCallReading['problems'] = []
  const flag = (node: ts.Node, problem: Problem) => problems.push({ line: line(node), problem })
  const isModule = (spec: ts.Node | undefined) => spec !== undefined && ts.isStringLiteralLike(spec) && MODULE.test(spec.text)

  /** The function a binding holds, if a same-file one: a declaration, a const's arrow or function, or useCallback's. */
  const functionOf = (binding: Binding | undefined): ts.Node | undefined => {
    if (!binding) return undefined
    if (ts.isFunctionDeclaration(binding.decl)) return binding.decl
    const init = binding.init && unwrap(binding.init)
    if (!init) return undefined
    if (isFunction(init)) return init
    if (ts.isCallExpression(init) && calleeName(init) === 'useCallback' && init.arguments[0] && isFunction(unwrap(init.arguments[0]))) return init.arguments[0]
    return undefined
  }
  /** Whether anything under `root` navigates, outside `skip`, the same-file functions it names included. */
  const navigates = (root: ts.Node | undefined, skip?: ts.Node, seen = new Set<ts.Node>()): boolean => {
    if (!root || seen.has(root)) return false
    seen.add(root)
    let found = false
    const walk = (node: ts.Node): void => {
      if (found || node === skip) return
      if (isNavigation(node) || (ts.isIdentifier(node) && navigates(functionOf(resolve(node)), skip, seen))) {
        found = true
        return
      }
      ts.forEachChild(node, walk)
    }
    walk(root)
    return found
  }

  /** The uses of a handler's promise: none when React discards it (inline in a JSX attribute), else its binding's references. */
  const handlerUses = (handler: ts.SignatureDeclaration): ts.Node[] | undefined => {
    const at = outermost(handler)
    if (ts.isJsxExpression(at.parent) && ts.isJsxAttribute(at.parent.parent)) return []
    if (ts.isFunctionDeclaration(handler) && handler.name) return [...references(handler)]
    let holder = at.parent
    if (ts.isCallExpression(holder) && calleeName(holder) === 'useCallback' && holder.arguments[0] === at) holder = outermost(holder).parent
    if (ts.isVariableDeclaration(holder) && ts.isIdentifier(holder.name) && isConst(holder)) return [...references(holder)]
    return undefined
  }
  /** React discards what a handler handed to a JSX attribute returns, and a call whose result is a statement's or void's. */
  const discarded = (use: ts.Node): boolean => {
    const at = outermost(use)
    if (ts.isJsxExpression(at.parent) && ts.isJsxAttribute(at.parent.parent)) return true
    const call = at.parent
    if (!ts.isCallExpression(call) || call.expression !== at) return false
    const result = outermost(call).parent
    return ts.isExpressionStatement(result) || ts.isVoidExpression(result)
  }

  /** `await logoutAndResetAccount(…)` as a statement inside a try, within the handler, whose catch the try has. */
  const awaitedInTry = (call: ts.CallExpression, handler: ts.SignatureDeclaration | undefined): boolean => {
    const awaited = outermost(call).parent
    if (!handler || !ts.isAwaitExpression(awaited)) return false
    const statement = outermost(awaited).parent
    if (!ts.isExpressionStatement(statement)) return false
    for (let at: ts.Node = statement; at.parent && at !== handler; at = at.parent) {
      if (ts.isTryStatement(at.parent) && at.parent.tryBlock === at) return at.parent.catchClause !== undefined
    }
    return false
  }
  const readHandler = (call: ts.CallExpression, handler: ts.SignatureDeclaration, continuation: ts.Node | undefined) => {
    if (navigates(handler, continuation)) flag(call, 'navigates on failure')
    const uses = handlerUses(handler)
    if (!uses) flag(handler, 'escapes')
    else for (const use of uses) if (!discarded(use)) flag(use, 'escapes')
  }

  /** The useMutation call whose inline options' mutationFn is this arrow, when its whole body is the call. */
  const mutationOf = (call: ts.CallExpression, handler: ts.SignatureDeclaration | undefined): ts.CallExpression | undefined => {
    if (!handler || !ts.isArrowFunction(handler)) return undefined
    const body = handler.body
    const only = ts.isBlock(body)
      ? body.statements.length === 1 && ts.isReturnStatement(body.statements[0]) && body.statements[0].expression !== undefined && unwrap(body.statements[0].expression) === call
      : unwrap(body) === call
    const property = outermost(handler).parent
    if (!only || !ts.isPropertyAssignment(property) || property.name.getText(sf) !== 'mutationFn') return undefined
    const options = property.parent
    const owner = outermost(options).parent
    return ts.isCallExpression(owner) && calleeName(owner) === 'useMutation' && owner.arguments[0] === outermost(options) ? owner : undefined
  }
  const readMutation = (mutation: ts.CallExpression) => {
    const options = unwrap(mutation.arguments[0]) as ts.ObjectLiteralExpression
    for (const property of options.properties) {
      if (ts.isSpreadAssignment(property)) {
        flag(property, 'escapes')
        continue
      }
      const key = property.name?.getText(sf)
      if (key === 'throwOnError') flag(property, 'escapes')
      if (key === 'onError' || key === 'onSettled') {
        const value = ts.isPropertyAssignment(property) ? property.initializer : ts.isShorthandPropertyAssignment(property) ? property.name : property
        if (navigates(value)) flag(property, 'navigates on failure')
      }
    }
    const holder = outermost(mutation).parent
    if (!ts.isVariableDeclaration(holder) || !ts.isIdentifier(holder.name) || !isConst(holder)) {
      flag(mutation, 'escapes')
      return
    }
    for (const use of references(holder)) {
      const access = outermost(use).parent
      if (!ts.isPropertyAccessExpression(access) || access.expression !== outermost(use)) {
        flag(use, 'escapes')
        continue
      }
      if (access.name.text === 'mutateAsync') flag(use, 'escapes')
      if (access.name.text !== 'mutate') continue
      const call = outermost(access).parent
      if (!ts.isCallExpression(call) || call.expression !== outermost(access) || call.arguments.length > 1) flag(use, 'escapes')
    }
  }

  const readCall = (call: ts.CallExpression) => {
    calls.push(line(call))
    const continuation = call.arguments[2]
    if (continuation && !returnsAtOnceOnFailure(continuation)) flag(call, 'continuation')
    const handler = innermostFunction(call)
    const mutation = mutationOf(call, handler)
    if (mutation) readMutation(mutation)
    else if (handler && awaitedInTry(call, handler)) readHandler(call, handler, continuation)
    else flag(call, 'no catch')
  }

  const readName = (id: ts.Identifier) => {
    const parent = id.parent
    if (ts.isImportSpecifier(parent) || ts.isExportSpecifier(parent)) return // read with its declaration below
    if (ts.isCallExpression(parent) && parent.expression === id) return readCall(parent)
    const declares = (ts.isFunctionDeclaration(parent) || ts.isVariableDeclaration(parent) || ts.isParameter(parent) ||
      ts.isBindingElement(parent) || ts.isClassDeclaration(parent) || ts.isFunctionExpression(parent)) && parent.name === id
    if (declares) {
      if (!(file === DEFINITION && ts.isFunctionDeclaration(parent))) flag(id, 'declaration')
      return
    }
    flag(id, 'reference')
  }

  const visit = (node: ts.Node): void => {
    if (ts.isImportDeclaration(node) && isModule(node.moduleSpecifier) && !node.importClause?.isTypeOnly) {
      const clause = node.importClause
      if (clause?.name || (clause?.namedBindings && ts.isNamespaceImport(clause.namedBindings))) flag(node, 'namespace')
    }
    if (ts.isImportSpecifier(node) && !node.isTypeOnly && node.propertyName && [node.name.text, node.propertyName.getText(sf)].includes(NAME)) {
      flag(node, 'renamed import')
    }
    if (ts.isExportDeclaration(node) && !node.isTypeOnly) {
      const clause = node.exportClause
      if (isModule(node.moduleSpecifier) && !clause) flag(node, 're-export')
      if (isModule(node.moduleSpecifier) && clause && ts.isNamespaceExport(clause)) flag(node, 'namespace')
      if (clause && ts.isNamedExports(clause) && clause.elements.some((el) => [el.name.getText(sf), el.propertyName?.getText(sf)].includes(NAME))) {
        flag(node, 're-export')
      }
    }
    const lazy = lazyImport(node)
    if (lazy !== undefined && MODULE.test(lazy)) flag(node, 'dynamic import')
    if (ts.isCallExpression(node) && calleeName(node) === 'require' && isModule(node.arguments[0])) flag(node, 'require')
    if (ts.isStringLiteralLike(node) && node.text === NAME) flag(node, 'string')
    if (ts.isIdentifier(node) && node.text === NAME) readName(node)
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return { calls, problems: problems.sort((a, b) => a.line - b.line || a.problem.localeCompare(b.problem)) }
}

const problemsOf = (source: string, file = 'app/fixture.tsx') => readLogoutCalls(source, file).problems.map(({ problem }) => problem)

const IMPORT = "import { logoutAndResetAccount } from '@/features/auth/lib/accountQueryState'\n"
/** A handler of the account menu's shape, with its catch's body and what follows the try replaceable. */
const handler = ({ caught = 'opener.current?.focus({ preventScroll: true })', after = '', continuation = `(succeeded) => {
      if (!succeeded) return
      router.push('/')
      router.refresh()
    }`, use = '<button onClick={handleLogout}>Log out</button>', finale = '' } = {}) => `${IMPORT}
export function Menu({ router, queryClient, logout, opener }) {
  const handleLogout = async () => {
    try {
      await logoutAndResetAccount(queryClient, logout, ${continuation})
    } catch {
      ${caught}
    }${finale}
    ${after}
  }
  return ${use}
}
`
/** A mutation of the dashboard's shape, with its options and its uses replaceable. */
const mutation = ({ options = "networkMode: 'always',", use = '<button onClick={() => logoutMutation.mutate()} aria-disabled={logoutMutation.isPending}>Log out</button>', holder = 'const logoutMutation' } = {}) => `${IMPORT}
export function Page({ router, queryClient, logout }) {
  ${holder} = useMutation({
    mutationFn: () => logoutAndResetAccount(queryClient, logout, (succeeded) => {
      if (!succeeded) return
      router.push('/login')
    }),
    ${options}
  })
  return ${use}
}
`

/** Each form: what the gate must say of it. A gap is a form the rule forbids that the gate passes (see the header). */
const FORMS: { form: string; source: string; file?: string; problems: Problem[]; gap?: true }[] = [
  // Look-alikes that must pass.
  { form: "the account menu's handler, whose catch hands focus back", source: handler(), problems: [] },
  { form: "the dashboard's mutation, with a toast on error", source: mutation({ options: "networkMode: 'always',\n    onError: () => toast.error('x')," }), problems: [] },
  { form: 'an inline handler whose continuation returns from a block', source: `${IMPORT}
export const Item = ({ qc, logout, router }) => <button onClick={async () => {
  try { await logoutAndResetAccount(qc, logout, (ok) => { if (!ok) { return } router.push('/') }) } catch { console.warn('kept') }
}}>Log out</button>
`, problems: [] },
  { form: 'a handler called from an inline arrow, its result discarded', source: handler({ use: '<button onClick={() => void handleLogout()}>Log out</button>' }), problems: [] },
  { form: 'a handler wrapped in useCallback', source: handler().replace('const handleLogout = async () => {', 'const handleLogout = useCallback(async () => {').replace('\n  return <button', ', [])\n  return <button'), problems: [] },
  { form: "a string's replace in the catch", source: handler({ caught: "setMessage(String(error).replace('Error: ', ''))" }), problems: [] },
  { form: 'a longer name, a comment and copy that mention it', source: `// logoutAndResetAccount settles the logout
export const note = 'Log out and reset the account'
export const logoutAndResetAccounts = () => logoutAndResetAccountsInner()
`, problems: [] },
  { form: 'no continuation, nothing that navigates', source: handler({ continuation: '' }).replace('logout, )', 'logout)'), problems: [] },

  // Forms that escape the inventory.
  { form: 'a namespace import, and the call through it', source: `import * as account from '@/features/auth/lib/accountQueryState'
async function out(qc, logout) { try { await account.logoutAndResetAccount(qc, logout) } catch {} }
`, problems: ['namespace', 'reference'] },
  { form: 'a default import of its module', source: "import account from '../features/auth/lib/accountQueryState'\n", problems: ['namespace'] },
  { form: 'a const alias, and the call through it', source: `${IMPORT}const out = logoutAndResetAccount
async function go(qc, logout) { try { await out(qc, logout) } catch {} }
`, problems: ['reference'] },
  { form: 'a renamed import', source: "import { logoutAndResetAccount as out } from '@/features/auth/lib/accountQueryState'\n", problems: ['renamed import'] },
  { form: 'a renaming barrel re-export', source: "export { logoutAndResetAccount as logOut } from './accountQueryState'\n", problems: ['re-export'] },
  { form: 'a plain re-export', source: "export { logoutAndResetAccount } from '@/features/auth/lib/accountQueryState.ts'\n", problems: ['re-export'] },
  { form: 'a star re-export', source: "export * from './accountQueryState'\n", problems: ['re-export'] },
  { form: 'a namespace re-export', source: "export * as account from './accountQueryState'\n", problems: ['namespace'] },
  { form: 'a local export that renames it', source: `${IMPORT}export { logoutAndResetAccount as logOut }\n`, problems: ['re-export'] },
  { form: 'a dynamic import, destructured', source: `async function go(qc, logout) {
  const { logoutAndResetAccount: out } = await import('@/features/auth/lib/accountQueryState')
  try { await out(qc, logout) } catch {}
}
`, problems: ['dynamic import', 'reference'] },
  { form: 'a dynamic import, its property called', source: `async function go(qc, logout) {
  try { await (await import('@/features/auth/lib/accountQueryState')).logoutAndResetAccount(qc, logout) } catch {}
}
`, problems: ['dynamic import', 'reference'] },
  { form: 'a lazy import of its module', source: "export const later = () => import('../lib/accountQueryState')\n", problems: ['dynamic import'] },
  { form: 'a require, in a .cjs file', file: 'scripts/fixture.cjs', source: "const m = require('../features/auth/lib/accountQueryState')\nmodule.exports = m\n", problems: ['require'] },
  { form: 'the name as a string key', source: `import * as m from '@/features/auth/lib/accountQueryState'
export const go = (qc, logout) => m['logoutAndResetAccount'](qc, logout)
`, problems: ['namespace', 'string'] },
  { form: 'the name handed on as a value', source: `${IMPORT}export const actions = { logout: logoutAndResetAccount }\n`, problems: ['reference'] },
  { form: 'a declaration of the name elsewhere', source: 'export async function logoutAndResetAccount() {}\n', problems: ['declaration'] },

  // Forms that navigate when the logout did not take.
  { form: 'a catch that navigates', source: handler({ caught: "router.push('/')" }), problems: ['navigates on failure'] },
  { form: 'a catch that navigates, in a .jsx file', file: 'components/Fixture.jsx', source: handler({ caught: "router.replace('/login')" }), problems: ['navigates on failure'] },
  { form: 'a catch that calls a same-file function that navigates', source: handler({ caught: 'leave()' }).replace('export function Menu', "const leave = () => window.location.assign('/')\nexport function Menu"), problems: ['navigates on failure'] },
  { form: 'a catch that sets the location', source: handler({ caught: "window.location.href = '/'" }), problems: ['navigates on failure'] },
  { form: 'a finally that navigates', source: handler({ finale: " finally {\n      router.refresh()\n    }" }), problems: ['navigates on failure'] },
  { form: 'a statement after the try that navigates', source: handler({ after: "router.push('/')" }), problems: ['navigates on failure'] },
  { form: 'a continuation that navigates first', source: handler({ continuation: "(succeeded) => { router.push('/') }" }), problems: ['continuation'] },
  { form: 'a continuation that navigates only on success, without returning first', source: handler({ continuation: "(succeeded) => { if (succeeded) router.push('/') }" }), problems: ['continuation'] },
  { form: 'a continuation passed by name', source: handler({ continuation: 'onSettled' }), problems: ['continuation'] },
  { form: 'an async continuation', source: handler({ continuation: "async (succeeded) => {\n      if (!succeeded) return\n      router.push('/')\n    }" }), problems: ['continuation'] },
  { form: 'a call nobody catches', source: `${IMPORT}export const go = (qc, logout) => { void logoutAndResetAccount(qc, logout) }\n`, problems: ['no catch'] },
  { form: "a call whose rejection a .catch navigates on", source: `${IMPORT}export const go = (qc, logout, router) => logoutAndResetAccount(qc, logout).catch(() => router.push('/'))\n`, problems: ['no catch'] },
  { form: 'a handler whose caller navigates when it settles', source: handler({ use: "<button onClick={() => handleLogout().then(() => router.push('/'))}>Log out</button>" }), problems: ['escapes'] },
  { form: 'a handler another function awaits', source: handler({ use: '<button onClick={async () => { await handleLogout() }}>Log out</button>' }), problems: ['escapes'] },
  { form: "a mutation whose onError navigates", source: mutation({ options: "onError: () => router.push('/')," }), problems: ['navigates on failure'] },
  { form: 'a mutation whose onSettled calls a same-file function that navigates', source: mutation({ options: 'onSettled: leave,' }).replace('export function Page', "function leave() { redirect('/') }\nexport function Page"), problems: ['navigates on failure'] },
  { form: 'a mutation that throws to an error boundary', source: mutation({ options: 'throwOnError: true,' }), problems: ['escapes'] },
  { form: 'a mutation whose options are spread in', source: mutation({ options: '...more,' }), problems: ['escapes'] },
  { form: 'a mutation awaited through mutateAsync', source: mutation({ use: "<button onClick={() => logoutMutation.mutateAsync().catch(() => router.push('/'))}>Log out</button>" }), problems: ['escapes'] },
  { form: 'a mutation handed options at mutate', source: mutation({ use: "<button onClick={() => logoutMutation.mutate(undefined, { onError: () => router.push('/') })}>Log out</button>" }), problems: ['escapes'] },
  { form: 'a mutation whose result is destructured', source: mutation({ holder: 'const { mutate }', use: '<button onClick={() => mutate()}>Log out</button>' }), problems: ['escapes'] },

  // Out of reach (the header names each): the gate passes them.
  { form: 'navigation through an imported helper', source: handler({ caught: 'goHome(router)' }), problems: [], gap: true },
  { form: 'navigation through state an effect acts on', source: handler({ caught: 'setLeaving(true)' }), problems: [], gap: true },
  { form: 'a dynamic import with a computed specifier', source: 'export const go = async (spec, name, qc, logout) => (await import(spec))[name](qc, logout)\n', problems: [], gap: true },
  { form: "a component that chains its handler prop's promise", source: handler({ use: '<Confirm onConfirm={handleLogout} />' }), problems: [], gap: true },
]

const listed = execFileSync('git', ['ls-files', '-z'], { cwd: FRONTEND, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 }).split('\0').filter(Boolean)
const files = scannedFiles(listed)
const readings = files.map((file) => ({ file, ...readLogoutCalls(readFileSync(path.join(FRONTEND, file), 'utf8'), file) }))

describe('a logout that did not take never navigates', () => {
  it('reads every tracked source file, of every JS and TS extension, in every directory but tests/', () => {
    expect(scannedFiles([
      'app/a.ts', 'app/b.tsx', 'c.js', 'lib/d.jsx', 'e.mjs', 'f.cjs', 'scripts/g.mts', 'h.cts', 'types/i.d.ts',
      'tests/unit/x.spec.ts', 'tests/e2e/y.spec.ts', 'public/logo.svg', 'README.md', 'data.json',
    ])).toEqual(['app/a.ts', 'app/b.tsx', 'c.js', 'lib/d.jsx', 'e.mjs', 'f.cjs', 'scripts/g.mts', 'h.cts', 'types/i.d.ts'])
    // Anchored to the tree: a walk that matched nothing would pass every check below.
    expect(files.length).toBeGreaterThan(300)
    expect(files).toEqual(expect.arrayContaining([DEFINITION, 'middleware.ts', 'next.config.js', 'eslint.config.mjs']))
  })

  it('scores each planted form', () => {
    const scored = FORMS.map(({ form, source, file, problems }) => ({ form, expected: problems, got: problemsOf(source, file) }))
    expect(scored.filter(({ expected, got }) => JSON.stringify(expected) !== JSON.stringify(got))).toEqual([])
    // Each look-alike is seen as the call it is, so its passing is the gate reading it, not missing it.
    for (const { form, source, file, problems, gap } of FORMS) {
      if (problems.length === 0 && !gap && source.includes(`${NAME}(`)) expect(readLogoutCalls(source, file ?? 'app/fixture.tsx').calls, form).toHaveLength(1)
    }
  })

  it('finds every call in the inventory, one per control, each taking a shape it can read', () => {
    const problems = readings.flatMap(({ file, problems }) => problems.map(({ line, problem }) => `${file}:${line} ${problem}`))
    expect(problems, 'see the header of tests/unit/logoutCallSitesGate.spec.ts for the shapes the gate reads').toEqual([])
    const calls = Object.fromEntries(readings.filter(({ calls }) => calls.length > 0).map(({ file, calls }) => [file, calls.length]))
    // A new control that logs out joins INVENTORY, and failedLogoutChecksSession.spec.tsx's cases.
    expect(calls).toEqual(Object.fromEntries(Object.keys(INVENTORY).map((file) => [file, 1])))
  })
})
