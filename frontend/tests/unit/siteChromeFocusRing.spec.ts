import { mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import os from 'node:os'
import path from 'node:path'
import postcss from 'postcss'
import tailwindcss, { type Config } from 'tailwindcss'
import resolveConfig from 'tailwindcss/resolveConfig'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { countControlClass, type CountControlKind } from '@/components/ui/countControl'
import { bindingResolver, type Binding } from './astBindings'
import { isLocal, lazyImport, routeFiles, walkImports } from './importWalk'

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
 * must carry the whole triple, or be the DS factory `buttonVariants(…)`, which composes it (pinned below), imported
 * from `@/components/ui` (the barrel or components/ui/Button.tsx, a namespace member included; a page's own function
 * of that name is not the factory, and its className is read as any call is).
 * The scan reads a className as the file writes it: a string, a template's static text, `cx(…)` (the DS
 * joiner) by its readable arguments, `buttonVariants(…)` as the factory, and two more sources of classes.
 * `countControlClass(…)` imported from `@/components/ui` (the barrel or components/ui/countControl.ts, under
 * any local name, a namespace member included) is read as the classes the recipe itself returns for the kind
 * it names: the spec calls the recipe, so the ring is read off it, not trusted by name, and a kind the scan
 * cannot read counts as the classes every kind countControl.ts declares shares. A `const` the file declares
 * (at module level or in the function that renders the control) is read as its initializer, read the same
 * way: `const RING = '…'` composed into `cx(…, RING)`, or `const LINK = cx('…', countControlClass('link'))`
 * written as the whole className. Anything else (a `let`, a parameter, an import, a field, a call to any
 * other function) is unreadable: as the whole className it fails, since the ring has to be visible in the
 * file or come from a recipe the scan reads; as a part (a template's `${…}`, a conditional, an argument of
 * `cx(…)` the scan cannot read) it is dynamic and ignored, so the triple must sit in what the scan reads.
 * A props spread fails too, on any element, since it may supply a tabIndex or a className; the one spread
 * the scan reads is a component's own rest props passed to the element that takes its className, as the DS
 * primitives write it (see ownRestProps). Three natively tabbable shapes fail whatever their className, since the
 * browser focuses something no class on them reaches (see unstylableStop): an <iframe> in the Tab order,
 * <audio> or <video> with `controls`, and a <details> with no <summary> of its own.
 *
 * A field the forms plugin styles (a text input, textarea, select, checkbox or radio) also takes off
 * @tailwindcss/forms' own focus ring (`focus:ring-0 focus:ring-offset-0`):
 * the plugin's base style draws a blue (#2563eb) ring with a white offset on any focus, and the shadow
 * utilities compose with it, so the triple alone shows the brand ring inside a blue one. A control that
 * is statically `disabled` is not a Tab stop. That field clause also runs app-wide, beyond the chrome (the
 * last describe): every field the plugin styles that a page styles itself, and that can take focus (a
 * `tabIndex={-1}` field still takes a click's), takes the plugin's ring off and draws a DS ring with its dark
 * twin. Fields built with `inputClasses(…)` and the DS components are held by
 * tests/unit/inputClassesNoOverrides.spec.tsx instead.
 *
 * Scope: the chrome a keyboard user tabs through on every route, discovered rather than listed (see
 * CHROME_ROOTS): everything app/layout.tsx mounts (the site header with its menus, the footer, the
 * verification banner and prompt, the cookie-consent bar, the providers' error boundary and feedback
 * widget), every route layout, template or error boundary under app/ (the admin section's nav, the
 * root error fallback), the auth routes' shell and the page header, with every module they import, the
 * DS primitives they render included (Modal's close ✕ is one of their stops). The page header also
 * renders the controls a page passes into its `actions` slot (the dashboard's "Log out"), so every
 * `<SecondaryHeader actions={…}>` in the app is scanned too, and its controls must be written inline. A
 * page's other controls are held by the page scan instead: every page.tsx under app/ and the feature modules it
 * reaches (PAGE_ROOTS), with the ringless stops found when it widened counted in a shrink-only residue
 * (RING_RESIDUE). The residue counts stops per file, not their identities: a PR that fixes one stop and
 * adds another in the same file keeps its count and is review-checked (the new ringless control is in its
 * diff); a key by line would move on every edit of the file, and one by tag and name would pass a
 * same-shaped swap and triple the list. This is the rule's one gate (AGENTS.md §4): no e2e walk repeats it.
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
/** Every route's page (each page.tsx under app/), discovered: with the feature modules they reach, their raw Tab
    stops are held to the same ring (field recipes already have app-wide coverage below and in
    inputClassesNoOverrides). A new page is scanned without anyone listing it. */
const PAGE_ROOTS = routeFiles('app', ['page.tsx'], ROOT)

/**
 * The ringless page and feature Tab stops found when the page scan widened from four routes to every route
 * (2026-10), counted per file. Shrink-only: a surface PR that rings a file's controls lowers its count or
 * deletes its line; a new ringless stop fails, in a listed file (its count rises) or an unlisted one. The
 * total of the counts and the number of files equal RING_RESIDUE_MAX, seeded at the scan's count and
 * lowered in the same commit as each shrink, so no slack is left and the list cannot grow without the cap
 * being raised in review. A PR that must raise it says why in its body.
 */
const RING_RESIDUE: Record<string, number> = {
  // Each line names the sweep PR that owns the file, or why it waits. A "props spread" finding in a chart
  // or Markdown renderer is the scan's limit (it cannot read what the spread holds), not always a stop.
  'app/dashboard/page.tsx': 1, // brand-dashboard-watchlist
  'app/delete-account/page.tsx': 4, // auth-adjacent page with no sweep owner yet
  'app/filing/[id]/page-client.tsx': 1, // brand-filing-page
  'app/forgot-password/page.tsx': 1, // brand-auth-pages-presentation
  'app/login/page.tsx': 2, // brand-auth-pages-presentation
  'app/privacy/page.tsx': 10, // legal page: waits on the founder (presentation follow-up)
  'app/reset-password/page.tsx': 2, // brand-auth-pages-presentation
  'app/security/page.tsx': 5, // legal page: waits on the founder (presentation follow-up)
  'app/terms/page.tsx': 4, // legal page: waits on the founder (presentation follow-up)
  'app/verify-email/page.tsx': 3, // brand-auth-pages-presentation
  'features/analysis/components/DataNotesLink.tsx': 1, // its button's class is sourceTraceChipClass, imported from features/filings/lib/sourceTraceChip, which carries the ring; the scan does not read across files (review-checked)
  'features/analysis/components/NarrativePane.tsx': 1, // Markdown renderer props spread on p, li, strong, em and td, which the scan cannot read (no Tab stop)
  'features/analysis/components/TrendCharts.tsx': 17, // chart props spreads the scan cannot read
  'features/analysis/lib/periodAxis.tsx': 2, // chart tick props spread on its SVG text, which the scan cannot read (no Tab stop)
  'features/auth/components/OAuthStartControl.tsx': 2, // brand-auth-pages-presentation
  'features/auth/components/RegisterForm.tsx': 5, // brand-auth-pages-presentation
  'features/companies/components/CompanyIdentity.tsx': 2, // its crumb and link take IDENTITY_CRUMB and IDENTITY_LINK, recipes imported from FilingIdentity, which the scan does not read across files (#1292 ringed them there; review-checked)
  'features/filings/components/FilingsHistoryNote.tsx': 1, // its link's class is IDENTITY_LINK, imported from FilingIdentity, which the scan does not read across files (#1292 ringed it through that recipe; review-checked)
  'features/filings/components/SourceTrace.tsx': 6, // brand-filing-page
  'features/filings/components/SupersededFilingNotice.tsx': 1, // brand-filing-page
  'features/filings/components/TickerFilingsView.tsx': 3, // brand-filing-page
  'features/filings/components/copilot/AskCopilotRail.tsx': 3, // brand-copilot
  'features/filings/components/copilot/CitationChip.tsx': 4, // brand-copilot
  'features/filings/components/copilot/CopilotMessage.tsx': 13, // brand-copilot
  'features/filings/components/copilot/CopilotTeaser.tsx': 1, // brand-copilot
  'features/filings/components/copilot/FilingViewer.tsx': 3, // brand-copilot
  'features/filings/components/copilot/PaneResizer.tsx': 1, // brand-copilot
  'features/filings/components/copilot/ReaderTable.tsx': 2, // brand-copilot (Markdown renderer props spreads)
  'features/filings/components/copilot/SecondaryPaneTabs.tsx': 1, // brand-copilot
  'features/fundamentals/components/FundamentalsTrendChart.tsx': 3, // the chart props spreads the scan cannot read; #1292 ringed its controls
  'features/marketing/components/CatchCard.tsx': 1, // #1311 (brand-public-pages) left it, and no open PR edits the file; the next public-pages change rings it
  'features/marketing/components/HeroExample.tsx': 1, // #1311 ringed its links; the evidence chip's className is sourceTraceChipClass(), a recipe the scan does not read (brand-filing-page owns SourceTrace)
  'features/marketing/components/TraceToSourceDemo.tsx': 1, // #1311 (brand-public-pages) left it, and no open PR edits the file; the next public-pages change rings it
  'features/peers/components/PeerComparisonPanel.tsx': 2, // #1292 ringed its controls; the rest are chart props spreads the scan cannot read
  'features/subscriptions/components/PeekLocked.tsx': 1, // brand-settings-subscriptions
  'features/subscriptions/components/TrialBanner.tsx': 1, // brand-settings-subscriptions
  'features/summaries/components/FinancialMetricsTable.tsx': 2, // brand-filing-page
  'features/summaries/components/SummaryActionsBar.tsx': 1, // brand-filing-page
  'features/summaries/components/SummaryBlocks.tsx': 1, // brand-filing-page
  'features/watchlist/components/PopularTickerChips.tsx': 1, // brand-dashboard-watchlist
}
const RING_RESIDUE_MAX = { files: 40, stops: 117 }

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
  return walkImports(roots, root).filter((file) => file.endsWith('.tsx'))
}

const RINGS = [
  ['focus-visible:outline-none', 'focus-visible:shadow-ring-brand', 'dark:focus-visible:shadow-ring-brand-dark'],
  ['focus:outline-none', 'focus:shadow-ring-brand', 'dark:focus:shadow-ring-brand-dark'],
  ['focus-visible:outline-none', 'focus-visible:shadow-ring-brand-inset', 'dark:focus-visible:shadow-ring-brand-inset-dark'],
  ['focus-visible:outline-none', 'focus-visible:shadow-ring-error', 'dark:focus-visible:shadow-ring-error-dark'],
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

/** The DS button factory, under the modules a file can import it from (`moduleKey`'s form). */
const BUTTON_FACTORY_IMPORTS = { 'components/ui/index': ['buttonVariants'], 'components/ui/Button': ['buttonVariants'] }
/** Whether a callee is the DS button factory: its import (importedName), or, in the factory's own module, the
    module-level function that declares it. A page's own function of the name is neither. */
function buttonFactory(sf: ts.SourceFile): (callee: ts.Expression) => boolean {
  const imported = importedName(sf, BUTTON_FACTORY_IMPORTS)
  const resolve = bindingResolver(sf)
  const own = sf.fileName.replace(/\.(tsx?|js)$/, '') === 'components/ui/Button'
  return (callee) => {
    if (imported(callee)) return true
    if (!own || !ts.isIdentifier(callee) || callee.text !== 'buttonVariants') return false
    const decl = resolve(callee)?.decl
    return !!decl && ts.isFunctionDeclaration(decl) && decl.parent === sf
  }
}
/** The count control's recipe, under the modules a file can import it from (`moduleKey`'s form). */
const COUNT_CONTROL_IMPORTS = { 'components/ui/index': ['countControlClass'], 'components/ui/countControl': ['countControlClass'] }
/** The count control's kinds, read off the union components/ui/countControl.ts declares (`CountControlKind`), so a
    kind added there is read here without anyone listing it. */
const COUNT_KINDS: string[] = (() => {
  const file = path.join(ROOT, 'components/ui/countControl.ts')
  const sf = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
  const alias = sf.statements.find((s): s is ts.TypeAliasDeclaration => ts.isTypeAliasDeclaration(s) && s.name.text === 'CountControlKind')
  const members = alias && ts.isUnionTypeNode(alias.type) ? alias.type.types : alias ? [alias.type] : []
  const kinds = members.flatMap((m) => (ts.isLiteralTypeNode(m) && ts.isStringLiteral(m.literal) ? [m.literal.text] : []))
  if (!kinds.length) throw new Error('components/ui/countControl.ts declares no CountControlKind the scan can read')
  return kinds
})()
const splitClasses = (text: string) => text.split(/\s+/).filter(Boolean)
/** The classes a `countControlClass(…)` call returns: the recipe's own, called with the kind the call names, or,
    for a kind the scan cannot read (`countControlClass(kind)`), the classes every declared kind shares. */
function countControlTokens(arg: ts.Expression | undefined): string[] {
  const named = arg && (ts.isStringLiteral(arg) || ts.isNoSubstitutionTemplateLiteral(arg)) ? arg.text : undefined
  if (named !== undefined && COUNT_KINDS.includes(named)) return splitClasses(countControlClass(named as CountControlKind))
  const lists = COUNT_KINDS.map((kind) => splitClasses(countControlClass(kind as CountControlKind)))
  return lists[0].filter((token) => lists.every((list) => list.includes(token)))
}

/** What a file's class expressions are read with: its bindings, to follow a `const` to its initializer, and the
    count control's recipe under the names the file imports it as. */
interface ClassContext {
  resolve: (ref: ts.Identifier) => Binding | undefined
  isCountControl: (callee: ts.Expression) => boolean
  isButtonFactory: (callee: ts.Expression) => boolean
}
const classContext = (sf: ts.SourceFile): ClassContext => ({
  resolve: bindingResolver(sf),
  isCountControl: importedName(sf, COUNT_CONTROL_IMPORTS),
  isButtonFactory: buttonFactory(sf),
})

/** The static class tokens of a className attribute, `'factory'` for buttonVariants(…), or null if unreadable. */
function classTokens(init: ts.JsxAttributeValue | undefined, ctx: ClassContext): string[] | 'factory' | null {
  if (!init) return null
  const expr = ts.isJsxExpression(init) ? init.expression : init
  return expr ? expressionTokens(expr, ctx) : null
}

/**
 * A class expression's static tokens: a string, a template's static text, `buttonVariants(…)` as
 * 'factory', `countControlClass(…)` as the classes the recipe returns (countControlTokens), a `const` the
 * file declares as the tokens of its initializer (a type assertion or parentheses around it read through;
 * `seen` ends a const that reaches itself), and `cx(…)`, the DS class joiner (components/ui/cx.ts) the
 * primitives write their classes with, as the tokens of its readable arguments. A conditional, a parameter,
 * a `let` or any other argument the scan cannot read (`loading && '…'`, the caller's className) is dynamic
 * and ignored, like a template's `${…}`. null: unreadable.
 */
function expressionTokens(expr: ts.Expression, ctx: ClassContext, seen: ReadonlySet<ts.Node> = new Set()): string[] | 'factory' | null {
  if (ts.isParenthesizedExpression(expr) || ts.isAsExpression(expr) || ts.isSatisfiesExpression(expr) || ts.isNonNullExpression(expr)) {
    return expressionTokens(expr.expression, ctx, seen)
  }
  if (ts.isStringLiteral(expr) || ts.isNoSubstitutionTemplateLiteral(expr)) return splitClasses(expr.text)
  if (ts.isTemplateExpression(expr)) return splitClasses([expr.head.text, ...expr.templateSpans.map((s) => s.literal.text)].join(' '))
  if (ts.isIdentifier(expr)) {
    const decl = ctx.resolve(expr)?.decl
    if (!decl || !ts.isVariableDeclaration(decl) || !decl.initializer || seen.has(decl)) return null
    if (!(ts.getCombinedNodeFlags(decl) & ts.NodeFlags.Const)) return null
    return expressionTokens(decl.initializer, ctx, new Set([...seen, decl]))
  }
  if (ts.isCallExpression(expr) && ctx.isCountControl(expr.expression)) return countControlTokens(expr.arguments[0])
  if (ts.isCallExpression(expr) && ctx.isButtonFactory(expr.expression)) return 'factory'
  if (ts.isCallExpression(expr) && ts.isIdentifier(expr.expression)) {
    if (expr.expression.text === 'cx') {
      const parts = expr.arguments.map((arg) => expressionTokens(arg, ctx, seen))
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
function missingRings(source: string, fileName = 'chrome.tsx', fieldsSeparately = false): { stops: number; findings: Finding[] } {
  const sf = parse(source, fileName)
  return scan(sf, sf, fieldsSeparately)
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

/** The display utilities that show an element a `hidden` class hides. */
const DISPLAY = /^(block|inline-block|inline|flex|inline-flex|grid|inline-grid|table|inline-table|table-\S+|flow-root|contents|list-item)$/
/** What both scans need to know about one JSX element: whether a user can Tab to it, whether it can take focus at
    all (a `tabIndex={-1}` element still takes a click's or a script's), and whether @tailwindcss/forms styles it. `linkNames` are next/link's default export under the names the file imports it as. */
function classify(node: ts.JsxOpeningElement | ts.JsxSelfClosingElement, sf: ts.SourceFile, linkNames: Set<string>) {
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
  // Out of the Tab order, an element still takes a click's focus, unless it is display:none: a static `hidden`
  // attribute, or a literal className whose only display class is `hidden`, as the waitlist honeypot's is. Any other
  // display class (`md:block`, `!block`, `[display:block]`) may show it, and a className read any other way may hold
  // one, so either fails the exemption.
  const hiddenAttr = attr('hidden')
  const init = attr('className')?.initializer
  const expr = init && ts.isJsxExpression(init) ? init.expression : init
  const literal = expr && (ts.isStringLiteral(expr) || ts.isNoSubstitutionTemplateLiteral(expr)) ? expr.text : ''
  const classes = literal.split(/\s+/).filter(Boolean)
  const shows = (t: string) => {
    const utility = splitClass(t).utility.replace(/^!/, '')
    return t !== 'hidden' && (DISPLAY.test(utility) || utility.startsWith('[display:'))
  }
  const displayNone = (!!hiddenAttr && settled(hiddenAttr) && !hiddenAttr.initializer) || (classes.includes('hidden') && !classes.some(shows))
  // A display:none element takes no focus at all, in the Tab order or out of it (`<input hidden />`).
  const focusable = !displayNone && (tabbable || (removed && !staticallyDisabled))
  const typeAttr = attr('type')?.initializer
  // Every field @tailwindcss/forms styles: a textarea, a select, and an input that is not a button or
  // a hidden, file, range or colour control (a missing or dynamic type counts as a field).
  const field =
    tag === 'textarea' ||
    tag === 'select' ||
    (tag === 'input' && !(typeAttr && ts.isStringLiteral(typeAttr) && NOT_FORMS_STYLED.includes(typeAttr.text)))
  return { tag, attr, tabbable, focusable, field, spread, unstylable }
}

function scan(root: ts.Node, sf: ts.SourceFile, fieldsSeparately = false): { stops: number; findings: Finding[] } {
  // next/link's default export under whatever name the file imports it as.
  const linkNames = defaultImportNames(sf, (m) => m === 'next/link')
  const ctx = classContext(sf)
  const findings: Finding[] = []
  let stops = 0
  const visit = (node: ts.Node): void => {
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
      const { tag, attr, tabbable, field, spread, unstylable } = classify(node, sf, linkNames)
      if (tabbable && !(fieldsSeparately && field)) {
        stops += 1
        const line = sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
        const className = attr('className')
        const tokens = classTokens(className?.initializer, ctx)
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

/** The DS field module: its fields are held by tests/unit/inputClassesNoOverrides.spec.tsx (each `inputClasses()`
    combination and the Input, Textarea and Select components take the forms ring off and draw the DS ring). */
const FIELD_FACTORY = 'components/ui/Input.tsx'
/** The DS ring tokens, pinned, each light one with the dark token it pairs with: `ring-brand` with `ring-brand-dark`,
    and `ring-error` with `ring-error-dark`. A misspelt
    token generates no CSS, and a `ring-*` key added to the theme later need not draw a ring (`ring-none: 'none'`), so
    only these count; the describe below holds each to a visible shadow in tailwind.config.js. */
const DARK_RING: Record<string, string> = { 'ring-brand': 'ring-brand-dark', 'ring-error': 'ring-error-dark' }
const RING_TOKENS = new Set([...Object.keys(DARK_RING), ...Object.values(DARK_RING)])
const THEME_SHADOWS = resolveConfig(createRequire(import.meta.url)(path.join(ROOT, 'tailwind.config.js')) as Config).theme
  .boxShadow as Record<string, string>
/** A field's DS rings as `state token` pairs: in light, a pinned light token (`focus:shadow-ring-brand` → `focus
    ring-brand`); in dark, the light token whose pinned twin it is (`dark:focus:shadow-ring-brand-dark` → `focus
    ring-brand`), so the light token repeated under `dark:` is no twin. */
function rings(tokens: string[], dark: boolean): string[] {
  return tokens.flatMap((t) => {
    const m = t.match(dark ? /^dark:(focus|focus-visible):!?shadow-(\S+)$/ : /^(focus|focus-visible):!?shadow-(\S+)$/)
    if (!m) return []
    const light = dark ? Object.keys(DARK_RING).filter((k) => DARK_RING[k] === m[2]) : m[2] in DARK_RING ? [m[2]] : []
    return light.map((token) => `${m[1]} ${token}`)
  })
}
/** A theme's DS rings when they are more than one, from `rings()`'s `state token` pairs: `focus` and `focus-visible`
    both match a keyboard focus, so of two rings across them, as within one, the later in the stylesheet shows. */
function doubledRings(pairs: string[]): string[] {
  const unique = [...new Set(pairs)]
  return new Set(unique.map((pair) => pair.split(' ')[1])).size > 1 ? [unique.join(', ')] : []
}
/** The properties a focus ring is drawn with: the box-shadow, the shadow `shadow-ring-*` sets, and the ring variables the
    forms plugin and Tailwind's `ring-*` set. */
const SHADOW_PROPS = new Set(['box-shadow', '--tw-shadow', '--tw-shadow-colored', '--tw-ring-shadow', '--tw-ring-offset-shadow', '--tw-ring-offset-width', '--tw-ring-inset'])
const TAILWIND_CONFIG = createRequire(import.meta.url)(path.join(ROOT, 'tailwind.config.js')) as Config
/** What each class declares, read off Tailwind's own compile of it (this config, globals.css as input): property names, by
    class. A class Tailwind does not generate declares nothing. */
const declared = new Map<string, Set<string>>()
const unescapeCss = (s: string) =>
  s.replace(/\\([0-9a-fA-F]{1,6}) ?|\\(.)/g, (_, hex: string | undefined, ch: string | undefined) => (hex ? String.fromCodePoint(parseInt(hex, 16)) : ch!))
async function loadDeclarations(tokens: string[]): Promise<void> {
  const missing = [...new Set(tokens)].filter((t) => !declared.has(t))
  if (!missing.length) return
  for (const t of missing) declared.set(t, new Set())
  const from = path.join(ROOT, 'app/globals.css')
  const result = await postcss([tailwindcss({ ...TAILWIND_CONFIG, content: [{ raw: missing.join(' '), extension: 'html' }], safelist: [] })]).process(
    readFileSync(from, 'utf8'),
    { from },
  )
  result.root.walkRules((rule) => {
    // A utility's own class can sit anywhere in its rule's selector: first in `.focus\:ring-0:focus`, last in
    // `.group:focus-within .group-focus-within\:\!shadow-none` and `.peer:focus ~ .peer-focus\:shadow-none`. Every class
    // in it that is a requested token takes the rule's declarations; a bare marker (`group`) declares nothing of its
    // own, carries no variant, and so never competes.
    for (const m of rule.selector.matchAll(/\.((?:\\[0-9a-fA-F]{1,6} ?|\\.|[\w-])+)/g)) {
      const props = declared.get(unescapeCss(m[1]))
      if (props) rule.walkDecls((d) => void props.add(d.prop))
    }
  })
}
/** A class's variants and its utility, split at the colons outside brackets and parentheses, as Tailwind reads them:
    `supports-[selector(:focus-visible)]:focus:[box-shadow:none]` → [`supports-[selector(:focus-visible)]`, `focus`] and
    `[box-shadow:none]`. */
function splitClass(token: string): { variants: string[]; utility: string } {
  const variants: string[] = []
  let depth = 0
  let start = 0
  for (let i = 0; i < token.length; i += 1) {
    const c = token[i]
    if (c === '[' || c === '(') depth += 1
    else if (c === ']' || c === ')') depth -= 1
    else if (c === ':' && depth === 0) {
      variants.push(token.slice(start, i))
      start = i + 1
    }
  }
  return { variants, utility: token.slice(start) }
}

/**
 * The classes on a field that styles itself which draw on its focus ring beside the reset and the DS ring: any class in
 * a state (any variant at all: focus, hover, a `supports-[…]` query) or marked `!important` whose compiled rule sets the
 * box-shadow or a ring variable (`focus:ring-2`, `focus:[box-shadow:none]`, `focus-visible:shadow-none`). It fails
 * closed rather than deciding which states can hold with focus, and reads what Tailwind declares, not the class's
 * spelling. Only a resting shadow passes (a focus-state ring outranks it), and a ring colour (`ring-brand`) sets only
 * the colour, which the zeroed ring never shows.
 */
function competingRings(tokens: string[]): string[] {
  return tokens.filter((t) => {
    const { variants, utility } = splitClass(t)
    // The reset, and a DS ring rings() counts: a pinned token in its own theme. One in the other theme
    // (`focus:shadow-ring-brand-dark`, a dropped `dark:`) draws over the ring like any other shadow.
    if (FORMS_RING_OFF.includes(t) || rings([t], false).length || rings([t], true).length) return false
    const stated = variants.length > 0 || utility.startsWith('!')
    return stated && [...(declared.get(t) ?? [])].some((prop) => SHADOW_PROPS.has(prop))
  })
}

/** A self-styled field's classes, read strictly: a string, a template with no `${…}`, or `cx`/`clsx` of those. Unlike the
    chrome scan, which ignores a dynamic part, a `${…}`, a condition or a variable here could add a class that draws on the
    ring (`focus:[box-shadow:none]`), so the className is unreadable. Every field in the app writes its classes this way. */
function strictTokens(init: ts.JsxAttributeValue | undefined, isJoiner: (callee: ts.Expression) => boolean): string[] | null {
  const read = (e: ts.Expression): string[] | null => {
    if (ts.isStringLiteral(e) || ts.isNoSubstitutionTemplateLiteral(e)) return e.text.split(/\s+/).filter(Boolean)
    if (ts.isParenthesizedExpression(e)) return read(e.expression)
    if (ts.isCallExpression(e) && isJoiner(e.expression)) {
      const parts = e.arguments.map(read)
      return parts.every((part): part is string[] => part !== null) ? parts.flat() : null
    }
    return null
  }
  const expr = init && (ts.isJsxExpression(init) ? init.expression : init)
  return expr ? read(expr) : null
}


/** `@/components/ui` and `../ui/Input` alike, as a path under frontend/ without extension; a package stays as is. */
function moduleKey(file: string, specifier: string): string {
  let key = specifier
  if (specifier.startsWith('@/')) key = specifier.slice(2)
  else if (specifier.startsWith('.')) key = path.posix.normalize(path.posix.join(path.posix.dirname(file), specifier))
  else return specifier
  key = key.replace(/\.(tsx?|js)$/, '')
  return key === 'components/ui' ? 'components/ui/index' : key
}

/** The names a file imports from the given modules (`{ 'components/ui/Input': ['inputClasses'] }`, 'default' for a
    default import), each as the predicate "this expression is that import": a reference with no local binding of the
    name shadowing it, or, unless `namespaces` is false, a member of a namespace import of the module (`UI.Input` after
    `import * as UI`). A page's own helper of that name, or one imported from elsewhere, is not the import. */
function importedName(sf: ts.SourceFile, wanted: Record<string, string[]>, namespaces = true): (callee: ts.Expression) => boolean {
  const resolve = bindingResolver(sf)
  const imported = new Set<string>()
  const members = new Map<string, string[]>()
  for (const st of sf.statements) {
    if (!ts.isImportDeclaration(st) || !ts.isStringLiteral(st.moduleSpecifier)) continue
    const names = wanted[moduleKey(sf.fileName, st.moduleSpecifier.text)]
    if (!names) continue
    const clause = st.importClause
    if (clause?.name && names.includes('default')) imported.add(clause.name.text)
    const named = clause?.namedBindings
    if (named && ts.isNamespaceImport(named) && namespaces) members.set(named.name.text, names)
    if (named && ts.isNamedImports(named)) {
      for (const el of named.elements) if (names.includes((el.propertyName ?? el.name).text)) imported.add(el.name.text)
    }
  }
  return (callee) =>
    ts.isIdentifier(callee)
      ? imported.has(callee.text) && !resolve(callee)
      : ts.isPropertyAccessExpression(callee) &&
        ts.isIdentifier(callee.expression) &&
        !!members.get(callee.expression.text)?.includes(callee.name.text) &&
        !resolve(callee.expression)
}
/** What a field's `style` prop does to its focus ring: nothing (no prop, or an object literal of other properties), or
    an inline box-shadow or ring variable, which outranks every class and so takes the DS ring off (`style={{ boxShadow:
    'none' }}`). Anything the scan cannot read key by key (a variable, a spread, a shorthand) fails closed. */
function inlineRing(attr: ts.JsxAttribute | undefined): string | null {
  if (!attr) return null
  const expr = attr.initializer && ts.isJsxExpression(attr.initializer) ? attr.initializer.expression : undefined
  if (!expr || !ts.isObjectLiteralExpression(expr)) return 'a style prop the scan cannot read'
  for (const p of expr.properties) {
    if (!ts.isPropertyAssignment(p) || !(ts.isIdentifier(p.name) || ts.isStringLiteral(p.name))) return 'a style prop the scan cannot read'
    if (p.name.text === 'boxShadow' || p.name.text.startsWith('--tw-')) return `an inline ${p.name.text}, which outranks the DS ring`
  }
  return null
}

/** The DS factory, and the class joiners a field's classes may be written with: clsx, and the DS `cx`. */
const FACTORY_IMPORTS = { 'components/ui/Input': ['inputClasses'], 'components/ui/index': ['inputClasses'] }
const JOINER_IMPORTS = { clsx: ['clsx', 'default'], 'components/ui/cx': ['cx'], 'components/ui/index': ['cx'] }
/** The DS field components, which pass a `style` prop on to their field through `...rest`. */
const FIELD_COMPONENT_IMPORTS = { 'components/ui/Input': ['Input', 'Textarea', 'Select'], 'components/ui/index': ['Input', 'Textarea', 'Select'] }

/** Whether a className is built by the DS factory: `inputClasses(…)` itself, a direct argument of `cx`/`clsx`, or a
    template's `${…}`. A call nested anywhere else (a branch of a condition) leaves the other branch a field that styles
    itself, so that className is read like any other (and a condition is unreadable). */
function factoryBuilt(init: ts.JsxAttributeValue, isFactory: (callee: ts.Expression) => boolean, isJoiner: (callee: ts.Expression) => boolean): boolean {
  const expr = ts.isJsxExpression(init) ? init.expression : init
  const factory = (e: ts.Expression) => ts.isCallExpression(e) && isFactory(e.expression)
  if (!expr) return false
  if (factory(expr)) return true
  if (ts.isCallExpression(expr) && isJoiner(expr.expression)) return expr.arguments.some(factory)
  if (ts.isTemplateExpression(expr)) return expr.templateSpans.some((span) => factory(span.expression))
  return false
}

/**
 * Every field @tailwindcss/forms styles, anywhere in a page, that can take focus (the plugin rings a field focused by a
 * click as much as by Tab, so `tabIndex={-1}` does not exempt one) and that its own className styles (not one built with `inputClasses(…)`, which the DS factory's gate holds): it takes the plugin's ring off
 * (FORMS_RING_OFF) and draws a DS ring in both themes. The reset without a ring would leave no focus indicator: the
 * full-text search's date inputs had no DS ring, so the plugin's blue ring was their only one in dark.
 *
 * What it cannot see: a DS field component, the factory or a joiner rebound to a local name (`const Field = multiline ?
 * Textarea : Input`), as inputClassesNoOverrides.spec.tsx cannot; no file in the app rebinds one.
 */
function unringedFields(source: string, fileName: string): { fields: number; factory: number; findings: Finding[]; raw: RawField[] } {
  const sf = parse(source, fileName)
  const linkNames = defaultImportNames(sf, (m) => m === 'next/link')
  // The factory's exemption hands its classes to inputClassesNoOverrides.spec.tsx, which follows named imports only, so a
  // namespace call (`UI.inputClasses()`) earns none: its className is read here, and fails closed as unreadable.
  const isFactory = importedName(sf, FACTORY_IMPORTS, false)
  const isJoiner = importedName(sf, JOINER_IMPORTS)
  const isFieldComponent = importedName(sf, FIELD_COMPONENT_IMPORTS)
  const findings: Finding[] = []
  const raw: RawField[] = []
  let fields = 0
  let factory = 0
  const visit = (node: ts.Node): void => {
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
      const { tag, attr, focusable, field, spread } = classify(node, sf, linkNames)
      const className = attr('className')
      // An inline style outranks every class, the factory's included, so it is read before the factory exemption, and
      // on a DS field component too, which passes it on to its field (`<Input style={{ boxShadow: 'none' }} />`), as it
      // does a props spread, which may carry one: on a component, a spread fails as on a raw field.
      const component = isFieldComponent(node.tagName as ts.Expression)
      const inline = (field && focusable) || component ? inlineRing(attr('style')) : null
      const at = sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
      if (inline) findings.push({ line: at, tag, problem: inline })
      if (component && spread) findings.push({ line: at, tag, problem: 'a props spread the scan cannot read' })
      // A spread may replace the className, the factory's included, so it is read before the factory exemption.
      if (field && focusable && !spread && className?.initializer && factoryBuilt(className.initializer, isFactory, isJoiner)) factory += 1
      else if (field && focusable) {
        fields += 1
        const line = sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
        const tokens = strictTokens(className?.initializer, isJoiner)
        const light = Array.isArray(tokens) ? rings(tokens, false) : []
        const dark = Array.isArray(tokens) ? rings(tokens, true) : []
        const missing = Array.isArray(tokens)
          ? [
              ...FORMS_RING_OFF.filter((t) => !tokens.includes(t)),
              ...(light.length ? [] : ['a focus:shadow-ring-* or focus-visible:shadow-ring-*']),
              ...(light.some((ring) => dark.includes(ring)) ? [] : ['its dark: twin in the same focus state']),
            ]
          : []
        // One DS ring per theme across its focus states: of two (`focus:shadow-ring-error`, or a `focus-visible:` one,
        // beside the brand ring), the later in the stylesheet shows, so a valid field would draw the error ring.
        const doubled = [...doubledRings(light), ...doubledRings(dark).map((r) => `dark: ${r}`)]
        if (spread) findings.push({ line, tag, problem: 'a props spread the scan cannot read' })
        else if (!className) findings.push({ line, tag, problem: "no className, so the forms plugin's blue ring is its focus ring" })
        else if (!Array.isArray(tokens)) findings.push({ line, tag, problem: 'a className the scan cannot read' })
        else {
          if (missing.length) findings.push({ line, tag, problem: `missing ${missing.join(', ')}` })
          if (doubled.length) findings.push({ line, tag, problem: `more than one DS ring across its focus states (${doubled.join('; ')})` })
          raw.push({ line, tag, tokens })
        }
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return { fields, factory, findings, raw }
}

/** A field that styles itself, with its static classes, for the declaration check (competingRings). */
interface RawField {
  line: number
  tag: string
  tokens: string[]
}

/** The field scan of one source, the declaration check included: the token findings and each competing ring setter, by line. */
async function fieldFindings(source: string, fileName: string): Promise<{ fields: number; factory: number; findings: Finding[] }> {
  const { fields, factory, findings, raw } = unringedFields(source, fileName)
  await loadDeclarations(raw.flatMap((f) => f.tokens))
  const competing = raw.flatMap(({ line, tag, tokens }) => {
    const extra = competingRings(tokens)
    return extra.length ? [{ line, tag, problem: `${extra.join(' ')} sets the box-shadow or a ring in a state, beside the reset and the DS ring` }] : []
  })
  return { fields, factory, findings: [...findings, ...competing].sort((x, y) => x.line - y.line) }
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

  it('every page and the feature modules it reaches: each control carries a ring in both themes, but the residue', () => {
    // Page/feature markup is the added scope. Shared composition helpers (Card, CompanyLogo,
    // RetryButton) accept props and are not raw page controls; their existing owning gates remain.
    const pages = chromeFiles(PAGE_ROOTS).filter((file) => !discovered.includes(file)
      && (file.startsWith('app/') || file.startsWith('features/') || file === 'components/ui/Switch.tsx'))
    for (const file of ['app/pricing/page.tsx', 'app/company/[ticker]/page-client.tsx', 'features/settings/components/ConnectedAccounts.tsx', 'features/settings/components/NotificationPreferencesForm.tsx', 'features/admin/components/InviteRow.tsx', 'features/admin/components/CopyLinkButton.tsx', 'features/admin/components/EmailChipsInput.tsx', 'features/admin/components/ShareInvite.tsx', 'features/admin/components/FeedbackRow.tsx', 'features/watchlist/components/WatchlistAddSearch.tsx', 'features/filings/components/copilot/AskCopilotRail.tsx', 'components/ui/Switch.tsx']) {
      expect(pages, 'the page graph must reach its controls').toContain(file)
    }
    const found = new Map<string, string[]>()
    for (const file of pages) {
      const findings = missingRings(readFileSync(path.join(ROOT, file), 'utf8'), file, true).findings
      if (findings.length) found.set(file, findings.map((f) => `${file}:${f.line} <${f.tag}> ${f.problem}`))
    }
    const problems: string[] = []
    for (const [file, lines] of found) {
      const allowed = RING_RESIDUE[file] ?? 0
      if (lines.length > allowed) problems.push(`${allowed ? `${file} has ${lines.length} ringless stops, ${allowed} listed` : `${file} is not in RING_RESIDUE`}:\n  ${lines.join('\n  ')}`)
      else if (lines.length < allowed) problems.push(`${file} has ${lines.length} ringless stops, ${allowed} listed: lower its RING_RESIDUE count`)
    }
    for (const file of Object.keys(RING_RESIDUE)) if (!found.has(file)) problems.push(`${file} has no ringless stop left: delete its RING_RESIDUE line`)
    expect(problems).toEqual([])
  }, 30_000) // it reads every route's page and the modules each reaches; the default 5s times out on a loaded box

  it('the ring residue only shrinks', () => {
    const stops = Object.values(RING_RESIDUE).reduce((sum, n) => sum + n, 0)
    // Equality, not a ceiling: a PR that shrinks the list lowers the cap in the same commit.
    expect(Object.keys(RING_RESIDUE).length, 'RING_RESIDUE changed its files: move RING_RESIDUE_MAX.files with it in the same commit').toBe(RING_RESIDUE_MAX.files)
    expect(stops, 'RING_RESIDUE changed its stops: move RING_RESIDUE_MAX.stops with it in the same commit').toBe(RING_RESIDUE_MAX.stops)
  })

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
      import { buttonVariants } from '@/components/ui'
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
    expect(block('destructive')).toContain('dark:focus-visible:shadow-ring-error-dark')
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

  // The count control's recipe (components/ui/countControl.ts) and a const the file declares are read by what they
  // hold: the recipe by calling it, so a ring dropped from its INK flags every count control here and in the app.
  it('the scan reads the count control recipe and a const by what they hold (a self-check on fixed sources)', () => {
    const ring = 'focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark'
    expect(COUNT_KINDS, 'the kinds countControl.ts declares').toEqual(expect.arrayContaining(['button', 'link', 'inline', 'summary']))
    const src = `
      import NextLink from 'next/link'
      import { countControlClass, cx } from '@/components/ui'
      import { countControlClass as countControl } from '@/components/ui/countControl'
      import * as UI from '@/components/ui'
      const RING = '${ring}'
      const LOCATOR = cx('inline-flex gap-1', countControl('link'))
      let LOOSE = '${ring}'
      export function A({ kind, open }: { kind: CountControlKind; open: boolean }) {
        const own = cx('h-8 px-2', RING) as string
        return (
          <nav>
            <NextLink href="/a" className={cx('rounded', countControlClass('link'))}>See all 4 companies</NextLink>
            <NextLink href="/b" className={cx('rounded')}>See all 4 companies</NextLink>
            <button className={cx('h-8 px-2', RING, open ? 'a' : 'b')}>Reviewed</button>
            <button className={cx('h-8 px-2', open ? 'a' : 'b')}>Reviewed</button>
            <a href="/c" className={LOCATOR}>Item 7</a>
            <summary className={UI.countControlClass(kind)}>Show 3 figures</summary>
            <button className={own}>Follow up</button>
            <button className={cx('h-8 px-2', LOOSE)}>Reviewed</button>
          </nav>
        )
      }
      export function B() {
        const countControlClass = (kind: string) => kind
        return <a href="/d" className={countControlClass('link')}>See all 4 companies</a>
      }
      export function C() {
        const buttonVariants = () => 'px-2'
        return <a href="/e" className={buttonVariants()}>Open</a>
      }`
    const { stops, findings } = missingRings(src)
    expect(stops).toBe(10)
    expect(findings.map((f) => `${f.line} <${f.tag}> ${f.problem}`)).toEqual([
      // The recipe removed from the count link, and the const removed from the button.
      '14 <NextLink> missing focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
      '16 <button> missing focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
      // A let may be reassigned, so its ring is not read.
      '20 <button> missing focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
      // A local function of the recipe's name is not the recipe, and one of the button factory's name is not the factory.
      '26 <a> a className the scan cannot read',
      '30 <a> a className the scan cannot read',
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
      }
      import { buttonVariants } from '@/components/ui/Button'`
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

describe('every field the forms plugin styles takes its ring off and draws the DS ring, app-wide', () => {
  it('the app’s own fields', async () => {
    let fields = 0
    let factory = 0
    const findings: string[] = []
    for (const file of appSources().filter((f) => f !== FIELD_FACTORY)) {
      const result = await fieldFindings(readFileSync(path.join(ROOT, file), 'utf8'), file)
      fields += result.fields
      factory += result.factory
      findings.push(...result.findings.map((f) => `${file}:${f.line} <${f.tag}> ${f.problem}`))
    }
    // A reader that finds nothing must not pass: the app styles a handful of fields itself and builds the rest with inputClasses().
    // Four since the four hand-rolled checkboxes became the one components/ui/Checkbox.tsx (ADM-37).
    expect(fields, 'fields that style themselves').toBeGreaterThanOrEqual(4)
    expect(factory, 'fields built with inputClasses()').toBeGreaterThanOrEqual(15)
    expect(findings).toEqual([])
  })

  it('every DS ring draws at least 3:1 focus ink on its theme’s page, panel and tinted controls', () => {
    const colors = resolveConfig(TAILWIND_CONFIG).theme.colors as Record<string, Record<string, string>>
    const rgba = (color: string): number[] => color.startsWith('#')
      ? [...color.slice(1).match(/../g)!.map((v) => parseInt(v, 16)), 1]
      : color.match(/[\d.]+/g)!.map(Number)
    const over = (ink: number[], ground: number[]): number[] => ink.slice(0, 3).map((v, i) => v * (ink[3] ?? 1) + ground[i] * (1 - (ink[3] ?? 1)))
    const luminance = (rgb: number[]) => rgb.slice(0, 3).map((v) => {
      const s = v / 255
      return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
    }).reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i], 0)
    for (const token of [...RING_TOKENS, 'ring-brand-inset', 'ring-brand-inset-dark']) {
      const m = THEME_SHADOWS[token]?.match(/^(?:inset )?0 0 0 [1-9]\d*px (rgba?\([\d.,\s]+\))$/)
      expect(m, token).toBeTruthy()
      const dark = token.endsWith('-dark')
      const theme = dark ? 'dark' : 'light'
      const page = rgba(colors.background[theme])
      const panel = rgba(colors.panel[theme])
      const grounds = [page, panel, ...(dark ? [page, panel].flatMap((ground) => [
        over(rgba('rgba(255,255,255,0.05)'), ground),
        over(rgba(colors.brand['weak-dark']), ground),
        over(rgba(colors.brand['border-dark']), ground),
      ]) : [rgba('#FFFFFF'), rgba(colors.brand.weak), over(rgba('rgba(207,224,214,0.6)'), panel)])]
      for (const ground of grounds) {
        const levels = [luminance(over(rgba(m![1]), ground)), luminance(ground)].sort((a, b) => b - a)
        expect((levels[0] + 0.05) / (levels[1] + 0.05), `${token} on ${ground.join(',')}`).toBeGreaterThanOrEqual(3)
      }
    }
  })

  it('the field scan takes only the DS factory, under any import name, for inputClasses()', () => {
    const at = (source: string, fileName = 'features/fixture/Page.tsx') => {
      const { factory, findings } = unringedFields(source, fileName)
      return { factory, findings: findings.map((f) => `${f.line} ${f.problem}`) }
    }
    const field = 'export const F = () => <input type="text" className={inputClasses()} />'
    // The factory under its own name, an alias, from the barrel, and through a relative path.
    expect(at(`import { inputClasses } from '@/components/ui/Input'\n${field}`)).toEqual({ factory: 1, findings: [] })
    expect(at(`import { inputClasses as field } from '@/components/ui'\nexport const F = () => <input className={field()} />`)).toEqual({ factory: 1, findings: [] })
    expect(at(`import { inputClasses } from '../../components/ui/Input'\n${field}`)).toEqual({ factory: 1, findings: [] })
    // A page's own helper of that name, one imported from elsewhere, and a local binding shadowing the import are not.
    const unread = { factory: 0, findings: ['2 a className the scan cannot read'] }
    expect(at(`const inputClasses = () => 'border'\n${field}`)).toEqual(unread)
    expect(at(`import { inputClasses } from '@/lib/forms'\n${field}`)).toEqual(unread)
    expect(
      at(`import { inputClasses } from '@/components/ui/Input'\nexport function F({ inputClasses }: { inputClasses: () => string }) {\n  return <input className={inputClasses()} />\n}`),
    ).toEqual({ factory: 0, findings: ['3 a className the scan cannot read'] })
    // The joiners too: a page's own `cx` (which may drop every class) is not the DS joiner, nor is one from elsewhere.
    const ring = 'focus:border-brand focus:shadow-ring-brand dark:focus:border-brand-dark dark:focus:shadow-ring-brand-dark focus:ring-0 focus:ring-offset-0'
    const joined = (imp: string) => at(`${imp}\nexport const F = () => <input type="date" className={cx('border', '${ring}')} />`).findings
    expect(joined(`import { cx } from '@/components/ui/cx'`)).toEqual([])
    expect(joined(`import { cx } from '@/components/ui'`)).toEqual([])
    expect(joined(`import cx from 'clsx'`)).toEqual([])
    expect(joined(`const cx = (...c: string[]) => ''`)).toEqual(['2 a className the scan cannot read'])
    expect(joined(`import { cx } from '@/lib/strings'`)).toEqual(['2 a className the scan cannot read'])
    // And the field components: a page's own `Input` is not the DS one, so its style is its own business.
    const styled = `export const F = () => <Input style={{ boxShadow: 'none' }} />`
    expect(at(`import { Input } from '@/components/ui'\n${styled}`).findings).toEqual(['2 an inline boxShadow, which outranks the DS ring'])
    expect(at(`const Input = (p: { style?: object }) => <div {...p} />\n${styled}`).findings).toEqual([])
    // A namespace import of the DS module reaches the same component and joiner, but not the factory exemption: the
    // override gate cannot follow `UI.inputClasses()`, so the classes beside it would go unchecked by both.
    expect(at(`import * as UI from '@/components/ui'\nexport const F = () => <UI.Input style={{ boxShadow: 'none' }} />`).findings).toEqual([
      '2 an inline boxShadow, which outranks the DS ring',
    ])
    expect(at(`import * as UI from '@/components/ui'\nexport const F = () => <input type="date" className={UI.cx('border', '${ring}')} />`).findings).toEqual([])
    expect(at(`import * as UI from '@/components/ui'\nexport const F = () => <input type="text" className={UI.cx(UI.inputClasses(), 'focus:[box-shadow:none]')} />`)).toEqual({
      factory: 0,
      findings: ['2 a className the scan cannot read'],
    })
    expect(at(`import * as UI from '@/lib/ui'\nexport const F = () => <input type="text" className={UI.inputClasses()} />`).findings).toEqual(['2 a className the scan cannot read'])
  })

  it('the field scan catches what it is for (a self-check on fixed sources)', async () => {
    const reset = 'focus:ring-0 focus:ring-offset-0'
    const field = `focus:border-brand focus:shadow-ring-brand dark:focus:border-brand-dark dark:focus:shadow-ring-brand-dark ${reset}`
    const control = `${reset} focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark`
    const src = `
      import { inputClasses, Input, Textarea } from '@/components/ui/Input'
      import { clsx } from 'clsx'
      export function F({ c, busy, rest }: Props) {
        return (
          <>
            <input type="checkbox" className="h-4 w-4 focus:shadow-ring-brand" />
            <input type="checkbox" className="h-4 w-4 ${control}" />
            <input type="date" className="border focus:border-brand focus:outline-none" />
            <input type="date" className="border ${field}" />
            <input type="date" className="border ${reset}" />
            <textarea className="focus:shadow-ring-brand ${reset}" />
            <select className={clsx(inputClasses({ select: true }), c)} />
            <input className={\`\${inputClasses()} mt-2\`} />
            <input type="text" className={c} />
            <input type="email" />
            <input type="text" {...rest} />
            <input type="submit" className="p-2" />
            <input type="checkbox" disabled className="h-4 w-4" />
            <input type="text" tabIndex={-1} className="hidden" />
            <input type="radio" disabled={busy} className="h-4 w-4" />
            <input type="date" className={busy ? inputClasses() : 'border px-2'} />
            <input type="date" className="border focus-visible:shadow-ring-brand dark:focus:shadow-ring-brand-dark ${reset}" />
            <input type="date" className="border focus:shadow-ring-brand-dark dark:focus:shadow-ring-brand-dark ${reset}" />
            <input type="date" className="border focus:shadow-ring-brand dark:focus:shadow-ring-brnad-dark ${reset}" />
            <input type="date" className="border focus:shadow-ring-brnad dark:focus:shadow-ring-brand-dark ${reset}" />
            <input type="text" className={inputClasses()} {...rest} />
            <input type="date" className="border focus:shadow-ring-none dark:focus:shadow-ring-none ${reset}" />
            <input type="date" className="border focus:shadow-ring-brand dark:focus:shadow-ring-brand ${reset}" />
            <input type="date" className="border focus:shadow-ring-error dark:focus:shadow-ring-error-dark ${reset}" />
            <input type="date" className="border ${field} focus:ring-2" />
            <input type="date" className="border ${field} dark:focus:ring-offset-2 ring-brand" />
            <input type="date" className="border ${field} focus:[box-shadow:none]" />
            <input type="date" className="border ${field} focus-visible:shadow-none shadow-sm !shadow-none" />
            <input type="date" className={\`border ${field} \${c}\`} />
            <input type="date" className={clsx('border', '${field}', busy && 'opacity-50')} />
            <input type="date" className={clsx('border', '${field}')} />
            <input type="date" className="border ${field} supports-[selector(:focus-visible)]:focus:[box-shadow:none]" />
            <input type="date" className="border ${field} hover:shadow-md" />
            <input type="date" className="border ${field} [box-shadow:0_0_0_1px_rgba(0,0,0,0.1)]" />
            <input type="date" className="border ${field} focus:shadow-ring-error" />
            <input type="date" className="border ${field} focus:shadow-ring-brand-dark" />
            <input type="date" className="border ${field} dark:focus:shadow-ring-brand" />
            <input type="date" tabIndex={-1} className="border focus:border-brand" />
            <input type="date" tabIndex={-1} className="hidden md:block" />
            <input type="date" className="border ${field}" style={{ boxShadow: 'none' }} />
            <input type="date" className="border ${field}" style={{ maxWidth: 200 }} />
            <input type="date" className="border ${field}" style={c} />
            <input className={inputClasses()} style={{ '--tw-shadow': '0 0 #0000' }} />
            <Input style={{ boxShadow: 'none' }} />
            <Textarea variant="composer" style={{ maxHeight: 120, overflowY: 'auto' }} />
            <Input {...{ style: { boxShadow: 'none' } }} />
            <input type="date" className="border ${field} focus-visible:shadow-ring-error dark:focus-visible:shadow-ring-error-dark" />
            <input type="date" className="border ${field} group-focus-within:!shadow-none peer-focus:shadow-none" />
            <input type="date" tabIndex={-1} className="hidden !block" />
            <input type="date" tabIndex={-1} className={\`hidden \${c}\`} />
            <input hidden type="text" />
          </>
        )
      }`
    const { fields, factory, findings } = await fieldFindings(src, 'page.tsx')
    const twin = 'its dark: twin in the same focus state'
    const competing = 'sets the box-shadow or a ring in a state, beside the reset and the DS ring'
    const ring = 'a focus:shadow-ring-* or focus-visible:shadow-ring-*'
    expect(factory).toBe(3)
    expect(fields).toBe(41)
    expect(findings.map((f) => `${f.line} <${f.tag}> ${f.problem}`)).toEqual([
      `7 <input> missing focus:ring-0, focus:ring-offset-0, ${twin}`,
      `9 <input> missing focus:ring-0, focus:ring-offset-0, ${ring}, ${twin}`,
      `11 <input> missing ${ring}, ${twin}`,
      `12 <textarea> missing ${twin}`,
      '15 <input> a className the scan cannot read',
      "16 <input> no className, so the forms plugin's blue ring is its focus ring",
      '17 <input> a props spread the scan cannot read',
      `21 <input> missing focus:ring-0, focus:ring-offset-0, ${ring}, ${twin}`,
      // An inputClasses() call in one branch of a condition leaves the other branch styling the field itself.
      '22 <input> a className the scan cannot read',
      // A dark ring in another focus state than the light one, and a dark token standing in for the light ring.
      `23 <input> missing ${twin}`,
      `24 <input> missing ${ring}, ${twin}`,
      // ...and the dark token in light draws over whatever ring the field does have.
      `24 <input> focus:shadow-ring-brand-dark ${competing}`,
      // A misspelt token generates no CSS, so it is no ring, in either theme.
      `25 <input> missing ${twin}`,
      `26 <input> missing ${ring}, ${twin}`,
      // A spread may replace the factory's className, so the factory does not exempt it.
      '27 <input> a props spread the scan cannot read',
      // Only the pinned DS ring tokens count, not any `ring-*` key.
      `28 <input> missing ${ring}, ${twin}`,
      // The light ring repeated under `dark:` is no dark twin; ring-error is its own until a dark token exists (line 30).
      `29 <input> missing ${twin}`,
      `29 <input> dark:focus:shadow-ring-brand ${competing}`,
      // A ring width or offset beside the reset draws the plugin's ring again; a ring colour does not.
      // Any focus-state or !important class whose rule sets the box-shadow or a ring variable, read off Tailwind's compile:
      // a ring width or offset, an arbitrary box-shadow, a shadow utility. A ring colour and a resting shadow do not.
      `31 <input> focus:ring-2 ${competing}`,
      `32 <input> dark:focus:ring-offset-2 ${competing}`,
      `33 <input> focus:[box-shadow:none] ${competing}`,
      `34 <input> focus-visible:shadow-none !shadow-none ${competing}`,
      // A dynamic part could add a class that draws on the ring, so it is unreadable; a cx of literals is read (line 37).
      '35 <input> a className the scan cannot read',
      '36 <input> a className the scan cannot read',
      // Variants are split outside brackets, so a colon inside an arbitrary query hides no state; any state counts.
      `38 <input> supports-[selector(:focus-visible)]:focus:[box-shadow:none] ${competing}`,
      `39 <input> hover:shadow-md ${competing}`,
      // A resting arbitrary box-shadow (line 40) has no variant: the colon inside its brackets is not one.
      // Two DS rings in one focus state: the later in the stylesheet shows.
      '41 <input> more than one DS ring across its focus states (focus ring-brand, focus ring-error)',
      // A pinned token in the other theme (a dropped or a stray `dark:`) is a shadow like any other.
      `42 <input> focus:shadow-ring-brand-dark ${competing}`,
      `43 <input> dark:focus:shadow-ring-brand ${competing}`,
      // Out of the Tab order, but a click still focuses it, and the plugin rings it blue.
      `44 <input> missing focus:ring-0, focus:ring-offset-0, ${ring}, ${twin}`,
      // `hidden` shows again from md, so it can take focus there; the honeypot's bare `hidden` (line 24) never can.
      `45 <input> missing focus:ring-0, focus:ring-offset-0, ${ring}, ${twin}`,
      // An inline style outranks every class: a box-shadow or ring variable in it takes the ring off, the factory's
      // included (line 49); other properties pass (line 47), and a style the scan cannot read fails closed.
      '46 <input> an inline boxShadow, which outranks the DS ring',
      '48 <input> a style prop the scan cannot read',
      '49 <input> an inline --tw-shadow, which outranks the DS ring',
      // A DS field component passes its style on to its field: read like a raw field's (the composer's passes).
      '50 <Input> an inline boxShadow, which outranks the DS ring',
      // ...as it passes on a spread, which may carry one.
      '52 <Input> a props spread the scan cannot read',
      // `focus` and `focus-visible` both match a keyboard focus: a ring in each is two rings.
      '53 <input> more than one DS ring across its focus states (focus ring-brand, focus-visible ring-error; dark: focus ring-brand, focus-visible ring-error)',
      // A group or peer variant's selector leads with the marker, not the utility's own class.
      `54 <input> group-focus-within:!shadow-none peer-focus:shadow-none ${competing}`,
      // An important display class shows a hidden field as a variant does (line 45).
      `55 <input> missing focus:ring-0, focus:ring-offset-0, ${ring}, ${twin}`,
      // A dynamic part may show it too, so a hidden className read any way but as a literal earns no exemption.
      '56 <input> a className the scan cannot read',
      // A static `hidden` attribute (line 57) takes the field out of focus whatever its tabIndex: no finding.
    ])
  })
})
