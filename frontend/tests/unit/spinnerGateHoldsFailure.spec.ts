import { readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { bindingResolver, type Binding } from './astBindings'

/**
 * Rule-12 gate for lessons/frontend-spinner-gate-on-shared-errored-query.md: a page's loading gate over a query
 * that other components observe must hold the failure it has shown (`useRetainedFailure(query).failed`).
 * Otherwise a child observer that mounts over the failed, data-less query refetches it (retryOnMount), the
 * refetch turns `isLoading` back on, the gate swaps the page (and that child) for its spinner, the refetch
 * fails, the child mounts again: the settings page's unbounded `/me` loop.
 *
 * What it reads, in every .tsx under app/ (the pages and layouts):
 *  - shared queries: a `useQuery` / `useSuspenseQuery` / `useInfiniteQuery` call whose key family (the
 *    `queryKey` with its call arguments dropped: `queryKeys.usage.byUser`) is observed in at least two modules
 *    under app/, components/, features/, hooks/ and lib/. That over-approximates "a child observes it": the
 *    scan cannot follow JSX into what a page renders, so a family two pages share counts too.
 *  - loading gates: `if (cond) return <JSX>` (or `return null`; either branch, a block's direct `return`
 *    included) and `cond ? <JSX> : …`, whose condition reads `isLoading`, `isPending` or `isInitialLoading` of
 *    a shared query: as a member (`userQuery.isLoading`), destructured from it (renamed or not), through
 *    same-file consts (followed transitively), or through a same-file hook's returned object
 *    (`const { isReady } = useAuthGate()`, `return { isReady: !isLoading }`).
 *  - the hold: a loading read is held when an enclosing `&&` (in the condition, or in a const it came through)
 *    also reads `!failure.failed`, where `failure` is `useRetainedFailure(<that same query>)`.
 * Every unheld read fails, unless its site is pinned in ALLOW by the condition's exact text, with a reason.
 *
 * Limits, so a reviewer still reads new gates: a key family built outside a `queryKey:` property (an options
 * helper), a loading state read as `status === 'pending'` or passed in through props, a hold read through an
 * alias (`const failed = failure.failed`), a gate inside a component under features/ or components/, and
 * `cond && <JSX>`, which adds content beside the page rather than replacing it (so `!isLoading && <Panel />`,
 * which unmounts the panel, is not seen).
 */
const ROOTS = ['app', 'components', 'features', 'hooks', 'lib']
const GATE_ROOT = 'app'
const QUERY_HOOK = /^(useQuery|useSuspenseQuery|useInfiniteQuery)$/
const LOADING = /^(isLoading|isPending|isInitialLoading)$/
/** Calls whose arguments are not part of a condition's value: the scan never follows a binding into them. */
const OPAQUE_CALL = /^(useQuery|useSuspenseQuery|useInfiniteQuery|useMutation|useRetainedFailure)$/

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')

function walk(dir: string, out: string[]): string[] {
  for (const name of readdirSync(dir)) {
    const p = path.join(dir, name)
    if (statSync(p).isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(p) && !p.endsWith('.d.ts')) out.push(p)
  }
  return out
}

const parse = (source: string, fileName: string) =>
  ts.createSourceFile(
    fileName, source, ts.ScriptTarget.Latest, true, fileName.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  )

const unwrap = (e: ts.Expression): ts.Expression => {
  while (ts.isParenthesizedExpression(e) || ts.isAsExpression(e) || ts.isNonNullExpression(e)) e = e.expression
  return e
}

/** `queryKeys.usage.byUser(id)` → `queryKeys.usage.byUser`; `['feed', id]` → `'feed'`. */
function keyFamily(key: ts.Expression): string {
  let e = unwrap(key)
  while (ts.isCallExpression(e)) e = unwrap(e.expression)
  if (ts.isArrayLiteralExpression(e)) return e.elements[0]?.getText() ?? '[]'
  return e.getText()
}

/** The key family of a query hook call (`useQuery({ queryKey, … })`), or null for any other node. */
function queryFamily(node: ts.Node): string | null {
  if (!ts.isCallExpression(node) || !ts.isIdentifier(node.expression) || !QUERY_HOOK.test(node.expression.text)) {
    return null
  }
  const options = node.arguments[0]
  if (!options || !ts.isObjectLiteralExpression(options)) return null
  for (const p of options.properties) {
    if (ts.isPropertyAssignment(p) && p.name.getText() === 'queryKey') return keyFamily(p.initializer)
  }
  return null
}

/** Every key family a module observes. */
function observedFamilies(source: string, fileName: string): Set<string> {
  const families = new Set<string>()
  const visit = (node: ts.Node): void => {
    const family = queryFamily(node)
    if (family !== null) families.add(family)
    ts.forEachChild(node, visit)
  }
  visit(parse(source, fileName))
  return families
}

interface Gate {
  line: number
  /** The gate's condition, whitespace collapsed: what ALLOW pins. */
  expr: string
  /** The shared key families it reads loading from without the hold. */
  families: string[]
}

const isRender = (e: ts.Expression | undefined): boolean => {
  if (!e) return false
  const inner = unwrap(e)
  return ts.isJsxElement(inner) || ts.isJsxSelfClosingElement(inner) || ts.isJsxFragment(inner) ||
    inner.kind === ts.SyntaxKind.NullKeyword
}
/** A branch that renders something else instead: `return <JSX>`, or a block with one among its statements. */
const returnsRender = (branch: ts.Statement | undefined): boolean => {
  if (!branch) return false
  if (ts.isReturnStatement(branch)) return isRender(branch.expression)
  return ts.isBlock(branch) && branch.statements.some((s) => ts.isReturnStatement(s) && isRender(s.expression))
}

/** Loading gates in one module that read a shared query's loading flag without holding its shown failure. */
function unheldGates(source: string, fileName: string, shared: Set<string>): Gate[] {
  const sf = parse(source, fileName)
  const visible = bindingResolver(sf)

  // Same-file functions by name, for a hook whose returned object a gate destructures.
  const functions = new Map<string, ts.FunctionLikeDeclaration>()
  for (const statement of sf.statements) {
    if (ts.isFunctionDeclaration(statement) && statement.name) functions.set(statement.name.text, statement)
    if (ts.isVariableStatement(statement)) {
      for (const d of statement.declarationList.declarations) {
        if (ts.isIdentifier(d.name) && d.initializer && (ts.isArrowFunction(d.initializer) || ts.isFunctionExpression(d.initializer))) {
          functions.set(d.name.text, d.initializer)
        }
      }
    }
  }

  /** The shared query call an expression holds: the call itself, or a const bound to one. */
  const queryOf = (e: ts.Expression | undefined, seen = new Set<Binding>()): ts.CallExpression | null => {
    if (!e) return null
    const inner = unwrap(e)
    if (ts.isCallExpression(inner)) {
      const family = queryFamily(inner)
      return family !== null && shared.has(family) ? inner : null
    }
    if (!ts.isIdentifier(inner)) return null
    const b = visible(inner)
    if (!b?.init || seen.has(b)) return null
    return queryOf(b.init, new Set([...seen, b]))
  }

  /** The query a `useRetainedFailure(<query>)` holds, for that call or a const bound to it. */
  const heldQueryOf = (e: ts.Expression, seen = new Set<Binding>()): ts.CallExpression | null => {
    const inner = unwrap(e)
    if (ts.isCallExpression(inner)) {
      const callee = inner.expression
      const isHold = ts.isIdentifier(callee) && callee.text === 'useRetainedFailure'
      return isHold && inner.arguments[0] ? queryOf(inner.arguments[0]) : null
    }
    if (!ts.isIdentifier(inner)) return null
    const b = visible(inner)
    if (!b?.init || seen.has(b)) return null
    return heldQueryOf(b.init, new Set([...seen, b]))
  }

  /** Queries whose shown failure `e` reads negated: `!failure.failed`. */
  const holdsIn = (e: ts.Node): Set<ts.CallExpression> => {
    const out = new Set<ts.CallExpression>()
    const visit = (n: ts.Node): void => {
      if (ts.isPrefixUnaryExpression(n) && n.operator === ts.SyntaxKind.ExclamationToken) {
        const operand = unwrap(n.operand)
        if (ts.isPropertyAccessExpression(operand) && operand.name.text === 'failed') {
          const q = heldQueryOf(operand.expression)
          if (q) out.add(q)
        }
      }
      ts.forEachChild(n, visit)
    }
    visit(e)
    return out
  }

  /** For `{ isLoading: x } = <shared query>`: that query; null for any other binding. */
  const destructuredLoading = (b: Binding): ts.CallExpression | null => {
    const d = b.decl
    if (!ts.isBindingElement(d) || !LOADING.test((d.propertyName ?? d.name).getText())) return null
    const declaration = d.parent.parent
    return ts.isVariableDeclaration(declaration) ? queryOf(declaration.initializer) : null
  }

  /** For `{ isReady } = useAuthGate()` with a same-file hook: what its returned object holds under that name. */
  const hookReturn = (b: Binding): ts.Expression | null => {
    const d = b.decl
    if (!ts.isBindingElement(d)) return null
    const declaration = d.parent.parent
    if (!ts.isVariableDeclaration(declaration) || !declaration.initializer) return null
    const call = unwrap(declaration.initializer)
    if (!ts.isCallExpression(call) || !ts.isIdentifier(call.expression)) return null
    const hook = functions.get(call.expression.text)
    const key = (d.propertyName ?? d.name).getText()
    let found: ts.Expression | null = null
    const visit = (n: ts.Node): void => {
      if (found) return
      if (n !== hook && ts.isFunctionLike(n)) return // a nested function's return is not the hook's
      if (ts.isReturnStatement(n) && n.expression && ts.isObjectLiteralExpression(unwrap(n.expression))) {
        for (const p of (unwrap(n.expression) as ts.ObjectLiteralExpression).properties) {
          if (ts.isPropertyAssignment(p) && p.name.getText() === key) found = p.initializer
          else if (ts.isShorthandPropertyAssignment(p) && p.name.text === key) found = p.name
        }
      }
      ts.forEachChild(n, visit)
    }
    if (hook?.body) visit(hook)
    return found
  }

  /** The shared queries whose loading flag `e` reads without a hold over it. */
  const unheld = (e: ts.Node, held: Set<ts.CallExpression>, path: Set<Binding>): ts.CallExpression[] => {
    const out: ts.CallExpression[] = []
    const visit = (n: ts.Node, held: Set<ts.CallExpression>): void => {
      if (ts.isBinaryExpression(n) && n.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken) {
        visit(n.left, new Set([...held, ...holdsIn(n.right)]))
        visit(n.right, new Set([...held, ...holdsIn(n.left)]))
        return
      }
      if (ts.isCallExpression(n) && ts.isIdentifier(n.expression) && OPAQUE_CALL.test(n.expression.text)) return
      if (ts.isPropertyAccessExpression(n) && LOADING.test(n.name.text)) {
        const q = queryOf(n.expression)
        if (q) {
          if (!held.has(q)) out.push(q)
          return
        }
      }
      if (ts.isIdentifier(n)) {
        if (ts.isPropertyAccessExpression(n.parent) && n.parent.name === n) return
        const b = visible(n)
        if (!b || path.has(b)) return
        const q = destructuredLoading(b)
        if (q) {
          if (!held.has(q)) out.push(q)
          return
        }
        const via = b.init ?? hookReturn(b)
        if (via) out.push(...unheld(via, held, new Set([...path, b])))
        return
      }
      if (ts.isStringLiteralLike(n)) return
      ts.forEachChild(n, (child) => visit(child, held))
    }
    visit(e, held)
    return out
  }

  const gates: Gate[] = []
  const check = (node: ts.Node, condition: ts.Expression): void => {
    const queries = unheld(condition, new Set(), new Set())
    if (!queries.length) return
    const { line } = sf.getLineAndCharacterOfPosition(node.getStart(sf))
    gates.push({
      line: line + 1,
      expr: condition.getText(sf).replace(/\s+/g, ' '),
      families: [...new Set(queries.map((q) => queryFamily(q) as string))].sort(),
    })
  }
  const visit = (node: ts.Node): void => {
    if (ts.isIfStatement(node) && (returnsRender(node.thenStatement) || returnsRender(node.elseStatement))) {
      check(node, node.expression)
    }
    if (ts.isConditionalExpression(node) && (isRender(node.whenTrue) || isRender(node.whenFalse))) {
      check(node, node.condition)
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return gates
}

/**
 * Gates that read a shared query's loading flag without the hold, kept because no observer of that query can
 * mount over its failure: pinned by the condition's exact text, with a reason. Shrink-only and capped.
 */
const ALLOW: Record<string, { sites: string[]; reason: string }> = {
  'app/admin/layout.tsx': {
    sites: ['isLoading'],
    reason:
      'A failed /me renders null (`!user`) and redirects: the admin pages, and any observer in them, mount only ' +
      'with a user, so no child refetches the failure and the skeleton cannot loop.',
  },
  'app/dashboard/watchlist/page.tsx': {
    sites: ['!isReady || isLoading'],
    reason:
      'A failed /me renders null (`!hasUser`), so nothing below mounts over it. Its watchlist-insights query is ' +
      'shared only with the dashboard page, another route: nothing this page renders observes it.',
  },
  'app/delete-account/page.tsx': {
    sites: ['isLoading'],
    reason:
      'A failed /me shows the sign-in card, which observes no query; the delete form mounts only with a user.',
  },
  'app/filing/[id]/page-client.tsx': {
    sites: [
      'isAuthResolved && !isAuthenticated && filing && !summaryLoading',
      '!activeErrorMessage && (summaryLoading || !isAuthResolved)',
    ],
    reason:
      "The summary pane's chain: the signup gate (GenerateSignupGate), the spinner and StreamingSummaryDisplay " +
      'swap only each other, and none observes a shared query. The copilot rail (AskCopilotRail), which observes ' +
      "/me, is FilingWorkspace's copilotBody, outside the swap.",
  },
}
const MAX_ALLOWLIST_SIZE = 4
const MAX_PINNED_SITES = 5

// Shared families: observed by at least two modules.
const observers = new Map<string, Set<string>>()
const gateFiles: Array<{ rel: string; source: string }> = []
for (const abs of ROOTS.flatMap((root) => walk(path.join(frontendRoot, root), []))) {
  const rel = path.relative(frontendRoot, abs).split(path.sep).join('/')
  const source = readFileSync(abs, 'utf8')
  for (const family of observedFamilies(source, rel)) observers.set(family, new Set([...(observers.get(family) ?? []), rel]))
  if (rel.startsWith(`${GATE_ROOT}/`) && rel.endsWith('.tsx')) gateFiles.push({ rel, source })
}
const shared = new Set([...observers].filter(([, files]) => files.size >= 2).map(([family]) => family))
const found = new Map<string, Gate[]>()
for (const { rel, source } of gateFiles) {
  const gates = unheldGates(source, rel, shared)
  if (gates.length) found.set(rel, gates)
}

const FIXTURE_SHARED = new Set(['queryKeys.currentUser', 'queryKeys.usage.byUser'])
const seen = (fixture: string) =>
  unheldGates(fixture, 'fixture.tsx', FIXTURE_SHARED).map((gate) => `${gate.line}: ${gate.expr} [${gate.families.join(', ')}]`)

describe('a page loading gate over a shared query holds its shown failure (rule-12 gate)', () => {
  it('sees loading read directly, as a member, renamed, through consts and through a same-file hook, and nothing else', () => {
    const fixture = [
      'function useAuthGate() {',
      '  const { isLoading } = useQuery({ queryKey: queryKeys.currentUser(), queryFn })',
      '  const helper = () => ({ isReady: true })', // a nested function's return is not the hook's
      '  return { isReady: !isLoading }',
      '}',
      'export function A() {',
      '  const userQuery = useQuery({ queryKey: queryKeys.currentUser(), queryFn })',
      '  const { isPending: userPending } = userQuery',
      '  const usage = useQuery({ queryKey: queryKeys.usage.byUser(id), queryFn, enabled: !userQuery.isLoading })',
      '  const feed = useQuery({ queryKey: queryKeys.dashboardFeed(), queryFn })', // not shared
      '  const blocked = userPending || usage.isLoading',
      '  const { isReady } = useAuthGate()',
      '  if (userQuery.isLoading) return <Spinner />', // member
      '  if (userPending) { track(); return null }', // renamed, a block, `return null`
      '  if (blocked) return <Skeleton />', // two through a const
      '  if (!isReady) return <Spinner />', // through the hook
      '  if (feed.isLoading) return <Spinner />', // not shared: does not count
      '  if (userQuery.isError) return <ErrorCard />', // not a loading flag
      '  if (userQuery.isLoading) track()', // renders nothing instead
      '  useEffect(() => { if (userQuery.isLoading) return }, [])', // an effect, not a render
      "  if (userQuery.isLoading) return 'loading'", // a string, not a render
      '  return <>{usage.isLoading ? <Spinner /> : <Panel />}</>', // a conditional counts
      '}',
    ].join('\n')
    expect(seen(fixture)).toEqual([
      '13: userQuery.isLoading [queryKeys.currentUser]',
      '14: userPending [queryKeys.currentUser]',
      '15: blocked [queryKeys.currentUser, queryKeys.usage.byUser]',
      '16: !isReady [queryKeys.currentUser]',
      '22: usage.isLoading [queryKeys.usage.byUser]',
    ])
  })

  it("holds a loading read only with that same query's `!failure.failed` beside it under `&&`", () => {
    const fixture = [
      'export function B() {',
      '  const userQuery = useQuery({ queryKey: queryKeys.currentUser(), queryFn })',
      '  const usageQuery = useQuery({ queryKey: queryKeys.usage.byUser(id), queryFn })',
      '  const { isLoading: userLoading } = userQuery',
      '  const userFailure = useRetainedFailure(userQuery)',
      '  const usageFailure = useRetainedFailure(usageQuery)',
      '  const spin = userLoading && !userFailure.failed',
      '  if (userLoading && !userFailure.failed) return <Spinner />', // held
      '  if (!userFailure.failed && userQuery.isPending) return <Spinner />', // held, either side
      '  if (spin) return <Spinner />', // held inside the const
      '  if ((userLoading && !userFailure.failed) || (usageQuery.isLoading && !usageFailure.failed)) return null', // both
      '  if (userLoading && !usageFailure.failed) return <Spinner />', // another query's hold
      '  if (userLoading || !userFailure.failed) return <Spinner />', // not under &&
      '  if (userLoading && userFailure.failed) return <Spinner />', // not negated
      '  if (usageQuery.isLoading && !userFailure.failed) return <Spinner />', // usage without its hold
      '  return <Page />',
      '}',
    ].join('\n')
    expect(seen(fixture)).toEqual([
      '12: userLoading && !usageFailure.failed [queryKeys.currentUser]',
      '13: userLoading || !userFailure.failed [queryKeys.currentUser]',
      '14: userLoading && userFailure.failed [queryKeys.currentUser]',
      '15: usageQuery.isLoading && !userFailure.failed [queryKeys.usage.byUser]',
    ])
  })

  it("fails on the settings page's old `if (userLoading)` gate, and passes its held one", () => {
    const settings = readFileSync(path.join(frontendRoot, 'app/dashboard/settings/page.tsx'), 'utf8')
    const held = 'if (userLoading && !userFailure.failed) {'
    expect(settings).toContain(held)
    expect(unheldGates(settings, 'app/dashboard/settings/page.tsx', shared)).toEqual([])
    const old = unheldGates(settings.replace(held, 'if (userLoading) {'), 'app/dashboard/settings/page.tsx', shared)
    expect(old.map((gate) => `${gate.expr} [${gate.families.join(', ')}]`)).toEqual(['userLoading [queryKeys.currentUser]'])
  })

  it('finds the shared queries it is meant to guard', () => {
    // A family that loses its second observer stops being guarded: anchor the scan to the known shares.
    for (const family of ['queryKeys.currentUser', 'queryKeys.subscription.byUser', 'queryKeys.usage.byUser']) {
      expect(shared, family).toContain(family)
    }
    expect(gateFiles.length).toBeGreaterThan(20)
  })

  it('no page gates a shared query on loading without holding its shown failure, outside the allowlist', () => {
    const offenders: string[] = []
    for (const [file, gates] of found) {
      const allowed = [...(ALLOW[file]?.sites ?? [])]
      for (const gate of gates) {
        const i = allowed.indexOf(gate.expr)
        if (i === -1) offenders.push(`${file}:${gate.line}: ${gate.expr} [${gate.families.join(', ')}]`)
        else allowed.splice(i, 1)
      }
    }
    expect(
      offenders,
      'A loading gate over a query other components observe must hold the failure it shows: ' +
        '`if (isLoading && !failure.failed)` with `const failure = useRetainedFailure(query)` ' +
        '(hooks/useRetainedFailure.tsx). See lessons/frontend-spinner-gate-on-shared-errored-query.md.',
    ).toEqual([])
  })

  it('is shrink-only, and every entry has a reason', () => {
    expect(Object.keys(ALLOW).length).toBeLessThanOrEqual(MAX_ALLOWLIST_SIZE)
    const pinned = Object.values(ALLOW).reduce((sum, { sites }) => sum + sites.length, 0)
    expect(pinned).toBeLessThanOrEqual(MAX_PINNED_SITES)
    for (const [file, { reason }] of Object.entries(ALLOW)) {
      expect(reason.trim().length, `${file} needs a reason`).toBeGreaterThan(0)
    }
  })

  it.each(Object.keys(ALLOW))('%s still has every pinned gate (remove the pins of fixed ones)', (file) => {
    const actual = (found.get(file) ?? []).map((gate) => gate.expr).sort()
    expect(actual).toEqual([...ALLOW[file].sites].sort())
  })
})
