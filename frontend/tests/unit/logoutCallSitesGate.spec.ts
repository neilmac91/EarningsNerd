import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { bindingReferences, bindingResolver, type Binding } from './astBindings'
import { lazyImport } from './importWalk'
import { LOGOUT_CALL_SITES } from './logoutCallSites'

/**
 * Gate (CLAUDE.md rule 12): a logout that did not take never navigates. `logoutAndResetAccount`
 * (features/auth/lib/accountQueryState.ts) settles every logout a control starts: when the request fails and /me still
 * answers with the reader, or cannot be read, it tells the reader, calls the continuation with `false` and rejects. A
 * control that navigated then would leave a reader who is still signed in believing they are not, on a shared
 * computer above all. So every call of it is inventoried (LOGOUT_CALL_SITES, tests/unit/logoutCallSites.ts, whose every
 * file failedLogoutChecksSession.spec.tsx gives a control and its failure cases), its continuation is an inline,
 * synchronous function that opens with `if (!succeeded) return` (the continuation shares a turn with the helper's
 * ownership check), and the continuation is the one place a logout navigates: nothing that runs when it rejects, or
 * whatever its outcome, goes anywhere.
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
 *   navigates outside the continuation (its catch, its finally, the statements before and after it). Its promise goes
 *   nowhere: it is inline in a JSX attribute, or a const (`useCallback` included) or a function declaration, not
 *   exported, whose every use is a JSX attribute or a call whose result is discarded (`void handle()`, or `handle()` as
 *   a statement).
 * - A mutation: the whole body of `mutationFn` in an inline `useMutation({…})` options object, with no `throwOnError`
 *   and no spread, whose other options navigate nowhere: `onMutate` runs before the logout, `onError`, `onSettled`,
 *   `retry` and `retryDelay` on its failure, and `onSuccess` outside the turn of the ownership check, so a login
 *   accepted meanwhile would be sent away. Its result is a const read only as `.mutate()` with no options, or for its
 *   state: `mutateAsync`, `mutate(v, options)`, a destructured result or the result passed on is refused.
 * What runs whatever the outcome navigates nowhere either, read outward from where the logout starts: the function a
 * `.mutate()` (or a refused `mutateAsync()`) sits in, before the call and after it; each function that calls the
 * handler, or that function, with its result discarded, through every caller, each held as the handler is; and the
 * element whose event runs one of them, by its default action (an `href`, an `action` or a `formAction` on it or on a
 * JSX element around it the event bubbles to, a submit control in a form) or by another attribute of any of them (a
 * second handler of the element, an ancestor's handler).
 * Navigation is a call of push, replace, back, forward, go, refresh, assign, reload, redirect, permanentRedirect,
 * submit or requestSubmit (on any object, so an array's push in such a handler is refused too; a string's replace, with
 * its replacement, is not), `open` with a target that is this tab or one the gate cannot read (`window.open(url,
 * '_self')`), and an assignment to `location`, `.location`, `.href`, `.pathname`, `.search`, `.host`, `.hostname`,
 * `.port` or `.protocol` (a fragment's, `.hash`, loads no page). Each is read where it is written and through the
 * same-file code a name there holds: a function (declared, a const's arrow or function, useCallback's), an object
 * literal of them, and what a destructuring takes them from (a same-file hook's call).
 *
 * Out of reach, planted below as gaps: navigation through a function imported from another module, a helper handed in
 * as a parameter or a prop, or state an effect acts on; a dynamic import whose specifier is computed; a component
 * handed a handler as a prop, which may chain its promise or navigate after calling it; an element another component
 * renders inside a link or a form; and a props spread on the element or one around it, which may carry an `href` or a
 * handler.
 */

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const NAME = 'logoutAndResetAccount'
const DEFINITION = 'features/auth/lib/accountQueryState.ts'
/** Its module under any specifier that names it: `@/features/auth/lib/accountQueryState`, `./accountQueryState.ts`. */
const MODULE = /(?:^|\/)accountQueryState(?:\.[cm]?[jt]sx?)?$/
/** Every JS and TS extension. */
const SOURCE = /\.(?:[cm]?[jt]s|[jt]sx)$/

/** Each call of the helper, by file: the control it settles. */
const INVENTORY = LOGOUT_CALL_SITES

type Problem =
  | 'renamed import' | 'namespace' | 're-export' | 'dynamic import' | 'require' | 'reference' | 'string' | 'declaration'
  | 'continuation' | 'no catch' | 'navigates on failure' | 'escapes'

/** The files the gate reads, from a `git ls-files` listing of frontend/. */
export const scannedFiles = (listed: string[]): string[] => listed.filter((file) => SOURCE.test(file) && !file.startsWith('tests/'))

const scriptKind = (file: string): ts.ScriptKind =>
  file.endsWith('.tsx') ? ts.ScriptKind.TSX : file.endsWith('.jsx') ? ts.ScriptKind.JSX : /\.[cm]?js$/.test(file) ? ts.ScriptKind.JS : ts.ScriptKind.TS

const NAVIGATORS = new Set([
  'push', 'replace', 'back', 'forward', 'go', 'refresh', 'assign', 'reload', 'redirect', 'permanentRedirect', 'submit', 'requestSubmit',
])
/** A location's parts whose assignment loads a page: the location itself and every part of its URL but the fragment. */
const LOCATION_PARTS = new Set(['location', 'href', 'pathname', 'search', 'host', 'hostname', 'port', 'protocol'])
/** `window.open` targets that load the page in this tab. */
const THIS_TAB = new Set(['_self', '_top', '_parent'])
/** Attributes holding a URL the browser goes to when the element's default action runs. */
const URL_ATTRIBUTES = new Set(['href', 'action', 'formAction'])

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
    if (name === 'open') {
      // A new tab leaves this one where it is; a target naming this tab, or one the gate cannot read, may not.
      const target = node.arguments[1] && unwrap(node.arguments[1])
      return target !== undefined && (!ts.isStringLiteralLike(target) || THIS_TAB.has(target.text))
    }
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

  /**
   * What a binding holds that a read of its name can run, in this file: a function (a declaration, a const's arrow or
   * function, useCallback's), an object literal (its methods), or, for a name a destructuring takes, what it takes it from
   * (`const { leave } = useLeave()`: the call, whose same-file hook is followed in turn).
   */
  const functionOf = (binding: Binding | undefined): ts.Node | undefined => {
    if (!binding) return undefined
    if (ts.isFunctionDeclaration(binding.decl)) return binding.decl
    if (ts.isBindingElement(binding.decl)) {
      let root: ts.Node = binding.decl
      while (ts.isBindingElement(root) || ts.isObjectBindingPattern(root) || ts.isArrayBindingPattern(root)) root = root.parent
      return ts.isVariableDeclaration(root) ? root.initializer : undefined
    }
    const init = binding.init && unwrap(binding.init)
    if (!init) return undefined
    if (isFunction(init) || ts.isObjectLiteralExpression(init)) return init
    if (ts.isCallExpression(init) && calleeName(init) === 'useCallback' && init.arguments[0] && isFunction(unwrap(init.arguments[0]))) return init.arguments[0]
    return undefined
  }
  /** Whether anything under `root` navigates, outside `skip`, the same-file code it names included; `seen` is read already. */
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

  /** The JSX attribute a node is the value of (`onClick={handleLogout}`, `onClick={() => …}`). */
  const attributeOf = (node: ts.Node): ts.JsxAttribute | undefined => {
    const at = outermost(node)
    return ts.isJsxExpression(at.parent) && ts.isJsxAttribute(at.parent.parent) ? at.parent.parent : undefined
  }
  const isExported = (decl: ts.Declaration) => (ts.getCombinedModifierFlags(decl) & ts.ModifierFlags.Export) !== 0
  /**
   * Where a function is used: itself, when it is inline in a JSX attribute, else the references to the const
   * (`useCallback` included) or the function declaration holding it; undefined when it is held any other way (an
   * argument, a property, an export), so its calls are out of the gate's sight.
   */
  const usesOf = (fn: ts.SignatureDeclaration): ts.Node[] | undefined => {
    if (attributeOf(fn)) return [fn]
    if (ts.isFunctionDeclaration(fn) && fn.name) return isExported(fn) ? undefined : [...references(fn)]
    const at = outermost(fn)
    let holder = at.parent
    if (ts.isCallExpression(holder) && calleeName(holder) === 'useCallback' && holder.arguments[0] === at) holder = outermost(holder).parent
    if (ts.isVariableDeclaration(holder) && ts.isIdentifier(holder.name) && isConst(holder) && !isExported(holder)) return [...references(holder)]
    return undefined
  }
  /** The call a use is the callee of, when its result is discarded: a statement's, or void's. */
  const discardedCall = (use: ts.Node): ts.CallExpression | undefined => {
    const at = outermost(use)
    const call = at.parent
    if (!ts.isCallExpression(call) || call.expression !== at) return undefined
    const result = outermost(call).parent
    return ts.isExpressionStatement(result) || ts.isVoidExpression(result) ? call : undefined
  }
  /** Whether a control submits its form when clicked: a button whose type is not `button` or `reset`, an input of type
      `submit` or `image`, a component given `type="submit"`, and a button or an input whose type the gate cannot read. */
  const submits = (element: ts.JsxOpeningElement | ts.JsxSelfClosingElement): boolean => {
    const tag = element.tagName.getText(sf)
    const type = element.attributes.properties.find((p): p is ts.JsxAttribute => ts.isJsxAttribute(p) && p.name.getText(sf) === 'type')
    const init = type?.initializer
    const value = init && (ts.isStringLiteral(init) ? init : ts.isJsxExpression(init) && init.expression ? unwrap(init.expression) : undefined)
    const text = value && ts.isStringLiteralLike(value) ? value.text : undefined
    if (tag === 'button') return !type || text === undefined || !['button', 'reset'].includes(text)
    if (tag === 'input') return !!type && (text === undefined || ['submit', 'image'].includes(text))
    return text === 'submit'
  }
  /**
   * Whether the event an attribute handles navigates whatever the handler does: by a default action (a URL on the
   * element, or on a JSX element around it the event bubbles to; a submit control in a form) or by another attribute of
   * any of them that navigates (a second handler of the element, an ancestor's handler). The attribute the walk climbs
   * through is the handler's own, and is not read again.
   */
  const elementNavigates = (attribute: ts.JsxAttribute, skip: ts.Node | undefined, seen: Set<ts.Node>): boolean => {
    const own = attribute.parent.parent
    let through: ts.Node = attribute
    let inForm = false
    const read = new Set<ts.Node>()
    for (let at: ts.Node | undefined = attribute.parent; at; at = at.parent) {
      if (ts.isJsxAttribute(at)) through = at
      const element = ts.isJsxOpeningElement(at) || ts.isJsxSelfClosingElement(at) ? at : ts.isJsxElement(at) ? at.openingElement : undefined
      if (!element || read.has(element)) continue
      read.add(element)
      if (element.tagName.getText(sf) === 'form') inForm = true
      for (const property of element.attributes.properties) {
        if (property === through || !ts.isJsxAttribute(property)) continue
        const name = property.name.getText(sf)
        if (name === 'form' && element === own) inForm = true
        if (URL_ATTRIBUTES.has(name)) return true
        const value = property.initializer && ts.isJsxExpression(property.initializer) ? property.initializer.expression : undefined
        if (value && navigates(value, skip, seen)) return true
      }
    }
    return inForm && submits(own)
  }
  /**
   * What runs whatever the logout's outcome, read outward from `fn`, the function it starts in: `fn` outside `skip` (the
   * continuation), each function that calls it with the result discarded, through every caller, and the element whose
   * event runs one of them. None navigates, and what `fn` returns goes nowhere. `site` is where a finding is reported;
   * `chain` holds the functions read so far, and `seen` the code navigates() has read, so nothing is reported twice.
   */
  const readRunsAnyway = (fn: ts.SignatureDeclaration, site: ts.Node, skip: ts.Node | undefined, chain = new Set<ts.Node>(), seen = new Set<ts.Node>()): void => {
    if (chain.has(fn)) return
    chain.add(fn)
    if (navigates(fn, skip, seen)) flag(site, 'navigates on failure')
    const uses = usesOf(fn)
    if (!uses) {
      flag(fn, 'escapes')
      return
    }
    for (const use of uses) {
      const attribute = attributeOf(use)
      if (attribute) {
        if (elementNavigates(attribute, skip, seen)) flag(use, 'navigates on failure')
        continue
      }
      const call = discardedCall(use)
      const caller = call && innermostFunction(call)
      if (caller) readRunsAnyway(caller, use, skip, chain, seen)
      else flag(use, 'escapes')
    }
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
      if (key === 'mutationFn') continue
      // Every other option runs outside the continuation: onMutate before the logout, onError, onSettled, retry and
      // retryDelay on its failure, onSuccess outside the ownership check's turn.
      const value = ts.isPropertyAssignment(property) ? property.initializer : ts.isShorthandPropertyAssignment(property) ? property.name : property
      if (navigates(value)) flag(property, 'navigates on failure')
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
      const trigger = access.name.text
      if (trigger === 'mutateAsync') flag(use, 'escapes')
      if (trigger !== 'mutate' && trigger !== 'mutateAsync') continue
      const call = outermost(access).parent
      if (!ts.isCallExpression(call) || call.expression !== outermost(access)) {
        if (trigger === 'mutate') flag(use, 'escapes')
        continue
      }
      if (trigger === 'mutate' && call.arguments.length > 1) flag(use, 'escapes')
      // What runs beside the trigger, before it or after it, runs whatever the logout's outcome.
      const fn = innermostFunction(call)
      if (fn) readRunsAnyway(fn, use, undefined)
      else flag(use, 'escapes')
    }
  }

  const readCall = (call: ts.CallExpression) => {
    calls.push(line(call))
    const continuation = call.arguments[2]
    if (continuation && !returnsAtOnceOnFailure(continuation)) flag(call, 'continuation')
    const handler = innermostFunction(call)
    const mutation = mutationOf(call, handler)
    if (mutation) readMutation(mutation)
    else if (handler && awaitedInTry(call, handler)) readRunsAnyway(handler, call, continuation)
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
/** Every kind of navigation the header names. */
const NAVIGATIONS = [
  "router.push('/')", "router.replace('/')", 'router.back()', 'router.forward()', 'router.refresh()', "redirect('/')",
  "permanentRedirect('/')", 'history.go(-1)', "window.location.href = '/'", "location.href = '/'", "window.location = '/'",
  "location.assign('/')", "window.location.replace('/')", 'location.reload()', "window.location.pathname = '/'",
  "location.search = '?out=1'", "location.host = 'example.com'", "window.location.hostname = 'example.com'",
  "location.port = '8080'", "location.protocol = 'http:'", "location = '/'", "window.open('/', '_self')",
  'formRef.current?.submit()', 'formRef.current?.requestSubmit()',
]
/** The places outside the continuation, each with a statement planted in it, and what the gate must say of a navigation
    there: the mutation's other options, the function its trigger sits in, the handler's catch, and its callers. */
const OUTSIDE: { place: string; plant: (statement: string) => string; problems: Problem[] }[] = [
  { place: "the mutation's onMutate", plant: (s) => mutation({ options: `onMutate: () => { ${s} },` }), problems: ['navigates on failure'] },
  { place: "the mutation's onError", plant: (s) => mutation({ options: `onError: () => { ${s} },` }), problems: ['navigates on failure'] },
  { place: "the mutation's onSettled", plant: (s) => mutation({ options: `onSettled: () => { ${s} },` }), problems: ['navigates on failure'] },
  { place: "the mutation's retry", plant: (s) => mutation({ options: `retry: () => { ${s}; return false },` }), problems: ['navigates on failure'] },
  { place: "the mutation's retryDelay", plant: (s) => mutation({ options: `retryDelay: () => { ${s}; return 0 },` }), problems: ['navigates on failure'] },
  { place: "the mutation's onSuccess", plant: (s) => mutation({ options: `onSuccess: () => { ${s} },` }), problems: ['navigates on failure'] },
  { place: 'the function its trigger sits in, after it', plant: (s) => mutation({ use: `<button onClick={() => { logoutMutation.mutate(); ${s} }}>Log out</button>` }), problems: ['navigates on failure'] },
  { place: 'the function its trigger sits in, before it', plant: (s) => mutation({ use: `<button onClick={() => { ${s}; logoutMutation.mutate() }}>Log out</button>` }), problems: ['navigates on failure'] },
  { place: 'the function mutateAsync sits in, after it', plant: (s) => mutation({ use: `<button onClick={() => { void logoutMutation.mutateAsync(); ${s} }}>Log out</button>` }), problems: ['escapes', 'navigates on failure'] },
  { place: "the handler's catch", plant: (s) => handler({ caught: s }), problems: ['navigates on failure'] },
  { place: 'a caller, after the handler call it discards', plant: (s) => handler({ use: `<button onClick={(e) => { void handleLogout(e); ${s} }}>Log out</button>` }), problems: ['navigates on failure'] },
  { place: 'a caller, after the handler call it does not await', plant: (s) => handler({ use: `<button onClick={() => { handleLogout(); ${s} }}>Log out</button>` }), problems: ['navigates on failure'] },
]
/** A source with a same-file helper, `leave()`, that runs `navigation`. */
const withHelper = (source: string, navigation: string) => source.replace(/export function (Menu|Page)/, (start) => `function leave() { ${navigation} }\n${start}`)

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
  { form: 'a mutation awaited through mutateAsync, its rejection navigating', source: mutation({ use: "<button onClick={() => logoutMutation.mutateAsync().catch(() => router.push('/'))}>Log out</button>" }), problems: ['escapes', 'navigates on failure'] },
  { form: 'a mutation handed options at mutate, one navigating', source: mutation({ use: "<button onClick={() => logoutMutation.mutate(undefined, { onError: () => router.push('/') })}>Log out</button>" }), problems: ['escapes', 'navigates on failure'] },
  { form: 'a mutation whose result is destructured', source: mutation({ holder: 'const { mutate }', use: '<button onClick={() => mutate()}>Log out</button>' }), problems: ['escapes'] },
  { form: 'an exported handler, which another module may chain', source: `${IMPORT}export async function handleLogout(qc, logout) {
  try { await logoutAndResetAccount(qc, logout) } catch {}
}
`, problems: ['escapes'] },

  // Every navigation the header names, in every place that runs whatever the outcome, written there or in a same-file
  // helper called there.
  ...OUTSIDE.flatMap(({ place, plant, problems }) => NAVIGATIONS.flatMap((navigation) => [
    { form: `${navigation} in ${place}`, source: plant(navigation), problems },
    { form: `${navigation} in a same-file helper called in ${place}`, source: withHelper(plant('leave()'), navigation), problems },
  ])),

  // The same reach through the code around: a caller, a timer, a hook's helper, an object of helpers.
  { form: "a function that triggers the mutation, whose caller then navigates", source: mutation({ use: "<button onClick={() => { onLogout(); router.push('/') }}>Log out</button>" }).replace('\n  return ', '\n  const onLogout = () => logoutMutation.mutate()\n  return '), problems: ['navigates on failure'] },
  { form: "the caller of the handler's caller navigates", source: handler({ use: '<button onClick={leaveAfter}>Log out</button>' }).replace('\n  return ', "\n  const logOut = () => { void handleLogout() }\n  const leaveAfter = () => { logOut(); router.push('/') }\n  return "), problems: ['navigates on failure'] },
  { form: 'a timer set beside the trigger navigates', source: mutation({ use: "<button onClick={() => { logoutMutation.mutate(); setTimeout(() => router.push('/'), 0) }}>Log out</button>" }), problems: ['navigates on failure'] },
  { form: 'a helper destructured from a same-file hook', source: handler({ caught: 'leave()' }).replace('export function Menu', "function useLeave(router) { return { leave: () => router.push('/') } }\nexport function Menu").replace('  const handleLogout', '  const { leave } = useLeave(router)\n  const handleLogout'), problems: ['navigates on failure'] },
  { form: 'a helper held in an object', source: handler({ caught: 'routes.home()' }).replace('export function Menu', "const routes = { home: () => window.location.assign('/') }\nexport function Menu"), problems: ['navigates on failure'] },

  // The element whose event starts the logout: its default action and what else the event runs.
  { form: 'a Link whose click logs out', source: handler({ use: '<Link href="/" onClick={handleLogout}>Log out</Link>' }), problems: ['navigates on failure'] },
  { form: "the mutation's trigger on a Link", source: mutation({ use: '<Link href="/login" onClick={() => logoutMutation.mutate()}>Log out</Link>' }), problems: ['navigates on failure'] },
  { form: 'an anchor around the Log out button', source: handler({ use: '<a href="/"><button type="button" onClick={handleLogout}>Log out</button></a>' }), problems: ['navigates on failure'] },
  { form: 'a second handler of the same element that navigates', source: handler({ use: "<button onClick={handleLogout} onPointerUp={() => router.push('/')}>Log out</button>" }), problems: ['navigates on failure'] },
  { form: "an ancestor's click handler that navigates", source: handler({ use: "<div onClick={() => router.push('/')}><button type=\"button\" onClick={handleLogout}>Log out</button></div>" }), problems: ['navigates on failure'] },
  { form: 'a submit button in a form', source: handler({ use: '<form><button onClick={handleLogout}>Log out</button></form>' }), problems: ['navigates on failure'] },
  { form: 'a submit input tied to a form by its form attribute', source: handler({ use: '<input type="submit" form="settings" onClick={handleLogout} value="Log out" />' }), problems: ['navigates on failure'] },
  { form: 'a form whose action is a URL', source: handler({ use: '<form action="/goodbye"><button type="button" onClick={handleLogout}>Log out</button></form>' }), problems: ['navigates on failure'] },
  { form: 'a button whose formAction is a URL', source: handler({ use: '<button type="submit" formAction="/goodbye" onClick={handleLogout}>Log out</button>' }), problems: ['navigates on failure'] },

  // Look-alikes beside those that must pass.
  { form: "a mutation whose onMutate only says it is logging out", source: mutation({ options: "onMutate: () => toast.loading('Logging out…')," }), problems: [] },
  { form: "a handler's caller that does more, none of it navigating", source: handler({ use: '<button onClick={(e) => { void handleLogout(e); setOpen(false) }}>Log out</button>' }), problems: [] },
  { form: 'a Link beside the Log out button', source: handler({ use: '<nav><Link href="/">Home</Link><button type="button" onClick={handleLogout}>Log out</button></nav>' }), problems: [] },
  { form: "a sibling's handler that navigates", source: mutation({ use: "<div><button onClick={() => router.push('/settings')}>Settings</button><button onClick={() => logoutMutation.mutate()}>Log out</button></div>" }), problems: [] },
  { form: 'a button in a form that does not submit it', source: handler({ use: '<form><button type="button" onClick={handleLogout}>Log out</button></form>' }), problems: [] },
  { form: "the dashboard's shape: the trigger in a header's actions, beside its back link", source: mutation({ use: '<SecondaryHeader backHref="/" title="Dashboard" actions={<button type="button" onClick={() => logoutMutation.mutate()}>Log out</button>} />' }), problems: [] },
  { form: 'a fragment set in the catch, which loads no page', source: handler({ caught: "window.location.hash = '#account'" }), problems: [] },
  { form: 'a new tab opened in the catch', source: handler({ caught: "window.open('/help', '_blank')" }), problems: [] },

  // Out of reach (the header names each): the gate passes them.
  { form: 'navigation through an imported helper', source: handler({ caught: 'goHome(router)' }), problems: [], gap: true },
  { form: 'navigation through a helper handed in as a prop', source: handler({ caught: 'leave()' }).replace('{ router, queryClient, logout, opener }', '{ router, queryClient, logout, opener, leave }'), problems: [], gap: true },
  { form: 'navigation through state an effect acts on', source: handler({ caught: 'setLeaving(true)' }), problems: [], gap: true },
  { form: 'a dynamic import with a computed specifier', source: 'export const go = async (spec, name, qc, logout) => (await import(spec))[name](qc, logout)\n', problems: [], gap: true },
  { form: "a component that chains its handler prop's promise", source: handler({ use: '<Confirm onConfirm={handleLogout} />' }), problems: [], gap: true },
  { form: 'a component that navigates after calling its handler prop', source: handler({ use: '<Confirm onConfirm={handleLogout} router={router} />' }).replace('export function Menu', "function Confirm({ onConfirm, router }) { return <button onClick={() => { onConfirm(); router.push('/') }}>Log out</button> }\nexport function Menu"), problems: [], gap: true },
  { form: 'an element another component renders inside a link', source: `${handler()}export const InLink = (props) => <Link href="/"><Menu {...props} /></Link>\n`, problems: [], gap: true },
  { form: 'an element another component renders inside a form', source: handler({ use: '<button onClick={handleLogout}>Log out</button>' }).concat('export const InForm = (props) => <form><Menu {...props} /></form>\n'), problems: [], gap: true },
  { form: 'a props spread that carries an href', source: handler({ use: '<Link {...home} onClick={handleLogout}>Log out</Link>' }).replace('export function Menu', "const home = { href: '/' }\nexport function Menu"), problems: [], gap: true },
  { form: 'a props spread that carries a handler that navigates', source: handler({ use: '<button {...more} onClick={handleLogout}>Log out</button>' }).replace('export function Menu', "const more = { onPointerUp: () => window.location.assign('/') }\nexport function Menu"), problems: [], gap: true },
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
    // A new control that logs out joins INVENTORY (tests/unit/logoutCallSites.ts), and failedLogoutChecksSession.spec.tsx
    // then fails until a control of its cases sits in the new file.
    expect(calls).toEqual(Object.fromEntries(Object.keys(INVENTORY).map((file) => [file, 1])))
  })
})
