import { readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import { render } from '@testing-library/react'
import { createElement, type ComponentType } from 'react'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import * as uiBarrel from '@/components/ui'
import * as cardModule from '@/components/ui/Card'
import { bindingResolver } from './astBindings'
import { FRONTEND_ROOT, MARKER, competing, declCache, loadDeclarations, parseClass, stylesOthers } from './tailwindCompeting'

/**
 * Rule-12 gate for components/ui/Card.tsx (E283's follow-up, D-076): a class written on a <Card>, <CardHeader>,
 * <CardBody>, <CardFooter> or <CardTitle> never competes with one the component sets itself. `cx` does no
 * tailwind-merge, so of two utilities that set one property in one state, the one later in the STYLESHEET wins,
 * whatever the class order: the settings page's Delete account card wrote a loss hairline on top of Card's own, and in
 * dark Card's own `dark:border-white/10` won, so the card drew its hairline in light only (E283, fixed by Card's `tone`
 * in #1932). The same order decides a fill (`bg-white` over `bg-panel-light`), a corner (`rounded-2xl` loses to
 * `rounded-xl`: Card's `radius` exists for it), a section's padding (`py-3` loses to CardBody's `py-4`, `py-5` wins),
 * and a section's layout (`block` loses to CardHeader's `flex`). What Card offers, a caller sets through its props:
 * `tone`, `radius`, `elevation`, `interactive`.
 *
 * The scan reads the TypeScript AST of every .ts and .tsx under app/, components/, features/, hooks/ and lib/, except
 * Card.tsx, which defines them. A JSX element is one of the five when its tag names it as imported from
 * components/ui/Card or the components/ui barrel, under any alias or as a namespace member (`ui.Card`), unless a local
 * binding shadows the name. Its className is read as inputClassesNoOverrides.spec.tsx reads a class source: string
 * literals, templates, both branches of a condition, `&&`, `||`, `??`, `cx`/`clsx` arguments, arrays, object keys, a
 * same-file const, and a string the components/ui modules export. Its props are read as written; a prop the scan cannot
 * read as a literal (`elevation={e}`) is checked with every value CardProps allows, the unions read off Card.tsx itself,
 * and a CardProps member of any other type than a boolean or a union of string literals (`as` aside) fails, so a new
 * prop or value is checked as soon as it exists. The component's own classes come from rendering it with each
 * combination, never from a copied list. Tailwind itself (this config, globals.css as input) says what each class
 * declares, through ./tailwindCompeting, the half this gate shares with the field's; a logical property is read as the
 * physical one it sets in this left-to-right app (`ps-0` as padding-left), and a shorthand as its longhands
 * (`[background:white]` as background-color, among others).
 *
 * It fails, for each combination: (a) a class on the same variant chain as one of the component's that sets one
 * property to another value, whichever wins today, since a token's rename flips stylesheet order; (b) a class that sets
 * what the component sets under `dark:` or a screen it lacks, with no twin there (a bare `bg-white` loses to Card's
 * `dark:bg-panel-dark` in dark on specificity); (f) two chains that hold at once and leave the winner to variant order;
 * `!important`; and a class Tailwind does not generate. An arbitrary variant (`[@container(…)]:px-1.5`) fails when its
 * utility sets a property the component sets anywhere, or is marked important or unknown: the gate cannot place it,
 * and it is harmless otherwise. What passes by design: Tailwind's composite plumbing (`ring-1` composes with Card's
 * shadow rather than replacing it, as the pricing page's popular plan draws), a utility that styles only other elements
 * (`divide-y`, `space-y-5`), a class equal to the component's on its chain, and a layer on a state or screen the
 * component leaves alone (`sm:rounded-2xl`, `focus:bg-white` on a card that is not interactive), which the stylesheet
 * orders after the component's resting class whatever their names.
 *
 * A position the scan cannot follow fails closed: spread props, a className from a parameter or a prop, an import it
 * cannot read, one of the five (or a forwarder) used as a value rather than a tag (`createElement(Card)`, `as={Card}`,
 * `memo(Card)`), and a module of theirs loaded with import(). A cx() that joins a forwarded className with literals
 * still reads the literals. FORWARDERS lists each component that passes its caller's className on to a Card, traced
 * by hand: its call sites are read as a Card's are, against the classes of the Card it renders, and its unreadable
 * positions are listed at their count. Out of reach: a class set inside a component a Card renders as its child, and a
 * page that sets `dir="rtl"` (the logical properties would then name the other side).
 */

const ROOTS = ['app', 'components', 'features', 'hooks', 'lib']
const DEFINITION = 'components/ui/Card.tsx'
const COMPONENTS = { Card: cardModule.Card, CardHeader: cardModule.CardHeader, CardBody: cardModule.CardBody, CardFooter: cardModule.CardFooter, CardTitle: cardModule.CardTitle } as const
type ComponentName = keyof typeof COMPONENTS
type Combo = Record<string, string | boolean>
const MODULES: Record<string, Record<string, unknown>> = { 'components/ui/Card': cardModule, 'components/ui/index': uiBarrel }
const JOINERS: Record<string, string[]> = { clsx: ['clsx', 'default'], 'components/ui/cx': ['cx'], 'components/ui/index': ['cx'] }

/** Components that pass their caller's className on to a Card, each traced by hand, with the Card props they render it
    with. Their call sites are read as a Card's; their forwarding positions, which the scan cannot follow, are listed at
    their count. A new forwarder is listed here on purpose. */
interface Forwarder { file: string; module: string; name: string; combo: Combo; unread: number; how: string }
const FORWARDERS: Forwarder[] = [
  {
    file: 'components/ChartErrorBoundary.tsx', module: 'components/ChartErrorBoundary', name: 'ChartErrorBoundary', combo: {}, unread: 1,
    how: "<Card className={cx(this.props.className, 'p-cap-6 text-center')}>: a class component's prop",
  },
  {
    file: 'features/peers/components/SectorPeersCard.tsx', module: 'features/peers/components/SectorPeersCard', name: 'default', combo: {}, unread: 1,
    how: "<Card as=\"section\" className={cx(className, 'p-cap-6')}>: a parameter",
  },
  {
    file: 'features/peers/components/SectorPeers.tsx', module: 'features/peers/components/SectorPeers', name: 'default', combo: {}, unread: 1,
    how: "import('./SectorPeersCard'), rendered lazily with SectorPeers' own className, which its call sites give",
  },
]

class Unreadable extends Error {}

/** Card's props a caller sets as a literal: each a union of string literals or a boolean, read off CardProps in
    Card.tsx. `as` (an element) changes no class; a member of any other type fails, so it is not rendered at its
    default alone. */
function cardPropValues(): Record<string, (string | boolean)[]> {
  const file = path.join(FRONTEND_ROOT, DEFINITION)
  const sf = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const iface = sf.statements.find((s): s is ts.InterfaceDeclaration => ts.isInterfaceDeclaration(s) && s.name.text === 'CardProps')
  if (!iface) throw new Error('CardProps not found in Card.tsx')
  const out: Record<string, (string | boolean)[]> = {}
  for (const m of iface.members) {
    if (!ts.isPropertySignature(m) || !m.type || !ts.isIdentifier(m.name)) throw new Error(`a CardProps member the gate cannot read: ${m.getText(sf)}`)
    const name = m.name.text
    const t = m.type
    if (name === 'as') continue
    if (t.kind === ts.SyntaxKind.BooleanKeyword) out[name] = [false, true]
    else if (ts.isUnionTypeNode(t) && t.types.every((u) => ts.isLiteralTypeNode(u) && ts.isStringLiteral(u.literal))) {
      out[name] = t.types.map((u) => ((u as ts.LiteralTypeNode).literal as ts.StringLiteral).text)
    } else throw new Error(`CardProps.${name}: a type the gate cannot read (${t.getText(sf)}); write a boolean or a union of string literals`)
  }
  return out
}
const CARD_PROPS = cardPropValues()

interface Site { file: string; line: number; label: string; component: ComponentName; combos: Combo[]; added: string[] }
interface Scan { sites: Site[]; unreadable: { file: string; line: number; why: string }[] }

/** `@/components/ui`, `@/components/ui/` and `../ui/Card` alike, as a path under frontend/ without extension; a package
    stays as is. */
function moduleKey(file: string, specifier: string): string {
  let key = specifier
  if (specifier.startsWith('@/')) key = specifier.slice(2)
  else if (specifier.startsWith('.')) key = path.posix.normalize(path.posix.join(path.posix.dirname(file), specifier))
  else return specifier
  key = key.replace(/\/+$/, '').replace(/\.(tsx?|js)$/, '').replace(/\/index$/, '')
  return key === 'components/ui' ? 'components/ui/index' : key
}

function scanSource(file: string, text: string): Scan {
  const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const resolve = bindingResolver(sf)
  const imports = new Map<string, { module: string; name: string }>()
  for (const st of sf.statements) {
    if (!ts.isImportDeclaration(st) || !ts.isStringLiteral(st.moduleSpecifier) || !st.importClause) continue
    const from = moduleKey(file, st.moduleSpecifier.text)
    const clause = st.importClause
    if (clause.name) imports.set(clause.name.text, { module: from, name: 'default' })
    const named = clause.namedBindings
    if (named && ts.isNamedImports(named)) {
      for (const el of named.elements) imports.set(el.name.text, { module: from, name: (el.propertyName ?? el.name).text })
    } else if (named) imports.set(named.name.text, { module: from, name: '*' })
  }
  /** The import a reference names, unless a local binding shadows it. */
  const importOf = (id: ts.Identifier) => (resolve(id) ? undefined : imports.get(id.text))
  const forwarderOf = (module: string, name: string) => FORWARDERS.find((f) => f.module === module && f.name === name)
  /** What a tag or a reference names: one of the five, a forwarder, or nothing of this gate's. */
  const named = (node: ts.Expression): { component: ComponentName; forwarder?: Forwarder } | undefined => {
    if (ts.isIdentifier(node)) {
      const imp = importOf(node)
      if (!imp) return undefined
      if (imp.module in MODULES && imp.name in COMPONENTS) return { component: imp.name as ComponentName }
      const forwarder = forwarderOf(imp.module, imp.name)
      return forwarder ? { component: 'Card', forwarder } : undefined
    }
    if (ts.isPropertyAccessExpression(node) && ts.isIdentifier(node.expression)) {
      const imp = importOf(node.expression)
      const name = node.name.text
      if (!imp || imp.name !== '*') return undefined
      if (imp.module in MODULES && name in COMPONENTS) return { component: name as ComponentName }
      const forwarder = forwarderOf(imp.module, name)
      return forwarder ? { component: 'Card', forwarder } : undefined
    }
    return undefined
  }
  const isJoiner = (e: ts.Expression): boolean => {
    if (!ts.isIdentifier(e)) return false
    const imp = importOf(e)
    return !!imp && (JOINERS[imp.module] ?? []).includes(imp.name)
  }
  const lineOf = (n: ts.Node) => sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1
  const split = (s: string) => s.split(/\s+/).filter(Boolean)

  /** Every class an expression can contribute; throws when the gate cannot read it. A joiner's argument it cannot read
      is noted in `partial` instead, so the literals beside a forwarded className are still read. */
  const classSource = (e: ts.Expression, partial: string[], depth = 0): string[] => {
    if (depth > 20) throw new Unreadable('a class source nested too deep to follow')
    if (ts.isStringLiteral(e) || ts.isNoSubstitutionTemplateLiteral(e)) return split(e.text)
    if (ts.isTemplateExpression(e)) {
      const out = split(e.head.text)
      let before = e.head.text
      e.templateSpans.forEach((span, i) => {
        // `${a}${b}` glues a's last class to b's first, as `px-${n}` and `${a}mt-2` glue to text.
        if ((i > 0 && before === '') || /\S$/.test(before) || /^\S/.test(span.literal.text)) throw new Unreadable('a class built from pieces of a template')
        out.push(...classSource(span.expression, partial, depth + 1), ...split(span.literal.text))
        before = span.literal.text
      })
      return out
    }
    if (ts.isParenthesizedExpression(e) || ts.isAsExpression(e) || ts.isNonNullExpression(e) || ts.isSatisfiesExpression(e)) return classSource(e.expression, partial, depth + 1)
    if (ts.isConditionalExpression(e)) return [...classSource(e.whenTrue, partial, depth + 1), ...classSource(e.whenFalse, partial, depth + 1)]
    if (ts.isBinaryExpression(e)) {
      const op = e.operatorToken.kind
      if (op === ts.SyntaxKind.AmpersandAmpersandToken) return classSource(e.right, partial, depth + 1)
      if (op === ts.SyntaxKind.BarBarToken || op === ts.SyntaxKind.QuestionQuestionToken) return [...classSource(e.left, partial, depth + 1), ...classSource(e.right, partial, depth + 1)]
    }
    if (e.kind === ts.SyntaxKind.FalseKeyword || e.kind === ts.SyntaxKind.NullKeyword) return []
    if (ts.isCallExpression(e) && isJoiner(e.expression)) {
      return e.arguments.flatMap((a) => {
        try {
          return classSource(a, partial, depth + 1)
        } catch (err) {
          if (!(err instanceof Unreadable)) throw err
          partial.push(err.message)
          return []
        }
      })
    }
    if (ts.isArrayLiteralExpression(e)) return e.elements.flatMap((a) => classSource(a, partial, depth + 1))
    if (ts.isObjectLiteralExpression(e)) {
      return e.properties.flatMap((p) => {
        if (ts.isPropertyAssignment(p) && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name))) return split(p.name.text)
        throw new Unreadable('a class object with a key the gate cannot read')
      })
    }
    if (ts.isIdentifier(e)) {
      if (e.text === 'undefined') return []
      const binding = resolve(e)
      if (binding) {
        const list = binding.decl.parent
        const isConst = ts.isVariableDeclaration(binding.decl) && ts.isVariableDeclarationList(list) && (list.flags & ts.NodeFlags.Const) !== 0
        if (isConst && binding.init) return classSource(binding.init, partial, depth + 1)
        throw new Unreadable(`a class from \`${e.text}\`, which is not a const with an initializer`)
      }
      const imp = imports.get(e.text)
      const value = imp && MODULES[imp.module]?.[imp.name]
      if (typeof value === 'string') return split(value)
      throw new Unreadable(`a class from \`${e.text}\`, which the gate cannot read`)
    }
    throw new Unreadable(`a class from a ${ts.SyntaxKind[e.kind]}`)
  }

  /** A prop's values as written: one literal, or every value CardProps allows when it is not a literal. */
  const propValues = (name: string, a: ts.JsxAttribute): (string | boolean)[] => {
    const init = a.initializer
    if (!init) return [true]
    if (ts.isStringLiteral(init)) return [init.text]
    const e = ts.isJsxExpression(init) ? init.expression : undefined
    if (e?.kind === ts.SyntaxKind.TrueKeyword) return [true]
    if (e?.kind === ts.SyntaxKind.FalseKeyword) return [false]
    if (e && (ts.isStringLiteral(e) || ts.isNoSubstitutionTemplateLiteral(e))) return [e.text]
    return CARD_PROPS[name]
  }

  /** A reference that only names a type, an import or a tag, which renders nothing on its own. */
  const isTagOrType = (node: ts.Node): boolean => {
    const p = node.parent
    if (ts.isImportSpecifier(p) || ts.isImportClause(p) || ts.isNamespaceImport(p)) return true
    if ((ts.isJsxOpeningElement(p) || ts.isJsxSelfClosingElement(p) || ts.isJsxClosingElement(p)) && p.tagName === node) return true
    if (ts.isTypeQueryNode(p) || ts.isTypeReferenceNode(p) || ts.isQualifiedName(p) || ts.isExpressionWithTypeArguments(p)) return true
    return false
  }

  const scan: Scan = { sites: [], unreadable: [] }
  const visit = (node: ts.Node): void => {
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
      const hit = named(node.tagName as ts.Expression)
      if (hit) {
        const label = hit.forwarder ? `${hit.forwarder.name === 'default' ? path.basename(hit.forwarder.file, '.tsx') : hit.forwarder.name} → Card` : hit.component
        const partial: string[] = []
        try {
          let added: string[] = []
          let combos: Combo[] = [hit.forwarder ? hit.forwarder.combo : {}]
          for (const p of node.attributes.properties) {
            if (ts.isJsxSpreadAttribute(p)) throw new Unreadable(`props spread into a <${label}>`)
            const name = p.name.getText(sf)
            if (name === 'className') {
              const init = p.initializer
              if (!init) continue
              const e = ts.isStringLiteral(init) ? init : ts.isJsxExpression(init) ? init.expression : undefined
              if (!e) throw new Unreadable('a className the gate cannot read')
              added = classSource(e, partial)
            } else if (!hit.forwarder && hit.component === 'Card' && name in CARD_PROPS) {
              const values = propValues(name, p)
              combos = combos.flatMap((c) => values.map((v) => ({ ...c, [name]: v })))
            }
          }
          if (added.length) scan.sites.push({ file, line: lineOf(node), label, component: hit.component, combos, added })
        } catch (err) {
          if (!(err instanceof Unreadable)) throw err
          partial.push(err.message)
        }
        for (const why of partial) scan.unreadable.push({ file, line: lineOf(node), why })
      }
    } else if ((ts.isIdentifier(node) || ts.isPropertyAccessExpression(node)) && !isTagOrType(node) && !(ts.isIdentifier(node) && ts.isPropertyAccessExpression(node.parent) && node.parent.expression === node)) {
      const hit = named(node)
      if (hit) scan.unreadable.push({ file, line: lineOf(node), why: `<${hit.forwarder ? 'a forwarder' : hit.component}> used as a value, so where it renders and with what cannot be read` })
    } else if (ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword) {
      const [arg] = node.arguments
      const loaded = arg && ts.isStringLiteralLike(arg) ? moduleKey(file, arg.text) : undefined
      if (!loaded) scan.unreadable.push({ file, line: lineOf(node), why: 'an import() of a module the gate cannot read' })
      else if (loaded in MODULES || FORWARDERS.some((f) => f.module === loaded)) scan.unreadable.push({ file, line: lineOf(node), why: `import('${arg && ts.isStringLiteralLike(arg) ? arg.text : ''}') loads a Card or a forwarder, rendered where the gate cannot read it` })
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return scan
}

const ownCache = new Map<string, string[]>()
/** The component's own classes for one combination of its props, as it renders them. */
function ownClasses(component: ComponentName, combo: Combo): string[] {
  const key = `${component} ${JSON.stringify(combo)}`
  if (!ownCache.has(key)) {
    const { container, unmount } = render(createElement(COMPONENTS[component] as ComponentType<Combo>, combo, 'x'))
    ownCache.set(key, (container.firstElementChild as HTMLElement).className.split(/\s+/).filter(Boolean))
    unmount()
  }
  return ownCache.get(key)!
}

/** An arbitrary variant the gate cannot place: dropped when its utility sets nothing the component sets anywhere, kept
    (and so failed by competing) when it does, or when it is important or a class Tailwind does not generate. */
function placeable(own: string[], added: string[]): string[] {
  const ownProps = new Set(own.flatMap((t) => (declCache.get(parseClass(t).utility) ?? []).flatMap((e) => e.decls.map((d) => d.prop))))
  return added.filter((t) => {
    const p = parseClass(t)
    if (!p.arbitrary || p.important) return true
    const entries = declCache.get(p.utility)
    if (!entries) return !stylesOthers.has(p.utility) && !MARKER.test(p.utility)
    return entries.some((e) => e.decls.some((d) => ownProps.has(d.prop)))
  })
}

/** Every finding of a scan as `file:line <Component> finding`, sorted. */
async function check(scan: Scan): Promise<string[]> {
  const utilities = scan.sites.flatMap((s) => [...s.added, ...s.combos.flatMap((c) => ownClasses(s.component, c))]).map((t) => parseClass(t).utility)
  await loadDeclarations(utilities)
  const out = new Set<string>()
  for (const site of scan.sites) {
    for (const combo of site.combos) {
      const own = ownClasses(site.component, combo)
      const props = Object.keys(combo).length ? ` ${JSON.stringify(combo)}` : ''
      for (const f of competing(own, placeable(own, site.added))) out.add(`${site.file}:${site.line} <${site.label}${props}> ${f}`)
    }
  }
  return [...out].sort()
}

function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const abs = path.join(dir, name)
    if (statSync(abs).isDirectory()) sourceFiles(abs, out)
    else if (/\.tsx?$/.test(name) && !/\.d\.ts$/.test(name)) out.push(abs)
  }
  return out
}

function scanApp(): Scan & { files: number } {
  const total: Scan & { files: number } = { sites: [], unreadable: [], files: 0 }
  for (const root of ROOTS) {
    for (const abs of sourceFiles(path.join(FRONTEND_ROOT, root))) {
      const rel = path.relative(FRONTEND_ROOT, abs).split(path.sep).join('/')
      if (rel === DEFINITION) continue
      const s = scanSource(rel, readFileSync(abs, 'utf8'))
      total.sites.push(...s.sites)
      total.unreadable.push(...s.unreadable)
      total.files += 1
    }
  }
  return total
}

/** The findings of one in-memory source, the unreadable positions included, without file or line. */
async function findingsOf(source: string, file = 'features/fixture/Fixture.tsx'): Promise<string[]> {
  const scan = scanSource(file, source)
  const found = (await check(scan)).map((f) => f.replace(/^\S+:\d+ /, ''))
  return [...found, ...scan.unreadable.map((u) => `unreadable: ${u.why}`)]
}

const SLOW = { timeout: 30_000 }
const IMPORTS = "import { Card, CardBody, CardHeader, CardFooter, CardTitle } from '@/components/ui'\nimport { cx } from '@/components/ui/cx'\n"

describe('a class on a Card never competes with what Card sets (E283, D-076)', SLOW, () => {
  it('no class on a Card, a Card section or a forwarder in the app competes with the component’s own', async () => {
    const scan = scanApp()
    expect(await check(scan)).toEqual([])
    const unread: Record<string, number> = {}
    for (const u of scan.unreadable) unread[u.file] = (unread[u.file] ?? 0) + 1
    expect(
      unread,
      `a position the gate cannot read: ${scan.unreadable.map((u) => `${u.file}:${u.line} ${u.why}`).join('; ')}. A component that forwards a caller's className to a Card is traced and listed in FORWARDERS`,
    ).toEqual(Object.fromEntries(FORWARDERS.map((f) => [f.file, f.unread])))
  })

  it('reads the app (a rename cannot leave it scanning nothing), and each forwarder is called where its classes are read', () => {
    const scan = scanApp()
    expect(scan.files).toBeGreaterThan(300)
    expect(scan.sites.length).toBeGreaterThanOrEqual(58)
    const files = new Set(scan.sites.map((s) => s.file))
    for (const f of ['app/dashboard/settings/page.tsx', 'app/delete-account/page.tsx', 'app/pricing/page.tsx', 'features/dashboard/components/YourCompanies.tsx']) {
      expect(files, f).toContain(f)
    }
    expect(scan.sites.some((s) => s.component === 'CardBody')).toBe(true)
    // The company page gives both of its forwarders their margin; the literals beside each forwarded className are read.
    const labels = scan.sites.map((s) => `${s.file} ${s.label} ${s.added.join(' ')}`)
    expect(labels).toEqual(expect.arrayContaining([
      'app/company/[ticker]/page-client.tsx ChartErrorBoundary → Card mt-8',
      'app/company/[ticker]/page-client.tsx SectorPeers → Card mt-8',
      'components/ChartErrorBoundary.tsx Card p-cap-6 text-center',
      'features/peers/components/SectorPeersCard.tsx Card p-cap-6',
    ]))
  })

  it("reads CardProps' unions off Card.tsx, every member but `as`", () => {
    expect(CARD_PROPS).toEqual({ interactive: [false, true], elevation: ['none', 'e1', 'e2', 'e3'], radius: ['xl', '2xl'], tone: ['default', 'danger'] })
  })
})

describe('the scanner', SLOW, () => {
  it("fails the settings card's override as main shipped it before E283, in light (same chain) and in dark", async () => {
    const found = await findingsOf(`${IMPORTS}export const S = () => <Card className="border-loss-light/40 p-cap-6 dark:border-loss-dark/30">x</Card>`)
    expect(found).toEqual([
      '<Card> border-loss-light/40 vs border-border-light [border-color] (same chain)',
      '<Card> dark:border-loss-dark/30 vs dark:border-white/10 [border-color] (same chain)',
    ])
  })

  it('passes the tone that replaced it; a hairline written on top of it does nothing in dark and fails', async () => {
    expect(await findingsOf(`${IMPORTS}export const S = () => <Card tone="danger" className="p-cap-6">x</Card>`)).toEqual([])
    // Equal to the tone's own on its chain, so nothing there; in dark the tone's `dark:` class outranks it.
    expect(await findingsOf(`${IMPORTS}export const S = () => <Card tone="danger" className="border-error-light/40">x</Card>`)).toEqual([
      '<Card {"tone":"danger"}> border-error-light/40 vs dark:border-error-dark/40 [border-color] (no dark twin)',
    ])
  })

  it('fails a fill with no dark twin, a corner, a section’s padding and layout', async () => {
    expect(await findingsOf(`${IMPORTS}export const S = () => <Card className="bg-white">x</Card>`)).toEqual([
      '<Card> bg-white vs bg-panel-light [background-color] (same chain)',
      '<Card> bg-white vs dark:bg-panel-dark [background-color] (no dark twin)',
    ])
    expect(await findingsOf(`${IMPORTS}export const S = () => <Card className="rounded-2xl">x</Card>`)).toEqual([
      '<Card> rounded-2xl vs rounded-xl [border-radius] (same chain)',
    ])
    expect(await findingsOf(`${IMPORTS}export const S = () => <CardBody className="py-3">x</CardBody>`)).toEqual([
      '<CardBody> py-3 vs py-4 [padding-top,padding-bottom] (same chain)',
    ])
    // py-5 is emitted after py-4 and wins today; it still fails, since a rename of either flips the order.
    expect(await findingsOf(`${IMPORTS}export const S = () => <CardBody className="py-5">x</CardBody>`)).toEqual([
      '<CardBody> py-5 vs py-4 [padding-top,padding-bottom] (same chain)',
    ])
    expect(await findingsOf(`${IMPORTS}export const S = () => <CardHeader className="block px-4">x</CardHeader>`)).toEqual([
      '<CardHeader> block vs flex [display] (same chain)',
      '<CardHeader> px-4 vs px-cap-5 [padding-left,padding-right] (same chain)',
    ])
  })

  it('reads a logical utility as the side it sets, and a shorthand as its longhands', async () => {
    expect(await findingsOf(`${IMPORTS}export const S = () => <CardBody className="ps-0">x</CardBody>`)).toEqual([
      '<CardBody> ps-0 vs px-cap-5 [padding-left] (same chain)',
    ])
    expect(await findingsOf(`${IMPORTS}export const S = () => <Card className="rounded-s-none">x</Card>`)).toEqual([
      '<Card> rounded-s-none vs rounded-xl [border-top-left-radius,border-bottom-left-radius] (same chain)',
    ])
    expect(await findingsOf(`${IMPORTS}export const S = () => <Card className="[background:white]">x</Card>`)).toEqual([
      '<Card> [background:white] vs bg-panel-light [background-color] (same chain)',
      '<Card> [background:white] vs dark:bg-panel-dark [background-color] (no dark twin)',
    ])
    expect(await findingsOf(`${IMPORTS}export const S = () => <Card className="[border:1px_solid_red]">x</Card>`)).toEqual([
      '<Card> [border:1px_solid_red] vs border [border-width] (same chain)',
      '<Card> [border:1px_solid_red] vs border-border-light [border-color] (same chain)',
      '<Card> [border:1px_solid_red] vs dark:border-white/10 [border-color] (no dark twin)',
    ])
  })

  it('passes a ring, a divide, spacing and layout Card leaves alone, arbitrary properties of their own, and a layer on a screen or state Card leaves alone', async () => {
    const found = await findingsOf(
      `${IMPORTS}export const S = () => <Card className="relative mt-6 overflow-hidden p-cap-6 ring-1 ring-brand dark:ring-brand-dark divide-y divide-border-light dark:divide-border-dark space-y-5 [--mark-gutter:2px] [container-type:inline-size] [[data-hint]_&]:block sm:rounded-2xl focus:bg-white dark:focus:bg-panel-dark">x</Card>`,
    )
    expect(found).toEqual([])
  })

  it('fails an arbitrary variant when its utility sets what the component sets, or is important or unknown', async () => {
    expect(await findingsOf(`${IMPORTS}export const S = () => <Card className="[@container(max-width:13em)]:px-1.5">x</Card>`)).toEqual([])
    expect(await findingsOf(`${IMPORTS}export const S = () => <CardHeader className="[@container(max-width:13em)]:px-1.5">x</CardHeader>`)).toEqual([
      '<CardHeader> [@container(max-width:13em)]:px-1.5 (arbitrary variant)',
    ])
    expect(await findingsOf(`${IMPORTS}export const S = () => <Card className="[&>p]:!mt-2 [&>p]:mt-nonsense">x</Card>`)).toEqual([
      '<Card> [&>p]:!mt-2 (arbitrary variant)',
      '<Card> [&>p]:!mt-2 (important)',
      '<Card> [&>p]:mt-nonsense (arbitrary variant)',
    ])
  })

  it('checks every value of a prop it cannot read, and a literal one as written', async () => {
    const found = await findingsOf(`${IMPORTS}export const S = ({ e }: { e: 'e1' | 'e3' }) => <Card elevation={e} interactive className="hover:bg-brand-weak">x</Card>`)
    // Same chain as the interactive card's hover fill, and in dark Card's `dark:bg-panel-dark` outranks it.
    expect(found).toEqual(
      ['e1', 'e2', 'e3', 'none'].flatMap((elevation) => [
        `<Card {"elevation":"${elevation}","interactive":true}> hover:bg-brand-weak vs dark:bg-panel-dark [background-color] (no dark twin)`,
        `<Card {"elevation":"${elevation}","interactive":true}> hover:bg-brand-weak vs hover:bg-white [background-color] (same chain)`,
      ]),
    )
    // Not interactive, so no hover fill of Card's own; with its dark twin the hover fill holds in both themes.
    expect(await findingsOf(`${IMPORTS}export const S = () => <Card interactive={false} className="hover:bg-brand-weak dark:hover:bg-brand-weak-dark">x</Card>`)).toEqual([])
  })

  it('follows an alias, a namespace import, a trailing-slash path, cx, a condition and a same-file const; skips a shadowing local', async () => {
    const source = `import { Card as Panel, CardFooter } from '@/components/ui/'
import * as ui from '@/components/ui/Card'
import { cx } from '@/components/ui/cx'
const EDGE = 'rounded-none'
export const A = ({ on }: { on: boolean }) => <Panel className={cx('mt-2', on && 'bg-white dark:bg-black')}>x</Panel>
export const B = () => <ui.CardTitle className={EDGE}>t</ui.CardTitle>
export const C = () => { const CardFooter = (p: { className?: string }) => <div {...p} />; return <CardFooter className="py-9" /> }
`
    expect(await findingsOf(source)).toEqual([
      '<Card> bg-white vs bg-panel-light [background-color] (same chain)',
      '<Card> dark:bg-black vs dark:bg-panel-dark [background-color] (same chain)',
    ])
    const titleSource = `import * as ui from '@/components/ui/Card'\nexport const B = () => <ui.CardTitle className="text-xs dark:text-white">t</ui.CardTitle>`
    expect(await findingsOf(titleSource)).toEqual([
      '<CardTitle> dark:text-white vs dark:text-text-primary-dark [color] (same chain)',
      '<CardTitle> text-xs vs text-sm [font-size,line-height] (same chain)',
    ])
  })

  it("reads a forwarder's call sites against its Card, and the literals beside a forwarded className", async () => {
    const caller = `import { ChartErrorBoundary } from '@/components/ChartErrorBoundary'
import SectorPeers from '@/features/peers/components/SectorPeers'
export const P = () => <><ChartErrorBoundary className="mt-8 bg-white">x</ChartErrorBoundary><SectorPeers ticker="X" className="rounded-2xl" /></>`
    expect(await findingsOf(caller, 'app/fixture/page.tsx')).toEqual([
      '<ChartErrorBoundary → Card> bg-white vs bg-panel-light [background-color] (same chain)',
      '<ChartErrorBoundary → Card> bg-white vs dark:bg-panel-dark [background-color] (no dark twin)',
      '<SectorPeers → Card> rounded-2xl vs rounded-xl [border-radius] (same chain)',
    ])
    const forwarding = `${IMPORTS}export const F = ({ className }: { className?: string }) => <Card className={cx(className, 'p-cap-6 rounded-lg')}>x</Card>`
    expect(await findingsOf(forwarding)).toEqual([
      '<Card> rounded-lg vs rounded-xl [border-radius] (same chain)',
      'unreadable: a class from `className`, which is not a const with an initializer',
    ])
  })

  it('fails !important, a class Tailwind does not generate, and every position it cannot follow', async () => {
    expect(await findingsOf(`${IMPORTS}export const S = () => <Card className="!mt-2 bg-panel-lite">x</Card>`)).toEqual([
      '<Card> !mt-2 (important)',
      '<Card> bg-panel-lite (not a class Tailwind generates)',
    ])
    const unread = await findingsOf(`${IMPORTS}import { createElement, memo } from 'react'
import { ChartErrorBoundary } from '@/components/ChartErrorBoundary'
export const S = ({ className, p }: { className?: string; p: object }) => <>
  <Card className={className}>x</Card>
  <Card {...p}>y</Card>
  <CardFooter className={\`p\${'x'}-2\`}>z</CardFooter>
  {createElement(Card, { className: 'bg-white' })}
  <section as={CardBody} />
</>
export const M = memo(ChartErrorBoundary)
export const load = () => import('@/components/ui/Card')
`)
    expect(unread).toEqual([
      'unreadable: a class from `className`, which is not a const with an initializer',
      'unreadable: props spread into a <Card>',
      'unreadable: a class built from pieces of a template',
      'unreadable: <Card> used as a value, so where it renders and with what cannot be read',
      'unreadable: <CardBody> used as a value, so where it renders and with what cannot be read',
      'unreadable: <a forwarder> used as a value, so where it renders and with what cannot be read',
      "unreadable: import('@/components/ui/Card') loads a Card or a forwarder, rendered where the gate cannot read it",
    ])
    // A type names no render: `typeof Card` and `ComponentProps<typeof Card>` pass.
    expect(await findingsOf(`${IMPORTS}import type { ComponentProps } from 'react'\nexport type P = ComponentProps<typeof Card>`)).toEqual([])
  })
})
