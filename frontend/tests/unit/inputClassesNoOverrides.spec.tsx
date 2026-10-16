import { readdirSync, readFileSync, statSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { render } from '@testing-library/react'
import postcss from 'postcss'
import tailwindcss, { type Config } from 'tailwindcss'
import resolveConfig from 'tailwindcss/resolveConfig'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import * as uiBarrel from '@/components/ui'
import * as inputModule from '@/components/ui/Input'
import { FieldSpinner, Input, Select, Textarea, inputClasses, type FieldDensity, type InputClassesOptions } from '@/components/ui/Input'
import { bindingResolver } from './astBindings'

/**
 * Rule-12 gate for components/ui/Input.tsx: a raw field takes inputClasses() options, never a class on top
 * that sets what the field already sets. `cx` and `clsx` do no tailwind-merge, so of two utilities that set one
 * property in one state, the one later in the STYLESHEET wins, whatever the class order. On main abda78ce
 * (Chromium 141, production build) `.w-auto` was rule 332 and `.w-full` rule 333, so `w-auto` on top of the
 * field's `w-full` lost: the settings page's digest select filled its 782px row and squeezed "Digest
 * frequency" into a 68px column, five lines deep; the admin filter selects stacked one per line; and the
 * percentage width zeroed the feedback status select's min-content width, so the scrolling table squeezed it to
 * 58px and "Resolved" read "R". `py-1.5` (rule 620) lost to the field's `py-2.5` (625) at both sites that set it;
 * `text-xs` (699) beat `text-sm` (697) by one rule. The options are `select` (a raw <select>'s chevron room),
 * `autoWidth` (sized to its content), `density`, `leadingIcon` and `trailingIcon` (the password field's reveal
 * toggle, which set `pr-10` on top until it existed); Button's twin gate is button-icon-size-gate.spec.ts. The
 * scan skips Input.tsx, so the module's own classes are held below: padding to explicit sides by "the field's
 * padding is explicit", each single-line field's box to DESIGN.md's `input` height (44px; `input-compact`'s 36px
 * from sm for a compact field) at 100% and 200% text by "the field's height is the documented one", and every
 * field (each combination of the options, and the Input, Textarea and Select components) to one class per
 * property per variant chain, with `invalid` (the components' `error`) picking the error tone's border and ring
 * rather than layering them, by "the field's tone is one class per state".
 *
 * The scan reads the TypeScript AST of every .ts and .tsx under app/, components/, features/, hooks/ and lib/,
 * except Input.tsx, which defines the field. For each `inputClasses(…)` call (imported from components/ui/Input
 * or the components/ui barrel, under any alias) it collects the classes combined with it: its `className`
 * option, the other chunks of an enclosing template literal, and the other arguments of an enclosing `clsx`/`cx`
 * (string literals, both branches of a condition, object keys, array elements, a same-file const, a string the
 * DS modules export such as `fieldUnavailableClass`), up to the `className` attribute that takes them. It reads
 * each option as written (a non-literal flag is checked both ways) and computes the field's own classes by
 * calling the real inputClasses() with them. Tailwind itself (this config, globals.css as input) says what each
 * bare utility declares. An added class COMPETES with a field class when both style the same element (or
 * pseudo-element) and declare one property with different values, `--tw-*` properties included, and a shorthand
 * against its longhands (`p-2` against `px-3.5`, `rounded-r-none` against `rounded-lg`). Two declarations that are
 * both Tailwind's composite plumbing (a value reading a `var(--tw-…)` its own rule does not set: the box-shadow
 * behind `shadow-*` and `ring-*`) never compete, so `focus:ring-0` passes against the field's ring shadow while
 * `focus:[box-shadow:none]` fails. It fails:
 *
 *  (a) same chain: the two carry the same variants (as a set). Stylesheet order decides: `w-auto` vs `w-full`.
 *  (b) no twin: the field sets the property under `dark:` or a screen (`sm:`) the added class lacks, plus only
 *      variants the added class carries, and no added class covers that chain. The field's rule outranks it
 *      there: the delete-account field's `focus:border-error-light` shows the brand border in dark.
 *  (c) `!important`, an arbitrary variant (`[&>option]:`) the gate cannot place, or a token Tailwind does not
 *      generate. A marker (`group`, `peer`) or a utility that styles only other elements (`space-x-2`) passes.
 *  (d) a <select> without `select` (PAD's 14px right inset leaves the forms plugin's chevron no room, and a
 *      select that sizes to its content puts its text under it; a list box, `multiple` or a literal `size` over
 *      1, draws no chevron and is exempt), or `select` on anything but a <select>.
 *  (e) a control drawn at an edge of the field without that edge's inset, reserved always. A sibling (beside the
 *      field in its parent, through `{cond && …}`, ternaries and fragments) that is `absolute` or `fixed` with a
 *      `right-*`/`end-*` class, or a <FieldSpinner />, needs `trailingIcon: true` (or `select: true`); one with
 *      `left-*`/`start-*` needs `leadingIcon: true`. A flag that follows the control's condition fails: when the
 *      padding grows, Chromium leaves the caret where it was, so a long query loses its end and the caret under
 *      the spinner for the whole load, and when it shrinks the line jumps. On main the three search fields drew a
 *      20px spinner at right-4 over the 14px inset, over the last 17–21px of typed text. `inset-y-*` is vertical
 *      (the reveal toggle's `inset-y-0 right-0`); a popover at `top-full` or with no horizontal anchor is not at an
 *      edge; `inset-*`, `inset-x-*`, both sides at once, or a sibling it cannot enumerate fails closed.
 *  (f) no union twin: the two carry different variant chains, neither inside the other, that can hold at once
 *      (not `disabled:` beside `focus:`), in one theme and screen, and the field does not style the added class's
 *      chain itself (that is (a)'s). Of the classes whose chain lies inside both chains together, the longest
 *      ones disagree, so variant order or a variant count, not the state, decides. On main the composer shell's
 *      `focus-within:border-brand` lost to the field's `hover:border-flat-light` (Tailwind emits `focus-within`
 *      before `hover`), so a hovered, focused composer turned grey, and `fieldUnavailableClass`'s
 *      `aria-disabled:hover:border-border-light` (0,3,0) beat a focused select's `focus:border-brand` (0,2,0).
 *      A class on the union chain (`hover:focus-within:border-brand`) settles it.
 *
 * A state layer passes: `aria-disabled:bg-background-light` over the field's `bg-white` (with its
 * `dark:aria-disabled:` twin), `aria-disabled:hover:focus:border-brand` on the focused select. A position the scan cannot
 * follow (the result held in a variable, returned, joined with `+`, passed to another function, a className
 * from a parameter, an option spread, a class glued to a template's text or to the next expression) fails rather
 * than passing unread.
 *
 * PINS holds the known findings by path and exact text, one entry per site, with a reason, capped and
 * shrink-only: a new finding fails, a second site with a pinned finding fails, and so does a pin that no longer
 * matches.
 *
 * The module's own tones are held to the same standard by "the field's tone is one class per state": the default
 * tone leaves only its `focus:` border over its `hover:` one to variant order, and the test reads Tailwind's
 * compile to show focus is emitted after hover; a shell (`inputClasses({ shell: true })`) restates its
 * `focus-within:` border under `hover:`.
 *
 * What it cannot see: a class reaching the field through a props spread or another component; a namespace import, a dynamic import, or a re-export
 * other than the components/ui barrel; a member-tag select (`<motion.select>`) reads as not a select; a positioned
 * control nested in an unpositioned sibling wrapper, or a component other than FieldSpinner that positions itself.
 */

const FRONTEND_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const ROOTS = ['app', 'components', 'features', 'hooks', 'lib']
const DEFINITION = 'components/ui/Input.tsx'

const PINS: Record<string, { findings: string[]; reason: string }> = {

}
/** Shrink-only: files, and findings (one entry per site, so a second site with the same override fails). */
const MAX_PINNED = { files: 0, findings: 0 }

/** The findings PINS does not cover, counting each pinned entry once, and the pins no finding matched. */
function againstPins(found: { file: string; line: number; finding: string }[], pins: typeof PINS) {
  const left = new Map<string, number>()
  for (const [file, pin] of Object.entries(pins)) for (const f of pin.findings) left.set(`${file}: ${f}`, (left.get(`${file}: ${f}`) ?? 0) + 1)
  const unpinned = found.flatMap((f) => {
    const key = `${f.file}: ${f.finding}`
    const n = left.get(key) ?? 0
    if (n > 0) {
      left.set(key, n - 1)
      return []
    }
    return [`${f.file}:${f.line} ${f.finding}`]
  })
  const stale = [...left].filter(([, n]) => n > 0).map(([key]) => key)
  return { unpinned, stale }
}

// ------------------------------------------------------------------------------------------------- scanner

type Options = { invalid: boolean; tone: 'default' | 'danger'; leadingIcon: boolean; trailingIcon: boolean; select: boolean; density: FieldDensity; autoWidth: boolean; shell: boolean }
const DEFAULTS: Options = { invalid: false, tone: 'default', leadingIcon: false, trailingIcon: false, select: false, density: 'comfortable', autoWidth: false, shell: false }
const BOOLEAN_OPTIONS = ['invalid', 'leadingIcon', 'trailingIcon', 'select', 'autoWidth', 'shell'] as const
const DENSITIES: FieldDensity[] = ['comfortable', 'compact']
const FIELD_TONES: Options['tone'][] = ['default', 'danger']

/** A sibling drawn at one edge of the field: it needs that side's inset, reserved always. */
interface Edge { tag: string; side: 'left' | 'right'; anchor: string }
interface Site { file: string; line: number; tag: string; listBox: boolean; combos: Options[]; added: string[]; edges: Edge[] }
interface Scan { calls: number; sites: Site[]; unreadable: string[] }

class Unreadable extends Error {}

/** The modules whose exports the scan reads at runtime, keyed by their path under frontend/ without extension. */
const DS_MODULES: Record<string, Record<string, unknown>> = {
  'components/ui/Input': inputModule,
  'components/ui/index': uiBarrel,
}
/** The class joiners, by module: what an enclosing call of theirs combines with the field. */
const JOINERS: Record<string, string[]> = { clsx: ['clsx', 'default'], 'components/ui/cx': ['cx'], 'components/ui/index': ['cx'] }

/** `@/components/ui` and `../ui/Input` alike, as a path under frontend/ without extension; a package stays as is. */
function moduleKey(file: string, specifier: string): string {
  let key = specifier
  if (specifier.startsWith('@/')) key = specifier.slice(2)
  else if (specifier.startsWith('.')) key = path.posix.normalize(path.posix.join(path.posix.dirname(file), specifier))
  else return specifier
  key = key.replace(/\.(tsx?|js)$/, '')
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
  const isInputClasses = (e: ts.Node): boolean => {
    if (!ts.isIdentifier(e)) return false
    const imp = importOf(e)
    return !!imp && imp.name === 'inputClasses' && imp.module in DS_MODULES
  }
  const isJoiner = (e: ts.Expression): boolean => {
    if (!ts.isIdentifier(e)) return false
    const imp = importOf(e)
    return !!imp && (JOINERS[imp.module] ?? []).includes(imp.name)
  }
  const lineOf = (n: ts.Node) => sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1
  const split = (s: string) => s.split(/\s+/).filter(Boolean)

  /** Every class an expression can contribute; throws when the gate cannot read it. */
  const classSource = (e: ts.Expression, depth = 0): string[] => {
    if (depth > 20) throw new Unreadable('a class source nested too deep to follow')
    if (ts.isStringLiteral(e) || ts.isNoSubstitutionTemplateLiteral(e)) return split(e.text)
    if (ts.isTemplateExpression(e)) return templateClasses(e, undefined, depth)
    if (ts.isParenthesizedExpression(e) || ts.isAsExpression(e) || ts.isNonNullExpression(e)) return classSource(e.expression, depth + 1)
    if (ts.isConditionalExpression(e)) return [...classSource(e.whenTrue, depth + 1), ...classSource(e.whenFalse, depth + 1)]
    if (ts.isBinaryExpression(e)) {
      const op = e.operatorToken.kind
      if (op === ts.SyntaxKind.AmpersandAmpersandToken) return classSource(e.right, depth + 1)
      if (op === ts.SyntaxKind.BarBarToken || op === ts.SyntaxKind.QuestionQuestionToken) {
        return [...classSource(e.left, depth + 1), ...classSource(e.right, depth + 1)]
      }
    }
    if (e.kind === ts.SyntaxKind.FalseKeyword || e.kind === ts.SyntaxKind.NullKeyword) return []
    if (ts.isCallExpression(e) && isJoiner(e.expression)) return e.arguments.flatMap((a) => classSource(a, depth + 1))
    if (ts.isArrayLiteralExpression(e)) return e.elements.flatMap((a) => classSource(a, depth + 1))
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
        if (isConst && binding.init) return classSource(binding.init, depth + 1)
        throw new Unreadable(`a class from \`${e.text}\`, which is not a const with an initializer`)
      }
      const imp = imports.get(e.text)
      const value = imp && DS_MODULES[imp.module]?.[imp.name]
      if (typeof value === 'string') return split(value)
      throw new Unreadable(`a class from \`${e.text}\`, which the gate cannot read`)
    }
    throw new Unreadable(`a class from a ${ts.SyntaxKind[e.kind]}`)
  }

  /** A template literal's classes, without the span that holds the call being read. */
  const templateClasses = (tpl: ts.TemplateExpression, except: ts.TemplateSpan | undefined, depth: number): string[] => {
    const out = split(tpl.head.text)
    let before = tpl.head.text
    tpl.templateSpans.forEach((span, i) => {
      // `${a}${b}` glues a's last class to b's first, as `px-${n}` and `${a}mt-2` glue to text.
      const glued = (i > 0 && before === '') || /\S$/.test(before) || /^\S/.test(span.literal.text)
      if (glued) throw new Unreadable('a class built from pieces of a template')
      if (span !== except) out.push(...classSource(span.expression, depth + 1))
      out.push(...split(span.literal.text))
      before = span.literal.text
    })
    return out
  }

  /** An attribute's literal value: true when it has none, null when it is not a literal, undefined when absent. */
  const attrValue = (element: ts.JsxOpeningLikeElement, name: string): string | boolean | null | undefined => {
    const a = element.attributes.properties.find((x): x is ts.JsxAttribute => ts.isJsxAttribute(x) && x.name.getText(sf) === name)
    if (!a) return undefined
    const init = a.initializer
    if (!init) return true
    if (ts.isStringLiteral(init)) return init.text
    const e = ts.isJsxExpression(init) ? init.expression : undefined
    if (e?.kind === ts.SyntaxKind.TrueKeyword) return true
    if (e?.kind === ts.SyntaxKind.FalseKeyword) return false
    if (e && (ts.isNumericLiteral(e) || ts.isStringLiteral(e))) return e.text
    return null
  }
  /** The forms plugin draws no chevron on `select[multiple]` or `select[size]:not([size="1"])`. A value the gate
      cannot read is not a list box, so such a select is held to `select: true`. */
  const isListBox = (element: ts.JsxOpeningLikeElement): boolean => {
    const multiple = attrValue(element, 'multiple')
    const size = attrValue(element, 'size')
    return multiple === true || (typeof size === 'string' && Number(size) > 1)
  }

  const readOptions = (call: ts.CallExpression): { combos: Options[]; className: string[] } => {
    if (call.arguments.length > 1) throw new Unreadable('inputClasses() given more than one argument')
    const arg = call.arguments[0]
    if (!arg) return { combos: [DEFAULTS], className: [] }
    if (!ts.isObjectLiteralExpression(arg)) throw new Unreadable('inputClasses() options that are not an object literal')
    const values: { [K in keyof Options]: Options[K][] } = {
      invalid: [false], tone: ['default'], leadingIcon: [false], trailingIcon: [false], select: [false], density: ['comfortable'], autoWidth: [false], shell: [false],
    }
    let className: string[] = []
    for (const p of arg.properties) {
      if (!ts.isPropertyAssignment(p) || !(ts.isIdentifier(p.name) || ts.isStringLiteral(p.name))) {
        throw new Unreadable('an inputClasses() option the gate cannot read (a spread, shorthand or computed key)')
      }
      const key = p.name.text
      const v = p.initializer
      if (key === 'className') className = classSource(v)
      else if ((BOOLEAN_OPTIONS as readonly string[]).includes(key)) {
        const k = key as (typeof BOOLEAN_OPTIONS)[number]
        values[k] = v.kind === ts.SyntaxKind.TrueKeyword ? [true] : v.kind === ts.SyntaxKind.FalseKeyword ? [false] : [false, true]
      } else if (key === 'density') {
        values.density = ts.isStringLiteral(v) && (DENSITIES as string[]).includes(v.text) ? [v.text as FieldDensity] : DENSITIES
      } else if (key === 'tone') {
        values.tone = ts.isStringLiteral(v) && (FIELD_TONES as string[]).includes(v.text) ? [v.text as Options['tone']] : FIELD_TONES
      } else throw new Unreadable(`an option inputClasses() does not take: ${key}`)
    }
    let combos: Options[] = [{ ...DEFAULTS }]
    for (const key of Object.keys(values) as (keyof Options)[]) {
      combos = combos.flatMap((c) => (values[key] as Options[typeof key][]).map((v) => ({ ...c, [key]: v })))
    }
    return { combos, className }
  }

  /** <FieldSpinner /> positions itself: absolute right-3, the box `trailingIcon` reserves. */
  const isFieldSpinner = (tag: ts.JsxTagNameExpression): boolean => {
    if (!ts.isIdentifier(tag)) return false
    const imp = importOf(tag)
    return !!imp && imp.name === 'FieldSpinner' && imp.module in DS_MODULES
  }
  const holdsInputClasses = (n: ts.Node): boolean =>
    (ts.isCallExpression(n) && isInputClasses(n.expression)) || !!ts.forEachChild(n, (c) => holdsInputClasses(c) || undefined)

  /** The edge a sibling element is drawn at, from its classes; undefined when it sits at no edge of the field. */
  const edgeOf = (el: ts.JsxOpeningLikeElement): Edge | undefined => {
    const tag = el.tagName.getText(sf)
    if (isFieldSpinner(el.tagName)) return { tag, side: 'right', anchor: 'absolute right-3' }
    const attr = el.attributes.properties.find((x): x is ts.JsxAttribute => ts.isJsxAttribute(x) && x.name.getText(sf) === 'className')
    const init = attr?.initializer
    const expr = init && (ts.isStringLiteral(init) ? init : ts.isJsxExpression(init) ? init.expression : undefined)
    // Another field beside this one is a site of its own.
    if (!expr || holdsInputClasses(expr)) return undefined
    const utilities = classSource(expr).map((t) => parseClass(t).utility.replace(/^-/, ''))
    if (!utilities.some((u) => u === 'absolute' || u === 'fixed')) return undefined
    // Outside the field's box: a popover below (`top-full`) or above it.
    if (utilities.some((u) => /^(top|bottom)-(full|\[100%\])$/.test(u))) return undefined
    const right = utilities.filter((u) => /^(right|end)-/.test(u))
    const left = utilities.filter((u) => /^(left|start)-/.test(u))
    // `inset-y-*` is vertical only (the reveal toggle's `absolute inset-y-0 right-0`); `inset-*` and `inset-x-*` span both edges.
    const both = utilities.filter((u) => /^inset-(?!y-)/.test(u))
    if (both.length || (right.length && left.length)) {
      throw new Unreadable(`a <${tag}> beside the field anchored to both of its edges (${[...both, ...left, ...right].join(' ')})`)
    }
    if (right.length) return { tag, side: 'right', anchor: right.join(' ') }
    if (left.length) return { tag, side: 'left', anchor: left.join(' ') }
    return undefined // no horizontal anchor: it sits at its static position, after the field
  }

  /** The elements a field's parent renders beside it, through {cond && X}, ternaries and fragments. */
  const siblingsOf = (field: ts.Node): ts.JsxOpeningLikeElement[] => {
    let node: ts.Node = field
    let p = node.parent
    for (;;) {
      if (ts.isParenthesizedExpression(p) || ts.isJsxExpression(p)) node = p
      else if (ts.isBinaryExpression(p) && node === p.right && p.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken) node = p
      else if (ts.isConditionalExpression(p) && node !== p.condition) node = p
      else break
      p = node.parent
    }
    if (!ts.isJsxElement(p) && !ts.isJsxFragment(p)) return [] // the root of what a component returns: nothing beside it
    const out: ts.JsxOpeningLikeElement[] = []
    const walk = (n: ts.Node): void => {
      if (ts.isJsxText(n) || n.kind === ts.SyntaxKind.NullKeyword || n.kind === ts.SyntaxKind.FalseKeyword) return
      if (ts.isStringLiteral(n) || ts.isNumericLiteral(n) || (ts.isIdentifier(n) && n.text === 'undefined')) return
      if (ts.isJsxSelfClosingElement(n)) out.push(n)
      else if (ts.isJsxElement(n)) out.push(n.openingElement)
      else if (ts.isJsxFragment(n)) n.children.forEach(walk)
      else if (ts.isJsxExpression(n)) {
        if (n.expression) walk(n.expression)
      } else if (ts.isParenthesizedExpression(n)) walk(n.expression)
      else if (ts.isBinaryExpression(n) && n.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken) walk(n.right)
      else if (ts.isConditionalExpression(n)) {
        walk(n.whenTrue)
        walk(n.whenFalse)
      } else throw new Unreadable(`a sibling of the field the gate cannot read (a ${ts.SyntaxKind[n.kind]})`)
    }
    for (const c of p.children) if (c !== node) walk(c)
    return out
  }

  /** Follows a call up to the className attribute that takes it, collecting what it is combined with. */
  const readSite = (call: ts.CallExpression): Site => {
    const { combos, className } = readOptions(call)
    const added = [...className]
    let node: ts.Node = call
    for (;;) {
      const p = node.parent
      if (ts.isParenthesizedExpression(p) || ts.isAsExpression(p) || ts.isNonNullExpression(p)) node = p
      else if (ts.isConditionalExpression(p) && node !== p.condition) node = p
      else if (ts.isBinaryExpression(p) && node === p.right && p.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken) node = p
      else if (ts.isTemplateSpan(p) && node === p.expression) {
        added.push(...templateClasses(p.parent, p, 0))
        node = p.parent
      } else if (ts.isCallExpression(p) && isJoiner(p.expression)) {
        for (const a of p.arguments) if (a !== node) added.push(...classSource(a))
        node = p
      } else if (ts.isArrayLiteralExpression(p) && ts.isCallExpression(p.parent) && isJoiner(p.parent.expression)) {
        for (const a of p.elements) if (a !== node) added.push(...classSource(a))
        node = p
      } else if (ts.isJsxExpression(p) && ts.isJsxAttribute(p.parent) && p.parent.name.getText(sf) === 'className') {
        const element = p.parent.parent.parent
        const edges = siblingsOf(ts.isJsxOpeningElement(element) ? element.parent : element).flatMap((el) => edgeOf(el) ?? [])
        return { file, line: lineOf(call), tag: element.tagName.getText(sf), listBox: isListBox(element), combos, added, edges }
      } else throw new Unreadable(`inputClasses() inside a ${ts.SyntaxKind[p.kind]}, which the gate cannot follow to a className`)
    }
  }

  const scan: Scan = { calls: 0, sites: [], unreadable: [] }
  const visit = (n: ts.Node): void => {
    if (ts.isCallExpression(n) && isInputClasses(n.expression)) {
      scan.calls += 1
      try {
        scan.sites.push(readSite(n))
      } catch (err) {
        if (!(err instanceof Unreadable)) throw err
        scan.unreadable.push(`${file}:${lineOf(n)} ${err.message}`)
      }
    } else if (
      isInputClasses(n) &&
      !(ts.isCallExpression(n.parent) && n.parent.expression === n) &&
      !ts.isImportSpecifier(n.parent)
    ) {
      scan.unreadable.push(`${file}:${lineOf(n)} inputClasses used as a value, so its calls cannot be read`)
    }
    ts.forEachChild(n, visit)
  }
  visit(sf)
  return scan
}

// ------------------------------------------------------------------------------------------------- Tailwind

const config = createRequire(import.meta.url)(path.join(FRONTEND_ROOT, 'tailwind.config.js')) as Config
const OUTRANKING = new Set(['dark', ...Object.keys(resolveConfig(config).theme.screens as Record<string, unknown>)])
const PSEUDO_ELEMENTS = new Set(['placeholder', 'before', 'after', 'file', 'marker', 'selection', 'first-line', 'first-letter', 'backdrop'])

/** `dark:hover:!w-auto` → chain {dark, hover}, utility `w-auto`, important. A colon in brackets does not split. */
function parseClass(token: string) {
  const variants: string[] = []
  let depth = 0
  let start = 0
  for (let i = 0; i < token.length; i += 1) {
    const c = token[i]
    if (c === '[' || c === '(') depth += 1
    else if (c === ']' || c === ')') depth -= 1
    else if (c === ':' && depth === 0) {
      variants.push(token.slice(start, i))
      start = i + 1
    }
  }
  const raw = token.slice(start)
  return {
    token,
    utility: raw.replace(/^!/, ''),
    important: raw.startsWith('!'),
    arbitrary: variants.some((v) => v.includes('[')),
    target: variants.filter((v) => PSEUDO_ELEMENTS.has(v)).sort().join(':'),
    chain: new Set(variants.filter((v) => !PSEUDO_ELEMENTS.has(v))),
  }
}

/** A declaration, and whether it is Tailwind's composite plumbing: a value reading a `--tw-*` its own rule does
    not set (the box-shadow behind `shadow-*` and `ring-*`). Two plumbing declarations never compete. */
type Decl = { prop: string; value: string; plumbing: boolean }
/** What a utility declares, per element it styles: '' is the element itself, `placeholder` its ::placeholder. */
type Entry = { target: string; decls: Decl[] }
const declCache = new Map<string, Entry[] | null>()
/** Utilities Tailwind generates that style no element of the field itself (`space-x-2` styles its children). */
const stylesOthers = new Set<string>()
/** Classes that generate no CSS and only mark an element for a variant (`group-focus-within:`, `peer-invalid:`). */
const MARKER = /^(group|peer)(\/[\w-]+)?$/

const SIDES = ['top', 'right', 'bottom', 'left']
/** A shorthand competes with its longhands: `p-2` (padding) with `px-3.5` (padding-left, padding-right). */
const LONGHANDS: Record<string, string[]> = {
  padding: SIDES.map((s) => `padding-${s}`),
  margin: SIDES.map((s) => `margin-${s}`),
  inset: SIDES,
  'border-width': SIDES.map((s) => `border-${s}-width`),
  'border-style': SIDES.map((s) => `border-${s}-style`),
  'border-color': SIDES.map((s) => `border-${s}-color`),
  'border-radius': ['top-left', 'top-right', 'bottom-right', 'bottom-left'].map((c) => `border-${c}-radius`),
  outline: ['outline-color', 'outline-style', 'outline-width'],
  overflow: ['overflow-x', 'overflow-y'],
  gap: ['row-gap', 'column-gap'],
}

/** A rule's declarations as longhands. A multi-value shorthand keeps its whole value, so it differs from a longhand. */
function longhands(decls: { prop: string; value: string }[]): Decl[] {
  const own = new Set(decls.map((d) => d.prop))
  return decls.flatMap(({ prop, value }) => {
    const plumbing = !prop.startsWith('--') && [...value.matchAll(/var\((--tw-[\w-]+)/g)].some((m) => !own.has(m[1]))
    const parts = LONGHANDS[prop]
    if (!parts) return [{ prop, value, plumbing }]
    const each = /\s/.test(value) ? `${prop}(${value})` : value
    return parts.map((p) => ({ prop: p, value: each, plumbing }))
  })
}

/** Unescapes a CSS identifier: `px-3\.5` → `px-3.5`, `\2c ` → `,`. */
const unescapeCss = (s: string) =>
  s.replace(/\\([0-9a-fA-F]{1,6}) ?|\\(.)/g, (_, hex: string | undefined, ch: string | undefined) => (hex ? String.fromCodePoint(parseInt(hex, 16)) : ch!))

/** What Tailwind declares for each bare utility, read off the rules whose selector is that one class, alone or with
    a pseudo-element (`.placeholder-x::placeholder`). A utility whose rules style anything else is noted in stylesOthers. */
async function loadDeclarations(utilities: string[]): Promise<void> {
  const missing = [...new Set(utilities)].filter((u) => !declCache.has(u))
  if (!missing.length) return
  const from = path.join(FRONTEND_ROOT, 'app/globals.css')
  const css = await postcss([tailwindcss({ ...config, content: [{ raw: missing.join(' '), extension: 'html' }], safelist: [] })]).process(
    readFileSync(from, 'utf8'),
    { from },
  )
  for (const u of missing) declCache.set(u, null)
  const CLASS = /\.((?:\\[0-9a-fA-F]{1,6} ?|\\.|[\w-])+)/g
  css.root.walkRules((rule) => {
    const own = rule.parent?.type === 'root' && rule.selector.match(/^\.((?:\\[0-9a-fA-F]{1,6} ?|\\.|[\w-])+)(?:::(-(?:moz|webkit|ms)-(?:input-)?)?([\w-]+))?$/)
    if (own) {
      const name = unescapeCss(own[1])
      if (!missing.includes(name)) return
      const decls: { prop: string; value: string }[] = []
      rule.walkDecls((d) => {
        decls.push({ prop: d.prop, value: d.value.trim() })
      })
      declCache.set(name, [...(declCache.get(name) ?? []), { target: own[3] ?? '', decls: longhands(decls) }])
      return
    }
    for (const m of rule.selector.matchAll(CLASS)) {
      const name = unescapeCss(m[1])
      if (missing.includes(name)) stylesOthers.add(name)
    }
  })
}

const joinTarget = (a: string, b: string) => [a, b].filter(Boolean).sort().join(':')

/** `[padding-top,padding-bottom]`, with a full set of longhands named by its shorthand: `[border-color]`. */
function propList(props: string[]): string {
  let out = [...new Set(props)]
  for (const [short, parts] of Object.entries(LONGHANDS)) {
    if (parts.every((p) => out.includes(p))) out = [...out.filter((p) => !parts.includes(p)), short]
  }
  return `[${out.join(',')}]`
}

const sameSet = (a: Set<string>, b: Set<string>) => a.size === b.size && [...a].every((x) => b.has(x))

type Parsed = ReturnType<typeof parseClass>
/** Variant pairs that cannot hold on one element at once (a disabled control takes no focus), so rule (f) skips them. */
const EXCLUSIVE: [string, string][] = [
  ['disabled', 'enabled'], ['disabled', 'focus'], ['disabled', 'focus-visible'], ['disabled', 'focus-within'],
  ['motion-safe', 'motion-reduce'], ['portrait', 'landscape'], ['ltr', 'rtl'], ['contrast-more', 'contrast-less'],
]
const isSubset = (x: Set<string>, y: Set<string>) => [...x].every((v) => y.has(v))

/** Rule (f). Returns the union chain when the outcome there is left to variant order. */
function cooccurring(a: Parsed, aTarget: string, f: Parsed, props: string[], field: string[], added: Parsed[]): string | undefined {
  if (isSubset(a.chain, f.chain) || isSubset(f.chain, a.chain)) return undefined
  if (EXCLUSIVE.some(([x, y]) => (a.chain.has(x) && f.chain.has(y)) || (a.chain.has(y) && f.chain.has(x)))) return undefined
  const fieldParsed = field.map(parseClass)
  const setsHere = (t: Parsed) =>
    (declCache.get(t.utility) ?? []).filter((e) => joinTarget(t.target, e.target) === aTarget).flatMap((e) => e.decls).filter((d) => props.includes(d.prop))
  // A chain the field styles itself: a differing class there is rule (a)'s finding, an equal one changes nothing.
  if (fieldParsed.some((g) => sameSet(g.chain, a.chain) && setsHere(g).length)) return undefined
  const union = new Set([...a.chain, ...f.chain])
  const holders = [...fieldParsed, ...added]
    .filter((t) => !t.arbitrary && isSubset(t.chain, union))
    .map((t) => ({ chain: t.chain, decls: setsHere(t).filter((d) => !d.plumbing) }))
    .filter((t) => t.decls.length)
  for (const prop of props) {
    const setting = holders.filter((h) => h.decls.some((d) => d.prop === prop))
    const maximal = setting.filter((h) => !setting.some((o) => o.chain.size > h.chain.size && isSubset(h.chain, o.chain)))
    if (new Set(maximal.flatMap((h) => h.decls.filter((d) => d.prop === prop).map((d) => d.value))).size > 1) return [...union].sort().join('+')
  }
  return undefined
}

function competing(field: string[], added: string[]): string[] {
  const out = new Set<string>()
  /** (f), one per added class and union state, naming the field class with the longest chain there. */
  const unionFindings = new Map<string, { size: number; text: string }>()
  const parsedAdded = added.map(parseClass)
  for (const a of parsedAdded) {
    if (a.important) out.add(`${a.token} (important)`)
    if (a.arbitrary) {
      out.add(`${a.token} (arbitrary variant)`)
      continue
    }
    const aEntries = declCache.get(a.utility)
    if (!aEntries) {
      if (!MARKER.test(a.utility) && !stylesOthers.has(a.utility)) out.add(`${a.token} (not a class Tailwind generates)`)
      continue
    }
    for (const ae of aEntries) {
      const aTarget = joinTarget(a.target, ae.target)
      for (const f of field.map(parseClass)) {
        for (const fe of declCache.get(f.utility) ?? []) {
          if (joinTarget(f.target, fe.target) !== aTarget) continue
          const props = fe.decls
            .filter((d) => ae.decls.some((x) => x.prop === d.prop && x.value !== d.value && !(x.plumbing && d.plumbing)))
            .map((d) => d.prop)
          if (!props.length) continue
          const list = propList(props)
          if (sameSet(a.chain, f.chain)) {
            out.add(`${a.token} vs ${f.token} ${list} (same chain)`)
            continue
          }
          const lacking = [...f.chain].filter((v) => OUTRANKING.has(v) && !a.chain.has(v))
          const rest = [...f.chain].filter((v) => !OUTRANKING.has(v))
          if (!lacking.length || !rest.every((v) => a.chain.has(v))) {
            // (f) owns the pairs in one theme and screen; a field chain under a dark/screen variant `a` lacks is (b)'s.
            const union = lacking.length ? undefined : cooccurring(a, aTarget, f, props, field, parsedAdded)
            if (union) {
              const key = `${a.token} ${union}`
              const held = unionFindings.get(key)
              if (!held || f.chain.size > held.size) unionFindings.set(key, { size: f.chain.size, text: `${a.token} vs ${f.token} ${list} (no ${union} twin)` })
            }
            continue
          }
          const want = new Set([...a.chain, ...lacking])
          const twin = parsedAdded.some((t) =>
            sameSet(t.chain, want) &&
            (declCache.get(t.utility) ?? []).some((te) => joinTarget(t.target, te.target) === aTarget && te.decls.some((d) => props.includes(d.prop))),
          )
          if (!twin) out.add(`${a.token} vs ${f.token} ${list} (no ${lacking.join('+')} twin)`)
        }
      }
    }
  }
  for (const { text } of unionFindings.values()) out.add(text)
  return [...out]
}

/** Every finding of a scan as `file:line finding`, sorted. */
async function check(scan: Scan): Promise<{ file: string; line: number; finding: string }[]> {
  const fieldOf = (o: Options) => inputClasses(o as InputClassesOptions).split(/\s+/)
  const utilities = scan.sites.flatMap((s) => [...s.added, ...s.combos.flatMap(fieldOf)]).map((t) => parseClass(t).utility)
  await loadDeclarations(utilities)
  const out: { file: string; line: number; finding: string }[] = []
  for (const site of scan.sites) {
    const found = new Set<string>()
    for (const combo of site.combos) {
      for (const f of competing(fieldOf(combo), site.added)) found.add(f)
      // The forms plugin draws no chevron on a list box (`multiple`, or `size` over 1), so the rule skips it.
      if (site.tag === 'select' && !site.listBox && !combo.select) {
        found.add("a <select> without select: true (PAD's 14px right inset leaves the chevron no room)")
      }
      if (site.tag !== 'select' && combo.select) found.add(`select: true on a <${site.tag}>`)
    }
    // An inset that follows its control's condition moves under the caret, so every combination must reserve it.
    for (const edge of site.edges) {
      const reserved = site.combos.every((c) => (edge.side === 'right' ? c.select || c.trailingIcon : c.leadingIcon && !c.select))
      const option = edge.side === 'right' ? 'trailingIcon' : 'leadingIcon'
      if (!reserved) found.add(`a <${edge.tag}> at the field's ${edge.side} edge (${edge.anchor}) without ${option}: true`)
    }
    for (const finding of [...found].sort()) out.push({ file: site.file, line: site.line, finding })
  }
  return out
}

/** The findings of one in-memory source, unreadable positions included, without file or line. */
async function findingsOf(source: string, file = 'features/fixture/Fixture.tsx'): Promise<string[]> {
  const scan = scanSource(file, source)
  const found = await check(scan)
  return [...scan.unreadable.map((u) => u.replace(/^\S+ /, 'unreadable: ')), ...found.map((f) => f.finding)]
}

// ------------------------------------------------------------------------------------------------- the gate

function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const p = path.join(dir, name)
    if (statSync(p).isDirectory()) sourceFiles(p, out)
    else if (/\.tsx?$/.test(name) && !name.endsWith('.d.ts')) out.push(p)
  }
  return out
}

let appScan: (Scan & { files: number }) | undefined

/** The app's scan, read once for both tests. */
function scanApp(): Scan & { files: number } {
  if (appScan) return appScan
  const total: Scan & { files: number } = { calls: 0, sites: [], unreadable: [], files: 0 }
  for (const root of ROOTS) {
    // A missing root throws: a rename must update the gate, not shrink what it covers.
    for (const abs of sourceFiles(path.join(FRONTEND_ROOT, root))) {
      const rel = path.relative(FRONTEND_ROOT, abs).split(path.sep).join('/')
      if (rel === DEFINITION) continue
      const scan = scanSource(rel, readFileSync(abs, 'utf8'))
      total.files += 1
      total.calls += scan.calls
      total.sites.push(...scan.sites)
      total.unreadable.push(...scan.unreadable)
    }
  }
  appScan = total
  return total
}

/** A first Tailwind compile plus the tree scan takes 1-2s here and longer on a loaded runner; 5s is too tight. */
const SLOW = { timeout: 30_000 }

describe('a raw field takes inputClasses() options, never a competing class on top', SLOW, () => {
  it('no class combined with inputClasses() competes with the field’s own', async () => {
    const scan = scanApp()
    expect(scan.unreadable, 'inputClasses() where the gate cannot read what it is combined with').toEqual([])
    const { unpinned, stale } = againstPins(await check(scan), PINS)
    expect(
      unpinned,
      'A class on top of inputClasses() that sets what the field sets resolves by stylesheet order, not class ' +
        'order (cx and clsx do no tailwind-merge). Use an option (select, autoWidth, density, leadingIcon, trailingIcon, invalid, tone, shell) ' +
        'or add one to components/ui/Input.tsx with explicit sides.',
    ).toEqual([])
    expect(stale, 'pins that no longer match a finding: remove them').toEqual([])
    expect(Object.keys(PINS).length).toBeLessThanOrEqual(MAX_PINNED.files)
    expect(Object.values(PINS).flatMap((p) => p.findings).length).toBeLessThanOrEqual(MAX_PINNED.findings)
  })

  it('reads the app (a rename cannot leave it scanning nothing)', () => {
    const scan = scanApp()
    expect(scan.files).toBeGreaterThan(100)
    expect(scan.calls).toBeGreaterThanOrEqual(10)
    // The controls drawn at a field's edge today: three search fields' glyphs and spinners, CompanySearch's "/" hint,
    // the password reveal toggle and the feedback row's pending spinner over its select. Fewer means the walk broke.
    expect(scan.sites.flatMap((site) => site.edges).length).toBeGreaterThanOrEqual(9)
  })
})

// ------------------------------------------------------------------------------------------------- the scanner

const IMPORTS = `import { clsx } from 'clsx'\nimport { fieldUnavailableClass, inputClasses } from '@/components/ui/Input'\n`
const NO_CHEVRON_ROOM = "a <select> without select: true (PAD's 14px right inset leaves the chevron no room)"

describe('the scanner', SLOW, () => {
  it('fails each override main abda78ce shipped, verbatim', async () => {
    expect(await findingsOf(`${IMPORTS}export const D = () => <select className={clsx(inputClasses(), 'w-auto py-1.5 text-sm', fieldUnavailableClass)} />`)).toEqual([
      NO_CHEVRON_ROOM,
      'py-1.5 vs py-2.5 [padding-top,padding-bottom] (same chain)',
      'w-auto vs w-full [width] (same chain)',
    ])
    expect(await findingsOf(`${IMPORTS}export const F = () => <select className={\`\${inputClasses()} w-auto py-1.5 pr-8 text-xs \${fieldUnavailableClass}\`} />`)).toEqual([
      NO_CHEVRON_ROOM,
      'pr-8 vs px-3.5 [padding-right] (same chain)',
      'py-1.5 vs py-2.5 [padding-top,padding-bottom] (same chain)',
      'text-xs vs text-sm [font-size,line-height] (same chain)',
      'w-auto vs w-full [width] (same chain)',
    ])
    expect(await findingsOf(`${IMPORTS}export const A = () => <select className={\`\${inputClasses()} w-auto\`} />`)).toEqual([
      NO_CHEVRON_ROOM,
      'w-auto vs w-full [width] (same chain)',
    ])
  })

  it('passes the options that replace them', async () => {
    expect(await findingsOf(`${IMPORTS}export const D = () => <select className={clsx(inputClasses({ select: true, autoWidth: true }), fieldUnavailableClass)} />`)).toEqual([])
    expect(
      await findingsOf(`${IMPORTS}export const F = () => <select className={\`\${inputClasses({ select: true, density: 'compact', autoWidth: true })} \${fieldUnavailableClass}\`} />`),
    ).toEqual([])
    // The password field's `pr-10` on top, and a trailing control beside a leading icon (a flag read both ways).
    expect(await findingsOf(`${IMPORTS}export const P = () => <input className={inputClasses({ trailingIcon: true })} />`)).toEqual([])
    expect(
      await findingsOf(`${IMPORTS}export const Q = ({ busy }: { busy: boolean }) => <input className={inputClasses({ leadingIcon: true, trailingIcon: busy, density: 'compact' })} />`),
    ).toEqual([])
  })

  it('reads a className option, nested joiners, conditions, object keys, arrays and a same-file const', async () => {
    expect(await findingsOf(`${IMPORTS}export const P = () => <input className={inputClasses({ className: 'pr-10' })} />`)).toEqual([
      'pr-10 vs px-3.5 [padding-right] (same chain)',
    ])
    const source = `${IMPORTS}import { cx } from '@/components/ui'
const WIDE = 'w-auto'
export const C = ({ on }: { on: boolean }) => (
  <input className={cx(cx(inputClasses(), on ? 'mt-2' : 'text-xs'), clsx({ 'py-1.5': on }, ['resize-y', WIDE]))} />
)`
    expect(await findingsOf(source)).toEqual([
      'py-1.5 vs py-2.5 [padding-top,padding-bottom] (same chain)',
      'text-xs vs text-sm [font-size,line-height] (same chain)',
      'w-auto vs w-full [width] (same chain)',
    ])
  })

  it('follows an alias, the barrel and a relative import', async () => {
    expect(await findingsOf(`import { inputClasses as field, cx } from '@/components/ui'\nexport const B = () => <input className={cx(field(), 'w-auto')} />`)).toEqual([
      'w-auto vs w-full [width] (same chain)',
    ])
    expect(
      await findingsOf(`import { inputClasses } from '../../components/ui/Input'\nexport const R = () => <input className={\`\${inputClasses()} w-auto\`} />`, 'features/x/R.tsx'),
    ).toEqual(['w-auto vs w-full [width] (same chain)'])
  })

  it('fails a state colour with no dark twin, and passes one that has it', async () => {
    expect(await findingsOf(`${IMPORTS}export const X = () => <input className={inputClasses({ className: 'focus:border-error-light focus:shadow-ring-error' })} />`)).toEqual(
      [
        'focus:border-error-light vs dark:border-border-dark [border-color] (no dark twin)',
        'focus:border-error-light vs dark:focus:border-brand-dark [border-color] (no dark twin)',
        'focus:border-error-light vs focus:border-brand [border-color] (same chain)',
        'focus:shadow-ring-error vs dark:focus:shadow-ring-brand-dark [--tw-shadow] (no dark twin)',
        'focus:shadow-ring-error vs focus:shadow-ring-brand [--tw-shadow] (same chain)',
      ],
    )
    // A focus-within layer on a shell (the chat composer's before `shell`) in light alone: each class wants its dark twin.
    const lightOnly = `import { cx, inputClasses } from '@/components/ui'
export const S = () => <div className={cx(inputClasses({ className: 'flex items-end gap-2' }), 'focus-within:border-brand hover:focus-within:border-brand focus-within:shadow-ring-brand')} />`
    expect(await findingsOf(lightOnly)).toEqual([
      'focus-within:border-brand vs dark:border-border-dark [border-color] (no dark twin)',
      'hover:focus-within:border-brand vs dark:border-border-dark [border-color] (no dark twin)',
      'hover:focus-within:border-brand vs dark:hover:border-flat-dark [border-color] (no dark twin)',
    ])
  })

  it('fails two chains that hold at once when variant order, not the state, picks the winner (rule f)', async () => {
    const shell = (classes: string) =>
      findingsOf(`import { cx, inputClasses } from '@/components/ui'\nexport const S = () => <div className={cx(inputClasses({ className: 'flex items-end gap-2' }), '${classes}')} />`)
    const RECIPE = 'focus-within:border-brand focus-within:shadow-ring-brand dark:focus-within:border-brand-dark dark:focus-within:shadow-ring-brand-dark'
    // The composer shell on main: Tailwind emits focus-within before hover, so the field's hover border won while both held.
    expect(await shell(RECIPE)).toEqual([
      'dark:focus-within:border-brand-dark vs dark:hover:border-flat-dark [border-color] (no dark+focus-within+hover twin)',
      'focus-within:border-brand vs hover:border-flat-light [border-color] (no focus-within+hover twin)',
    ])
    expect(await shell(`${RECIPE} hover:focus-within:border-brand dark:hover:focus-within:border-brand-dark`)).toEqual([])
    // The light twin alone: rule (b) asks for its dark twin, and (f) still sees the dark layer lose to dark:hover.
    expect(await shell(`${RECIPE} hover:focus-within:border-brand`)).toEqual([
      'dark:focus-within:border-brand-dark vs dark:hover:border-flat-dark [border-color] (no dark+focus-within+hover twin)',
      'hover:focus-within:border-brand vs dark:border-border-dark [border-color] (no dark twin)',
      'hover:focus-within:border-brand vs dark:hover:border-flat-dark [border-color] (no dark twin)',
    ])
    // A chain the field styles itself is rule (a)'s, not (f)'s: the delete-account pin gains nothing.
    expect(await shell('focus:border-error-light dark:focus:border-error-dark')).toEqual(['focus:border-error-light vs focus:border-brand [border-color] (same chain)', 'dark:focus:border-error-dark vs dark:focus:border-brand-dark [border-color] (same chain)'].sort())
    // Chains that cannot hold at once (a disabled control takes no focus) pass; an aria-disabled one can be disabled too.
    expect(await shell('focus-within:cursor-text')).toEqual([])
    expect(await shell('aria-disabled:cursor-text')).toEqual(['aria-disabled:cursor-text vs disabled:cursor-not-allowed [cursor] (no aria-disabled+disabled twin)'])
    // The field wins by count, not by order: `aria-disabled:hover:` (0,3,0) over `focus:border-brand` (0,2,0).
    expect(await shell('aria-disabled:hover:border-border-light dark:aria-disabled:hover:border-border-dark')).toEqual([
      'aria-disabled:hover:border-border-light vs focus:border-brand [border-color] (no aria-disabled+focus+hover twin)',
      'dark:aria-disabled:hover:border-border-dark vs dark:focus:border-brand-dark [border-color] (no aria-disabled+dark+focus+hover twin)',
    ])
    expect(
      await shell('aria-disabled:hover:border-border-light dark:aria-disabled:hover:border-border-dark aria-disabled:hover:focus:border-brand dark:aria-disabled:hover:focus:border-brand-dark'),
    ).toEqual([])
    // A state layer over the field's own chain passes, as before.
    expect(await shell('aria-disabled:bg-background-light dark:aria-disabled:bg-white/5')).toEqual([])
    expect(await findingsOf(`import { inputClasses } from '@/components/ui'\nexport const S = () => <div className={inputClasses({ shell: true, className: 'flex items-end gap-2' })} />`)).toEqual([])
  })

  it("passes #1178's ink-fade fieldUnavailableClass, and fails it without its dark twins", async () => {
    const fade =
      'aria-disabled:cursor-not-allowed aria-disabled:bg-background-light aria-disabled:text-text-primary-light/60 aria-disabled:hover:border-border-light ' +
      'dark:aria-disabled:bg-white/5 dark:aria-disabled:text-text-primary-dark/60 dark:aria-disabled:hover:border-border-dark ' +
      'aria-disabled:hover:focus:border-brand dark:aria-disabled:hover:focus:border-brand-dark'
    const site = (classes: string) => `${IMPORTS}const FADE = '${classes}'\nexport const U = () => <select className={clsx(inputClasses({ select: true, autoWidth: true }), FADE)} />`
    expect(await findingsOf(site(fade))).toEqual([])
    expect(await findingsOf(site(fade.replace(/ dark:aria-disabled:\S+/g, '')))).toEqual([
      'aria-disabled:bg-background-light vs dark:bg-white/5 [background-color] (no dark twin)',
      'aria-disabled:hover:border-border-light vs dark:border-border-dark [border-color] (no dark twin)',
      'aria-disabled:hover:border-border-light vs dark:hover:border-flat-dark [border-color] (no dark twin)',
      'aria-disabled:hover:focus:border-brand vs dark:border-border-dark [border-color] (no dark twin)',
      'aria-disabled:hover:focus:border-brand vs dark:focus:border-brand-dark [border-color] (no dark twin)',
      'aria-disabled:hover:focus:border-brand vs dark:hover:border-flat-dark [border-color] (no dark twin)',
      'aria-disabled:text-text-primary-light/60 vs dark:text-text-primary-dark [color] (no dark twin)',
    ])
  })

  it('fails a screen the field outranks it under, !important, an opacity, and an arbitrary variant', async () => {
    const at = (options: string, classes: string) => findingsOf(`${IMPORTS}export const T = () => <input className={inputClasses({ ${options}className: '${classes}' })} />`)
    expect(await at("density: 'compact', ", 'h-10')).toEqual(['h-10 vs sm:h-9 [height] (no sm twin)'])
    // The twin competes in the field's own chain: a density's height is the field's to set, through an option.
    expect(await at("density: 'compact', ", 'h-10 sm:h-10')).toEqual(['sm:h-10 vs sm:h-9 [height] (same chain)'])
    expect(await at('', '!w-auto')).toEqual(['!w-auto (important)', '!w-auto vs w-full [width] (same chain)'])
    expect(await at('', 'bg-opacity-50')).toEqual(['bg-opacity-50 vs bg-white [--tw-bg-opacity] (same chain)'])
    expect(await at('', '[&>option]:text-xs')).toEqual(['[&>option]:text-xs (arbitrary variant)'])
    // DESIGN_SYSTEM's own advice for a forms-plugin field: the ring and the shadow are different values.
    expect(await at('', 'focus:ring-0 focus:ring-offset-0')).toEqual([])
  })

  it('holds every <select> to the chevron padding, and `select` to a <select>', async () => {
    expect(await findingsOf(`${IMPORTS}export const S = () => <select className={inputClasses()} />`)).toEqual([NO_CHEVRON_ROOM])
    expect(await findingsOf(`${IMPORTS}export const S = () => <select className={inputClasses({ autoWidth: true })} />`)).toEqual([NO_CHEVRON_ROOM])
    expect(await findingsOf(`${IMPORTS}export const S = () => <select className={inputClasses({ select: true })} />`)).toEqual([])
    // A list box draws no chevron, so it is held to neither rule; `size={1}` and `multiple={false}` are dropdowns.
    expect(await findingsOf(`${IMPORTS}export const M = () => <select multiple className={inputClasses()} />`)).toEqual([])
    expect(await findingsOf(`${IMPORTS}export const M = () => <select size={4} className={inputClasses()} />`)).toEqual([])
    expect(await findingsOf(`${IMPORTS}export const M = () => <select size={1} className={inputClasses()} />`)).toEqual([NO_CHEVRON_ROOM])
    expect(await findingsOf(`${IMPORTS}export const M = () => <select multiple={false} className={inputClasses()} />`)).toEqual([NO_CHEVRON_ROOM])
    expect(await findingsOf(`${IMPORTS}export const M = ({ n }: { n: number }) => <select size={n} className={inputClasses()} />`)).toEqual([
      NO_CHEVRON_ROOM,
    ])
    expect(await findingsOf(`${IMPORTS}export const I = () => <input className={inputClasses({ select: true })} />`)).toEqual([
      'select: true on a <input>',
    ])
    // A flag it cannot read is checked both ways.
    expect(await findingsOf(`${IMPORTS}export const S = ({ on }: { on: boolean }) => <select className={inputClasses({ select: on })} />`)).toEqual([
      NO_CHEVRON_ROOM,
    ])
  })

  it('holds a control drawn at the field’s edge to that inset, reserved always', async () => {
    const beside = (options: string, sibling: string, extra = '') =>
      findingsOf(
        `import { FieldSpinner, inputClasses } from '@/components/ui'\n${extra}export const F = ({ busy }: { busy: boolean }) => (\n` +
          `  <div className="relative">\n    <input className={inputClasses({ ${options} })} />\n    ${sibling}\n  </div>\n)`,
      )
    // The search fields on main: a 20px spinner at right-4 over the 14px inset.
    const spinner = `{busy && <CircleNotchIcon className="absolute right-4 top-1/2 h-5 w-5 -translate-y-1/2 animate-spin" />}`
    expect(await beside('leadingIcon: true', spinner)).toEqual(["a <CircleNotchIcon> at the field's right edge (right-4) without trailingIcon: true"])
    // An inset that follows the control's condition is still a finding: it moves under the caret.
    expect(await beside('leadingIcon: true, trailingIcon: busy', spinner)).toEqual([
      "a <CircleNotchIcon> at the field's right edge (right-4) without trailingIcon: true",
    ])
    expect(await beside('leadingIcon: true, trailingIcon: true', spinner)).toEqual([])
    expect(await beside('leadingIcon: true', '{busy && <FieldSpinner />}')).toEqual([
      "a <FieldSpinner> at the field's right edge (absolute right-3) without trailingIcon: true",
    ])
    expect(await beside('leadingIcon: true, trailingIcon: true', '{busy && <FieldSpinner />}')).toEqual([])
    // The reveal toggle: `inset-y-0` anchors it vertically only.
    const reveal = '<button type="button" className="absolute inset-y-0 right-0 flex items-center pr-3" />'
    expect(await beside('', reveal)).toEqual(["a <button> at the field's right edge (right-0) without trailingIcon: true"])
    expect(await beside('trailingIcon: true', reveal)).toEqual([])
    // The leading glyph, and a select's chevron inset under the admin feedback row's pending spinner.
    const glyph = '<MagnifyingGlassIcon className="pointer-events-none absolute left-3.5 top-1/2 h-5 w-5 -translate-y-1/2" />'
    expect(await beside('', glyph)).toEqual(["a <MagnifyingGlassIcon> at the field's left edge (left-3.5) without leadingIcon: true"])
    expect(await beside('leadingIcon: true, trailingIcon: true', glyph)).toEqual([])
    expect(
      await findingsOf(
        `${IMPORTS}export const S = ({ busy }: { busy: boolean }) => <div className="relative"><select className={inputClasses({ select: true })} />{busy ? <CircleNotchIcon className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5" /> : null}</div>`,
      ),
    ).toEqual([])
    // Not at an edge of the field: no horizontal anchor, a popover below it, a relative sibling, another field.
    for (const other of [
      '<ul className="absolute z-10 mt-2 w-full rounded-xl" />',
      '<ul className="absolute left-0 right-0 top-full mt-2" />',
      '<p className="relative mt-1 text-xs">hint</p>',
      '<select className={inputClasses({ select: true, autoWidth: true })} />',
    ]) {
      expect(await beside('', other), other).toEqual([])
    }
    // Fails closed: an overlay on both edges, and siblings it cannot enumerate or read.
    const unreadable = async (sibling: string, extra = '') => (await beside('', sibling, extra)).map((f) => f.replace(/ \(.*$/, ''))
    expect(await unreadable('<span className="absolute inset-0" />')).toEqual(['unreadable: a <span> beside the field anchored to both of its edges'])
    expect(await unreadable('{children}', 'declare const children: React.ReactNode\n')).toEqual([
      'unreadable: a sibling of the field the gate cannot read',
    ])
    expect(await unreadable('{[1, 2].map((n) => <i key={n} />)}')).toEqual(['unreadable: a sibling of the field the gate cannot read'])
    expect(await unreadable('<i className={tone} />', 'declare const tone: string\n')).toEqual([
      'unreadable: a class from `tone`, which is not a const with an initializer',
    ])
  })

  it('compares a shorthand with its longhands, and a raw box-shadow with the ring', async () => {
    const at = (classes: string) => findingsOf(`${IMPORTS}export const T = () => <input className={inputClasses({ className: '${classes}' })} />`)
    expect(await at('p-2')).toEqual([
      'p-2 vs px-3.5 [padding-left,padding-right] (same chain)',
      'p-2 vs py-2.5 [padding-top,padding-bottom] (same chain)',
    ])
    expect(await at('rounded-r-none')).toEqual(['rounded-r-none vs rounded-lg [border-top-right-radius,border-bottom-right-radius] (same chain)'])
    expect(await at('border-b-0')).toEqual(['border-b-0 vs border [border-bottom-width] (same chain)'])
    expect(await at('focus:[box-shadow:none] dark:focus:[box-shadow:none]')).toEqual([
      'dark:focus:[box-shadow:none] vs dark:focus:shadow-ring-brand-dark [box-shadow] (same chain)',
      'focus:[box-shadow:none] vs focus:ring-0 [box-shadow] (same chain)',
      'focus:[box-shadow:none] vs focus:shadow-ring-brand [box-shadow] (same chain)',
    ])
    // A placeholder colour utility styles the ::placeholder the field's `placeholder:` class styles.
    expect(await at('placeholder-text-secondary-light')).toEqual([
      'placeholder-text-secondary-light vs dark:placeholder:text-text-secondary-dark [color] (no dark twin)',
      'placeholder-text-secondary-light vs placeholder:text-text-tertiary-light [color] (same chain)',
    ])
  })

  it('passes a marker or a utility that styles only other elements, and fails a token Tailwind does not know', async () => {
    const at = (classes: string) => findingsOf(`${IMPORTS}export const T = () => <div className={inputClasses({ className: '${classes}' })} />`)
    expect(await at('group peer group/field space-x-2 divide-x')).toEqual([])
    expect(await at('w-autoo')).toEqual(['w-autoo (not a class Tailwind generates)'])
  })

  it('pins one site per entry: a second site with a pinned finding fails, and an unmatched pin is stale', () => {
    const pins = { 'a.tsx': { findings: ['x'], reason: '' } }
    expect(againstPins([{ file: 'a.tsx', line: 3, finding: 'x' }], pins)).toEqual({ unpinned: [], stale: [] })
    expect(
      againstPins([{ file: 'a.tsx', line: 3, finding: 'x' }, { file: 'a.tsx', line: 9, finding: 'x' }], pins),
    ).toEqual({ unpinned: ['a.tsx:9 x'], stale: [] })
    expect(againstPins([], pins)).toEqual({ unpinned: [], stale: ['a.tsx: x'] })
  })

  it('fails closed on every position it cannot follow to a className', async () => {
    const unreadable = async (body: string) => (await findingsOf(`${IMPORTS}${body}`)).map((f) => f.replace(/^unreadable: /, '').replace(/(,| \().*$/, ''))
    expect(await unreadable('const c = inputClasses()\nexport const V = () => <input className={c} />')).toEqual(['inputClasses() inside a VariableDeclaration'])
    expect(await unreadable('export function h() { return inputClasses() }')).toEqual(['inputClasses() inside a ReturnStatement'])
    expect(await unreadable("export const J = () => <input className={inputClasses() + ' w-auto'} />")).toEqual(['inputClasses() inside a BinaryExpression'])
    expect(await unreadable('declare const wrap: (s: string) => string\nexport const W = () => <input className={wrap(inputClasses())} />')).toEqual([
      'inputClasses() inside a CallExpression',
    ])
    expect(await unreadable('export const O = () => <input {...{ className: inputClasses() }} />')).toEqual(['inputClasses() inside a PropertyAssignment'])
    expect(await unreadable('export const K = ({ className }: { className: string }) => <input className={clsx(inputClasses(), className)} />')).toEqual([
      'a class from `className`',
    ])
    expect(await unreadable('declare const o: object\nexport const Q = () => <input className={inputClasses({ ...o })} />')).toEqual([
      'an inputClasses() option the gate cannot read',
    ])
    expect(await unreadable('declare const tone: string\nexport const G = () => <input className={`${inputClasses()} text-${tone}`} />')).toEqual([
      'a class built from pieces of a template',
    ])
    // No space between two expressions glues the field's last class to the next one's first.
    expect(await unreadable('export const H = () => <input className={`${inputClasses()}${fieldUnavailableClass}`} />')).toEqual([
      'a class built from pieces of a template',
    ])
    expect(await unreadable('export const f = inputClasses')).toEqual(['inputClasses used as a value'])
  })
})

/** Every combination of the options, built from the gate's own lists so a new flag joins it unasked. */
const ALL: Options[] = BOOLEAN_OPTIONS.reduce<Options[]>(
  (combos, k) => combos.flatMap((c) => [{ ...c, [k]: false }, { ...c, [k]: true }]),
  DENSITIES.flatMap((density) => FIELD_TONES.map((tone) => ({ ...DEFAULTS, density, tone }))),
)

// ------------------------------------------------------------------------------------------------- width

describe("the field's width is explicit", () => {
  it('inputClasses() fills its container unless autoWidth, which caps it instead', () => {
    expect(inputClasses().split(' ')).toContain('w-full')
    expect(inputClasses({ select: true }).split(' ')).toContain('w-full')
    const auto = inputClasses({ select: true, autoWidth: true }).split(' ')
    expect(auto).not.toContain('w-full')
    expect(auto).toContain('max-w-full')
  })

  it('the Input, Textarea and Select components still fill their Shell', () => {
    const { container } = render(
      <>
        <Input aria-label="a" />
        <Textarea aria-label="b" />
        <Select aria-label="c">
          <option>x</option>
        </Select>
      </>,
    )
    for (const tag of ['input', 'textarea', 'select']) expect(container.querySelector(tag)?.classList.contains('w-full'), tag).toBe(true)
  })
})

// ------------------------------------------------------------------------------------------------- padding

describe("the field's padding is explicit", () => {
  const SIDES_OF: Record<string, string[]> = { p: ['t', 'r', 'b', 'l'], px: ['r', 'l'], py: ['t', 'b'], pt: ['t'], pr: ['r'], pb: ['b'], pl: ['l'] }
  /** Each side a combination's padding classes set: its screen (`sm:`, or '' for none), the side, the class. */
  const padding = (o: Options) =>
    inputClasses(o as InputClassesOptions)
      .split(' ')
      .flatMap((token) => {
        const m = token.match(/^((?:[\w-]+:)*)(p[xytrbl]?)-\S+$/)
        return m ? SIDES_OF[m[2]].map((side) => ({ screen: m[1], side, token })) : []
      })
  /** One side's padding on every screen, by spacing step in class order: `['3.5', 'sm:3']` is 14px, then 12px from sm. */
  const steps = (o: Options, side: string) => padding(o).filter((p) => p.side === side).map((p) => p.token.replace(/p[xytrbl]?-/, ''))

  it('sets each side once per screen, for every combination of the options', () => {
    for (const o of ALL) {
      const seen = new Map<string, string>()
      for (const { screen, side, token } of padding(o)) {
        const key = `${screen}${side}`
        expect(seen.get(key), `${JSON.stringify(o)}: ${token} sets the same side as ${seen.get(key)}`).toBeUndefined()
        seen.set(key, token)
      }
    }
  })

  it('gives every combination its documented box on every screen', () => {
    expect(ALL.filter((o) => o.trailingIcon && !o.select).length, 'trailingIcon is one of BOOLEAN_OPTIONS').toBeGreaterThan(0)
    for (const o of ALL) {
      const compact = o.density === 'compact'
      // A field's edge is 14px, and 12px from sm up when compact. A select's chevron keeps 36px and a trailing
      // control 40px at both densities (neither moves), so a copied `sm:px-3` would put the reveal toggle over text.
      const edge = compact ? ['3.5', 'sm:3'] : ['3.5']
      const vertical = compact ? ['2.5', 'sm:1.5'] : ['2.5']
      expect(
        {
          left: steps(o, 'l'),
          right: steps(o, 'r'),
          top: steps(o, 't'),
          bottom: steps(o, 'b'),
          height: inputClasses(o as InputClassesOptions).split(' ').filter((c) => /^((?:[\w-]+:)*)h-/.test(c)),
        },
        JSON.stringify(o),
      ).toEqual({
        left: o.leadingIcon && !o.select ? (compact ? ['11', 'sm:10'] : ['11']) : edge,
        right: o.select ? ['9'] : o.trailingIcon ? ['10'] : edge,
        top: vertical,
        bottom: vertical,
        height: compact ? ['sm:h-9'] : [],
      })
    }
  })
  it('the Input component reserves its trailing inset whenever it takes `loading`, and FieldSpinner fits that inset', () => {
    const { container } = render(
      <>
        <Input aria-label="plain" />
        <Input aria-label="idle" loading={false} />
        <Input aria-label="busy" loading />
      </>,
    )
    const [plain, idle, busy] = [...container.querySelectorAll('input')].map((el) => el.classList)
    expect(plain.contains('pr-3.5')).toBe(true)
    // The padding never moves under the caret when the lookup starts or ends.
    expect(idle.contains('pr-10') && busy.contains('pr-10')).toBe(true)
    // The gate reads <FieldSpinner /> as a control at the right edge: its classes must keep it inside the inset.
    const spinner = render(<FieldSpinner />).container.querySelector('svg')!.classList
    for (const c of ['absolute', 'right-3', 'h-4', 'w-4']) expect(spinner.contains(c), c).toBe(true)
  })
})

// ------------------------------------------------------------------------------------------------- height

describe("the field's height is the documented one", SLOW, () => {
  /** DESIGN.md's frontmatter height for a component, in rem. Read inside the test, so a missing key fails it by name. */
  const documentedHeight = (key: string) => {
    const md = readFileSync(path.join(FRONTEND_ROOT, '../DESIGN.md'), 'utf8').replace(/\r\n/g, '\n')
    const frontmatter = `${md.match(/^---\n([\s\S]*?)\n---\n/)?.[1] ?? ''}\n`
    const block = frontmatter.match(new RegExp(`^  ${key}:\\n((?: {4}.+\\n)+)`, 'm'))?.[1] ?? ''
    const rem = block.match(/^ {4}height: "([\d.]+)rem"$/m)?.[1]
    if (!rem) throw new Error(`DESIGN.md's components.${key} has no height in rem`)
    return Number(rem)
  }
  /** The terms a single-line field states itself; one left to the forms plugin fails rather than reading 0. */
  const BOX = ['border-top-width', 'padding-top', 'line-height', 'padding-bottom', 'border-bottom-width']
  /** A single-line field's border-box height (preflight makes every field border-box) on one screen, '' below sm
      and 'sm' from 640px, at a root font size: what Tailwind declares for its classes in the plain state, an `sm:`
      class replacing a bare one as its rule follows it in the stylesheet. An explicit height, else the borders,
      vertical padding and line, held up by the min-height. */
  const fieldHeight = (classes: string[], screen: '' | 'sm', root: number) => {
    const set = new Map<string, string>()
    for (const chain of screen ? ['', screen] : ['']) {
      for (const c of classes.map(parseClass)) {
        if (c.target || [...c.chain].join(':') !== chain) continue
        for (const e of declCache.get(c.utility) ?? []) if (!e.target) for (const d of e.decls) set.set(d.prop, d.value)
      }
    }
    const px = (prop: string) => {
      const value = set.get(prop)
      if (value === undefined) throw new Error(`${prop} is left to the forms plugin: ${classes.join(' ')}`)
      return value.endsWith('rem') ? parseFloat(value) * root : parseFloat(value)
    }
    const natural = BOX.reduce((sum, prop) => sum + px(prop), 0)
    return Math.max(set.has('min-height') ? px('min-height') : 0, set.has('height') ? px('height') : natural)
  }

  it("every single-line field is DESIGN.md's input height on every screen, and a compact one input-compact's from sm, in rem", async () => {
    const input = documentedHeight('input')
    const compactSm = documentedHeight('input-compact')
    expect(documentedHeight('input-search'), 'a search field is a comfortable field').toBe(input)
    const { container } = render(
      <>
        <Input aria-label="Input" />
        <Input aria-label="Input icon loading" icon="i" loading />
        <Select aria-label="Select">
          <option>x</option>
        </Select>
        <Select aria-label="Select compact" density="compact">
          <option>x</option>
        </Select>
      </>,
    )
    // A shell takes its content's height (the composer's is 54px) and a textarea its rows', so neither is here.
    const fields = [
      ...ALL.filter((o) => !o.shell).map((o) => ({ name: JSON.stringify(o), compact: o.density === 'compact', classes: inputClasses(o as InputClassesOptions).split(' ') })),
      ...[...container.querySelectorAll('input, select')].map((el) => ({ name: el.getAttribute('aria-label')!, compact: el.getAttribute('aria-label') === 'Select compact', classes: [...el.classList] })),
    ]
    expect(fields.length).toBe(ALL.length / 2 + 4)
    await loadDeclarations(fields.flatMap((f) => f.classes).map((t) => parseClass(t).utility))
    for (const f of fields) {
      for (const root of [16, 32]) {
        expect({ phone: fieldHeight(f.classes, '', root), sm: fieldHeight(f.classes, 'sm', root) }, `${f.name} at a ${root}px root`).toEqual({
          phone: input * root,
          sm: (f.compact ? compactSm : input) * root,
        })
      }
    }
  })
})

// ------------------------------------------------------------------------------------------------- tone

describe("the field's tone is one class per state", SLOW, () => {
  /** The fields the components draw, with and without an error (a message, or `true` for none), Input with its
      icon and loading insets too. */
  const componentFields = () => {
    const { container } = render(
      <>
        <Input aria-label="Input" />
        <Input aria-label="Input error" error="Required" />
        <Input aria-label="Input boolean error" error />
        <Input aria-label="Input icon loading error" icon="i" loading error="Required" />
        <Textarea aria-label="Textarea" />
        <Textarea aria-label="Textarea error" error="Required" />
        <Select aria-label="Select">
          <option>x</option>
        </Select>
        <Select aria-label="Select compact error" density="compact" error="Required">
          <option>x</option>
        </Select>
      </>,
    )
    return [...container.querySelectorAll('input, textarea, select')].map((el) => ({
      name: el.getAttribute('aria-label')!,
      invalid: el.getAttribute('aria-invalid') === 'true',
      tone: 'default' as const,
      shell: false,
      classes: [...el.classList],
    }))
  }
  /** Every field the module draws: each combination of inputClasses() options, then the components. */
  const fields = () => [
    ...ALL.map((o) => ({ name: JSON.stringify(o), invalid: o.invalid, tone: o.tone, shell: o.shell, classes: inputClasses(o as InputClassesOptions).split(' ') })),
    ...componentFields(),
  ]

  /** Two of a field's own classes that set one property of one element in one variant chain: stylesheet order,
      not the field's state, decides between them. Tailwind's `transition-*` sets the default duration that its
      `duration-*` exists to override, the one pairing it documents and the one exempt. */
  const layered = (classes: string[]) => {
    const parsed = classes.map(parseClass)
    const durationPair = (a: string, b: string) => /^transition(-|$)/.test(a) && /^duration-/.test(b)
    return parsed.flatMap((a, i) =>
      parsed.slice(i + 1).flatMap((b) => {
        if (!sameSet(a.chain, b.chain)) return []
        const props = (declCache.get(a.utility) ?? []).flatMap((ae) =>
          (declCache.get(b.utility) ?? [])
            .filter((be) => joinTarget(a.target, ae.target) === joinTarget(b.target, be.target))
            .flatMap((be) => ae.decls.filter((d) => be.decls.some((x) => x.prop === d.prop && !(x.plumbing && d.plumbing))))
            .map((d) => d.prop)
            .filter((prop) => !(prop === 'transition-duration' && (durationPair(a.utility, b.utility) || durationPair(b.utility, a.utility)))),
        )
        return props.length ? [`${a.token} vs ${b.token} ${propList(props)}`] : []
      }),
    )
  }

  it('sets each property once per variant chain, for every combination of the options and every component', async () => {
    const all = fields()
    await loadDeclarations(all.flatMap((f) => f.classes).map((t) => parseClass(t).utility))
    expect(all.length).toBe(ALL.length + 8)
    expect(all.filter((f) => f.invalid).length, '`invalid` is one of BOOLEAN_OPTIONS, and the components take `error`').toBe(ALL.length / 2 + 5)
    for (const f of all) expect(layered(f.classes), f.name).toEqual([])
  })

  /** Each tone's border and ring by state: the classes that set the field's border colour, then its shadow, keyed
      by variant chain. The error border holds on hover (the red names the problem), and a disabled field's hover
      changes nothing in either tone. Each tone states its focus border even where it equals the rest border:
      @tailwindcss/forms draws `input:where([type='text']):focus` and its siblings with a #2563EB border at
      specificity 0,1,1, which a bare `border-*` class (0,1,0) loses to. Measured in Chromium, an error tone without
      `focus:border-error-light` showed that blue border on focus in light. */
  const TONES = {
    default: {
      border: {
        '': 'border-border-light',
        hover: 'hover:border-flat-light',
        focus: 'focus:border-brand',
        'disabled:hover': 'disabled:hover:border-border-light',
        dark: 'dark:border-border-dark',
        'dark:hover': 'dark:hover:border-flat-dark',
        'dark:focus': 'dark:focus:border-brand-dark',
        'dark:disabled:hover': 'dark:disabled:hover:border-border-dark',
      },
      ring: { focus: 'focus:shadow-ring-brand', 'dark:focus': 'dark:focus:shadow-ring-brand-dark' },
    },
    danger: {
      border: {
        '': 'border-border-light',
        hover: 'hover:border-flat-light',
        focus: 'focus:border-error-light',
        'disabled:hover': 'disabled:hover:border-border-light',
        dark: 'dark:border-border-dark',
        'dark:hover': 'dark:hover:border-flat-dark',
        'dark:focus': 'dark:focus:border-error-dark',
        'dark:disabled:hover': 'dark:disabled:hover:border-border-dark',
      },
      ring: { focus: 'focus:shadow-ring-error', 'dark:focus': 'dark:focus:shadow-ring-error-dark' },
    },
    error: {
      border: {
        '': 'border-error-light',
        focus: 'focus:border-error-light',
        dark: 'dark:border-error-dark',
        'dark:focus': 'dark:focus:border-error-dark',
      },
      ring: { focus: 'focus:shadow-ring-error', 'dark:focus': 'dark:focus:shadow-ring-error-dark' },
    },
  }
  const SHELL_TONES = {
    default: {
      border: {
        '': 'border-border-light',
        hover: 'hover:border-flat-light',
        'focus-within': 'focus-within:border-brand',
        'focus-within:hover': 'hover:focus-within:border-brand',
        dark: 'dark:border-border-dark',
        'dark:hover': 'dark:hover:border-flat-dark',
        'dark:focus-within': 'dark:focus-within:border-brand-dark',
        'dark:focus-within:hover': 'dark:hover:focus-within:border-brand-dark',
      },
      ring: { 'focus-within': 'focus-within:shadow-ring-brand', 'dark:focus-within': 'dark:focus-within:shadow-ring-brand-dark' },
    },
    danger: {
      border: {
        '': 'border-border-light',
        hover: 'hover:border-flat-light',
        'focus-within': 'focus-within:border-error-light',
        'focus-within:hover': 'hover:focus-within:border-error-light',
        dark: 'dark:border-border-dark',
        'dark:hover': 'dark:hover:border-flat-dark',
        'dark:focus-within': 'dark:focus-within:border-error-dark',
        'dark:focus-within:hover': 'dark:hover:focus-within:border-error-dark',
      },
      ring: { 'focus-within': 'focus-within:shadow-ring-error', 'dark:focus-within': 'dark:focus-within:shadow-ring-error-dark' },
    },
    error: {
      border: {
        '': 'border-error-light',
        'focus-within': 'focus-within:border-error-light',
        dark: 'dark:border-error-dark',
        'dark:focus-within': 'dark:focus-within:border-error-dark',
      },
      ring: { 'focus-within': 'focus-within:shadow-ring-error', 'dark:focus-within': 'dark:focus-within:shadow-ring-error-dark' },
    },
  }
  /** The classes that set `prop` on the field itself, keyed by their variant chain (sorted, `:`-joined). */
  const setters = (classes: string[], prop: string) =>
    Object.fromEntries(
      classes
        .map(parseClass)
        .filter((c) => !c.target && (declCache.get(c.utility) ?? []).some((e) => !e.target && e.decls.some((d) => d.prop === prop)))
        .map((c) => [[...c.chain].sort().join(':'), c.token]),
    )

  /** @tailwindcss/forms rings a focused field itself (`input:where([type='text']):focus`, `select:focus`, `textarea:focus`,
      0,1,1: a 1px #2563EB ring; 2px past a 2px white offset on a checkbox or radio), and `shadow-ring-*` composites
      `var(--tw-ring-offset-shadow), var(--tw-ring-shadow)` ahead of its own `--tw-shadow` instead of replacing them, so
      the blue ring drew over the DS one on every field. Each field takes it off in the plain `focus` chain (0,2,0),
      which outranks the plugin's rule and holds in both themes; a bare `ring-0` loses to it, and `focus-visible:` misses
      the mouse focus the DS ring shows on. Measured on production builds: `rgb(37, 99, 235) 0px 0px 0px 1px` before
      the DS ring on main, `0px` with the reset. */
  it('every field takes off the forms plugin’s own focus ring', async () => {
    // The composer Textarea has no tone (its shell draws the ring), so it is checked here and not in fields().
    const composer = render(<Textarea aria-label="Composer" variant="composer" />).container.querySelector('textarea')!
    const all = [...fields(), { name: 'Textarea composer', invalid: false, classes: [...composer.classList] }]
    await loadDeclarations(all.flatMap((f) => f.classes).map((t) => parseClass(t).utility))
    // Every class that sets the property, not one per chain: a second setter (`focus:ring-2` beside `focus:ring-0`)
    // would win by stylesheet order, and the composer is outside the `layered` check below.
    const every = (classes: string[], prop: string) =>
      classes.filter((t) => (declCache.get(parseClass(t).utility) ?? []).some((e) => !e.target && e.decls.some((d) => d.prop === prop)))
    for (const f of all) {
      expect({ ring: every(f.classes, '--tw-ring-shadow'), offset: every(f.classes, '--tw-ring-offset-width') }, f.name).toEqual({
        ring: ['focus:ring-0'],
        offset: ['focus:ring-offset-0'],
      })
    }
  })

  /** Pairs of the field's own classes that hold at once and that Tailwind's variant order, not the state, decides. */
  const orderDecided = (classes: string[]) => {
    const parsed = classes.map(parseClass)
    const out = new Set<string>()
    for (const x of parsed) {
      for (const y of parsed) {
        if (x === y || isSubset(x.chain, y.chain) || isSubset(y.chain, x.chain)) continue
        if (EXCLUSIVE.some(([p, q]) => (x.chain.has(p) && y.chain.has(q)) || (x.chain.has(q) && y.chain.has(p)))) continue
        for (const xe of declCache.get(x.utility) ?? []) for (const ye of declCache.get(y.utility) ?? []) {
          const target = joinTarget(x.target, xe.target)
          if (target !== joinTarget(y.target, ye.target)) continue
          const props = xe.decls.filter((d) => !d.plumbing && ye.decls.some((e) => e.prop === d.prop && e.value !== d.value && !e.plumbing)).map((d) => d.prop)
          if (!props.length) continue
          const union = new Set([...x.chain, ...y.chain])
          const holders = parsed.filter((t) => isSubset(t.chain, union)).flatMap((t) =>
            (declCache.get(t.utility) ?? []).filter((e) => joinTarget(t.target, e.target) === target).map((e) => ({ chain: t.chain, decls: e.decls.filter((d) => !d.plumbing && props.includes(d.prop)) })),
          ).filter((h) => h.decls.length)
          for (const prop of props) {
            const setting = holders.filter((h) => h.decls.some((d) => d.prop === prop))
            const maximal = setting.filter((h) => !setting.some((o) => o.chain.size > h.chain.size && isSubset(h.chain, o.chain)))
            if (new Set(maximal.flatMap((h) => h.decls.filter((d) => d.prop === prop).map((d) => d.value))).size > 1) {
              out.add([x.token, y.token].sort().join(' vs ') + ` (${[...union].sort().join('+')})`)
            }
          }
        }
      }
    }
    return [...out].sort()
  }

  /** The position of each class's rule in the stylesheet Tailwind emits for them (this config, globals.css as input). */
  const ruleOrder = async (tokens: string[]) => {
    const from = path.join(FRONTEND_ROOT, 'app/globals.css')
    const css = await postcss([tailwindcss({ ...config, content: [{ raw: tokens.join(' '), extension: 'html' }], safelist: [] })]).process(readFileSync(from, 'utf8'), { from })
    const order = new Map<string, number>()
    let i = 0
    css.root.walkRules((rule) => {
      i += 1
      const m = rule.selector.match(/^\.((?:\\[0-9a-fA-F]{1,6} ?|\\.|[\w-])+)/)
      const token = m && unescapeCss(m[1])
      if (token && tokens.includes(token) && !order.has(token)) order.set(token, i)
    })
    return order
  }

  it('neutral resting tones leave only focus-over-hover to variant order, and Tailwind emits focus after hover; invalid fields and shells leave none', async () => {
    const all = fields()
    await loadDeclarations(all.flatMap((f) => f.classes).map((t) => parseClass(t).utility))
    const FOCUS_OVER_HOVER = [
      'dark:focus:border-brand-dark vs dark:hover:border-flat-dark (dark+focus+hover)',
      'dark:focus:border-brand-dark vs hover:border-flat-light (dark+focus+hover)',
      'dark:hover:border-flat-dark vs focus:border-brand (dark+focus+hover)',
      'focus:border-brand vs hover:border-flat-light (focus+hover)',
    ]
    for (const f of all) {
      const focusOverHover = f.tone === 'danger'
        ? FOCUS_OVER_HOVER.map((pair) => pair.replaceAll('border-brand-dark', 'border-error-dark').replaceAll('border-brand', 'border-error-light')).sort()
        : FOCUS_OVER_HOVER
      expect(orderDecided(f.classes), f.name).toEqual(!f.shell && !f.invalid ? focusOverHover : [])
    }
    const order = await ruleOrder(['hover:border-flat-light', 'focus:border-brand', 'focus:border-error-light', 'dark:hover:border-flat-dark', 'dark:focus:border-brand-dark', 'dark:focus:border-error-dark'])
    for (const ink of ['brand', 'error-light']) expect(order.get(`focus:border-${ink}`)!).toBeGreaterThan(order.get('hover:border-flat-light')!)
    for (const ink of ['brand-dark', 'error-dark']) expect(order.get(`dark:focus:border-${ink}`)!).toBeGreaterThan(order.get('dark:hover:border-flat-dark')!)
  })

  it('danger changes focus only, while invalid and component errors take precedence with an error border in every state', async () => {
    const all = fields()
    await loadDeclarations(all.flatMap((f) => f.classes).map((t) => parseClass(t).utility))
    for (const f of all) {
      expect(
        { border: setters(f.classes, 'border-top-color'), ring: setters(f.classes, '--tw-shadow') },
        f.name,
      ).toEqual((f.shell ? SHELL_TONES : TONES)[f.invalid ? 'error' : f.tone])
    }
  })
})
