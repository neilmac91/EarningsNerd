import { readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { bindingResolver, type Binding } from './astBindings'

/**
 * Rule-12 gate for lessons/frontend-busy-controls-stay-focusable.md: a control busy with a request
 * never takes native `disabled`. Chromium blurs a focused control the moment it turns disabled, so
 * keyboard focus falls to <body> and stays there. A busy state uses the DS Button's `loading`, or
 * `aria-disabled` (+ `aria-busy`) and an early return in the handler; a text field uses `readOnly`.
 *
 * The scan reads the TypeScript AST of every .tsx under app/, components/, features/, hooks/ and lib/ (so
 * RetryButton, the one control behind every Retry, is scanned too). It counts
 * each JSX `disabled={…}` whose expression names a busy flag (BUSY below) or a post-success flag
 * (AFTER_SUCCESS: the control's own success leaves it unavailable, e.g. "Link sent"), directly, through a member
 * (`mutation.isPending`), or through the binding visible from the site: a `const` (followed
 * transitively, so `const canSend = … && !sending` counts), a renamed destructured prop
 * (`{ isPending: waiting }`), or a function declaration's body (`function reload() { … }`). Names resolve in their lexical scope, so a parameter shadows an outer
 * const and two components may each declare their own `cannotSubmit`. Any JSX element counts,
 * components included: a `disabled` prop fed by a busy flag is the same bug one component away.
 * Strings and comments never count.
 *
 * What it cannot see, so per-site specs stay the real proof of focus:
 *  - a busy or post-success flag under a name outside BUSY and AFTER_SUCCESS, such as `!dirty` after
 *    a save;
 *  - a value threaded through props under another name, or computed in another file.
 *
 * ALLOW pins every sanctioned site, per file and with a reason, by the exact text of its `disabled`
 * expression (whitespace collapsed). A new site fails, a busy flag added to a pinned expression fails
 * (its text changes), and a converted site fails until its pin is removed. Files and pinned sites are
 * both capped, shrink-only.
 *
 * A second gate in this file holds every Retry of a query to `<RetryButton>` (hooks/useRetainedFailure.tsx),
 * seen two ways: by its wiring (`loading` fed by a fetching flag, a handler that refetches, invalidates or
 * retries; the same binding resolver) and by what the user reads (a "Retrying…" loadingText, a label starting
 * Retry or Try again, a same-file string const included). Each has its own shrink-only, capped allowlist with
 * reasons: ALLOW_RETRY and ALLOW_RETRY_LABEL. RetryButton's own definition is the one exemption from both
 * Retry clauses (it is the sanctioned wiring and label); the busy-disabled clause still scans it. Every Retry
 * converted in the retry-hardening follow-up fails both at its pre-conversion version (026d6df). A third clause
 * holds what RetryButton is given: each of its `failures` is `useRetainedFailure(…)`'s, or a failure built by
 * hand that ALLOW_HAND_BUILT_FAILURE pins (a stream restart, which has no query to hold).
 */
const BUSY = /pending|loading|submitting|saving|sending|streaming|running|busy|refetching|fetching|mutating|deleting|removing|inflight/i
/** Flags a control's own success sets, which leave it unavailable while it still holds focus. */
const AFTER_SUCCESS = /resent|saved|copied|succeeded|success|cooldown/i

const ALLOW: Record<string, { sites: string[]; reason: string }> = {
  // Kept by design.
  'features/calendar/components/AlertBell.tsx': {
    sites: ['checking'],
    reason:
      '`checking` (identity not yet resolved) keeps native disabled: it holds only before identity first ' +
      'resolves, when the bell cannot have focus yet. Its own in-flight toggle is aria-disabled.',
  },
  'features/analysis/components/AnalysisPageClient.tsx': {
    sites: ['!range || running'],
    reason:
      "Run's native disabled while running is pinned by analysis-api.spec.ts (the SSE parsing contract). " +
      'Converting it needs a PR-body-documented contract change (CLAUDE.md rule 6).',
  },
  'features/admin/components/RevokeConfirmModal.tsx': {
    sites: ['isPending'],
    reason:
      'Cancel is disabled while Revoke runs. Revoke (`loading`) is the control that holds focus, and Cancel ' +
      'cannot be activated during the request, so it never holds focus when it flips.',
  },
  'app/admin/invites/page.tsx': {
    sites: ['sending', 'sending', 'sending', 'sending'],
    reason:
      'The invite fields stay disabled while sending: only Send (`loading`) starts a send, and there is no ' +
      'form, so Enter in a field submits nothing. Focus is on Send, never on a field, when they flip.',
  },
  'app/dashboard/settings/page.tsx': {
    sites: ['deleteMutation.isPending', 'deleteMutation.isPending'],
    reason:
      'The delete-confirm field and Cancel stay disabled while deleting: only Confirm (`loading`) starts the ' +
      'delete, with no form, so focus is on Confirm, never on them, when they flip.',
  },
}

/** Frozen ceilings on files and on pinned sites: lower them as sites are converted, never raise them. */
const MAX_ALLOWLIST_SIZE = 5
const MAX_PINNED_SITES = 9

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const ROOTS = ['app', 'components', 'features', 'hooks', 'lib']

function walk(dir: string, out: string[]): string[] {
  for (const name of readdirSync(dir)) {
    const p = path.join(dir, name)
    if (statSync(p).isDirectory()) walk(p, out)
    else if (p.endsWith('.tsx')) out.push(p)
  }
  return out
}

interface Site {
  line: number
  /** The `disabled` expression, whitespace collapsed: what ALLOW pins. */
  expr: string
}

/**
 * One entry per JSX attribute named by `attribute` whose expression reaches a name matching `flag`, or names
 * one matching `direct` in the attribute's own expression (not through a binding).
 */
function sitesReaching(source: string, fileName: string, attribute: RegExp, flag: RegExp, direct?: RegExp): Site[] {
  const sf = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const visible = bindingResolver(sf)

  // Aliases are followed transitively. `path` holds only the bindings on the current chain, so a cycle
  // stops there but an alias already met on another branch is still followed on this one. A binding
  // proven busy stays busy from anywhere, so that result is remembered; "not busy" may be a cycle
  // cut-off and is not.
  const busyBindings = new Set<Binding>()
  const reachesBusy = (expr: ts.Node, path: Set<Binding>): boolean => {
    let hit = false
    const visit = (n: ts.Node): void => {
      if (hit) return
      if (ts.isIdentifier(n)) {
        if (flag.test(n.text) || (direct && path.size === 0 && direct.test(n.text))) {
          hit = true
          return
        }
        // `form.cannotSubmit` names a property, not a local binding.
        if (ts.isPropertyAccessExpression(n.parent) && n.parent.name === n) return
        const binding = visible(n)
        if (!binding?.alias || path.has(binding)) return
        if (busyBindings.has(binding)) {
          hit = true
          return
        }
        path.add(binding)
        const busy = reachesBusy(binding.alias, path)
        path.delete(binding)
        if (busy) {
          busyBindings.add(binding)
          hit = true
        }
        return
      }
      if (ts.isStringLiteralLike(n)) return
      ts.forEachChild(n, visit)
    }
    visit(expr)
    return hit
  }

  const sites: Site[] = []
  const visit = (node: ts.Node): void => {
    if (
      ts.isJsxAttribute(node) &&
      attribute.test(node.name.getText(sf)) &&
      node.initializer &&
      ts.isJsxExpression(node.initializer) &&
      node.initializer.expression &&
      reachesBusy(node.initializer.expression, new Set())
    ) {
      const { line } = sf.getLineAndCharacterOfPosition(node.getStart(sf))
      sites.push({ line: line + 1, expr: node.initializer.expression.getText(sf).replace(/\s+/g, ' ') })
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return sites
}

/** One entry per `disabled={…}` site whose expression reaches a busy or post-success flag. */
const BUSY_OR_AFTER_SUCCESS = new RegExp(`${BUSY.source}|${AFTER_SUCCESS.source}`, 'i')
const busyDisabledSites = (source: string, fileName: string): Site[] =>
  sitesReaching(source, fileName, /^disabled$/, BUSY_OR_AFTER_SUCCESS)

/**
 * A Retry of a query is `<RetryButton>` (hooks/useRetainedFailure.tsx): its busy state is the query's
 * `fetchStatus !== 'idle'`, it keeps the failure on screen through any refetch, and it hands focus off when
 * it unmounts while holding it. Two hand-rolled forms fail here:
 *  - `loading={…}` that reaches a fetching flag (`isFetching`, `xFetching`, `isRefetching`: false while a
 *    fetch waits paused offline or in a hidden tab, so the control goes live mid-request) or the query's
 *    `fetchStatus` (the right busy signal, hand-rolled: RetryButton owns it);
 *  - a handler (`on…`) that reaches `refetch…` (`refetchQueries` included) or a failure's `retry`, or that
 *    calls `invalidateQueries` or `resetQueries` in its own expression: a pressed refetch outside RetryButton.
 *    Those two count only written in the handler itself. Through bindings they reach every mutation whose
 *    `onSuccess` invalidates (rule (f) requires it) and every submit that refreshes after it lands: 20
 *    handlers in 15 files when measured, none of them a Retry. A Retry that invalidates through a named
 *    handler is left to the label clause.
 * RetryButton's own definition is exempt (RETRY_BUTTON below), and only it.
 */
const FETCHING = /fetching|fetchStatus/i
const PRESSED_REFETCH = /^refetch|^retry$/
const PRESSED_INVALIDATE = /^(invalidateQueries|resetQueries)$/
const retrySites = (source: string, fileName: string): Site[] =>
  outsideRetryButton(source, fileName, [
    ...sitesReaching(source, fileName, /^loading$/, FETCHING),
    ...sitesReaching(source, fileName, /^on[A-Z]/, PRESSED_REFETCH, PRESSED_INVALIDATE),
  ])

/** The sanctioned Retry: its own wiring and label are the rule, not an exception to it. */
const RETRY_BUTTON = { file: 'hooks/useRetainedFailure.tsx', name: 'RetryButton' }

/** The 1-based line range of RetryButton's own function declaration, in its file only; null elsewhere. */
function retryButtonLines(source: string, fileName: string): [number, number] | null {
  if (fileName !== RETRY_BUTTON.file) return null
  const sf = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  for (const statement of sf.statements) {
    if (ts.isFunctionDeclaration(statement) && statement.name?.text === RETRY_BUTTON.name) {
      const line = (pos: number) => sf.getLineAndCharacterOfPosition(pos).line + 1
      return [line(statement.getStart(sf)), line(statement.end)]
    }
  }
  return null
}

/** Drops the sites inside RetryButton's own definition; every other site, in any file, stays. */
function outsideRetryButton(source: string, fileName: string, sites: Site[]): Site[] {
  const lines = retryButtonLines(source, fileName)
  return lines ? sites.filter((site) => site.line < lines[0] || site.line > lines[1]) : sites
}

/**
 * The same rule by what the user reads, so a Retry wired through other names is still seen: any JSX element
 * other than `<RetryButton>` whose `loadingText` starts with "Retrying", or whose own label starts with
 * "Retry" or "Try again". The label is the element's text children and string-literal children (each
 * branch of a `cond ? 'a' : 'b'` child counts on its own), whitespace collapsed; a nested element's text is
 * that element's own label. `expr` is `Tag "label"`, which ALLOW_RETRY_LABEL pins.
 */
const RETRY_LABEL = /^(retry|try again)\b/i
const RETRY_LOADING_TEXT = /^Retrying/
function retryLabelSites(source: string, fileName: string): Site[] {
  const sf = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const visible = bindingResolver(sf)
  /**
   * String literals an expression child can render: itself, either branch of a conditional or `||`/`??`/`&&`,
   * or what a same-file const visible from it holds (`const label = 'Retry'`; `seen` stops a cycle).
   */
  const literals = (e: ts.Expression, seen = new Set<Binding>()): string[] => {
    if (ts.isStringLiteralLike(e)) return [e.text]
    if (ts.isParenthesizedExpression(e)) return literals(e.expression, seen)
    if (ts.isConditionalExpression(e)) return [...literals(e.whenTrue, seen), ...literals(e.whenFalse, seen)]
    if (ts.isBinaryExpression(e)) return [...literals(e.left, seen), ...literals(e.right, seen)]
    if (ts.isIdentifier(e)) {
      const binding = visible(e)
      if (!binding?.init || seen.has(binding)) return []
      return literals(binding.init, new Set([...seen, binding]))
    }
    return []
  }
  const collapse = (text: string) => text.replace(/\s+/g, ' ').trim()
  const sites: Site[] = []
  const visit = (node: ts.Node): void => {
    if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) {
      const opening = ts.isJsxElement(node) ? node.openingElement : node
      const tag = opening.tagName.getText(sf)
      const labels: string[] = []
      for (const attr of opening.attributes.properties) {
        if (!ts.isJsxAttribute(attr) || attr.name.getText(sf) !== 'loadingText' || !attr.initializer) continue
        const value = ts.isStringLiteral(attr.initializer)
          ? [attr.initializer.text]
          : attr.initializer.expression ? literals(attr.initializer.expression) : []
        labels.push(...value.map(collapse).filter((text) => RETRY_LOADING_TEXT.test(text)))
      }
      if (ts.isJsxElement(node)) {
        let text = ''
        for (const child of node.children) {
          if (ts.isJsxText(child)) text += child.text
          else if (ts.isJsxExpression(child) && child.expression) {
            const options = literals(child.expression)
            if (options.length === 1) text += options[0]
            else labels.push(...options.map(collapse).filter((option) => RETRY_LABEL.test(option)))
          }
        }
        if (RETRY_LABEL.test(collapse(text))) labels.unshift(collapse(text))
      }
      if (labels.length && tag !== 'RetryButton') {
        const { line } = sf.getLineAndCharacterOfPosition(node.getStart(sf))
        sites.push({ line: line + 1, expr: `${tag} "${labels[0]}"` })
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return outsideRetryButton(source, fileName, sites)
}

/**
 * What RetryButton is given: each element of its `failures={[…]}` is the query's retained failure,
 * `useRetainedFailure(query, queryKey)`, written inline, held by a same-file `const`, or as either branch of a
 * conditional. Anything else is a failure built by hand, `{ failed, error, busy, retry }`: it skips the hold
 * (a refetch nobody pressed swaps the card, and its focused Retry, for a skeleton), and its `busy` can be
 * `isFetching`, the bug the wiring clause catches on `loading`. What the scan cannot prove counts as built by
 * hand too: a `failures` that is not an array literal, a spread element, a call of anything else, a `let` or
 * `var` (a later assignment can replace it), and any JSX spread on a RetryButton (`{...props}` can carry
 * `failures`, so a forwarding wrapper fails here). RetryButton is matched by its own name and by any local
 * name an import gives it (`{ RetryButton as Again }`). `expr` is the element's text.
 *
 * A failure that arrives as a destructured prop of the component rendering RetryButton (YourCompanies'
 * `failure`) is followed to every JSX use of that component in the scanned files (FailureProp, propPassSites):
 * by its declared name in its own file, and elsewhere by the local name an import of its module gives it (a
 * default import may take any name). The value passed there must be retained the same way; a use that spreads props into it (`{...rest}`)
 * cannot be proven and fails, and a prop no scanned file passes fails as unproven. One hop only: a value that
 * is itself a prop at the call site fails.
 */
const RETAINED_FAILURE = 'useRetainedFailure'
interface FailureProp { component: string; prop: string; line: number; isDefault: boolean }

/** Whether an expression is a retained failure, resolved in its own file. */
function retainedIn(sf: ts.SourceFile): (e: ts.Expression) => boolean {
  const visible = bindingResolver(sf)
  const isConst = (binding: Binding) =>
    ts.isVariableDeclaration(binding.decl) && (ts.getCombinedNodeFlags(binding.decl) & ts.NodeFlags.Const) !== 0
  const retained = (e: ts.Expression, seen = new Set<Binding>()): boolean => {
    if (ts.isParenthesizedExpression(e)) return retained(e.expression, seen)
    if (ts.isConditionalExpression(e)) return retained(e.whenTrue, seen) && retained(e.whenFalse, seen)
    if (ts.isCallExpression(e)) return ts.isIdentifier(e.expression) && e.expression.text === RETAINED_FAILURE
    if (ts.isIdentifier(e)) {
      const binding = visible(e)
      if (!binding?.init || seen.has(binding) || !isConst(binding)) return false
      return retained(binding.init, new Set([...seen, binding]))
    }
    return false
  }
  return (e) => retained(e)
}

/** Local names an import in this file gives `exported` (a named export) or the default export of a module. */
function importedNames(sf: ts.SourceFile, fileName: string, from: (specifier: string) => boolean, exported: string, isDefault: boolean): string[] {
  const names: string[] = []
  for (const statement of sf.statements) {
    if (!ts.isImportDeclaration(statement) || !ts.isStringLiteral(statement.moduleSpecifier)) continue
    if (!from(resolveModule(fileName, statement.moduleSpecifier.text))) continue
    const clause = statement.importClause
    if (!clause) continue
    if (isDefault && clause.name) names.push(clause.name.text)
    if (clause.namedBindings && ts.isNamedImports(clause.namedBindings)) {
      for (const el of clause.namedBindings.elements) {
        const imported = (el.propertyName ?? el.name).text
        if (imported === exported || (isDefault && imported === 'default')) names.push(el.name.text)
      }
    }
  }
  return names
}

/** A module specifier as a path from the frontend root without an extension ('@/x/y' and './y' alike). */
function resolveModule(fileName: string, specifier: string): string {
  if (specifier.startsWith('@/')) return specifier.slice(2)
  if (specifier.startsWith('.')) return path.posix.join(path.posix.dirname(fileName), specifier)
  return specifier
}
const withoutExtension = (file: string) => file.replace(/\.(tsx?|jsx?)$/, '').replace(/\/index$/, '')

/** RetryButton's local names in this file: its own, and any an import from its module gives it. */
function retryButtonNames(sf: ts.SourceFile, fileName: string): Set<string> {
  const home = withoutExtension(RETRY_BUTTON.file)
  return new Set([RETRY_BUTTON.name, ...importedNames(sf, fileName, (m) => withoutExtension(m) === home, RETRY_BUTTON.name, false)])
}

/** The component a destructured prop belongs to, the prop's name, and whether it is its module's default export. */
function propOf(sf: ts.SourceFile, e: ts.Expression): { component: string; prop: string; isDefault: boolean } | null {
  if (!ts.isIdentifier(e)) return null
  const decl = bindingResolver(sf)(e)?.decl
  if (!decl || !ts.isBindingElement(decl) || !ts.isObjectBindingPattern(decl.parent)) return null
  const param = decl.parent.parent
  if (!ts.isParameter(param)) return null
  const fn = param.parent
  const name = ts.isFunctionDeclaration(fn)
    ? fn.name?.text
    : (ts.isArrowFunction(fn) || ts.isFunctionExpression(fn)) && ts.isVariableDeclaration(fn.parent) && ts.isIdentifier(fn.parent.name)
      ? fn.parent.name.text
      : undefined
  if (!name) return null
  const exportsDefault =
    (ts.isFunctionDeclaration(fn) &&
      !!fn.modifiers?.some((m) => m.kind === ts.SyntaxKind.ExportKeyword) &&
      !!fn.modifiers?.some((m) => m.kind === ts.SyntaxKind.DefaultKeyword)) ||
    sf.statements.some((st) => ts.isExportAssignment(st) && !st.isExportEquals && ts.isIdentifier(st.expression) && st.expression.text === name)
  return { component: name, prop: (decl.propertyName ?? decl.name).getText(sf), isDefault: exportsDefault }
}

const jsxOf = (attr: ts.Node): ts.JsxOpeningElement | ts.JsxSelfClosingElement | null =>
  attr.parent && (ts.isJsxOpeningElement(attr.parent.parent) || ts.isJsxSelfClosingElement(attr.parent.parent)) ? attr.parent.parent : null

/** RetryButton's failures in one file: those built by hand, and those that arrive as a prop (followed by propPassSites). */
function failureScan(source: string, fileName: string): { handBuilt: Site[]; props: FailureProp[] } {
  const sf = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const retained = retainedIn(sf)
  const retryNames = retryButtonNames(sf, fileName)
  const handBuilt: Site[] = []
  const props: FailureProp[] = []
  const lineOf = (node: ts.Node) => sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
  const flag = (node: ts.Node) => handBuilt.push({ line: lineOf(node), expr: node.getText(sf).replace(/\s+/g, ' ') })
  const check = (e: ts.Expression) => {
    if (retained(e)) return
    const prop = propOf(sf, e)
    if (prop) props.push({ ...prop, line: lineOf(e) })
    else flag(e)
  }
  const visit = (node: ts.Node): void => {
    const element = ts.isJsxAttribute(node) || ts.isJsxSpreadAttribute(node) ? jsxOf(node) : null
    if (element && retryNames.has(element.tagName.getText(sf))) {
      if (ts.isJsxSpreadAttribute(node)) flag(node)
      else if (ts.isJsxAttribute(node) && node.name.getText(sf) === 'failures') {
        const value = node.initializer && ts.isJsxExpression(node.initializer) ? node.initializer.expression : undefined
        if (!value) flag(node)
        else if (!ts.isArrayLiteralExpression(value)) check(value)
        else for (const item of value.elements) {
          if (ts.isSpreadElement(item)) flag(item)
          else check(item)
        }
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return { handBuilt, props }
}

/**
 * Every JSX use in one file of a component given in `props` (by its declared name in its own file, and by any
 * local name an import of its module gives it): `passed` marks each prop seen, a value that is not a retained failure is a site,
 * `Component prop={…}`, and so is a spread into it (`Component {...rest}`).
 */
function propPassSites(source: string, fileName: string, props: (FailureProp & { file: string })[], passed: Set<string>): Site[] {
  const sf = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const retained = retainedIn(sf)
  const local = new Map<string, (FailureProp & { file: string })[]>()
  for (const p of props) {
    const home = withoutExtension(p.file)
    // Its declared name in its own file; elsewhere only what an import of its module binds (another file's
    // `Card` from another module is another component).
    const names = [
      ...(withoutExtension(fileName) === home ? [p.component] : []),
      ...importedNames(sf, fileName, (m) => withoutExtension(m) === home, p.component, p.isDefault),
    ]
    for (const name of new Set(names)) local.set(name, [...(local.get(name) ?? []), p])
  }
  const sites: Site[] = []
  const site = (node: ts.Node, tag: string) => {
    const { line } = sf.getLineAndCharacterOfPosition(node.getStart(sf))
    sites.push({ line: line + 1, expr: `${tag} ${node.getText(sf).replace(/\s+/g, ' ')}` })
  }
  const visit = (node: ts.Node): void => {
    const element = ts.isJsxAttribute(node) || ts.isJsxSpreadAttribute(node) ? jsxOf(node) : null
    const tag = element?.tagName.getText(sf)
    const uses = tag ? local.get(tag) : undefined
    if (element && tag && uses) {
      if (ts.isJsxSpreadAttribute(node)) site(node, tag)
      else if (ts.isJsxAttribute(node)) {
        for (const p of uses.filter((u) => u.prop === node.name.getText(sf))) {
          passed.add(`${p.file}:${p.component}.${p.prop}`)
          const value = node.initializer && ts.isJsxExpression(node.initializer) ? node.initializer.expression : undefined
          if (!value || !retained(value)) site(node, tag)
        }
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return sites
}

/**
 * Failures built by hand, pinned by the element's exact text (whitespace collapsed), so a change to one (a
 * `busy` fed by a fetching flag) fails until it is re-reviewed. Capped. The one sanctioned way in is a stream
 * restart converted to RetryButton: that change raises both caps by one as its ALLOW_RETRY_LABEL pin, and that
 * list's caps, go down by one. Anything else only shrinks it.
 */
const ALLOW_HAND_BUILT_FAILURE: Record<string, { sites: string[]; reason: string }> = {
  'app/filing/[id]/StreamingSummaryDisplay.tsx': {
    sites: ['{ failed: true, error: error || message, busy: false, retry: onRetry }'],
    reason:
      'Retry generation restarts the SSE stream, not a query: there is no query to hold. Its press clears the ' +
      'error in the render that starts the stream, so the card never shows a run in flight (busy is false) and ' +
      'leaves with the press when the run starts (a signed-out press starts none: the card stays, Retry focused); ' +
      'RetryButton is there for the hand-off to the progress heading (EN-05).',
  },
}
const MAX_HAND_BUILT_FAILURE_FILES = 1
const MAX_HAND_BUILT_FAILURE_SITES = 1

/** Open rule (h) cases, pinned by exact expression. Shrink-only: converting one to RetryButton removes its pin. */
const ALLOW_RETRY: Record<string, { sites: string[]; reason: string }> = {
  'app/company/[ticker]/page-client.tsx': {
    sites: ['filingsRefetching', 'filingsRefetching', '() => refetchFilings()'],
    reason: "The filings Retry and Show full history: open in rule (h), the company page's own follow-up.",
  },
  'features/calendar/components/EarningsCalendarPage.tsx': {
    sites: ['() => query.refetch()'],
    reason: '"Try again" on the calendar error card: open in rule (h).',
  },
  'features/search/components/FullTextSearch.tsx': {
    sites: ['() => refetch()'],
    reason: 'The full-text search Retry: open in rule (h).',
  },
}
const MAX_RETRY_ALLOWLIST_SIZE = 3
const MAX_RETRY_PINNED_SITES = 5

/**
 * Every element the label scan sees that is not a RetryButton, pinned by `Tag "label"`, with a reason.
 * Shrink-only and capped: converting one to RetryButton removes its pin, and a new one fails.
 */
const ERROR_BOUNDARY_RESET =
  "A React error boundary's reset: it re-renders the crashed subtree, with no query to hold a failure for or to " +
  'retry, and nothing it refetches can swap it for a skeleton.'
const STREAM_RESTART =
  'Restarts a streamed generation or answer (SSE), not a query refetch, so there is no query to hold. Not yet ' +
  "converted: converting one makes it RetryButton with a failure built by hand, as the filing page's Retry " +
  'generation is, moving its pin (and one from each cap) from this list to ALLOW_HAND_BUILT_FAILURE. '
const ALLOW_RETRY_LABEL: Record<string, { sites: string[]; reason: string }> = {
  'app/error.tsx': { sites: ['Button "Try again"'], reason: ERROR_BOUNDARY_RESET },
  'app/global-error.tsx': { sites: ['button "Try again"'], reason: ERROR_BOUNDARY_RESET },
  'app/dashboard/error.tsx': { sites: ['Button "Try Again"'], reason: ERROR_BOUNDARY_RESET },
  'components/GlobalErrorBoundary.tsx': { sites: ['Button "Try again"'], reason: ERROR_BOUNDARY_RESET },
  'features/summaries/components/SummaryDisplay.tsx': {
    sites: ['Button "Retry"'],
    reason: STREAM_RESTART + "The filing page's summary Retry regenerates it; open in rule (h).",
  },
  'features/filings/components/copilot/CopilotMessage.tsx': {
    sites: ['Button "Retry"'],
    reason: STREAM_RESTART + 'Re-asks a copilot question whose answer stream failed.',
  },
  'features/filings/components/AskFilingAnswer.tsx': {
    sites: ['Button "Retry"'],
    reason: STREAM_RESTART + "The design system's reference copilot answer (0 importers), as CopilotMessage.",
  },
  'app/company/[ticker]/page-client.tsx': {
    sites: ['Button "Retry"'],
    reason: "The filings Retry: open in rule (h), the company page's own follow-up (also in ALLOW_RETRY).",
  },
  'features/calendar/components/EarningsCalendarPage.tsx': {
    sites: ['Button "Try again"'],
    reason: '"Try again" on the calendar error card: open in rule (h) (also in ALLOW_RETRY).',
  },
  'features/search/components/FullTextSearch.tsx': {
    sites: ['button "Retry"'],
    reason: 'The full-text search Retry: open in rule (h) (also in ALLOW_RETRY).',
  },
  'features/filings/components/copilot/FilingViewer.tsx': {
    sites: ['Button "Try again"'],
    reason: '"Try again" for the filing text, a hand-rolled fetch, not a query: open in rule (h).',
  },
}
const MAX_RETRY_LABEL_ALLOWLIST_SIZE = 11
const MAX_RETRY_LABEL_PINNED_SITES = 11

/** Sites not covered by their file's pins, as `file:line: expr`. Each pin covers one site. */
function unpinned(foundSites: Map<string, Site[]>, allow: Record<string, { sites: string[] }>): string[] {
  const offenders: string[] = []
  for (const [file, sites] of foundSites) {
    const allowed = [...(allow[file]?.sites ?? [])]
    for (const site of sites) {
      const i = allowed.indexOf(site.expr)
      if (i === -1) offenders.push(`${file}:${site.line}: ${site.expr}`)
      else allowed.splice(i, 1)
    }
  }
  return offenders
}

const found = new Map<string, Site[]>()
const foundRetry = new Map<string, Site[]>()
const foundRetryLabel = new Map<string, Site[]>()
const foundHandBuilt = new Map<string, Site[]>()
const failureProps: (FailureProp & { file: string })[] = []
const sources = new Map<string, string>()
const scanned: string[] = []
for (const abs of ROOTS.flatMap((root) => walk(path.join(frontendRoot, root), []))) {
  const rel = path.relative(frontendRoot, abs).split(path.sep).join('/')
  scanned.push(rel)
  const source = readFileSync(abs, 'utf8')
  const sites = busyDisabledSites(source, rel)
  if (sites.length) found.set(rel, sites)
  const retries = retrySites(source, rel)
  if (retries.length) foundRetry.set(rel, retries)
  const labels = retryLabelSites(source, rel)
  if (labels.length) foundRetryLabel.set(rel, labels)
  const { handBuilt, props } = failureScan(source, rel)
  if (handBuilt.length) foundHandBuilt.set(rel, handBuilt)
  failureProps.push(...props.map((prop) => ({ ...prop, file: rel })))
  sources.set(rel, source)
}
// A failure that arrives as a prop: its value at every call site, and a prop no scanned file passes.
const passedProps = new Set<string>()
for (const [rel, source] of sources) {
  const sites = propPassSites(source, rel, failureProps, passedProps)
  if (sites.length) foundHandBuilt.set(rel, [...(foundHandBuilt.get(rel) ?? []), ...sites])
}
for (const prop of failureProps) {
  if (passedProps.has(`${prop.file}:${prop.component}.${prop.prop}`)) continue
  const site = { line: prop.line, expr: `${prop.component} ${prop.prop}: never passed` }
  foundHandBuilt.set(prop.file, [...(foundHandBuilt.get(prop.file) ?? []), site])
}

describe('busy controls stay focusable (rule-12 gate)', () => {
  it('the scanner sees busy and post-success flags directly, through members and through same-file consts, and nothing else', () => {
    const fixture = [
      'const refreshDisabled = isRefetching || !ready',
      'const viaTwo = refreshDisabled',
      'export function X() {',
      '  return (<>',
      '    <button disabled={mutation.isPending} />',
      '    <Button disabled={loading || !valid} />',
      '    <button disabled={viaTwo} />',
      '    <Button disabled={resent} />',
      '    <button disabled={mutation.isSuccess || cooldown > 0} />',
      '    <Button loading={saving} disabled={!valid} />',
      '    <button aria-disabled={pending} />',
      '    <button disabled={!email} />',
      "    <button disabled={'pending' === mode} />",
      '    {/* <button disabled={isPending} /> */}',
      '    <button disabled />',
      '  </>)',
      '}',
    ].join('\n')
    expect(busyDisabledSites(fixture, 'fixture.tsx').map((site) => site.expr)).toEqual([
      'mutation.isPending',
      'loading || !valid',
      'viaTwo',
      'resent',
      'mutation.isSuccess || cooldown > 0',
    ])
  })

  it('resolves each name to the binding visible from the site, not the last one declared in the file', () => {
    const fixture = [
      'const shadowed = isLoading',
      'function A() {',
      '  const cannotSubmit = isPending',
      '  return <button disabled={cannotSubmit} />', // A's own busy alias: counts
      '}',
      'function B() {',
      '  const cannotSubmit = !valid',
      '  return <button disabled={cannotSubmit} />', // B's validation alias: does not count
      '}',
      'function C({ isPending: waiting, ready }: Props) {',
      '  return <><button disabled={waiting} /><button disabled={ready} /></>', // renamed busy prop counts
      '}',
      'function D(shadowed: boolean) {',
      '  return <button disabled={shadowed} />', // the parameter, not the outer busy const
      '}',
      'function E() {',
      '  return <button disabled={shadowed} />', // the outer busy const
      '}',
      'function F() {',
      '  return <button disabled={form.cannotSubmit} />', // a property, not A's binding
      '}',
      // The same pair in the other order: the earlier, non-busy sibling must not count either.
      'function G() {',
      '  const canSend = true',
      '  return <button disabled={!canSend} />', // does not count
      '}',
      'function H() {',
      '  const canSend = !request.isPending',
      '  return <button disabled={!canSend} />', // counts
      '}',
    ].join('\n')
    expect(busyDisabledSites(fixture, 'fixture.tsx').map((site) => `${site.line}: ${site.expr}`)).toEqual([
      '4: cannotSubmit',
      '11: waiting',
      '17: shadowed',
      '28: !canSend',
    ])
  })

  it('follows every path to an alias, however long, and stops only on a cycle', () => {
    const fixture = [
      'function I() {',
      '  const a2 = mutation.isPending',
      '  const a1 = a2',
      '  const fieldBlocked = a1', // three hops to the busy flag
      '  const b1 = fieldBlocked',
      '  const buttonBlocked = b1', // reaches fieldBlocked first, on a longer path
      '  return <button disabled={buttonBlocked || fieldBlocked} />', // counts
      '}',
      'function J() {',
      '  const c5 = isSaving',
      '  const c4 = c5',
      '  const c3 = c4',
      '  const c2 = c3',
      '  const c1 = c2',
      '  return <button disabled={c1} />', // five hops: counts
      '}',
      'function K() {',
      '  let x = y',
      '  let y = x',
      '  return <button disabled={x} />', // a cycle with no busy flag: does not count, and terminates
      '}',
    ].join('\n')
    expect(busyDisabledSites(fixture, 'fixture.tsx').map((site) => `${site.line}: ${site.expr}`)).toEqual([
      '7: buttonBlocked || fieldBlocked',
      '15: c1',
    ])
  })

  it('no control takes native disabled from a busy flag outside the allowlist', () => {
    const offenders: string[] = []
    for (const [file, sites] of found) {
      const allowed = [...(ALLOW[file]?.sites ?? [])]
      for (const site of sites) {
        const i = allowed.indexOf(site.expr)
        if (i === -1) offenders.push(`${file}:${site.line}: disabled={${site.expr}}`)
        else allowed.splice(i, 1)
      }
    }
    expect(
      offenders,
      'A control busy with a request must stay focusable: use the DS Button `loading` prop, or aria-disabled ' +
        '(+ aria-busy) and an early return in the handler; readOnly for a text field. ' +
        'See lessons/frontend-busy-controls-stay-focusable.md.',
    ).toEqual([])
  })

  it('is shrink-only, and every entry has a reason', () => {
    expect(
      Object.keys(ALLOW).length,
      `ALLOW has ${Object.keys(ALLOW).length} entries but the ceiling is ${MAX_ALLOWLIST_SIZE}. Fix the control instead of adding an entry.`,
    ).toBeLessThanOrEqual(MAX_ALLOWLIST_SIZE)
    // Files alone are not enough: a new exception appended to a listed file keeps the file count.
    const pinned = Object.values(ALLOW).reduce((sum, { sites }) => sum + sites.length, 0)
    expect(
      pinned,
      `ALLOW pins ${pinned} sites but the ceiling is ${MAX_PINNED_SITES}. Fix the control instead of pinning it.`,
    ).toBeLessThanOrEqual(MAX_PINNED_SITES)
    for (const [file, { reason }] of Object.entries(ALLOW)) {
      expect(reason.trim().length, `${file} needs a reason`).toBeGreaterThan(0)
    }
  })

  it.each(Object.keys(ALLOW))('%s still has every pinned site (remove the pins of converted ones)', (file) => {
    const actual = (found.get(file) ?? []).map((site) => site.expr).sort()
    expect(actual, `${file}: a pinned busy-disabled site was converted or edited; update its ALLOW pins.`).toEqual(
      [...ALLOW[file].sites].sort(),
    )
  })
})

const RETRY_GATE_MESSAGE =
  'A Retry of a query is <RetryButton failures={[useRetainedFailure(query, queryKey)]} focusTarget={headingRef}> ' +
  '(hooks/useRetainedFailure.tsx): busy from fetchStatus (isFetching is false while a fetch waits paused), the ' +
  'failure held through any refetch, "Retrying…" only for its own press, and a focus hand-off when it unmounts ' +
  'while focused. See lessons/frontend-busy-controls-stay-focusable.md (d), (g).'

describe('a Retry of a query is RetryButton (rule-12 gate)', () => {
  it('sees loading fed by a fetching flag or fetchStatus and a handler that refetches, invalidates or retries, and nothing else', () => {
    const fixture = [
      'function A({ isFetching: inFlight }: Props) {',
      '  const { refetch, isFetching } = query',
      '  const busy = isFetching',
      '  const onRetry = () => { armed.current = true; failure.retry() }',
      '  const save = useMutation({ mutationFn, onSuccess: () => queryClient.invalidateQueries({ queryKey }) })',
      '  const onReload = () => queryClient.invalidateQueries({ queryKey })',
      '  function reload() { void query.refetch() }',
      '  return (<>',
      '    <Button loading={busy} onClick={() => refetch()}>Retry</Button>', // both clauses
      '    <Button loading={inFlight} onClick={onRetry}>Retry</Button>', // renamed prop; retry through a const
      "    <Button loading={query.fetchStatus !== 'idle'} onClick={() => setOpen(true)}>Open</Button>", // fetchStatus
      '    <Button onClick={() => queryClient.invalidateQueries({ queryKey })}>Reload</Button>', // invalidate, inline
      '    <Button onClick={() => void client.resetQueries()}>Reload</Button>', // reset, inline
      '    <Button onClick={() => client.refetchQueries()}>Reload</Button>', // refetchQueries is a refetch…
      '    <Button loading={save.isPending} onClick={() => save.mutate()}>Save</Button>', // neither: its onSuccess
      '    <Button onClick={onReload}>Reload</Button>', // neither: invalidate counts only inline
      '    <RetryButton failures={[failure]} focusTarget={ref}>Retry</RetryButton>', // neither
      '    <Button onClick={reload}>Reload</Button>', // refetch through a function declaration
      '  </>)',
      '}',
    ].join('\n')
    expect(retrySites(fixture, 'fixture.tsx').map((site) => `${site.line}: ${site.expr}`)).toEqual([
      '9: busy',
      '10: inFlight',
      "11: query.fetchStatus !== 'idle'",
      '9: () => refetch()',
      '10: onRetry',
      '12: () => queryClient.invalidateQueries({ queryKey })',
      '13: () => void client.resetQueries()',
      '14: () => client.refetchQueries()',
      '18: reload',
    ])
  })

  it('binds a function declaration in its own block, and an overloaded one to its implementation', () => {
    const fixture = [
      'export function A({ query }: Props) {',
      '  function reload() { void query.refetch() }',
      '  return <Button onClick={reload}>Reload</Button>', // A's reload refetches: counts
      '}',
      'export function B() {',
      "  function reload() { track('reload') }",
      '  return <Button onClick={reload}>Reload</Button>', // B's own reload, not A's: does not count
      '}',
      'function refresh(): void',
      'function refresh(force?: boolean) { void client.refetchQueries() }',
      'export function C() {',
      '  return <Button onClick={refresh}>Reload</Button>', // the implementation, not the bodiless signature: counts
      '}',
    ].join('\n')
    expect(retrySites(fixture, 'fixture.tsx').map((site) => `${site.line}: ${site.expr}`)).toEqual([
      '3: reload',
      '12: refresh',
    ])
  })

  it("exempts RetryButton's own definition, in its own file, and nothing else", () => {
    const handRolled = (name: string) => [
      `export function ${name}({ query }: Props) {`,
      "  return <Button loading={query.isFetching} loadingText={'Retrying…'} onClick={() => query.refetch()}>Retry</Button>",
      '}',
    ]
    const fixture = [...handRolled('RetryButton'), ...handRolled('OtherRetry')].join('\n')
    const seen = (file: string) => [
      ...retrySites(fixture, file).map((site) => `${site.line}: ${site.expr}`),
      ...retryLabelSites(fixture, file).map((site) => `${site.line}: ${site.expr}`),
    ]
    expect(seen(RETRY_BUTTON.file)).toEqual([
      '5: query.isFetching',
      '5: () => query.refetch()',
      '5: Button "Retry"',
    ])
    // Anywhere else, a function named RetryButton is just another hand-rolled Retry.
    expect(seen('features/x/RetryButton.tsx')).toHaveLength(6)
    // The real definition is still there to exempt, and unexempted it would fail both Retry clauses: the
    // exemption is not vacuous, and a renamed RetryButton fails here instead of silently losing it.
    const real = readFileSync(path.join(frontendRoot, RETRY_BUTTON.file), 'utf8')
    expect(retryButtonLines(real, RETRY_BUTTON.file)).not.toBeNull()
    expect(sitesReaching(real, RETRY_BUTTON.file, /^on[A-Z]/, PRESSED_REFETCH).length).toBeGreaterThan(0)
    expect(retryLabelSites(real, 'unexempted.tsx').length).toBeGreaterThan(0)
  })

  it('scans hooks/ and lib/ too, so RetryButton itself is held to the busy-disabled clause', () => {
    expect(scanned).toContain(RETRY_BUTTON.file)
    expect(scanned.some((file) => file.startsWith('lib/'))).toBe(true)
  })

  it('sees a Retry by its label or its "Retrying…" text on anything but RetryButton, and nothing else', () => {
    const fixture = [
      'export function X() {',
      '  return (<>',
      '    <Button onClick={load}>Retry</Button>', // label
      '    <button onClick={reset}>',
      '      <Icon /> Try again', // label after an icon
      '    </button>',
      '    <Button loading={busy} loadingText="Retrying…" onClick={go}>Load</Button>', // loadingText
      "    <Button loading={busy} loadingText={'Retrying…'} onClick={go}>Load</Button>", // loadingText, expression
      "    <Button onClick={go}>{busy ? 'Retrying…' : 'Retry generation'}</Button>", // a branch's label
      '    <Button onClick={go}>Retry account check</Button>', // label
      '    <RetryButton failures={[f]} focusTarget={ref}>Retry</RetryButton>', // the sanctioned control
      '    <Button onClick={go}>Retrying is not a word here</Button>', // "Retrying" is no Retry label
      '    <p>Please try again later.</p>', // prose: the label does not start with it
      '    <Button aria-label="Retry" onClick={go}>Reload</Button>', // attributes other than loadingText
      '    {/* <Button>Retry</Button> */}',
      '    <Button onClick={go}>{retryLabel}</Button>', // a same-file const
      '    <Button loading={busy} loadingText={pressedText} onClick={go}>Load</Button>', // a const, conditional
      '    <Button onClick={go}>{label}</Button>', // a parameter: not resolved
      '  </>)',
      '}',
      "const retryLabel = 'Try again'",
      "const pressedText = pressed ? 'Retrying…' : 'Loading…'",
      'function Y(label: string) {',
      '  return <Button onClick={go}>{label}</Button>', // the parameter, not an outer const
      '}',
      'const label = loop', // a cycle with no string: terminates
      'const loop = label',
    ].join('\n')
    expect(retryLabelSites(fixture, 'fixture.tsx').map((site) => `${site.line}: ${site.expr}`)).toEqual([
      '3: Button "Retry"',
      '4: button "Try again"',
      '7: Button "Retrying…"',
      '8: Button "Retrying…"',
      '9: Button "Retry generation"',
      '10: Button "Retry account check"',
      '16: Button "Try again"',
      '17: Button "Retrying…"',
    ])
  })

  it("sees a failure built by hand in RetryButton's failures, and not the retained one, however it is held", () => {
    const fixture = [
      "import { RetryButton as Again, type RetryButtonProps } from '@/hooks/useRetainedFailure'",
      'export function X({ fromProp, other }: { fromProp: RetainedFailure; other: number }, extra: RetainedFailure) {',
      '  const failure = useRetainedFailure(query, key)',
      '  const alias = failure',
      '  const built = { failed: q.isError, error: q.error, busy: q.isFetching, retry: () => void q.refetch() }',
      '  let reassigned = useRetainedFailure(query, key)',
      '  reassigned = built',
      '  return (<>',
      '    <RetryButton failures={[failure]} focusTarget={ref}>Retry</RetryButton>', // a const
      '    <RetryButton failures={[useRetainedFailure(q, k)]} focusTarget={ref} />', // inline
      '    <RetryButton failures={[a ? failure : (alias)]} focusTarget={ref} />', // both branches, an alias
      '    <RetryButton failures={[{ failed: q.isError, error: q.error, busy: q.isFetching, retry: q.refetch }]} focusTarget={ref} />',
      '    <RetryButton failures={[failure, built]} focusTarget={ref} />', // a const holding a literal
      '    <RetryButton failures={[a ? failure : built]} focusTarget={ref} />', // one branch built by hand
      '    <RetryButton failures={list} focusTarget={ref} />', // not an array literal
      '    <RetryButton failures={[...list]} focusTarget={ref} />', // a spread element
      '    <RetryButton failures={[makeFailure(q)]} focusTarget={ref} />', // a call of anything else
      '    <RetryButton failures={[extra]} focusTarget={ref} />', // a plain parameter, not a prop
      '    <RetryButton failures={[reassigned]} focusTarget={ref} />', // a let: a later assignment replaced it
      '    <RetryButton {...{ failures: [built] }} focusTarget={ref} />', // a JSX spread can carry failures
      '    <Again failures={[built]} focusTarget={ref}>Reload list</Again>', // RetryButton under an import alias
      '    <RetryButton failures={[fromProp]} focusTarget={ref} />', // a prop: followed to its call sites
      '    <Other failures={[{ failed: true }]} />', // not RetryButton
      '  </>)',
      '}',
      'export function Forward(props: RetryButtonProps) {',
      '  return <RetryButton size="sm" {...props} />', // a forwarding wrapper: the spread carries failures
      '}',
    ].join('\n')
    const { handBuilt, props } = failureScan(fixture, 'fixture.tsx')
    expect(handBuilt.map((site) => `${site.line}: ${site.expr}`)).toEqual([
      '12: { failed: q.isError, error: q.error, busy: q.isFetching, retry: q.refetch }',
      '13: built',
      '14: a ? failure : built',
      '15: list',
      '16: ...list',
      '17: makeFailure(q)',
      '18: extra',
      '19: reassigned',
      '20: {...{ failures: [built] }}',
      '21: built',
      '27: {...props}',
    ])
    expect(props).toEqual([{ component: 'X', prop: 'fromProp', line: 22, isDefault: false }])
  })

  it('follows a failure prop to every use of its component, under any imported name, and fails a spread or an unproven prop', () => {
    const component = [
      "import { RetryButton } from '@/hooks/useRetainedFailure'",
      'export default function Card({ failure }: { failure: RetainedFailure }) {',
      '  return <RetryButton failures={[failure]} focusTarget={ref}>Retry</RetryButton>',
      '}',
    ].join('\n')
    const { handBuilt, props } = failureScan(component, 'features/x/Card.tsx')
    expect(handBuilt).toEqual([])
    expect(props).toEqual([{ component: 'Card', prop: 'failure', line: 3, isDefault: true }])
    const threaded = props.map((p) => ({ ...p, file: 'features/x/Card.tsx' }))
    const caller = [
      "import Renamed from '@/features/x/Card'", // a default import may take any name
      'export function Page({ rest }: { rest: object }) {',
      '  const held = useRetainedFailure(query, key)',
      '  const loose = { failed: true, error: null, busy: q.isFetching, retry: q.refetch }',
      '  return (<>',
      '    <Renamed failure={held} />', // retained: passes
      '    <Renamed failure={loose} />', // built by hand at the call site
      '    <Renamed {...rest} />', // a spread could carry the failure
      "    <Card failure={loose} />", // no Card is imported here: another component, not followed
      '    <Other failure={loose} />', // another component: not followed
      '  </>)',
      '}',
    ].join('\n')
    const passed = new Set<string>()
    expect(propPassSites(caller, 'app/page.tsx', threaded, passed).map((site) => `${site.line}: ${site.expr}`)).toEqual([
      '7: Renamed failure={loose}',
      '8: Renamed {...rest}',
    ])
    expect([...passed]).toEqual(['features/x/Card.tsx:Card.failure'])
    // A `Card` imported from another module is another component: it passes nothing for this one.
    const unrelated = new Set<string>()
    expect(propPassSites("import Card from '@/features/y/Other'\nexport const P = () => <Card failure={x} />", 'app/p.tsx', threaded, unrelated)).toEqual([])
    expect(unrelated.size).toBe(0)
  })

  it('no failure built by hand for RetryButton outside the allowlist', () => {
    expect(unpinned(foundHandBuilt, ALLOW_HAND_BUILT_FAILURE), RETRY_GATE_MESSAGE).toEqual([])
  })

  it.each(Object.keys(ALLOW_HAND_BUILT_FAILURE))('%s still has its pinned failure built by hand (remove the pins of converted ones)', (file) => {
    const actual = (foundHandBuilt.get(file) ?? []).map((site) => site.expr).sort()
    expect(actual).toEqual([...ALLOW_HAND_BUILT_FAILURE[file].sites].sort())
  })

  it('no hand-rolled Retry outside the allowlist, by its wiring', () => {
    expect(unpinned(foundRetry, ALLOW_RETRY), RETRY_GATE_MESSAGE).toEqual([])
  })

  it('no hand-rolled Retry outside the allowlist, by its label', () => {
    expect(unpinned(foundRetryLabel, ALLOW_RETRY_LABEL), RETRY_GATE_MESSAGE).toEqual([])
  })

  it('the three allowlists are shrink-only, and every entry has a reason', () => {
    const pinned = (allow: Record<string, { sites: string[] }>) =>
      Object.values(allow).reduce((sum, { sites }) => sum + sites.length, 0)
    expect(Object.keys(ALLOW_RETRY).length).toBeLessThanOrEqual(MAX_RETRY_ALLOWLIST_SIZE)
    expect(pinned(ALLOW_RETRY)).toBeLessThanOrEqual(MAX_RETRY_PINNED_SITES)
    expect(Object.keys(ALLOW_RETRY_LABEL).length).toBeLessThanOrEqual(MAX_RETRY_LABEL_ALLOWLIST_SIZE)
    expect(pinned(ALLOW_RETRY_LABEL)).toBeLessThanOrEqual(MAX_RETRY_LABEL_PINNED_SITES)
    expect(Object.keys(ALLOW_HAND_BUILT_FAILURE).length).toBeLessThanOrEqual(MAX_HAND_BUILT_FAILURE_FILES)
    expect(pinned(ALLOW_HAND_BUILT_FAILURE)).toBeLessThanOrEqual(MAX_HAND_BUILT_FAILURE_SITES)
    for (const [file, { reason }] of [
      ...Object.entries(ALLOW_RETRY),
      ...Object.entries(ALLOW_RETRY_LABEL),
      ...Object.entries(ALLOW_HAND_BUILT_FAILURE),
    ]) {
      expect(reason.trim().length, `${file} needs a reason`).toBeGreaterThan(0)
    }
  })

  it.each(Object.keys(ALLOW_RETRY))('%s still has every pinned Retry wiring (remove the pins of converted ones)', (file) => {
    const actual = (foundRetry.get(file) ?? []).map((site) => site.expr).sort()
    expect(actual).toEqual([...ALLOW_RETRY[file].sites].sort())
  })

  it.each(Object.keys(ALLOW_RETRY_LABEL))('%s still has every pinned Retry label (remove the pins of converted ones)', (file) => {
    const actual = (foundRetryLabel.get(file) ?? []).map((site) => site.expr).sort()
    expect(actual).toEqual([...ALLOW_RETRY_LABEL[file].sites].sort())
  })
})
