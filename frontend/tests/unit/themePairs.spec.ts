import { readdirSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * Every colour is a light/dark pair (DESIGN_SYSTEM.md §2, CLAUDE.md rules 11 and 12). The ESLint design
 * rules stop raw hex and palette colours; nothing stopped a theme token from shipping without its dark
 * half: the password strength meter's bars were `bg-error-light`, `bg-warning-light` and
 * `bg-success-light` alone, so dark mode drew the light theme's colours on navy (the 2026-10 audit, UA-44).
 *
 * The rule: a colour class on a light half has a `dark:` twin in the same class list. A light half is a
 * token tailwind.config.js pairs by name: every `-light` token, and every token beside a `<name>-dark`
 * (`brand-weak` with `brand-weak-dark`, `gain` with `gain-dark`), so `bg-error-light`,
 * `hover:bg-brand-weak` and `text-text-secondary-light/50` are all read. The twin is a `dark:` colour class
 * on the same property (bg, text, border, border-t, ring, ring-offset, …) under the same other variants
 * (`hover:`, `aria-disabled:`, in any order). Its colour is free (`dark:hover:bg-white/5` twins
 * `hover:bg-brand-weak`'s row, and `dark:bg-brand-dark/15` twins `bg-brand-strong/10`), but it must be a
 * colour that is not itself a light half: a dark token, white, black, transparent, current, a palette step
 * or an arbitrary colour. `dark:text-sm`, `dark:border-0`, `dark:bg-none` or `dark:bg-error-light` is not a
 * twin. Tokens the config gives no dark sibling (the chart palette and overlay, one value in both themes,
 * and `brand-emphasis`, `gain-text`, `loss-text`, `info-text`, `error-emphasis`) are not read.
 *
 * The other half: a colour class on a dark half (every token the config names `-dark`, beside a `-light` or
 * suffixless sibling or not: `brand-fill-dark`, the dark theme's pressed fill, has neither) with no `dark:`
 * variant paints the dark theme's colour in the light theme too. UserMenu's unverified dot wore
 * `ring-background-dark` alone, a navy ring on the cream header, and the verification banner's dismiss hover
 * tinted the light band with the dark amber. Such a class fails wherever it is, unless its surface is dark in
 * both themes on purpose, listed in BARE_DARK_RESIDUE. In a stylesheet, a rule block whose every selector
 * names `.dark` (the config's `darkMode: 'class'`) outside a `:not(…)` or `:has(…)`, or that sits inside one,
 * is the dark theme's: `html:not(.dark) .x` is the light theme's. A limit: `.dark` beside another selector in an
 * `:is(…)` or `:where(…)` counts too, so `:is(.dark, .card) .x { @apply bg-panel-dark; }` reads as the dark
 * theme's though it also paints `.card .x` in the light theme.
 *
 * A class list is the strings that always render together: one string, the static parts of one template, or
 * the unconditional strings of one call to the class joiners (`cx`, `clsx`, `cn`), one inline `[…].join(…)`
 * or one `+` chain. A string under a condition (`on && '…'`, a ternary arm, a `clsx({ '…': on })` key, a
 * template slot) renders only sometimes, so it is a class list of its own beside those unconditional
 * strings: its light class may take its twin from them, but nothing takes a twin from it, and no arm or key
 * takes one from another. A joiner nested under a condition pairs its own unconditional strings the same
 * way. A call that is not a joiner (a helper building its own list) is read on its own, and a value in a
 * lookup table (`STRENGTH_COLORS[score]`) is a class list of its own and carries its own twin. In a
 * stylesheet under the scanned directories (app/globals.css), the `@apply` statements of one rule block,
 * from its `{` to its `}` with nested blocks apart and comments removed, style one element, so together
 * they are one class list; a statement ends at its `;` or, the last in its block, at the block's `}`, as CSS
 * and PostCSS read it (`.x { @apply bg-error-light }` compiles to a colour).
 *
 * The scan reads every script and stylesheet under SCAN_DIRS (`.ts`, `.tsx`, `.js`, `.jsx`, `.mjs`, `.cjs`,
 * `.css`); any other file there fails the first case until it is read or listed in NOT_READ with why it
 * holds no class list, so a new kind of source cannot sit outside the scan.
 *
 * THEME_PAIR_RESIDUE holds what the scan finds, counted per file and per class (variants and opacity
 * included), and THEME_PAIR_RESIDUE_MAX equals its totals: a new unpaired class fails (an unlisted file or
 * class, or a listed count that rises), a fixed one fails until its count is lowered or its entry deleted,
 * and the cap moves down with the list in the same commit, so a shrink leaves no headroom for a later
 * class to refill. Swapping a fixed class for a different one fails too; what a count cannot see is the
 * same class moved to another element of the same file.
 */
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']

/** Longest first: `border-t-…` and `ring-offset-…` are their own properties. */
const PROPERTY = /^(ring-offset|border-[xytblrse]|bg|text|border|ring|fill|stroke|from|via|to|divide|outline|decoration|accent|caret|placeholder|shadow)-(.+)$/
const OPACITY = /\/(?:\d+|\[[^\]]+\])$/
const JOINERS = new Set(['cx', 'clsx', 'cn'])

/** The colour names Tailwind resolves here: the config's tokens, the built-ins, and the default palette. */
function colourNames(colors: Record<string, unknown>, prefix = ''): string[] {
  return Object.entries(colors).flatMap(([key, value]) => {
    const name = key === 'DEFAULT' ? prefix : prefix ? `${prefix}-${key}` : key
    return typeof value === 'object' && value !== null ? colourNames(value as Record<string, unknown>, name) : [name]
  })
}
const TAILWIND = createRequire(import.meta.url)('../../tailwind.config.js') as {
  theme: { colors?: Record<string, unknown>; extend: { colors: Record<string, unknown> } }
}
const TOKENS = [...colourNames(TAILWIND.theme.extend.colors), ...colourNames(TAILWIND.theme.colors ?? {})]
const COLOURS = new Set([...TOKENS, 'white', 'black', 'transparent', 'current', 'inherit'])
/** The light halves the config pairs by name: `<name>-light`, or `<name>` beside a `<name>-dark`. */
const LIGHT_HALVES = new Set(TOKENS.filter((name) => name.endsWith('-light') || COLOURS.has(`${name}-dark`)))
const PALETTE_STEP = /^(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-(50|[1-9]00|950)$/
const ARBITRARY_COLOUR = /^\[(?:#|rgba?\(|hsla?\(|color:)/
const bare = (value: string) => value.replace(OPACITY, '')
const isColour = (value: string) => COLOURS.has(bare(value)) || PALETTE_STEP.test(bare(value)) || ARBITRARY_COLOUR.test(bare(value))
const isLightHalf = (value: string) => LIGHT_HALVES.has(bare(value))
/** The dark theme's colours: every token the config names `<name>-dark`, with a light sibling or without one (`brand-fill-dark`). */
const DARK_HALVES = new Set(TOKENS.filter((name) => name.endsWith('-dark')))
const isDarkHalf = (value: string) => DARK_HALVES.has(bare(value))
/** A colour utility on a light half, with an optional opacity (`/50`, `/[0.06]`): its property. */
function lightProperty(utility: string): string | undefined {
  const match = PROPERTY.exec(utility)
  return match && isLightHalf(match[2]) ? match[1] : undefined
}

type Finding = { rel: string; line: number; className: string }

/** Scripts (TS or JS, JSX or not) and stylesheets are read. */
const READ = /\.(?:[cm]?[jt]sx?|css)$/
/** Every other extension under SCAN_DIRS, with why it holds no class list. */
const NOT_READ: Record<string, string> = {
  '.json': 'data (the analysis demo), never a className',
  '.md': 'prose (a feature README), never rendered',
}

function allFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) return entry.name === 'node_modules' ? [] : allFiles(full)
    return [full]
  })
}
/** A test or a type declaration renders nothing (tests live under tests/, testHomesAllowlist.spec.ts). */
const isSource = (file: string) => READ.test(file) && !/\.(?:spec|test)\.[cm]?[jt]sx?$/.test(file) && !/\.d\.[cm]?ts$/.test(file)
const scriptKind = (rel: string) =>
  rel.endsWith('.tsx') ? ts.ScriptKind.TSX : rel.endsWith('.jsx') ? ts.ScriptKind.JSX : /\.[cm]?js$/.test(rel) ? ts.ScriptKind.JS : ts.ScriptKind.TS

/** A class's variants and utility, split on the colons outside brackets (`dark:text-[color:var(--ink)]`). */
function splitClass(token: string): { variants: string[]; utility: string } {
  const parts: string[] = []
  let depth = 0
  let start = 0
  for (let i = 0; i < token.length; i++) {
    if (token[i] === '[') depth++
    else if (token[i] === ']') depth--
    else if (token[i] === ':' && depth === 0) {
      parts.push(token.slice(start, i))
      start = i + 1
    }
  }
  parts.push(token.slice(start))
  return { variants: parts.slice(0, -1), utility: parts[parts.length - 1].replace(/^!/, '') }
}

/** The unpaired light-half classes of `own`, whose twins may sit in `own` or in `shared` (what always renders beside it). */
function unpaired(own: string, shared = ''): string[] {
  const classes = own.split(/\s+/).filter(Boolean)
  const darkKeys = new Set(
    [...classes, ...shared.split(/\s+/).filter(Boolean)].flatMap((token) => {
      const { variants, utility } = splitClass(token)
      const match = PROPERTY.exec(utility)
      if (!variants.includes('dark') || !match || !isColour(match[2]) || isLightHalf(match[2])) return []
      return [`${variants.filter((v) => v !== 'dark').sort().join(':')}|${match[1]}`]
    }),
  )
  return classes.filter((token) => {
    const { variants, utility } = splitClass(token)
    const property = lightProperty(utility)
    if (variants.includes('dark') || !property) return false
    return !darkKeys.has(`${[...variants].sort().join(':')}|${property}`)
  })
}

/**
 * The text ramp keeps its rung in dark (DESIGN_SYSTEM.md §2). Tertiary's twin is tertiary-dark, the de-emphasised
 * gray-400; secondary's is secondary-dark, the reading gray-300. Twinned across rungs, de-emphasised copy reads as body
 * copy in dark, or body copy fades: until the dark secondary rose to gray-300, 140 tertiary sites took secondary-dark as
 * their twin because tertiary-dark (then gray-600) failed as text, and they would all have brightened with it.
 */
const CROSSED_RUNG: Record<string, string> = { 'text-tertiary-light': 'text-secondary-dark', 'text-secondary-light': 'text-tertiary-dark' }
/** The classes of `own` on a light text rung whose `dark:` twin, in `own` or in `shared`, is the other rung's. */
function crossedRungs(own: string, shared = ''): string[] {
  const twins = new Map<string, Set<string>>()
  for (const token of [...own.split(/\s+/), ...shared.split(/\s+/)].filter(Boolean)) {
    const { variants, utility } = splitClass(token)
    const match = PROPERTY.exec(utility)
    if (!variants.includes('dark') || !match) continue
    const key = `${variants.filter((v) => v !== 'dark').sort().join(':')}|${match[1]}`
    twins.set(key, (twins.get(key) ?? new Set()).add(bare(match[2])))
  }
  return own.split(/\s+/).filter(Boolean).filter((token) => {
    const { variants, utility } = splitClass(token)
    const match = PROPERTY.exec(utility)
    const crossed = match && !variants.includes('dark') ? CROSSED_RUNG[bare(match[2])] : undefined
    return !!crossed && !!twins.get(`${[...variants].sort().join(':')}|${match![1]}`)?.has(crossed)
  })
}

/**
 * A hover the dark theme can see (DESIGN_SYSTEM.md §2). Dark primary (#D7DADC) and dark secondary (#D1D5DB) are 1.05:1
 * apart, so a control that rests in the secondary ink and only turns primary under the pointer shows no hover in dark
 * (light keeps a 1.69:1 step). Such a control steps to white in dark or carries another hover cue: a fill, a border, a
 * ring, a shadow or an underline. Thirteen controls had only the ink step when the dark secondary rose to gray-300.
 *
 * The cue must change something in dark. A `dark:` variant compiles to `:is(.dark *)`, as specific as `:hover` and later
 * in the stylesheet, so a `hover:` cue without `dark:` is overruled in dark by a `dark:` rest or `dark:` hover of the same
 * property: the toast close button's light tint (`hover:!bg-brand-weak`) lost to its forced `dark:!bg-panel-dark`, and
 * its `dark:hover:!bg-panel-dark` repeated the rest, so dark showed no hover while this gate passed it.
 */
const cueProperty = (utility: string) =>
  utility === 'underline' ? 'underline' : /^(bg|border(?:-[xytblrse])?|ring|shadow|outline|decoration)-/.exec(utility)?.[1]
function faintHovers(own: string, shared = ''): string[] {
  const all = [...own.split(/\s+/), ...shared.split(/\s+/)].filter(Boolean).map((token) => ({ token, ...splitClass(token), bare: splitClass(token).utility.replace(/^!/, '') }))
  const at = (variants: string[], test: (utility: string) => boolean) =>
    all.some((c) => c.variants.length === variants.length && variants.every((v) => c.variants.includes(v)) && test(c.bare))
  const restsSecondary = at(['dark'], (u) => u === 'text-text-secondary-dark')
  const hovered = (c: { variants: string[] }) => c.variants.includes('hover') || c.variants.includes('group-hover')
  const darkRest = (property: string) => all.filter((c) => c.variants.length === 1 && c.variants[0] === 'dark' && cueProperty(c.bare) === property).map((c) => c.bare)
  const darkHover = (property: string) => all.some((c) => hovered(c) && c.variants.includes('dark') && cueProperty(c.bare) === property)
  const cue = all.some((c) => {
    const property = hovered(c) ? cueProperty(c.bare) : undefined
    if (!property) return false
    // A dark hover is a cue when it differs from the dark rest; a plain hover only when nothing dark overrules it.
    return c.variants.includes('dark') ? !darkRest(property).includes(c.bare) : !darkRest(property).length && !darkHover(property)
  })
  if (!restsSecondary || cue) return []
  return own.split(/\s+/).filter(Boolean).filter((token) => {
    const { variants, utility } = splitClass(token)
    return variants.length === 2 && variants.includes('dark') && variants.includes('hover') && /^!?text-text-(?:primary|heading)-dark$/.test(utility)
  })
}

const isPlus = (node: ts.Node): node is ts.BinaryExpression => ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken
const isText = (node: ts.Node) => ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isTemplateExpression(node)

/** The parts of one built className: `cx(…)`, `clsx(…)`, `cn(…)`, `[…].join(…)`, or a `+` chain that carries a string. */
function joinedParts(node: ts.Node): readonly ts.Expression[] | undefined {
  if (ts.isCallExpression(node)) {
    const callee = node.expression
    if (ts.isIdentifier(callee) && JOINERS.has(callee.text)) return node.arguments
    if (ts.isPropertyAccessExpression(callee) && callee.name.text === 'join' && ts.isArrayLiteralExpression(callee.expression)) {
      return callee.expression.elements
    }
    return undefined
  }
  if (!isPlus(node)) return undefined
  const parts: ts.Expression[] = []
  const flatten = (n: ts.Expression): void => {
    if (isPlus(n)) {
      flatten(n.left)
      flatten(n.right)
    } else if (ts.isParenthesizedExpression(n) && isPlus(n.expression)) flatten(n.expression)
    else parts.push(n)
  }
  flatten(node)
  return parts.some(isText) ? parts : undefined
}

/**
 * A string's text, or the static text of a template: its literal parts, and each slot that names a string constant of
 * the same file (`${MUTED}`), which renders every time. Other slots are read apart.
 */
function staticText(node: ts.Node, consts: ReadonlyMap<string, string> = new Map()): string | undefined {
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return node.text
  if (ts.isTemplateExpression(node)) {
    return [node.head.text, ...node.templateSpans.flatMap((span) => [ts.isIdentifier(span.expression) ? consts.get(span.expression.text) ?? '' : '', span.literal.text])].join(' ')
  }
  return undefined
}

/** A file's `const NAME = '…'` strings, which a template slot naming one renders whole. */
function stringConsts(sf: ts.SourceFile): Map<string, string> {
  const consts = new Map<string, string>()
  const collect = (node: ts.Node): void => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer && (node.parent.flags & ts.NodeFlags.Const)
      && (ts.isStringLiteral(node.initializer) || ts.isNoSubstitutionTemplateLiteral(node.initializer))) consts.set(node.name.text, node.initializer.text)
    ts.forEachChild(node, collect)
  }
  collect(sf)
  return consts
}

function themePairFindings(source: string, rel: string, check: (own: string, shared?: string) => string[] = unpaired): Finding[] {
  const sf = ts.createSourceFile(rel, source, ts.ScriptTarget.Latest, true, scriptKind(rel))
  const consts = stringConsts(sf)
  const findings: Finding[] = []
  const report = (node: ts.Node, own: string, shared: string) => {
    const line = sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
    for (const className of check(own, shared)) findings.push({ rel, line, className })
  }
  /** One built className: its unconditional strings are one list, and each conditional string sits beside them. */
  const built = (node: ts.Node, parts: readonly ts.Node[], context: string) => {
    const always = parts.map((part) => staticText(part, consts)).filter((text): text is string => text !== undefined)
    report(node, always.join(' '), context)
    const shared = [context, ...always].join(' ')
    for (const part of parts) {
      if (ts.isTemplateExpression(part)) part.templateSpans.forEach((span) => sometimes(span.expression, shared))
      else if (staticText(part) === undefined) sometimes(part, shared)
    }
  }
  /** Strings under `node` render only sometimes: each is its own class list beside `shared`. */
  const sometimes = (node: ts.Node, shared: string): void => {
    const parts = joinedParts(node)
    if (parts) return built(node, parts, shared)
    if (ts.isTemplateExpression(node)) return built(node, [node], shared)
    const text = staticText(node, consts)
    if (text !== undefined) return report(node, text, shared)
    // A call that is not a joiner (a helper building its own list) is read on its own.
    if (ts.isCallExpression(node)) return visit(node)
    ts.forEachChild(node, (child) => sometimes(child, shared))
  }
  const visit = (node: ts.Node): void => {
    const parts = joinedParts(node)
    if (parts) return built(node, parts, '')
    if (ts.isTemplateExpression(node)) return built(node, [node], '')
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return report(node, node.text, '')
    // Imports and module specifiers hold paths, not classes.
    if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) return
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return findings
}

type Apply = { classes: string; line: number; dark: boolean }
/** A selector with each `:not(…)` and `:has(…)` taken out: `.dark` inside one never makes the selector the dark theme's. */
function outsideNegations(selector: string): string {
  let out = ''
  for (let i = 0; i < selector.length; ) {
    const group = /^:(?:not|has)\(/i.exec(selector.slice(i))
    if (!group) {
      out += selector[i++]
      continue
    }
    let j = i + group[0].length
    for (let depth = 1; j < selector.length && depth > 0; j++) {
      if (selector[j] === '(') depth++
      else if (selector[j] === ')') depth--
    }
    i = j
  }
  return out
}
/** Whether every selector of a rule (commas inside brackets apart) names the `.dark` class outside a `:not(…)` or `:has(…)`. */
function darkSelector(selector: string): boolean {
  const parts: string[] = []
  let depth = 0
  let start = 0
  for (let i = 0; i < selector.length; i++) {
    if ('([{'.includes(selector[i])) depth++
    else if (')]}'.includes(selector[i])) depth--
    else if (selector[i] === ',' && depth === 0) {
      parts.push(selector.slice(start, i))
      start = i + 1
    }
  }
  parts.push(selector.slice(start))
  return parts.every((part) => /\.dark(?![\w-])/.test(outsideNegations(part)))
}
/**
 * A stylesheet's `@apply` statements, grouped by the rule block they sit directly in (nested blocks apart).
 * Comments are blanked, their newlines kept, so a switched-off class counts for nothing and lines still count.
 */
function applyBlocks(source: string): Apply[][] {
  const text = source.replace(/\/\*[\s\S]*?\*\//g, (comment) => comment.replace(/[^\n]/g, ' '))
  const lineAt = (offset: number) => text.slice(0, offset).split('\n').length
  const blocks: Apply[][] = []
  const open: { applies: Apply[]; dark: boolean }[] = [{ applies: [], dark: false }]
  let from = 0
  // A statement ends at its `;`, or at its block's `}` when it is the last: CSS lets that one go without a `;`.
  for (const match of text.matchAll(/[{}]|@apply\s+([^;{}]+)(?:;|(?=\}))/g)) {
    const at = match.index ?? 0
    const top = open[open.length - 1]
    if (match[0] === '{') open.push({ applies: [], dark: top.dark || darkSelector(text.slice(from, at).split(';').pop() ?? '') })
    else if (match[0] === '}') {
      if (open.length > 1) blocks.push((open.pop() as { applies: Apply[] }).applies)
    } else top.applies.push({ classes: match[1], line: lineAt(at), dark: top.dark })
    from = at + match[0].length
  }
  return [...blocks, ...open.map((block) => block.applies)]
}

/** A stylesheet's rule blocks: the `@apply` statements directly inside one `{ … }` style one element, so they are one class list. */
function applyFindings(source: string, rel: string, check: (own: string, shared?: string) => string[] = unpaired): Finding[] {
  return applyBlocks(source).flatMap((block) =>
    block.flatMap((apply) => {
      const shared = block.filter((other) => other !== apply).map((other) => other.classes).join(' ')
      return check(apply.classes, shared).map((className) => ({ rel, line: apply.line, className }))
    }),
  )
}

/** The colour classes of `classes` on a dark half with no `dark:` variant: the light theme paints them too. */
function bareDark(classes: string): string[] {
  return classes.split(/\s+/).filter(Boolean).filter((token) => {
    const { variants, utility } = splitClass(token)
    const match = PROPERTY.exec(utility)
    return !variants.includes('dark') && !!match && isDarkHalf(match[2])
  })
}

/** Every bare dark half in a file: each string or template's static text, and each stylesheet `@apply` outside the dark theme's blocks. */
function bareDarkFindings(source: string, rel: string): Finding[] {
  if (rel.endsWith('.css')) {
    return applyBlocks(source)
      .flat()
      .filter((apply) => !apply.dark)
      .flatMap((apply) => bareDark(apply.classes).map((className) => ({ rel, line: apply.line, className })))
  }
  const sf = ts.createSourceFile(rel, source, ts.ScriptTarget.Latest, true, scriptKind(rel))
  const findings: Finding[] = []
  const visit = (node: ts.Node): void => {
    if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) return
    const text = staticText(node)
    if (text !== undefined) {
      const line = sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
      for (const className of bareDark(text)) findings.push({ rel, line, className })
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return findings
}

/** Unpaired per file and class. Each entry says why the class stays light; a new one names who owns its fix. */
const THEME_PAIR_RESIDUE: Record<string, Record<string, number>> = {
  // The forced-light modes (`mode="light"`) are light on purpose: no dark twin.
  'components/EarningsNerdLogo.tsx': { 'text-text-primary-light': 1, 'text-brand-strong': 1 },
  'components/EarningsNerdLogoIcon.tsx': { 'text-brand-strong': 1 },
  'components/ThemeToggle.tsx': { 'text-text-secondary-light': 1 }, // the pre-mount placeholder's ink, before the theme is known
  // The destructive fill and its disabled tint are red-700 under a white label in both themes.
  'components/ui/Button.tsx': { 'bg-error-light': 1, 'disabled:bg-error-light/40': 1 },
  'features/auth/components/GoogleSignInButton.tsx': { 'border-border-light': 1 }, // Google's button stays white in both themes, with its light hairline
  'components/CompanyLogo.tsx': { 'text-brand-strong': 1 }, // the company mark's tile is white in both themes (DESIGN_SYSTEM.md §9), so its monogram keeps the light ink
}
const THEME_PAIR_RESIDUE_MAX = { files: 6, classes: 8 }

/** Bare dark halves per file and class: surfaces dark in both themes on purpose. Each entry says why. */
const BARE_DARK_RESIDUE: Record<string, Record<string, number>> = {
  // The forced-dark modes (`mode="dark"`) are dark on purpose, beside the forced-light ones above.
  'components/EarningsNerdLogo.tsx': { 'text-text-primary-dark': 1, 'text-brand-strong-dark': 1 },
  'components/EarningsNerdLogoIcon.tsx': { 'text-brand-strong-dark': 1 },
  // The debug payload panel is fixed-dark in both themes (its own comment says so).
  'features/summaries/components/SummaryDisplay.tsx': { 'bg-panel-dark': 1, 'border-border-dark': 1, 'text-text-primary-dark': 2 },
}
const BARE_DARK_RESIDUE_MAX = { files: 3, classes: 7 }

/** What a residue keyed by file and class gets wrong against the scan's findings. */
function residueProblems(found: Finding[], residue: Record<string, Record<string, number>>, name: string, what: string): string[] {
  const byFile = new Map<string, Map<string, Finding[]>>()
  for (const f of found) {
    const byClass = byFile.get(f.rel) ?? new Map<string, Finding[]>()
    byClass.set(f.className, [...(byClass.get(f.className) ?? []), f])
    byFile.set(f.rel, byClass)
  }
  const problems: string[] = []
  for (const file of new Set([...byFile.keys(), ...Object.keys(residue)])) {
    const byClass = byFile.get(file)
    if (!byClass) {
      problems.push(`${file}: none left, delete it from ${name}`)
      continue
    }
    const listed = residue[file] ?? {}
    for (const className of new Set([...byClass.keys(), ...Object.keys(listed)])) {
      const list = byClass.get(className) ?? []
      const allowed = listed[className] ?? 0
      const lines = list.map((f) => `${f.rel}:${f.line} ${f.className}`)
      if (list.length > allowed) problems.push(`${file} ${className}: ${list.length} ${what}, ${allowed} in ${name}\n  ${lines.join('\n  ')}`)
      else if (list.length < allowed) problems.push(`${file} ${className}: ${list.length} ${what}, ${allowed} in ${name}: lower the count, or delete it at none`)
    }
  }
  return problems
}

const ALL_FILES = SCAN_DIRS.flatMap((dir) => allFiles(path.join(ROOT, dir)))
const FILES = ALL_FILES.filter(isSource)
const rel = (file: string) => path.relative(ROOT, file).split(path.sep).join('/')

const findingsIn = (file: string): Finding[] => {
  const source = readFileSync(file, 'utf8')
  return file.endsWith('.css') ? applyFindings(source, rel(file)) : themePairFindings(source, rel(file))
}

describe('every theme token is a light/dark pair: a light half has its dark: twin, a dark half sits under dark: (DESIGN_SYSTEM.md §2)', () => {
  const findings = FILES.flatMap(findingsIn)
  const bareFindings = FILES.flatMap((file) => bareDarkFindings(readFileSync(file, 'utf8'), rel(file)))

  it('reads the app and its stylesheet (a scan that finds no source must not pass)', () => {
    expect(
      ALL_FILES.filter((file) => !READ.test(file) && !(path.extname(file) in NOT_READ)).map(rel),
      'a file the scan does not read: read its extension (READ), or list it in NOT_READ with why it holds no class list',
    ).toEqual([])
    expect(FILES.length).toBeGreaterThan(300)
    expect(FILES.map(rel)).toEqual(
      expect.arrayContaining(['features/auth/components/PasswordField.tsx', 'components/ui/Notice.tsx', 'app/globals.css']),
    )
    // Every token the app pairs is a colour this scan knows, so no twin is refused for a name it lacks.
    expect(['error-light', 'text-secondary-light', 'border-light', 'brand-weak', 'white', 'red-700'].filter((v) => !isColour(v))).toEqual([])
    // The light halves come from the config, the suffixless pairs included.
    expect(['error-light', 'border-light', 'brand', 'brand-strong', 'brand-weak', 'brand-border', 'gain', 'loss-soft'].filter((v) => !isLightHalf(v))).toEqual([])
    expect(['brand-dark', 'brand-weak-dark', 'white', 'chart-1', 'brand-emphasis'].filter(isLightHalf)).toEqual([])
    // And the dark halves, which a class outside `dark:` must not name.
    expect(['background-dark', 'brand-dark', 'brand-weak-dark', 'text-primary-dark', 'warning-dark', 'brand-fill-dark'].filter((v) => !isDarkHalf(v))).toEqual([])
    expect(['background-light', 'brand', 'white', 'black', 'chart-1', 'brand-emphasis'].filter(isDarkHalf)).toEqual([])
  })

  it('every unpaired class is in the residue, and every residue count is current', () => {
    expect(residueProblems(findings, THEME_PAIR_RESIDUE, 'THEME_PAIR_RESIDUE', 'unpaired'), 'give each light-half class its dark: twin in the same class list').toEqual([])
  })

  it('keeps tertiary and secondary on their own rungs in dark: no tertiary-light twinned with secondary-dark, or the reverse', () => {
    const crossed = FILES.flatMap((file) => {
      const source = readFileSync(file, 'utf8')
      return file.endsWith('.css') ? applyFindings(source, rel(file), crossedRungs) : themePairFindings(source, rel(file), crossedRungs)
    })
    expect(crossed.map((f) => `${f.rel}:${f.line} ${f.className}`), 'twin text-text-tertiary-light with dark:text-text-tertiary-dark').toEqual([])
  })

  it('reads a crossed rung wherever a twin is read (a self-check on a fixed source)', () => {
    const src = [
      "const caption = 'text-xs text-text-tertiary-light dark:text-text-secondary-dark'",
      "const body = 'text-text-secondary-light dark:text-text-tertiary-dark'",
      "const field = cx('placeholder:text-text-tertiary-light', 'dark:placeholder:text-text-secondary-dark')",
      // On its own rung, or twinned under another variant, nothing is crossed.
      "const muted = 'text-text-tertiary-light dark:text-text-tertiary-dark'",
      "const read = 'text-text-secondary-light dark:text-text-secondary-dark hover:text-text-tertiary-light dark:hover:text-text-tertiary-dark'",
      "const other = 'text-text-tertiary-light dark:text-text-tertiary-dark dark:hover:text-text-secondary-dark'",
    ].join('\n')
    expect(themePairFindings(src, 'probe.tsx', crossedRungs).map((f) => `${f.line} ${f.className}`)).toEqual([
      '1 text-text-tertiary-light',
      '2 text-text-secondary-light',
      '3 placeholder:text-text-tertiary-light',
    ])
    const css = ':is(.markdown-body) a { @apply underline decoration-text-tertiary-light;\n  @apply dark:decoration-text-secondary-dark; }'
    expect(applyFindings(css, 'probe.css', crossedRungs).map((f) => `${f.line} ${f.className}`)).toEqual(['1 decoration-text-tertiary-light'])
  })

  it('gives every dark hover a visible step: secondary never turns only primary under the pointer', () => {
    const faint = FILES.flatMap((file) => {
      const source = readFileSync(file, 'utf8')
      return file.endsWith('.css') ? applyFindings(source, rel(file), faintHovers) : themePairFindings(source, rel(file), faintHovers)
    })
    expect(faint.map((f) => `${f.rel}:${f.line} ${f.className}`), 'step to dark:hover:text-white, or add a hover fill, border or underline').toEqual([])
  })

  it('reads a faint dark hover wherever a twin is read (a self-check on a fixed source)', () => {
    const src = [
      "const link = 'text-text-secondary-light hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:text-text-primary-dark'",
      "const split = cx('text-text-secondary-light dark:text-text-secondary-dark', 'dark:hover:!text-text-heading-dark')",
      // A brighter step, or a hover cue that is not ink, is visible in dark.
      "const bright = 'text-text-secondary-light hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:text-white'",
      "const tinted = 'text-text-secondary-light dark:text-text-secondary-dark hover:bg-brand-weak dark:hover:bg-white/5 dark:hover:text-text-primary-dark'",
      "const lined = 'text-text-secondary-light dark:text-text-secondary-dark hover:underline dark:hover:text-text-primary-dark'",
      // A control that rests in another ink is not this rule's.
      "const quiet = 'text-text-tertiary-light dark:text-text-tertiary-dark dark:hover:text-text-primary-dark'",
      // A cue dark never shows: the toast close's light tint lost to its forced dark rest, and its dark hover fill
      // repeated that rest; a plain hover fill loses to any dark rest fill.
      "const toast = '!bg-panel-light !text-text-secondary-light hover:!bg-brand-weak hover:!text-text-primary-light dark:!bg-panel-dark dark:!text-text-secondary-dark dark:hover:!bg-panel-dark dark:hover:!text-text-primary-dark'",
      "const lightTint = 'bg-panel-light dark:bg-panel-dark text-text-secondary-light dark:text-text-secondary-dark hover:bg-brand-weak dark:hover:text-text-primary-dark'",
      // The resting ink through a string constant's slot is read too.
      "const MUTED = 'text-text-secondary-light dark:text-text-secondary-dark'",
      "const nav = `rounded hover:text-text-primary-light dark:hover:text-text-primary-dark ${MUTED}`",
      // A plain hover fill shows in dark when no dark rest or dark hover of that property overrules it.
      "const plainTint = 'text-text-secondary-light dark:text-text-secondary-dark hover:bg-white/5 dark:hover:text-text-primary-dark'",
    ].join('\n')
    expect(themePairFindings(src, 'probe.tsx', faintHovers).map((f) => `${f.line} ${f.className}`)).toEqual([
      '1 dark:hover:text-text-primary-dark',
      '2 dark:hover:!text-text-heading-dark',
      '7 dark:hover:!text-text-primary-dark',
      '8 dark:hover:text-text-primary-dark',
      '10 dark:hover:text-text-primary-dark',
    ])
  })

  it('every dark half outside a dark: variant is in BARE_DARK_RESIDUE, and every count is current', () => {
    expect(
      residueProblems(bareFindings, BARE_DARK_RESIDUE, 'BARE_DARK_RESIDUE', 'bare'),
      'put the dark half under dark: beside its light twin (ring-background-light dark:ring-background-dark), or list an always-dark surface',
    ).toEqual([])
  })

  it('each cap equals its residue, so a shrink moves it down in the same commit', () => {
    const residues = [
      ['THEME_PAIR_RESIDUE', THEME_PAIR_RESIDUE, THEME_PAIR_RESIDUE_MAX],
      ['BARE_DARK_RESIDUE', BARE_DARK_RESIDUE, BARE_DARK_RESIDUE_MAX],
    ] as const
    for (const [name, residue, max] of residues) {
      const counts = Object.values(residue).flatMap((byClass) => Object.values(byClass))
      expect(counts.filter((n) => !Number.isInteger(n) || n < 1), `${name}: a listed count is a whole number of classes: delete an entry at none`).toEqual([])
      expect(Object.keys(residue).length, `${name}_MAX.files must equal the files in ${name}: lower it with the list, never raise it`).toBe(max.files)
      expect(
        counts.reduce((sum, n) => sum + n, 0),
        `${name}_MAX.classes must equal the classes in ${name}: lower it with the list, never raise it`,
      ).toBe(max.classes)
    }
  })

  it('the scan catches what it is for (a self-check on a fixed source)', () => {
    const src = [
      "const BARS = ['bg-error-light dark:bg-error-dark', 'bg-warning-light']",
      "const row = 'hover:bg-brand-weak dark:hover:bg-white/5 text-text-secondary-light'",
      // A twin under a condition renders only sometimes, so it pairs nothing.
      "const chip = cx('border-error-light/25 aria-disabled:text-warning-light/50', cond && 'dark:border-error-dark/25 dark:aria-disabled:text-warning-dark/50')",
      "const joined = ['hover:border-flat-light', 'dark:hover:border-flat-dark'].join(' ')",
      'export function Probe({ on }: { on: boolean }) {',
      "  return <p className={`h-1 ${on ? 'dark:text-white' : ''} text-success-light`}>x</p>",
      '}',
      "const wrongVariant = 'hover:text-error-light dark:text-error-dark'",
      // A dark: utility that is not a colour, or is a light half itself, is not a twin.
      "const size = 'text-text-secondary-light dark:text-sm'",
      "const width = 'border border-border-light dark:border-0'",
      "const image = 'bg-error-light dark:bg-none'",
      "const align = 'text-text-secondary-light dark:text-center'",
      "const self = 'bg-error-light dark:bg-error-light ring-brand-border dark:ring-brand-border'",
      // A side border is its own property; a colour twin on that side pairs it.
      "const side = 'border-t border-t-border-light dark:border-t-border-dark ring-offset-background-light dark:ring-offset-background-dark'",
      // A light half without the suffix is read; UserMenu's rows without their dark hover.
      "const menu = 'text-brand-strong dark:text-brand-strong-dark hover:bg-brand-weak'",
      // A conditional light class takes its twin from what always renders, and a conditional joiner
      // pairs its own strings; a `+` chain is one list.
      "const lit = cx('dark:text-white', on && 'text-success-light')",
      "const card = cx('border border-border-light dark:border-white/10', on && cx('hover:border-brand-border', 'dark:hover:border-brand-border-dark'))",
      "const chain = 'border-brand-border bg-brand-weak ' + 'dark:border-brand-border-dark dark:bg-brand-weak-dark'",
      // A twin in another arm of a ternary, across an `&&` or under another object key never renders with the
      // class: each arm and each key is a list of its own (the principal review's five shapes).
      "const arm = cx(on ? 'bg-error-light' : 'bg-success-light dark:bg-success-dark')",
      "const and = cx('bg-error-light', on && 'dark:bg-error-dark')",
      "const keys = clsx({ 'bg-error-light': a, 'dark:bg-error-dark': b })",
      "const arms = cn('p-2', isOpen ? 'text-text-primary-light' : 'dark:text-text-primary-dark')",
      "const listed = [on ? 'border-border-light' : 'dark:border-border-dark', 'p-2'].join(' ')",
      // An arm or a key paired within itself is paired; a type-hinted arbitrary colour is a twin.
      "const own = cx(on ? 'bg-error-light dark:bg-error-dark' : 'bg-success-light dark:bg-success-dark', { 'border-border-light dark:border-white/10': a })",
      "const typed = 'text-text-primary-light dark:text-[color:var(--ink)]'",
    ].join('\n')
    expect(themePairFindings(src, 'probe.tsx').map((f) => `${f.line} ${f.className}`)).toEqual([
      '1 bg-warning-light',
      '2 text-text-secondary-light',
      '3 border-error-light/25',
      '3 aria-disabled:text-warning-light/50',
      // The template's static part renders always; its slot only sometimes.
      '6 text-success-light',
      // The twin must sit under the same variants: dark:text-… is not dark:hover:text-….
      '8 hover:text-error-light',
      '9 text-text-secondary-light',
      '10 border-border-light',
      '11 bg-error-light',
      '12 text-text-secondary-light',
      '13 bg-error-light',
      '13 ring-brand-border',
      '15 hover:bg-brand-weak',
      '19 bg-error-light',
      '20 bg-error-light',
      '21 bg-error-light',
      '22 text-text-primary-light',
      '23 border-border-light',
    ])
    const css = [
      '.a { @apply text-text-primary-light dark:text-text-primary-dark; }',
      '.b { @apply border-b border-border-light px-3; }',
      // One rule block is one element: a twin on another @apply line of the block pairs it (#1326's prose links).
      ':is(.markdown-body) a { @apply underline decoration-text-tertiary-light;',
      '  @apply hover:text-brand-strong;',
      '  @apply dark:decoration-text-secondary-dark dark:hover:text-brand-strong-dark; }',
      // A twin in another block, a nested block or a comment pairs nothing.
      '.d { @apply bg-error-light; } .e { @apply dark:bg-error-dark; }',
      '.f { @apply border-border-light; /* @apply dark:border-border-dark; */ }',
      '@media (min-width: 640px) { .g { @apply text-text-secondary-light; &:hover { @apply dark:text-text-secondary-dark; } } }',
      // The last statement of a block may go without its `;` (the review of #1310); a twin so written pairs too.
      '.h { @apply bg-error-light }',
      '.i { @apply bg-error-light; @apply dark:bg-error-dark }',
    ].join('\n')
    expect(applyFindings(css, 'probe.css').map((f) => `${f.line} ${f.className}`)).toEqual([
      '2 border-border-light',
      '6 bg-error-light',
      '7 border-border-light',
      '8 text-text-secondary-light',
      '9 bg-error-light',
    ])
    // A dark half outside `dark:` paints in the light theme: under hover or a condition too.
    const dark = [
      "const dot = 'ring-2 ring-background-dark'",
      "const pairedDot = 'ring-2 ring-background-light dark:ring-background-dark'",
      "const tint = 'hover:bg-warning-dark/15 dark:hover:bg-warning-dark/25'",
      "const scoped = 'dark:hover:bg-warning-dark/15 hover:dark:text-brand-strong-dark'",
      'export function Probe({ on }: { on: boolean }) {',
      "  return <p className={`p-2 ${on ? 'text-text-primary-dark' : ''}`}>x</p>",
      '}',
      "const suffixless = 'bg-brand-dark/15'",
      // Not a dark half: white, a palette step, a shadow token named for a ring.
      "const other = 'text-white bg-slate-900 shadow-ring-brand-dark'",
      // A dark token with no light sibling is the dark theme's too (the review of #1310): bare, it paints the light theme.
      "const fill = 'bg-brand-fill-dark text-white'",
      "const pressed = 'dark:active:bg-brand-fill-dark'",
    ].join('\n')
    expect(bareDarkFindings(dark, 'probe.tsx').map((f) => `${f.line} ${f.className}`)).toEqual([
      '1 ring-background-dark',
      '3 hover:bg-warning-dark/15',
      '6 text-text-primary-dark',
      '8 bg-brand-dark/15',
      '10 bg-brand-fill-dark',
    ])
    // In a stylesheet the dark theme is a `.dark` block: every selector of it, or a block inside one.
    const darkCss = [
      '.a { @apply bg-panel-dark; }',
      '.dark .b { @apply bg-panel-dark text-text-primary-dark; }',
      '@media (min-width: 640px) { .dark .c, .d { @apply border-border-dark; } }',
      '.e { @apply dark:bg-panel-dark; /* @apply bg-panel-dark; */ }',
      '.f { @apply text-text-primary-light; .dark & { @apply text-text-primary-dark; } }',
      '.dark-panel { @apply bg-panel-dark; } :is(.dark .g, .dark .h) { @apply bg-panel-dark; }',
      // The review of #1310's forms: a last statement with no `;`, and `.dark` inside a :not() or a :has(), which
      // select the light theme; `.dark` outside one still is the dark theme's.
      '.i { @apply bg-panel-dark }',
      'html:not(.dark) .j { @apply bg-panel-dark; }',
      '.k:has(.dark) { @apply text-text-primary-dark; }',
      '.dark .l:not(.m) { @apply bg-panel-dark; }',
    ].join('\n')
    expect(bareDarkFindings(darkCss, 'probe.css').map((f) => `${f.line} ${f.className}`)).toEqual([
      '1 bg-panel-dark',
      '3 border-border-dark',
      '6 bg-panel-dark',
      '7 bg-panel-dark',
      '8 bg-panel-dark',
      '9 text-text-primary-dark',
    ])
  })
})
