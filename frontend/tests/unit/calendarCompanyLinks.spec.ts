// @vitest-environment node
/* =============================================================================
   calendarCompanyLinks.spec.ts — guardrail
   -----------------------------------------------------------------------------
   An earnings event carries Alpha Vantage's spelling of a share class (BRK.B),
   and the company page binds SEC's (BRK-B) by exact match, so a company link
   built from an event's own ticker answers not found for a dual-class company.
   The calendar feature renders events, so every company-page link it builds
   passes its ticker through `secTicker` (features/calendar/lib/tickers.ts).

   The scan reads each source file's TypeScript AST under features/calendar
   (comments never count) and reports a link built without it: a template
   literal that opens with `/company/` whose first interpolation is not a
   `secTicker(...)` call, and a `'/company/' + …` concatenation whose right side
   is not one. The links it guards are pinned by file, so a scan that stopped
   seeing them fails too.

   Not covered: a link built outside features/calendar from an event's ticker,
   one assembled from a variable that holds the path, and a route helper.
============================================================================= */

import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

const CALENDAR = path.resolve(__dirname, '../../features/calendar')

function sourceFiles(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) return sourceFiles(full)
    return /\.tsx?$/.test(entry.name) ? [full] : []
  })
}

const isSecTicker = (node: ts.Expression): boolean =>
  ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'secTicker'

/** The lines of a source's company-page links, split by whether the ticker passes through secTicker. */
function companyLinks(source: string): { guarded: number[]; raw: number[] } {
  const file = ts.createSourceFile('source.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const found = { guarded: [] as number[], raw: [] as number[] }
  const record = (node: ts.Node, ticker: ts.Expression) => {
    const line = file.getLineAndCharacterOfPosition(node.getStart(file)).line + 1
    found[isSecTicker(ticker) ? 'guarded' : 'raw'].push(line)
  }
  const visit = (node: ts.Node): void => {
    if (ts.isTemplateExpression(node) && node.head.text === '/company/') {
      record(node, node.templateSpans[0].expression)
    } else if (
      ts.isBinaryExpression(node) &&
      node.operatorToken.kind === ts.SyntaxKind.PlusToken &&
      ts.isStringLiteralLike(node.left) &&
      node.left.text === '/company/'
    ) {
      record(node, node.right)
    }
    ts.forEachChild(node, visit)
  }
  visit(file)
  return found
}

describe('the calendar builds a company-page link in SEC’s spelling', () => {
  it('passes every company link’s ticker through secTicker', () => {
    const raw: string[] = []
    const guarded: Record<string, number> = {}
    for (const file of sourceFiles(CALENDAR)) {
      const relative = path.relative(CALENDAR, file)
      const links = companyLinks(fs.readFileSync(file, 'utf8'))
      raw.push(...links.raw.map((line) => `${relative}:${line}`))
      if (links.guarded.length) guarded[relative] = links.guarded.length
    }
    expect(raw, 'a company link built from an event’s own ticker answers not found for BRK.B; wrap it in secTicker').toEqual([])
    expect(guarded).toEqual({ 'components/EventRow.tsx': 1, 'components/ReportingThisWeek.tsx': 1 })
  })

  it('finds each raw form, and takes a comment for nothing', () => {
    expect(companyLinks('const a = `/company/${ev.ticker}`').raw).toEqual([1])
    expect(companyLinks("const a = '/company/' + ev.ticker").raw).toEqual([1])
    expect(companyLinks('const a = `/company/${ev.ticker.toUpperCase()}/filings`').raw).toEqual([1])
    expect(companyLinks('const a = `/company/${secTicker(ev.ticker)}`')).toEqual({ guarded: [1], raw: [] })
    expect(companyLinks("const a = '/company/' + secTicker(ev.ticker)")).toEqual({ guarded: [1], raw: [] })
    expect(companyLinks('// `/company/${ev.ticker}`\nconst a = 1')).toEqual({ guarded: [], raw: [] })
  })
})
