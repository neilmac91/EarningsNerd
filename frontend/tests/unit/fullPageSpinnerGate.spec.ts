/* =============================================================================
   fullPageSpinnerGate.spec.ts — P-09 (Design Critique 2026-10)
   -----------------------------------------------------------------------------
   A page never swaps itself for a full-page spinner. While it loads it renders its
   own frame and header over bones in the loaded layout's cards (DESIGN_SYSTEM.md
   §11 "Loading"), so nothing jumps when the content arrives and reduced motion has
   a still page, not a spinner screen.

   The scan reads the TypeScript AST of every .tsx under app/, components/ and
   features/ and reports a spinner screen: an element whose literal class text names
   `min-h-screen` and whose whole content is spinners (CircleNotchIcon, SpinnerIcon,
   SpinnerGapIcon, Spinner, or anything classed `animate-spin`), screen-reader-only
   text and bare div/span wrappers around them. The outermost such element counts
   once. Kept sites are pinned per file with a reason, shrink-only; app/dashboard
   has none and pins none.

   Limits: a class that reaches the element only through a variable or a helper the
   scan cannot read as literal text, a spinner rendered conditionally inside the
   screen (`{loading && <Spinner />}`), and a spinner screen that is another
   component's whole render.
============================================================================= */

import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

const ROOT = path.join(__dirname, '../..')
const SCAN_DIRS = ['app', 'components', 'features']
const SPINNER_TAG = /^(CircleNotchIcon|SpinnerIcon|SpinnerGapIcon|Spinner)$/
const WRAPPER_TAG = /^(div|span)$/

// Shrink-only: lower it when an entry goes; never raise it to fit a new spinner screen.
const MAX_ALLOWLIST_SIZE = 3
const ALLOW: Record<string, { count: number; reason: string }> = {
  'app/company/[ticker]/page-client.tsx': {
    count: 1,
    reason:
      'The server seeds the company (ISR), so the page paints at once; the spinner shows only when that seed is ' +
      'missing. Replace it with the company lead over bones when the page is next reworked.',
  },
  'app/filing/[id]/page-client.tsx': {
    count: 1,
    reason:
      'The server seeds the filing, so the page paints at once; the spinner shows only when that seed is missing. ' +
      'Replace it with the filing identity over bones when the page is next reworked.',
  },
  'features/filings/components/TickerFilingsView.tsx': {
    count: 1,
    reason:
      'The /filing/<TICKER> route loads its company on the client on every visit. Replace the spinner with the ' +
      'filings list over bones when the route is next reworked.',
  },
}

/** The literal class text on a JSX element: every string and template chunk under its className. */
function classTokens(attributes: ts.JsxAttributes): string[] {
  const parts: string[] = []
  for (const attr of attributes.properties) {
    if (!ts.isJsxAttribute(attr) || attr.name.getText() !== 'className' || !attr.initializer) continue
    const visit = (node: ts.Node): void => {
      if (ts.isStringLiteralLike(node)) parts.push(node.text)
      else if (ts.isTemplateHead(node) || ts.isTemplateMiddle(node) || ts.isTemplateTail(node)) parts.push(node.text)
      ts.forEachChild(node, visit)
    }
    visit(attr.initializer)
  }
  return parts.join(' ').split(/\s+/).filter(Boolean)
}

interface Element {
  tag: string
  classes: string[]
  children: readonly ts.JsxChild[]
}

function asElement(node: ts.Node): Element | null {
  if (ts.isJsxElement(node)) {
    const { tagName, attributes } = node.openingElement
    return { tag: tagName.getText(), classes: classTokens(attributes), children: node.children }
  }
  if (ts.isJsxSelfClosingElement(node)) {
    return { tag: node.tagName.getText(), classes: classTokens(node.attributes), children: [] }
  }
  return null
}

const isSpinner = (el: Element) => SPINNER_TAG.test(el.tag) || el.classes.includes('animate-spin')

/** How many spinners the children hold, and whether they hold anything else a reader would see. */
function weigh(children: readonly ts.JsxChild[]): { spinners: number; content: boolean } {
  let spinners = 0
  let content = false
  for (const child of children) {
    if (ts.isJsxText(child)) {
      if (child.text.trim()) content = true
      continue
    }
    if (ts.isJsxExpression(child)) {
      if (child.expression) content = true // a comment is an empty expression
      continue
    }
    const el = asElement(child)
    if (!el) {
      const inner = ts.isJsxFragment(child) ? weigh(child.children) : { spinners: 0, content: true }
      spinners += inner.spinners
      content ||= inner.content
    } else if (isSpinner(el)) {
      spinners += 1
    } else if (el.classes.includes('sr-only')) {
      // Screen-reader text names the wait; it shows nothing.
    } else if (WRAPPER_TAG.test(el.tag)) {
      const inner = weigh(el.children)
      spinners += inner.spinners
      content ||= inner.content
    } else {
      content = true
    }
  }
  return { spinners, content }
}

/** The 1-based lines of the spinner screens in a source file, outermost element only. */
function spinnerScreens(source: string, fileName = 'probe.tsx'): number[] {
  const file = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const lines: number[] = []
  const visit = (node: ts.Node): void => {
    const el = asElement(node)
    if (el && el.classes.includes('min-h-screen')) {
      const { spinners, content } = weigh(el.children)
      if (spinners > 0 && !content) {
        lines.push(file.getLineAndCharacterOfPosition(node.getStart(file)).line + 1)
        return
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(file)
  return lines
}

function walk(dir: string, out: string[] = []): string[] {
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name)
    if (fs.statSync(p).isDirectory()) walk(p, out)
    else if (p.endsWith('.tsx')) out.push(p)
  }
  return out
}

function scan(dirs: string[]): Map<string, number[]> {
  const found = new Map<string, number[]>()
  for (const file of dirs.flatMap((d) => walk(path.join(ROOT, d)))) {
    const lines = spinnerScreens(fs.readFileSync(file, 'utf8'), file)
    if (lines.length) found.set(path.relative(ROOT, file).split(path.sep).join('/'), lines)
  }
  return found
}

const wrap = (jsx: string) => `export function P() {\n  return (\n${jsx}\n  )\n}\n`

describe('spinnerScreens', () => {
  it('finds the full-page spinner forms the app has used', () => {
    // The settings and watchlist pages before P-09.
    expect(spinnerScreens(wrap(`
      <div className="min-h-screen bg-background-light dark:bg-background-dark flex items-center justify-center">
        <CircleNotchIcon className="h-8 w-8 animate-spin text-brand-strong dark:text-brand-strong-dark" />
      </div>`))).toEqual([4])
    // Named for screen readers, and nested in a second full-height wrapper: one screen each.
    expect(spinnerScreens(wrap(`
      <div role="status" aria-label="Loading company" className="min-h-screen flex items-center justify-center">
        <CircleNotchIcon className="h-8 w-8 animate-spin" />
        <span className="sr-only">Loading company…</span>
      </div>`))).toEqual([4])
    expect(spinnerScreens(wrap(`
      <div className="min-h-screen bg-background-light">
        <div className="flex h-full min-h-screen items-center justify-center">
          <CircleNotchIcon className="h-8 w-8 animate-spin" />
        </div>
      </div>`))).toEqual([4])
    // A CSS border spinner, and a class written as a template.
    expect(spinnerScreens(wrap(`
      <div className={\`min-h-screen \${tone}\`}>
        {/* waiting */}
        <div className="animate-spin rounded-full h-8 w-8 border-b-2" />
      </div>`))).toEqual([4])
  })

  it('passes a frame over bones, a spinner beside visible text, and a page holding a busy control', () => {
    expect(spinnerScreens(wrap(`
      <div className="min-h-screen bg-background-light">
        {header}
        <Card className="p-6 mb-6"><SkeletonText lines={3} /></Card>
      </div>`))).toEqual([])
    expect(spinnerScreens(wrap(`
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <CircleNotchIcon className="mx-auto h-10 w-10 animate-spin" />
          <p>Verifying your email…</p>
        </div>
      </div>`))).toEqual([])
    expect(spinnerScreens(wrap(`
      <div className="min-h-screen">
        <Button loading>Save</Button>
        <CircleNotchIcon className="h-4 w-4 animate-spin" />
      </div>`))).toEqual([])
  })
})

describe('full-page spinners (P-09)', () => {
  const found = scan(SCAN_DIRS)

  it('no page under app/dashboard renders one', () => {
    expect([...found.keys()].filter((file) => file.startsWith('app/dashboard/'))).toEqual([])
    expect(Object.keys(ALLOW).filter((file) => file.startsWith('app/dashboard/'))).toEqual([])
  })

  it('none outside the allowlist', () => {
    const offenders = [...found].filter(([file]) => !(file in ALLOW)).map(([file, lines]) => `${file}:${lines.join(',')}`)
    expect(
      offenders,
      'A loading page renders its own frame and header over bones in the loaded layout’s cards (the dashboard, ' +
        'settings and watchlist pages), never a full-page spinner. See DESIGN_SYSTEM.md §11 "Loading".',
    ).toEqual([])
  })

  it.each(Object.entries(ALLOW))('%s still has its pinned spinner screens (lower the pin as they go)', (file, { count }) => {
    expect(found.get(file)?.length ?? 0).toBe(count)
  })

  it('is shrink-only, and every entry has a reason', () => {
    expect(Object.keys(ALLOW).length).toBeLessThanOrEqual(MAX_ALLOWLIST_SIZE)
    for (const [file, { reason }] of Object.entries(ALLOW)) expect(reason.trim().length, file).toBeGreaterThan(0)
  })
})
