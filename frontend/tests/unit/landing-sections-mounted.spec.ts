import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * Mount guard for the landing route's live-data sections (W3-10).
 *
 * The 2026-09-10 revamp dropped <NotableFilings /> from app/page.tsx. Nothing went red: the
 * component, its fetcher and its unit spec all survived and kept passing in isolation, so the
 * section was simply gone from the page while every gate stayed green. It surfaced three days
 * later only because W3-10's recorded done-criterion ("the homepage section renders in both
 * themes after ISR") could not be satisfied.
 *
 * A section that self-omits on empty data cannot be caught by a render test — absence is its
 * correct behaviour when the flag is off — so the only place the mount is observable is the
 * route source. This pins it there: each live-data section must be rendered by Home AND fed by
 * its fetcher. A future redesign that removes one has to delete it from this list deliberately,
 * which is the decision the revamp made silently.
 */
const PAGE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../app/page.tsx')
const HOME_COMPONENT = 'Home'

/** Section component → the serverApi fetcher whose data it is mounted with. */
const LIVE_DATA_SECTIONS: ReadonlyArray<readonly [string, string]> = [
  ['LandingHero', 'fetchExampleData'],
  ['ReportingThisWeek', 'fetchReportingThisWeek'],
  ['NotableFilings', 'fetchNotableFilings'],
  ['PricingSection', 'fetchSignupConfig'],
]

const sourceFile = ts.createSourceFile(
  PAGE,
  readFileSync(PAGE, 'utf8'),
  ts.ScriptTarget.Latest,
  true,
  ts.ScriptKind.TSX,
)

function findHome(): ts.FunctionDeclaration {
  const home = sourceFile.statements.find(
    (s): s is ts.FunctionDeclaration =>
      ts.isFunctionDeclaration(s) && s.name?.text === HOME_COMPONENT,
  )
  if (!home) throw new Error(`${HOME_COMPONENT} is not a top-level function in app/page.tsx`)
  return home
}

function collectJsxTagNames(node: ts.Node): Set<string> {
  const tags = new Set<string>()
  const visit = (n: ts.Node): void => {
    if (ts.isJsxOpeningElement(n) || ts.isJsxSelfClosingElement(n)) {
      const name = n.tagName
      if (ts.isIdentifier(name)) tags.add(name.text)
    }
    ts.forEachChild(n, visit)
  }
  visit(node)
  return tags
}

function collectCalledIdentifiers(node: ts.Node): Set<string> {
  const calls = new Set<string>()
  const visit = (n: ts.Node): void => {
    if (ts.isCallExpression(n) && ts.isIdentifier(n.expression)) calls.add(n.expression.text)
    ts.forEachChild(n, visit)
  }
  visit(node)
  return calls
}

describe('landing route keeps its live-data sections mounted', () => {
  const home = findHome()
  const tags = collectJsxTagNames(home)
  const calls = collectCalledIdentifiers(home)

  it.each(LIVE_DATA_SECTIONS)('renders <%s /> on the landing route', (component) => {
    expect(tags.has(component)).toBe(true)
  })

  it.each(LIVE_DATA_SECTIONS)('feeds %s from %s', (_component, fetcher) => {
    expect(calls.has(fetcher)).toBe(true)
  })

  it('imports every mounted live-data section', () => {
    const imported = new Set(
      sourceFile.statements
        .filter(ts.isImportDeclaration)
        .flatMap((statement) => {
          const clause = statement.importClause
          if (!clause) return []
          const names: string[] = []
          if (clause.name) names.push(clause.name.text)
          if (clause.namedBindings && ts.isNamedImports(clause.namedBindings)) {
            names.push(...clause.namedBindings.elements.map((element) => element.name.text))
          }
          return names
        }),
    )
    for (const [component, fetcher] of LIVE_DATA_SECTIONS) {
      expect(imported.has(component), `${component} is rendered but not imported`).toBe(true)
      expect(imported.has(fetcher), `${fetcher} is called but not imported`).toBe(true)
    }
  })
})
