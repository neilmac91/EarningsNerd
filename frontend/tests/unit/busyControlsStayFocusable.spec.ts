import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
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
 * retries; the same binding resolver) and by what the user reads (a busy loadingText, "Retrying…" or "Trying
 * again…", a label starting Retry or Try again, a same-file string const included). Each has its own
 * shrink-only, capped allowlist with reasons: ALLOW_RETRY and ALLOW_RETRY_LABEL. RetryButton's own definition is
 * the one exemption from both Retry clauses (it is the sanctioned wiring and label); the busy-disabled clause
 * still scans it. Every Retry converted in the retry-hardening follow-up fails both at its pre-conversion version
 * (026d6df). A third clause holds what RetryButton is given: each of its `failures` is `useRetainedFailure(…)`'s
 * (in this file, or in the module of a hook it was destructured from), or a failure built by hand that
 * ALLOW_HAND_BUILT_FAILURE pins (a stream restart, which has no query to hold).
 *
 * A third gate holds the one retry verb (D-032), "Try again", busy "Trying again…": a RetryButton call site
 * passes no label, and RetryButtonProps declares each label prop `never` (neverProps), every retry control
 * (RetryButton's own definition included, with no exemption) reads exactly the one verb, and no copy says
 * "retry" (oneVerbSites and retryWordSites, with ALLOW_RETRY_WORD).
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

/** Equal to the files and to the pinned sites: lower each in the commit that converts a site, never raise it. */
const MAX_ALLOWLIST_SIZE = 5
const MAX_PINNED_SITES = 9

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const ROOTS = ['app', 'components', 'features', 'hooks', 'lib']

function walk(dir: string, out: string[], file = /\.tsx$/): string[] {
  for (const name of readdirSync(dir)) {
    const p = path.join(dir, name)
    if (statSync(p).isDirectory()) walk(p, out, file)
    else if (file.test(p)) out.push(p)
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
        // An options key such as useQuery({ retry: false }) is not an invoked retry handler.
        // Keep shorthand properties and property reads: they still refer to the bound value.
        if (ts.isPropertyAssignment(n.parent) && n.parent.name === n) return
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
 * other than `<RetryButton>` whose `loadingText` starts with "Retrying" or "Trying again", or whose own label
 * starts with "Retry" or "Try again". The label is the element's text children and string-literal children (each
 * branch of a `cond ? 'a' : 'b'` child counts on its own), whitespace collapsed, or a `children` attribute read
 * the same way; a nested element's text is that element's own label. `expr` is `Tag "label"`, which
 * ALLOW_RETRY_LABEL pins.
 */
const RETRY_LABEL = /^(retry|try again)\b/i
const RETRY_LOADING_TEXT = /^(Retrying|Trying again)/
/** The attributes that carry a button's busy text: the one it shows, and the one whose room it keeps at rest. */
const BUSY_TEXT_ATTRS = new Set(['loadingText', 'reserveLoadingText'])
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
        if (!ts.isJsxAttribute(attr) || !attr.initializer) continue
        const name = attr.name.getText(sf)
        // A `children` attribute is the element's label, as its text children are.
        if (!BUSY_TEXT_ATTRS.has(name) && name !== 'children') continue
        const value = ts.isStringLiteral(attr.initializer)
          ? [attr.initializer.text]
          : attr.initializer.expression ? literals(attr.initializer.expression) : []
        labels.push(...value.map(collapse).filter((text) => (name === 'children' ? RETRY_LABEL : RETRY_LOADING_TEXT).test(text)))
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
 * The one retry verb (docs/brand/decisions-log.md D-032): the product says "Try again" for the act and
 * "Trying again…" (U+2026) while it runs. Two clauses hold it.
 *
 * oneVerbSites, on controls. A RetryButton call site passes no label of its own: the label is RetryButton's, so the
 * verb has one source. Any child (text, an expression, an element; whitespace and a `{/* comment *\/}` aside), a
 * `children`, `aria-label` or `aria-labelledby` attribute, or a JSX spread (whose props the scan cannot read) fails.
 * RetryButton is matched by its own name and by every name an import of its module gives it (`{ RetryButton as Again
 * }`, a default import, `H.RetryButton` under `import * as H`); any other use of it fails as a form whose label the
 * scan cannot read: the name anywhere but a JSX tag, an import or a type (an alias, a prop, a createElement
 * argument, an export of it), an `export *` of its module or an `import()` of it. This clause is the third of three
 * holds on the label: RetryButtonProps declares the three label props `never`, so TypeScript refuses each at a call
 * site, and RetryButton drops each at run time, for one a spread or a cast brings in. Every other element is a retry
 * control when its label (its text, or a `children` attribute), its aria-label or its busy text reads as one
 * (RETRY_LABEL, any text that starts "Retry", or a busy text that starts "Retrying" or "Trying again"), a template's
 * text before its first substitution included (an icon-only Button's ``aria-label={`Try again for ${name}`}``),
 * RetryButton's own definition included: each label it can show is exactly "Try again" (or "Trying again…", a busy
 * branch), its busy text exactly "Trying again…", its aria-label exactly "Try again", and any of them that starts
 * "Retry" fails whatever follows. The label is read as the label scan reads it (text children, string children, each
 * branch of a conditional apart), plus `&&`'s rendered side alone, a `||` or `??` both sides and a same-file
 * `const`; a part of a retry control it cannot read (a parameter, a `let`, a call, a member, a template with a
 * substitution, an aria-labelledby, whose name is another element's text) fails as unread instead of passing. Its
 * limit: a label split across elements (`Try <b>again</b>`) is read per element; a control no text marks as a retry
 * (a "Reload" wired to a refetch) is the wiring clause's and the label pins' to see; and the text an aria-labelledby
 * points to is read only by the copy clause, which fails a "retry" in it.
 *
 * retryWordSites, on copy: no string literal, template text or JSX text in any .ts or .tsx under the scanned roots
 * says "retry", "retrying", "retries" or "retried", in any case: a description beside the control says "try again"
 * too, and a status line "Trying again…". Code is not copy: a console call's arguments, an import or export
 * specifier, an object key, a string type, a code attribute (CODE_ATTRS) and the header name Retry-After are
 * skipped. ALLOW_RETRY_WORD pins, with a reason, the code strings that carry the word (backend tokens the app
 * matches and never shows). Text the server sends at run time (a 503's detail) is outside any source scan. Its
 * limit, planted as a gap in the self-check: a word split across JSX text and an expression (`Please re{''}try`) is
 * read a part at a time, so neither clause sees it (the one-verb clause joins the parts, but prose like this does
 * not start with the verb); review catches it.
 */
const ONE_VERB = 'Try again'
const ONE_BUSY_TEXT = 'Trying again…'
const STARTS_RETRY = /^retry/i
const RETRY_BUSY_TEXT = /^(retrying|trying again)/i
const LABEL_ATTRS = new Set(['children', 'aria-label', 'aria-labelledby'])

/**
 * The texts an expression can render, a same-file const followed, and the parts the scan cannot read; for a template
 * with a substitution, which it cannot read, also the text before the first substitution (its head), so a label
 * such as `Try again for ${name}` still marks its control a retry.
 */
type Read = { texts: string[]; unread: string[]; heads: string[] }
function readTexts(e: ts.Expression, visible: (ref: ts.Identifier) => Binding | undefined, seen = new Set<Binding>()): Read {
  const none: Read = { texts: [], unread: [], heads: [] }
  if (ts.isStringLiteralLike(e)) return { ...none, texts: [e.text] }
  if (ts.isNumericLiteral(e)) return { ...none, texts: [e.text] }
  if (e.kind === ts.SyntaxKind.NullKeyword || e.kind === ts.SyntaxKind.TrueKeyword || e.kind === ts.SyntaxKind.FalseKeyword) return none
  if (ts.isParenthesizedExpression(e)) return readTexts(e.expression, visible, seen)
  const both = (a: ts.Expression, b: ts.Expression): Read => {
    const left = readTexts(a, visible, seen)
    const right = readTexts(b, visible, seen)
    return { texts: [...left.texts, ...right.texts], unread: [...left.unread, ...right.unread], heads: [...left.heads, ...right.heads] }
  }
  if (ts.isConditionalExpression(e)) return both(e.whenTrue, e.whenFalse)
  if (ts.isBinaryExpression(e)) {
    const op = e.operatorToken.kind
    // `cond && 'text'` renders its right side or nothing a reader sees.
    if (op === ts.SyntaxKind.AmpersandAmpersandToken) return readTexts(e.right, visible, seen)
    if (op === ts.SyntaxKind.BarBarToken || op === ts.SyntaxKind.QuestionQuestionToken) return both(e.left, e.right)
  }
  if (ts.isIdentifier(e)) {
    if (e.text === 'undefined') return none
    const binding = visible(e)
    const isConst =
      !!binding && ts.isVariableDeclaration(binding.decl) && (ts.getCombinedNodeFlags(binding.decl) & ts.NodeFlags.Const) !== 0
    if (binding?.init && isConst && !seen.has(binding)) return readTexts(binding.init, visible, new Set([...seen, binding]))
  }
  const unread = [e.getText().replace(/\s+/g, ' ')]
  return ts.isTemplateExpression(e) ? { ...none, unread, heads: [e.head.text] } : { ...none, unread }
}

function oneVerbSites(source: string, fileName: string): Site[] {
  const sf = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const visible = bindingResolver(sf)
  const retryNames = retryButtonNames(sf, fileName)
  const isHome = (specifier: ts.Node | undefined) =>
    !!specifier && ts.isStringLiteralLike(specifier) && withoutExtension(resolveModule(fileName, specifier.text)) === withoutExtension(RETRY_BUTTON.file)
  const collapse = (text: string) => text.replace(/\s+/g, ' ').trim()
  const lineOf = (node: ts.Node) => sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
  const sites: Site[] = []
  /** A name in a place that renders nothing: an import, a declaration's own name, a type, a member's name. */
  const inert = (node: ts.Node): boolean => {
    const parent = node.parent
    if (ts.isImportSpecifier(parent) || ts.isImportClause(parent) || ts.isNamespaceImport(parent)) return true
    if ('name' in parent && (parent as { name?: ts.Node }).name === node && !ts.isShorthandPropertyAssignment(parent) && !ts.isExportSpecifier(parent)) return true
    for (let up: ts.Node | undefined = parent; up; up = up.parent) if (ts.isTypeNode(up)) return true
    return false
  }
  const isTag = (node: ts.Node) =>
    (ts.isJsxOpeningElement(node.parent) || ts.isJsxSelfClosingElement(node.parent) || ts.isJsxClosingElement(node.parent)) && node.parent.tagName === node
  const visit = (node: ts.Node): void => {
    // `export * from` its module, or `export * as`, hands RetryButton on under a name no import of its module
    // gives it; an `import()` of its module (next/dynamic's) loads it under one.
    if (ts.isExportDeclaration(node) && isHome(node.moduleSpecifier) && (!node.exportClause || ts.isNamespaceExport(node.exportClause))) {
      sites.push({ line: lineOf(node), expr: `${collapse(node.getText(sf))}: re-exports RetryButton under a name the scan cannot follow` })
    }
    if (ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword && isHome(node.arguments[0])) {
      sites.push({ line: lineOf(node), expr: `${collapse(node.getText(sf))}: loads RetryButton under a name the scan cannot follow` })
    }
    // RetryButton named as a value, not a tag (an alias, a prop, a createElement argument, an export): its label
    // is then set where the scan cannot read it.
    if ((ts.isIdentifier(node) || ts.isPropertyAccessExpression(node)) && retryNames.has(node.getText(sf)) && !isTag(node) && !inert(node)) {
      sites.push({ line: lineOf(node), expr: `${node.getText(sf)} used other than as a JSX tag: a label the scan cannot read` })
    }
    if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) {
      const opening = ts.isJsxElement(node) ? node.openingElement : node
      const tag = opening.tagName.getText(sf)
      const at = lineOf(node)
      const flag = (what: string) => sites.push({ line: at, expr: `${tag} ${what}` })
      const children = ts.isJsxElement(node) ? node.children : ts.factory.createNodeArray<ts.JsxChild>()
      if (retryNames.has(tag)) {
        for (const attr of opening.attributes.properties) {
          if (ts.isJsxSpreadAttribute(attr)) flag(`${attr.getText(sf)}: a spread whose label the scan cannot read`)
          else if (LABEL_ATTRS.has(attr.name.getText(sf))) flag(`${collapse(attr.getText(sf))}: a label of its own`)
        }
        for (const child of children) {
          if (ts.isJsxText(child) ? collapse(child.text) === '' : ts.isJsxExpression(child) && !child.expression) continue
          flag(`"${collapse(child.getText(sf))}": a label of its own`)
        }
      } else {
        const labels: string[] = []
        const busy: string[] = []
        const aria: string[] = []
        const unread: string[] = []
        // The heads of templates it cannot read: they tell a retry control, never pass as its words.
        const heads: string[] = []
        const busyHeads: string[] = []
        let text = ''
        for (const child of children) {
          if (ts.isJsxText(child)) text += child.text
          else if (ts.isJsxExpression(child) && child.expression) {
            const read = readTexts(child.expression, visible)
            unread.push(...read.unread.map((part) => `{${part}}`))
            heads.push(...read.heads.map(collapse))
            if (read.texts.length === 1 && !read.unread.length) text += read.texts[0]
            else labels.push(...read.texts.map(collapse))
          }
        }
        if (collapse(text)) labels.unshift(collapse(text))
        for (const attr of opening.attributes.properties) {
          if (!ts.isJsxAttribute(attr) || !attr.initializer) continue
          const name = attr.name.getText(sf)
          // aria-labelledby names the control with another element's text, which the scan does not read here.
          if (name === 'aria-labelledby') {
            unread.push(collapse(attr.getText(sf)))
            continue
          }
          if (!BUSY_TEXT_ATTRS.has(name) && name !== 'aria-label' && name !== 'children') continue
          const read: Read = ts.isStringLiteral(attr.initializer)
            ? { texts: [attr.initializer.text], unread: [], heads: [] }
            : attr.initializer.expression ? readTexts(attr.initializer.expression, visible) : { texts: [], unread: [], heads: [] }
          ;(BUSY_TEXT_ATTRS.has(name) ? busy : name === 'children' ? labels : aria).push(...read.texts.map(collapse))
          ;(BUSY_TEXT_ATTRS.has(name) ? busyHeads : heads).push(...read.heads.map(collapse))
          unread.push(...read.unread.map((part) => `${name}={${part}}`))
        }
        const isRetry =
          [...labels, ...aria, ...heads].some((t) => RETRY_LABEL.test(t) || STARTS_RETRY.test(t)) ||
          [...busy, ...busyHeads].some((t) => RETRY_BUSY_TEXT.test(t))
        if (isRetry) {
          for (const label of labels) {
            // A label branch shown while busy is held to the busy form, any other to the verb.
            const want = RETRY_BUSY_TEXT.test(label) ? ONE_BUSY_TEXT : ONE_VERB
            if (label !== want) flag(`label "${label}" is not "${want}"`)
          }
          for (const t of busy) if (t !== ONE_BUSY_TEXT) flag(`busy text "${t}" is not "${ONE_BUSY_TEXT}"`)
          for (const t of aria) if (t !== ONE_VERB) flag(`aria-label "${t}" is not "${ONE_VERB}"`)
          for (const part of unread) flag(`text it cannot read: ${part}`)
        }
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return sites
}

/**
 * RetryButton's own label and busy texts, read from its definition: the element inside it that renders them, its
 * label, the busy text it shows (`loadingText`) and the busy text whose room it keeps at rest (`reserveLoadingText`).
 */
function retryButtonOwnText(source: string): { labels: string[]; loadingText: string[]; reserveLoadingText: string[] }[] {
  const sf = ts.createSourceFile(RETRY_BUTTON.file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const visible = bindingResolver(sf)
  const definition = sf.statements.find((s) => ts.isFunctionDeclaration(s) && s.name?.text === RETRY_BUTTON.name)
  const out: { labels: string[]; loadingText: string[]; reserveLoadingText: string[] }[] = []
  const visit = (node: ts.Node): void => {
    if (ts.isJsxElement(node)) {
      const texts = (name: string): string[] => {
        const attr = node.openingElement.attributes.properties.find(
          (a): a is ts.JsxAttribute => ts.isJsxAttribute(a) && a.name.getText(sf) === name,
        )
        if (!attr?.initializer) return []
        if (ts.isStringLiteral(attr.initializer)) return [attr.initializer.text]
        return attr.initializer.expression ? readTexts(attr.initializer.expression, visible).texts : []
      }
      const labels = node.children.filter(ts.isJsxText).map((child) => child.text.replace(/\s+/g, ' ').trim()).filter(Boolean)
      out.push({ labels, loadingText: texts('loadingText'), reserveLoadingText: texts('reserveLoadingText') })
    }
    ts.forEachChild(node, visit)
  }
  if (definition) visit(definition)
  return out
}

/**
 * The props RetryButtonProps declares `never`, read from its definition: the ones TypeScript refuses at a call
 * site. Leaving a name out of the props would not do for a hyphenated one: JSX never checks an undeclared
 * attribute such as aria-label against the props.
 */
function neverProps(source: string): string[] {
  const sf = ts.createSourceFile(RETRY_BUTTON.file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const props = sf.statements.find((s): s is ts.InterfaceDeclaration => ts.isInterfaceDeclaration(s) && s.name.text === `${RETRY_BUTTON.name}Props`)
  return (props?.members ?? []).flatMap((member) =>
    ts.isPropertySignature(member) && member.type?.kind === ts.SyntaxKind.NeverKeyword && (ts.isIdentifier(member.name) || ts.isStringLiteral(member.name))
      ? [member.name.text]
      : [],
  )
}

/** Attributes whose string is code, not copy: what the word scan skips. */
const CODE_ATTRS = new Set(['className', 'class', 'id', 'key', 'href', 'src', 'type', 'role', 'name', 'htmlFor', 'rel', 'target', 'variant', 'size', 'as'])
const RETRY_WORD = /\bretr(?:y|ying|ies|ied)\b(?!-after)/i

function retryWordSites(source: string, fileName: string): Site[] {
  const kind = fileName.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS
  const sf = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, kind)
  const sites: Site[] = []
  const isCode = (node: ts.Node): boolean => {
    const parent = node.parent
    if (!parent) return false
    if ('name' in parent && (parent as { name?: ts.Node }).name === node) return true // an object key, a member name
    if (ts.isLiteralTypeNode(parent)) return true
    // An attribute's value, written bare or inside `{…}` (a conditional's branch, a fallback), is its attribute's.
    let at: ts.Node = node
    while (
      at.parent &&
      (ts.isJsxExpression(at.parent) || ts.isParenthesizedExpression(at.parent) || ts.isConditionalExpression(at.parent) || ts.isBinaryExpression(at.parent))
    ) {
      at = at.parent
    }
    if (at.parent && ts.isJsxAttribute(at.parent)) {
      const name = at.parent.name.getText(sf)
      return CODE_ATTRS.has(name) || name.startsWith('data-')
    }
    return false
  }
  const visit = (node: ts.Node): void => {
    if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) return
    if (
      ts.isCallExpression(node) &&
      (node.expression.kind === ts.SyntaxKind.ImportKeyword ||
        (ts.isPropertyAccessExpression(node.expression) && ts.isIdentifier(node.expression.expression) && node.expression.expression.text === 'console'))
    ) {
      return
    }
    const text = ts.isJsxText(node)
      ? node.text
      : ts.isStringLiteralLike(node) || ts.isTemplateHead(node) || ts.isTemplateMiddle(node) || ts.isTemplateTail(node)
        ? node.text
        : null
    if (text !== null && RETRY_WORD.test(text) && !isCode(node)) {
      const { line } = sf.getLineAndCharacterOfPosition(node.getStart(sf))
      sites.push({ line: line + 1, expr: `"${text.replace(/\s+/g, ' ').trim()}"` })
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return sites
}

/**
 * What RetryButton is given: each element of its `failures={[…]}` is the query's retained failure,
 * `useRetainedFailure(query, queryKey)`, written inline, held by a same-file `const`, or as either branch of a
 * conditional. The hook is the one its module exports, under whatever name an import of hooks/useRetainedFailure
 * gives it: a same-named local (a lookalike, or a parameter shadowing the import) is a call of anything else. Anything else is a failure built by hand, `{ failed, error, busy, retry }`: it skips the hold
 * (a refetch nobody pressed swaps the card, and its focused Retry, for a skeleton), and its `busy` can be
 * `isFetching`, the bug the wiring clause catches on `loading`. What the scan cannot prove counts as built by
 * hand too: a `failures` that is not an array literal, an empty one (a visible Retry whose press retries
 * nothing), a spread element, a call of anything else, a `let` or
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
 *
 * A failure destructured from what a hook in another module returns (ComparePeriodsCard's `const { failure } =
 * useWhatChanged(id)`, renamed or not) is followed into that module: the hook is a named import here (under any
 * alias, with no local binding shadowing it), its module is read from disk (`.ts`, then `.tsx`, under the
 * frontend root), and the export of that name is a function (declared, or a const arrow or function expression)
 * whose every own `return` is an object literal giving the property a value retained there by these same rules,
 * so one hook may hand on another's (a cycle stops). Anything else counts as built by hand: a default value
 * (`{ failure = x }`), a rest or nested pattern, a `let`, a member read (`thing.failure`), a default import, a
 * module the scan cannot read, a bare `return`, a return that is not an object literal, or a property missing
 * from one return.
 */
const RETAINED_FAILURE = 'useRetainedFailure'
interface FailureProp { component: string; prop: string; line: number; isDefault: boolean }

/** A module's file and source by its root-relative path without extension; null when the scan cannot read it. */
type ModuleSource = (module: string) => { file: string; source: string } | null
const MODULE_EXTENSIONS = ['.ts', '.tsx']
/** The one file the import names; null when none or more than one exists (two files for one import: not proven). */
const moduleFile = (module: string, has: (file: string) => boolean): string | null => {
  const found = MODULE_EXTENSIONS.map((ext) => `${module}${ext}`).filter(has)
  return found.length === 1 ? found[0] : null
}
const diskModules = new Map<string, { file: string; source: string } | null>()
/** Modules under the frontend root, read once from disk. */
const diskModule: ModuleSource = (module) => {
  if (!diskModules.has(module)) {
    const file = moduleFile(module, (candidate) => existsSync(path.join(frontendRoot, candidate)))
    diskModules.set(module, file ? { file, source: readFileSync(path.join(frontendRoot, file), 'utf8') } : null)
  }
  return diskModules.get(module) ?? null
}
/** Modules a self-test supplies, keyed by file (`features/x/useThing.ts`). */
const mappedModules =
  (sources: Map<string, string>): ModuleSource =>
  (module) => {
    const file = moduleFile(module, (candidate) => sources.has(candidate))
    return file ? { file, source: sources.get(file) as string } : null
  }

/** The named import binding `local` in this file: the module it resolves to and the name exported there. */
function namedImport(sf: ts.SourceFile, fileName: string, local: string): { module: string; exported: string } | null {
  for (const statement of sf.statements) {
    if (!ts.isImportDeclaration(statement) || !ts.isStringLiteral(statement.moduleSpecifier)) continue
    const named = statement.importClause?.namedBindings
    if (!named || !ts.isNamedImports(named)) continue
    for (const el of named.elements) {
      if (el.name.text === local) return { module: resolveModule(fileName, statement.moduleSpecifier.text), exported: (el.propertyName ?? el.name).text }
    }
  }
  return null
}

/** The function a module exports under `name`: a declaration, or a const bound to an arrow or function expression. */
function exportedFunction(sf: ts.SourceFile, name: string): ts.FunctionLikeDeclaration | null {
  const isExported = (st: ts.Statement) => !!ts.getModifiers(st)?.some((m) => m.kind === ts.SyntaxKind.ExportKeyword)
  for (const st of sf.statements) {
    if (!isExported(st)) continue
    if (ts.isFunctionDeclaration(st) && st.name?.text === name && st.body) return st
    if (!ts.isVariableStatement(st)) continue
    for (const decl of st.declarationList.declarations) {
      if (!ts.isIdentifier(decl.name) || decl.name.text !== name || !decl.initializer) continue
      if ((ts.getCombinedNodeFlags(decl) & ts.NodeFlags.Const) === 0) return null
      return ts.isArrowFunction(decl.initializer) || ts.isFunctionExpression(decl.initializer) ? decl.initializer : null
    }
  }
  return null
}

/** A function's own returns (an expression body is one); null when one is bare, or a nested function's are the only ones. */
function ownReturns(fn: ts.FunctionLikeDeclaration): ts.Expression[] | null {
  if (!fn.body) return null
  if (!ts.isBlock(fn.body)) return [fn.body]
  const out: ts.Expression[] = []
  let bare = false
  const visit = (node: ts.Node): void => {
    if (ts.isReturnStatement(node)) {
      if (node.expression) out.push(node.expression)
      else bare = true
      return
    }
    if (ts.isFunctionLike(node) || ts.isClassLike(node)) return
    ts.forEachChild(node, visit)
  }
  visit(fn.body)
  return bare || !out.length ? null : out
}

/**
 * Whether an expression is a retained failure, resolved in its own file; `modules` reads the module of a hook
 * it was destructured from, and `hooks` the hooks already being followed (a cycle is not retained).
 */
function retainedIn(sf: ts.SourceFile, fileName: string, modules: ModuleSource = diskModule, hooks = new Set<string>()): (e: ts.Expression) => boolean {
  const visible = bindingResolver(sf)
  const isConst = (binding: Binding) =>
    ts.isVariableDeclaration(binding.decl) && (ts.getCombinedNodeFlags(binding.decl) & ts.NodeFlags.Const) !== 0
  const unparen = (e: ts.Expression): ts.Expression => (ts.isParenthesizedExpression(e) ? unparen(e.expression) : e)
  /** `const { failure } = useX(…)`, `failure` renamed or not: the property of what the hook returns, proven in its module. */
  const fromHook = (binding: Binding): boolean => {
    const decl = binding.decl
    if (!ts.isBindingElement(decl) || decl.initializer || decl.dotDotDotToken || !ts.isObjectBindingPattern(decl.parent)) return false
    const variable = decl.parent.parent
    if (!ts.isVariableDeclaration(variable) || variable.name !== decl.parent || !variable.initializer) return false
    if ((ts.getCombinedNodeFlags(variable) & ts.NodeFlags.Const) === 0) return false
    const call = unparen(variable.initializer)
    if (!ts.isCallExpression(call) || !ts.isIdentifier(call.expression) || visible(call.expression)) return false
    const property = decl.propertyName ?? decl.name
    if (!ts.isIdentifier(property)) return false
    const target = namedImport(sf, fileName, call.expression.text)
    if (!target) return false
    const id = `${target.module}:${target.exported}`
    const found = hooks.has(id) ? null : modules(target.module)
    if (!found) return false
    const hookSf = ts.createSourceFile(found.file, found.source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
    const fn = exportedFunction(hookSf, target.exported)
    const returns = fn ? ownReturns(fn) : null
    if (!returns) return false
    const retainedThere = retainedIn(hookSf, found.file, modules, new Set([...hooks, id]))
    return returns.every((value) => {
      const literal = unparen(value)
      if (!ts.isObjectLiteralExpression(literal)) return false
      // A spread can carry the same property name from anywhere, after the one named here.
      if (literal.properties.some(ts.isSpreadAssignment)) return false
      const member = literal.properties.find(
        (p) => (ts.isPropertyAssignment(p) || ts.isShorthandPropertyAssignment(p)) && ts.isIdentifier(p.name) && p.name.text === property.text,
      )
      if (!member) return false
      return retainedThere(ts.isPropertyAssignment(member) ? member.initializer : (member as ts.ShorthandPropertyAssignment).name)
    })
  }
  // The hook as this file names it: what an import of its module binds (an alias included) with no local
  // binding shadowing that name, or, in the module itself, its own top-level declaration.
  const home = withoutExtension(RETRY_BUTTON.file)
  const ownModule = withoutExtension(fileName) === home
  const imported = new Set(importedNames(sf, fileName, (m) => withoutExtension(m) === home, RETAINED_FAILURE, false))
  const isHook = (callee: ts.Expression): boolean => {
    if (!ts.isIdentifier(callee)) return false
    const local = visible(callee)
    if (ownModule) return callee.text === RETAINED_FAILURE && !!local && ts.isFunctionDeclaration(local.decl) && local.decl.parent === sf
    return imported.has(callee.text) && !local
  }
  const retained = (e: ts.Expression, seen = new Set<Binding>()): boolean => {
    if (ts.isParenthesizedExpression(e)) return retained(e.expression, seen)
    if (ts.isConditionalExpression(e)) return retained(e.whenTrue, seen) && retained(e.whenFalse, seen)
    if (ts.isCallExpression(e)) return isHook(e.expression)
    if (ts.isIdentifier(e)) {
      const binding = visible(e)
      if (!binding || seen.has(binding)) return false
      if (binding.init) return isConst(binding) && retained(binding.init, new Set([...seen, binding]))
      return fromHook(binding)
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

/**
 * RetryButton's tag names in this file, for the one-verb and failures clauses: its own; any name an import of its
 * module gives it (`{ RetryButton as Again }`, and a default import: the module has none today, so TypeScript
 * refuses one, and one it gains later is read as RetryButton until this says otherwise); and `H.RetryButton` for
 * a namespace import of its module (`import * as H`). Any other way to reach it (an alias, a prop, a
 * createElement argument, a re-export, an `import()`) fails the one-verb clause as a form the scan cannot read.
 */
function retryButtonNames(sf: ts.SourceFile, fileName: string): Set<string> {
  const home = withoutExtension(RETRY_BUTTON.file)
  const fromHome = (m: string) => withoutExtension(m) === home
  const names = new Set([RETRY_BUTTON.name, ...importedNames(sf, fileName, fromHome, RETRY_BUTTON.name, true)])
  for (const statement of sf.statements) {
    if (!ts.isImportDeclaration(statement) || !ts.isStringLiteral(statement.moduleSpecifier)) continue
    if (!fromHome(resolveModule(fileName, statement.moduleSpecifier.text))) continue
    const bindings = statement.importClause?.namedBindings
    if (bindings && ts.isNamespaceImport(bindings)) names.add(`${bindings.name.text}.${RETRY_BUTTON.name}`)
  }
  return names
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
function failureScan(source: string, fileName: string, modules: ModuleSource = diskModule): { handBuilt: Site[]; props: FailureProp[] } {
  const sf = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const retained = retainedIn(sf, fileName, modules)
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
        else if (value.elements.length === 0) flag(value)
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
  const retained = retainedIn(sf, fileName)
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
      'leaves with the press when the run starts (a signed-out press starts none: the card stays with a sign-in ' +
      'sentence no retry can help, so the Retry leaves); RetryButton is there for the hand-off to the progress ' +
      "heading, or to the card's own heading when the card stays (EN-05).",
  },
}
const MAX_HAND_BUILT_FAILURE_FILES = 1
const MAX_HAND_BUILT_FAILURE_SITES = 1

/** Open rule (h) cases, pinned by exact expression. Shrink-only: converting one to RetryButton removes its pin. */
const ALLOW_RETRY: Record<string, { sites: string[]; reason: string }> = {
  'app/company/[ticker]/page-client.tsx': {
    sites: ['filingsRefetching'],
    reason:
      "Show full history: its loading is the filings query's fetching flag (a background refetch of the default " +
      'list; activating the button unmounts it), and it is not a Retry. Its focus through that refetch and its ' +
      'hand-off to the "SEC filings" heading are pinned in busyControls.watchlist.spec.tsx.',
  },
}
const MAX_RETRY_ALLOWLIST_SIZE = 1
const MAX_RETRY_PINNED_SITES = 1

/**
 * Every element the label scan sees that is not a RetryButton, pinned by `Tag "label"`, with a reason.
 * Shrink-only, and its two caps are equalities (lessons/test-allowlist-caps-are-equalities.md): converting
 * one to RetryButton removes its pin and lowers both caps in the same commit, and a new one fails.
 */
const ERROR_BOUNDARY_RESET =
  "A React error boundary's reset: it re-renders the crashed subtree, with no query to hold a failure for or to " +
  'retry, and nothing it refetches can swap it for a skeleton.'
const STREAM_RESTART =
  'Restarts a streamed generation or answer (SSE), not a query refetch, so there is no query to hold. Not yet ' +
  "converted: converting one makes it RetryButton with a failure built by hand, as the filing page's generation " +
  'restart is, moving its pin (and one from each cap) from this list to ALLOW_HAND_BUILT_FAILURE. '
const ALLOW_RETRY_LABEL: Record<string, { sites: string[]; reason: string }> = {
  'app/error.tsx': { sites: ['Button "Try again"'], reason: ERROR_BOUNDARY_RESET },
  'app/global-error.tsx': { sites: ['button "Try again"'], reason: ERROR_BOUNDARY_RESET },
  'app/dashboard/error.tsx': { sites: ['Button "Try again"'], reason: ERROR_BOUNDARY_RESET },
  'components/GlobalErrorBoundary.tsx': { sites: ['Button "Try again"'], reason: ERROR_BOUNDARY_RESET },
  'features/summaries/components/SummaryDisplay.tsx': {
    sites: ['Button "Try again"'],
    reason: STREAM_RESTART + "The filing page's summary Retry regenerates it; open in rule (h).",
  },
  'features/filings/components/copilot/CopilotMessage.tsx': {
    sites: ['Button "Try again"'],
    reason: STREAM_RESTART + 'Re-asks a copilot question whose answer stream failed.',
  },
}
const MAX_RETRY_LABEL_ALLOWLIST_SIZE = 6
const MAX_RETRY_LABEL_PINNED_SITES = 6

/**
 * Code strings that carry the old verb, pinned by their text with a reason: tokens the app matches against what
 * the server stores and never shows. Shrink-only, and its two caps are equalities
 * (lessons/test-allowlist-caps-are-equalities.md); a string a reader can see is never pinned here.
 */
const ALLOW_RETRY_WORD: Record<string, { sites: string[]; reason: string }> = {
  'lib/formatters.ts': {
    sites: ['"retry"'],
    reason:
      "PLACEHOLDER_PATTERNS mirrors the backend's summary_sections.PLACEHOLDER_PATTERNS: a substring isPlaceholderText " +
      'matches to hide filler text from the page, never text the page shows.',
  },
  'features/summaries/lib/summaryPlaceholder.ts': {
    sites: ['"Summary temporarily unavailable. Please retry."'],
    reason:
      "SUMMARY_FALLBACK_MESSAGE is the backend's stored failure body, matched as a failure token " +
      '(summaryPlaceholder.spec.ts holds the tokens equal to the backend\'s); the filing page shows its error card in ' +
      'its place, never this text.',
  },
}
const MAX_RETRY_WORD_FILES = 2
const MAX_RETRY_WORD_SITES = 2

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
const foundOneVerb = new Map<string, Site[]>()
const foundRetryWord = new Map<string, Site[]>()
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
  const verbs = oneVerbSites(source, rel)
  if (verbs.length) foundOneVerb.set(rel, verbs)
}
// The copy clause reads every .ts module too: a status line or a fallback sentence lives in an api or hook file.
const wordScanned: string[] = []
for (const abs of ROOTS.flatMap((root) => walk(path.join(frontendRoot, root), [], /\.tsx?$/))) {
  const rel = path.relative(frontendRoot, abs).split(path.sep).join('/')
  wordScanned.push(rel)
  const words = retryWordSites(readFileSync(abs, 'utf8'), rel)
  if (words.length) foundRetryWord.set(rel, words)
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
      `ALLOW has ${Object.keys(ALLOW).length} entries and MAX_ALLOWLIST_SIZE is ${MAX_ALLOWLIST_SIZE}. Fix the control instead of adding an entry; lower the cap with an entry that goes.`,
    ).toBe(MAX_ALLOWLIST_SIZE)
    // Files alone are not enough: a new exception appended to a listed file keeps the file count.
    const pinned = Object.values(ALLOW).reduce((sum, { sites }) => sum + sites.length, 0)
    expect(
      pinned,
      `ALLOW pins ${pinned} sites and MAX_PINNED_SITES is ${MAX_PINNED_SITES}. Fix the control instead of pinning it; lower the cap with a site that goes.`,
    ).toBe(MAX_PINNED_SITES)
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
  'failure held through any refetch, "Trying again…" only for its own press, and a focus hand-off when it unmounts ' +
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
    expect(retrySites([
      'function Viewer() {',
      '  const media = useQuery({ queryKey, queryFn, retry: false })',
      '  const download = () => downloadBlob(media.data)',
      '  return <>',
      '    <Button onClick={download}>Download</Button>',
      '    <Button onClick={() => media.refetch()}>Try again</Button>',
      '  </>',
      '}',
    ].join('\n'), 'fixture.tsx').map((site) => site.expr)).toEqual(['() => media.refetch()'])
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

  it('sees a Retry by its label or its busy text ("Retrying…" or "Trying again…") on anything but RetryButton, and nothing else', () => {
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
      '    <Button loading={busy} loadingText="Trying again…" onClick={go}>Load</Button>', // the one busy form, a Retry's too
      '    <Button loading={busy} reserveLoadingText="Trying again…" onClick={go}>Load</Button>', // its room kept at rest
      '    <Button onClick={go} children="Try again" />', // a children attribute is a label
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
      '19: Button "Trying again…"',
      '20: Button "Trying again…"',
      '21: Button "Try again"',
    ])
  })

  it("sees a failure built by hand in RetryButton's failures, and not the retained one, however it is held", () => {
    const fixture = [
      "import { RetryButton as Again, useRetainedFailure, type RetryButtonProps } from '@/hooks/useRetainedFailure'",
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

  it('takes useRetainedFailure only as the hook its module exports, under any imported name, and fails an empty list', () => {
    const lines = (scan: ReturnType<typeof failureScan>) => scan.handBuilt.map((site) => `${site.line}: ${site.expr}`)
    const aliased = [
      "import { RetryButton, useRetainedFailure as useHold } from '@/hooks/useRetainedFailure'",
      'export function A() {',
      '  const held = useHold(query, key)',
      '  return (<>',
      '    <RetryButton failures={[held]} focusTarget={ref} />', // the hook under an import alias: retained
      '    <RetryButton failures={[]} focusTarget={ref} />', // an empty list: a Retry whose press retries nothing
      '  </>)',
      '}',
      'export function B(useHold: () => RetainedFailure) {',
      '  return <RetryButton failures={[useHold()]} focusTarget={ref} />', // a parameter shadows the import
      '}',
    ].join('\n')
    expect(lines(failureScan(aliased, 'fixture.tsx'))).toEqual(['6: []', '10: useHold()'])
    const lookalike = [
      "import { RetryButton } from '@/hooks/useRetainedFailure'",
      'function useRetainedFailure() { return { failed: true, error: null, busy: false, retry: () => {} } }',
      'export const C = () => <RetryButton failures={[useRetainedFailure(q, k)]} focusTarget={ref} />', // a same-named local
    ].join('\n')
    expect(lines(failureScan(lookalike, 'fixture.tsx'))).toEqual(['3: useRetainedFailure(q, k)'])
    const unimported = "import { RetryButton } from '@/hooks/useRetainedFailure'\nexport const D = () => <RetryButton failures={[useRetainedFailure(q, k)]} focusTarget={ref} />"
    expect(lines(failureScan(unimported, 'fixture.tsx'))).toEqual(['2: useRetainedFailure(q, k)']) // never imported here
    const ownModule = [
      'export function useRetainedFailure(query: Q, key: K) { return hold(query, key) }',
      'export const E = () => <RetryButton failures={[useRetainedFailure(q, k)]} focusTarget={ref} />', // the hook's own module
    ].join('\n')
    expect(lines(failureScan(ownModule, 'hooks/useRetainedFailure.tsx'))).toEqual([])
  })

  it("follows a failure destructured from a hook in another module into that hook's returns, and nothing looser", () => {
    const modules = mappedModules(
      new Map([
        [
          'features/x/useThing.ts',
          [
            "import { useRetainedFailure } from '@/hooks/useRetainedFailure'",
            'export function useThing(id: number) {',
            '  const query = useQuery({ queryKey: key, queryFn })',
            '  const failure = useRetainedFailure(query, key)',
            '  const loose = { failed: q.isError, error: q.error, busy: q.isFetching, retry: q.refetch }',
            '  const inner = () => { return { failure: loose } }', // a nested function's return is not the hook's
            '  return { query, failure, held: (useRetainedFailure(query, key)), loose, inner }',
            '}',
            'export const useArrow = (id: number) => ({ failure: useRetainedFailure(useQuery({ queryKey: key, queryFn }), key) })',
            'export function useMixed(flag: boolean) {',
            '  const failure = useRetainedFailure(query, key)',
            '  if (flag) return { failure }',
            '  return { failure: { failed: true, error: null, busy: false, retry: () => {} } }', // one return built by hand
            '}',
            'export function useBare(flag: boolean) {',
            '  if (flag) return', // a bare return: nothing to read a property from
            '  return { failure: useRetainedFailure(query, key) }',
            '}',
            'export function useOther() { return useThing(1) }', // returns a call, not an object literal
            'export let useLet = () => ({ failure: useRetainedFailure(query, key) })', // a let: a later assignment can replace it
            'function useListed() { return { failure: useRetainedFailure(query, key) } }', // a declaration of that name, not exported
            'export { useLocal as useListed }', // an export list is not followed, whatever it is named
            'export function useSpread(extra: object) {',
            '  const failure = useRetainedFailure(query, key)',
            '  return { failure, ...extra }', // a spread after the property can carry a `failure` of its own
            '}',
          ].join('\n'),
        ],
        ['features/x/useTwin.ts', "import { useRetainedFailure } from '@/hooks/useRetainedFailure'\nexport function useTwin() { return { failure: useRetainedFailure(query, key) } }"],
        ['features/x/useTwin.tsx', "export function useTwin() { return { failure: { failed: true, error: null, busy: false, retry: () => {} } } }"], // two files for one import
        [
          'features/x/useChain.tsx',
          [
            "import { useThing } from './useThing'", // a relative import, resolved from the module's own folder
            'export function useChain(id: number) {',
            '  const { failure } = useThing(id)', // one hook hands on another's
            '  return { failure }',
            '}',
          ].join('\n'),
        ],
        ['features/x/useCycleA.ts', "import { useCycleB } from './useCycleB'\nexport function useCycleA() { const { failure } = useCycleB(); return { failure } }"],
        ['features/x/useCycleB.ts', "import { useCycleA } from './useCycleA'\nexport function useCycleB() { const { failure } = useCycleA(); return { failure } }"],
      ]),
    )
    const consumer = [
      "import { RetryButton } from '@/hooks/useRetainedFailure'",
      "import { useThing, useThing as useAlias, useArrow, useMixed, useBare, useOther, useLet, useListed, useSpread } from '@/features/x/useThing'",
      "import { useChain } from '@/features/x/useChain'",
      "import { useCycleA } from '@/features/x/useCycleA'",
      "import { useMissing } from '@/features/x/missing'",
      "import { useTwin } from '@/features/x/useTwin'",
      "import useDefault from '@/features/x/useThing'",
      'export function A() {',
      '  const { failure } = useThing(1)', // the hook's retained failure
      '  const { failure: renamed, held } = (useAlias(2))', // renamed, and the hook under an import alias
      '  const { failure: arrow } = useArrow(3)',
      '  const { failure: chained } = useChain(4)',
      '  const { loose } = useThing(5)', // the hook's own hand-built property
      '  const { failure: mixed } = useMixed(true)', // one of its returns is built by hand
      '  const { failure: bare } = useBare(true)',
      '  const { failure: other } = useOther()',
      '  const { failure: fromLet } = useLet()',
      '  const { failure: listed } = useListed()',
      '  const { failure: spread } = useSpread({})', // the literal spreads another object
      '  const { failure: twin } = useTwin()', // the module exists as .ts and .tsx
      '  const { failure: cyclic } = useCycleA()',
      '  const { failure: missing } = useMissing()', // a module the scan cannot read
      '  const { failure: viaDefault } = useDefault(6)', // a default import
      '  const { failure: defaulted = loose } = useThing(7)', // a default value
      '  const { thing: { failure: deep } } = useThing(8)', // a nested pattern
      '  const { ...rest } = useThing(9)', // a rest element
      '  const { ...failure2 } = useThing(12)', // a rest element named like the property is still the rest
      '  const [failure3] = useThing(13)', // an array pattern
      '  let { failure: mutable } = useThing(10)', // a let
      '  const whole = useThing(11)',
      '  return (<>',
      '    <RetryButton failures={[failure, renamed, held, arrow, chained]} focusTarget={ref} />',
      '    <RetryButton failures={[loose, mixed, bare, other, fromLet, listed, spread, twin, cyclic, missing, viaDefault, defaulted, deep, rest, failure2, failure3, mutable]} focusTarget={ref} />',
      '    <RetryButton failures={[whole.failure]} focusTarget={ref} />', // a member read: not followed
      '  </>)',
      '}',
      'export function B(useThing: () => Thing) {',
      '  const { failure } = useThing()', // a parameter shadows the import
      '  return <RetryButton failures={[failure]} focusTarget={ref} />',
      '}',
    ].join('\n')
    const { handBuilt, props } = failureScan(consumer, 'app/page.tsx', modules)
    const flagged = ['loose', 'mixed', 'bare', 'other', 'fromLet', 'listed', 'spread', 'twin', 'cyclic', 'missing', 'viaDefault', 'defaulted', 'deep', 'rest', 'failure2', 'failure3', 'mutable']
    expect(handBuilt.map((site) => `${site.line}: ${site.expr}`)).toEqual([
      ...flagged.map((name) => `33: ${name}`),
      '34: whole.failure',
      '39: failure',
    ])
    expect(props).toEqual([])
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
      "import { useRetainedFailure } from '@/hooks/useRetainedFailure'",
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
      '8: Renamed failure={loose}',
      '9: Renamed {...rest}',
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
    expect(Object.keys(ALLOW_RETRY).length).toBe(MAX_RETRY_ALLOWLIST_SIZE)
    expect(pinned(ALLOW_RETRY)).toBe(MAX_RETRY_PINNED_SITES)
    expect(Object.keys(ALLOW_RETRY_LABEL).length).toBe(MAX_RETRY_LABEL_ALLOWLIST_SIZE)
    expect(pinned(ALLOW_RETRY_LABEL)).toBe(MAX_RETRY_LABEL_PINNED_SITES)
    expect(Object.keys(ALLOW_HAND_BUILT_FAILURE).length).toBe(MAX_HAND_BUILT_FAILURE_FILES)
    expect(pinned(ALLOW_HAND_BUILT_FAILURE)).toBe(MAX_HAND_BUILT_FAILURE_SITES)
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

const ONE_VERB_MESSAGE =
  'The product has one retry verb (docs/brand/decisions-log.md D-032): "Try again", busy "Trying again…". A ' +
  "RetryButton call site passes no label (the label is RetryButton's own); any other retry control reads exactly " +
  '"Try again" and, busy, "Trying again…"; copy beside it says "try again", never "retry", and a status line ' +
  '"Trying again…". See frontend/DESIGN_SYSTEM.md §4 and lessons/frontend-busy-controls-stay-focusable.md (d).'

describe('the one retry verb, "Try again" (D-032; rule-12 gate)', () => {
  it('fails a RetryButton that names itself and every form of a retry control that reads another verb, and nothing else', () => {
    const fixture = [
      "import { RetryButton as Again } from '@/hooks/useRetainedFailure'",
      'export function X({ label, busyText }: Props) {',
      '  return (<>',
      '    <RetryButton failures={[f]} focusTarget={ref} />', // the label is RetryButton's
      '    <RetryButton failures={[f]} focusTarget={ref} leftIcon={<Icon />} />', // an icon is no label
      '    <RetryButton failures={[f]} focusTarget={ref}>', // whitespace and a comment are no label
      "      {/* the label is RetryButton's */}",
      '    </RetryButton>',
      '    <RetryButton failures={[f]} focusTarget={ref}>Retry</RetryButton>', // a label of its own
      '    <RetryButton failures={[f]} focusTarget={ref}>Try again</RetryButton>', // even the verb: one source
      "    <RetryButton failures={[f]} focusTarget={ref}>{'Retry generation'}</RetryButton>", // an expression
      '    <RetryButton failures={[f]} focusTarget={ref}>{label}</RetryButton>', // a parameter
      '    <RetryButton failures={[f]} focusTarget={ref}><Icon /></RetryButton>', // an element
      '    <RetryButton failures={[f]} focusTarget={ref} aria-label="Retry account check" />',
      '    <RetryButton failures={[f]} focusTarget={ref} aria-labelledby="usage-title" />',
      '    <RetryButton failures={[f]} focusTarget={ref} children="Retry usage" />',
      '    <RetryButton {...props} />', // a spread could carry a label
      '    <Again failures={[f]} focusTarget={ref}>Retry subscription</Again>', // under an import alias
      '    <Button onClick={reset}>Try again</Button>', // the one verb
      '    <Button onClick={go}>Retry</Button>',
      '    <button onClick={go}><Icon /> Retry account check</button>', // after an icon
      '    <Button onClick={go}>Try again later</Button>', // words after the verb
      '    <Button onClick={go}>Retrying is not a word here</Button>', // any text that starts "Retry"
      '    <Button loading={b} loadingText="Retrying…" onClick={go}>Try again</Button>', // the old busy form
      '    <Button loading={b} loadingText="Trying again..." onClick={go}>Try again</Button>', // three dots
      '    <Button loading={b} loadingText="Trying again…" onClick={go}>Try again</Button>', // the one busy form
      '    <Button loading={b} loadingText={busyText} onClick={go}>Try again</Button>', // busy text it cannot read
      "    <Button onClick={go}>{busy ? 'Retrying…' : 'Try again'}</Button>", // a busy branch
      "    <Button onClick={go}>{busy ? 'Trying again…' : 'Try again'}</Button>", // both forms right
      '    <Button onClick={go}>{retryLabel}</Button>', // a same-file const
      '    <Button aria-label="Retry" onClick={go}>Reload</Button>', // an aria-label marks it a retry
      "    <Button onClick={go}>{failed ? 'Try again' : label}</Button>", // a branch it cannot read
      "    <Button onClick={go}>{failed && 'Try again'}</Button>", // && renders its right side
      '    <p>Please try again later.</p>', // prose: the label does not start with the verb
      '    <Button onClick={go}>Reload</Button>', // nothing here marks it a retry (the wiring clause and the pins do)
      '    <Button onClick={go}>{`Retry`}</Button>', // a template
      "    <Button loading={b} loadingText={pressed ? 'Retrying…' : undefined} onClick={go}>Load</Button>", // busy text marks it
      '    <Button onClick={go}>{mutable}</Button>', // a let it cannot read, and no retry text: the copy clause sees its string
      "    <Button onClick={go}>{'Try again'}{' '}</Button>", // the one verb, from expressions
      '    {/* <Button>Retry</Button> */}',
      "    <Button loading={b} loadingText={pressed ? 'Trying again…' : undefined} reserveLoadingText=\"Retrying…\" onClick={go}>Try again</Button>", // the room kept at rest
      '  </>)',
      '}',
      "const retryLabel = 'Retry'",
      "let mutable = 'Retry'",
      'function Y() {',
      "  return <Button onClick={go}>{mutable ? 'Try again' : mutable}</Button>", // a let it cannot read on a retry control
      '}',
    ].join('\n')
    expect(oneVerbSites(fixture, 'fixture.tsx').map((site) => `${site.line}: ${site.expr}`)).toEqual([
      '9: RetryButton "Retry": a label of its own',
      '10: RetryButton "Try again": a label of its own',
      "11: RetryButton \"{'Retry generation'}\": a label of its own",
      '12: RetryButton "{label}": a label of its own',
      '13: RetryButton "<Icon />": a label of its own',
      '14: RetryButton aria-label="Retry account check": a label of its own',
      '15: RetryButton aria-labelledby="usage-title": a label of its own',
      '16: RetryButton children="Retry usage": a label of its own',
      '17: RetryButton {...props}: a spread whose label the scan cannot read',
      '18: Again "Retry subscription": a label of its own',
      '20: Button label "Retry" is not "Try again"',
      '21: button label "Retry account check" is not "Try again"',
      '22: Button label "Try again later" is not "Try again"',
      '23: Button label "Retrying is not a word here" is not "Trying again…"',
      '24: Button busy text "Retrying…" is not "Trying again…"',
      '25: Button busy text "Trying again..." is not "Trying again…"',
      '27: Button text it cannot read: loadingText={busyText}',
      '28: Button label "Retrying…" is not "Trying again…"',
      '30: Button label "Retry" is not "Try again"',
      '31: Button label "Reload" is not "Try again"',
      '31: Button aria-label "Retry" is not "Try again"',
      '32: Button text it cannot read: {label}',
      '36: Button label "Retry" is not "Try again"',
      '37: Button label "Load" is not "Try again"',
      '37: Button busy text "Retrying…" is not "Trying again…"',
      '41: Button busy text "Retrying…" is not "Trying again…"',
      '47: Button text it cannot read: {mutable}',
    ])
  })

  it('reads RetryButton under every name an import of its module gives it, fails any other use of it, and reads aria-labelledby and children on any retry control', () => {
    const fixture = [
      "import * as H from '@/hooks/useRetainedFailure'",
      "import Again, { RetryButton, type RetryButtonProps } from '../hooks/useRetainedFailure'", // a default import, a relative path
      "import { createElement } from 'react'",
      "export * from '@/hooks/useRetainedFailure'", // an importer of this file gets it under any name
      "export * as Retained from '@/hooks/useRetainedFailure'",
      "export { RetryButton as Retry, useRetainedFailure } from '@/hooks/useRetainedFailure'", // renamed; the hook is not it
      'const Alias = RetryButton',
      "const Lazy = dynamic(() => import('@/hooks/useRetainedFailure').then((m) => m.RetryButton))",
      'type Props = RetryButtonProps & { as?: typeof RetryButton | typeof H.RetryButton }', // a type renders nothing
      'export function X({ label }: { label: string }) {',
      '  const { RetryButton: Renamed } = H',
      '  return (<>',
      '    <H.RetryButton failures={[f]} focusTarget={ref} />', // a namespace member, no label of its own
      '    <H.RetryButton failures={[f]} focusTarget={ref} aria-labelledby="usage-title" />',
      '    <H.RetryButton failures={[f]} focusTarget={ref}>Retry</H.RetryButton>',
      '    <Again failures={[f]} focusTarget={ref} aria-label="Retry usage" />',
      '    {createElement(RetryButton, { failures: [f], focusTarget: ref })}',
      '    <Slot as={H.RetryButton} render={{ RetryButton }} />',
      '    <Button onClick={go} aria-labelledby="usage-title">Try again</Button>', // named by text the scan does not read
      '    <Button onClick={go} aria-labelledby="usage-title">Reload</Button>', // nothing marks it a retry
      '    <Button onClick={go} children="Retry" />',
      '    <Button onClick={go} children={label} aria-label="Try again" />',
      '  </>)',
      '}',
      'export default RetryButton',
    ].join('\n')
    expect(oneVerbSites(fixture, 'components/fixture.tsx').map((site) => `${site.line}: ${site.expr}`)).toEqual([
      "4: export * from '@/hooks/useRetainedFailure': re-exports RetryButton under a name the scan cannot follow",
      "5: export * as Retained from '@/hooks/useRetainedFailure': re-exports RetryButton under a name the scan cannot follow",
      '6: RetryButton used other than as a JSX tag: a label the scan cannot read',
      '7: RetryButton used other than as a JSX tag: a label the scan cannot read',
      "8: import('@/hooks/useRetainedFailure'): loads RetryButton under a name the scan cannot follow",
      '11: RetryButton used other than as a JSX tag: a label the scan cannot read',
      '14: H.RetryButton aria-labelledby="usage-title": a label of its own',
      '15: H.RetryButton "Retry": a label of its own',
      '16: Again aria-label="Retry usage": a label of its own',
      '17: RetryButton used other than as a JSX tag: a label the scan cannot read',
      '18: H.RetryButton used other than as a JSX tag: a label the scan cannot read',
      '18: RetryButton used other than as a JSX tag: a label the scan cannot read',
      '19: Button text it cannot read: aria-labelledby="usage-title"',
      '21: Button label "Retry" is not "Try again"',
      '22: Button text it cannot read: children={label}',
      '25: RetryButton used other than as a JSX tag: a label the scan cannot read',
    ])
    // The failures clause matches it by the same names: each `f` here is built by hand.
    expect(failureScan(fixture, 'components/fixture.tsx').handBuilt.map((site) => `${site.line}: ${site.expr}`)).toEqual([
      '13: f',
      '14: f',
      '15: f',
      '16: f',
    ])
  })

  it("reads RetryButton's own definition, with no exemption: its label is the one verb and its busy text the one busy form", () => {
    const real = readFileSync(path.join(frontendRoot, RETRY_BUTTON.file), 'utf8')
    // The busy text it shows is the one whose room it keeps at rest, so the swap never resizes it.
    expect(retryButtonOwnText(real)).toEqual([{ labels: [ONE_VERB], loadingText: [ONE_BUSY_TEXT], reserveLoadingText: [ONE_BUSY_TEXT] }])
    expect(oneVerbSites(real, RETRY_BUTTON.file)).toEqual([])
    // The old busy form inside the definition fails the app-wide clause too: nothing exempts it.
    const old = real.replace(`'${ONE_BUSY_TEXT}'`, "'Retrying…'")
    expect(old).not.toBe(real)
    expect(oneVerbSites(old, RETRY_BUTTON.file).map((site) => site.expr)).toEqual([
      'Button busy text "Retrying…" is not "Trying again…"',
      'Button busy text "Retrying…" is not "Trying again…"',
    ])
  })

  it("reads a template's head to tell a retry control, and fails the template it cannot read", () => {
    const fixture = [
      'export function X({ name, n }: { name: string; n: number }) {',
      '  return (<>',
      '    <Button onClick={go} aria-label={`Try again for ${name}`}><Icon /></Button>', // an icon-only retry control
      '    <Button onClick={go}>{`Retry ${n} more`}</Button>',
      '    <Button loading={b} loadingText={`Retrying ${name}…`} onClick={go}>Load</Button>', // busy text marks it
      '    <Button onClick={go} aria-label={`Open ${name}`}><Icon /></Button>', // a head that is no retry
      '    <Button onClick={go} aria-label={`${name}: try again`}><Icon /></Button>', // not at the start: as in prose
      '  </>)',
      '}',
    ].join('\n')
    expect(oneVerbSites(fixture, 'fixture.tsx').map((site) => `${site.line}: ${site.expr}`)).toEqual([
      '3: Button text it cannot read: aria-label={`Try again for ${name}`}',
      '4: Button text it cannot read: {`Retry ${n} more`}',
      '5: Button label "Load" is not "Try again"',
      '5: Button text it cannot read: loadingText={`Retrying ${name}…`}',
    ])
  })

  it('RetryButtonProps declares each label prop `never`, so TypeScript refuses one at a call site', () => {
    const real = readFileSync(path.join(frontendRoot, RETRY_BUTTON.file), 'utf8')
    expect(neverProps(real).sort()).toEqual([...LABEL_ATTRS].sort())
  })

  it('no RetryButton call site passes a label, and every retry control reads the one verb', () => {
    const offenders = [...foundOneVerb].flatMap(([file, sites]) => sites.map((site) => `${file}:${site.line}: ${site.expr}`))
    expect(offenders, ONE_VERB_MESSAGE).toEqual([])
  })

  it('reads every form of the old verb in copy, and leaves code alone', () => {
    const fixture = [
      "import { thing } from './retry'",
      "export * from './retrying'",
      "type Mode = 'retry' | 'idle'",
      "const codes = { 'retry': 1, retrying: 2 }",
      "const msg = 'Retry to refresh it.'",
      'const later = "Please retry in a moment."',
      'const tpl = `Retrying ${n} of ${m} times`',
      'const tail = `${a} retried`',
      'const mid = `${a} then retries ${b} more`',
      'console.warn(`[summary] attempt failed; retrying once...`)',
      "console.error('retry failed', err)",
      "const header = response.headers.get('Retry-After')",
      "const ok = 'Try again'",
      "const able = 'isRetryable'",
      '// retry in a comment is not copy',
      'export function X() {',
      '  return (<>',
      '    <p>Please retry.</p>',
      '    <Notice description="Retry to generate it again." />',
      "    <Notice description={failed ? 'Please retry.' : 'Done.'} />",
      '    <div className="retry-row" data-testid="retry" id="retry" />',
      '    <Button onClick={go}>Try again</Button>',
      "    <Status text={'Connection interrupted. Retrying...'} />",
      '  </>)',
      '}',
      "const lazy = import('./retry')",
    ].join('\n')
    expect(retryWordSites(fixture, 'fixture.tsx').map((site) => `${site.line}: ${site.expr}`)).toEqual([
      '5: "Retry to refresh it."',
      '6: "Please retry in a moment."',
      '7: "Retrying"',
      '8: "retried"',
      '9: "then retries"',
      '18: "Please retry."',
      '19: "Retry to generate it again."',
      '20: "Please retry."',
      '23: "Connection interrupted. Retrying..."',
    ])
    // Out of reach, planted as the gap the header names: a word split across JSX text and an expression is read a
    // part at a time, so neither clause sees it.
    const gap = "export const P = () => <p>Please re{''}try in a moment.</p>"
    expect(retryWordSites(gap, 'features/probe/Gap.tsx'), 'the gap is out of reach of the copy clause, as the header says').toEqual([])
    expect(oneVerbSites(gap, 'features/probe/Gap.tsx'), 'the gap is out of reach of the one-verb clause, as the header says').toEqual([])
  })

  it('reads every .ts and .tsx module under the roots for copy, a status line in an api module included', () => {
    expect(wordScanned).toContain('features/summaries/api/summaries-api.ts')
    expect(wordScanned).toContain(RETRY_BUTTON.file)
    expect(wordScanned.length).toBeGreaterThan(scanned.length)
  })

  it('no copy says "retry" outside the pinned code strings', () => {
    expect(unpinned(foundRetryWord, ALLOW_RETRY_WORD), ONE_VERB_MESSAGE).toEqual([])
  })

  it.each(Object.keys(ALLOW_RETRY_WORD))('%s still has its pinned code string (remove the pin when it goes)', (file) => {
    const actual = (foundRetryWord.get(file) ?? []).map((site) => site.expr).sort()
    expect(actual).toEqual([...ALLOW_RETRY_WORD[file].sites].sort())
  })

  it('ALLOW_RETRY_WORD is shrink-only: its caps equal the list, and every entry has a reason', () => {
    const pinned = Object.values(ALLOW_RETRY_WORD).reduce((sum, { sites }) => sum + sites.length, 0)
    expect(Object.keys(ALLOW_RETRY_WORD).length).toBe(MAX_RETRY_WORD_FILES)
    expect(pinned).toBe(MAX_RETRY_WORD_SITES)
    for (const [file, { reason }] of Object.entries(ALLOW_RETRY_WORD)) {
      expect(reason.trim().length, `${file} needs a reason`).toBeGreaterThan(0)
    }
  })
})
