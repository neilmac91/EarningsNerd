import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * Every colour is a light/dark pair (DESIGN_SYSTEM.md §1, CLAUDE.md rules 11 and 12). The ESLint design
 * rules stop raw hex and palette colours; nothing stopped a theme token from shipping without its dark
 * half: the password strength meter's bars were `bg-error-light`, `bg-warning-light` and
 * `bg-success-light` alone, so dark mode drew the light theme's colours on navy (the 2026-10 audit, UA-44).
 *
 * The rule: a colour class whose token ends in `-light` (`bg-error-light`, `hover:border-flat-light`,
 * `text-text-secondary-light/50`) has a `dark:` twin in the same class list: a `dark:` class on the same
 * property (bg, text, border, ring, …) under the same other variants (`hover:`, `aria-disabled:`, in any
 * order). The twin's value is free (`dark:hover:bg-white/5` twins `hover:bg-brand-weak`'s row, and
 * `dark:bg-brand-dark/15` twins `bg-brand-strong/10`); only its presence is checked.
 *
 * A class list is one string or template literal, or every static string inside one call to the class
 * joiners (`cx`, `clsx`, `cn`) or one inline `[…].join(…)`, since those build a single className. A value in
 * a lookup table (`STRENGTH_COLORS[score]`) is a class list of its own and carries its own twin.
 *
 * THEME_PAIR_RESIDUE holds what the scan found on the day it landed, counted per file. It only shrinks: a
 * new unpaired class fails (an unlisted file, or a listed count that rises), a fixed one fails until its
 * count is lowered or its line deleted, and the list is capped at the seed (THEME_PAIR_RESIDUE_MAX).
 */
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']

const PROPERTIES = 'bg|text|border|ring|fill|stroke|from|via|to|divide|outline|decoration|accent|caret|placeholder|shadow'
/** A colour utility on a `-light` theme token, with an optional opacity (`/50`, `/[0.06]`). */
const LIGHT_TOKEN = new RegExp(`^(${PROPERTIES})-[a-z0-9-]+-light(?:/\\S+)?$`)
const PROPERTY = new RegExp(`^(${PROPERTIES})-`)
const JOINERS = new Set(['cx', 'clsx', 'cn'])

type Finding = { rel: string; line: number; className: string }

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) return entry.name === 'node_modules' ? [] : sourceFiles(full)
    return /\.tsx?$/.test(entry.name) && !/\.(spec|test)\.tsx?$/.test(entry.name) && !entry.name.endsWith('.d.ts') ? [full] : []
  })
}

function splitClass(token: string): { variants: string[]; utility: string } {
  const parts = token.split(':')
  return { variants: parts.slice(0, -1), utility: parts[parts.length - 1].replace(/^!/, '') }
}

/** The unpaired `-light` classes in one class list. */
function unpaired(classList: string): string[] {
  const classes = classList.split(/\s+/).filter(Boolean)
  const darkKeys = new Set(
    classes.flatMap((token) => {
      const { variants, utility } = splitClass(token)
      const property = PROPERTY.exec(utility)?.[1]
      if (!variants.includes('dark') || !property) return []
      return [`${variants.filter((v) => v !== 'dark').sort().join(':')}|${property}`]
    }),
  )
  return classes.filter((token) => {
    const { variants, utility } = splitClass(token)
    const match = LIGHT_TOKEN.exec(utility)
    if (variants.includes('dark') || !match) return false
    return !darkKeys.has(`${[...variants].sort().join(':')}|${match[1]}`)
  })
}

/** Every static string under a node, template chunks included. */
function staticStrings(node: ts.Node): string[] {
  const out: string[] = []
  const visit = (n: ts.Node): void => {
    if (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)) out.push(n.text)
    else if (ts.isTemplateExpression(n)) {
      out.push(n.head.text, ...n.templateSpans.map((span) => span.literal.text))
      n.templateSpans.forEach((span) => visit(span.expression))
    } else ts.forEachChild(n, visit)
  }
  visit(node)
  return out
}

/** A call that joins its strings into one className: `cx(…)`, `clsx(…)`, `cn(…)` or `[…].join(…)`. */
function isJoiner(node: ts.Node): node is ts.CallExpression {
  if (!ts.isCallExpression(node)) return false
  const callee = node.expression
  if (ts.isIdentifier(callee)) return JOINERS.has(callee.text)
  return ts.isPropertyAccessExpression(callee) && callee.name.text === 'join' && ts.isArrayLiteralExpression(callee.expression)
}

function themePairFindings(source: string, rel: string): Finding[] {
  const sf = ts.createSourceFile(rel, source, ts.ScriptTarget.Latest, true, rel.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const findings: Finding[] = []
  const report = (node: ts.Node, classList: string) => {
    const line = sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
    for (const className of unpaired(classList)) findings.push({ rel, line, className })
  }
  const visit = (node: ts.Node): void => {
    if (isJoiner(node)) {
      report(node, staticStrings(node).join(' '))
      // A nested call that is not a joiner (a helper building its own list) is read on its own.
      const nested = (n: ts.Node): void => {
        if (ts.isCallExpression(n) && n !== node && !isJoiner(n)) visit(n)
        else ts.forEachChild(n, nested)
      }
      ts.forEachChild(node, nested)
      return
    }
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return report(node, node.text)
    if (ts.isTemplateExpression(node)) {
      report(node, [node.head.text, ...node.templateSpans.map((span) => span.literal.text)].join(' '))
      node.templateSpans.forEach((span) => visit(span.expression))
      return
    }
    // Imports and module specifiers hold paths, not classes.
    if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) return
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return findings
}

/** Unpaired on 2026-10-13, per file. Each line names who owns the fix, or why the class stays light. */
const THEME_PAIR_RESIDUE: Record<string, number> = {
  'components/CookieConsent.tsx': 3, // the consent dialog's checkboxes: border-border-light alone (brand-chrome-primitives' Checkbox)
  'components/EarningsNerdLogo.tsx': 1, // the forced-light mode (`mode="light"`) is light on purpose: no dark twin
  'components/ThemeToggle.tsx': 1, // the pre-mount placeholder's ink, before the theme is known
  'components/ui/Button.tsx': 1, // the destructive fill is red-700 under a white label in both themes
  'features/auth/components/GoogleSignInButton.tsx': 1, // Google's button stays white in both themes, with its light hairline
}
const THEME_PAIR_RESIDUE_MAX = { files: 5, classes: 7 }

const FILES = SCAN_DIRS.flatMap((dir) => sourceFiles(path.join(ROOT, dir)))
const rel = (file: string) => path.relative(ROOT, file).split(path.sep).join('/')

describe('every -light theme token has its dark: twin (DESIGN_SYSTEM.md §1)', () => {
  const findings = FILES.flatMap((file) => themePairFindings(readFileSync(file, 'utf8'), rel(file)))

  it('reads the app (a scan that finds no source must not pass)', () => {
    expect(FILES.length).toBeGreaterThan(300)
    expect(FILES.map(rel)).toEqual(expect.arrayContaining(['features/auth/components/PasswordField.tsx', 'components/ui/Notice.tsx']))
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
    expect(problems, 'give each -light class its dark: twin in the same class list').toEqual([])
  })

  it('the residue only shrinks', () => {
    const counts = Object.values(THEME_PAIR_RESIDUE)
    expect(counts.length, 'THEME_PAIR_RESIDUE gained a file').toBeLessThanOrEqual(THEME_PAIR_RESIDUE_MAX.files)
    expect(counts.reduce((sum, n) => sum + n, 0), 'THEME_PAIR_RESIDUE gained a class').toBeLessThanOrEqual(THEME_PAIR_RESIDUE_MAX.classes)
  })

  it('the scan catches what it is for (a self-check on a fixed source)', () => {
    const src = [
      "const BARS = ['bg-error-light dark:bg-error-dark', 'bg-warning-light']",
      "const row = 'hover:bg-brand-weak dark:hover:bg-white/5 text-text-secondary-light'",
      "const chip = cx('border-error-light/25 aria-disabled:text-warning-light/50', cond && 'dark:border-error-dark/25 dark:aria-disabled:text-warning-dark/50')",
      "const joined = ['hover:border-flat-light', 'dark:hover:border-flat-dark'].join(' ')",
      'export function Probe({ on }: { on: boolean }) {',
      "  return <p className={`h-1 ${on ? 'text-success-light' : ''} dark:text-white`}>x</p>",
      '}',
      "const wrongVariant = 'hover:text-error-light dark:text-error-dark'",
    ].join('\n')
    expect(themePairFindings(src, 'probe.tsx').map((f) => `${f.line} ${f.className}`)).toEqual([
      '1 bg-warning-light',
      '2 text-text-secondary-light',
      // A conditional string inside a template is a class list of its own.
      '6 text-success-light',
      // The twin must sit under the same variants: dark:text-… is not dark:hover:text-….
      '8 hover:text-error-light',
    ])
  })
})
