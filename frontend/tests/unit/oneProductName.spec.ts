import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * One product name in copy (D-034; CLAUDE.md rule 12): the feature is "Ask this Filing" as a name and
 * "ask this filing" inside a sentence, and "Copilot" leaves user copy. Two names for one feature read
 * as two features.
 *
 * The scan reads every string literal, template part and JSX text under app, components, features,
 * hooks and lib, the way brandCopyRules.spec.ts reads them, and counts each mention of the name, its
 * plural and the hyphenated spelling included. In any literal, a one-word label too, it fails on the
 * capitalised "Copilot" and on "co-pilot" in any case, since no identifier is spelled either way. Where a
 * literal reads as copy (JSX text, a string of more than one word, a template part with whitespace at a
 * substitution edge, as the tail " copilot" of `Ask your ${type} copilot`, or a literal substituted into a
 * template whose joined text reads as copy, as 'copilot' in `Ask the ${'copilot'} now`) it fails on the word in any
 * case, and only a letter, a digit or `_` joins it to more there: "Ask the copilot: what changed", "the
 * copilot-powered rail", "the copilot/filing pane" and "Ask @copilot anything" fail. A one-word literal is
 * read as an id and keeps the joins (`:`, `-`, `/`, `.`, `@`): the "copilot" tab id, the PostHog event
 * "copilot_question_asked", the class "copilot-answer", the storage key "copilot:paneWidth", the path
 * "/api/copilot/ask", and a component or module name ("CopilotMessage", which has no word break after the
 * name). A class list is not copy either: a className attribute's value or an argument of cx or clsx,
 * through conditionals, `&&`, `||`, `??`, `+`, templates, arrays and objects, or a same-file const that is
 * not exported and is read only in such places (matched by name). Module specifiers (an import, an export,
 * a dynamic import, require) and console arguments are skipped. Known limits: a one-word literal that is
 * copy still reads as an id (`title="copilot"` passes), and a name split across literals or JSX elements
 * is not read. NAME_RESIDUE lists each file that still says the name, with its count of mentions and
 * why; the count is an equality, so a site that leaves must delete its line.
 */
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']
/** The capitalised name and the hyphenated spelling in any case: a mention in any literal, a one-word label included. */
const IN_ANY_LITERAL = [/\bCopilots?\b/g, /\bco-pilots?\b/gi]
/** The word in any case, either spelling, where a literal reads as copy: only a letter, a digit or `_` joins it to more. */
const IN_COPY = /\bco-?pilots?\b/gi

const NAME_RESIDUE: Record<string, { count: number; why: string }> = {
  'app/security/page.tsx': {
    count: 1,
    why: 'the DeepSeek line ("powering summaries and Copilot") is on a legal page, off limits until the founder decides the /security claims',
  },
}

/** How many times a literal's text names the feature the old way (each mention once, whichever pattern finds it). */
function mentions(text: string, copy: boolean): number {
  const at = new Set<number>()
  for (const name of copy ? [...IN_ANY_LITERAL, IN_COPY] : IN_ANY_LITERAL) for (const match of text.matchAll(name)) at.add(match.index)
  return at.size
}

/** True when a text names the feature the old way: JSX text and a string of more than one word read as copy. */
const saysCopilot = (text: string, jsxText = false) => mentions(text, jsxText || /\S\s+\S/.test(text.trim())) > 0

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(entry.name) && !/\.(spec|test)\.tsx?$|\.d\.ts$/.test(entry.name)) out.push(p)
  }
  return out
}

const visit = (node: ts.Node, fn: (n: ts.Node) => void) => {
  fn(node)
  ts.forEachChild(node, (child) => visit(child, fn))
}

/** The text of a literal that can reach the screen, or null. */
function copyText(node: ts.Node): string | null {
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isJsxText(node)) return node.text
  if (ts.isTemplateHead(node) || ts.isTemplateMiddle(node) || ts.isTemplateTail(node)) return node.text
  return null
}

/** The string a substitution holds: a literal, through parentheses, `as` and a conditional's branches; '' otherwise. */
function substitutedText(e: ts.Expression): string {
  if (ts.isParenthesizedExpression(e) || ts.isAsExpression(e)) return substitutedText(e.expression)
  if (ts.isStringLiteral(e) || ts.isNoSubstitutionTemplateLiteral(e)) return e.text
  if (ts.isConditionalExpression(e)) return substitutedText(e.whenTrue) || substitutedText(e.whenFalse)
  return ''
}

/** The template a literal is substituted into (through parentheses, `as`, a conditional's branches, `&&`, `||`, `??` and
    `+`), or null. */
function templateOf(node: ts.Node): ts.TemplateExpression | null {
  for (let at: ts.Node = node, p = node.parent; p; at = p, p = p.parent) {
    if (ts.isTemplateSpan(p)) return p.expression === at ? p.parent : null
    const passes = ts.isParenthesizedExpression(p) || ts.isAsExpression(p) ||
      (ts.isConditionalExpression(p) && p.condition !== at) || (ts.isBinaryExpression(p) && JOINS_CLASSES.has(p.operatorToken.kind))
    if (!passes) return null
  }
  return null
}

/** JSX text, a string of more than one word, a template part with whitespace at a substitution edge, or a literal substituted
    into a template whose joined text has more than one word reads as copy; any other one-word literal may be an id. */
function readsAsCopy(node: ts.Node, text: string): boolean {
  if (ts.isJsxText(node) || /\S\s+\S/.test(text.trim())) return true
  const openEnd = (ts.isTemplateHead(node) || ts.isTemplateMiddle(node)) && /\s$/.test(text)
  const openStart = (ts.isTemplateMiddle(node) || ts.isTemplateTail(node)) && /^\s/.test(text)
  if (openEnd || openStart) return true
  const template = (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) ? templateOf(node) : null
  if (!template) return false
  const joined = template.head.text + template.templateSpans.map((span) => substitutedText(span.expression) + span.literal.text).join('')
  return /\S\s+\S/.test(joined.trim())
}

/** A module specifier (import, export, import(), require) or a console argument: never user copy. */
function notCopy(node: ts.Node): boolean {
  const parent = node.parent
  if (!parent) return false
  if ((ts.isImportDeclaration(parent) || ts.isExportDeclaration(parent)) && parent.moduleSpecifier === node) return true
  if (ts.isExternalModuleReference(parent)) return true
  if (ts.isCallExpression(parent)) {
    if (parent.expression.kind === ts.SyntaxKind.ImportKeyword) return true
    if (ts.isIdentifier(parent.expression) && parent.expression.text === 'require') return true
    const callee = parent.expression
    if (ts.isPropertyAccessExpression(callee) && ts.isIdentifier(callee.expression) && callee.expression.text === 'console') return true
  }
  return false
}

const CLASS_HELPERS = new Set(['cx', 'clsx'])
const JOINS_CLASSES = new Set([ts.SyntaxKind.AmpersandAmpersandToken, ts.SyntaxKind.BarBarToken, ts.SyntaxKind.QuestionQuestionToken, ts.SyntaxKind.PlusToken])

/** True when a node is a class list, never copy: a className attribute's value or a cx or clsx argument, through
    conditionals, `&&`, `||`, `??`, `+`, templates, arrays and objects, or a same-file const read only in such places. */
function inClassList(node: ts.Node, sf: ts.SourceFile): boolean {
  for (let at = node, p = node.parent; p; at = p, p = p.parent) {
    if (ts.isJsxAttribute(p)) return p.name.getText(sf) === 'className'
    if (ts.isPropertyAssignment(p) && p.initializer === at && p.name.getText(sf) === 'className') return true
    if (ts.isCallExpression(p)) return p.arguments.some((arg) => arg === at) && ts.isIdentifier(p.expression) && CLASS_HELPERS.has(p.expression.text)
    if (ts.isVariableDeclaration(p)) return p.initializer === at && classConst(p, sf)
    if (ts.isConditionalExpression(p) && p.condition === at) return false
    if (ts.isBinaryExpression(p) && !JOINS_CLASSES.has(p.operatorToken.kind)) return false
    const passes =
      ts.isJsxExpression(p) || ts.isParenthesizedExpression(p) || ts.isConditionalExpression(p) || ts.isBinaryExpression(p) ||
      ts.isTemplateSpan(p) || ts.isTemplateExpression(p) || ts.isArrayLiteralExpression(p) || ts.isPropertyAssignment(p) ||
      ts.isObjectLiteralExpression(p) || ts.isAsExpression(p) || ts.isSatisfiesExpression(p)
    if (!passes) return false
  }
  return false
}

/** A same-file const, not exported, read only as a class list (by name; a cycle reads as copy). */
const CLASS_CONSTS = new Map<ts.VariableDeclaration, boolean>()
function classConst(declaration: ts.VariableDeclaration, sf: ts.SourceFile): boolean {
  const known = CLASS_CONSTS.get(declaration)
  if (known !== undefined) return known
  CLASS_CONSTS.set(declaration, false)
  const list = declaration.parent
  const statement = list.parent
  const exported = ts.isVariableStatement(statement) && !!statement.modifiers?.some((m) => m.kind === ts.SyntaxKind.ExportKeyword)
  if (!ts.isIdentifier(declaration.name) || !(list.flags & ts.NodeFlags.Const) || exported) return false
  const name = declaration.name.text
  const reads: ts.Node[] = []
  visit(sf, (n) => {
    if (!ts.isIdentifier(n) || n.text !== name || n === declaration.name) return
    const p = n.parent
    const fieldName = (ts.isPropertyAccessExpression(p) || ts.isPropertyAssignment(p) || ts.isJsxAttribute(p)) && p.name === n
    if (!fieldName) reads.push(n)
  })
  const result = reads.length > 0 && reads.every((read) => inClassList(read, sf))
  CLASS_CONSTS.set(declaration, result)
  return result
}

const parse = (file: string, text: string) =>
  ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)

const SOURCES = SCAN_DIRS.flatMap((dir) => walk(path.join(ROOT, dir))).map((file) => ({
  rel: path.relative(ROOT, file).split(path.sep).join('/'),
  sf: parse(file, readFileSync(file, 'utf8')),
}))

/** Every mention of the old name in copy, by file: a literal that says it twice is listed twice. */
function sites(sources: { rel: string; sf: ts.SourceFile }[] = SOURCES): Map<string, string[]> {
  const out = new Map<string, string[]>()
  for (const { rel, sf } of sources) {
    visit(sf, (n) => {
      const text = copyText(n)
      if (text === null) return
      const count = mentions(text, readsAsCopy(n, text))
      if (!count || notCopy(n) || inClassList(n, sf)) return
      const line = sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1
      out.set(rel, [...(out.get(rel) ?? []), ...Array<string>(count).fill(`${rel}:${line} ${JSON.stringify(text.trim().slice(0, 80))}`)])
    })
  }
  return out
}

describe('one product name in copy (D-034)', () => {
  it('no shipped string or JSX text calls the feature "Copilot", in any case, outside NAME_RESIDUE', () => {
    const offenders: string[] = []
    for (const [rel, found] of sites()) {
      const listed = NAME_RESIDUE[rel]
      if (!listed) offenders.push(...found)
      else if (found.length !== listed.count) offenders.push(`${rel}: ${found.length} mentions, NAME_RESIDUE lists ${listed.count}: ${found.join(' | ')}`)
    }
    expect(offenders, 'say "Ask this Filing" as a name, "ask this filing" in a sentence').toEqual([])
  })

  it('NAME_RESIDUE holds no stale line: every listed file exists and still says the name', () => {
    const found = sites()
    const stale = Object.keys(NAME_RESIDUE).filter((rel) => !found.has(rel))
    expect(stale, 'a residue line whose site left: delete it').toEqual([])
    for (const [rel, { why }] of Object.entries(NAME_RESIDUE)) expect(why.length, rel).toBeGreaterThan(20)
  })

  it('the classifier flags the old name in any case and leaves internal identifiers alone (self-check)', () => {
    for (const copy of [
      'Ask the Copilot', 'Tap a question to ask the Copilot.', 'Copilot questions', 'Copilot', 'Open the copilot',
      // Lowercase, in a sentence: the planted phrases round 2's gate let through.
      'You have 2 free copilot questions left', 'Meet your filing copilot.', 'An AI copilot for SEC filings', 'copilot answers, cited',
      // Joined to punctuation in copy: the planted phrases round 3's gate let through.
      'Ask the copilot: what changed', 'the copilot-powered rail', 'the copilot/filing pane', 'Meet your copilot: answers', 'copilot: ready',
      'Ask @copilot anything', 'Open the .copilot pane', 'AI copilots for filings', 'the copilot’s answer',
      // The hyphenated spelling, in any literal and any case, a one-word label included.
      'co-pilot', 'Co-pilot', 'Co-Pilot', 'Ask the co-pilot', 'Your filing CO-PILOT',
    ]) {
      expect(saysCopilot(copy), copy).toBe(true)
    }
    for (const text of ['copilot', 'copilot:', 'copilot-powered', 'copilot/filing', '@copilot', '.copilot']) {
      expect(saysCopilot(text, true), `JSX text "${text}" is copy`).toBe(true)
    }
    for (const id of [
      // One-word ids keep the joins: the same joined forms pass as a single word.
      'copilot_question_asked', 'copilot_rail', 'copilot-answer', 'CopilotMessage', './CopilotTeaser', 'copilot:paneWidth', 'copilot',
      'copilot-1712345678-0', '--copilot-w', '/api/copilot/ask', 'copilot:', 'copilot-powered', 'copilot/filing', '@copilot', '.copilot',
      // In copy, a letter, a digit or `_` still joins the word to an identifier.
      'the copilot_question_asked event', 'Ask this Filing', 'Sign in to ask this filing a question.',
    ]) {
      expect(saysCopilot(id), id).toBe(false)
    }
    // A class list reads as copy by its text alone; its place exempts it (next case).
    expect(saysCopilot('copilot-answer tnum font-data'), 'a class list held in a string').toBe(true)
  })

  it('a class list is no copy, a template part open at its edge is, and each mention counts (self-check)', () => {
    const planted = parse('planted.tsx', [
      "const REGISTER = 'copilot-answer tnum font-data'",
      "const LABEL = 'Ask @copilot anything'",
      'export const A = ({ open, type }: { open: boolean; type: string }) => (',
      "  <div className={cx(REGISTER, open && 'copilot-open grid')} data-x={`copilot-${type}`}>",
      "    <p className={`lg:grid-cols-[minmax(0,1fr)_var(--copilot-w)] ${open ? 'copilot-wide x' : ''}`} title={`Ask your ${type} copilot`}>",
      '      {LABEL} Meet your copilot: answers. The Copilot, the co-pilot.',
      '    </p>',
      '  </div>',
      ')',
      "export const B = () => <span className={EXPORTED}>{SHOWN}</span>",
      "export const EXPORTED = 'copilot-chip x'",
      "const SHOWN = 'copilot-chip y'",
      "export const C = ({ id }: { id: string }) => <p title={`Ask the ${'copilot'} now`} data-x={`${'copilot'}-${id}`}>x</p>",
    ].join('\n'))
    const lines = (sites([{ rel: 'planted.tsx', sf: planted }]).get('planted.tsx') ?? []).map((site) => Number(/:(\d+) /.exec(site)?.[1]))
    // 2: a const read as text; 5: the tail " copilot"; 6: three mentions in one JSX text; 11: an exported const may be read
    // elsewhere; 12: a const read as text; 13: a one-word literal substituted into a sentence. The cx and className lists
    // (1, 4, 5), the one-word id `copilot-${type}` and the one-word joined id `${'copilot'}-${id}` pass.
    expect(lines).toEqual([2, 5, 6, 6, 6, 11, 12, 13])
  })

  it('the scan sees the Ask surfaces it guards', () => {
    const rels = new Set(SOURCES.map((s) => s.rel))
    for (const rel of [
      'features/filings/components/copilot/AskCopilotRail.tsx', 'features/filings/components/copilot/CopilotMessage.tsx',
      'features/filings/api/copilot-api.ts', 'features/summaries/components/SummaryDisplay.tsx', 'app/security/page.tsx',
    ]) {
      expect(rels.has(rel), rel).toBe(true)
    }
  })
})
