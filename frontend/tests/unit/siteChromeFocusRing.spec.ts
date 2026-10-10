import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * Every control in the site chrome shows the brand focus ring, never the browser's default outline
 * (EN-05c, rule 12). There is no global :focus-visible rule (globals.css), so a control without the
 * recipe falls back to Chromium's `outline: auto 1px`: the logo link, the theme toggle, the mobile
 * menu button and its links did, beside nav links that carry the sage ring. The recipe is
 * DESIGN_SYSTEM.md §4's "Focus ring": `focus-visible:outline-none focus-visible:shadow-ring-brand
 * dark:focus-visible:shadow-ring-brand-dark`. The skip link's reveal uses the same triple on `focus:`,
 * since it must show on any focus.
 *
 * The scan reads the TypeScript AST of each chrome file below and checks every element a user can Tab
 * to (a, area, button, embed, input, object, select, summary, textarea, next/link's Link, anything with a
 * tabIndex the scan cannot prove negative: 0 or more, or a dynamic value such as a roving
 * `tabIndex={selected ? 0 : -1}`, and any contentEditable region the scan cannot prove off). Its className
 * must carry the whole triple, or be the DS factory `buttonVariants(…)`, which composes it (pinned below).
 * A className the scan cannot read (a variable, a call to anything but `buttonVariants` and the DS joiner
 * `cx`) fails: the ring has to be visible in the file. Dynamic parts (a template's `${…}`, a conditional
 * or variable argument of `cx(…)`) are ignored, so the triple must sit in the static text. A props spread
 * fails too, on any element, since it may supply a tabIndex or a className; the one spread the scan reads
 * is a component's own rest props passed to the element that takes its className, as the DS primitives
 * write it (see ownRestProps). Three natively tabbable shapes fail whatever their className, since the
 * browser focuses something no class on them reaches (see unstylableStop): an <iframe> in the Tab order,
 * <audio> or <video> with `controls`, and a <details> with no <summary> of its own.
 *
 * A field the forms plugin styles (a text input, textarea, select, checkbox or radio) also takes off
 * @tailwindcss/forms' own focus ring (`focus:ring-0 focus:ring-offset-0`):
 * the plugin's base style draws a blue (#2563eb) ring with a white offset on any focus, and the shadow
 * utilities compose with it, so the triple alone shows the brand ring inside a blue one. A control that
 * is statically `disabled` is not a Tab stop.
 *
 * Scope: the chrome a keyboard user tabs through on every route, discovered rather than listed (see
 * CHROME_ROOTS): everything app/layout.tsx mounts (the site header with its menus, the footer, the
 * verification banner and prompt, the cookie-consent bar, the providers' error boundary and feedback
 * widget), every route layout, template or error boundary under app/ (the admin section's nav, the
 * root error fallback), the auth routes' shell and the page header, with every module they import, the
 * DS primitives they render included (Modal's close ✕ is one of their stops). The page header also
 * renders the controls a page passes into its `actions` slot (the dashboard's "Log out"), so every
 * `<SecondaryHeader actions={…}>` in the app is scanned too, and its controls must be written inline. A
 * page's other controls are not chrome: the filing identity strip's breadcrumb carries the recipe but
 * is outside this gate. This is the rule's one gate (AGENTS.md §4): no e2e walk repeats it.
 */
const ROOT = path.resolve(__dirname, '../..')

/**
 * Where the site chrome is mounted: the root layout (header, footer, verification banner and prompt,
 * consent bar, and the providers' app-wide widgets, on every route), the auth routes' shell, and the
 * page header pages render. The scanned files are discovered from these: every .tsx module they reach,
 * transitively, through `@/` or relative imports (lazy `import('…')` included) and re-exports, .ts barrels
 * included, by the names the chrome takes, so the components/ui barrel brings in the DS primitives the
 * chrome renders (Modal with its close ✕, Button, Skeleton, …) and not the others. A new banner, menu,
 * widget or primitive the chrome imports is scanned without anyone listing it.
 */
const CHROME_ROOTS = ['app/layout.tsx', 'features/auth/components/AuthShell.tsx', 'components/SecondaryHeader.tsx']

/**
 * Every route layout, template and error boundary under app/ (`app/admin/layout.tsx`'s section nav, the
 * fallback `global-error.tsx` renders in place of the whole layout). Next composes them around a route's
 * pages from the file system, never through an import, so the import graph from CHROME_ROOTS cannot
 * reach them; they are roots of their own.
 */
function routeShells(root: string = ROOT): string[] {
  const out: string[] = []
  const walk = (dir: string) => {
    for (const entry of readdirSync(path.join(root, dir), { withFileTypes: true })) {
      const rel = path.join(dir, entry.name)
      if (entry.isDirectory()) walk(rel)
      else if (['layout.tsx', 'template.tsx', 'error.tsx', 'global-error.tsx'].includes(entry.name)) out.push(rel)
    }
  }
  walk('app')
  return out.sort()
}

/** Chrome files the scan skips, each with its reason. Shrink-only: fix the file and delete its line. */
const NOT_SCANNED: Record<string, string> = {}

/**
 * Third-party components the chrome renders (`module Tag`), and how their Tab stops meet the rule. The
 * scan cannot read inside a package, so a new one fails until it is classified here.
 */
const THIRD_PARTY: Record<string, string> = {
  'next/link Link': 'renders an <a>: scanned as a Tab stop like any other',
  'react Suspense': 'renders no control',
  '@vercel/analytics/next Analytics': 'renders no control',
  'posthog-js/react PHProvider': 'a provider: renders no control',
  '@phosphor-icons/react IconContext.Provider': 'a provider: renders no control',
  '@tanstack/react-query QueryClientProvider': 'a provider: renders no control',
  'sonner Toaster': 'its focusable toasts and their buttons take the ring through toastOptions.classNames (pinned below)',
}

/** The specifier of an `import('…')` call, the lazy form of an import (`dynamic(() => import('…'))`). */
const lazyImport = (node: ts.Node): string | undefined =>
  ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword && node.arguments[0] && ts.isStringLiteralLike(node.arguments[0])
    ? node.arguments[0].text
    : undefined

const isLocal = (spec: string) => spec.startsWith('@/') || spec.startsWith('.')

/** The third-party components `source` renders, as `module Tag`. */
function thirdPartyTags(source: string, fileName: string): string[] {
  const sf = parse(source, fileName)
  const modules = new Map<string, string>()
  for (const stmt of sf.statements) {
    if (!ts.isImportDeclaration(stmt) || !ts.isStringLiteral(stmt.moduleSpecifier)) continue
    const pkg = stmt.moduleSpecifier.text
    if (isLocal(pkg)) continue
    const clause = stmt.importClause
    if (clause?.name) modules.set(clause.name.text, pkg)
    if (clause?.namedBindings && ts.isNamedImports(clause.namedBindings)) {
      for (const el of clause.namedBindings.elements) modules.set(el.name.text, pkg)
    }
    // A namespace import (`import * as Menu from '…'`) renders as <Menu.Root>.
    if (clause?.namedBindings && ts.isNamespaceImport(clause.namedBindings)) modules.set(clause.namedBindings.name.text, pkg)
  }
  // A component loaded lazily from a package renders under the name it is bound to
  // (`const Devtools = dynamic(() => import('pkg'))`).
  const lazyPackage = (node: ts.Node): string | undefined => {
    const spec = lazyImport(node)
    return spec !== undefined && !isLocal(spec) ? spec : ts.forEachChild(node, lazyPackage)
  }
  const bind = (node: ts.Node): void => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) {
      const pkg = lazyPackage(node.initializer)
      if (pkg) modules.set(node.name.text, pkg)
    }
    ts.forEachChild(node, bind)
  }
  bind(sf)
  const tags = new Set<string>()
  const visit = (node: ts.Node): void => {
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
      const tag = node.tagName.getText(sf)
      const pkg = modules.get(tag.split('.')[0])
      if (pkg) tags.add(`${pkg} ${tag}`)
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return [...tags]
}

/**
 * The chrome's .tsx modules, discovered from `roots` through the module graph: every import and
 * `export … from` that is not type-only, and every lazy `import('…')`, through `@/` or relative paths,
 * including .ts modules such as a barrel's index.ts. A module reached at all is read whole, but a named
 * re-export (`export { Modal } from './Modal'`) leads on only when the chrome takes that name; an
 * `export *` passes the names on. Only the .tsx modules are returned; a .ts module renders nothing itself.
 */
function chromeFiles(roots: string[] = CHROME_ROOTS, root: string = ROOT): string[] {
  const resolveImport = (from: string, spec: string): string | null => {
    let base: string
    if (spec.startsWith('@/')) base = path.join(root, spec.slice(2))
    else if (spec.startsWith('.')) base = path.resolve(path.dirname(path.join(root, from)), spec)
    else return null
    for (const candidate of [`${base}.tsx`, `${base}.ts`, path.join(base, 'index.tsx'), path.join(base, 'index.ts')]) {
      if (existsSync(candidate)) return path.relative(root, candidate)
    }
    return null
  }
  // What the chrome takes from each module it reaches: all of it ('*') or the names it imports. A module
  // reached again for a name it was not taken for is read again, for the re-exports that name leads to.
  const taken = new Map<string, Set<string> | '*'>()
  const queue: string[] = []
  const take = (file: string | null, names: Set<string> | '*') => {
    if (!file || (names !== '*' && names.size === 0)) return
    const had = taken.get(file)
    if (had === '*' || (had && names !== '*' && [...names].every((name) => had.has(name)))) return
    taken.set(file, names === '*' || !had ? names : new Set([...had, ...names]))
    queue.push(file)
  }
  for (const file of roots) take(file, '*')
  while (queue.length) {
    const file = queue.shift()!
    const names = taken.get(file)!
    const sf = parse(readFileSync(path.join(root, file), 'utf8'), file)
    for (const stmt of sf.statements) {
      if (ts.isImportDeclaration(stmt) && !stmt.importClause?.isTypeOnly && ts.isStringLiteral(stmt.moduleSpecifier)) {
        take(resolveImport(file, stmt.moduleSpecifier.text), importedNames(stmt.importClause))
      } else if (ts.isExportDeclaration(stmt) && !stmt.isTypeOnly && stmt.moduleSpecifier && ts.isStringLiteral(stmt.moduleSpecifier)) {
        const target = resolveImport(file, stmt.moduleSpecifier.text)
        const clause = stmt.exportClause
        if (!clause) take(target, names)
        else if (ts.isNamespaceExport(clause)) take(target, names === '*' || names.has(clause.name.text) ? '*' : new Set())
        else {
          const picked = clause.elements.filter((el) => !el.isTypeOnly && (names === '*' || names.has(el.name.text)))
          take(target, new Set(picked.map((el) => (el.propertyName ?? el.name).text)))
        }
      }
    }
    // A module loaded lazily, wherever in the file its import() sits, is rendered all the same: taken whole.
    const lazy = (node: ts.Node): void => {
      const spec = lazyImport(node)
      if (spec !== undefined) take(resolveImport(file, spec), '*')
      ts.forEachChild(node, lazy)
    }
    lazy(sf)
  }
  return [...taken.keys()].filter((file) => file.endsWith('.tsx')).sort()
}

/** The names an import takes from its module: '*' for a namespace or side-effect import, 'default' for a default one. */
function importedNames(clause: ts.ImportClause | undefined): Set<string> | '*' {
  if (!clause || (clause.namedBindings && ts.isNamespaceImport(clause.namedBindings))) return '*'
  const names = new Set<string>()
  if (clause.name) names.add('default')
  if (clause.namedBindings && ts.isNamedImports(clause.namedBindings)) {
    for (const el of clause.namedBindings.elements) if (!el.isTypeOnly) names.add((el.propertyName ?? el.name).text)
  }
  return names
}

const RINGS = [
  ['focus-visible:outline-none', 'focus-visible:shadow-ring-brand', 'dark:focus-visible:shadow-ring-brand-dark'],
  ['focus:outline-none', 'focus:shadow-ring-brand', 'dark:focus:shadow-ring-brand-dark'],
]
/** @tailwindcss/forms rings a focused field (text input, textarea, select, checkbox, radio) itself; these take that ring off. */
const FORMS_RING_OFF = ['focus:ring-0', 'focus:ring-offset-0']
/** Input types the forms plugin leaves unstyled, so they draw no ring of their own. */
const NOT_FORMS_STYLED = ['submit', 'button', 'reset', 'hidden', 'image', 'file', 'range', 'color']
/** Elements in the Tab order by themselves whose own className styles their focus (Chromium 141). */
const INTRINSIC = new Set(['a', 'area', 'button', 'embed', 'input', 'object', 'select', 'summary', 'textarea'])
/** Elements the browser may focus where no class on them reaches (see unstylableStop). */
const UNSTYLABLE = new Set(['audio', 'details', 'iframe', 'video'])

interface Finding {
  line: number
  tag: string
  problem: string
}

/** The static class tokens of a className attribute, `'factory'` for buttonVariants(…), or null if unreadable. */
function classTokens(init: ts.JsxAttributeValue | undefined): string[] | 'factory' | null {
  if (!init) return null
  const expr = ts.isJsxExpression(init) ? init.expression : init
  return expr ? expressionTokens(expr) : null
}

/**
 * A class expression's static tokens: a string, a template's static text, `buttonVariants(…)` as
 * 'factory', and `cx(…)`, the DS class joiner (components/ui/cx.ts) the primitives write their classes
 * with, as the tokens of its readable arguments. A conditional or variable argument (`loading && '…'`,
 * the caller's className) is dynamic and ignored, like a template's `${…}`. null: unreadable.
 */
function expressionTokens(expr: ts.Expression): string[] | 'factory' | null {
  if (ts.isStringLiteral(expr) || ts.isNoSubstitutionTemplateLiteral(expr)) return expr.text.split(/\s+/).filter(Boolean)
  if (ts.isTemplateExpression(expr)) {
    const text = [expr.head.text, ...expr.templateSpans.map((s) => s.literal.text)].join(' ')
    return text.split(/\s+/).filter(Boolean)
  }
  if (ts.isCallExpression(expr) && ts.isIdentifier(expr.expression)) {
    if (expr.expression.text === 'buttonVariants') return 'factory'
    if (expr.expression.text === 'cx') {
      const parts = expr.arguments.map((arg) => expressionTokens(arg))
      return parts.includes('factory') ? 'factory' : parts.flatMap((part) => (Array.isArray(part) ? part : []))
    }
  }
  return null
}

/**
 * A component's own rest props passed to the element that takes its className, as the DS primitives
 * write it: `function ModalBody({ className, ...rest }) { return <div className={cx('px-6', className)}
 * {...rest} /> }`. The pattern takes className out of `rest`, and everything else in it, a tabIndex
 * included, is written at the component's call sites, where the scan reads it with the className that
 * reaches this element, which must always include it (see carries). A function not named as a
 * component is called (`renderRow({ tabIndex: 0 })`), not rendered, so nothing reads what it is given:
 * its spread stays unread. So does one onto an element whose focus a prop no call site is read for
 * decides: media (`controls`), an <iframe> or a <details> (see unstylableStop), and an element the
 * caller chooses (`{ as: Tag = 'div' }` rendered `as="a"`).
 */
function ownRestProps(spread: ts.JsxSpreadAttribute, element: ts.JsxOpeningElement | ts.JsxSelfClosingElement, sf: ts.SourceFile): boolean {
  if (!ts.isIdentifier(spread.expression)) return false
  const restName = spread.expression.text
  const tag = element.tagName.getText(sf)
  if (UNSTYLABLE.has(tag)) return false
  for (let node: ts.Node | undefined = element.parent; node; node = node.parent) {
    if (!ts.isFunctionDeclaration(node) && !ts.isFunctionExpression(node) && !ts.isArrowFunction(node)) continue
    const pattern = node.parameters[0]?.name
    if (!pattern || !ts.isObjectBindingPattern(pattern)) continue
    if (!pattern.elements.some((el) => el.dotDotDotToken && ts.isIdentifier(el.name) && el.name.text === restName)) continue
    // The nearest function that destructures the spread owns it.
    if (!/^[A-Z]/.test(functionName(node) ?? '')) return false
    if (pattern.elements.some((el) => !el.dotDotDotToken && ts.isIdentifier(el.name) && el.name.text === tag)) return false
    const className = pattern.elements.find((el) => !el.dotDotDotToken && (el.propertyName ?? el.name).getText(sf) === 'className')
    const attr = element.attributes.properties.find((p): p is ts.JsxAttribute => ts.isJsxAttribute(p) && p.name.getText(sf) === 'className')
    const classes = attr?.initializer && ts.isJsxExpression(attr.initializer) ? attr.initializer.expression : undefined
    return !!className && ts.isIdentifier(className.name) && carries(classes, className.name.text)
  }
  return false
}

/**
 * Whether a class expression always includes the binding `name`: the binding itself, a template's
 * `${name}`, or an argument of `cx(…)` that is one of these. A conditional (`open && className`) can
 * drop the caller's classes, ring included, so it does not count.
 */
function carries(expr: ts.Expression | undefined, name: string): boolean {
  if (!expr) return false
  if (ts.isIdentifier(expr)) return expr.text === name
  if (ts.isTemplateExpression(expr)) return expr.templateSpans.some((span) => carries(span.expression, name))
  if (ts.isCallExpression(expr) && ts.isIdentifier(expr.expression) && expr.expression.text === 'cx') return expr.arguments.some((arg) => carries(arg, name))
  return false
}

/** A function's name: its own, or the variable that holds it, through a wrapper such as forwardRef(…). */
function functionName(fn: ts.FunctionDeclaration | ts.FunctionExpression | ts.ArrowFunction): string | undefined {
  if (!ts.isArrowFunction(fn) && fn.name) return fn.name.text
  const holder = ts.isCallExpression(fn.parent) ? fn.parent.parent : fn.parent
  return ts.isVariableDeclaration(holder) && ts.isIdentifier(holder.name) ? holder.name.text : undefined
}

/** A module's default export under whatever names the file imports it as. */
function defaultImportNames(sf: ts.SourceFile, matches: (module: string) => boolean): Set<string> {
  const names = new Set<string>()
  for (const stmt of sf.statements) {
    if (ts.isImportDeclaration(stmt) && ts.isStringLiteral(stmt.moduleSpecifier) && matches(stmt.moduleSpecifier.text)) {
      const name = stmt.importClause?.name?.text
      if (name) names.add(name)
    }
  }
  return names
}

const parse = (source: string, fileName: string) => ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)

/** Every Tab stop in `source` whose className does not carry the brand ring. */
function missingRings(source: string, fileName = 'chrome.tsx'): { stops: number; findings: Finding[] } {
  const sf = parse(source, fileName)
  return scan(sf, sf)
}

/** The same check on the controls `source` passes into a `<SecondaryHeader actions={…}>` slot. */
function missingRingsInHeaderActions(source: string, fileName = 'page.tsx'): { stops: number; findings: Finding[] } {
  const sf = parse(source, fileName)
  const headers = defaultImportNames(sf, (m) => /(^|\/)components\/SecondaryHeader$/.test(m))
  const result = { stops: 0, findings: [] as Finding[] }
  const visit = (node: ts.Node): void => {
    if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && headers.has(node.tagName.getText(sf))) {
      const line = sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
      const tag = node.tagName.getText(sf)
      // A spread can carry `actions` the scan cannot see.
      if (node.attributes.properties.some(ts.isJsxSpreadAttribute)) result.findings.push({ line, tag, problem: 'a props spread the scan cannot read' })
      const actions = node.attributes.properties.find((p) => ts.isJsxAttribute(p) && p.name.getText(sf) === 'actions')
      if (actions && ts.isJsxAttribute(actions) && actions.initializer) {
        const { stops, findings } = scan(actions.initializer, sf)
        // The slot's controls must be written inline: a variable or a component of its own
        // (`actions={headerActions}`, `actions={<HeaderActions />}`) hides them from the scan.
        if (stops === 0) result.findings.push({ line, tag, problem: 'an actions slot with no control the scan can read (write its controls inline)' })
        result.stops += stops
        result.findings.push(...findings)
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return result
}

/**
 * What each branch of a tabIndex expression can be: 'negative' (a negative literal), 'unset' (undefined or
 * null, which leaves the element's own tabbability) or 'stop' (0 or more, or anything the scan cannot
 * evaluate). Conditionals and parentheses are followed into their branches.
 */
function tabIndexBranches(e: ts.Expression): Array<'negative' | 'unset' | 'stop'> {
  if (ts.isParenthesizedExpression(e)) return tabIndexBranches(e.expression)
  if (ts.isConditionalExpression(e)) return [...tabIndexBranches(e.whenTrue), ...tabIndexBranches(e.whenFalse)]
  if (ts.isPrefixUnaryExpression(e) && e.operator === ts.SyntaxKind.MinusToken && ts.isNumericLiteral(e.operand) && Number(e.operand.text) > 0) {
    return ['negative']
  }
  if (e.kind === ts.SyntaxKind.NullKeyword || (ts.isIdentifier(e) && e.text === 'undefined')) return ['unset']
  return ['stop']
}

/**
 * What the browser focuses for a natively tabbable element no class on it can style (measured in Chromium
 * 141), or null: an <iframe> in the Tab order sends focus into the frame's own document; <audio> or <video>
 * with `controls` (unless `{false}`) adds the browser's own controls, each drawn with the browser's ring; a
 * <details> with no <summary> child focuses the browser's own "Details" summary (with one, the summary is
 * the stop, scanned as any other).
 */
function unstylableStop(node: ts.JsxOpeningElement | ts.JsxSelfClosingElement, sf: ts.SourceFile, outOfOrder: boolean): string | null {
  const tag = node.tagName.getText(sf)
  if (tag === 'iframe') return outOfOrder ? null : "focus goes into the frame's own document, which no class here can style"
  if (tag === 'audio' || tag === 'video') {
    const controls = node.attributes.properties.find((p): p is ts.JsxAttribute => ts.isJsxAttribute(p) && p.name.getText(sf) === 'controls')
    const off = !!controls?.initializer && ts.isJsxExpression(controls.initializer) && controls.initializer.expression?.kind === ts.SyntaxKind.FalseKeyword
    return controls && !off ? "the browser's own controls take focus, each with the browser's ring" : null
  }
  if (tag === 'details') {
    const children = ts.isJsxOpeningElement(node) ? node.parent.children : []
    const own = children.some((c) => (ts.isJsxElement(c) ? c.openingElement : ts.isJsxSelfClosingElement(c) ? c : undefined)?.tagName.getText(sf) === 'summary')
    return own ? null : 'no <summary> of its own, so the browser\'s "Details" summary takes focus with the default outline'
  }
  return null
}

function scan(root: ts.Node, sf: ts.SourceFile): { stops: number; findings: Finding[] } {
  // next/link's default export under whatever name the file imports it as.
  const linkNames = defaultImportNames(sf, (m) => m === 'next/link')
  const findings: Finding[] = []
  let stops = 0
  const visit = (node: ts.Node): void => {
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
      const tag = node.tagName.getText(sf)
      const attrs = node.attributes.properties.filter(ts.isJsxAttribute)
      const attr = (name: string) => attrs.find((a) => a.name.getText(sf) === name)
      // A tabIndex is read branch by branch (see tabIndexBranches): it removes a stop only when every
      // branch is negative (`tabIndex={-1}`), and makes one when any branch may be 0 or more, a dynamic
      // value included (`tabIndex={selected ? 0 : -1}`, a roving stop), just as a dynamic `disabled` may
      // leave a control enabled. `tabIndex={ref ? -1 : undefined}` on a focus target is neither.
      const tabIndex = attr('tabIndex')?.initializer
      const branches = tabIndex && ts.isJsxExpression(tabIndex) && tabIndex.expression ? tabIndexBranches(tabIndex.expression) : []
      // An attribute written before a props spread is the spread's to override (`<button disabled {...rest}>`
      // rendered with `disabled={false}`), so only one no spread follows takes a control out of the order.
      const settled = (a: ts.JsxAttribute | undefined) => !!a && !node.attributes.properties.some((p) => ts.isJsxSpreadAttribute(p) && p.pos > a.pos)
      const removed = branches.length > 0 && branches.every((b) => b === 'negative') && settled(attr('tabIndex'))
      const indexed = branches.some((b) => b === 'stop')
      // An editable region is a Tab stop of its own, unless provably off (`false`, "false", "inherit");
      // a bare or dynamic contentEditable may be on.
      const editable = attr('contentEditable') ?? attr('contenteditable')
      const editableOff =
        !!editable?.initializer &&
        ((ts.isStringLiteral(editable.initializer) && ['false', 'inherit'].includes(editable.initializer.text)) ||
          (ts.isJsxExpression(editable.initializer) && editable.initializer.expression?.kind === ts.SyntaxKind.FalseKeyword))
      const editableStop = editable !== undefined && !editableOff
      // `disabled` or `disabled={true}`; a dynamic value may be enabled, so it still counts.
      const disabled = attr('disabled')
      const staticallyDisabled =
        disabled !== undefined &&
        settled(disabled) &&
        (!disabled.initializer ||
          (ts.isJsxExpression(disabled.initializer) && disabled.initializer.expression?.kind === ts.SyntaxKind.TrueKeyword))
      // A props spread (`<div {...getButtonProps()}>`, `<Menu {...menuProps} />`) can supply a tabIndex and a
      // ringless className the scan cannot see, so the element counts as a stop and fails unread, a component
      // included, since it may pass the spread on to an element of its own. The one spread the scan reads is
      // a component's own rest props on the element that takes its className (ownRestProps).
      const spread = node.attributes.properties.some((p) => ts.isJsxSpreadAttribute(p) && !ownRestProps(p, node, sf))
      const unstylable = unstylableStop(node, sf, removed)
      const tabbable =
        unstylable !== null ||
        spread ||
        ((INTRINSIC.has(tag) || linkNames.has(tag) || indexed || editableStop) && !removed && !staticallyDisabled)
      const typeAttr = attr('type')?.initializer
      // Every field @tailwindcss/forms styles: a textarea, a select, and an input that is not a button or
      // a hidden, file, range or colour control (a missing or dynamic type counts as a field).
      const field =
        tag === 'textarea' ||
        tag === 'select' ||
        (tag === 'input' && !(typeAttr && ts.isStringLiteral(typeAttr) && NOT_FORMS_STYLED.includes(typeAttr.text)))
      if (tabbable) {
        stops += 1
        const line = sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
        const className = attr('className')
        const tokens = classTokens(className?.initializer)
        if (unstylable) findings.push({ line, tag, problem: unstylable })
        else if (spread) findings.push({ line, tag, problem: 'a props spread the scan cannot read' })
        else if (!className) findings.push({ line, tag, problem: 'no className, so the browser default outline' })
        else if (tokens === null) findings.push({ line, tag, problem: 'a className the scan cannot read' })
        else if (tokens !== 'factory' && !RINGS.some((ring) => ring.every((t) => tokens.includes(t)))) {
          findings.push({ line, tag, problem: `missing ${RINGS[0].filter((t) => !tokens.includes(t)).join(' ')}` })
        } else if (field && tokens !== 'factory' && !FORMS_RING_OFF.every((t) => tokens.includes(t))) {
          findings.push({ line, tag, problem: `missing ${FORMS_RING_OFF.filter((t) => !tokens.includes(t)).join(' ')} (the forms plugin's ring)` })
        }
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(root)
  return { stops, findings }
}

/** The app's .tsx sources (app/, features/, components/), repository-relative. */
function appSources(): string[] {
  const out: string[] = []
  const walk = (dir: string) => {
    for (const entry of readdirSync(path.join(ROOT, dir), { withFileTypes: true })) {
      const rel = path.join(dir, entry.name)
      if (entry.isDirectory()) walk(rel)
      else if (entry.name.endsWith('.tsx')) out.push(rel)
    }
  }
  for (const dir of ['app', 'features', 'components']) walk(dir)
  return out
}

describe('every Tab stop in the site chrome carries the brand focus ring (EN-05c)', () => {
  const discovered = chromeFiles([...CHROME_ROOTS, ...routeShells()])

  it('the discovery reaches the chrome it is for (a resolver that finds nothing must not pass)', () => {
    for (const file of ['components/Header.tsx', 'components/Footer.tsx', 'components/ThemeToggle.tsx', 'features/auth/components/UserMenu.tsx', 'features/notifications/components/NotificationBell.tsx', 'features/auth/components/VerificationBanner.tsx', 'components/CookieConsent.tsx', 'app/admin/layout.tsx', 'app/global-error.tsx', 'components/ui/Modal.tsx', 'components/ui/Button.tsx']) {
      expect(discovered, file).toContain(file)
    }
    for (const file of Object.keys(NOT_SCANNED)) expect(discovered, `${file} is no longer chrome: drop its exemption`).toContain(file)
  })

  it('the discovery follows barrels and re-exports by the names taken, and skips type-only imports', () => {
    const dir = mkdtempSync(path.join(os.tmpdir(), 'chrome-graph-'))
    const files: Record<string, string> = {
      'app/layout.tsx': "import { Banner, Menu } from '@/components/chrome'\nimport type { Props } from '@/components/types'\nimport { Modal as Dialog } from '@/components/ui'",
      'app/admin/layout.tsx': "import * as UI from '@/components/ui'",
      'app/lazy/layout.tsx': "import dynamic from 'next/dynamic'\nconst Menu = dynamic(() => import('@/components/chrome/Menu').then((m) => m.Menu))",
      'components/chrome/index.ts': "export { Banner } from './Banner'\nexport * from './Menu'",
      'components/chrome/Banner.tsx': 'export const Banner = () => null',
      'components/chrome/Menu.tsx': 'export const Menu = () => null',
      'components/types.tsx': 'export type Props = object',
      'components/ui/index.ts': "export { Modal, ModalHeader } from './Modal'\nexport { Input } from './Input'\nexport { type InputProps } from './InputProps'",
      'components/ui/Modal.tsx': 'export const Modal = () => null\nexport const ModalHeader = () => null',
      'components/ui/Input.tsx': 'export const Input = () => null',
      'components/ui/InputProps.tsx': 'export type InputProps = object',
    }
    try {
      for (const [file, source] of Object.entries(files)) {
        mkdirSync(path.dirname(path.join(dir, file)), { recursive: true })
        writeFileSync(path.join(dir, file), source)
      }
      // The primitive the layout renders, under its own name or another, and not the barrel's other ones.
      expect(chromeFiles(['app/layout.tsx'], dir)).toEqual(['app/layout.tsx', 'components/chrome/Banner.tsx', 'components/chrome/Menu.tsx', 'components/ui/Modal.tsx'])
      // A namespace import takes the whole barrel, its type-only re-export aside.
      expect(chromeFiles(['app/admin/layout.tsx'], dir)).toEqual(['app/admin/layout.tsx', 'components/ui/Input.tsx', 'components/ui/Modal.tsx'])
      // A module loaded lazily is chrome too.
      expect(chromeFiles(['app/lazy/layout.tsx'], dir)).toEqual(['app/lazy/layout.tsx', 'components/chrome/Menu.tsx'])
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })

  it('every third-party component the chrome renders is classified', () => {
    // The reader itself, on a fixed source: default, named and namespace imports all count, and so does
    // a component loaded lazily from a package; a local module does not, lazy or not.
    const fixture = [
      "import Link from 'next/link'",
      "import dynamic from 'next/dynamic'",
      "import { Toaster } from 'sonner'",
      "import * as Menu from '@radix-ui/react-menu'",
      "import { Local } from '@/components/Local'",
      "const Devtools = dynamic(() => import('@tanstack/react-query-devtools').then((m) => m.ReactQueryDevtools))",
      "const LazyLocal = dynamic(() => import('@/components/LazyLocal'))",
      'export const A = () => (<><Link href="/" /><Toaster /><Menu.Root><Menu.Item /></Menu.Root><Local /><Devtools /><LazyLocal /></>)',
    ].join('\n')
    expect(thirdPartyTags(fixture, 'fixture.tsx').sort()).toEqual([
      '@radix-ui/react-menu Menu.Item',
      '@radix-ui/react-menu Menu.Root',
      '@tanstack/react-query-devtools Devtools',
      'next/link Link',
      'sonner Toaster',
    ])
    const used = new Set(discovered.flatMap((file) => thirdPartyTags(readFileSync(path.join(ROOT, file), 'utf8'), file)))
    expect([...used].filter((tag) => !(tag in THIRD_PARTY)), 'classify each in THIRD_PARTY').toEqual([])
    expect(Object.keys(THIRD_PARTY).filter((tag) => !used.has(tag)), 'no longer rendered: drop it').toEqual([])
  })

  // Sonner injects its own grey :focus-visible shadow at runtime with equal or higher specificity than
  // a Tailwind utility, so the ring on its toasts and buttons needs the `!` modifier.
  it('the Toaster passes the ring to every class slot Sonner focuses', () => {
    const file = 'app/providers.tsx'
    const sf = parse(readFileSync(path.join(ROOT, file), 'utf8'), file)
    const consts = new Map<string, ts.Expression>()
    for (const stmt of sf.statements) {
      if (!ts.isVariableStatement(stmt)) continue
      for (const decl of stmt.declarationList.declarations) {
        if (ts.isIdentifier(decl.name) && decl.initializer) consts.set(decl.name.text, decl.initializer)
      }
    }
    const resolve = (expr: ts.Expression | undefined): ts.Expression | undefined =>
      expr && ts.isIdentifier(expr) ? resolve(consts.get(expr.text)) : expr
    let options: ts.Expression | undefined
    const visit = (node: ts.Node): void => {
      if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && node.tagName.getText(sf) === 'Toaster') {
        const attr = node.attributes.properties.find((p) => ts.isJsxAttribute(p) && p.name.getText(sf) === 'toastOptions')
        if (attr && ts.isJsxAttribute(attr) && attr.initializer && ts.isJsxExpression(attr.initializer)) options = resolve(attr.initializer.expression)
      }
      ts.forEachChild(node, visit)
    }
    visit(sf)
    expect(options && ts.isObjectLiteralExpression(options), '<Toaster toastOptions={…}> as an object the scan can read').toBe(true)
    const prop = (obj: ts.ObjectLiteralExpression, name: string) =>
      resolve(obj.properties.find((p): p is ts.PropertyAssignment => ts.isPropertyAssignment(p) && p.name.getText(sf) === name)?.initializer)
    const classNames = prop(options as ts.ObjectLiteralExpression, 'classNames')
    expect(classNames && ts.isObjectLiteralExpression(classNames), 'toastOptions.classNames').toBe(true)
    for (const slot of ['toast', 'closeButton', 'actionButton', 'cancelButton']) {
      const value = prop(classNames as ts.ObjectLiteralExpression, slot)
      const tokens = value && ts.isStringLiteralLike(value) ? value.text.split(/\s+/) : []
      expect(tokens, slot).toEqual(expect.arrayContaining(['focus-visible:outline-none', 'focus-visible:!shadow-ring-brand', 'dark:focus-visible:!shadow-ring-brand-dark']))
    }
  })

  for (const file of discovered.filter((f) => !(f in NOT_SCANNED))) {
    it(file, () => {
      const { findings } = missingRings(readFileSync(path.join(ROOT, file), 'utf8'), file)
      expect(findings.map((f) => `${file}:${f.line} <${f.tag}> ${f.problem}`)).toEqual([])
    })
  }

  it('controls a page passes into the page header\'s actions slot', () => {
    const consumers = appSources().filter((f) => /from ['"]@\/components\/SecondaryHeader['"]/.test(readFileSync(path.join(ROOT, f), 'utf8')))
    expect(consumers.length, 'no page renders SecondaryHeader any more: drop this case').toBeGreaterThan(0)
    let stops = 0
    const findings: string[] = []
    for (const file of consumers) {
      const result = missingRingsInHeaderActions(readFileSync(path.join(ROOT, file), 'utf8'), file)
      stops += result.stops
      findings.push(...result.findings.map((f) => `${file}:${f.line} <${f.tag}> ${f.problem}`))
    }
    expect(stops, 'no page passes a control into the actions slot: drop this case').toBeGreaterThan(0)
    expect(findings).toEqual([])
  })

  it('the actions-slot scan reads only the slot, under any import name', () => {
    const src = `
      import PageHeader from '@/components/SecondaryHeader'
      export function P() {
        return (
          <>
            <button className="p-2">page control, not chrome</button>
            <PageHeader title="T" actions={<><button className="text-sm">Log out</button><a href="/x" className={buttonVariants({ variant: 'primary' })}>go</a></>} />
          </>
        )
      }`
    const { stops, findings } = missingRingsInHeaderActions(src)
    expect(stops).toBe(2)
    expect(findings.map((f) => `${f.tag}: ${f.problem}`)).toEqual([
      'button: missing focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
    ])
    // Indirection the scan cannot follow fails rather than passing empty.
    const hidden = `
      import SecondaryHeader from '@/components/SecondaryHeader'
      function HeaderActions() { return <button className="text-sm">Log out</button> }
      export function P(props: object) {
        const headerActions = <button className="text-sm">Log out</button>
        return (
          <>
            <SecondaryHeader title="A" actions={headerActions} />
            <SecondaryHeader title="B" actions={<HeaderActions />} />
            <SecondaryHeader title="C" {...props} />
            <SecondaryHeader title="D" />
          </>
        )
      }`
    expect(missingRingsInHeaderActions(hidden).findings.map((f) => `${f.line}: ${f.problem}`)).toEqual([
      '8: an actions slot with no control the scan can read (write its controls inline)',
      '9: an actions slot with no control the scan can read (write its controls inline)',
      '10: a props spread the scan cannot read',
    ])
  })

  // The scan trusts buttonVariants(…), so the factory itself must compose the ring: the shared base takes
  // the outline off, and each brand variant draws the ring in both themes (destructive draws ring-error).
  it('buttonVariants composes the ring the scan trusts it for', () => {
    const button = readFileSync(path.join(ROOT, 'components/ui/Button.tsx'), 'utf8')
    const block = (name: string) => button.split(`\n  ${name}: cx(`)[1]?.split('\n  ),')[0] ?? ''
    expect(button.split('const BASE = cx(')[1]?.split(')')[0]).toContain("'focus-visible:outline-none'")
    for (const variant of ['primary', 'secondary', 'ghost']) {
      expect(block(variant), variant).toContain('focus-visible:shadow-ring-brand')
      expect(block(variant), variant).toContain('dark:focus-visible:shadow-ring-brand-dark')
    }
    expect(block('destructive')).toContain('focus-visible:shadow-ring-error')
  })

  it('the scan catches what it is for (a self-check on fixed sources)', () => {
    const ring = 'focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark'
    const src = `
      import NextLink from 'next/link'
      import { buttonVariants } from '@/components/ui'
      export function A({ c, busy, selected }: { c: string; busy: boolean; selected: boolean }) {
        return (
          <nav>
            <NextLink href="/" className="flex">logo</NextLink>
            <button className={\`p-2 \${c} focus-visible:outline-none focus-visible:shadow-ring-brand\`}>toggle</button>
            <a href="/x">bare</a>
            <span tabIndex={0} className="${ring}">stop</span>
            <div tabIndex={0}>stop</div>
            <button className={c}>unknown</button>
            <button tabIndex={-1} aria-hidden="true" className="scrim" />
            <NextLink href="/p" className={buttonVariants({ variant: 'ghost' })}>cta</NextLink>
            <NextLink href="/q" className={\`\${c} ${ring}\`}>ok</NextLink>
            <a href="#main" className="sr-only focus:outline-none focus:shadow-ring-brand dark:focus:shadow-ring-brand-dark">skip</a>
            <input type="checkbox" className="h-5 w-5 ${ring}" />
            <input type="radio" className="focus:ring-0 focus:ring-offset-0 ${ring}" />
            <input type="checkbox" disabled className="h-5 w-5" />
            <button disabled={busy} className="p-2">busy</button>
            <li tabIndex={selected ? 0 : -1} className="p-1">roving</li>
            <h1 tabIndex={selected ? -1 : undefined}>focus target</h1>
            <div contentEditable className="p-1">notes</div>
            <div contentEditable={selected} className="p-1">maybe</div>
            <div contentEditable={false} className="p-1">static</div>
            <textarea className="${ring}" />
            <input type="submit" className="${ring}" />
            <div {...getButtonProps()}>headless</div>
            <NextLink {...linkProps} href="/r" className="${ring}">spread link</NextLink>
            <Menu {...menuProps} />
          </nav>
        )
      }`
    const { stops, findings } = missingRings(src)
    expect(stops).toBe(20)
    expect(findings.map((f) => `${f.tag}: ${f.problem}`)).toEqual([
      'NextLink: missing focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
      'button: missing dark:focus-visible:shadow-ring-brand-dark',
      'a: no className, so the browser default outline',
      'div: no className, so the browser default outline',
      'button: a className the scan cannot read',
      "input: missing focus:ring-0 focus:ring-offset-0 (the forms plugin's ring)",
      'button: missing focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
      'li: missing focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
      'div: missing focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
      'div: missing focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
      "textarea: missing focus:ring-0 focus:ring-offset-0 (the forms plugin's ring)",
      'div: a props spread the scan cannot read',
      'NextLink: a props spread the scan cannot read',
      'Menu: a props spread the scan cannot read',
    ])
  })

  // The DS primitives the chrome renders are read as they are written: classes joined by cx(…), and the
  // component's own rest props passed to the element that takes the caller's className. Modal's close ✕
  // (components/ui/Modal.tsx) is the first case's shape.
  it('the scan reads a primitive as it is written: cx(…) classes and its own rest props', () => {
    const ring = 'focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark'
    const src = `
      import { forwardRef } from 'react'
      import { cx } from './cx'
      export function ModalHeader({ className, onClose, open, ...rest }: Props) {
        return (
          <div className={cx('flex gap-3', className)} {...rest}>
            <button onClick={onClose} className={cx('-m-2 p-2', 'hover:text-x', '${ring}')}>close</button>
            <button onClick={onClose} className={cx('-m-2 p-2', open && '${ring}')}>ring only when open</button>
            <button onClick={onClose} className={cx('-m-2 p-2', 'focus-visible:outline-none')}>ring stripped</button>
          </div>
        )
      }
      export const Button = forwardRef(function Button({ className, ...rest }: Props, ref) {
        return <button ref={ref} className={cx(buttonVariants({ variant: 'primary' }), className)} {...rest} />
      })
      export function Body({ ...rest }: Props) { return <div className="p-4" {...rest} /> }
      export function Footer({ className, ...rest }: Props) { return <div className="p-4" {...rest} /> }
      export function Drop({ className, open, ...rest }: Props) { return <div className={cx('p-2', open && className)} {...rest} /> }
      function row({ className, ...rest }: Props) { return <div className={cx('p-1', className)} {...rest} /> }
      export function Player({ className, ...rest }: Props) { return <video className={cx('w-full', className)} {...rest} /> }
      export function Card({ as: Tag = 'div', className, ...rest }: Props) { return <Tag className={cx('border', className)} {...rest} /> }
      export function Toggle({ className, ...rest }: Props) { return <button disabled className={cx('p-1', className)} {...rest} /> }
      export function Scrim({ className, ...rest }: Props) { return <button {...rest} tabIndex={-1} className={cx('inset-0', className)} /> }
      export function Page() {
        return <><ModalHeader {...headerProps} /><Body tabIndex={0} className="p-2" /></>
      }`
    const { stops, findings } = missingRings(src)
    expect(stops).toBe(13)
    expect(findings.map((f) => `${f.line} <${f.tag}> ${f.problem}`)).toEqual([
      '8 <button> missing focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
      '9 <button> missing focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
      // Rest props that may still hold a className, whose element never takes the caller's className or
      // takes it only on a condition, or that a function is called with rather than rendered with, are
      // read nowhere.
      '16 <div> a props spread the scan cannot read',
      '17 <div> a props spread the scan cannot read',
      '18 <div> a props spread the scan cannot read',
      '19 <div> a props spread the scan cannot read',
      // Nor are the props that decide these elements' focus: a caller's `controls`, a caller's `as="a"`.
      '20 <video> a props spread the scan cannot read',
      '21 <Tag> a props spread the scan cannot read',
      // A `disabled` the rest props can override takes nothing out of the order; a tabIndex written after
      // them does (Scrim, line 23, is no stop).
      '22 <button> missing focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
      // What a call site gives a component is read at the call site.
      '25 <ModalHeader> a props spread the scan cannot read',
      '25 <Body> missing focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
    ])
  })

  // Measured in Chromium 141 by Tabbing a probe page: <area>, <embed> and <object> take focus themselves
  // and their classes style it. An <iframe> sends focus into the frame's document (with tabIndex -1 the
  // frame is skipped whole), a <video controls> took 5 stops and an <audio controls> 2, the browser's own
  // controls after the element, and a <details> with no <summary> focused the browser's own "Details"
  // summary, drawing the default outline; with a <summary>, only the summary was a stop.
  it('every natively tabbable element is a stop, and one no class can style fails whatever its className', () => {
    const ring = 'focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark'
    const src = `
      export function A({ on }: { on: boolean }) {
        return (
          <>
            <map name="m"><area href="/x" alt="x" className="${ring}" /><area href="/y" alt="y" /></map>
            <embed src="/a.pdf" className="${ring}" />
            <object data="/a.pdf" />
            <iframe src="/frame" className="${ring}" />
            <iframe src="/frame" tabIndex={-1} />
            <video controls className="${ring}" />
            <video className="h-4" />
            <audio controls={on} />
            <audio controls={false} />
            <details className="${ring}"><p>body</p></details>
            <details><summary className="${ring}">More</summary><p>body</p></details>
          </>
        )
      }`
    const { stops, findings } = missingRings(src)
    expect(stops).toBe(9)
    expect(findings.map((f) => `${f.tag}: ${f.problem}`)).toEqual([
      'area: no className, so the browser default outline',
      'object: no className, so the browser default outline',
      "iframe: focus goes into the frame's own document, which no class here can style",
      "video: the browser's own controls take focus, each with the browser's ring",
      "audio: the browser's own controls take focus, each with the browser's ring",
      'details: no <summary> of its own, so the browser\'s "Details" summary takes focus with the default outline',
    ])
  })
})
