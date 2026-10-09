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
 * to (a, button, input, select, textarea, summary, next/link's Link, anything with a tabIndex the scan
 * cannot prove negative: 0 or more, or a dynamic value such as a roving `tabIndex={selected ? 0 : -1}`,
 * and any contentEditable region the scan cannot prove off). Its className must carry the whole triple,
 * or be the DS factory `buttonVariants(…)`, which composes it (pinned below). A className the scan cannot
 * read (a variable, a call to anything else) fails: the ring has to be visible in the file. So does a
 * props spread on a host element or a Link, which may supply a tabIndex or a className. Dynamic `${…}`
 * parts of a template are ignored, so the triple must sit in the template's static text. The DS
 * components (<Button>, <Input>) are not scanned here: they own the recipe.
 *
 * A checkbox or radio also takes off @tailwindcss/forms' own focus ring (`focus:ring-0 focus:ring-offset-0`):
 * the plugin's base style draws a blue (#2563eb) ring with a white offset on any focus, and the shadow
 * utilities compose with it, so the triple alone shows the brand ring inside a blue one. A control that
 * is statically `disabled` is not a Tab stop.
 *
 * Scope: the chrome a keyboard user tabs through on every route, discovered rather than listed (see
 * CHROME_ROOTS): everything app/layout.tsx mounts (the site header with its menus, the footer, the
 * verification banner and prompt, the cookie-consent bar, the providers' error boundary and feedback
 * widget), every route layout, template or error boundary under app/ (the admin section's nav, the
 * root error fallback), the auth routes' shell and the page header, with every module they import. The
 * page header also renders the controls a page passes into its `actions` slot (the dashboard's "Log
 * out"), so every `<SecondaryHeader actions={…}>` in the app is scanned too, and its controls must be
 * written inline. A
 * page's other controls are not chrome: the filing identity strip's breadcrumb carries the recipe but
 * is outside this gate. This is the rule's one gate (AGENTS.md §4): no e2e walk repeats it.
 */
const ROOT = path.resolve(__dirname, '../..')

/**
 * Where the site chrome is mounted: the root layout (header, footer, verification banner and prompt,
 * consent bar, and the providers' app-wide widgets, on every route), the auth routes' shell, and the
 * page header pages render. The scanned files are discovered from these: every .tsx module they reach,
 * transitively, through `@/` or relative imports and re-exports, .ts barrels included. The DS
 * primitives in components/ui are not followed: they own the recipe, and `buttonVariants` is pinned
 * below. A new banner, menu or widget the chrome imports is scanned without anyone listing it.
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

/** The third-party components `source` renders, as `module Tag`. */
function thirdPartyTags(source: string, fileName: string): string[] {
  const sf = parse(source, fileName)
  const modules = new Map<string, string>()
  for (const stmt of sf.statements) {
    if (!ts.isImportDeclaration(stmt) || !ts.isStringLiteral(stmt.moduleSpecifier)) continue
    const pkg = stmt.moduleSpecifier.text
    if (pkg.startsWith('@/') || pkg.startsWith('.')) continue
    const clause = stmt.importClause
    if (clause?.name) modules.set(clause.name.text, pkg)
    if (clause?.namedBindings && ts.isNamedImports(clause.namedBindings)) {
      for (const el of clause.namedBindings.elements) modules.set(el.name.text, pkg)
    }
    // A namespace import (`import * as Menu from '…'`) renders as <Menu.Root>.
    if (clause?.namedBindings && ts.isNamespaceImport(clause.namedBindings)) modules.set(clause.namedBindings.name.text, pkg)
  }
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
 * `export … from` that is not type-only, through `@/` or relative paths, including .ts modules such as
 * a barrel's index.ts. Only the .tsx modules are returned; a .ts module renders nothing itself.
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
  const seen = new Set<string>()
  const queue = [...roots]
  while (queue.length) {
    const file = queue.shift()!
    if (seen.has(file)) continue
    seen.add(file)
    const sf = parse(readFileSync(path.join(root, file), 'utf8'), file)
    for (const stmt of sf.statements) {
      const spec = ts.isImportDeclaration(stmt) && !stmt.importClause?.isTypeOnly ? stmt.moduleSpecifier
        : ts.isExportDeclaration(stmt) && !stmt.isTypeOnly ? stmt.moduleSpecifier
          : undefined
      if (!spec || !ts.isStringLiteral(spec)) continue
      const target = resolveImport(file, spec.text)
      if (target && !target.startsWith(`components${path.sep}ui${path.sep}`)) queue.push(target)
    }
  }
  return [...seen].filter((file) => file.endsWith('.tsx')).sort()
}

const RINGS = [
  ['focus-visible:outline-none', 'focus-visible:shadow-ring-brand', 'dark:focus-visible:shadow-ring-brand-dark'],
  ['focus:outline-none', 'focus:shadow-ring-brand', 'dark:focus:shadow-ring-brand-dark'],
]
/** @tailwindcss/forms rings a focused checkbox or radio itself; these take that ring off. */
const FORMS_RING_OFF = ['focus:ring-0', 'focus:ring-offset-0']
const INTRINSIC = new Set(['a', 'button', 'input', 'select', 'textarea', 'summary'])

interface Finding {
  line: number
  tag: string
  problem: string
}

/** The static class tokens of a className attribute, `'factory'` for buttonVariants(…), or null if unreadable. */
function classTokens(init: ts.JsxAttributeValue | undefined): string[] | 'factory' | null {
  if (!init) return null
  const expr = ts.isJsxExpression(init) ? init.expression : init
  if (!expr) return null
  if (ts.isStringLiteral(expr) || ts.isNoSubstitutionTemplateLiteral(expr)) return expr.text.split(/\s+/).filter(Boolean)
  if (ts.isTemplateExpression(expr)) {
    const text = [expr.head.text, ...expr.templateSpans.map((s) => s.literal.text)].join(' ')
    return text.split(/\s+/).filter(Boolean)
  }
  if (ts.isCallExpression(expr) && ts.isIdentifier(expr.expression) && expr.expression.text === 'buttonVariants') return 'factory'
  return null
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
      const removed = branches.length > 0 && branches.every((b) => b === 'negative')
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
        (!disabled.initializer ||
          (ts.isJsxExpression(disabled.initializer) && disabled.initializer.expression?.kind === ts.SyntaxKind.TrueKeyword))
      // A props spread on a host element or a Link (`<div {...getButtonProps()}>`) can supply a tabIndex and
      // a ringless className the scan cannot see, so the element counts as a stop and fails unread. A spread
      // on a component of our own is read in that component's file.
      const spread = (/^[a-z]/.test(tag) || linkNames.has(tag)) && node.attributes.properties.some(ts.isJsxSpreadAttribute)
      const tabbable =
        spread || ((INTRINSIC.has(tag) || linkNames.has(tag) || indexed || editableStop) && !removed && !staticallyDisabled)
      const typeAttr = attr('type')?.initializer
      const toggle = tag === 'input' && !!typeAttr && ts.isStringLiteral(typeAttr) && ['checkbox', 'radio'].includes(typeAttr.text)
      if (tabbable) {
        stops += 1
        const line = sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
        const className = attr('className')
        const tokens = classTokens(className?.initializer)
        if (spread) findings.push({ line, tag, problem: 'a props spread the scan cannot read' })
        else if (!className) findings.push({ line, tag, problem: 'no className, so the browser default outline' })
        else if (tokens === null) findings.push({ line, tag, problem: 'a className the scan cannot read' })
        else if (tokens !== 'factory' && !RINGS.some((ring) => ring.every((t) => tokens.includes(t)))) {
          findings.push({ line, tag, problem: `missing ${RINGS[0].filter((t) => !tokens.includes(t)).join(' ')}` })
        } else if (toggle && tokens !== 'factory' && !FORMS_RING_OFF.every((t) => tokens.includes(t))) {
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
    for (const file of ['components/Header.tsx', 'components/Footer.tsx', 'components/ThemeToggle.tsx', 'features/auth/components/UserMenu.tsx', 'features/notifications/components/NotificationBell.tsx', 'features/auth/components/VerificationBanner.tsx', 'components/CookieConsent.tsx', 'app/admin/layout.tsx', 'app/global-error.tsx']) {
      expect(discovered, file).toContain(file)
    }
    for (const file of Object.keys(NOT_SCANNED)) expect(discovered, `${file} is no longer chrome: drop its exemption`).toContain(file)
  })

  it('the discovery follows barrels and re-exports, and skips type-only imports', () => {
    const dir = mkdtempSync(path.join(os.tmpdir(), 'chrome-graph-'))
    const files: Record<string, string> = {
      'app/layout.tsx': "import { Banner, Menu } from '@/components/chrome'\nimport type { Props } from '@/components/types'",
      'components/chrome/index.ts': "export { Banner } from './Banner'\nexport * from './Menu'",
      'components/chrome/Banner.tsx': 'export const Banner = () => null',
      'components/chrome/Menu.tsx': 'export const Menu = () => null',
      'components/types.tsx': 'export type Props = object',
    }
    try {
      for (const [file, source] of Object.entries(files)) {
        mkdirSync(path.dirname(path.join(dir, file)), { recursive: true })
        writeFileSync(path.join(dir, file), source)
      }
      expect(chromeFiles(['app/layout.tsx'], dir)).toEqual(['app/layout.tsx', 'components/chrome/Banner.tsx', 'components/chrome/Menu.tsx'])
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })

  it('every third-party component the chrome renders is classified', () => {
    // The reader itself, on a fixed source: default, named and namespace imports all count; a local
    // module does not.
    const fixture = [
      "import Link from 'next/link'",
      "import { Toaster } from 'sonner'",
      "import * as Menu from '@radix-ui/react-menu'",
      "import { Local } from '@/components/Local'",
      'export const A = () => (<><Link href="/" /><Toaster /><Menu.Root><Menu.Item /></Menu.Root><Local /></>)',
    ].join('\n')
    expect(thirdPartyTags(fixture, 'fixture.tsx').sort()).toEqual([
      '@radix-ui/react-menu Menu.Item',
      '@radix-ui/react-menu Menu.Root',
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
            <div {...getButtonProps()}>headless</div>
            <NextLink {...linkProps} href="/r" className="${ring}">spread link</NextLink>
            <Menu {...menuProps} />
          </nav>
        )
      }`
    const { stops, findings } = missingRings(src)
    expect(stops).toBe(17)
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
      'div: a props spread the scan cannot read',
      'NextLink: a props spread the scan cannot read',
    ])
  })
})
