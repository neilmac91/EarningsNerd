import { readdirSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { PHOSPHOR, isIconModule } from './iconModules'

/**
 * Three glyphs carry one meaning each (DESIGN.md › Icons; docs/brand/06-system.md §4): the quotes glyph
 * marks a passage from the filing, the curly braces an XBRL fact, and the sparkle the AI summary alone.
 * Spent elsewhere (on an upgrade button, a status badge, a reader's quote) the glyph stops meaning
 * anything (chrome/F24). This gate counts, per file, every use of SparkleIcon, QuotesIcon and
 * BracketsCurlyIcon imported from @/lib/icons (by that alias or a relative path to it) or from the
 * Phosphor package at any of its entries (`@phosphor-icons/react`, its `ssr` and `dist/…` subpaths, a
 * per-icon path), under any local name and under Phosphor's deprecated alias for the glyph (`Sparkle`,
 * `Quotes`, `BracketsCurly`, read off the package's own per-icon declarations): a named import, a member
 * of a namespace import (`<Icons.SparkleIcon />`, `Icons['QuotesIcon']`) and a member destructured from
 * one (`const { SparkleIcon: Spark } = Icons`), a namespace held by another name included. A glyph a same-file
 * binding holds counts where the binding is read, never where it is held: an alias, a conditional or logical
 * hold and a held element (`const EvidenceGlyph = QuotesIcon`, `const Icon = ok ? BracketsCurlyIcon :
 * QuotesIcon`, `const mark = <QuotesIcon />`, a chain of them) at each reference; an object's property
 * (`const GLYPH = { passage: QuotesIcon }`) at each read of it by name or literal key, and every glyph the
 * object holds at a read by a key the scan cannot read (`GLYPH[kind]`) or of the object whole; a holder
 * nobody reads counts once, as a bare import does. It counts every hand-drawn stand-in (a local component
 * named for one of them that draws its own <svg>), and the ✨ emoji, against two lists:
 *
 *  - MEANING lists the sites that use a glyph for its meaning. A new one is a design decision, made in
 *    review against DESIGN.md.
 *  - RESIDUE lists what the audit found spent elsewhere on 2026-10-12, with the PR that removes it.
 *    Shrink-only: a fixed use fails until its count is lowered, a new one fails, and the list's size
 *    equals RESIDUE_MAX, seeded at the audit's count and lowered in the same commit as each shrink.
 *
 * Review-checked, out of the scan's reach: a namespace member read by a key it cannot read
 * (`Icons[name]`), a glyph re-exported through a module of the app's own other than lib/icons.ts, a
 * binding assigned a glyph after its declaration, and a glyph drawn inside a local component or function,
 * which counts where it is drawn however often the component renders.
 */

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']
const GLYPHS = ['SparkleIcon', 'QuotesIcon', 'BracketsCurlyIcon'] as const
type Glyph = (typeof GLYPHS)[number]
/** The names a glyph is exported under, read off Phosphor's own per-icon declaration: `dist/csr/Sparkle.d.ts`
    exports SparkleIcon and its deprecated alias Sparkle, the same component. */
const GLYPH_NAMES: Map<string, Glyph> = (() => {
  const pkg = path.dirname(createRequire(import.meta.url).resolve(`${PHOSPHOR}/package.json`))
  const names = new Map<string, Glyph>()
  for (const glyph of GLYPHS) {
    const file = path.join(pkg, 'dist/csr', `${glyph.replace(/Icon$/, '')}.d.ts`)
    const sf = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true)
    for (const st of sf.statements) {
      if (ts.isVariableStatement(st) && st.modifiers?.some((m) => m.kind === ts.SyntaxKind.ExportKeyword)) {
        for (const d of st.declarationList.declarations) if (ts.isIdentifier(d.name)) names.set(d.name.text, glyph)
      }
      if (ts.isExportDeclaration(st) && st.exportClause && ts.isNamedExports(st.exportClause)) {
        for (const el of st.exportClause.elements) names.set(el.name.text, glyph)
      }
    }
    if (names.get(glyph) !== glyph) throw new Error(`${file} no longer exports ${glyph}: read the glyph's names again`)
  }
  return names
})()
/** A local component drawing one of the glyphs by hand. */
const HAND_DRAWN: Array<[Glyph, RegExp]> = [
  ['SparkleIcon', /sparkle/i],
  ['QuotesIcon', /quote/i],
  ['BracketsCurlyIcon', /brace|bracket/i],
]

type Counts = Partial<Record<Glyph, number>>

const MEANING: Record<string, Counts> = {
  // The two heading sparkles (the generating header and the summary card's head). The design owner's
  // call on #1288: they come off in brand-filing-page (#1293), which edits this file, and this entry is
  // dropped in that merge; the sparkle then has no sanctioned site until an AI-summary chip exists
  // (DESIGN.md › Icons: the AI summary chip alone; section headings carry no icon).
  'app/filing/[id]/StreamingSummaryDisplay.tsx': { SparkleIcon: 2 },
  // Source chips: a located passage (quotes) or an XBRL fact (braces).
  'features/filings/components/SourceTrace.tsx': { QuotesIcon: 1, BracketsCurlyIcon: 1 },
  'features/marketing/components/HeroExample.tsx': { QuotesIcon: 1 },
  'features/marketing/components/TraceToSourceDemo.tsx': { QuotesIcon: 1 },
  'features/marketing/components/CatchCard.tsx': { BracketsCurlyIcon: 1 },
}

const RESIDUE: Record<string, Counts> = {
  'app/filing/[id]/StreamingSummaryDisplay.tsx': { SparkleIcon: 2 }, // brand-filing-page: the waiting notice and the free-limit card
  'app/dashboard/watchlist/page.tsx': { SparkleIcon: 1 }, // brand-dashboard-watchlist: "Analyze trends" (DSW-18)
  'features/filings/components/copilot/CopilotMessage.tsx': { SparkleIcon: 2 }, // brand-copilot: follow-up chips, upgrade button
  'features/filings/components/copilot/AskCopilotRail.tsx': { SparkleIcon: 2 }, // brand-copilot: launcher and rail header
  'features/filings/components/copilot/CopilotTeaser.tsx': { SparkleIcon: 1 }, // brand-copilot: upgrade button
  'features/filings/components/copilot/AskAboutSelection.tsx': { SparkleIcon: 1 }, // brand-copilot: the selection prompt
  'features/settings/components/BillingPanel.tsx': { SparkleIcon: 1 }, // brand-settings-subscriptions: the Pro badge
  'features/subscriptions/components/TrialBanner.tsx': { SparkleIcon: 1 }, // brand-settings-subscriptions: the trial banner
  'features/subscriptions/components/SubscriptionGate.tsx': { SparkleIcon: 1 }, // brand-settings-subscriptions (DSW-35 deletes it)
  'features/summaries/components/GenerateSignupGate.tsx': { SparkleIcon: 1 }, // brand-filing-page: the sign-up gate
  'features/feedback/components/FeedbackWidget.tsx': { SparkleIcon: 1 }, // brand-chrome-primitives: the "✨ Idea" option
  'features/marketing/components/ReaderQuoteSlot.tsx': { QuotesIcon: 1 }, // a reader's words, not the filing's (BG-28): the slot renders nothing until a quote lands (READER_QUOTE is null since #1311), and the glyph is decided with that quote
  'features/marketing/components/AskFilingDemo.tsx': { QuotesIcon: 1 }, // the Ask this Filing mark on the landing demo, decided with brand-copilot's (#1295) AskFilingAnswer entry, the same mark; #1311 left it
  'features/filings/components/AskFilingAnswer.tsx': { QuotesIcon: 2 }, // brand-copilot: a hand-drawn quotes glyph as the Ask this Filing mark
}
const RESIDUE_MAX = { files: 14, uses: 18 }

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(entry.name) && !/\.(spec|test)\.tsx?$|\.d\.ts$/.test(entry.name)) out.push(p)
  }
  return out
}

/** The reserved-glyph uses in one source: imported glyphs (each reference, or the bare import when it has
    none), hand-drawn stand-ins (the declaration and each use) and the ✨ emoji in a literal. */
export function glyphUses(source: string, fileName: string): Counts {
  const sf = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, fileName.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const counts: Counts = {}
  const bump = (glyph: Glyph, n = 1) => {
    counts[glyph] = (counts[glyph] ?? 0) + n
  }
  const local = new Map<string, Glyph>()
  const namespaces = new Set<string>()
  for (const stmt of sf.statements) {
    if (!ts.isImportDeclaration(stmt) || !ts.isStringLiteral(stmt.moduleSpecifier) || !isIconModule(stmt.moduleSpecifier.text, fileName)) continue
    const bindings = stmt.importClause?.namedBindings
    if (bindings && ts.isNamedImports(bindings)) {
      for (const el of bindings.elements) {
        const glyph = GLYPH_NAMES.get((el.propertyName ?? el.name).text)
        if (glyph) local.set(el.name.text, glyph)
      }
    }
    // A namespace import (`import * as Icons from '@/lib/icons'`) draws a glyph through its members.
    if (bindings && ts.isNamespaceImport(bindings)) namespaces.add(bindings.name.text)
  }
  const unwrapHeld = (e: ts.Expression): ts.Expression =>
    ts.isParenthesizedExpression(e) || ts.isAsExpression(e) || ts.isSatisfiesExpression(e) || ts.isNonNullExpression(e) ? unwrapHeld(e.expression) : e
  // A namespace held by another name (`const Glyphs = Icons`, a chain of them) is that namespace.
  for (let before = -1; before !== namespaces.size;) {
    before = namespaces.size
    const alias = (node: ts.Node): void => {
      if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) {
        const value = unwrapHeld(node.initializer)
        if (ts.isIdentifier(value) && namespaces.has(value.text)) namespaces.add(node.name.text)
      }
      ts.forEachChild(node, alias)
    }
    alias(sf)
  }
  // A member destructured from a namespace (`const { SparkleIcon: Spark } = Icons`) is a local name for its glyph.
  const destructure = (node: ts.Node): void => {
    if (ts.isVariableDeclaration(node) && ts.isObjectBindingPattern(node.name) && node.initializer && ts.isIdentifier(node.initializer) && namespaces.has(node.initializer.text)) {
      for (const el of node.name.elements) {
        const key = el.propertyName ?? el.name
        const glyph = ts.isIdentifier(key) || ts.isStringLiteral(key) ? GLYPH_NAMES.get(key.text) : undefined
        if (glyph && ts.isIdentifier(el.name)) local.set(el.name.text, glyph)
      }
    }
    ts.forEachChild(node, destructure)
  }
  destructure(sf)
  // Hand-drawn stand-ins: a function or const named for a glyph whose body draws an <svg>.
  const drawn = new Map<string, Glyph>()
  const drawsSvg = (node: ts.Node) => {
    let svg = false
    const find = (n: ts.Node) => {
      if ((ts.isJsxOpeningElement(n) || ts.isJsxSelfClosingElement(n)) && n.tagName.getText(sf) === 'svg') svg = true
      if (!svg) ts.forEachChild(n, find)
    }
    find(node)
    return svg
  }
  const declare = (node: ts.Node): void => {
    const name = (ts.isFunctionDeclaration(node) || ts.isVariableDeclaration(node)) && node.name && ts.isIdentifier(node.name) ? node.name.text : null
    if (name && !local.has(name) && /^[A-Z]/.test(name) && drawsSvg(node)) {
      const hit = HAND_DRAWN.find(([, re]) => re.test(name))
      if (hit) drawn.set(name, hit[0])
    }
    ts.forEachChild(node, declare)
  }
  declare(sf)
  // A name read as a value: not the name an import or a destructuring binds (a declaration, or the key it
  // reads), nor a member's or a key's name (`Icons.SparkleIcon` reads the namespace, `{ SparkleIcon: x }` a key).
  const isReference = (n: ts.Identifier): boolean => {
    const p = n.parent
    if (ts.isImportSpecifier(p) || ts.isBindingElement(p) || ts.isJsxAttribute(p)) return false
    if ((ts.isPropertyAccessExpression(p) || ts.isPropertyAssignment(p) || ts.isQualifiedName(p)) && (ts.isQualifiedName(p) ? p.right : p.name) === n) return false
    return true
  }
  // Where a glyph comes from, its root: a name an import or a destructuring binds (`n:`), a hand-drawn stand-in
  // (`d:`), or one namespace member in the source (`m:` and its place). A root counts each read that reaches it,
  // and once when nothing does (a bare import, a holder nobody reads).
  type Root = string
  const glyphOf = new Map<Root, Glyph>()
  for (const [name, glyph] of local) glyphOf.set(`n:${name}`, glyph)
  for (const [name, glyph] of drawn) glyphOf.set(`d:${name}`, glyph)
  const memberKey = (n: ts.PropertyAccessExpression | ts.ElementAccessExpression): string | undefined =>
    ts.isPropertyAccessExpression(n) ? n.name.text : ts.isStringLiteralLike(n.argumentExpression) || ts.isNumericLiteral(n.argumentExpression) ? n.argumentExpression.text : undefined
  /** A namespace member's root, read by name or by a literal key (`Icons.SparkleIcon`, `Icons['QuotesIcon']`). */
  const memberRoot = (n: ts.PropertyAccessExpression | ts.ElementAccessExpression): Root | undefined => {
    const key = memberKey(n)
    const glyph = key === undefined ? undefined : GLYPH_NAMES.get(key)
    if (!glyph) return undefined
    glyphOf.set(`m:${n.getStart(sf)}`, glyph)
    return `m:${n.getStart(sf)}`
  }
  // Holders, read by name to a fixed point: a binding whose value is a glyph, and an object whose properties hold one.
  const aliases = new Map<string, Set<Root>>()
  const objects = new Map<string, Map<string, Set<Root>>>()
  const objectRoots = (name: string): Root[] => [...objects.get(name)!.values()].flatMap((roots) => [...roots])
  /** The roots a value holds; each node it reads them through is pushed to `leaves`. */
  const held = (e: ts.Expression, leaves: ts.Node[]): Root[] => {
    const x = unwrapHeld(e)
    if (ts.isIdentifier(x)) {
      const roots = local.has(x.text) ? [`n:${x.text}`] : drawn.has(x.text) ? [`d:${x.text}`]
        : aliases.has(x.text) ? [...aliases.get(x.text)!] : objects.has(x.text) ? objectRoots(x.text) : []
      if (roots.length) leaves.push(x)
      return roots
    }
    if ((ts.isPropertyAccessExpression(x) || ts.isElementAccessExpression(x)) && ts.isIdentifier(x.expression)) {
      const owner = x.expression.text
      const key = memberKey(x)
      const roots = namespaces.has(owner) ? [memberRoot(x)].filter((root): root is Root => !!root)
        : objects.has(owner) ? (key === undefined ? objectRoots(owner) : [...(objects.get(owner)!.get(key) ?? [])]) : []
      if (roots.length) leaves.push(x)
      return roots
    }
    if (ts.isJsxSelfClosingElement(x) || ts.isJsxElement(x)) {
      const tag = (ts.isJsxElement(x) ? x.openingElement : x).tagName
      return ts.isIdentifier(tag) || ts.isPropertyAccessExpression(tag) ? held(tag, leaves) : []
    }
    if (ts.isConditionalExpression(x)) return [...held(x.whenTrue, leaves), ...held(x.whenFalse, leaves)]
    if (ts.isBinaryExpression(x)) {
      const op = x.operatorToken.kind
      if (op === ts.SyntaxKind.BarBarToken || op === ts.SyntaxKind.QuestionQuestionToken) return [...held(x.left, leaves), ...held(x.right, leaves)]
      if (op === ts.SyntaxKind.AmpersandAmpersandToken) return held(x.right, leaves)
    }
    return []
  }
  const bindings: ts.VariableDeclaration[] = []
  const collect = (node: ts.Node): void => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer && !local.has(node.name.text) && !drawn.has(node.name.text)) bindings.push(node)
    ts.forEachChild(node, collect)
  }
  collect(sf)
  const leavesOf = new Map<ts.VariableDeclaration, ts.Node[]>()
  const heldSize = () => [...aliases.values()].reduce((sum, roots) => sum + roots.size, 0)
    + [...objects.values()].reduce((sum, props) => sum + [...props.values()].reduce((n, roots) => n + roots.size, 0), 0)
  for (let before = -1; before !== heldSize();) {
    before = heldSize()
    for (const d of bindings) {
      const name = (d.name as ts.Identifier).text
      const leaves: ts.Node[] = []
      const value = unwrapHeld(d.initializer!)
      if (ts.isObjectLiteralExpression(value)) {
        const props = new Map<string, Set<Root>>()
        for (const p of value.properties) {
          if (!(ts.isPropertyAssignment(p) || ts.isShorthandPropertyAssignment(p))) continue
          if (!(ts.isIdentifier(p.name) || ts.isStringLiteral(p.name) || ts.isNumericLiteral(p.name))) continue
          const roots = held(ts.isPropertyAssignment(p) ? p.initializer : p.name, leaves)
          if (roots.length) props.set(p.name.text, new Set(roots))
        }
        if (props.size) objects.set(name, props)
      } else {
        const roots = held(value, leaves)
        if (roots.length) aliases.set(name, new Set(roots))
      }
      leavesOf.set(d, leaves)
    }
  }
  // Each read of a root, a holder or a namespace member. A held leaf counts where its holder is read, and a closing
  // tag repeats its opening tag's name: one use.
  const heldLeaves = new Set([...leavesOf.values()].flat())
  const uses = new Map<Root, number>()
  const tally = (roots: Iterable<Root>) => {
    for (const root of roots) uses.set(root, (uses.get(root) ?? 0) + 1)
  }
  const declares = (n: ts.Identifier) => ts.isVariableDeclaration(n.parent) && n.parent.name === n
  const ownsMember = (n: ts.Identifier) => (ts.isPropertyAccessExpression(n.parent) || ts.isElementAccessExpression(n.parent)) && n.parent.expression === n
  const visit = (node: ts.Node): void => {
    if ((ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isJsxText(node)) && node.text.includes('✨')) bump('SparkleIcon')
    if (heldLeaves.has(node) || ts.isJsxClosingElement(node)) return
    if (ts.isIdentifier(node) && isReference(node)) {
      const name = node.text
      if (local.has(name)) tally([`n:${name}`])
      else if (drawn.has(name)) tally([`d:${name}`])
      else if (aliases.has(name) && !declares(node)) tally(aliases.get(name)!)
      // An object read whole (passed on, spread, iterated) reads every glyph it holds.
      else if (objects.has(name) && !declares(node) && !ownsMember(node)) tally(objectRoots(name))
    }
    if ((ts.isPropertyAccessExpression(node) || ts.isElementAccessExpression(node)) && ts.isIdentifier(node.expression)) {
      const owner = node.expression.text
      // A namespace's member, by name or by a literal key (`<Icons.SparkleIcon />`, `Icons['QuotesIcon']`).
      if (namespaces.has(owner)) {
        const root = memberRoot(node)
        if (root) tally([root])
      // An object's property by name or literal key, or every glyph it holds for a key the scan cannot read.
      } else if (objects.has(owner)) {
        const key = memberKey(node)
        tally(key === undefined ? objectRoots(owner) : objects.get(owner)!.get(key) ?? [])
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  for (const [root, glyph] of glyphOf) bump(glyph, Math.max(uses.get(root) ?? 0, 1))
  return counts
}

const rel = (file: string) => path.relative(ROOT, file).split(path.sep).join('/')

describe('reserved glyphs keep their one meaning', () => {
  const uses = new Map<string, Counts>()
  for (const file of SCAN_DIRS.flatMap((dir) => walk(path.join(ROOT, dir)))) {
    const r = rel(file)
    if (r === 'lib/icons.ts') continue
    const counts = glyphUses(readFileSync(file, 'utf8'), r)
    if (Object.keys(counts).length) uses.set(r, counts)
  }

  it('every use is a meaning site or listed residue, at its current count', () => {
    const problems: string[] = []
    const files = new Set([...uses.keys(), ...Object.keys(MEANING), ...Object.keys(RESIDUE)])
    for (const file of files) {
      for (const glyph of GLYPHS) {
        const actual = uses.get(file)?.[glyph] ?? 0
        const meant = MEANING[file]?.[glyph] ?? 0
        const residue = RESIDUE[file]?.[glyph] ?? 0
        if (actual > meant + residue) {
          problems.push(`${file}: ${actual} ${glyph}, ${meant + residue} allowed. ${glyph} is reserved (DESIGN.md › Icons): use LightningIcon or no icon on commerce, another glyph elsewhere`)
        } else if (actual < meant + residue) {
          problems.push(`${file}: ${actual} ${glyph}, ${meant + residue} listed: ${residue ? 'lower its RESIDUE count (stale)' : 'lower its MEANING count'}`)
        }
      }
    }
    expect(problems).toEqual([])
  })

  it('the residue only shrinks', () => {
    const counts = Object.values(RESIDUE).flatMap((c) => Object.values(c))
    // Equality, not a ceiling: a PR that shrinks the list lowers the cap in the same commit.
    expect(Object.keys(RESIDUE).length, 'RESIDUE changed its files: move RESIDUE_MAX.files with it in the same commit').toBe(RESIDUE_MAX.files)
    expect(counts.reduce((sum, n) => sum + (n ?? 0), 0), 'RESIDUE changed its uses: move RESIDUE_MAX.uses with it in the same commit').toBe(RESIDUE_MAX.uses)
  })

  it('the scan catches what it is for (a self-check on fixed sources)', () => {
    const src = [
      "import { SparkleIcon as Spark, QuotesIcon, ArrowRightIcon } from '@/lib/icons'",
      "import { BracketsCurlyIcon } from '@phosphor-icons/react'",
      'function QuoteMark() { return <svg viewBox="0 0 24 24"><path d="M0 0" /></svg> }',
      'export const A = () => (<><Spark /><Spark className="h-4 w-4"></Spark><QuoteMark /><ArrowRightIcon /><span>✨ Idea</span></>)',
      'const config = { Icon: QuotesIcon }',
    ].join('\n')
    expect(glyphUses(src, 'probe.tsx')).toEqual({ SparkleIcon: 3, QuotesIcon: 3, BracketsCurlyIcon: 1 })
    // A namespace's members (a self-closing tag, an open-and-close pair counted once, a literal key), a
    // Phosphor subpath, a deprecated alias, a member destructured from a namespace and a relative path to
    // lib/icons count; another icon, a key the scan cannot read, and a module named for a glyph do not.
    const wide = [
      "import * as Icons from '@/lib/icons'",
      "import { SparkleIcon as Ssr } from '@phosphor-icons/react/dist/ssr'",
      "import { Quotes, ArrowRightIcon } from '@phosphor-icons/react'",
      "import * as Ph from '@phosphor-icons/react/ssr'",
      "import { BracketsCurlyIcon as Braces } from '../../lib/icons'",
      "import { SparkleIcon as NotTheIcon } from '@/lib/sparkle'",
      'const { BracketsCurlyIcon: Curly, SparkleIcon } = Ph',
      'export const B = ({ name }: { name: string }) => (',
      '  <>',
      '    <Icons.SparkleIcon /><Icons.SparkleIcon className="h-4"></Icons.SparkleIcon><Ssr /><SparkleIcon />',
      "    <Quotes /><span>{Icons['QuotesIcon'] ? 'q' : ''}</span><Braces /><Curly />",
      '    <ArrowRightIcon /><Icons.ArrowRightIcon />{Icons[name] ? <NotTheIcon /> : null}',
      '  </>',
      ')',
    ].join('\n')
    expect(glyphUses(wide, 'features/zzprobe/Probe.tsx')).toEqual({ SparkleIcon: 4, QuotesIcon: 2, BracketsCurlyIcon: 2 })
    // A glyph a binding holds counts where the binding is read (the review's case: an alias read twice is two uses).
    const aliased = [
      "import { QuotesIcon } from '@/lib/icons'",
      'const EvidenceGlyph = QuotesIcon',
      'export const D = () => <><EvidenceGlyph /><EvidenceGlyph /></>',
    ].join('\n')
    expect(glyphUses(aliased, 'features/zzprobe/Aliased.tsx')).toEqual({ QuotesIcon: 2 })
    // Every holder: an alias read three times (an open-and-close pair once) and through a chain, a conditional
    // hold, an element placed twice, an object's property read twice by name and once by a key the scan cannot
    // read (which reads every glyph it holds), a namespace member held under a cast, a namespace held by another
    // name; a holder nobody reads adds nothing to a glyph read elsewhere.
    const holders = [
      "import { QuotesIcon, SparkleIcon, BracketsCurlyIcon } from '@/lib/icons'",
      "import * as Icons from '@/lib/icons'",
      'const Glyphs = Icons',
      'const EvidenceGlyph = QuotesIcon',
      'const Chained = EvidenceGlyph',
      'const Either = ok ? SparkleIcon : null',
      "const mark = <BracketsCurlyIcon className='h-3' />",
      'const GLYPH = { passage: QuotesIcon, fact: BracketsCurlyIcon } as const',
      'const Member = (Glyphs.SparkleIcon) as typeof Icons.ArrowRightIcon',
      'const Unread = QuotesIcon',
      'export const C = ({ kind }: { kind: "passage" | "fact" }) => (',
      '  <>',
      '    <EvidenceGlyph /><EvidenceGlyph className="h-4"></EvidenceGlyph><Chained />',
      '    <Either />{mark}{mark}',
      '    <GLYPH.passage /><GLYPH.passage />{createElement(GLYPH[kind])}',
      '    <Member />',
      '  </>',
      ')',
    ].join('\n')
    expect(glyphUses(holders, 'features/zzprobe/Holders.tsx')).toEqual({ QuotesIcon: 6, SparkleIcon: 2, BracketsCurlyIcon: 3 })
  })
})
