import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { HEADLINES } from '@/features/marketing/lib/headline'

/**
 * Three brand rules as gates (CLAUDE.md rule 12; docs/brand/06-system.md §6; docs/voice-and-style.md
 * › Claims), read from the source the way landing-sections-mounted.spec.ts reads app/page.tsx:
 *
 * 1. Scope stays on matching claims. The server checks only some figures (a mapped concept of at
 *    least $1M: backend/app/services/provenance_service.py, build_metric_source), so shipped copy
 *    never says "each figure" or "every figure" without the scope beside it ("checkable", "where
 *    they can be", "the server can check"). The 2026-10-11 review caught a voice pass that had
 *    deleted that scope in nine places.
 * 2. Sage never colours a number on the public surfaces (the brand brief's reading of DESIGN.md ›
 *    the Separate Signals Rule; PUBLIC_SURFACES below). Text inside an element whose own text
 *    colour is a sage token may not contain a digit, whether written inline or mapped in from a
 *    literal array. Activity variants (hover:, focus:, group-hover:) are sage's other job and are
 *    not read; the device's citation brackets ("[1]", "[F1]") are not numbers. A value computed at
 *    runtime is out of a source scan's reach; the waitlist counter's own spec covers the one on
 *    the public pages. Inside the product DESIGN.md's wording lets sage mark activity, and three
 *    calendar sites use it that way (tasks/todo.md holds the decision on them).
 * 3. The Marked Copy Rule (DESIGN.md › Graphic device): the highlight (`en-mark`) never sits on a
 *    figure or a price, the hero's accent phrases included; the margin (`en-margin`) exists only
 *    inside MarkedCopy, and every MarkedCopy carries at least one marker (`EnRef`).
 */
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'lib']

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(entry.name) && !/\.(spec|test)\.tsx?$|\.d\.ts$/.test(entry.name)) out.push(p)
  }
  return out
}

const FILES = SCAN_DIRS.flatMap((dir) => walk(path.join(ROOT, dir)))
/** The surfaces a stranger meets before signing in, where the brand brief's strict reading holds. */
const PUBLIC_SURFACES = [
  'app/page.tsx', 'app/not-found.tsx', 'app/waitlist/', 'app/pricing/', 'app/login/', 'app/register/', 'app/forgot-password/',
  'features/marketing/', 'features/waitlist/', 'features/auth/components/',
  'components/Header.tsx', 'components/Footer.tsx', 'components/CookieConsent.tsx',
]
const isPublic = (rel: string) => PUBLIC_SURFACES.some((prefix) => (prefix.endsWith('/') ? rel.startsWith(prefix) : rel === prefix))
const SOURCES = FILES.map((file) => ({
  rel: path.relative(ROOT, file).split(path.sep).join('/'),
  sf: ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS),
}))

const where = (rel: string, sf: ts.SourceFile, node: ts.Node, text: string) =>
  `${rel}:${sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1} ${JSON.stringify(text.trim().slice(0, 80))}`

function visit(node: ts.Node, fn: (n: ts.Node) => void) {
  fn(node)
  ts.forEachChild(node, (child) => visit(child, fn))
}

/** The literal text a node carries, or null. */
function literalText(node: ts.Node): string | null {
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isJsxText(node)) return node.text
  if (ts.isTemplateExpression(node)) return [node.head.text, ...node.templateSpans.map((span) => span.literal.text)].join(' ')
  if (ts.isNumericLiteral(node)) return node.text
  return null
}

const unwrap = (e: ts.Expression): ts.Expression =>
  ts.isAsExpression(e) || ts.isSatisfiesExpression(e) || ts.isParenthesizedExpression(e) ? unwrap(e.expression) : e

/** `item.step` inside `ARRAY.map((item) => …)` over a literal array: the literal values of `step`. */
function mappedValues(access: ts.PropertyAccessExpression, sf: ts.SourceFile): string[] {
  if (!ts.isIdentifier(access.expression)) return []
  const param = access.expression.text
  const prop = access.name.text
  let fn: ts.Node | undefined = access.parent
  while (fn && !((ts.isArrowFunction(fn) || ts.isFunctionExpression(fn)) && fn.parameters.some((p) => ts.isIdentifier(p.name) && p.name.text === param))) fn = fn.parent
  const call = fn?.parent
  if (!call || !ts.isCallExpression(call) || !ts.isPropertyAccessExpression(call.expression) || call.expression.name.text !== 'map') return []
  let array = unwrap(call.expression.expression)
  if (ts.isIdentifier(array)) {
    const name = array.text
    let init: ts.Expression | undefined
    visit(sf, (n) => {
      if (!init && ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.name.text === name && n.initializer) init = n.initializer
    })
    if (!init) return []
    array = unwrap(init)
  }
  if (!ts.isArrayLiteralExpression(array)) return []
  const values: string[] = []
  for (const element of array.elements) {
    if (!ts.isObjectLiteralExpression(element)) continue
    for (const property of element.properties) {
      if (ts.isPropertyAssignment(property) && (ts.isIdentifier(property.name) || ts.isStringLiteral(property.name)) && property.name.text === prop) {
        const text = literalText(unwrap(property.initializer))
        if (text !== null) values.push(text)
      }
    }
  }
  return values
}

/** Every string a className attribute can produce, split into tokens. */
function classTokens(opening: ts.JsxOpeningLikeElement): string[] {
  const attr = opening.attributes.properties.find((p): p is ts.JsxAttribute => ts.isJsxAttribute(p) && p.name.getText() === 'className')
  if (!attr?.initializer) return []
  const parts: string[] = []
  visit(attr.initializer, (n) => {
    const text = ts.isJsxText(n) ? null : literalText(n)
    if (text !== null) parts.push(text)
  })
  return parts.join(' ').split(/\s+/).filter(Boolean)
}

const SAGE = /^text-(?:brand(?:-strong|-emphasis|-dark|-strong-dark|-fill-dark)?|accent-strong)$/
const NOT_COLOUR = /^text-(?:xs|sm|base|lg|xl|[2-9]xl|data-[a-z]+|left|center|right|justify|start|end|ellipsis|clip|wrap|nowrap|balance|pretty)$/
const PASSIVE_VARIANTS = new Set(['dark', 'sm', 'md', 'lg', 'xl', '2xl'])
const CITATION = /^\[F?\d+\]$/

/** 'sage' when the element's own resting text colour is a sage token, 'other' for any other colour. */
function textColour(opening: ts.JsxOpeningLikeElement): 'sage' | 'other' | null {
  let colour: 'sage' | 'other' | null = null
  for (const token of classTokens(opening)) {
    const parts = token.split(':')
    const utility = parts.pop()!.replace(/^!/, '')
    if (!utility.startsWith('text-') || NOT_COLOUR.test(utility)) continue
    if (parts.some((variant) => !PASSIVE_VARIANTS.has(variant))) continue
    if (SAGE.test(utility)) return 'sage'
    colour = 'other'
  }
  return colour
}

/** The literal texts an element renders in its own ink (stops at a child that sets its own colour). */
function inkTexts(children: ts.NodeArray<ts.JsxChild>, sf: ts.SourceFile, out: { node: ts.Node; text: string }[] = []) {
  const expr = (e: ts.Expression) => {
    const x = unwrap(e)
    const text = literalText(x)
    if (text !== null) out.push({ node: x, text })
    else if (ts.isConditionalExpression(x)) [x.whenTrue, x.whenFalse].forEach(expr)
    else if (ts.isBinaryExpression(x)) [x.left, x.right].forEach(expr)
    else if (ts.isPropertyAccessExpression(x)) mappedValues(x, sf).forEach((value) => out.push({ node: x, text: value }))
    else if (ts.isJsxElement(x) || ts.isJsxFragment(x)) inkTexts(x.children, sf, out)
  }
  for (const child of children) {
    if (ts.isJsxText(child)) out.push({ node: child, text: child.text })
    else if (ts.isJsxExpression(child) && child.expression) expr(child.expression)
    else if (ts.isJsxFragment(child)) inkTexts(child.children, sf, out)
    else if (ts.isJsxElement(child) && textColour(child.openingElement) === null) inkTexts(child.children, sf, out)
  }
  return out
}

/** All literal text under an element, whatever its colour (for the highlight rule). */
function allTexts(node: ts.Node, sf: ts.SourceFile): { node: ts.Node; text: string }[] {
  const out: { node: ts.Node; text: string }[] = []
  visit(node, (n) => {
    if (ts.isJsxAttribute(n.parent ?? n) && n !== node) return
    const text = ts.isJsxText(n) || ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n) || ts.isTemplateExpression(n) || ts.isNumericLiteral(n) ? literalText(n) : null
    if (text !== null && !(n.parent && ts.isJsxAttribute(n.parent))) out.push({ node: n, text })
    if (ts.isPropertyAccessExpression(n)) mappedValues(n, sf).forEach((value) => out.push({ node: n, text: value }))
  })
  return out
}

describe('brand rule 1: matching claims keep their scope', () => {
  const UNSCOPED = /\b(?:each|every|all)\s+(?:figure|number)s?\b/i
  const SCOPE = /checkable|can be checked|can check|where (?:they|it) can be/i

  it('no shipped string or JSX text says "each figure" or "every figure" without the scope beside it', () => {
    const offenders: string[] = []
    for (const { rel, sf } of SOURCES) {
      visit(sf, (n) => {
        if (ts.isImportDeclaration(n.parent ?? n) || ts.isExportDeclaration(n.parent ?? n)) return
        const text = literalText(n)
        if (text !== null && !ts.isNumericLiteral(n) && UNSCOPED.test(text) && !SCOPE.test(text)) offenders.push(where(rel, sf, n, text))
      })
    }
    expect(offenders, 'say what the server checks: "where they can be checked", "checkable figures"').toEqual([])
  })
})

describe('brand rule 2: sage never colours a number', () => {
  it('no element on a public surface whose own text colour is a sage token renders a digit', () => {
    const offenders: string[] = []
    for (const { rel, sf } of SOURCES.filter((s) => isPublic(s.rel))) {
      visit(sf, (n) => {
        if (!ts.isJsxElement(n) || textColour(n.openingElement) !== 'sage') return
        for (const { node, text } of inkTexts(n.children, sf)) {
          const trimmed = text.trim()
          if (/\d/.test(trimmed) && !CITATION.test(trimmed)) offenders.push(where(rel, sf, node, trimmed))
        }
      })
    }
    expect(offenders, 'set the number in the ink (text-text-primary / secondary); sage signals brand and activity').toEqual([])
  })
})

describe('brand rule 3: the Marked Copy Rule', () => {
  it('the highlight (en-mark) never sits on a figure or a price', () => {
    const offenders: string[] = []
    for (const { rel, sf } of SOURCES) {
      visit(sf, (n) => {
        if (!ts.isJsxElement(n) || !classTokens(n.openingElement).includes('en-mark')) return
        for (const { node, text } of allTexts(n, sf)) if (/[\d$%]/.test(text)) offenders.push(where(rel, sf, node, text))
      })
    }
    expect(offenders).toEqual([])
  })

  it("the hero's accent phrases (rendered inside the highlight) carry no figure or price", () => {
    for (const [variant, headline] of Object.entries(HEADLINES)) expect(headline.accent, variant).not.toMatch(/[\d$%]/)
  })

  it('the margin exists only inside MarkedCopy, and every MarkedCopy carries a marker', () => {
    const marginOutside: string[] = []
    const withoutMarker: string[] = []
    for (const { rel, sf } of SOURCES) {
      visit(sf, (n) => {
        if ((ts.isJsxElement(n) || ts.isJsxSelfClosingElement(n)) && rel !== 'features/marketing/components/MarkedCopy.tsx') {
          const opening = ts.isJsxElement(n) ? n.openingElement : n
          if (classTokens(opening).includes('en-margin')) marginOutside.push(where(rel, sf, n, 'en-margin'))
        }
        if (ts.isJsxElement(n) && n.openingElement.tagName.getText() === 'MarkedCopy') {
          let marker = false
          visit(n, (m) => {
            if ((ts.isJsxElement(m) && m.openingElement.tagName.getText() === 'EnRef') || (ts.isJsxSelfClosingElement(m) && m.tagName.getText() === 'EnRef')) marker = true
          })
          if (!marker) withoutMarker.push(where(rel, sf, n, '<MarkedCopy> without <EnRef>'))
        }
      })
    }
    expect(marginOutside, 'render <MarkedCopy> instead of a bare gutter').toEqual([])
    expect(withoutMarker, 'a margin appears only beside text that carries a marker').toEqual([])
  })

  it('the scan sees the surfaces it guards (the rules above stay meaningful)', () => {
    expect(PUBLIC_SURFACES.every((prefix) => SOURCES.some((s) => (prefix.endsWith('/') ? s.rel.startsWith(prefix) : s.rel === prefix))), 'every public surface prefix matches a file').toBe(true)
    const rels = new Set(SOURCES.map((s) => s.rel))
    for (const rel of ['features/marketing/components/HeroHeadline.tsx', 'features/marketing/components/HeroExample.tsx', 'app/waitlist/page.tsx', 'app/pricing/page.tsx', 'features/auth/components/AuthShell.tsx']) {
      expect(rels.has(rel), rel).toBe(true)
    }
    const marked = SOURCES.filter(({ sf }) => {
      let found = false
      visit(sf, (n) => {
        if (ts.isJsxElement(n) && classTokens(n.openingElement).includes('en-mark')) found = true
      })
      return found
    }).map((s) => s.rel)
    expect(marked).toEqual(expect.arrayContaining(['features/marketing/components/HeroHeadline.tsx', 'app/waitlist/page.tsx', 'features/auth/components/AuthShell.tsx']))
  })
})
