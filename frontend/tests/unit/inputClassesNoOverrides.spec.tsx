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
import { Input, Select, Textarea, inputClasses, type FieldDensity, type InputClassesOptions } from '@/components/ui/Input'
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
 * `autoWidth` (sized to its content), `density` and `leadingIcon`; Button's twin gate is
 * button-icon-size-gate.spec.ts.
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
 * pseudo-element) and declare one property with different values, `--tw-*` properties included; a declaration
 * that reads a `var(--tw-…)` its own rule does not set is Tailwind's composite plumbing (box-shadow behind
 * `shadow-*` and `ring-*`) and is skipped, so `focus:ring-0` does not compete with the field's ring shadow. It
 * fails:
 *
 *  (a) same chain: the two carry the same variants (as a set). Stylesheet order decides: `w-auto` vs `w-full`.
 *  (b) no twin: the field sets the property under `dark:` or a screen (`sm:`) the added class lacks, plus only
 *      variants the added class carries, and no added class covers that chain. The field's rule outranks it
 *      there: the delete-account field's `focus:border-error-light` shows the brand border in dark.
 *  (c) `!important`, or an arbitrary variant (`[&>option]:`) the gate cannot place.
 *  (d) `autoWidth` on a <select> without `select` (the forms plugin's chevron then sits over its text), or
 *      `select` on anything but a <select>.
 *
 * A state layer passes: `aria-disabled:bg-background-light` over the field's `bg-white` (with its
 * `dark:aria-disabled:` twin), `focus-within:border-brand` on the composer shell. A position the scan cannot
 * follow (the result held in a variable, returned, joined with `+`, passed to another function, a className
 * from a parameter, an option spread) fails rather than passing unread.
 *
 * PINS holds the known sites by path and exact finding, with a reason, capped and shrink-only: a new finding
 * fails, and so does a pin that no longer matches.
 *
 * What it cannot see: two different state chains of one specificity that Tailwind's variant order decides (the
 * composer shell's `focus-within:` border loses to the field's `hover:` border while both hold); a class reaching
 * the field through a props spread or another component; a namespace import; a utility outside this config.
 */

const FRONTEND_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const ROOTS = ['app', 'components', 'features', 'hooks', 'lib']
const DEFINITION = 'components/ui/Input.tsx'

const PINS: Record<string, { findings: string[]; reason: string }> = {
  'features/auth/components/PasswordField.tsx': {
    findings: ['pr-10 vs px-3.5 [padding-right] (same chain)'],
    reason:
      'Wins today only because the padding plugin emits side utilities after axis ones (.px-3.5 rule 614 < ' +
      '.pr-10 658), the gamble the DS forbids. Needs a trailing-inset option on inputClasses (the Input ' +
      "component's own `loading ? 'pr-10' : 'pr-3.5'`), with its compact and leading-icon combinations.",
  },
  'app/dashboard/settings/page.tsx': {
    findings: [
      'focus:border-error-light vs dark:border-border-dark [border-color] (no dark twin)',
      'focus:border-error-light vs dark:focus:border-brand-dark [border-color] (no dark twin)',
      'focus:border-error-light vs focus:border-brand [border-color] (same chain)',
      'focus:shadow-ring-error vs dark:focus:shadow-ring-brand-dark [--tw-shadow] (no dark twin)',
      'focus:shadow-ring-error vs focus:shadow-ring-brand [--tw-shadow] (same chain)',
    ],
    reason:
      'The delete-account confirm field: its error-toned focus wins in light by one rule and loses in dark (the ' +
      'sage brand border and ring show). The fix shows `shadow-ring-error` in dark, which reads 1.27:1 on panel, ' +
      'so it waits on the dark ring-error token decision (rule 11) recorded by #1178.',
  },
}
const MAX_PINNED_SITES = 2

// ------------------------------------------------------------------------------------------------- scanner

type Options = { invalid: boolean; leadingIcon: boolean; select: boolean; density: FieldDensity; autoWidth: boolean }
const DEFAULTS: Options = { invalid: false, leadingIcon: false, select: false, density: 'comfortable', autoWidth: false }
const BOOLEAN_OPTIONS = ['invalid', 'leadingIcon', 'select', 'autoWidth'] as const
const DENSITIES: FieldDensity[] = ['comfortable', 'compact']

interface Site { file: string; line: number; tag: string; combos: Options[]; added: string[] }
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
    for (const span of tpl.templateSpans) {
      if (/\S$/.test(before) || /^\S/.test(span.literal.text)) throw new Unreadable('a class built from pieces of a template')
      if (span !== except) out.push(...classSource(span.expression, depth + 1))
      out.push(...split(span.literal.text))
      before = span.literal.text
    }
    return out
  }

  const readOptions = (call: ts.CallExpression): { combos: Options[]; className: string[] } => {
    if (call.arguments.length > 1) throw new Unreadable('inputClasses() given more than one argument')
    const arg = call.arguments[0]
    if (!arg) return { combos: [DEFAULTS], className: [] }
    if (!ts.isObjectLiteralExpression(arg)) throw new Unreadable('inputClasses() options that are not an object literal')
    const values: { [K in keyof Options]: Options[K][] } = {
      invalid: [false], leadingIcon: [false], select: [false], density: ['comfortable'], autoWidth: [false],
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
      } else throw new Unreadable(`an option inputClasses() does not take: ${key}`)
    }
    let combos: Options[] = [{ ...DEFAULTS }]
    for (const key of Object.keys(values) as (keyof Options)[]) {
      combos = combos.flatMap((c) => (values[key] as Options[typeof key][]).map((v) => ({ ...c, [key]: v })))
    }
    return { combos, className }
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
        return { file, line: lineOf(call), tag: element.tagName.getText(sf), combos, added }
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

type Decl = { prop: string; value: string }
const declCache = new Map<string, Decl[] | null>()

/** Unescapes a CSS identifier: `px-3\.5` → `px-3.5`, `\2c ` → `,`. */
const unescapeCss = (s: string) =>
  s.replace(/\\([0-9a-fA-F]{1,6}) ?|\\(.)/g, (_, hex: string | undefined, ch: string | undefined) => (hex ? String.fromCodePoint(parseInt(hex, 16)) : ch!))

/** What Tailwind declares for each bare utility, read off the rules whose selector is that one class. */
async function loadDeclarations(utilities: string[]): Promise<void> {
  const missing = [...new Set(utilities)].filter((u) => !declCache.has(u))
  if (!missing.length) return
  const from = path.join(FRONTEND_ROOT, 'app/globals.css')
  const css = await postcss([tailwindcss({ ...config, content: [{ raw: missing.join(' '), extension: 'html' }], safelist: [] })]).process(
    readFileSync(from, 'utf8'),
    { from },
  )
  for (const u of missing) declCache.set(u, null)
  css.root.walkRules((rule) => {
    if (rule.parent?.type !== 'root') return
    const m = rule.selector.match(/^\.((?:\\[0-9a-fA-F]{1,6} ?|\\.|[\w-])+)$/)
    if (!m) return
    const name = unescapeCss(m[1])
    if (!missing.includes(name)) return
    const decls: Decl[] = []
    rule.walkDecls((d) => {
      decls.push({ prop: d.prop, value: d.value.trim() })
    })
    declCache.set(name, [...(declCache.get(name) ?? []), ...decls])
  })
}

/** The declarations that carry a value: a declaration reading a `--tw-*` its own rule does not set is plumbing. */
function valued(decls: Decl[]): Decl[] {
  const own = new Set(decls.map((d) => d.prop))
  return decls.filter((d) => d.prop.startsWith('--') || ![...d.value.matchAll(/var\((--tw-[\w-]+)/g)].some((m) => !own.has(m[1])))
}

const sameSet = (a: Set<string>, b: Set<string>) => a.size === b.size && [...a].every((x) => b.has(x))

function competing(field: string[], added: string[]): string[] {
  const out = new Set<string>()
  const parsedAdded = added.map(parseClass)
  for (const a of parsedAdded) {
    if (a.important) out.add(`${a.token} (important)`)
    if (a.arbitrary) {
      out.add(`${a.token} (arbitrary variant)`)
      continue
    }
    const aDecls = declCache.get(a.utility)
    if (!aDecls) {
      out.add(`${a.token} (not a utility this config generates)`)
      continue
    }
    for (const f of field.map(parseClass)) {
      if (f.target !== a.target) continue
      const fDecls = valued(declCache.get(f.utility) ?? [])
      const ad = valued(aDecls)
      const props = fDecls.filter((d) => ad.some((x) => x.prop === d.prop && x.value !== d.value)).map((d) => d.prop)
      if (!props.length) continue
      const list = `[${[...new Set(props)].join(',')}]`
      if (sameSet(a.chain, f.chain)) {
        out.add(`${a.token} vs ${f.token} ${list} (same chain)`)
        continue
      }
      const lacking = [...f.chain].filter((v) => OUTRANKING.has(v) && !a.chain.has(v))
      const rest = [...f.chain].filter((v) => !OUTRANKING.has(v))
      if (!lacking.length || !rest.every((v) => a.chain.has(v))) continue
      const want = new Set([...a.chain, ...lacking])
      const twin = parsedAdded.some(
        (t) => t.target === a.target && sameSet(t.chain, want) && (declCache.get(t.utility) ?? []).some((d) => props.includes(d.prop)),
      )
      if (!twin) out.add(`${a.token} vs ${f.token} ${list} (no ${lacking.join('+')} twin)`)
    }
  }
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
      if (site.tag === 'select' && combo.autoWidth && !combo.select) {
        found.add('autoWidth on a <select> without select: true (the chevron sits over its text)')
      }
      if (site.tag !== 'select' && combo.select) found.add(`select: true on a <${site.tag}>`)
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

function scanApp(): Scan & { files: number } {
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
  return total
}

describe('a raw field takes inputClasses() options, never a competing class on top', () => {
  it('no class combined with inputClasses() competes with the field’s own', async () => {
    const scan = scanApp()
    expect(scan.unreadable, 'inputClasses() where the gate cannot read what it is combined with').toEqual([])
    const found = await check(scan)
    const unpinned = found.filter((f) => !PINS[f.file]?.findings.includes(f.finding)).map((f) => `${f.file}:${f.line} ${f.finding}`)
    expect(
      unpinned,
      'A class on top of inputClasses() that sets what the field sets resolves by stylesheet order, not class ' +
        'order (cx and clsx do no tailwind-merge). Use an option (select, autoWidth, density, leadingIcon, invalid) ' +
        'or add one to components/ui/Input.tsx with explicit sides.',
    ).toEqual([])
    const stale = Object.entries(PINS).flatMap(([file, pin]) =>
      pin.findings.filter((finding) => !found.some((f) => f.file === file && f.finding === finding)).map((finding) => `${file}: ${finding}`),
    )
    expect(stale, 'pins that no longer match a finding: remove them').toEqual([])
    expect(Object.keys(PINS).length).toBeLessThanOrEqual(MAX_PINNED_SITES)
  })

  it('reads the app (a rename cannot leave it scanning nothing)', () => {
    const scan = scanApp()
    expect(scan.files).toBeGreaterThan(100)
    expect(scan.calls).toBeGreaterThanOrEqual(10)
  })
})

// ------------------------------------------------------------------------------------------------- the scanner

const IMPORTS = `import { clsx } from 'clsx'\nimport { fieldUnavailableClass, inputClasses } from '@/components/ui/Input'\n`

describe('the scanner', () => {
  it('fails each override main abda78ce shipped, verbatim', async () => {
    expect(await findingsOf(`${IMPORTS}export const D = () => <select className={clsx(inputClasses(), 'w-auto py-1.5 text-sm', fieldUnavailableClass)} />`)).toEqual([
      'py-1.5 vs py-2.5 [padding-top,padding-bottom] (same chain)',
      'w-auto vs w-full [width] (same chain)',
    ])
    expect(await findingsOf(`${IMPORTS}export const F = () => <select className={\`\${inputClasses()} w-auto py-1.5 pr-8 text-xs \${fieldUnavailableClass}\`} />`)).toEqual([
      'pr-8 vs px-3.5 [padding-right] (same chain)',
      'py-1.5 vs py-2.5 [padding-top,padding-bottom] (same chain)',
      'text-xs vs text-sm [font-size,line-height] (same chain)',
      'w-auto vs w-full [width] (same chain)',
    ])
    expect(await findingsOf(`${IMPORTS}export const A = () => <select className={\`\${inputClasses()} w-auto\`} />`)).toEqual([
      'w-auto vs w-full [width] (same chain)',
    ])
  })

  it('passes the options that replace them', async () => {
    expect(await findingsOf(`${IMPORTS}export const D = () => <select className={clsx(inputClasses({ select: true, autoWidth: true }), fieldUnavailableClass)} />`)).toEqual([])
    expect(
      await findingsOf(`${IMPORTS}export const F = () => <select className={\`\${inputClasses({ select: true, density: 'compact', autoWidth: true })} \${fieldUnavailableClass}\`} />`),
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
      PINS['app/dashboard/settings/page.tsx'].findings,
    )
    // The chat composer's shell: a focus-within state layer with its dark twin.
    const composer = `import { cx, inputClasses } from '@/components/ui'
export const S = () => <div className={cx(inputClasses({ className: 'flex items-end gap-2' }), 'focus-within:border-brand focus-within:shadow-ring-brand', 'dark:focus-within:border-brand-dark dark:focus-within:shadow-ring-brand-dark')} />`
    expect(await findingsOf(composer)).toEqual([])
    expect(await findingsOf(composer.replace(", 'dark:focus-within:border-brand-dark dark:focus-within:shadow-ring-brand-dark'", ''))).toEqual([
      'focus-within:border-brand vs dark:border-border-dark [border-color] (no dark twin)',
    ])
  })

  it("passes #1178's ink-fade fieldUnavailableClass, and fails it without its dark twins", async () => {
    const fade =
      'aria-disabled:cursor-not-allowed aria-disabled:bg-background-light aria-disabled:text-text-primary-light/60 aria-disabled:hover:border-border-light ' +
      'dark:aria-disabled:bg-white/5 dark:aria-disabled:text-text-primary-dark/60 dark:aria-disabled:hover:border-border-dark'
    const site = (classes: string) => `${IMPORTS}const FADE = '${classes}'\nexport const U = () => <select className={clsx(inputClasses({ select: true, autoWidth: true }), FADE)} />`
    expect(await findingsOf(site(fade))).toEqual([])
    expect(await findingsOf(site(fade.replace(/ dark:aria-disabled:\S+/g, '')))).toEqual([
      'aria-disabled:bg-background-light vs dark:bg-white/5 [background-color] (no dark twin)',
      'aria-disabled:hover:border-border-light vs dark:border-border-dark [border-color] (no dark twin)',
      'aria-disabled:hover:border-border-light vs dark:hover:border-flat-dark [border-color] (no dark twin)',
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

  it('holds a <select> that sizes to its content to the chevron padding, and `select` to a <select>', async () => {
    expect(await findingsOf(`${IMPORTS}export const S = () => <select className={inputClasses({ autoWidth: true })} />`)).toEqual([
      'autoWidth on a <select> without select: true (the chevron sits over its text)',
    ])
    expect(await findingsOf(`${IMPORTS}export const I = () => <input className={inputClasses({ select: true })} />`)).toEqual([
      'select: true on a <input>',
    ])
    // A flag it cannot read is checked both ways.
    expect(await findingsOf(`${IMPORTS}export const S = ({ wide }: { wide: boolean }) => <select className={inputClasses({ autoWidth: wide })} />`)).toEqual([
      'autoWidth on a <select> without select: true (the chevron sits over its text)',
    ])
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
    expect(await unreadable('export const f = inputClasses')).toEqual(['inputClasses used as a value'])
  })
})

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
