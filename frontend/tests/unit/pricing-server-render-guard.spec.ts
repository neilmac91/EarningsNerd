import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * Regression guard for the /pricing server-render fix (WS-5 item 2, audit C5).
 *
 * `useSearchParams()` bails its nearest <Suspense> subtree out of the server HTML. When it lived in
 * PricingContent — the sole child of the page-level Suspense — the server rendered ONLY the spinner
 * fallback and crawlers saw no H1/plans/prices/FAQ. The fix isolates the hook in a render-nothing
 * `PricingQueryEffects` that is the only thing inside Suspense, with PricingContent rendered
 * OUTSIDE it. Every other gate (lint, tsc, vitest render tests, build) stays green if someone moves
 * the hook back, so this spec pins the shape at source level:
 *   1. `useSearchParams` is referenced by exactly one top-level function: PricingQueryEffects;
 *   2. in PricingPage, <Suspense> wraps PricingQueryEffects and NOT PricingContent, and
 *      PricingContent is still rendered (outside the boundary).
 */
const PAGE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../app/pricing/page.tsx')
const EFFECTS_COMPONENT = 'PricingQueryEffects'
const CONTENT_COMPONENT = 'PricingContent'
const PAGE_COMPONENT = 'PricingPage'

const sourceFile = ts.createSourceFile(PAGE, readFileSync(PAGE, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)

const topLevelFunctions = sourceFile.statements.filter(
  (s): s is ts.FunctionDeclaration => ts.isFunctionDeclaration(s) && Boolean(s.name),
)

function referencesIdentifier(node: ts.Node, name: string): boolean {
  let found = false
  const visit = (n: ts.Node): void => {
    if (found) return
    if (ts.isIdentifier(n) && n.text === name) {
      found = true
      return
    }
    ts.forEachChild(n, visit)
  }
  visit(node)
  return found
}

function jsxTagName(node: ts.Node): string | null {
  if (ts.isJsxElement(node)) return node.openingElement.tagName.getText(sourceFile)
  if (ts.isJsxSelfClosingElement(node)) return node.tagName.getText(sourceFile)
  return null
}

function collectTagNames(node: ts.Node, into: Set<string>): void {
  const tag = jsxTagName(node)
  if (tag) into.add(tag)
  ts.forEachChild(node, (child) => collectTagNames(child, into))
}

describe('/pricing server-render guard', () => {
  it('the page still defines the three components the guard reasons about', () => {
    const names = topLevelFunctions.map((f) => f.name!.text)
    expect(names).toEqual(expect.arrayContaining([EFFECTS_COMPONENT, CONTENT_COMPONENT, PAGE_COMPONENT]))
  })

  it(`useSearchParams is referenced ONLY inside ${EFFECTS_COMPONENT}`, () => {
    const users = topLevelFunctions
      .filter((f) => referencesIdentifier(f.body ?? f, 'useSearchParams'))
      .map((f) => f.name!.text)
    expect(
      users,
      `useSearchParams() must stay isolated in ${EFFECTS_COMPONENT} (the only child of <Suspense>); ` +
        'anywhere else it bails the whole pricing body out of the server HTML (audit C5).',
    ).toEqual([EFFECTS_COMPONENT])
  })

  it(`<Suspense> wraps ${EFFECTS_COMPONENT} only; ${CONTENT_COMPONENT} renders outside it`, () => {
    const page = topLevelFunctions.find((f) => f.name!.text === PAGE_COMPONENT)!
    const insideSuspense = new Set<string>()
    const everywhere = new Set<string>()
    collectTagNames(page.body!, everywhere)

    const visit = (n: ts.Node): void => {
      if (ts.isJsxElement(n) && n.openingElement.tagName.getText(sourceFile) === 'Suspense') {
        for (const child of n.children) collectTagNames(child, insideSuspense)
      }
      ts.forEachChild(n, visit)
    }
    visit(page.body!)

    expect(insideSuspense.has(EFFECTS_COMPONENT), `${EFFECTS_COMPONENT} must be rendered inside <Suspense>`).toBe(true)
    expect(
      insideSuspense.has(CONTENT_COMPONENT),
      `${CONTENT_COMPONENT} must NOT be inside <Suspense> — that is exactly the spinner-only server HTML the fix removed.`,
    ).toBe(false)
    expect(everywhere.has(CONTENT_COMPONENT), `${PAGE_COMPONENT} must still render ${CONTENT_COMPONENT}`).toBe(true)
  })
})
