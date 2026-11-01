/* =============================================================================
   trailingArrowRun.spec.ts: a trailing glyph keeps with its last word
   -----------------------------------------------------------------------------
   A label with a trailing glyph is TrailingArrowLabel: its glyph and its last
   word's last letter in one no-wrap run, so a label that wraps under 200% text
   carries the glyph onto its last line (DESIGN_SYSTEM.md §4, Trailing arrow;
   E272, E274, E275, E276, E279). The glyph is the arrow, or the external link's square
   (glyph="external"). A glyph drawn as the last item of a flex row after the
   words parts from them when they wrap: it sits at the row's far edge, centred
   on the box, never after the last word. Review found the fault link by link,
   so this scan fails any element whose last child is a bare ArrowRightIcon or
   ArrowSquareOutIcon after its words (text, an expression or an element
   before it), whatever the element: a Link, an a, or a span inside one.

   What a reader sees decides it, so the scan reads past what a screen reader
   alone hears: an sr-only element (a new-tab cue) is neither words nor the
   last child. And it reads a glyph where a fragment, or a component of the
   same file, draws only one: the Copilot Sources list's locator drew its
   square through such a component (OpensOriginal, before E279).

   A button's glyph stays in its flex row, since the button's box binds it: an
   element styled by buttonVariants() (its class attribute calls it), a Button
   and a MarketingCta pass, and so does the component's own run. A glyph alone
   (an icon link) and a glyph before the words are no trailing glyph. So are
   the row marks, held by name below: a square that marks a whole row link,
   not a label's words.

   The remedy holds only outside a flex or grid row: in one, the label's words
   and its run are two items, so the run sits beside the wrapped words, not
   after them. So an element with a TrailingArrowLabel among its
   children also fails where its class attributes make it a flex or grid row
   at any width (flex, inline-flex, grid or inline-grid, behind any variant):
   a link that stands alone and can wrap is inline-block. It reads those
   classes in the attribute and through each const of the file the attribute
   names, resolved by scope (the Copilot locators' LOCATOR_LINK), so a
   parameter that shadows a const reads as none.

   It reads each file's TypeScript AST (tests/unit/classListScan.ts's parser),
   so comments never count. It looks through a fragment to the element that
   lays its children out, and through a conditional (`&&`, `||`, `??`, a
   ternary's arms) to the glyph or the label it may render. Out of reach: a
   glyph a component renders after children it is passed, a glyph or a label
   held in a variable (FigureReceipt's and SourceTrace's chip glyphs lead their
   words), a component from another file, a glyph inside an element of its own
   (which may be an icon control, not part of the label), other glyphs after a
   link's words (a caret), and a row class that a call builds, an import holds
   or an object's key holds. Planted cases hold the reader.
============================================================================= */

import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { bindingResolver, type Binding } from './astBindings'
import { CLASS_ATTRIBUTE, literalTexts, parse, sourceFiles, tokensOf } from './classListScan'

const ROOT = path.join(__dirname, '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']
const COMPONENT = 'components/ui/TrailingArrowLabel.tsx'
const LABEL = 'TrailingArrowLabel'
// The trailing glyphs: the arrow, and the external link's square (E279).
const GLYPHS = new Set(['ArrowRightIcon', 'ArrowSquareOutIcon'])
// A class that makes its element a flex or grid row, behind any variant prefix and with `!` either side.
const ROW = /(?:^|:)!?(?:inline-)?(?:flex|grid)!?$/
// The button components whose box binds the glyph (DESIGN_SYSTEM.md §4, Trailing arrow).
const BUTTONS = new Set(['Button', 'MarketingCta'])
// The row marks, by file and the tag that lays the square out: a square that marks a whole row link, not a label's
// words. The filing index's row link, whose square stands alone below 48rem and follows its one word "SEC.gov" from
// there (chief design on #1914, 5728343724), and the full-text search's result row, whose square stands at the row's
// top right beside its lines (E279).
const ROW_MARKS = ['features/filings/components/FilingIndex.tsx <a>', 'features/search/components/FullTextSearch.tsx <>']

interface Site {
  file: string
  line: number
  tag: string
  // The glyph or glyphs the last child may draw, joined by '|'.
  glyph: string
  // Why the glyph stands: a button's box binds it, it marks a row, or it is the component's own run.
  binds: 'button' | 'row' | 'component' | null
}

type Element = ts.JsxElement

const tagOf = (element: Element, sourceFile: ts.SourceFile) => element.openingElement.tagName.getText(sourceFile)

/** A site's file and the tag that lays its glyph out, as ROW_MARKS writes it: `<a>`, or `<>` for a fragment no element
    lays out. */
const placeOf = (site: { file: string; tag: string }) => `${site.file} ${site.tag === '<>' ? '<>' : `<${site.tag}>`}`

/** True where the node is an element whose class attributes carry sr-only: words for a screen reader alone. */
function srOnly(node: ts.JsxChild, sourceFile: ts.SourceFile): boolean {
  const attributes = ts.isJsxElement(node) ? node.openingElement.attributes : ts.isJsxSelfClosingElement(node) ? node.attributes : null
  return (attributes?.properties ?? []).some(
    (attribute) =>
      ts.isJsxAttribute(attribute) &&
      CLASS_ATTRIBUTE.test(attribute.name.getText(sourceFile)) &&
      !!attribute.initializer &&
      literalTexts(attribute.initializer).flatMap(tokensOf).includes('sr-only'),
  )
}

/** The children a reader sees: no whitespace-only text, no empty expression (a JSX comment is one), no sr-only element. */
const visible = (children: ts.NodeArray<ts.JsxChild>, sourceFile: ts.SourceFile) =>
  children.filter(
    (child) => !(ts.isJsxText(child) && child.text.trim() === '') && !(ts.isJsxExpression(child) && !child.expression) && !srOnly(child, sourceFile),
  )

type Rendered = ts.JsxElement | ts.JsxSelfClosingElement | ts.JsxFragment

/** What a JSX child may render at its top: itself where it is an element or a fragment, and through an expression,
    parentheses and a conditional (`&&`'s right side, either side of `||` or `??`, a ternary's arms). */
function branches(node: ts.Node): Rendered[] {
  if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node) || ts.isJsxFragment(node)) return [node]
  if (ts.isJsxExpression(node)) return node.expression ? branches(node.expression) : []
  if (ts.isParenthesizedExpression(node)) return branches(node.expression)
  if (ts.isConditionalExpression(node)) return [...branches(node.whenTrue), ...branches(node.whenFalse)]
  if (ts.isBinaryExpression(node)) {
    const operator = node.operatorToken.kind
    if (operator === ts.SyntaxKind.AmpersandAmpersandToken) return branches(node.right)
    if (operator === ts.SyntaxKind.BarBarToken || operator === ts.SyntaxKind.QuestionQuestionToken) return [...branches(node.left), ...branches(node.right)]
  }
  return []
}

const nameOf = (node: Rendered, sourceFile: ts.SourceFile) =>
  ts.isJsxFragment(node) ? null : (ts.isJsxElement(node) ? node.openingElement.tagName : node.tagName).getText(sourceFile)

/** True where `node` is a JSX element of that name. */
const named = (node: Rendered, name: string, sourceFile: ts.SourceFile) => nameOf(node, sourceFile) === name

/** The glyphs `node` draws where it draws nothing else a reader sees: a glyph, a component of `drawers` (the file's own
    components that draw only a glyph), or a fragment whose one visible child may draw one. Empty where it draws more. */
function glyphsDrawn(node: Rendered, drawers: Map<string, string[]>, sourceFile: ts.SourceFile): string[] {
  const name = nameOf(node, sourceFile)
  if (name !== null) return GLYPHS.has(name) ? [name] : drawers.get(name) ?? []
  const children = visible(node.children, sourceFile)
  return children.length === 1 ? branches(children[0]).flatMap((branch) => glyphsDrawn(branch, drawers, sourceFile)) : []
}

/** What a function returns at its top: an expression body, or each return statement that is not a nested function's. */
function returned(fn: ts.SignatureDeclaration & { body?: ts.Node }): ts.Expression[] {
  if (!fn.body) return []
  if (!ts.isBlock(fn.body)) return [fn.body as ts.Expression]
  const out: ts.Expression[] = []
  const visit = (node: ts.Node): void => {
    if (ts.isReturnStatement(node)) {
      if (node.expression) out.push(node.expression)
    } else if (!ts.isFunctionLike(node)) ts.forEachChild(node, visit)
  }
  ts.forEachChild(fn.body, visit)
  return out
}

/** The file's components (a capitalized function or a capitalized const bound to one) that may draw a glyph and nothing
    else a reader sees, with the glyphs each draws; a component drawn by another such component counts too. */
function glyphDrawers(sourceFile: ts.SourceFile): Map<string, string[]> {
  const components: Array<[string, ts.SignatureDeclaration & { body?: ts.Node }]> = []
  const visit = (node: ts.Node): void => {
    if (ts.isFunctionDeclaration(node) && node.name && /^[A-Z]/.test(node.name.text)) components.push([node.name.text, node])
    if (
      ts.isVariableDeclaration(node) &&
      ts.isIdentifier(node.name) &&
      /^[A-Z]/.test(node.name.text) &&
      node.initializer &&
      (ts.isArrowFunction(node.initializer) || ts.isFunctionExpression(node.initializer))
    ) {
      components.push([node.name.text, node.initializer])
    }
    ts.forEachChild(node, visit)
  }
  visit(sourceFile)
  // Until no set grows: a component read before the one it draws through gains that one's glyphs on the next pass.
  const drawers = new Map<string, string[]>()
  for (let changed = true; changed; ) {
    changed = false
    for (const [name, fn] of components) {
      const glyphs = [...new Set(returned(fn).flatMap(branches).flatMap((branch) => glyphsDrawn(branch, drawers, sourceFile)))].sort()
      if (glyphs.length && glyphs.join('|') !== (drawers.get(name) ?? []).join('|')) {
        drawers.set(name, glyphs)
        changed = true
      }
    }
  }
  return drawers
}

/** The element that lays out a fragment's children: its nearest element ancestor, through any expression, or none
    where the fragment is what a component returns. */
function hostOf(node: ts.Node): Element | null {
  let up = node.parent
  while (up && (ts.isJsxExpression(up) || ts.isParenthesizedExpression(up) || ts.isConditionalExpression(up) || ts.isBinaryExpression(up) || ts.isJsxFragment(up))) {
    up = up.parent
  }
  return up && ts.isJsxElement(up) ? up : null
}

/** True where the element's class attributes call buttonVariants(), alone or inside a joiner. */
function styledAsButton(element: Element): boolean {
  let found = false
  const visit = (node: ts.Node): void => {
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'buttonVariants') found = true
    else ts.forEachChild(node, visit)
  }
  for (const attribute of element.openingElement.attributes.properties) {
    if (ts.isJsxAttribute(attribute) && CLASS_ATTRIBUTE.test(attribute.name.getText()) && attribute.initializer) visit(attribute.initializer)
  }
  return found
}

/** Every element or fragment in `source` whose last visible child is, or may draw, a bare glyph after its words. A
    fragment's row is its host element's, so the host's tag and button styling decide it. */
function trailingArrowSites(source: string, file: string): Site[] {
  const sourceFile = parse(source, file)
  const drawers = glyphDrawers(sourceFile)
  const sites: Site[] = []
  const visit = (node: ts.Node): void => {
    if (ts.isJsxElement(node) || ts.isJsxFragment(node)) {
      const children = visible(node.children, sourceFile)
      const last = children[children.length - 1]
      const glyphs = last && children.length > 1 ? [...new Set(branches(last).flatMap((branch) => glyphsDrawn(branch, drawers, sourceFile)))].sort() : []
      if (glyphs.length) {
        const host = ts.isJsxElement(node) ? node : hostOf(node)
        const tag = host ? tagOf(host, sourceFile) : '<>'
        const binds =
          file === COMPONENT
            ? 'component'
            : host && (BUTTONS.has(tag) || styledAsButton(host))
              ? 'button'
              : ROW_MARKS.includes(placeOf({ file, tag }))
                ? 'row'
                : null
        sites.push({ file, line: sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1, tag, glyph: glyphs.join('|'), binds })
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(sourceFile)
  return sites
}

/** The class tokens of a class attribute's value: its strings and template chunks, and the same of each const of the file
    that an identifier in it names as a value (not a callee, not either side of a member access), resolved by scope and
    followed through consts that name others. A parameter or a destructured name has no initializer, so it reads as none. */
function classTokens(value: ts.Node, resolve: (ref: ts.Identifier) => Binding | undefined): string[] {
  const seen = new Set<ts.Node>()
  const read = (node: ts.Node): string[] => {
    const tokens = literalTexts(node).flatMap(tokensOf)
    const visit = (n: ts.Node): void => {
      if (ts.isIdentifier(n) && !ts.isPropertyAccessExpression(n.parent) && !(ts.isCallExpression(n.parent) && n.parent.expression === n)) {
        const binding = resolve(n)
        if (binding?.init && !seen.has(binding.decl)) {
          seen.add(binding.decl)
          tokens.push(...read(binding.init))
        }
      }
      ts.forEachChild(n, visit)
    }
    visit(node)
    return tokens
  }
  return read(value)
}

interface Parent {
  file: string
  line: number
  tag: string
  // The classes that make the parent a flex or grid row.
  rows: string[]
}

/** Every element in `source` with a TrailingArrowLabel among its children (behind a conditional or inside a fragment
    too), and the row classes it carries. */
function labelParents(source: string, file: string): Parent[] {
  const sourceFile = parse(source, file)
  const resolve = bindingResolver(sourceFile)
  const parents: Parent[] = []
  const rendersLabel = (child: ts.Node): boolean =>
    branches(child).some((branch) => named(branch, LABEL, sourceFile) || (ts.isJsxFragment(branch) && branch.children.some(rendersLabel)))
  const visit = (node: ts.Node): void => {
    if (ts.isJsxElement(node) && node.children.some(rendersLabel)) {
      const tokens = node.openingElement.attributes.properties.flatMap((attribute) =>
        ts.isJsxAttribute(attribute) && CLASS_ATTRIBUTE.test(attribute.name.getText(sourceFile)) && attribute.initializer
          ? classTokens(attribute.initializer, resolve)
          : [],
      )
      parents.push({
        file,
        line: sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1,
        tag: tagOf(node, sourceFile),
        rows: tokens.filter((token) => ROW.test(token)),
      })
    }
    ts.forEachChild(node, visit)
  }
  visit(sourceFile)
  return parents
}

const where = (site: Site) => `${placeOf(site)}:${site.line} ${site.glyph}`

describe('a trailing glyph keeps with its last word (DESIGN_SYSTEM.md §4, Trailing arrow)', () => {
  const sources = sourceFiles(ROOT, SCAN_DIRS).map((file) => ({ file, source: fs.readFileSync(path.join(ROOT, file), 'utf8') }))
  const sites = sources.flatMap(({ file, source }) => trailingArrowSites(source, file))
  const parents = sources.flatMap(({ file, source }) => labelParents(source, file))

  it('reads the glyphs that stand: the buttons that bind theirs, and the component run with both glyphs', () => {
    const standing = sites.filter((site) => site.binds === 'button' || site.binds === 'component').map((site) => `${site.file} ${site.binds} ${site.glyph}`)
    // One of each kind the scan lets stand, the square's button among them, so a reader that finds no trailing arrow or
    // no square at all fails here.
    expect(standing).toEqual(
      expect.arrayContaining([
        `${COMPONENT} component ArrowRightIcon|ArrowSquareOutIcon`,
        'features/marketing/components/LandingHero.tsx button ArrowRightIcon',
        'app/company/[ticker]/page-client.tsx button ArrowRightIcon',
        'features/filings/components/copilot/FilingViewer.tsx button ArrowSquareOutIcon',
      ]),
    )
  })

  it('reads the two row marks, and only those', () => {
    expect(sites.filter((site) => site.binds === 'row').map(placeOf)).toEqual(ROW_MARKS)
  })

  it('finds no label that ends in a bare glyph after its words: it takes TrailingArrowLabel', () => {
    expect(sites.filter((site) => site.binds === null).map(where)).toEqual([])
  })

  it('reads every TrailingArrowLabel caller, and sets none in a flex or grid row', () => {
    // The thirteen callers (E272, E274, E275, E276, E279), so a reader that finds no label fails here.
    expect([...new Set(parents.map((parent) => parent.file))].sort()).toEqual([
      'app/waitlist/page.tsx',
      'features/calendar/components/ReportingThisWeek.tsx',
      'features/companies/components/CompanyIdentity.tsx',
      'features/dashboard/components/FilingFeed.tsx',
      'features/dashboard/components/WhatChangedCard.tsx',
      'features/dashboard/components/YourCompanies.tsx',
      'features/filings/components/ComparePeriodsCard.tsx',
      'features/filings/components/FilingIdentity.tsx',
      'features/filings/components/FilingsHistoryNote.tsx',
      'features/filings/components/copilot/CopilotMessage.tsx',
      'features/filings/components/copilot/FilingViewer.tsx',
      'features/filings/components/copilot/FilingWorkspace.tsx',
      'features/marketing/components/HeroExample.tsx',
    ])
    expect(parents.filter((parent) => parent.rows.length > 0).map((parent) => `${parent.file}:${parent.line} <${parent.tag}> ${parent.rows.join(' ')}`)).toEqual([])
  })
})

describe('the trailing-arrow reader, on planted sources', () => {
  const planted = (source: string, file = 'planted.tsx') => trailingArrowSites(source, file)
  const faults = (source: string) => planted(source).filter((site) => site.binds === null).map((site) => site.tag)

  it('finds a bare arrow after words, an expression or an element, in a link, an a or a span', () => {
    expect(
      faults(`
        export const A = () => <Link href="/a" className="inline-flex items-center gap-1">See all <ArrowRightIcon className="h-4 w-4" /></Link>
        export const B = ({ label }: { label: string }) => <a href="/b">{label}<ArrowRightIcon aria-hidden="true" /></a>
        export const C = () => (
          <Link href="/c">
            <span className="flex items-center gap-1">
              <span>Open</span>
              <ArrowRightIcon />
            </span>
          </Link>
        )
      `),
    ).toEqual(['Link', 'a', 'span'])
  })

  it('lets a button bind its arrow: buttonVariants() alone or joined, a Button and a MarketingCta', () => {
    const sites = planted(`
      export const A = () => <Link href="/a" className={buttonVariants({ variant: 'primary' })}>Start <ArrowRightIcon /></Link>
      export const B = () => <Link href="/b" className={cx(buttonVariants({ variant: 'primary', size: 'md' }), 'mt-4')}>Start <ArrowRightIcon /></Link>
      export const C = () => <Button>Continue <ArrowRightIcon /></Button>
      export const D = () => <MarketingCta href="/d">See a live example <ArrowRightIcon /></MarketingCta>
    `)
    expect(sites.map((site) => site.binds)).toEqual(['button', 'button', 'button', 'button'])
  })

  it('passes the remedy, an arrow alone, an arrow before the words and a comment in place of words', () => {
    expect(
      planted(`
        export const A = () => <Link href="/a" className="inline-block"><TrailingArrowLabel>See all</TrailingArrowLabel></Link>
        export const B = () => <Link href="/b" aria-label="Next"><ArrowRightIcon /></Link>
        export const C = () => <Link href="/c" className="inline-flex gap-1"><ArrowRightIcon /> Next filing</Link>
        export const D = () => <Link href="/d">{/* See all */}<ArrowRightIcon /></Link>
      `),
    ).toEqual([])
  })

  it('reads the arrow after the words when the arrow carries children of its own', () => {
    expect(faults(`export const A = () => <Link href="/a">Open <ArrowRightIcon><title>next</title></ArrowRightIcon></Link>`)).toEqual(['Link'])
  })

  it('finds a bare arrow inside a fragment, behind && or ??, and in a ternary arm, named by the element that lays it out', () => {
    expect(
      faults(`
        export const A = ({ x }: { x: boolean }) => <Link href="/a" className="inline-flex gap-1">{x ? <>See all <ArrowRightIcon /></> : null}</Link>
        export const B = ({ open }: { open: boolean }) => <Link href="/b" className="inline-flex gap-1">See all {open && <ArrowRightIcon />}</Link>
        export const C = ({ open }: { open: boolean }) => <a href="/c">Open {open ? <ArrowRightIcon /> : null}</a>
        export const D = ({ icon }: { icon?: JSX.Element }) => <span>Next {icon ?? <ArrowRightIcon />}</span>
        export const E = () => <>See all <ArrowRightIcon /></>
      `),
    ).toEqual(['Link', 'Link', 'a', 'span', '<>'])
  })

  it('lets a button bind an arrow it lays out through a fragment, and passes a conditional arrow alone', () => {
    const sites = planted(`
      export const A = ({ x }: { x: boolean }) => <Button>{x ? <>Next <ArrowRightIcon /></> : null}</Button>
      export const B = ({ open }: { open: boolean }) => <Link href="/b" aria-label="Next">{open && <ArrowRightIcon />}</Link>
    `)
    expect(sites.map((site) => `${site.tag} ${site.binds}`)).toEqual(['Button button'])
  })

  it('finds the square after words, with its new-tab cue after it or not, and names the glyph', () => {
    const sites = planted(`
      export const A = ({ u }: { u: string }) => <a href={u} className="inline-flex items-center gap-1">Original on SEC.gov <ArrowSquareOutIcon className="h-3.5 w-3.5" /></a>
      export const B = ({ u }: { u: string }) => (
        <a href={u} className="inline-flex gap-1">
          <span className="min-w-0 break-words">Item 7. MD&A</span>
          <ArrowSquareOutIcon aria-hidden="true" />
          <span className="sr-only"> (opens in a new tab)</span>
        </a>
      )
    `)
    expect(sites.map((site) => `${site.tag} ${site.binds} ${site.glyph}`)).toEqual(['a null ArrowSquareOutIcon', 'a null ArrowSquareOutIcon'])
  })

  it('finds the square a same-file component draws alone, the fragment that draws it with its cue, and a component that draws one', () => {
    expect(
      faults(`
        function OpensOriginal() {
          return (
            <>
              <ArrowSquareOutIcon aria-hidden="true" className="h-3 w-3 shrink-0" />
              <span className="sr-only"> (opens in a new tab)</span>
            </>
          )
        }
        const Cue = ({ arrow }: { arrow: boolean }) => (arrow ? <ArrowRightIcon /> : <OpensOriginal />)
        export const A = ({ u }: { u: string }) => <a href={u} className="inline-flex gap-1"><span>Item 7. MD&A</span><OpensOriginal /></a>
        export const B = ({ u }: { u: string }) => <a href={u}>Open <><ArrowSquareOutIcon /><span className="sr-only"> (opens in a new tab)</span></></a>
        export const C = ({ u }: { u: string }) => <a href={u}>Open <Cue arrow={false} /></a>
      `),
    ).toEqual(['a', 'a', 'a'])
  })

  it('passes a square before its words, a square alone, the remedy with its cue, and an sr-only name in place of words', () => {
    expect(
      planted(`
        export const A = ({ u }: { u: string }) => (
          <a href={u} className="mt-2 flex items-center gap-1">
            <ArrowSquareOutIcon className="h-3 w-3 shrink-0" aria-hidden="true" />
            Open the passage on SEC.gov
            <span className="sr-only"> (opens in a new tab)</span>
          </a>
        )
        export const B = ({ u }: { u: string }) => <a href={u} aria-label="SEC.gov"><ArrowSquareOutIcon /></a>
        export const C = ({ u }: { u: string }) => (
          <a href={u} className="inline-block">
            <TrailingArrowLabel glyph="external" arrowClassName="ml-1 h-3 w-3">Item 7. MD&A</TrailingArrowLabel>
            <span className="sr-only"> (opens in a new tab)</span>
          </a>
        )
        export const D = ({ u }: { u: string }) => <a href={u}><span className="sr-only">The filing on SEC.gov</span><ArrowSquareOutIcon /></a>
        function Label() { return <span>Open</span> }
        export const E = ({ u }: { u: string }) => <a href={u}><Label /></a>
      `),
    ).toEqual([])
  })

  it('reads a component that draws words beside its glyph, or its glyph inside an element, as no glyph', () => {
    expect(
      faults(`
        function Badge() { return <><ArrowSquareOutIcon /> SEC.gov</> }
        function Chip() { return <span className="inline-flex"><ArrowSquareOutIcon /></span> }
        export const A = ({ u }: { u: string }) => <a href={u}>Open <Badge /></a>
        export const B = ({ u }: { u: string }) => <a href={u}>Open <Chip /></a>
      `),
    ).toEqual([])
  })

  it('lets a button bind the square, and reads a row mark by its file and tag alone', () => {
    const button = planted(`export const A = ({ u }: { u: string }) => <a href={u} className={buttonVariants({ variant: 'primary', size: 'sm' })}>Open the original on SEC.gov <ArrowSquareOutIcon /></a>`)
    expect(button.map((site) => `${site.binds} ${site.glyph}`)).toEqual(['button ArrowSquareOutIcon'])
    const row = `export const A = ({ u }: { u: string }) => <a href={u} className="inline-flex h-11 w-11"><span className="hidden">SEC.gov</span><ArrowSquareOutIcon /></a>`
    expect(planted(row, 'features/filings/components/FilingIndex.tsx').map((site) => site.binds)).toEqual(['row'])
    expect(planted(row).map((site) => site.binds)).toEqual([null])
    expect(planted(`export const A = ({ u }: { u: string }) => <><span>Open</span><a href={u}>See all <ArrowSquareOutIcon /></a></>`, 'features/filings/components/FilingIndex.tsx').map((site) => `${site.tag} ${site.binds}`)).toEqual(['a row'])
  })

  it('finds a label set in a flex or grid row, behind a variant or in a joiner, and passes one outside it', () => {
    const parents = labelParents(
      `
        export const A = () => <Link href="/a" className="inline-flex items-center gap-1"><TrailingArrowLabel>See all</TrailingArrowLabel></Link>
        export const B = () => <Link href="/b" className={cx('inline-block', 'sm:flex')}><TrailingArrowLabel>See all</TrailingArrowLabel></Link>
        export const C = () => <div className="!grid"><TrailingArrowLabel>See all</TrailingArrowLabel></div>
        export const D = () => <Link href="/d" className="inline-block min-h-9 py-2"><TrailingArrowLabel>See all</TrailingArrowLabel></Link>
        export const E = () => <div className="flex-1 grid-cols-2"><TrailingArrowLabel>See all</TrailingArrowLabel></div>
        export const F = ({ show }: { show: boolean }) => <Link href="/f" className="inline-flex">{show && <TrailingArrowLabel>See all</TrailingArrowLabel>}</Link>
        export const G = ({ x }: { x: boolean }) => <Link href="/g" className="flex">{x ? <><TrailingArrowLabel>See all</TrailingArrowLabel></> : null}</Link>
        export const H = ({ u }: { u: string }) => <a href={u} className="inline-flex gap-1"><TrailingArrowLabel glyph="external">Original on SEC.gov</TrailingArrowLabel><span className="sr-only"> (opens in a new tab)</span></a>
      `,
      'planted.tsx',
    )
    expect(parents.map((parent) => parent.rows)).toEqual([['inline-flex'], ['sm:flex'], ['!grid'], [], [], ['inline-flex'], ['flex'], ['inline-flex']])
  })

  it("reads a row class through the file's own consts, by scope, and through a const that names another", () => {
    const parents = labelParents(
      `
        const ROWED = cx('inline-flex min-w-0 items-center gap-1', countControlClass('link'))
        const BASE = 'sm:flex'
        const JOINED = cx(BASE, 'gap-1')
        const BLOCK = cx('inline-block break-words', countControlClass('link'))
        export const A = ({ u }: { u: string }) => <a href={u} className={ROWED}><TrailingArrowLabel glyph="external">Item 7. MD&A</TrailingArrowLabel></a>
        export const B = () => <Link href="/b" className={JOINED}><TrailingArrowLabel>See all</TrailingArrowLabel></Link>
        export const C = ({ u }: { u: string }) => <a href={u} className={BLOCK}><TrailingArrowLabel glyph="external">Item 7. MD&A</TrailingArrowLabel></a>
        export const D = ({ ROWED }: { ROWED: string }) => <a href="/d" className={ROWED}><TrailingArrowLabel>See all</TrailingArrowLabel></a>
        export const E = ({ open }: { open: boolean }) => <a href="/e" className={open ? ROWED : BLOCK}><TrailingArrowLabel>See all</TrailingArrowLabel></a>
      `,
      'planted.tsx',
    )
    expect(parents.map((parent) => parent.rows)).toEqual([['inline-flex'], ['sm:flex'], [], [], ['inline-flex']])
  })
})
