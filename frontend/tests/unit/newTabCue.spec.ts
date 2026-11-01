/* =============================================================================
   newTabCue.spec.ts: a link that opens a new tab says so
   -----------------------------------------------------------------------------
   Every element the app writes with target="_blank" says, in its accessible
   name, that it opens a new tab (E281; chief design on #1918, 5729280088). A
   sighted reader has the square, or nothing; a screen reader hears only the
   name. It says so in one of two forms:
   - after its label, a hidden tail that brings its own space, as
     lessons/frontend-hidden-name-tails-bring-their-own-space.md has it:
     {' '}<span className="sr-only">(opens in a new tab)</span>. A space written
     inside an sr-only span is lost in an engine that adds no separator for the
     span's blockified box (jsdom drops it), so the space stands before it;
   - or at the end of its aria-label, "… (opens in a new tab)": where the label
     names the link already, and where the link's own text must stay as it is
     written (the Footer's attribution, a feedback message read literally).

   It reads each file's TypeScript AST (tests/unit/classListScan.ts's parser),
   so comments never count. An element is a new-tab link where its target
   attribute holds the string '_blank' anywhere (a literal, or behind a
   condition). Any other '_blank' in the app (a window.open call) fails as
   unread. An own aria-label is read to its words: a string, or a template's
   last chunk; one built otherwise, or an aria-label a spread may set after it
   (a spread with no own label after it), fails as unread. The tail is read in
   the element's children at any depth. The residue, held by name: the terms
   page's link, on a legal page whose text waits on the founder's go-ahead.
   A glyph that marks the new tab says nothing itself: inside a new-tab link,
   an ArrowSquareOutIcon takes aria-hidden, and so does an element around a
   text arrow (↗). Planted cases hold the reader.
============================================================================= */

import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { CLASS_ATTRIBUTE, literalTexts, parse, sourceFiles, tokensOf } from './classListScan'

const ROOT = path.join(__dirname, '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']
const CUE = '(opens in a new tab)'
// The links that may stay silent, each until its own decision: the terms page's, whose text waits on the founder.
const RESIDUE = ['app/terms/page.tsx <a>']

type Verdict = 'tail' | 'label' | 'silent' | 'unread'

interface Site {
  file: string
  line: number
  tag: string
  verdict: Verdict
  // The glyphs inside it a screen reader would read: a square without aria-hidden, a text arrow no hidden element holds.
  spoken: string[]
}

const place = (site: Site) => `${site.file} <${site.tag}>`
const where = (site: Site) => `${site.file}:${site.line} <${site.tag}> ${site.verdict}`

function attributeName(attribute: ts.JsxAttributeLike, sourceFile: ts.SourceFile): string | null {
  return ts.isJsxAttribute(attribute) ? attribute.name.getText(sourceFile) : null
}

/** The words an aria-label's value ends with, or null where the scan cannot read them: a string, or a template's last
    chunk. */
function labelEnd(initializer: ts.JsxAttributeValue | undefined): string | null {
  if (!initializer) return null
  if (ts.isStringLiteral(initializer)) return initializer.text
  if (!ts.isJsxExpression(initializer) || !initializer.expression) return null
  const value = initializer.expression
  if (ts.isStringLiteralLike(value)) return value.text
  if (ts.isTemplateExpression(value)) return value.templateSpans[value.templateSpans.length - 1].literal.text
  return null
}

/** True where the element's class attributes carry sr-only. */
function srOnly(element: ts.JsxElement, sourceFile: ts.SourceFile): boolean {
  return element.openingElement.attributes.properties.some(
    (attribute) =>
      ts.isJsxAttribute(attribute) &&
      CLASS_ATTRIBUTE.test(attribute.name.getText(sourceFile)) &&
      !!attribute.initializer &&
      literalTexts(attribute.initializer).flatMap(tokensOf).includes('sr-only'),
  )
}

/** The text an element's children write, where they write only text: JSX text and strings in braces. */
function textOf(element: ts.JsxElement): string | null {
  let text = ''
  for (const child of element.children) {
    if (ts.isJsxText(child)) text += child.text
    else if (ts.isJsxExpression(child) && child.expression && ts.isStringLiteralLike(child.expression)) text += child.expression.text
    else if (ts.isJsxExpression(child) && !child.expression) continue
    else return null
  }
  return text
}

/** True where `children` hold the tail at any depth: an sr-only element whose text is the cue, right after a `{' '}`. */
function holdsTail(children: ts.NodeArray<ts.JsxChild>, sourceFile: ts.SourceFile): boolean {
  return children.some((child, index) => {
    if (ts.isJsxElement(child) && srOnly(child, sourceFile) && textOf(child) === CUE) {
      const before = children[index - 1]
      return !!before && ts.isJsxExpression(before) && !!before.expression && ts.isStringLiteralLike(before.expression) && before.expression.text === ' '
    }
    return ts.isJsxElement(child) && holdsTail(child.children, sourceFile)
  })
}

/** What a new-tab element's name says: its aria-label's end where it has one the scan reads (the last that sets it
    wins, as React applies props in order), else its children's tail. */
function verdictOf(opening: ts.JsxOpeningElement | ts.JsxSelfClosingElement, sourceFile: ts.SourceFile): Verdict {
  const attributes = opening.attributes.properties
  const lastLabel = [...attributes].reverse().find((attribute) => ts.isJsxSpreadAttribute(attribute) || attributeName(attribute, sourceFile) === 'aria-label')
  if (lastLabel && ts.isJsxSpreadAttribute(lastLabel)) return 'unread'
  if (lastLabel && ts.isJsxAttribute(lastLabel)) {
    const end = labelEnd(lastLabel.initializer)
    if (end === null) return 'unread'
    return end.endsWith(` ${CUE}`) ? 'label' : 'silent'
  }
  const element = ts.isJsxOpeningElement(opening) ? opening.parent : null
  return element && holdsTail(element.children, sourceFile) ? 'tail' : 'silent'
}

/** True where the element carries aria-hidden set to true. */
function hidden(opening: ts.JsxOpeningElement | ts.JsxSelfClosingElement, sourceFile: ts.SourceFile): boolean {
  return opening.attributes.properties.some((attribute) => {
    if (!ts.isJsxAttribute(attribute) || attribute.name.getText(sourceFile) !== 'aria-hidden') return false
    const value = attribute.initializer
    if (!value) return true
    if (ts.isStringLiteral(value)) return value.text === 'true'
    return !!value.expression && (value.expression.kind === ts.SyntaxKind.TrueKeyword || (ts.isStringLiteralLike(value.expression) && value.expression.text === 'true'))
  })
}

/** The glyphs in `children` a screen reader would read, at any depth: a square without aria-hidden, and a text arrow
    (↗) that no aria-hidden element holds. A hidden element hides all it holds. */
function spokenGlyphs(children: ts.NodeArray<ts.JsxChild>, sourceFile: ts.SourceFile): string[] {
  return children.flatMap((child): string[] => {
    if (ts.isJsxText(child)) return child.text.includes('↗') ? ['↗'] : []
    if (ts.isJsxExpression(child)) return child.expression && ts.isStringLiteralLike(child.expression) && child.expression.text.includes('↗') ? ['↗'] : []
    if (ts.isJsxSelfClosingElement(child)) return child.tagName.getText(sourceFile) === 'ArrowSquareOutIcon' && !hidden(child, sourceFile) ? ['ArrowSquareOutIcon'] : []
    if (ts.isJsxElement(child)) {
      if (hidden(child.openingElement, sourceFile)) return []
      const own = child.openingElement.tagName.getText(sourceFile) === 'ArrowSquareOutIcon' ? ['ArrowSquareOutIcon'] : []
      return [...own, ...spokenGlyphs(child.children, sourceFile)]
    }
    return []
  })
}

/** True where `node` sits in a JSX target attribute's value. */
function inTarget(node: ts.Node, sourceFile: ts.SourceFile): boolean {
  for (let up = node.parent; up; up = up.parent) {
    if (ts.isJsxAttribute(up)) return up.name.getText(sourceFile) === 'target'
    if (ts.isJsxElement(up) || ts.isJsxSelfClosingElement(up) || ts.isSourceFile(up)) return false
  }
  return false
}

/** Every new-tab element in `source` with what its name says, and each '_blank' elsewhere as unread. */
function newTabSites(source: string, file: string): Site[] {
  const sourceFile = parse(source, file)
  const sites: Site[] = []
  const at = (node: ts.Node) => sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1
  const visit = (node: ts.Node): void => {
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
      const target = node.attributes.properties.find((attribute) => attributeName(attribute, sourceFile) === 'target')
      if (target && ts.isJsxAttribute(target) && target.initializer && literalTexts(target.initializer).includes('_blank')) {
        const spoken = ts.isJsxOpeningElement(node) ? spokenGlyphs(node.parent.children, sourceFile) : []
        sites.push({ file, line: at(node), tag: node.tagName.getText(sourceFile), verdict: verdictOf(node, sourceFile), spoken })
      }
    } else if (ts.isStringLiteralLike(node) && node.text === '_blank' && !inTarget(node, sourceFile)) {
      sites.push({ file, line: at(node), tag: '_blank', verdict: 'unread', spoken: [] })
    }
    ts.forEachChild(node, visit)
  }
  visit(sourceFile)
  return sites
}

describe('a link that opens a new tab says so (DESIGN_SYSTEM.md §4, Links in both surfaces)', () => {
  const sites = sourceFiles(ROOT, SCAN_DIRS).flatMap((file) => newTabSites(fs.readFileSync(path.join(ROOT, file), 'utf8'), file))

  it('reads the new-tab links of both forms', () => {
    // One of each form, so a reader that finds no new-tab link, or reads neither form, fails here.
    expect(sites.map((site) => `${site.file} ${site.verdict}`)).toEqual(
      expect.arrayContaining([
        'features/filings/components/FilingIdentity.tsx tail',
        'features/filings/components/SourceTrace.tsx tail',
        'features/filings/components/SourceTrace.tsx label',
        'features/filings/components/copilot/CitationChip.tsx label',
        'components/Footer.tsx label',
      ]),
    )
  })

  it('finds no new-tab link whose name does not say so, the residue aside, and none the scan cannot read', () => {
    expect(sites.filter((site) => site.verdict === 'unread').map(where)).toEqual([])
    expect(sites.filter((site) => site.verdict === 'silent' && !RESIDUE.includes(place(site))).map(where)).toEqual([])
  })

  it('holds the residue exactly: each entry is a silent link the scan finds', () => {
    expect(sites.filter((site) => site.verdict === 'silent').map(place)).toEqual(RESIDUE)
  })

  it('lets no glyph inside a new-tab link speak: its square and its text arrow are aria-hidden', () => {
    expect(sites.filter((site) => site.spoken.length > 0).map((site) => `${where(site)} ${site.spoken.join(' ')}`)).toEqual([])
  })
})

describe('the new-tab reader, on planted sources', () => {
  const verdicts = (source: string) => newTabSites(source, 'planted.tsx').map((site) => `${site.tag} ${site.verdict}`)

  it('reads the tail after a label, at any depth, and the label that ends in the cue', () => {
    expect(
      verdicts(`
        export const A = ({ u }: { u: string }) => <a href={u} target="_blank">Original on SEC.gov{' '}<span className="sr-only">(opens in a new tab)</span></a>
        export const B = ({ u }: { u: string }) => <a href={u} target="_blank"><span>Open <span>original</span>{' '}<span className="sr-only">(opens in a new tab)</span></span></a>
        export const C = ({ u, n }: { u: string; n: number }) => <a href={u} target="_blank" aria-label={\`Source \${n} (opens in a new tab)\`}>Source</a>
        export const D = ({ u }: { u: string }) => <Link href={u} target="_blank" aria-label="Logos provided by Logo.dev (opens in a new tab)">Logos provided by Logo.dev</Link>
      `),
    ).toEqual(['a tail', 'a tail', 'a label', 'Link label'])
  })

  it('finds a silent link: no cue, the cue with its space inside or with none, a cue not hidden, and a label that does not say so', () => {
    expect(
      verdicts(`
        export const A = ({ u }: { u: string }) => <a href={u} target="_blank">Original on SEC.gov</a>
        export const B = ({ u }: { u: string }) => <a href={u} target="_blank">Open<span className="sr-only"> (opens in a new tab)</span></a>
        export const C = ({ u }: { u: string }) => <a href={u} target="_blank">Open<span className="sr-only">(opens in a new tab)</span></a>
        export const D = ({ u }: { u: string }) => <a href={u} target="_blank" aria-label="Open the filing">Open{' '}<span className="sr-only">(opens in a new tab)</span></a>
        export const E = ({ u }: { u: string }) => <a href={u} target="_blank">Open{' '}<span>(opens in a new tab)</span></a>
        export const F = ({ u }: { u: string }) => <a href={u} target="_blank">Open{' '}<span className="sr-only"> (opens in a new tab)</span></a>
      `),
    ).toEqual(['a silent', 'a silent', 'a silent', 'a silent', 'a silent', 'a silent'])
  })

  it('reads a target behind a condition, and lets an own label after a spread win', () => {
    expect(
      verdicts(`
        export const A = ({ u, x }: { u: string; x: boolean }) => <a href={u} target={x ? '_blank' : undefined}>Open</a>
        export const B = ({ u, p }: { u: string; p: object }) => <a {...p} aria-label="Source 1 (opens in a new tab)" href={u} target="_blank">1</a>
        export const C = ({ u }: { u: string }) => <a href={u} target="_self">Open</a>
      `),
    ).toEqual(['a silent', 'a label'])
  })

  it('reads a spoken glyph inside a new-tab link, at any depth: a square without aria-hidden, a text arrow outside a hidden element', () => {
    const spoken = (source: string) => newTabSites(source, 'planted.tsx').map((site) => site.spoken.join(' '))
    expect(
      spoken(`
        export const A = ({ u }: { u: string }) => <a href={u} target="_blank"><ArrowSquareOutIcon />Open{' '}<span className="sr-only">(opens in a new tab)</span></a>
        export const B = ({ u }: { u: string }) => <a href={u} target="_blank">Open original ↗{' '}<span className="sr-only">(opens in a new tab)</span></a>
        export const C = ({ u }: { u: string }) => <a href={u} target="_blank"><ArrowSquareOutIcon aria-hidden="true" />Open <span aria-hidden="true">↗</span>{' '}<span className="sr-only">(opens in a new tab)</span></a>
        export const D = ({ u }: { u: string }) => <a href={u} target="_blank"><span><ArrowSquareOutIcon aria-hidden /></span>Open{' '}<span className="sr-only">(opens in a new tab)</span></a>
        export const E = ({ u }: { u: string }) => <a href={u}><ArrowSquareOutIcon />Open</a>
        export const F = ({ u }: { u: string }) => <a href={u} target="_blank"><span><ArrowSquareOutIcon /> Open ↗</span>{' '}<span className="sr-only">(opens in a new tab)</span></a>
      `),
    ).toEqual(['ArrowSquareOutIcon', '↗', '', '', 'ArrowSquareOutIcon ↗'])
  })

  it('fails as unread a label it cannot read, a spread after the label, and a _blank outside a target, in a handler or a call', () => {
    expect(
      verdicts(`
        export const A = ({ u, name }: { u: string; name: string }) => <a href={u} target="_blank" aria-label={name}>Open</a>
        export const B = ({ u, p }: { u: string; p: object }) => <a aria-label="Open (opens in a new tab)" {...p} href={u} target="_blank">Open</a>
        export const C = ({ u, p }: { u: string; p: object }) => <a {...p} href={u} target="_blank">Open{' '}<span className="sr-only">(opens in a new tab)</span></a>
        export const D = ({ u }: { u: string }) => <button type="button" onClick={() => window.open(u, '_blank')}>Open</button>
        export const open = (u: string) => window.open(u, '_blank')
      `),
    ).toEqual(['a unread', 'a unread', 'a unread', '_blank unread', '_blank unread'])
  })
})
