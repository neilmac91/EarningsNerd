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
 * A class list is the strings that always render together: one string, the static parts of one template,
 * or the unconditional strings of one call to the class joiners (`cx`, `clsx`, `cn`), one inline
 * `[…].join(…)` or one `+` chain. A string under a condition (`on && '…'`, a ternary branch, a template
 * slot) renders only sometimes, so it is a class list of its own beside those unconditional strings: its
 * light class may take its twin from them, but nothing takes a twin from it. A joiner nested under a
 * condition pairs its own unconditional strings the same way. A call that is not a joiner (a helper
 * building its own list) is read on its own, and a value in a lookup table (`STRENGTH_COLORS[score]`) is a
 * class list of its own and carries its own twin. In a stylesheet under the scanned directories
 * (app/globals.css), the `@apply` statements of one rule block, from its `{` to its `}` with nested blocks
 * apart and comments removed, style one element, so together they are one class list.
 *
 * THEME_PAIR_RESIDUE holds what the scan finds, counted per file, and THEME_PAIR_RESIDUE_MAX equals its
 * totals: a new unpaired class fails (an unlisted file, or a listed count that rises), a fixed one fails
 * until its count is lowered or its line deleted, and the cap moves down with the list in the same commit,
 * so a shrink leaves no headroom for a later class to refill.
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
/** A colour utility on a light half, with an optional opacity (`/50`, `/[0.06]`): its property. */
function lightProperty(utility: string): string | undefined {
  const match = PROPERTY.exec(utility)
  return match && isLightHalf(match[2]) ? match[1] : undefined
}

type Finding = { rel: string; line: number; className: string }

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) return entry.name === 'node_modules' ? [] : sourceFiles(full)
    return /\.(tsx?|css)$/.test(entry.name) && !/\.(spec|test)\.tsx?$/.test(entry.name) && !entry.name.endsWith('.d.ts') ? [full] : []
  })
}

function splitClass(token: string): { variants: string[]; utility: string } {
  const parts = token.split(':')
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

/** A string's text, or the static text of a template (its slots apart). */
function staticText(node: ts.Node): string | undefined {
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return node.text
  if (ts.isTemplateExpression(node)) return [node.head.text, ...node.templateSpans.map((span) => span.literal.text)].join(' ')
  return undefined
}

function themePairFindings(source: string, rel: string): Finding[] {
  const sf = ts.createSourceFile(rel, source, ts.ScriptTarget.Latest, true, rel.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const findings: Finding[] = []
  const report = (node: ts.Node, own: string, shared: string) => {
    const line = sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
    for (const className of unpaired(own, shared)) findings.push({ rel, line, className })
  }
  /** One built className: its unconditional strings are one list, and each conditional string sits beside them. */
  const built = (node: ts.Node, parts: readonly ts.Node[], context: string) => {
    const always = parts.map(staticText).filter((text): text is string => text !== undefined)
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
    const text = staticText(node)
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

/** A stylesheet's rule blocks: the `@apply` statements directly inside one `{ … }` style one element, so they are one class list. */
function applyFindings(source: string, rel: string): Finding[] {
  // Comments are blanked, their newlines kept, so a switched-off twin pairs nothing and lines still count.
  const text = source.replace(/\/\*[\s\S]*?\*\//g, (comment) => comment.replace(/[^\n]/g, ' '))
  const lineAt = (offset: number) => text.slice(0, offset).split('\n').length
  type Apply = { classes: string; line: number }
  const findings: Finding[] = []
  const close = (block: Apply[]) => {
    for (const apply of block) {
      const shared = block.filter((other) => other !== apply).map((other) => other.classes).join(' ')
      for (const className of unpaired(apply.classes, shared)) findings.push({ rel, line: apply.line, className })
    }
  }
  const open: Apply[][] = [[]]
  for (const match of text.matchAll(/[{}]|@apply\s+([^;{}]+);/g)) {
    if (match[0] === '{') open.push([])
    else if (match[0] === '}') close(open.length > 1 ? (open.pop() as Apply[]) : [])
    else open[open.length - 1].push({ classes: match[1], line: lineAt(match.index ?? 0) })
  }
  open.forEach(close)
  return findings
}

/** Unpaired per file, re-seeded on 2026-10-14 for the light halves without the suffix. Each line names who owns the fix, or why the class stays light. */
const THEME_PAIR_RESIDUE: Record<string, number> = {
  // The native checkboxes #1289's Checkbox replaces: the admin invite's checked ink (text-brand-strong) alone,
  // and the consent dialog's three, each with border-border-light and that ink alone. The later of #1289 and
  // #1310 to land deletes these two lines and lowers the cap to { files: 12, classes: 15 }.
  'app/admin/invites/page.tsx': 1,
  'components/CookieConsent.tsx': 6,
  // The forced-light modes (`mode="light"`) are light on purpose: no dark twin.
  'components/EarningsNerdLogo.tsx': 2,
  'components/EarningsNerdLogoIcon.tsx': 1,
  'components/ThemeToggle.tsx': 1, // the pre-mount placeholder's ink, before the theme is known
  'components/ui/Button.tsx': 2, // the destructive fill and its disabled tint are red-700 under a white label in both themes
  'features/auth/components/GoogleSignInButton.tsx': 1, // Google's button stays white in both themes, with its light hairline
  // tasks/todo.md E53: brand-border hairlines and the interactive card's pressed fill with no dark twin,
  // so dark mode draws the light theme's pale sage on navy.
  'app/waitlist/page.tsx': 1,
  'components/ui/Card.tsx': 1,
  'features/filings/components/copilot/AskCopilotRail.tsx': 1,
  'features/filings/components/copilot/AskFilingCallout.tsx': 1,
  'features/filings/components/copilot/CopilotMessage.tsx': 2,
  'features/filings/components/copilot/CopilotTeaser.tsx': 1,
  'features/summaries/components/SummaryDisplay.tsx': 1,
}
const THEME_PAIR_RESIDUE_MAX = { files: 14, classes: 22 }

const FILES = SCAN_DIRS.flatMap((dir) => sourceFiles(path.join(ROOT, dir)))
const rel = (file: string) => path.relative(ROOT, file).split(path.sep).join('/')

const findingsIn = (file: string): Finding[] => {
  const source = readFileSync(file, 'utf8')
  return file.endsWith('.css') ? applyFindings(source, rel(file)) : themePairFindings(source, rel(file))
}

describe('every light-half theme token has its dark: twin (DESIGN_SYSTEM.md §2)', () => {
  const findings = FILES.flatMap(findingsIn)

  it('reads the app and its stylesheet (a scan that finds no source must not pass)', () => {
    expect(FILES.length).toBeGreaterThan(300)
    expect(FILES.map(rel)).toEqual(
      expect.arrayContaining(['features/auth/components/PasswordField.tsx', 'components/ui/Notice.tsx', 'app/globals.css']),
    )
    // Every token the app pairs is a colour this scan knows, so no twin is refused for a name it lacks.
    expect(['error-light', 'text-secondary-light', 'border-light', 'brand-weak', 'white', 'red-700'].filter((v) => !isColour(v))).toEqual([])
    // The light halves come from the config, the suffixless pairs included.
    expect(['error-light', 'border-light', 'brand', 'brand-strong', 'brand-weak', 'brand-border', 'gain', 'loss-soft'].filter((v) => !isLightHalf(v))).toEqual([])
    expect(['brand-dark', 'brand-weak-dark', 'white', 'chart-1', 'brand-emphasis'].filter(isLightHalf)).toEqual([])
  })

  it('every unpaired class is in the residue, and every residue count is current', () => {
    const byFile = new Map<string, Finding[]>()
    for (const f of findings) byFile.set(f.rel, [...(byFile.get(f.rel) ?? []), f])
    const problems: string[] = []
    for (const [file, list] of byFile) {
      const allowed = THEME_PAIR_RESIDUE[file] ?? 0
      const lines = list.map((f) => `${f.rel}:${f.line} ${f.className}`)
      if (list.length > allowed) problems.push(`${file}: ${list.length} unpaired, ${allowed} in THEME_PAIR_RESIDUE\n  ${lines.join('\n  ')}`)
      else if (list.length < allowed) problems.push(`${file}: ${list.length} unpaired, ${allowed} in THEME_PAIR_RESIDUE: lower the count`)
    }
    for (const file of Object.keys(THEME_PAIR_RESIDUE)) {
      if (!byFile.has(file)) problems.push(`${file}: none left, delete it from THEME_PAIR_RESIDUE`)
    }
    expect(problems, 'give each light-half class its dark: twin in the same class list').toEqual([])
  })

  it('the cap equals the residue, so a shrink moves it down in the same commit', () => {
    const counts = Object.values(THEME_PAIR_RESIDUE)
    expect(counts.length, 'THEME_PAIR_RESIDUE_MAX.files must equal the files in THEME_PAIR_RESIDUE: lower it with the list, never raise it').toBe(
      THEME_PAIR_RESIDUE_MAX.files,
    )
    expect(
      counts.reduce((sum, n) => sum + n, 0),
      'THEME_PAIR_RESIDUE_MAX.classes must equal the classes in THEME_PAIR_RESIDUE: lower it with the list, never raise it',
    ).toBe(THEME_PAIR_RESIDUE_MAX.classes)
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
    ].join('\n')
    expect(applyFindings(css, 'probe.css').map((f) => `${f.line} ${f.className}`)).toEqual([
      '2 border-border-light',
      '6 bg-error-light',
      '7 border-border-light',
      '8 text-text-secondary-light',
    ])
  })
})
