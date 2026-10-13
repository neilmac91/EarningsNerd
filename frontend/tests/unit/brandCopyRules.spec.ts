import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { Badge, buttonVariants, type BadgeVariant, type ButtonVariant } from '@/components/ui'
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
 *    inside the product as on the public surfaces). Nothing an element renders in sage ink at rest
 *    may carry a digit, written inline, in a callback or mapped in from a literal array (SEC form
 *    codes such as "10-K" are names, and the device's citation brackets, "[1]" and "[F1]", are not
 *    numbers), or a value. Sage ink is any brand-family colour token, with or without an opacity
 *    modifier, in a state the element can rest in (dark:, a breakpoint, aria-*, data-*, disabled:);
 *    hover:, focus: and their group- and peer- forms are activity, sage's other job, so a control
 *    may turn sage under the pointer while its count rests in the ink. The ink comes from the
 *    className at the call site (inline or a same-file const), from a variant component (Button,
 *    RetryButton, MarketingCta and Badge, each variant's colour asked of the component itself, and
 *    buttonVariants() in a className likewise), or from an app component followed through the
 *    checker: one that renders its children in sage is a sage element, and one that renders a
 *    number in the ink it inherits fails inside a sage parent. A value is read through the type
 *    checker (one program from tsconfig.json): a number-typed expression, a template or a call fed
 *    one (a formatter, and so also a lookup such as labelFor(i)), a number's own method, a
 *    same-file constant holding one, or what a callback returns, through conditionals and JSX
 *    branches. A citation whose bracket is its whole text ("[{n}]") and a link that renders its own
 *    address are text. Out of a source scan's reach, and so review-checked: a date or an index name
 *    computed as text, a colour set by an inline style or on a pseudo-element, a library
 *    component's internals, and SVG text coloured by attribute (the chart theme, which carries no
 *    sage). The waitlist counter's own spec covers the count on the public pages.
 * 3. The Marked Copy Rule (DESIGN.md › Graphic device): the highlight (`en-mark`) never sits on a
 *    figure or a price, the hero's accent phrases included; the margin (`en-margin`) exists only
 *    inside MarkedCopy, and every MarkedCopy carries at least one marker (`EnRef`).
 */
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']

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
 *  number, a template with a number in it, a formatter fed a number), not only what its literals say.
 *  This build is the suite's slowest import (about 11 s on a laptop, outside any test's timeout): the
 *  price of seeing a runtime count a source scan cannot; skipLibCheck is set, and nothing else trims
 *  it without losing the checker, so do not fold it back into a regex. */
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

/** The nodes a className attribute is read from: its initializer, and the same-file const behind an
    identifier written as the whole expression or as a direct argument of its call (`className={cls}`,
    `className={cx(cls, '…')}`), so a class string held in a const is read as if written inline. */
function classNameNodes(opening: ts.JsxOpeningLikeElement): ts.Node[] {
  const attr = opening.attributes.properties.find((p): p is ts.JsxAttribute => ts.isJsxAttribute(p) && p.name.getText() === 'className')
  if (!attr?.initializer) return []
  const nodes: ts.Node[] = [attr.initializer]
  if (ts.isJsxExpression(attr.initializer) && attr.initializer.expression) {
    const e = unwrap(attr.initializer.expression)
    const ids = ts.isIdentifier(e) ? [e] : ts.isCallExpression(e) ? e.arguments.map(unwrap).filter(ts.isIdentifier) : []
    for (const id of ids) {
      const init = localInitializer(id, opening.getSourceFile())
      if (init) nodes.push(init)
    }
  }
  return nodes
}

/** Every string a className attribute can produce, split into tokens. */
function classTokens(opening: ts.JsxOpeningLikeElement): string[] {
  const parts: string[] = []
  for (const node of classNameNodes(opening)) {
    visit(node, (n) => {
      const text = ts.isJsxText(n) ? null : literalText(n)
      if (text !== null) parts.push(text)
    })
  }
  return parts.join(' ').split(/\s+/).filter(Boolean)
}

type Ink = 'sage' | 'other' | null

/** A sage colour token: any colour of the brand family (`text-brand`, `-strong`, `-strong-dark`, …), with or
    without an opacity modifier (`text-brand-strong/70`), or the legacy accent-strong alias. `fill-` counts on
    SVG text, whose glyphs it paints. */
const SAGE = /^(?:text|fill)-(?:brand(?:-[a-z]+)*|accent-strong)(?:\/(?:\d+|\[[^\]]+\]))?$/
const NOT_COLOUR = /^text-(?:xs|sm|base|lg|xl|[2-9]xl|data-[a-z]+|left|center|right|justify|start|end|ellipsis|clip|wrap|nowrap|balance|pretty)$|^fill-(?:none|current|inherit)$/
/** Variants that apply only under the pointer or keyboard focus (activity, sage's other job), and those that
    colour a pseudo-element rather than the element's own text. Every other variant (dark, a breakpoint,
    aria-*, data-*, disabled, open, checked, first, …) is a state an element can rest in, so its colour counts:
    a selected tab's sage count is a sage count. */
const ACTIVITY = /^(?:(?:group|peer)-)?(?:hover|focus|focus-visible|focus-within|active|visited|target)(?:\/[\w-]+)?$|^\[.*:(?:hover|focus|focus-visible|focus-within|active)\b.*\]$/
const PSEUDO = /^(?:placeholder|file|marker|selection|before|after|first-letter|first-line|backdrop)$/
const SVG_TEXT = new Set(['text', 'tspan', 'textPath'])
const CITATION = /^\[F?\d+\]$/
/** SEC form codes are names, not values ("Open the 10-K"), as a form code read from a variable already is. */
const FORM_CODE = /\b(?:10-K|10-Q|8-K|20-F|40-F|6-K|11-K|S-1|S-3|S-4|S-8|F-1|F-3|DEF 14A|13F)(?:\/A)?\b/g
const carriesDigit = (text: string) => {
  const trimmed = text.trim()
  return !CITATION.test(trimmed) && /\d/.test(trimmed.replace(FORM_CODE, ''))
}

/** A class token's variants and utility, split on the colons outside brackets (`data-[state=open]:…`). */
function splitVariants(token: string): string[] {
  const parts: string[] = []
  let depth = 0
  let start = 0
  for (let i = 0; i < token.length; i++) {
    if (token[i] === '[') depth++
    else if (token[i] === ']') depth--
    else if (token[i] === ':' && depth === 0) { parts.push(token.slice(start, i)); start = i + 1 }
  }
  parts.push(token.slice(start))
  return parts
}

/** The resting text colour class tokens give an element: 'sage', 'other', or null when they set none. */
function tokenInk(tokens: string[], svgText = false): Ink {
  let ink: Ink = null
  for (const token of tokens) {
    const parts = splitVariants(token)
    const utility = parts.pop()!.replace(/^!/, '')
    if (!(utility.startsWith('text-') || (svgText && utility.startsWith('fill-'))) || NOT_COLOUR.test(utility)) continue
    if (parts.some((variant) => ACTIVITY.test(variant) || PSEUDO.test(variant))) continue
    if (SAGE.test(utility)) return 'sage'
    ink = 'other'
  }
  return ink
}

/** The scanned files, so a component is followed only into the app's own code, never into a library. */
const SCANNED = new Set(FILES.map((file) => path.normalize(file)))

/** The declaration behind an identifier or a component tag, followed through imports and re-exports. */
function declarationOf(name: ts.Node): ts.Declaration | undefined {
  let symbol = CHECKER.getSymbolAtLocation(ts.isPropertyAccessExpression(name) ? name.name : name)
  if (symbol && symbol.flags & ts.SymbolFlags.Alias) symbol = CHECKER.getAliasedSymbol(symbol)
  const declaration = symbol?.valueDeclaration ?? symbol?.declarations?.[0]
  return declaration && SCANNED.has(path.normalize(declaration.getSourceFile().fileName)) ? declaration : undefined
}

/** The function a component declaration renders through: itself, the function a const holds, or the one
    passed to forwardRef() or memo(). */
function functionOf(node: ts.Node): ts.FunctionLikeDeclaration | undefined {
  if (ts.isFunctionDeclaration(node) || ts.isArrowFunction(node) || ts.isFunctionExpression(node)) return node
  const init = ts.isVariableDeclaration(node) ? node.initializer : ts.isExportAssignment(node) ? node.expression : undefined
  if (!init) return undefined
  const x = unwrap(init)
  if (ts.isArrowFunction(x) || ts.isFunctionExpression(x)) return x
  const target = ts.isCallExpression(x) && x.arguments[0] ? unwrap(x.arguments[0]) : x
  if (ts.isArrowFunction(target) || ts.isFunctionExpression(target)) return target
  if (ts.isIdentifier(target)) {
    const declaration = declarationOf(target)
    return declaration && declaration !== node ? functionOf(declaration) : undefined
  }
  return undefined
}

/** The app component a JSX tag renders, or undefined for an element or a library component. */
function componentFunction(opening: ts.JsxOpeningLikeElement): ts.FunctionLikeDeclaration | undefined {
  const tag = opening.tagName
  if (ts.isIdentifier(tag) && /^[a-z]/.test(tag.text)) return undefined
  const declaration = declarationOf(tag)
  return declaration && functionOf(declaration)
}

/** The expressions a function returns (its body when it is one), skipping nested functions. */
function returnedExpressions(fn: ts.FunctionLikeDeclaration): ts.Expression[] {
  if (!fn.body) return []
  if (!ts.isBlock(fn.body)) return [fn.body]
  const out: ts.Expression[] = []
  const collect = (n: ts.Node) => {
    if (ts.isFunctionLike(n)) return
    if (ts.isReturnStatement(n) && n.expression) out.push(n.expression)
    ts.forEachChild(n, collect)
  }
  ts.forEachChild(fn.body, collect)
  return out
}

/** What a call renders through the callbacks it is given (`rows.map((r) => …)`, with or without a block body). */
const callbackReturns = (call: ts.CallExpression) =>
  call.arguments.map(unwrap).filter((a): a is ts.ArrowFunction | ts.FunctionExpression => ts.isArrowFunction(a) || ts.isFunctionExpression(a)).flatMap(returnedExpressions)

/** The string members of a union type alias (`ButtonVariant`), read through the checker. */
function unionMembers(rel: string, name: string): string[] {
  const sf = PROGRAM.getSourceFile(path.join(ROOT, rel))
  let alias: ts.TypeAliasDeclaration | undefined
  if (sf) visit(sf, (n) => { if (!alias && ts.isTypeAliasDeclaration(n) && n.name.text === name) alias = n })
  if (!alias) throw new Error(`${rel} declares no ${name}`)
  const type = CHECKER.getTypeAtLocation(alias.name)
  return (type.isUnion() ? type.types : [type]).filter((t): t is ts.StringLiteralType => t.isStringLiteral()).map((t) => t.value)
}

/** The function a file declares under a name, for the variant components below. */
function declaredFunction(rel: string, name: string): ts.FunctionLikeDeclaration {
  const sf = PROGRAM.getSourceFile(path.join(ROOT, rel))
  let fn: ts.FunctionLikeDeclaration | undefined
  if (sf) visit(sf, (n) => {
    if (fn) return
    if (ts.isFunctionDeclaration(n) && n.name?.text === name) fn = n
    else if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.name.text === name) fn = functionOf(n)
  })
  if (!fn) throw new Error(`${rel} declares no component ${name}`)
  return fn
}

/** The variant a component takes when the call site names none, from its own destructuring default. */
function defaultVariant(fn: ts.FunctionLikeDeclaration, name: string): string {
  const binding = fn.parameters[0]?.name
  const element = binding && ts.isObjectBindingPattern(binding)
    ? binding.elements.find((e) => ts.isIdentifier(e.name) && e.name.text === 'variant')
    : undefined
  if (!element?.initializer || !ts.isStringLiteral(element.initializer)) throw new Error(`${name} declares no literal default variant`)
  return element.initializer.text
}

/** Each variant's resting ink, asked of the component itself (buttonVariants() for the Button family, a static
    render for Badge), so a variant that turns sage is read the day it does. */
const BUTTON_INK = new Map<string, Ink>(unionMembers('components/ui/Button.tsx', 'ButtonVariant')
  .map((v) => [v, tokenInk(buttonVariants({ variant: v as ButtonVariant }).split(/\s+/))]))
const BADGE_INK = new Map<string, Ink>(unionMembers('components/ui/Badge.tsx', 'BadgeVariant').map((v) => {
  const html = renderToStaticMarkup(createElement(Badge, { variant: v as BadgeVariant }, 'x'))
  return [v, tokenInk((html.match(/^<[a-z]+[^>]*?\bclass="([^"]*)"/)?.[1] ?? '').split(/\s+/))]
}))
/** The components whose colour is their `variant` prop, with the variant each takes by default. RetryButton
    (hooks/useRetainedFailure.tsx) and MarketingCta render a ui Button's treatment. */
const VARIANT_COMPONENTS = new Map(([
  ['components/ui/Button.tsx', 'Button', BUTTON_INK],
  ['hooks/useRetainedFailure.tsx', 'RetryButton', BUTTON_INK],
  ['features/marketing/components/MarketingCta.tsx', 'MarketingCta', BUTTON_INK],
  ['components/ui/Badge.tsx', 'Badge', BADGE_INK],
] as const).map(([rel, name, inks]) => {
  const fn = declaredFunction(rel, name)
  return [fn as ts.Node, { inks, fallback: defaultVariant(fn, name) }] as const
}))

function variantLiterals(e: ts.Expression): string[] {
  const x = unwrap(e)
  const text = literalText(x)
  if (text !== null) return [text]
  if (ts.isConditionalExpression(x)) return [...variantLiterals(x.whenTrue), ...variantLiterals(x.whenFalse)]
  if (ts.isBinaryExpression(x)) return [...variantLiterals(x.left), ...variantLiterals(x.right)]
  return []
}

/** The inks a variant component, or a `buttonVariants()` call in an element's className, can give its
    children, or null when the element is neither. A variant the scan cannot read (an identifier, a spread,
    a shorthand `variant`) counts as sage, since it may be. */
function variantInks(opening: ts.JsxOpeningLikeElement): Ink[] | null {
  const ink = (inks: Map<string, Ink>) => (v: string): Ink => (inks.has(v) ? inks.get(v)! : 'sage')
  const fn = componentFunction(opening)
  const component = fn && VARIANT_COMPONENTS.get(fn)
  if (component) {
    const attr = opening.attributes.properties.find((p): p is ts.JsxAttribute => ts.isJsxAttribute(p) && p.name.getText() === 'variant')
    let variants: string[]
    if (opening.attributes.properties.some((p) => ts.isJsxSpreadAttribute(p))) variants = ['unknown']
    else if (!attr) variants = [component.fallback]
    else if (attr.initializer && ts.isStringLiteral(attr.initializer)) variants = [attr.initializer.text]
    else if (attr.initializer && ts.isJsxExpression(attr.initializer) && attr.initializer.expression) {
      variants = variantLiterals(attr.initializer.expression)
      if (variants.length === 0) variants = ['unknown']
    } else variants = ['unknown']
    return variants.map(ink(component.inks))
  }
  const variants: string[] = []
  for (const node of classNameNodes(opening)) {
    visit(node, (n) => {
      if (!ts.isCallExpression(n) || n.expression.getText() !== 'buttonVariants') return
      const options = n.arguments[0]
      // No options: the factory's default, primary.
      if (!options) { variants.push('primary'); return }
      const opaque = !ts.isObjectLiteralExpression(options)
        || options.properties.some((p) => ts.isSpreadAssignment(p) || (ts.isShorthandPropertyAssignment(p) && p.name.text === 'variant'))
      if (opaque) { variants.push('unknown'); return }
      const variant = options.properties.find((p): p is ts.PropertyAssignment => ts.isPropertyAssignment(p) && p.name.getText() === 'variant')
      const read = variant ? variantLiterals(variant.initializer) : ['primary']
      variants.push(...(read.length ? read : ['unknown']))
    })
  }
  return variants.length ? variants.map(ink(BUTTON_INK)) : null
}

/** The resting ink the call site gives an element: a variant component's variant, or the className written
    there (inline, a same-file const, or buttonVariants() in it). */
function siteInk(opening: ts.JsxOpeningLikeElement): Ink {
  const classes = tokenInk(classTokens(opening), SVG_TEXT.has(opening.tagName.getText()))
  const variants = variantInks(opening)
  if (!variants) return classes
  return variants.includes('sage') || classes === 'sage' ? 'sage' : variants.includes(null) ? classes : 'other'
}

const COLOURS = new Map<ts.Node, Ink>()
/** The ink an element gives its children: 'sage' or 'other' when it sets a resting text colour, null when
    they inherit its parent's. The call site's ink first; then, for a component the app declares, the ink it
    renders its children in, so a component that wraps its children in sage is a sage element. */
function textColour(opening: ts.JsxOpeningLikeElement): Ink {
  const known = COLOURS.get(opening)
  if (known !== undefined) return known
  COLOURS.set(opening, null)
  let ink = siteInk(opening)
  if (ink === null) {
    const fn = componentFunction(opening)
    if (fn) ink = summary(fn).childrenInk
  }
  COLOURS.set(opening, ink)
  return ink
}

/** What a component does with the ink it inherits: the ink its children render in (null when they inherit
    it too), and whether it renders a number of its own in that inherited ink, which a sage parent colours. */
interface Summary { childrenInk: Ink; inheritsValue: boolean }
const SUMMARIES = new Map<ts.Node, Summary>()
function summary(fn: ts.FunctionLikeDeclaration): Summary {
  const known = SUMMARIES.get(fn)
  if (known) return known
  // A component that renders itself reads, mid-walk, as one that passes its ink through and carries nothing.
  SUMMARIES.set(fn, { childrenInk: null, inheritsValue: false })
  const sf = fn.getSourceFile()
  const childInks = new Set<'sage' | 'other' | 'inherit'>()
  let carries = false
  const props = fn.parameters[0]
  const takesChildren = !!props && !!CHECKER.getTypeAtLocation(props).getProperty('children')
  const isChildren = (e: ts.Expression) => {
    const x = unwrap(e)
    return (ts.isIdentifier(x) && x.text === 'children') || (ts.isPropertyAccessExpression(x) && x.name.text === 'children')
  }
  const element = (el: ts.JsxElement | ts.JsxSelfClosingElement, ink: 'sage' | 'other' | 'inherit') => {
    const opening = ts.isJsxElement(el) ? el.openingElement : el
    const next = textColour(opening) ?? ink
    // A spread can carry the children through (`<span {...rest} />`).
    if (takesChildren && opening.attributes.properties.some((p) => ts.isJsxSpreadAttribute(p))) childInks.add(next)
    if (ink === 'inherit' && inheritsValue(opening)) carries = true
    if (ts.isJsxElement(el)) children(el.children, next)
  }
  const children = (list: ts.NodeArray<ts.JsxChild>, ink: 'sage' | 'other' | 'inherit') => {
    list.forEach((child, i) => {
      if (ts.isJsxText(child)) { if (ink === 'inherit' && carriesDigit(child.text)) carries = true }
      else if (ts.isJsxExpression(child) && child.expression) { if (!citationBracket(list, i) && !bracketTemplate(child.expression)) expression(child.expression, ink) }
      else if (ts.isJsxElement(child) || ts.isJsxSelfClosingElement(child)) element(child, ink)
      else if (ts.isJsxFragment(child)) children(child.children, ink)
    })
  }
  const expression = (e: ts.Expression, ink: 'sage' | 'other' | 'inherit') => {
    const x = unwrap(e)
    if (isChildren(x)) childInks.add(ink)
    else if (ts.isJsxElement(x) || ts.isJsxSelfClosingElement(x)) element(x, ink)
    else if (ts.isJsxFragment(x)) children(x.children, ink)
    else if (ts.isConditionalExpression(x)) { expression(x.whenTrue, ink); expression(x.whenFalse, ink) }
    else if (ts.isBinaryExpression(x)) { expression(x.left, ink); expression(x.right, ink) }
    else if (ts.isCallExpression(x) && callbackReturns(x).length) callbackReturns(x).forEach((r) => expression(r, ink))
    else if (ink === 'inherit') {
      const text = literalText(x)
      if (text !== null ? carriesDigit(text) : rendersValue(x, sf)) carries = true
    }
  }
  for (const r of returnedExpressions(fn)) expression(r, 'inherit')
  const result: Summary = {
    childrenInk: childInks.has('sage') ? 'sage' : childInks.has('inherit') ? null : 'other',
    inheritsValue: carries,
  }
  SUMMARIES.set(fn, result)
  return result
}

/** Whether a component element renders a number in the ink it inherits, which a sage parent would colour. */
function inheritsValue(opening: ts.JsxOpeningLikeElement): boolean {
  if (siteInk(opening) !== null) return false
  const fn = componentFunction(opening)
  return !!fn && summary(fn).inheritsValue
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
    else if (ts.isJsxFragment(x)) inkTexts(x.children, sf, out)
    else if (ts.isJsxElement(x) && textColour(x.openingElement) === null) inkTexts(x.children, sf, out)
    else if (ts.isCallExpression(x)) callbackReturns(x).forEach(expr)
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

/** Whether a JSX expression renders a value: a number-typed expression, a template or concatenation with a
 *  number in it, a string-returning call fed a number (a formatter, and so also a lookup such as
 *  `labelFor(i)`: give that label its own ink or pass it a string), what a callback returns, a conditional
 *  with such a branch, a same-file constant built from one of those, or a component that renders a number
 *  in the ink it inherits. */
function rendersValue(e: ts.Expression, sf: ts.SourceFile, depth = 0): boolean {
  const x = unwrap(e)
  if (depth > 6) return false
  if (ts.isJsxSelfClosingElement(x)) return inheritsValue(x)
  if (ts.isJsxFragment(x)) return inkValues(x.children, sf).length > 0
  if (ts.isJsxElement(x)) return inheritsValue(x.openingElement) || (textColour(x.openingElement) === null && inkValues(x.children, sf).length > 0)
  if (ts.isTemplateExpression(x)) return x.templateSpans.some((span) => rendersValue(span.expression, sf, depth + 1))
  if (literalText(x) !== null) return false
  if (ts.isConditionalExpression(x)) return rendersValue(x.whenTrue, sf, depth + 1) || rendersValue(x.whenFalse, sf, depth + 1)
  if (ts.isBinaryExpression(x)) return rendersValue(x.left, sf, depth + 1) || rendersValue(x.right, sf, depth + 1)
  if (ts.isCallExpression(x)) {
    // A number's own method ("n.toLocaleString()"), a call that returns one, a formatter fed one
    // (a literal argument such as "slice(0, 20)" is not a value), or what a callback returns.
    if (isNumberTyped(x)) return true
    if (ts.isPropertyAccessExpression(x.expression) && isNumberTyped(x.expression.expression)) return true
    if (callbackReturns(x).some((r) => rendersValue(r, sf, depth + 1))) return true
    return x.arguments.some((a) => !ts.isArrowFunction(unwrap(a)) && !ts.isFunctionExpression(unwrap(a)) && literalText(unwrap(a)) === null && isNumberTyped(a))
  }
  if (ts.isIdentifier(x)) {
    const init = localInitializer(x, sf)
    if (init) return rendersValue(init, sf, depth + 1) || isNumberTyped(x)
  }
  return isNumberTyped(x)
}

/** The device's citation marker: an expression whose bracket is the whole of the text around it ("[{n}]"). */
function citationBracket(children: ts.NodeArray<ts.JsxChild>, i: number): boolean {
  const before = children[i - 1]
  const after = children[i + 1]
  return !!before && !!after && ts.isJsxText(before) && ts.isJsxText(after) && /^\s*\[\s*$/.test(before.text) && /^\s*\]\s*$/.test(after.text)
}

/** A template whose brackets are its whole text (`{`[${n}]`}`): the citation marker written as one string. */
function bracketTemplate(e: ts.Expression): boolean {
  const x = unwrap(e)
  return ts.isTemplateExpression(x) && /^\s*\[\s*$/.test(x.head.text) && x.templateSpans.length === 1 && /^\s*\]\s*$/.test(x.templateSpans[0].literal.text)
}

/** The expression a link renders as its own address (`<a href={url}>{url}</a>`): text, not a value. */
function ownAddress(opening: ts.JsxOpeningLikeElement | undefined, e: ts.Expression): boolean {
  const href = opening?.attributes.properties.find((p): p is ts.JsxAttribute => ts.isJsxAttribute(p) && p.name.getText() === 'href')
  return !!href?.initializer && ts.isJsxExpression(href.initializer) && !!href.initializer.expression && href.initializer.expression.getText() === e.getText()
}

/** The expressions and component elements an element renders in its own ink that carry a value (stops at a
    child with its own colour). */
function inkValues(children: ts.NodeArray<ts.JsxChild>, sf: ts.SourceFile, out: ts.Node[] = [], opening?: ts.JsxOpeningLikeElement) {
  const element = (el: ts.JsxElement | ts.JsxSelfClosingElement | ts.JsxFragment) => {
    if (ts.isJsxFragment(el)) return void inkValues(el.children, sf, out)
    const own = ts.isJsxElement(el) ? el.openingElement : el
    if (inheritsValue(own)) out.push(el)
    if (ts.isJsxElement(el) && textColour(own) === null) inkValues(el.children, sf, out)
  }
  children.forEach((child, i) => {
    if (ts.isJsxExpression(child) && child.expression) {
      if (citationBracket(children, i) || ownAddress(opening, child.expression)) return
      if (bracketTemplate(child.expression)) return
      const x = unwrap(child.expression)
      if (ts.isJsxElement(x) || ts.isJsxSelfClosingElement(x) || ts.isJsxFragment(x)) return element(x)
      if (rendersValue(child.expression, sf)) out.push(child.expression)
    } else if (ts.isJsxElement(child) || ts.isJsxSelfClosingElement(child) || ts.isJsxFragment(child)) element(child)
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
        for (const { node, text } of inkTexts(n.children, sf)) if (carriesDigit(text)) offenders.push(where(rel, sf, node, text))
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
