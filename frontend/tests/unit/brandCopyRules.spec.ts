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
 *    deleted that scope in nine places. Two siblings keep the other scopes: 1b, the outline is "up
 *    to nine parts"; 1c, only risk excerpts are promised as located or withheld.
 * 2. Sage never colours a number, anywhere in the app (DESIGN.md › the Separate Signals Rule;
 *    docs/brand/decisions-log.md D-030, the founder's call of 2026-10-11: the strict reading holds
 *    inside the product as on the public surfaces). Text inside an element whose own text colour
 *    is a sage token may not contain a digit, whether written inline or mapped in from a literal
 *    array. Activity variants (hover:, focus:, group-hover:) are sage's other job and are not
 *    read, so a control may turn sage under the pointer while its count rests in the ink; the
 *    device's citation brackets ("[1]", "[F1]") are not numbers. A value computed at runtime is
 *    out of a source scan's reach: the waitlist counter's own spec covers the one on the public
 *    pages, and the calendar's "+N more" controls, whose N is computed, rest in the ink by the
 *    same rule.
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
/** One program over the scanned files, so rule 2 can ask the checker what an expression renders (a
 *  number, a template with a number in it, a formatter fed a number), not only what its literals say. */
const TSCONFIG = ts.readConfigFile(path.join(ROOT, 'tsconfig.json'), ts.sys.readFile)
const PARSED = ts.parseJsonConfigFileContent(TSCONFIG.config, ts.sys, ROOT)
const PROGRAM = ts.createProgram(FILES, { ...PARSED.options, noEmit: true, skipLibCheck: true })
const CHECKER = PROGRAM.getTypeChecker()
/** The surfaces a stranger meets before signing in, where the brand brief's strict reading holds. */
const PUBLIC_SURFACES = [
  'app/page.tsx', 'app/not-found.tsx', 'app/waitlist/', 'app/pricing/', 'app/login/', 'app/register/', 'app/forgot-password/',
  'features/marketing/', 'features/waitlist/', 'features/auth/components/',
  'components/Header.tsx', 'components/Footer.tsx', 'components/CookieConsent.tsx',
]
const isPublic = (rel: string) => PUBLIC_SURFACES.some((prefix) => (prefix.endsWith('/') ? rel.startsWith(prefix) : rel === prefix))
const SOURCES = FILES.map((file) => {
  const sf = PROGRAM.getSourceFile(file)
  if (!sf) throw new Error(`${file} is not in the program`)
  return { rel: path.relative(ROOT, file).split(path.sep).join('/'), sf }
})

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

const NUMBER_LIKE = ts.TypeFlags.NumberLike
function isNumberTyped(e: ts.Expression): boolean {
  const t = CHECKER.getTypeAtLocation(e)
  if (t.flags & NUMBER_LIKE) return true
  // A union is a number when every member that is not null or undefined is one (`number | null`);
  // ReactNode and `string | number` carry other things and are not read as values.
  if (!t.isUnion()) return false
  const members = t.types.filter((u) => !(u.flags & (ts.TypeFlags.Null | ts.TypeFlags.Undefined)))
  return members.length > 0 && members.every((u) => (u.flags & NUMBER_LIKE) !== 0)
}

/** The initializer of a `const` declared in this file under that name, if any (one level, as mappedValues resolves). */
function localInitializer(id: ts.Identifier, sf: ts.SourceFile): ts.Expression | undefined {
  let init: ts.Expression | undefined
  visit(sf, (n) => {
    if (!init && ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.name.text === id.text && n.initializer) init = n.initializer
  })
  return init
}

/** Whether a JSX expression renders a value: a number-typed expression, a template or concatenation
 *  with a number in it, a string-returning call fed a number (a formatter), a conditional with such
 *  a branch, or a same-file constant built from one of those. */
function rendersValue(e: ts.Expression, sf: ts.SourceFile, depth = 0): boolean {
  const x = unwrap(e)
  if (depth > 6 || ts.isJsxSelfClosingElement(x)) return false
  if (ts.isJsxFragment(x)) return inkValues(x.children, sf).length > 0
  if (ts.isJsxElement(x)) return textColour(x.openingElement) === null && inkValues(x.children, sf).length > 0
  if (ts.isTemplateExpression(x)) return x.templateSpans.some((span) => rendersValue(span.expression, sf, depth + 1))
  if (literalText(x) !== null) return false
  if (ts.isConditionalExpression(x)) return rendersValue(x.whenTrue, sf, depth + 1) || rendersValue(x.whenFalse, sf, depth + 1)
  if (ts.isBinaryExpression(x)) return rendersValue(x.left, sf, depth + 1) || rendersValue(x.right, sf, depth + 1)
  if (ts.isCallExpression(x)) return isNumberTyped(x) || x.arguments.some((a) => isNumberTyped(a))
  if (ts.isIdentifier(x)) {
    const init = localInitializer(x, sf)
    if (init) return rendersValue(init, sf, depth + 1)
  }
  return isNumberTyped(x)
}

/** The device's citation marker: an expression set between a "[" and a "]" of its own line of text ("[{n}]"). */
function citationBracket(children: ts.NodeArray<ts.JsxChild>, i: number): boolean {
  const before = children[i - 1]
  const after = children[i + 1]
  return !!before && !!after && ts.isJsxText(before) && ts.isJsxText(after) && /\[\s*$/.test(before.text) && /^\s*\]/.test(after.text)
}

/** The expression a link renders as its own address (`<a href={url}>{url}</a>`): text, not a value. */
function ownAddress(opening: ts.JsxOpeningLikeElement | undefined, e: ts.Expression): boolean {
  const href = opening?.attributes.properties.find((p): p is ts.JsxAttribute => ts.isJsxAttribute(p) && p.name.getText() === 'href')
  return !!href?.initializer && ts.isJsxExpression(href.initializer) && !!href.initializer.expression && href.initializer.expression.getText() === e.getText()
}

/** The expressions an element renders in its own ink that carry a value (stops at a child with its own colour). */
function inkValues(children: ts.NodeArray<ts.JsxChild>, sf: ts.SourceFile, out: ts.Node[] = [], opening?: ts.JsxOpeningLikeElement) {
  children.forEach((child, i) => {
    if (ts.isJsxExpression(child) && child.expression) {
      if (citationBracket(children, i) || ownAddress(opening, child.expression)) return
      const x = unwrap(child.expression)
      if (ts.isTemplateExpression(x) && /\[\s*$/.test(x.head.text) && x.templateSpans.length === 1 && /^\s*\]/.test(x.templateSpans[0].literal.text)) return
      if (ts.isJsxElement(x) || ts.isJsxFragment(x)) { if (ts.isJsxElement(x) ? textColour(x.openingElement) === null : true) inkValues(x.children, sf, out); return }
      if (rendersValue(child.expression, sf)) out.push(child.expression)
    } else if (ts.isJsxFragment(child)) inkValues(child.children, sf, out)
    else if (ts.isJsxElement(child) && textColour(child.openingElement) === null) inkValues(child.children, sf, out)
  })
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

describe('brand rule 1b: the nine-part outline keeps its scope', () => {
  // The schema's nine sections are all optional (backend/app/services/summary_schema.py,
  // SummaryDocSections) and the render builders drop an empty one, so a filing without segment
  // disclosure has eight. Shipped copy may name the nine-part outline, never promise nine parts
  // per filing (Codex review of PR #1226).
  const PROMISE = /\bnine parts,? (?:per|for every|in every|every)\b|\bevery (?:filing|summary|10-K)\b[^.]*\bnine parts\b/i
  it('no shipped text promises nine parts for every filing unless it says "up to"', () => {
    const offenders: string[] = []
    for (const { rel, sf } of SOURCES) {
      visit(sf, (n) => {
        const text = literalText(n)
        if (text !== null && !ts.isNumericLiteral(n) && PROMISE.test(text) && !/\bup to nine parts\b/i.test(text)) offenders.push(where(rel, sf, n, text))
      })
    }
    expect(offenders, 'say "up to nine parts", or name the outline').toEqual([])
  })
})

describe('brand rule 1c: the withholding promise names risk excerpts', () => {
  // Of a summary's quotes, only risk excerpts are withheld when the filing's text does not match:
  // the server projects a risk only from a whitespace-exact span and counts the rest
  // (backend/app/services/provenance_service.py). A Forward Signals quote stays on the page,
  // labelled Cited, while AI_FORWARD_QUOTE_GATE is off (backend/app/services/ai/
  // forward_quote_gate.py). So a public surface may promise that risk excerpts are located or
  // withheld, or are the filing's own words, never that quotes in general are (the founder's
  // review of PR #1226). An object literal is read as one statement, so a claims row's subject
  // and label are judged together.
  const PROMISE = /\bwithheld\b|\bown words\b|\bpassage (?:it|they) came from\b/i
  const QUOTES = /\bquot(?:e|es|ed|ation|ations)\b|\bexcerpts?\b/i
  const SCOPE = /\brisks?\b/i

  /** The statement a literal belongs to: every literal value of its object literal, or itself. */
  function statement(n: ts.Node, text: string): string {
    const assignment = n.parent
    if (!assignment || !ts.isPropertyAssignment(assignment) || !ts.isObjectLiteralExpression(assignment.parent)) return text
    return assignment.parent.properties
      .map((p) => (ts.isPropertyAssignment(p) ? literalText(unwrap(p.initializer)) : null))
      .filter((t): t is string => t !== null)
      .join(' · ')
  }

  it('no text on a public surface promises that quotes are withheld or are the filing’s own words unless it names risk excerpts', () => {
    const offenders: string[] = []
    for (const { rel, sf } of SOURCES.filter((s) => isPublic(s.rel))) {
      visit(sf, (n) => {
        const text = literalText(n)
        if (text === null || ts.isNumericLiteral(n)) return
        const whole = statement(n, text)
        if (PROMISE.test(text) && QUOTES.test(whole) && !SCOPE.test(whole)) offenders.push(where(rel, sf, n, whole))
      })
    }
    expect(offenders, 'name what is enforced: "risk excerpts … or withheld"').toEqual([])
  })
})

describe('brand rule 2: sage never colours a number', () => {
  it('no element in the app whose own text colour is a sage token renders a digit', () => {
    const offenders: string[] = []
    for (const { rel, sf } of SOURCES) {
      visit(sf, (n) => {
        if (!ts.isJsxElement(n) || textColour(n.openingElement) !== 'sage') return
        for (const { node, text } of inkTexts(n.children, sf)) {
          const trimmed = text.trim()
          if (/\d/.test(trimmed) && !CITATION.test(trimmed)) offenders.push(where(rel, sf, node, trimmed))
        }
        for (const node of inkValues(n.children, sf, [], n.openingElement)) offenders.push(where(rel, sf, node, `{${node.getText(sf)}}`))
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
    for (const rel of ['features/marketing/components/HeroHeadline.tsx', 'features/marketing/components/HeroExample.tsx', 'app/waitlist/page.tsx', 'app/pricing/page.tsx', 'features/auth/components/AuthShell.tsx', 'features/calendar/components/EarningsCalendarPage.tsx', 'features/calendar/components/MonthView.tsx', 'features/calendar/components/WeekView.tsx']) {
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
