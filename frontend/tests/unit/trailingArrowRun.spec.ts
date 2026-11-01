/* =============================================================================
   trailingArrowRun.spec.ts: a trailing arrow keeps with its last word
   -----------------------------------------------------------------------------
   A label with a trailing arrow is TrailingArrowLabel: its last word and its
   arrow in one no-wrap run, so a label that wraps under 200% text carries the
   arrow onto its last line (DESIGN_SYSTEM.md §4, Trailing arrow; E272, E274,
   E275, E276). An arrow drawn as the last item of a flex row after the words
   parts from them when they wrap: it sits at the row's far edge, centred on
   the box, never after the last word. Review found the fault link by link, so
   this scan fails any element whose last child is a bare ArrowRightIcon after
   its words (text, an expression or an element before it), whatever the
   element: a Link, an a, or a span inside one.

   A button's arrow stays in its flex row, since the button's box binds it: an
   element styled by buttonVariants() (its class attribute calls it), a Button
   and a MarketingCta pass, and so does the component's own run. An arrow
   alone (an icon link) and an arrow before the words are no trailing arrow.

   The remedy holds only outside a flex or grid row: in one, the label's words
   and its last word's run are two items, so the run sits beside the wrapped
   words, not after them. So an element with a TrailingArrowLabel among its
   children also fails where its class attributes make it a flex or grid row
   at any width (flex, inline-flex, grid or inline-grid, behind any variant):
   a link that stands alone and can wrap is inline-block.

   It reads each file's TypeScript AST (tests/unit/classListScan.ts's parser),
   so comments never count. Out of reach: an arrow a component renders after
   children it is passed, and other glyphs after a link's words (a caret, and
   the external link's square, which E279 brings in). Planted cases hold the
   reader.
============================================================================= */

import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { CLASS_ATTRIBUTE, literalTexts, parse, sourceFiles, tokensOf } from './classListScan'

const ROOT = path.join(__dirname, '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']
const COMPONENT = 'components/ui/TrailingArrowLabel.tsx'
const LABEL = 'TrailingArrowLabel'
const ARROW = 'ArrowRightIcon'
// A class that makes its element a flex or grid row, behind any variant prefix and with `!` either side.
const ROW = /(?:^|:)!?(?:inline-)?(?:flex|grid)!?$/
// The button components whose box binds the arrow (DESIGN_SYSTEM.md §4, Trailing arrow).
const BUTTONS = new Set(['Button', 'MarketingCta'])

interface Site {
  file: string
  line: number
  tag: string
  // Why the arrow stands: a button's box binds it, or the component's own run.
  binds: 'button' | 'component' | null
}

type Element = ts.JsxElement

const tagOf = (element: Element, sourceFile: ts.SourceFile) => element.openingElement.tagName.getText(sourceFile)

/** The children that render: no whitespace-only text, no empty expression (a JSX comment is one). */
const rendered = (children: ts.NodeArray<ts.JsxChild>) =>
  children.filter((child) => !(ts.isJsxText(child) && child.text.trim() === '') && !(ts.isJsxExpression(child) && !child.expression))

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

/** Every element in `source` whose last rendered child is a bare ArrowRightIcon after its words. */
function trailingArrowSites(source: string, file: string): Site[] {
  const sourceFile = parse(source, file)
  const sites: Site[] = []
  const visit = (node: ts.Node): void => {
    if (ts.isJsxElement(node)) {
      const children = rendered(node.children)
      const last = children[children.length - 1]
      const arrow = last && (ts.isJsxSelfClosingElement(last) ? last.tagName : ts.isJsxElement(last) ? last.openingElement.tagName : null)
      if (arrow && arrow.getText(sourceFile) === ARROW && children.length > 1) {
        const tag = tagOf(node, sourceFile)
        const binds = file === COMPONENT ? 'component' : BUTTONS.has(tag) || styledAsButton(node) ? 'button' : null
        sites.push({ file, line: sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1, tag, binds })
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(sourceFile)
  return sites
}

interface Parent {
  file: string
  line: number
  tag: string
  // The classes that make the parent a flex or grid row.
  rows: string[]
}

/** Every element in `source` with a TrailingArrowLabel among its children, and the row classes it carries. */
function labelParents(source: string, file: string): Parent[] {
  const sourceFile = parse(source, file)
  const parents: Parent[] = []
  const isLabel = (child: ts.JsxChild) =>
    (ts.isJsxElement(child) ? child.openingElement.tagName : ts.isJsxSelfClosingElement(child) ? child.tagName : null)?.getText(sourceFile) === LABEL
  const visit = (node: ts.Node): void => {
    if (ts.isJsxElement(node) && node.children.some(isLabel)) {
      const tokens = node.openingElement.attributes.properties.flatMap((attribute) =>
        ts.isJsxAttribute(attribute) && CLASS_ATTRIBUTE.test(attribute.name.getText(sourceFile)) && attribute.initializer
          ? literalTexts(attribute.initializer).flatMap(tokensOf)
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

const where = (site: Site) => `${site.file}:${site.line} <${site.tag}>`

describe('a trailing arrow keeps with its last word (DESIGN_SYSTEM.md §4, Trailing arrow)', () => {
  const sources = sourceFiles(ROOT, SCAN_DIRS).map((file) => ({ file, source: fs.readFileSync(path.join(ROOT, file), 'utf8') }))
  const sites = sources.flatMap(({ file, source }) => trailingArrowSites(source, file))
  const parents = sources.flatMap(({ file, source }) => labelParents(source, file))

  it('reads the arrows that stand: the buttons that bind theirs, and the component run', () => {
    const standing = sites.filter((site) => site.binds !== null).map((site) => `${site.file} ${site.binds}`)
    // One of each kind the scan lets stand, so a reader that finds no trailing arrow at all fails here.
    expect(standing).toEqual(
      expect.arrayContaining([
        `${COMPONENT} component`,
        'features/marketing/components/LandingHero.tsx button',
        'app/company/[ticker]/page-client.tsx button',
      ]),
    )
  })

  it('finds no label that ends in a bare arrow after its words: it takes TrailingArrowLabel', () => {
    expect(sites.filter((site) => site.binds === null).map(where)).toEqual([])
  })

  it('reads every TrailingArrowLabel caller, and sets none in a flex or grid row', () => {
    // The eight callers (E272, E274, E275, E276), so a reader that finds no label fails here.
    expect([...new Set(parents.map((parent) => parent.file))].sort()).toEqual([
      'app/waitlist/page.tsx',
      'features/calendar/components/ReportingThisWeek.tsx',
      'features/dashboard/components/FilingFeed.tsx',
      'features/dashboard/components/WhatChangedCard.tsx',
      'features/dashboard/components/YourCompanies.tsx',
      'features/filings/components/ComparePeriodsCard.tsx',
      'features/filings/components/copilot/CopilotMessage.tsx',
      'features/marketing/components/HeroExample.tsx',
    ])
    expect(parents.filter((parent) => parent.rows.length > 0).map((parent) => `${parent.file}:${parent.line} <${parent.tag}> ${parent.rows.join(' ')}`)).toEqual([])
  })
})

describe('the trailing-arrow reader, on planted sources', () => {
  const planted = (source: string) => trailingArrowSites(source, 'planted.tsx')
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

  it('finds a label set in a flex or grid row, behind a variant or in a joiner, and passes one outside it', () => {
    const parents = labelParents(
      `
        export const A = () => <Link href="/a" className="inline-flex items-center gap-1"><TrailingArrowLabel>See all</TrailingArrowLabel></Link>
        export const B = () => <Link href="/b" className={cx('inline-block', 'sm:flex')}><TrailingArrowLabel>See all</TrailingArrowLabel></Link>
        export const C = () => <div className="!grid"><TrailingArrowLabel>See all</TrailingArrowLabel></div>
        export const D = () => <Link href="/d" className="inline-block min-h-9 py-2"><TrailingArrowLabel>See all</TrailingArrowLabel></Link>
        export const E = () => <div className="flex-1 grid-cols-2"><TrailingArrowLabel>See all</TrailingArrowLabel></div>
      `,
      'planted.tsx',
    )
    expect(parents.map((parent) => parent.rows)).toEqual([['inline-flex'], ['sm:flex'], ['!grid'], [], []])
  })
})
