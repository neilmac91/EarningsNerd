import { readdirSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { PHOSPHOR, isIconModule } from './iconModules'
import { heldValues, isWrite, leavesOf, memberKey, scopeResolver } from './heldValues'

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
 * one (`const { SparkleIcon: Spark } = Icons`), a namespace held by another name included. Each name is read by the
 * declaration its scope gives it, so a parameter or a local that shadows an import is not the import. A glyph a same-file
 * binding holds counts where the binding is read, never where it is held, by the reading the heading-icon clause
 * shares (tests/unit/heldValues.ts), each name read by its scope (a name two functions declare reads its own): an alias with its shape kept, a conditional or logical hold and a held
 * element (`const EvidenceGlyph = QuotesIcon`, `const Icon = ok ? BracketsCurlyIcon : QuotesIcon`, `const mark =
 * <QuotesIcon />`, a chain of them) at each reference, each glyph as many times as the value renders it (`const pair =
 * <><QuotesIcon /><QuotesIcon /></>` is two uses at each read; a conditional's, its larger arm's); an object's property (`const GLYPH = { passage: QuotesIcon
 * }`, an object that spreads one, `{ ...GLYPH }`, a later property overriding the spread's, a nested object and a
 * member destructured from one) at each read of it by name or literal key, and every glyph the object holds at a
 * read by a key the scan cannot read (`GLYPH[kind]`) or of the object whole; a holder
 * nobody reads counts once, as a bare import does. The reading follows every other way a name is given a glyph too:
 * each assignment, a loop's variable, a parameter at each same-file call (a component's props and children included),
 * a callback however it is handed over, a function's return, what is put in an object or an array after it is made,
 * and React's createElement, cloneElement, Children and useMemo; a glyph handed to a same-file function or component
 * counts where it is read there, not where it is passed, and a glyph a same-file component draws counts at each place
 * the component is rendered (by JSX or createElement), not inside it. It counts every hand-drawn stand-in (a local component
 * named for one of them that draws its own <svg>), and the ✨ emoji, against two lists:
 *
 *  - MEANING lists the sites that use a glyph for its meaning. A new one is a design decision, made in
 *    review against DESIGN.md.
 *  - RESIDUE lists what the audit found spent elsewhere on 2026-10-12, with the PR that removes it.
 *    Shrink-only: a fixed use fails until its count is lowered, a new one fails, and the list's size
 *    equals RESIDUE_MAX, seeded at the audit's count and lowered in the same commit as each shrink.
 *
 * Review-checked, out of the scan's reach and planted as gaps in the self-check: a namespace member read by a key it
 * cannot read (`Icons[name]`), a glyph re-exported through a module of the app's own other than lib/icons.ts, a
 * glyph held in React state, a class's field read through `this`, a promise's `then` and a generator's `yield`.
 * A glyph drawn inside a local component that the file never renders counts once where it is drawn.
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
  // Source chips: a located passage (quotes) or an XBRL fact (braces).
  'features/filings/components/SourceTrace.tsx': { QuotesIcon: 1, BracketsCurlyIcon: 1 },
  'features/marketing/components/HeroExample.tsx': { QuotesIcon: 1 },
  'features/marketing/components/TraceToSourceDemo.tsx': { QuotesIcon: 1 },
  'features/marketing/components/CatchCard.tsx': { BracketsCurlyIcon: 1 },
}

const RESIDUE: Record<string, Counts> = {
  'features/filings/components/copilot/CopilotMessage.tsx': { SparkleIcon: 3 }, // brand-copilot: follow-up chips (FollowupChips, rendered at two places), upgrade button
  'features/filings/components/copilot/AskCopilotRail.tsx': { SparkleIcon: 2 }, // brand-copilot: launcher and rail header
  'features/filings/components/copilot/CopilotTeaser.tsx': { SparkleIcon: 1 }, // brand-copilot: upgrade button
  'features/filings/components/copilot/AskAboutSelection.tsx': { SparkleIcon: 1 }, // brand-copilot: the selection prompt
  'features/marketing/components/ReaderQuoteSlot.tsx': { QuotesIcon: 1 }, // a reader's words, not the filing's (BG-28): the slot renders nothing until a quote lands (READER_QUOTE is null since #1311), and the glyph is decided with that quote
  'features/marketing/components/AskFilingDemo.tsx': { QuotesIcon: 1 }, // the Ask this Filing mark on the landing demo, decided with brand-copilot's (#1295) AskFilingAnswer entry, the same mark; #1311 left it
  'features/filings/components/AskFilingAnswer.tsx': { QuotesIcon: 2 }, // brand-copilot: a hand-drawn quotes glyph as the Ask this Filing mark
}
const RESIDUE_MAX = { files: 7, uses: 11 }

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
  // By declaration (heldValues.ts's scopeResolver): a named import of a glyph to its name and glyph, and the namespace
  // imports of the icon modules, whose members the shared model follows like any other value (a namespace held by
  // another name, assigned, destructured or passed on).
  const declarationOf = scopeResolver(sf)
  const local = new Map<ts.Node, [string, Glyph]>()
  const namespaces = new Set<ts.Node>()
  for (const stmt of sf.statements) {
    if (!ts.isImportDeclaration(stmt) || !ts.isStringLiteral(stmt.moduleSpecifier) || !isIconModule(stmt.moduleSpecifier.text, fileName)) continue
    const bindings = stmt.importClause?.namedBindings
    if (bindings && ts.isNamedImports(bindings)) {
      for (const el of bindings.elements) {
        const glyph = GLYPH_NAMES.get((el.propertyName ?? el.name).text)
        if (glyph) local.set(el, [el.name.text, glyph])
      }
    }
    // A namespace import (`import * as Icons from '@/lib/icons'`) draws a glyph through its members.
    if (bindings && ts.isNamespaceImport(bindings)) namespaces.add(bindings)
  }
  // Hand-drawn stand-ins: a function or const named for a glyph whose body draws an <svg>.
  const drawn = new Map<ts.Node, [string, Glyph]>()
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
    if (name && /^[A-Z]/.test(name) && drawsSvg(node)) {
      const hit = HAND_DRAWN.find(([, re]) => re.test(name))
      if (hit) drawn.set(node, [name, hit[0]])
    }
    ts.forEachChild(node, declare)
  }
  declare(sf)
  // A name read as a value: not the name an import or a destructuring binds (a declaration, or the key it
  // reads), nor a member's or a key's name (`Icons.SparkleIcon` reads the namespace, `{ SparkleIcon: x }` a key).
  const isReference = (n: ts.Identifier): boolean => {
    const p = n.parent
    if (ts.isImportSpecifier(p) || ts.isJsxAttribute(p)) return false
    // A destructuring element's name and key are declarations; its default is a read.
    if (ts.isBindingElement(p) && (p.name === n || p.propertyName === n)) return false
    if ((ts.isPropertyAccessExpression(p) || ts.isPropertyAssignment(p) || ts.isQualifiedName(p)) && (ts.isQualifiedName(p) ? p.right : p.name) === n) return false
    return true
  }
  // Where a glyph comes from, its root, keyed by its declaration or its place so that two bindings of one name stay
  // apart: an import's (`n:`), a hand-drawn stand-in's (`d:`), or a namespace's member where it is read or destructured
  // (`m:`). A root counts each read that reaches it, and once when nothing does (a bare import, a holder nobody reads).
  type Root = string
  const NAMESPACE: Root = 'ns'
  const glyphOf = new Map<Root, Glyph>()
  const rootAt = (prefix: string, node: ts.Node, glyph: Glyph): Root => {
    const root = `${prefix}:${node.getStart(sf)}`
    glyphOf.set(root, glyph)
    return root
  }
  for (const [declaration, [, glyph]] of local) rootAt('n', declaration, glyph)
  for (const [declaration, [, glyph]] of drawn) rootAt('d', declaration, glyph)
  /** The roots a name is by itself, by its declaration: an import's or a stand-in's; a namespace import is the
      namespace, a leaf whose members are glyphs (memberRoots). */
  const rootsOf = (x: ts.Expression): Root[] | undefined => {
    if (!ts.isIdentifier(x)) return undefined
    const declaration = declarationOf(x)
    if (!declaration) return undefined
    const imported = local.get(declaration)
    if (imported) return [rootAt('n', declaration, imported[1])]
    if (namespaces.has(declaration)) return [NAMESPACE]
    const stand = drawn.get(declaration)
    return stand ? [rootAt('d', declaration, stand[1])] : undefined
  }
  /** A namespace's member by name or literal key (`Icons.SparkleIcon`, `Icons['QuotesIcon']`, `const { QuotesIcon: Q }
      = Icons`) is its glyph, a root at the read or the binding; one read by a key the scan cannot read is none. */
  const memberRoots = (leaf: Root, key: string | undefined, node: ts.Node): Root[] | undefined => {
    const glyph = leaf === NAMESPACE && key !== undefined ? GLYPH_NAMES.get(key) : undefined
    return glyph ? [rootAt('m', node, glyph)] : undefined
  }
  // What each same-file binding holds, by the reading the heading-icon clause shares (tests/unit/heldValues.ts).
  const values = heldValues(sf, rootsOf, { memberLeaf: memberRoots })
  // Each read of a root, of a holder or of a holder's member. A hold counts where its holder is read, and a closing
  // tag repeats its opening tag's name: one use.
  const uses = new Map<Root, number>()
  const tally = (roots: Root[] | Map<Root, number>) => {
    for (const [root, n] of Array.isArray(roots) ? roots.map((root): [Root, number] => [root, 1]) : roots) uses.set(root, (uses.get(root) ?? 0) + n)
  }
  // A variable's or a parameter's own name declares it: not a read.
  const declares = (n: ts.Identifier) => (ts.isVariableDeclaration(n.parent) || ts.isParameter(n.parent)) && n.parent.name === n
  const ownsMember = (n: ts.Identifier) => (ts.isPropertyAccessExpression(n.parent) || ts.isElementAccessExpression(n.parent)) && n.parent.expression === n
  const visit = (node: ts.Node): void => {
    // Every ✨ in a literal is a use, so a second one in an already-listed literal counts.
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isJsxText(node)) {
      const sparkles = [...node.text.matchAll(/✨/gu)].length
      if (sparkles > 0) bump('SparkleIcon', sparkles)
    }
    if (values.held.has(node) || ts.isJsxClosingElement(node)) return
    // A same-file component's element (JSX or createElement) renders what the component returns: its glyphs count
    // here, at each render, and not inside the component.
    if (ts.isJsxSelfClosingElement(node) || ts.isJsxOpeningElement(node) || ts.isCallExpression(node)) {
      const rendered = leavesOf(values.renderOf(node))
      if (rendered.size > 0) tally(rendered)
    }
    // An assignment's target is written, not read.
    if (ts.isIdentifier(node) && isReference(node) && !isWrite(node)) {
      const own = rootsOf(node)
      if (own) tally(own)
      // A holder read whole (rendered, passed on, spread, iterated) reads every glyph it holds, as often as it renders it.
      else if (!declares(node) && !ownsMember(node)) {
        const holder = values.holderOf(node)
        if (holder) tally(leavesOf(holder))
      }
    }
    if ((ts.isPropertyAccessExpression(node) || ts.isElementAccessExpression(node)) && !isWrite(node)) {
      const own = rootsOf(node)
      if (own) {
        tally(own)
        return
      }
      // A holder's member, by name or literal key and nested or not, or every glyph it holds for a key the scan
      // cannot read: read here once, so its object is not read again whole.
      const read = leavesOf(values.valueOf(node))
      if (read.size > 0) {
        tally(read)
        return
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
      'export const A = () => (<><Spark /><Spark className="h-4 w-4"></Spark><QuoteMark /><ArrowRightIcon /><span>✨✨ Idea</span></>)',
      'const config = { Icon: QuotesIcon }',
    ].join('\n')
    // The two sparkle tags and both ✨ in the one literal (each emoji counts, the review's case).
    expect(glyphUses(src, 'probe.tsx')).toEqual({ SparkleIcon: 4, QuotesIcon: 3, BracketsCurlyIcon: 1 })
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
    // An object that spreads a glyph object holds its properties: three reads of the copy are three uses, and a
    // property written after the spread overrides the spread's.
    const spread = [
      "import { QuotesIcon, SparkleIcon } from '@/lib/icons'",
      'const base = { passage: QuotesIcon }',
      'const copy = { ...base }',
      'const over = { ...base, passage: SparkleIcon }',
      'export const E = () => <><copy.passage /><copy.passage /><copy.passage /><over.passage /></>',
    ].join('\n')
    expect(glyphUses(spread, 'features/zzprobe/Spread.tsx')).toEqual({ QuotesIcon: 3, SparkleIcon: 1 })
    // A binding keeps the shape of what it holds (tests/unit/heldValues.ts): an alias of an object spread into another
    // (the review's case, read three times), an object nested in another read through two members (twice), and a
    // member destructured from an object (once).
    const shapes = [
      "import { QuotesIcon } from '@/lib/icons'",
      'const base = { passage: QuotesIcon }',
      'const alias = base',
      'const copy = { ...alias }',
      'const NEST = { inner: { passage: QuotesIcon } }',
      'const { passage: Passage } = base',
      'export const F = () => <><copy.passage /><copy.passage /><copy.passage /><NEST.inner.passage /><NEST.inner.passage /><Passage /></>',
    ].join('\n')
    expect(glyphUses(shapes, 'features/zzprobe/Shapes.tsx')).toEqual({ QuotesIcon: 6 })
    // A JSX value holds what its children hold, as many times as it renders them: a fragment and a wrapper element,
    // each placed twice; a value that renders the glyph twice, placed once (the review's case: two uses); and a
    // conditional between that value and one glyph, which counts its larger arm (two more).
    const jsx = [
      "import { QuotesIcon } from '@/lib/icons'",
      'const frag = <><QuotesIcon /></>',
      "const chip = <span className='inline-flex'><QuotesIcon /></span>",
      'const pair = <><QuotesIcon /><QuotesIcon /></>',
      'const either = ok ? pair : <QuotesIcon />',
      'export const G = () => <>{frag}{frag}{chip}{chip}{pair}{either}</>',
    ].join('\n')
    expect(glyphUses(jsx, 'features/zzprobe/Jsx.tsx')).toEqual({ QuotesIcon: 8 })
    // A name two functions declare reads its own function's binding (the review's case): P's Mark is the quotes, Q's
    // the sparkle twice, and R's is not a glyph, so its read adds nothing.
    const shadowed = [
      "import { QuotesIcon, SparkleIcon } from '@/lib/icons'",
      'export function P() { const Mark = QuotesIcon; return <Mark /> }',
      'export function Q() { const Mark = SparkleIcon; return <><Mark /><Mark /></> }',
      'export function R() { const Mark = Other; return <Mark /> }',
    ].join('\n')
    expect(glyphUses(shadowed, 'features/zzprobe/Shadowed.tsx')).toEqual({ QuotesIcon: 1, SparkleIcon: 2 })
    // An array holds its elements by index (the review's case: `marks[0]` read twice is two uses): a read by a key the
    // scan cannot read is any element, a literal index on the array itself reads its element, and past a spread a
    // literal index may read any element from the spread on.
    const arrays = [
      "import { QuotesIcon, SparkleIcon } from '@/lib/icons'",
      'const marks = [<QuotesIcon />, <SparkleIcon />]',
      'const Picked = [QuotesIcon][0]',
      'const more = [...marks, <QuotesIcon />]',
      'export const H = ({ i }: { i: number }) => <>{marks[0]}{marks[0]}{marks[i]}<Picked />{more[2]}</>',
    ].join('\n')
    expect(glyphUses(arrays, 'features/zzprobe/Arrays.tsx')).toEqual({ QuotesIcon: 5, SparkleIcon: 2 })
    // A member destructured from an array, and from an object nested in one, counts at each read (the review's case:
    // `const [Mark] = [QuotesIcon]` read twice is two uses).
    const destructured = [
      "import { QuotesIcon, SparkleIcon } from '@/lib/icons'",
      'const [Mark] = [QuotesIcon]',
      'const [{ passage: Passage }] = [{ passage: SparkleIcon }]',
      'export const I = () => <><Mark /><Mark /><Passage /></>',
    ].join('\n')
    expect(glyphUses(destructured, 'features/zzprobe/Destructured.tsx')).toEqual({ QuotesIcon: 2, SparkleIcon: 1 })
    // A destructuring default holds its glyph where the member is missing (the review's case), and so does a
    // parameter's default: Mark and G are each read twice, Glyph once.
    const defaults = [
      "import { QuotesIcon, SparkleIcon } from '@/lib/icons'",
      'const { mark: Mark = QuotesIcon } = {}',
      'const [Glyph = SparkleIcon] = []',
      'export const J = () => <><Mark /><Mark /><Glyph /></>',
      'export function K({ glyph: G = QuotesIcon }: { glyph?: () => null }) { return <><G /><G /></> }',
    ].join('\n')
    expect(glyphUses(defaults, 'features/zzprobe/Defaults.tsx')).toEqual({ QuotesIcon: 4, SparkleIcon: 1 })
    // A parameter that shadows an import is not the import: P's two reads are its prop's, so QuotesIcon is a bare import.
    const shadowedImport = [
      "import { QuotesIcon, SparkleIcon } from '@/lib/icons'",
      'export function P({ QuotesIcon }: { QuotesIcon: () => null }) { return <><QuotesIcon /><QuotesIcon /></> }',
      'export function Q() { return <><SparkleIcon /><SparkleIcon /></> }',
    ].join('\n')
    expect(glyphUses(shadowedImport, 'features/zzprobe/ShadowedImport.tsx')).toEqual({ QuotesIcon: 1, SparkleIcon: 2 })
    // Every way a name is given a glyph (tests/unit/heldValues.ts; lessons/test-gates-must-be-as-wide-as-their-rule.md),
    // each counted where the name is read, never where it is given: an assignment after the declaration read twice (the
    // review's case), a logical assignment, a destructuring assignment and its default, a loop's variable, a parameter at
    // a direct call, a component's prop and its children, a callback handed to an array's method and to a same-file
    // function, a function's return, what is put in an object and an array after they are made, Object.values, React's
    // createElement of a same-file component and Children.map, and useMemo. Each is read twice where it renders, so the
    // count tells the reading from the one bare reference a glyph has where it is given. A name given another icon holds
    // no glyph.
    const given = (lines: string[]) =>
      glyphUses(
        [`import { ${GLYPHS.filter((g) => lines.some((l) => l.includes(g))).join(', ')} } from '@/lib/icons'`, ...lines].join('\n'),
        'features/zzprobe/Given.tsx',
      )
    expect(given(['let Mark; Mark = QuotesIcon', 'export const A = () => <><Mark /><Mark /></>'])).toEqual({ QuotesIcon: 2 })
    expect(given(['let Mark = null; Mark ??= SparkleIcon', 'export const B = () => <><Mark /><Mark /></>'])).toEqual({ SparkleIcon: 2 })
    expect(given(['let A, B; ({ passage: A, fact: B = BracketsCurlyIcon } = { passage: QuotesIcon })', 'export const C = () => <><A /><A /><B /><B /></>'])).toEqual({
      QuotesIcon: 2,
      BracketsCurlyIcon: 2,
    })
    expect(given(['export function D() { for (const Mark of [QuotesIcon, SparkleIcon]) return <><Mark /><Mark /></> }'])).toEqual({ QuotesIcon: 2, SparkleIcon: 2 })
    expect(given(['function render(Mark) { return <><Mark /><Mark /></> }', 'export const E = () => render(QuotesIcon)'])).toEqual({ QuotesIcon: 2 })
    expect(
      given(['function Chip({ icon: Icon, children }) { return <span><Icon /><Icon />{children}{children}</span> }', 'export const F = () => <Chip icon={SparkleIcon}><QuotesIcon /></Chip>']),
    ).toEqual({ SparkleIcon: 2, QuotesIcon: 2 })
    expect(given(['export const G = () => <>{[QuotesIcon, SparkleIcon].map((Mark) => <span key="m"><Mark /><Mark /></span>)}</>'])).toEqual({ QuotesIcon: 2, SparkleIcon: 2 })
    expect(given(['function each(cb) { return cb(BracketsCurlyIcon) }', 'export const H = () => each((Mark) => <><Mark /><Mark /></>)'])).toEqual({ BracketsCurlyIcon: 2 })
    expect(given(['const pick = () => QuotesIcon', 'const Picked = pick()', 'export const I = () => <><Picked /><Picked /></>'])).toEqual({ QuotesIcon: 2 })
    expect(
      given(['const BOX = {}', 'BOX.mark = SparkleIcon', 'const LIST = []', 'LIST.push(QuotesIcon)', 'export const J = () => <><BOX.mark /><BOX.mark />{LIST.map((M) => <span key="m"><M /><M /></span>)}</>']),
    ).toEqual({ SparkleIcon: 2, QuotesIcon: 2 })
    expect(given(['const GLYPHS = { passage: QuotesIcon }', 'export const K = () => <>{Object.values(GLYPHS).map((G) => <span key="g"><G /><G /></span>)}</>'])).toEqual({ QuotesIcon: 2 })
    expect(given(['function Badge({ icon: Icon }) { return <><Icon /><Icon /></> }', 'export const L = () => createElement(Badge, { icon: QuotesIcon })'])).toEqual({ QuotesIcon: 2 })
    expect(
      given(['function List({ children }) { return <ul>{Children.map(children, (child) => <li>{child}{child}</li>)}</ul> }', 'export const M = () => <List><SparkleIcon /></List>']),
    ).toEqual({ SparkleIcon: 2 })
    expect(given(['export function N() { const Mark = useMemo(() => QuotesIcon, []); return <><Mark /><Mark /></> }'])).toEqual({ QuotesIcon: 2 })
    // A call that gives back what it is given holds it (the review's case: `memo(() => <QuotesIcon />)` rendered three
    // times is three uses): React's memo and forwardRef, nested and read through React, Object.assign's target (a
    // compound component, rendered as itself and as its part) and Object.freeze.
    expect(given(['const Mark = memo(() => <QuotesIcon />)', 'export const A = () => <><Mark /><Mark /><Mark /></>'])).toEqual({ QuotesIcon: 3 })
    expect(given(['const Both = React.memo(forwardRef((props, ref) => <SparkleIcon />))', 'export const B = () => <><Both /><Both /></>'])).toEqual({ SparkleIcon: 2 })
    expect(given(['function Root() { return <QuotesIcon /> }', 'const Card = Object.assign(Root, { Part: Root })', 'export const C = () => <><Card /><Card.Part /></>'])).toEqual({
      QuotesIcon: 2,
    })
    expect(given(['const MARKS = Object.freeze({ passage: BracketsCurlyIcon })', 'export const D = () => <><MARKS.passage /><MARKS.passage /></>'])).toEqual({
      BracketsCurlyIcon: 2,
    })
    // React's utilities under another name are what they are (the review's case: `Children as Kids` then
    // `Kids.only(<QuotesIcon />)` placed twice is two uses): Children destructured under another name, a renamed
    // createElement and memo, and a same-file alias of useMemo.
    expect(given(["import { Children as Kids } from 'react'", 'const mark = Kids.only(<QuotesIcon />)', 'export const E = () => <>{mark}{mark}</>'])).toEqual({ QuotesIcon: 2 })
    expect(given(['const { Children: Kin } = React', 'const marks = Kin.toArray(<SparkleIcon />)', 'export const F = () => <>{marks}{marks}</>'])).toEqual({ SparkleIcon: 2 })
    expect(given(["import { createElement as h } from 'react'", 'function PassageMark() { return <QuotesIcon /> }', 'export const G = () => [h(PassageMark), h(PassageMark)]'])).toEqual({
      QuotesIcon: 2,
    })
    expect(given(["import { memo as keep } from 'react'", 'const Mark = keep(() => <BracketsCurlyIcon />)', 'export const H = () => <><Mark /><Mark /></>'])).toEqual({
      BracketsCurlyIcon: 2,
    })
    expect(given(['const memoize = useMemo', 'export function I() { const Mark = memoize(() => SparkleIcon, []); return <><Mark /><Mark /></> }'])).toEqual({
      SparkleIcon: 2,
    })
    // A name declared again in its scope is one binding (the review's case: `var Mark; var Mark = QuotesIcon` read twice
    // is two uses), and an alias under either declaration is what it aliases; an overload's signature declares nothing,
    // so the implementation draws; and a function's parameter shadows the function's own name, which is no read of the
    // parameter (an expression's, and a declaration's: `function Echo(Echo)` called once draws through its parameter twice).
    expect(given(['var Mark; var Mark = QuotesIcon', 'export const J = () => <><Mark /><Mark /></>'])).toEqual({ QuotesIcon: 2 })
    expect(given(['var memoize; var memoize = useMemo', 'export function K() { const Mark = memoize(() => SparkleIcon, []); return <><Mark /><Mark /></> }'])).toEqual({
      SparkleIcon: 2,
    })
    expect(given(['function Drawn(): ReactNode', 'function Drawn() { return <QuotesIcon /> }', 'export const L = () => <><Drawn /><Drawn /></>'])).toEqual({ QuotesIcon: 2 })
    expect(given(['const show = function Glyph(Glyph) { return <><Glyph /><Glyph /></> }', 'export const M = () => show(SparkleIcon)'])).toEqual({ SparkleIcon: 2 })
    expect(given(['function Echo(Echo) { return <><Echo /><Echo /></> }', 'export const N = () => Echo(QuotesIcon)'])).toEqual({ QuotesIcon: 2 })
    expect(given(["import { ArrowRightIcon } from '@/lib/icons'", 'let Mark; Mark = ArrowRightIcon', 'export const O = () => <Mark />'])).toEqual({})
    // A rest element takes the rest (the review's case: `const [...Marks] = [QuotesIcon]` read twice is two uses): an
    // array's elements from its place on, re-indexed, so `Others[0]` reads the second glyph alone; an object's
    // properties the pattern does not name, so `rest.passage` and `o.a` read nothing; a rest in a destructuring
    // assignment, array and object, and in a component's props; and a rest parameter, each argument at its position, so `marks[1]` reads
    // the second argument alone and the whole renders each argument.
    expect(given(['const [...Marks] = [QuotesIcon]', 'export const A = () => <>{createElement(Marks[0])}{createElement(Marks[0])}</>'])).toEqual({ QuotesIcon: 2 })
    expect(given(['const [, ...Others] = [SparkleIcon, QuotesIcon, BracketsCurlyIcon]', 'const Next = Others[0]', 'export const B = () => <><Next /><Next /></>'])).toEqual({
      SparkleIcon: 1,
      QuotesIcon: 2,
      BracketsCurlyIcon: 1,
    })
    expect(given(['const { passage, ...rest } = { passage: SparkleIcon, fact: QuotesIcon }', 'export const C = () => <><rest.fact /><rest.fact /><rest.passage /><rest.passage /></>'])).toEqual({
      QuotesIcon: 2,
      SparkleIcon: 1,
    })
    expect(given(['let first, more; [first, ...more] = [SparkleIcon, QuotesIcon]', 'export const D = () => <>{createElement(more[0])}{createElement(more[0])}</>'])).toEqual({
      QuotesIcon: 2,
      SparkleIcon: 1,
    })
    expect(given(['let a, o; ({ a, ...o } = { a: SparkleIcon, mark: QuotesIcon })', 'export const E = () => <><o.mark /><o.mark /><o.a /><o.a /></>'])).toEqual({
      QuotesIcon: 2,
      SparkleIcon: 1,
    })
    expect(given(['function Chip({ label, ...marks }) { return <><marks.icon /><marks.icon /></> }', "export const F = () => <Chip label='x' icon={QuotesIcon} />"])).toEqual({ QuotesIcon: 2 })
    expect(given(['function pair(...marks) { const Second = marks[1]; return <><Second /><Second /></> }', 'export const G = () => pair(SparkleIcon, QuotesIcon)'])).toEqual({
      SparkleIcon: 1,
      QuotesIcon: 2,
    })
    expect(given(['function All(...marks) { return <>{marks}{marks}</> }', 'export const H = () => All(<QuotesIcon />, <QuotesIcon />)'])).toEqual({ QuotesIcon: 4 })
    // A glyph a same-file component draws counts at each place the component is rendered (the review's case: rendered
    // twice is two uses), by JSX or createElement, through a component that renders another, and once where it is drawn
    // when the file never renders the component.
    expect(given(['function PassageMark() { return <QuotesIcon /> }', 'export const U = () => <><PassageMark /><PassageMark /></>'])).toEqual({ QuotesIcon: 2 })
    expect(given(['function PassageMark() { return <QuotesIcon /> }', 'export const V = () => [createElement(PassageMark), createElement(PassageMark)]'])).toEqual({ QuotesIcon: 2 })
    expect(
      given(['function Inner() { return <QuotesIcon /> }', 'function Outer() { return <><Inner /><Inner /></> }', 'export const W = () => <><Outer /><Outer /></>']),
    ).toEqual({ QuotesIcon: 4 })
    expect(given(['export function PassageMark() { return <QuotesIcon /> }'])).toEqual({ QuotesIcon: 1 })
    // A namespace is a value like any other (the review's case: assigned after its declaration, two reads are two uses),
    // passed as a prop to a component rendered twice; and each root is its own declaration's, so two functions' `Mark`,
    // each destructured from the namespace, keep their own glyphs (the review's case).
    const namespaced = (lines: string[], file: string) => glyphUses(["import * as Icons from '@/lib/icons'", ...lines].join('\n'), `features/zzprobe/${file}.tsx`)
    expect(namespaced(['let Marks; Marks = Icons', 'export const X = () => <><Marks.QuotesIcon /><Marks.QuotesIcon /></>'], 'Assigned')).toEqual({ QuotesIcon: 2 })
    expect(namespaced(['function Show({ set }) { return <set.SparkleIcon /> }', 'export const Y = () => <><Show set={Icons} /><Show set={Icons} /></>'], 'Prop')).toEqual({
      SparkleIcon: 2,
    })
    expect(
      namespaced(
        ['export function P() { const { QuotesIcon: Mark } = Icons; return <Mark /> }', 'export function Q() { const { SparkleIcon: Mark } = Icons; return <><Mark /><Mark /></> }'],
        'TwoMarks',
      ),
    ).toEqual({ QuotesIcon: 1, SparkleIcon: 2 })
    // A namespace's rest keeps its other members: `Rest.SparkleIcon` read twice is two uses.
    expect(namespaced(['const { QuotesIcon: Q, ...Rest } = Icons', 'export const Z = () => <><Rest.SparkleIcon /><Rest.SparkleIcon /></>'], 'Rest')).toEqual({
      SparkleIcon: 2,
      QuotesIcon: 1,
    })
    // The model's one over-count, named in heldValues.ts's header: a parameter holds what every call passes it, so a
    // component rendered once with each of two glyphs counts both at each render. It fails closed (no app file passes a
    // reserved glyph as a prop); telling calls apart would take a context-sensitive model.
    expect(given(['function Show({ icon: Icon }) { return <Icon /> }', 'export const X = () => <><Show icon={QuotesIcon} /><Show icon={SparkleIcon} /></>'])).toEqual({
      QuotesIcon: 2,
      SparkleIcon: 2,
    })
    // Out of reach, planted as the gaps the header names: a glyph held in React state, a class's field read through
    // `this`, a promise's then and a generator's yield each count once where they are written, though each renders it
    // twice; and a glyph an app module exports is not known for one.
    expect(given(['export function P() { const [Mark] = useState(() => QuotesIcon); return <><Mark /><Mark /></> }'])).toEqual({ QuotesIcon: 1 })
    expect(given(['export class Q { mark = QuotesIcon; render() { return <><this.mark /><this.mark /></> } }'])).toEqual({ QuotesIcon: 1 })
    expect(given(['export const R = () => Promise.resolve(QuotesIcon).then((Mark) => <><Mark /><Mark /></>)'])).toEqual({ QuotesIcon: 1 })
    expect(given(['function* marks() { yield QuotesIcon }', 'export function S() { for (const Mark of marks()) return <><Mark /><Mark /></> }'])).toEqual({ QuotesIcon: 1 })
    expect(glyphUses(["import { EvidenceMark } from './marks'", 'export const T = () => <><EvidenceMark /><EvidenceMark /></>'].join('\n'), 'features/zzprobe/Imported.tsx')).toEqual({})
    // A declaration that reads itself would count without end: the scan throws.
    const cycle = [
      "import { QuotesIcon } from '@/lib/icons'",
      'export function A() { const a = <>{a}<QuotesIcon /></>; return a }',
    ].join('\n')
    expect(() => glyphUses(cycle, 'features/zzprobe/Cycle.tsx')).toThrow('features/zzprobe/Cycle.tsx: what a same-file binding holds reads itself')
  })
})
