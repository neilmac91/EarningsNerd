import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'

// recharts measures the DOM, which jsdom can't do: stub it, as analysis-teaser.spec.tsx does.
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ComposedChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => null,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
}))
// PeekLocked's UpgradeModal calls useRouter; no app router is mounted under vitest.
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }))

import demo from '@/features/analysis/demo/demo-analysis.json'
import AnalysisTeaser from '@/features/analysis/components/AnalysisTeaser'
import DataNotes from '@/features/analysis/components/DataNotes'
import { DataNotesProvider } from '@/features/analysis/components/DataNotesContext'
import KpiStrip from '@/features/analysis/components/KpiStrip'
import MetricsTable from '@/features/analysis/components/MetricsTable'
import NarrativePane from '@/features/analysis/components/NarrativePane'
import PeriodPicker from '@/features/analysis/components/PeriodPicker'
import AnalysisDemo from '@/features/marketing/components/AnalysisDemo'
import { citationDisplay } from '@/features/analysis/lib/narrativeDisplay'
import { ANALYSIS_PERIOD_KEY, formatAnalysisPeriod, formatAnalysisPeriods, formatAnalysisWindow } from '@/features/analysis/lib/periodLabels'
import type { AnalysisCitation, AnalysisCompletion, AnalysisCoverage, AnalysisDataset } from '@/features/analysis/api/analysis-api'

/**
 * E78: the analysis page prints a period window one way, the voice guide's unspaced range ("FY2020–FY2025",
 * "Q1 2024–Q4 2025"), and a window of one period as that period ("FY2021", E177), which is also how the exports
 * print it (`period_label` in backend/app/services/analysis_export_metadata.py), through formatAnalysisWindow in
 * features/analysis/lib/periodLabels.ts. The API, the stored narrative and every lookup keep the key
 * ("FY2020..FY2025", "FY2021..FY2021").
 *
 * Three holds.
 *  - What the page renders: the committed demo run (one saved pipeline run, features/analysis/demo) through the
 *    teaser, the landing's Multi-Period screen and a reader's own report with the source dialog open, plus the period
 *    picker in both modes and the streamed narrative. Their text, read whole, and every attribute (a title, an
 *    accessible name) carry no window key and no spaced window, and the range stands where each used to print.
 *  - Where a window field is read: in every tracked script outside tests/, the API's window fields (`period_key`,
 *    `cagr_window`, `window_pp_range`), read off their object or by their own name, and windowRange's result reach
 *    page text (JSX text, a prop, a template) only through a call, the formatter's. In the analysis code and every
 *    file that imports it, so does a `period`, which carries a CAGR's window on a citation, a point or a note; a
 *    single period read there takes formatAnalysisPeriod too, which gives a quarter its display form.
 *  - Where a range is joined: in the analysis code and every file that imports it, no string, template or JSX text
 *    outside periodLabels.ts holds an en-dash, written, escaped, as an entity or made by String.fromCharCode.
 *
 * Out of reach, each planted below as the gap it is: a window key held in a variable of another name or in an object
 * before it is printed, or handed to a function other than the formatter, when the spec renders no surface it
 * reaches; and a source excerpt the citation reader cannot parse, shown exactly as the server wrote it (the
 * fail-open narrative-pane.spec.tsx holds). Every excerpt the server writes today parses, a CAGR's included. The
 * server's narrative compaction formats quarters, not windows, so a code-owned quarterly window would reach the page
 * as "Q1 2024..Q4 2025"; the only code-owned window is the CAGR's, which is annual, and the rendered half reads that
 * form too.
 */

const KEY = /(?:FY)?\d{4}(?:Q[1-4])?\.\.(?:FY)?\d{4}(?:Q[1-4])?|Q[1-4] \d{4}\.\.Q[1-4] \d{4}/g
const SPACED = /(?:FY\d{4}|Q[1-4] \d{4}) – (?:FY\d{4}|Q[1-4] \d{4})/g

/** Each window key or spaced window under `root`: in its text read whole (React splits one line into several text
 *  nodes, "FY2020", " – ", "FY2025") and in each attribute. */
function windowPrints(root: Element): string[] {
  const values = [root.textContent ?? '', ...[root, ...root.querySelectorAll('*')].flatMap((el) => [...el.attributes].map((a) => a.value))]
  return values.flatMap((value) => [...value.matchAll(KEY), ...value.matchAll(SPACED)]
    .map((m) => value.slice(Math.max(0, (m.index ?? 0) - 40), (m.index ?? 0) + 40)))
}

const run = demo.dataset as unknown as AnalysisDataset
const completion = demo.completion as unknown as AnalysisCompletion
/** The run with the server's notes envelope set aside and revenue's CAGR marked for review (the e2e annual geometry
 *  fixture's reason), so the notes derived from provenance name a window comparison. */
const noted = (() => {
  const dataset = structuredClone(run)
  delete dataset.data_notes
  const revenue = dataset.series.find((series) => series.concept === 'revenue')!
  revenue.cagr_provenance = { ...revenue.cagr_provenance!, validation: 'needs_review', reasons: ['source_check_needed'] }
  revenue.cagr_reconciled = false
  return dataset
})()
const { narrative_presentation: _presentation, ...legacyCompletion } = structuredClone(completion)

describe('formatAnalysisWindow', () => {
  it('joins a window’s two ends with an unspaced en-dash, in each period’s own display form', () => {
    expect(formatAnalysisWindow('FY2020', 'FY2025')).toBe('FY2020–FY2025')
    expect(formatAnalysisWindow('2024Q1', '2025Q4')).toBe('Q1 2024–Q4 2025')
    expect(formatAnalysisWindow('2024Q1', '2025Q4', 'short')).toBe('Q1 ’24–Q4 ’25')
  })

  it('reads a window key wherever a period is formatted, and leaves a single period, or anything else, as it was', () => {
    expect(formatAnalysisPeriod('FY2016..FY2025')).toBe('FY2016–FY2025')
    expect(formatAnalysisPeriod('2023Q3..2026Q2')).toBe('Q3 2023–Q2 2026')
    expect(formatAnalysisPeriod('FY2025')).toBe('FY2025')
    expect(formatAnalysisPeriod('2026Q2')).toBe('Q2 2026')
    expect(formatAnalysisPeriod('draft..final')).toBe('draft..final')
  })

  it('prints a window of one period as that period, never as a range from it to itself (E177)', () => {
    expect(formatAnalysisWindow('FY2021', 'FY2021')).toBe('FY2021')
    expect(formatAnalysisWindow('2025Q3', '2025Q3')).toBe('Q3 2025')
    expect(formatAnalysisWindow('2025Q3', '2025Q3', 'short')).toBe('Q3 ’25')
    expect(formatAnalysisPeriod('FY2021..FY2021')).toBe('FY2021')
    expect(formatAnalysisPeriods('Revenue held in FY2021..FY2021 and 2025Q3..2025Q3.')).toBe('Revenue held in FY2021 and Q3 2025.')
  })

  it('formats every key in a run of prose, windows before quarters, and changes nothing a second time', () => {
    const prose = 'Revenue CAGR was +8.7% over FY2020..FY2025 [2]. Margins held from 2024Q1..2025Q4, and net income rose in 2026Q2 [3].'
    const formatted = 'Revenue CAGR was +8.7% over FY2020–FY2025 [2]. Margins held from Q1 2024–Q4 2025, and net income rose in Q2 2026 [3].'
    expect(formatAnalysisPeriods(prose)).toBe(formatted)
    expect(formatAnalysisPeriods(formatted)).toBe(formatted)
  })

  it('reads the period key the export reads and joins a window as its period_label does, so the PDF and the page print one range', () => {
    const exportMetadata = readFileSync(path.resolve(process.cwd(), '../backend/app/services/analysis_export_metadata.py'), 'utf8')
    expect(exportMetadata).toContain(`_PERIOD_KEY = r"${ANALYSIS_PERIOD_KEY}"`)
    // Its two ends joined by the en-dash, and a window of one period printed as that period (E177).
    expect(exportMetadata).toContain(String.raw`window[1] if window[1] == window[2] else f"{window[1]}\u2013{window[2]}"`)
  })
})

describe('the demo run on the page', () => {
  it('prints its window as a range in the teaser, in its text, its tooltips and its accessible names', () => {
    render(<AnalysisTeaser />)
    expect(windowPrints(document.body)).toEqual([])
    expect(document.body.textContent).toContain('Revenue CAGR was +8.7% over FY2020–FY2025')
    expect(document.body.textContent).toContain('Revenue CAGR · FY2020–FY2025 · +8.7%')
    expect(document.querySelector('[title="Computed over FY2020–FY2025"]')).not.toBeNull()
    expect(document.querySelector('[aria-label^="Revenue CAGR, FY2020–FY2025: +8.7%"]')).not.toBeNull()
  })

  it('prints it as a range on the landing’s Multi-Period screen', () => {
    render(<AnalysisDemo />)
    expect(windowPrints(document.body)).toEqual([])
    expect(screen.getByText(/· Annual · FY2020–FY2025$/)).toBeInTheDocument()
    expect(document.querySelector('[title^="Percentage-point change over FY2020–FY2025."]')).not.toBeNull()
  })

  it('prints it as a range in a reader’s own report, its data notes and its source dialog included', () => {
    render(<DataNotesProvider dataset={noted}>
      <KpiStrip dataset={noted} />
      <DataNotes dataset={noted} />
      <NarrativePane state={{ status: 'done', text: legacyCompletion.narrative, completion: legacyCompletion }} />
      <MetricsTable dataset={noted} />
    </DataNotesProvider>)
    expect(windowPrints(document.body)).toEqual([])
    expect(document.body.textContent).toContain('Comparisons: Revenue CAGR (FY2020–FY2025).')
    expect(document.body.textContent).toContain('Revenue CAGR was +8.7% over FY2020–FY2025')
    expect(screen.getByText('FY2020–FY2025', { selector: '[aria-hidden="true"]' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /^Revenue CAGR, FY2020–FY2025: \+8\.7%/ }))
    expect(screen.getByRole('dialog')).toHaveTextContent('Revenue CAGR · FY2020–FY2025')
    expect(windowPrints(document.body)).toEqual([])
  })
})

describe('the other windows a reader meets', () => {
  const coverage: AnalysisCoverage = {
    ticker: 'AAPL', company_name: 'Apple Inc.', supported: true, reason: null, syncing: false, synced_at: null,
    limits: { annual: 10, quarterly: 12 },
    annual: run.periods.map((period) => ({ key: period.key, fiscal_year: period.fiscal_year, period_end: period.period_end, has_core: true })),
    quarterly: Array.from({ length: 8 }, (_, index) => {
      const fiscal_year = 2024 + Math.floor(index / 4)
      const fiscal_period = `Q${index % 4 + 1}`
      return { key: `${fiscal_year}${fiscal_period}`, fiscal_year, fiscal_period, period_end: `${fiscal_year}-12-31`, derived: false }
    }),
  }

  it.each([
    { mode: 'annual' as const, range: { start: 'FY2020', end: 'FY2025' }, line: 'FY2020–FY2025 · 6 years' },
    { mode: 'quarterly' as const, range: { start: '2024Q1', end: '2025Q4' }, line: 'Q1 2024–Q4 2025 · 8 quarters' },
    // E177: a selection of one period names that period, as the exports' period_label prints its key.
    { mode: 'annual' as const, range: { start: 'FY2021', end: 'FY2021' }, line: 'FY2021 · 1 year' },
    { mode: 'quarterly' as const, range: { start: '2025Q3', end: '2025Q3' }, line: 'Q3 2025 · 1 quarter' },
  ])('names the $mode range under the period picker as one window: $line', ({ mode, range, line }) => {
    render(<PeriodPicker coverage={coverage} mode={mode} range={range} onModeChange={vi.fn()} onRangeChange={vi.fn()} />)
    expect(screen.getByText(line)).toBeInTheDocument()
    expect(windowPrints(document.body)).toEqual([])
  })

  it('prints a window as a range while the narrative streams', () => {
    render(<NarrativePane state={{ status: 'streaming', text: 'Revenue CAGR was +8.7% over FY2020..FY2025 [F12]. Margins held from 2024Q1..2025Q4.' }} />)
    expect(windowPrints(document.body)).toEqual([])
    expect(document.body.textContent).toContain('over FY2020–FY2025 [F12]. Margins held from Q1 2024–Q4 2025.')
  })

  it('reads a CAGR excerpt’s window as a range, and leaves an excerpt the citation reader cannot parse as written', () => {
    const citation = completion.citations[1] as AnalysisCitation
    expect(citation.excerpt).toBe('Revenue CAGR = +8.7% (FY2020..FY2025)')
    expect(citationDisplay(citation)).toMatch(/^Revenue CAGR · FY2020–FY2025 · \+8\.7% /)
    // The gap, planted: an excerpt the reader cannot parse shows exactly as the server wrote it (the fail-open that
    // narrative-pane.spec.tsx holds), so a key inside one stays a key.
    expect(citationDisplay({ ...citation, excerpt: 'Revenue CAGR over FY2020..FY2025' })).toBe('Revenue CAGR over FY2020..FY2025')
  })
})

describe('where a window is read and joined', () => {
  const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
  const FORMATTER = 'features/analysis/lib/periodLabels.ts'
  const read = (file: string) => readFileSync(path.join(FRONTEND, file), 'utf8')
  /** Every tracked script outside tests/ (git ls-files), whatever its extension. */
  const SOURCES = execFileSync('git', ['ls-files', '*.ts', '*.tsx', '*.js', '*.jsx', '*.mjs', '*.cjs', '*.mts', '*.cts'], { cwd: FRONTEND, encoding: 'utf8' })
    .split('\n').filter((file) => file && !file.startsWith('tests/') && !file.endsWith('.d.ts'))
  // The analysis code, and every file elsewhere that imports from it (the landing's Multi-Period screen among them).
  const SCOPE = SOURCES.filter((file) => file.startsWith('features/analysis/') || /from ['"](?:@\/features\/analysis\/|(?:\.\.\/)+analysis\/)/.test(read(file)))
  /** An en-dash in the scope that joins no period window ("10–20 seconds"), by file and text, with its reason. */
  const NOT_A_WINDOW: Array<{ file: string; text: string; reason: string }> = []
  const parse = (file: string, text: string) =>
    ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, /\.[jt]sx$/.test(file) ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const lineOf = (source: ts.SourceFile, node: ts.Node) => source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1

  const ENTITY = /&(?:ndash|#8211|#x2013);/i
  /** Each string, template text or JSX text that holds an en-dash, written, escaped or as an entity JSX decodes, and
   *  each String.fromCharCode or fromCodePoint that makes one. Comments are not read. */
  function enDashes(file: string, text: string): Array<{ line: number; text: string }> {
    const source = parse(file, text)
    const found: Array<{ line: number; text: string }> = []
    const visit = (node: ts.Node) => {
      if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isTemplateHead(node)
        || ts.isTemplateMiddle(node) || ts.isTemplateTail(node) || ts.isJsxText(node)) {
        const jsx = ts.isJsxText(node) || ts.isJsxAttribute(node.parent)
        if (node.text.includes('\u2013') || (jsx && ENTITY.test(node.text))) found.push({ line: lineOf(source, node), text: node.text })
      }
      if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)
        && ts.isIdentifier(node.expression.expression) && node.expression.expression.text === 'String'
        && ['fromCharCode', 'fromCodePoint'].includes(node.expression.name.text)
        && node.arguments.some((arg) => ts.isNumericLiteral(arg) && Number(arg.text) === 0x2013)) {
        found.push({ line: lineOf(source, node), text: node.getText(source) })
      }
      ts.forEachChild(node, visit)
    }
    visit(source)
    return found
  }

  const WINDOW_FIELDS = new Set(['period_key', 'cagr_window', 'window_pp_range'])
  /** In the analysis code a `period` is read too: a citation's, a point's or a note's carries a CAGR's window. Outside
   *  it the name is any one period's (RevenueBars' bars), so it is not. */
  const SCOPE_FIELDS = new Set([...WINDOW_FIELDS, 'period'])
  /** A window field read into text no reader meets (a URL, a storage key), by file and text, with its reason. */
  const NOT_PAGE_TEXT: Array<{ file: string; text: string; reason: string }> = []
  /** The lines where a window key the API carries is read straight into page text: JSX text, an element's or a
   *  component's prop or a template, through `??`, `||`, `+`, the right of `&&` and a conditional's arms. A field
   *  counts read off its object or by its own name (`const { cagr_window } = series`). Any call takes the key out of
   *  this reading, the formatter's included, and so do an object literal, data handed on (SourceValue's `point`),
   *  React's own key and ref, and a `data-*` attribute, which no reader meets either (the trend charts' `data-period`,
   *  spec D4). A template counts wherever else it goes, since one held in an object or a variable is printed later
   *  (KpiStrip's tooltip was one). */
  function rawWindowReads(file: string, text: string, fields = WINDOW_FIELDS): Array<{ line: number; text: string }> {
    const source = parse(file, text)
    const lines = text.split('\n')
    const found = new Map<number, string>()
    const callee = (call: ts.CallExpression) => (ts.isIdentifier(call.expression) ? call.expression.text
      : ts.isPropertyAccessExpression(call.expression) ? call.expression.name.text : undefined)
    const isRead = (node: ts.Node) => (ts.isPropertyAccessExpression(node) && fields.has(node.name.text))
      || (ts.isElementAccessExpression(node) && ts.isStringLiteralLike(node.argumentExpression) && fields.has(node.argumentExpression.text))
      || (ts.isIdentifier(node) && WINDOW_FIELDS.has(node.text))
      || (ts.isCallExpression(node) && callee(node) === 'windowRange')
    const reactOwn = (node: ts.Node) => ts.isJsxAttribute(node) && ts.isIdentifier(node.name)
      && (['key', 'ref'].includes(node.name.text) || node.name.text.startsWith('data-'))
    /** Whether a value goes on through `node` from its `child` as it is: parentheses, `as`, `!`, `satisfies`, `??`,
     *  `||`, `+`, the right of `&&` and a conditional's arms. */
    const carries = (node: ts.Node, child: ts.Node): boolean => {
      if (ts.isParenthesizedExpression(node) || ts.isAsExpression(node) || ts.isNonNullExpression(node) || ts.isSatisfiesExpression(node)) return true
      if (ts.isConditionalExpression(node)) return child !== node.condition
      if (!ts.isBinaryExpression(node)) return false
      const op = node.operatorToken.kind
      return op === ts.SyntaxKind.QuestionQuestionToken || op === ts.SyntaxKind.BarBarToken || op === ts.SyntaxKind.PlusToken
        || (op === ts.SyntaxKind.AmpersandAmpersandToken && child === node.right)
    }
    /** Where a value lands: the first node past the ones it goes on through. */
    const destination = (value: ts.Node): ts.Node => {
      let child = value
      while (carries(child.parent, child)) child = child.parent
      return child.parent
    }
    const printed = (read: ts.Node): boolean => {
      const node = destination(read)
      if (ts.isTemplateSpan(node)) {
        if (ts.isTaggedTemplateExpression(node.parent.parent)) return false
        const template = destination(node.parent)
        return !(ts.isJsxExpression(template) && reactOwn(template.parent))
      }
      // A component's prop counts too (ChartTooltip prints its label).
      return ts.isJsxExpression(node) && !reactOwn(node.parent)
    }
    const visit = (node: ts.Node) => {
      if (isRead(node) && printed(node)) { const line = lineOf(source, node); found.set(line, lines[line - 1].trim()) }
      ts.forEachChild(node, visit)
    }
    visit(source)
    return [...found].map(([line, text]) => ({ line, text }))
  }

  it('reads every way a range is spelled, and no comment', () => {
    for (const planted of [
      'const a = `${start}–${end}`',
      "const b = start + ' – ' + end",
      'const c = <p>{start} – {end}</p>',
      'const d = <p title="FY2020–FY2025" />',
      "const e = [start, end].join('\\u2013')",
      'const f = `From ${start}–`',
      'const g = <p>{start}&ndash;{end}</p>',
      'const h = <p>{start}&#8211;{end}</p>',
      'const i = <p title="FY2020&#x2013;FY2025" />',
      'const j = [start, end].join(String.fromCharCode(8211))',
      'const k = String.fromCodePoint(0x2013)',
    ]) expect(enDashes('planted.tsx', planted).map((found) => found.line), planted).toEqual([1])
    expect(enDashes('planted.tsx', '// FY2020–FY2025\n/** 8–9px */ const l = 1\nconst m = "&ndash; is only JSX\'s"')).toEqual([])
  })

  it('reads a window field printed past the formatter, and marks what it cannot follow', () => {
    for (const planted of [
      'const a = <p>{dataset.period_key}</p>',
      'const b = <span title={series.cagr_window} />',
      'const c = `Percentage-point change over ${row.series.window_pp_range}.`',
      'const d = <p>{series.cagr_window ?? dataset.period_key}</p>',
      "const e = <abbr title={dataset['period_key']} />",
      'const f = `Computed over ${windowRange(series)}`',
      "const g = <p>{'over ' + dataset.period_key}</p>",
      'const h = <p>{annual ? series.cagr_window : point.period}</p>',
      'const i = <ChartTooltip label={dataset.period_key} />',
      'const j = `Computed over ${growth.windowRange(series)}`',
      'const k = ({ cagr_window }: Series) => <p>{cagr_window}</p>',
      // An ARIA attribute is read aloud; only data-* is unread.
      'const o = <rect aria-label={dataset.period_key} />',
      // A template assigned on its way to a key is kept, and may be printed later.
      'const n = <Row key={(label = `${dataset.period_key}`)} />',
    ]) expect(rawWindowReads('planted.tsx', planted).map((found) => found.line), planted).toEqual([1])
    expect(rawWindowReads('planted.tsx', 'const l = <p>{citation.period}</p>', SCOPE_FIELDS).map((found) => found.line)).toEqual([1])
    expect(rawWindowReads('planted.tsx', 'const m = <rect data-period={bar.period} />', SCOPE_FIELDS)).toEqual([])
    for (const clear of [
      'const a = <p>{formatAnalysisPeriod(dataset.period_key)}</p>',
      'const b = comparisonId(series.concept, windowRange(series) ?? dataset.period_key)',
      'const c = { periodKey: dataset.period_key }',
      'const d = <SourceValue point={{ period: series.cagr_window ?? dataset.period_key }} />',
      'const e = <p>{series.cagr_window && <Mark />}</p>',
      "const f = `${dataset.ticker}_${dataset.period_key.replace(/\\.\\./g, '-')}.png`",
      'const g = series.cagr_window ? `Computed over ${formatAnalysisPeriod(series.cagr_window)}` : undefined',
      'const h = <Row key={dataset.period_key} />',
      'const l = <Row key={`${dataset.period_key}-${series.concept}`} />',
      'const n = <rect data-period={dataset.period_key} data-key={`${dataset.period_key}`} />',
      // Outside the analysis code a `period` is any one period's: RevenueBars prints its bars' annual keys.
      'const m = <span>{bar.period}</span>',
      // The gaps: a key held in a variable of another name or in an object first, or handed to another function.
      'const w = windowRange(series)\nconst i = <p>{w}</p>',
      'const j = <Header labels={{ title: dataset.period_key }} />',
      'const k = <p>{String(dataset.period_key)}</p>',
    ]) expect(rawWindowReads('planted.tsx', clear), clear).toEqual([])
  })

  it('reads a window field into page text only through the formatter', () => {
    const scope = new Set(SCOPE)
    const raw = SOURCES.flatMap((file) => rawWindowReads(file, read(file), scope.has(file) ? SCOPE_FIELDS : WINDOW_FIELDS)
      .filter((found) => !NOT_PAGE_TEXT.some((entry) => entry.file === file && found.text.includes(entry.text)))
      .map((found) => `${file}:${found.line}`))
    expect(raw, 'Print a window field through formatAnalysisPeriod or formatAnalysisWindow (features/analysis/lib/periodLabels.ts); '
      + 'a read no reader meets (a URL, a storage key) takes a NOT_PAGE_TEXT entry with its reason.').toEqual([])
  })

  it('holds an en-dash only in the formatter, so no surface joins two periods itself', () => {
    expect(SCOPE).toEqual(expect.arrayContaining([
      FORMATTER, 'features/analysis/components/DataNotes.tsx', 'features/analysis/components/PeriodPicker.tsx',
      'features/analysis/components/MetricsTable.tsx', 'features/analysis/components/AnalysisTeaser.tsx',
      'features/marketing/components/AnalysisDemo.tsx', 'app/analysis/page.tsx',
    ]))
    expect(enDashes(FORMATTER, read(FORMATTER)).length).toBeGreaterThan(0)
    const outside = SCOPE.filter((file) => file !== FORMATTER).flatMap((file) => enDashes(file, read(file))
      .filter((found) => !NOT_A_WINDOW.some((entry) => entry.file === file && found.text.includes(entry.text)))
      .map((found) => `${file}:${found.line}`))
    expect(outside, 'Join a period window through formatAnalysisWindow (features/analysis/lib/periodLabels.ts); an en-dash that '
      + 'joins no period window takes a NOT_A_WINDOW entry with its reason.').toEqual([])
  })
})
