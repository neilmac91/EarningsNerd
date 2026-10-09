import { readFileSync } from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * Every control in the site chrome shows the brand focus ring, never the browser's default outline
 * (EN-05c, rule 12). There is no global :focus-visible rule (globals.css), so a control without the
 * recipe falls back to Chromium's `outline: auto 1px`: the logo link, the theme toggle, the mobile
 * menu button and its links did, beside nav links that carry the sage ring. The recipe is
 * DESIGN_SYSTEM.md §4's "Focus ring": `focus-visible:outline-none focus-visible:shadow-ring-brand
 * dark:focus-visible:shadow-ring-brand-dark`. The skip link's reveal uses the same triple on `focus:`,
 * since it must show on any focus.
 *
 * The scan reads the TypeScript AST of each chrome file below and checks every element a user can Tab
 * to (a, button, input, select, textarea, summary, next/link's Link, or anything with a tabIndex of 0
 * or more). Its className must carry the whole triple, or be the DS factory `buttonVariants(…)`, which
 * composes it (pinned below). A className the scan cannot read (a variable, a call to anything else)
 * fails: the ring has to be visible in the file. Dynamic `${…}` parts of a template are ignored, so the
 * triple must sit in the template's static text. The DS components (<Button>, <Input>) are not scanned
 * here: they own the recipe.
 *
 * A checkbox or radio also takes off @tailwindcss/forms' own focus ring (`focus:ring-0 focus:ring-offset-0`):
 * the plugin's base style draws a blue (#2563eb) ring with a white offset on any focus, and the shadow
 * utilities compose with it, so the triple alone shows the brand ring inside a blue one. A control that
 * is statically `disabled` is not a Tab stop.
 *
 * Scope: the chrome a keyboard user tabs through on every route — the skip link, the site header (both
 * widths, its account and notification menus), the theme toggle, the verification banner under it, the
 * page header with its back link, the footer, the cookie-consent bar and its settings dialog, and the
 * auth routes' header (app/layout.tsx mounts the banner and the consent bar beside the header and
 * footer). A page's own controls are not chrome; the filing page's "← Back" is checked in a real
 * browser (tests/e2e/chrome-focus-ring.spec.ts).
 */
const ROOT = path.resolve(__dirname, '../..')

const CHROME_FILES = [
  'components/SiteChrome.tsx',
  'components/Header.tsx',
  'components/ThemeToggle.tsx',
  'features/auth/components/UserMenu.tsx',
  'features/notifications/components/NotificationBell.tsx',
  'features/auth/components/VerificationBanner.tsx',
  'components/SecondaryHeader.tsx',
  'components/Footer.tsx',
  'components/CookieConsent.tsx',
  'features/auth/components/AuthShell.tsx',
]

const RINGS = [
  ['focus-visible:outline-none', 'focus-visible:shadow-ring-brand', 'dark:focus-visible:shadow-ring-brand-dark'],
  ['focus:outline-none', 'focus:shadow-ring-brand', 'dark:focus:shadow-ring-brand-dark'],
]
/** @tailwindcss/forms rings a focused checkbox or radio itself; these take that ring off. */
const FORMS_RING_OFF = ['focus:ring-0', 'focus:ring-offset-0']
const INTRINSIC = new Set(['a', 'button', 'input', 'select', 'textarea', 'summary'])

interface Finding {
  line: number
  tag: string
  problem: string
}

/** The static class tokens of a className attribute, `'factory'` for buttonVariants(…), or null if unreadable. */
function classTokens(init: ts.JsxAttributeValue | undefined): string[] | 'factory' | null {
  if (!init) return null
  const expr = ts.isJsxExpression(init) ? init.expression : init
  if (!expr) return null
  if (ts.isStringLiteral(expr) || ts.isNoSubstitutionTemplateLiteral(expr)) return expr.text.split(/\s+/).filter(Boolean)
  if (ts.isTemplateExpression(expr)) {
    const text = [expr.head.text, ...expr.templateSpans.map((s) => s.literal.text)].join(' ')
    return text.split(/\s+/).filter(Boolean)
  }
  if (ts.isCallExpression(expr) && ts.isIdentifier(expr.expression) && expr.expression.text === 'buttonVariants') return 'factory'
  return null
}

/** Every Tab stop in `source` whose className does not carry the brand ring. */
function missingRings(source: string, fileName = 'chrome.tsx'): { stops: number; findings: Finding[] } {
  const sf = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  // next/link's default export under whatever name the file imports it as.
  const linkNames = new Set<string>()
  for (const stmt of sf.statements) {
    if (ts.isImportDeclaration(stmt) && ts.isStringLiteral(stmt.moduleSpecifier) && stmt.moduleSpecifier.text === 'next/link') {
      const name = stmt.importClause?.name?.text
      if (name) linkNames.add(name)
    }
  }
  const findings: Finding[] = []
  let stops = 0
  const visit = (node: ts.Node): void => {
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
      const tag = node.tagName.getText(sf)
      const attrs = node.attributes.properties.filter(ts.isJsxAttribute)
      const attr = (name: string) => attrs.find((a) => a.name.getText(sf) === name)
      const tabIndex = attr('tabIndex')?.initializer
      const tabIndexValue =
        tabIndex && ts.isJsxExpression(tabIndex) && tabIndex.expression
          ? Number(tabIndex.expression.getText(sf))
          : undefined
      const removed = tabIndexValue !== undefined && tabIndexValue < 0
      // `disabled` or `disabled={true}`; a dynamic value may be enabled, so it still counts.
      const disabled = attr('disabled')
      const staticallyDisabled =
        disabled !== undefined &&
        (!disabled.initializer ||
          (ts.isJsxExpression(disabled.initializer) && disabled.initializer.expression?.kind === ts.SyntaxKind.TrueKeyword))
      const tabbable =
        (INTRINSIC.has(tag) || linkNames.has(tag) || (tabIndexValue !== undefined && tabIndexValue >= 0)) && !removed && !staticallyDisabled
      const typeAttr = attr('type')?.initializer
      const toggle = tag === 'input' && !!typeAttr && ts.isStringLiteral(typeAttr) && ['checkbox', 'radio'].includes(typeAttr.text)
      if (tabbable) {
        stops += 1
        const line = sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
        const className = attr('className')
        const tokens = classTokens(className?.initializer)
        if (!className) findings.push({ line, tag, problem: 'no className, so the browser default outline' })
        else if (tokens === null) findings.push({ line, tag, problem: 'a className the scan cannot read' })
        else if (tokens !== 'factory' && !RINGS.some((ring) => ring.every((t) => tokens.includes(t)))) {
          findings.push({ line, tag, problem: `missing ${RINGS[0].filter((t) => !tokens.includes(t)).join(' ')}` })
        } else if (toggle && tokens !== 'factory' && !FORMS_RING_OFF.every((t) => tokens.includes(t))) {
          findings.push({ line, tag, problem: `missing ${FORMS_RING_OFF.filter((t) => !tokens.includes(t)).join(' ')} (the forms plugin's ring)` })
        }
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return { stops, findings }
}

describe('every Tab stop in the site chrome carries the brand focus ring (EN-05c)', () => {
  for (const file of CHROME_FILES) {
    it(file, () => {
      const { stops, findings } = missingRings(readFileSync(path.join(ROOT, file), 'utf8'), file)
      // A file that no longer has a Tab stop has moved or changed role: update the list, don't let it pass empty.
      expect(stops, `${file} has no Tab stop left to check`).toBeGreaterThan(0)
      expect(findings.map((f) => `${file}:${f.line} <${f.tag}> ${f.problem}`)).toEqual([])
    })
  }

  // The scan trusts buttonVariants(…), so the factory itself must compose the ring: the shared base takes
  // the outline off, and each brand variant draws the ring in both themes (destructive draws ring-error).
  it('buttonVariants composes the ring the scan trusts it for', () => {
    const button = readFileSync(path.join(ROOT, 'components/ui/Button.tsx'), 'utf8')
    const block = (name: string) => button.split(`\n  ${name}: cx(`)[1]?.split('\n  ),')[0] ?? ''
    expect(button.split('const BASE = cx(')[1]?.split(')')[0]).toContain("'focus-visible:outline-none'")
    for (const variant of ['primary', 'secondary', 'ghost']) {
      expect(block(variant), variant).toContain('focus-visible:shadow-ring-brand')
      expect(block(variant), variant).toContain('dark:focus-visible:shadow-ring-brand-dark')
    }
    expect(block('destructive')).toContain('focus-visible:shadow-ring-error')
  })

  it('the scan catches what it is for (a self-check on fixed sources)', () => {
    const ring = 'focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark'
    const src = `
      import NextLink from 'next/link'
      import { buttonVariants } from '@/components/ui'
      export function A({ c, busy }: { c: string; busy: boolean }) {
        return (
          <nav>
            <NextLink href="/" className="flex">logo</NextLink>
            <button className={\`p-2 \${c} focus-visible:outline-none focus-visible:shadow-ring-brand\`}>toggle</button>
            <a href="/x">bare</a>
            <span tabIndex={0} className="${ring}">stop</span>
            <div tabIndex={0}>stop</div>
            <button className={c}>unknown</button>
            <button tabIndex={-1} aria-hidden="true" className="scrim" />
            <NextLink href="/p" className={buttonVariants({ variant: 'ghost' })}>cta</NextLink>
            <NextLink href="/q" className={\`\${c} ${ring}\`}>ok</NextLink>
            <a href="#main" className="sr-only focus:outline-none focus:shadow-ring-brand dark:focus:shadow-ring-brand-dark">skip</a>
            <input type="checkbox" className="h-5 w-5 ${ring}" />
            <input type="radio" className="focus:ring-0 focus:ring-offset-0 ${ring}" />
            <input type="checkbox" disabled className="h-5 w-5" />
            <button disabled={busy} className="p-2">busy</button>
          </nav>
        )
      }`
    const { stops, findings } = missingRings(src)
    expect(stops).toBe(12)
    expect(findings.map((f) => `${f.tag}: ${f.problem}`)).toEqual([
      'NextLink: missing focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
      'button: missing dark:focus-visible:shadow-ring-brand-dark',
      'a: no className, so the browser default outline',
      'div: no className, so the browser default outline',
      'button: a className the scan cannot read',
      "input: missing focus:ring-0 focus:ring-offset-0 (the forms plugin's ring)",
      'button: missing focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
    ])
  })
})
