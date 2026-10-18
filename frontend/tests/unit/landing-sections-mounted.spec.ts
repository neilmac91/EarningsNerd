import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { LANDING_SECTIONS_ELSEWHERE } from '../../eslint.designRules.mjs'

/**
 * Mount guard for the landing route's live-data sections (W3-10), and the composition gate for D-045.
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
  // NotableFilings left this list on 2026-10-11 (brand studio, docs/brand/01-interview.md A8). It waits on
  // E90, which remounts it under D-046's curation rule; the component and fetcher remain for that day.
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

/**
 * The composition gate (D-045, composition C; CLAUDE.md rule 12). The landing keeps its two-column hero, and every
 * section after it is one ruled row: it renders inside LandingRow (features/marketing/components/LandingRow.tsx,
 * the rule, the label column with the number, the title as the section's h2 and one line, then the content), in
 * the order below, and the page closes with ClosingLine, one line and no row. Read from the source, as the mount
 * guard above reads it, because a section that omits itself on empty data renders nothing a render test could
 * check:
 *  - Home's <main> holds the hero, then ROWS in order, then the close, and no other element;
 *  - each row's component, at the module page.tsx imports it from, returns LandingRow (the default import of the
 *    primitive's module, under any local name) or null from its own body, on every path: a return of anything
 *    else (a bare <section>, a wrapper around the row, a ternary with one arm that is not the row) fails;
 *  - each row's module is one the four-up rule reads (earningsnerd/no-four-up-grid: features/marketing, or a
 *    section from elsewhere listed in LANDING_SECTIONS_ELSEWHERE), so a section mounted from another feature
 *    cannot leave that rule's reach in silence;
 *  - the close renders one paragraph and no heading, row or card.
 * The checks are scored on PLANTED forms below before they read the real files. Out of reach, review-checked: a
 * row's component that renders LandingRow through a helper function of its own, and what LandingRow's children
 * contain (the four-up rule and the e2e specs read those).
 */
const ROWS = [
  'MeasuredClaims',
  'EvidenceSection',
  'SummaryContents',
  'ProDepth',
  'PricingSection',
  'ReaderQuoteSlot',
  'ReportingThisWeek',
] as const
const HERO = 'LandingHero'
const CLOSE = 'ClosingLine'
const PRIMITIVE_MODULE = '@/features/marketing/components/LandingRow'
const FRONTEND = path.resolve(path.dirname(PAGE), '..')

const parse = (file: string, text: string) => ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)

/** The element names <main> holds in a Home component's source, in order (text and comments aside). */
function mainChildren(source: ts.SourceFile): string[] {
  let found: string[] | null = null
  const visit = (node: ts.Node): void => {
    if (found) return
    if (ts.isJsxElement(node) && node.openingElement.tagName.getText(source) === 'main') {
      found = node.children.flatMap((child) => {
        if (ts.isJsxElement(child)) return [child.openingElement.tagName.getText(source)]
        if (ts.isJsxSelfClosingElement(child)) return [child.tagName.getText(source)]
        if (ts.isJsxExpression(child) && child.expression) return [`{${child.expression.getText(source)}}`]
        return []
      })
      return
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  return found ?? []
}

/** The module a default import comes from, by its local name. */
function defaultImports(source: ts.SourceFile): Map<string, string> {
  const map = new Map<string, string>()
  for (const statement of source.statements) {
    if (ts.isImportDeclaration(statement) && statement.importClause?.name && ts.isStringLiteral(statement.moduleSpecifier)) {
      map.set(statement.importClause.name.text, statement.moduleSpecifier.text)
    }
  }
  return map
}

const strip = (expression: ts.Expression): ts.Expression =>
  ts.isParenthesizedExpression(expression) ? strip(expression.expression) : expression

/** What a section component's own body returns that is not the ruled row: each offending return, as written. A
 *  return inside a nested function (a .map callback) is the callback's, not the component's. */
function returnsOtherThanRow(file: string, text: string): string[] {
  const source = parse(file, text)
  const rowNames = [...defaultImports(source)].filter(([, from]) => from === PRIMITIVE_MODULE).map(([name]) => name)
  const component = source.statements.find(
    (s): s is ts.FunctionDeclaration =>
      ts.isFunctionDeclaration(s) && !!s.modifiers?.some((m) => m.kind === ts.SyntaxKind.DefaultKeyword),
  )
  if (!component?.body) return ['no `export default function` component']
  const isRow = (expression: ts.Expression): boolean => {
    const e = strip(expression)
    const tag = ts.isJsxElement(e) ? e.openingElement.tagName : ts.isJsxSelfClosingElement(e) ? e.tagName : null
    return !!tag && ts.isIdentifier(tag) && rowNames.includes(tag.text)
  }
  const isNull = (expression: ts.Expression): boolean => strip(expression).kind === ts.SyntaxKind.NullKeyword
  const returns: ts.ReturnStatement[] = []
  const collect = (node: ts.Node): void => {
    if (ts.isFunctionLike(node)) return
    if (ts.isReturnStatement(node)) {
      returns.push(node)
      return
    }
    ts.forEachChild(node, collect)
  }
  ts.forEachChild(component.body, collect)
  const offending = returns
    .filter((r) => !r.expression || !(isRow(r.expression) || isNull(r.expression)))
    .map((r) => (r.expression ?? r).getText(source))
  if (!returns.some((r) => r.expression && isRow(r.expression))) offending.push('no return renders the row')
  return offending
}

/** What the close renders that a line does not: a heading, a row, a card, or other than one paragraph. */
function closeIsNotALine(file: string, text: string): string[] {
  const source = parse(file, text)
  const tags: string[] = []
  const visit = (node: ts.Node): void => {
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) tags.push(node.tagName.getText(source))
    ts.forEachChild(node, visit)
  }
  visit(source)
  const problems = tags.filter((tag) => /^(h[1-6]|section|LandingRow|Card)$/.test(tag)).map((tag) => `renders <${tag}>`)
  const paragraphs = tags.filter((tag) => tag === 'p').length
  if (paragraphs !== 1) problems.push(`renders ${paragraphs} paragraphs, not one line`)
  return problems
}

const moduleFile = (specifier: string): string => path.join(FRONTEND, `${specifier.replace(/^@\//, '')}.tsx`)
const relative = (file: string): string => path.relative(FRONTEND, file).split(path.sep).join('/')

describe('the composition gate reads its planted forms (D-045)', () => {
  const ROW_IMPORT = `import LandingRow from '${PRIMITIVE_MODULE}'\n`
  it('passes a section that returns its row, or null, on every path of its own body', () => {
    expect(returnsOtherThanRow('a.tsx', `${ROW_IMPORT}export default function A() { return <LandingRow id="a" title="A" impression="a">x</LandingRow> }`)).toEqual([])
    expect(returnsOtherThanRow('b.tsx', `${ROW_IMPORT}export default function B({ d }: { d: string[] }) {\n  if (!d.length) return null\n  return (\n    <LandingRow id="b" title="B" impression="b">{d.map((x) => { return <li key={x}>{x}</li> })}</LandingRow>\n  )\n}`)).toEqual([])
    // The primitive under another local name is the primitive.
    expect(returnsOtherThanRow('c.tsx', `import Row from '${PRIMITIVE_MODULE}'\nexport default function C() { return <Row id="c" title="C" impression="c" /> }`)).toEqual([])
  })
  it('fails a bare section, a wrapper, a look-alike, a branch that is not the row, and a component that only returns null', () => {
    expect(returnsOtherThanRow('d.tsx', `${ROW_IMPORT}export default function D() { return <section aria-label="D">x</section> }`)).toEqual([
      '<section aria-label="D">x</section>',
      'no return renders the row',
    ])
    expect(returnsOtherThanRow('e.tsx', `${ROW_IMPORT}export default function E() { return <div><LandingRow id="e" title="E" impression="e">x</LandingRow></div> }`)).toHaveLength(2)
    expect(returnsOtherThanRow('f.tsx', `import LandingRow from './elsewhere'\nexport default function F() { return <LandingRow id="f" title="F" impression="f" /> }`)).toHaveLength(2)
    expect(returnsOtherThanRow('g.tsx', `${ROW_IMPORT}export default function G({ a }: { a: boolean }) { return a ? <LandingRow id="g" title="G" impression="g" /> : <section /> }`)).toHaveLength(2)
    expect(returnsOtherThanRow('h.tsx', `${ROW_IMPORT}export default function H() { return null }`)).toEqual(['no return renders the row'])
  })
  it('reads <main> in order, an expression child included, and fails a close that is a banner', () => {
    const page = parse('page.tsx', 'export default function Home() { return <div><main><Hero />{cond && <A />}<B></B></main></div> }')
    expect(mainChildren(page)).toEqual(['Hero', '{cond && <A />}', 'B'])
    expect(closeIsNotALine('x.tsx', 'export default function X() { return <div><p>One line <a href="/">go</a></p></div> }')).toEqual([])
    expect(closeIsNotALine('y.tsx', 'export default function Y() { return <Card><h2>Start</h2><p>a</p><p>b</p></Card> }')).toEqual([
      'renders <Card>',
      'renders <h2>',
      'renders 2 paragraphs, not one line',
    ])
  })
})

describe('the landing composition (D-045): every section after the hero is one ruled row, in order', () => {
  const imports = defaultImports(sourceFile)

  it('mounts the hero, then every row in order, then the one-line close, and nothing else in <main>', () => {
    expect(mainChildren(sourceFile)).toEqual([HERO, ...ROWS, CLOSE])
  })

  it.each(ROWS)('renders <%s /> inside LandingRow on every path', (name) => {
    const specifier = imports.get(name)
    expect(specifier, `${name} is a default import of app/page.tsx`).toBeTruthy()
    const file = moduleFile(specifier!)
    expect(existsSync(file), `${relative(file)} exists`).toBe(true)
    expect(returnsOtherThanRow(file, readFileSync(file, 'utf8')), `${relative(file)} returns only its LandingRow or null`).toEqual([])
  })

  it('keeps every row inside the four-up rule\'s reach', () => {
    for (const name of ROWS) {
      const file = relative(moduleFile(imports.get(name)!))
      expect(
        file.startsWith('features/marketing/') || LANDING_SECTIONS_ELSEWHERE.includes(file),
        `${file} is a landing row outside features/marketing: add it to LANDING_SECTIONS_ELSEWHERE (eslint.designRules.mjs)`,
      ).toBe(true)
    }
    // And the list names no file the page no longer mounts.
    const mounted = ROWS.map((name) => relative(moduleFile(imports.get(name)!)))
    for (const file of LANDING_SECTIONS_ELSEWHERE) expect(mounted, `${file} is listed but not mounted`).toContain(file)
  })

  it('closes with one line: one paragraph, no heading, no row, no card', () => {
    const file = moduleFile(imports.get(CLOSE)!)
    expect(closeIsNotALine(file, readFileSync(file, 'utf8'))).toEqual([])
  })
})
