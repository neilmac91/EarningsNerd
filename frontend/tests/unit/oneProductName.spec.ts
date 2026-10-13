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
 * hooks and lib, the way brandCopyRules.spec.ts reads them, and fails on the capitalised name
 * ("Copilot") or the lowercase phrase "the copilot". Internal identifiers are not copy and do not trip
 * it: the case-sensitive name never matches the lowercase PostHog events ("copilot_question_asked"),
 * tab ids, storage keys or class names ("copilot-answer"), a file or component name ("CopilotMessage")
 * has no word break after the name, and module specifiers (an import, an export, a dynamic import) and
 * console arguments are skipped. NAME_RESIDUE lists each file that still says the name, with the count
 * and why; the count is an equality, so a site that leaves must delete its line.
 */
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']
const NAMES = [/\bCopilot\b/, /\bthe copilot\b/i]

const NAME_RESIDUE: Record<string, { count: number; why: string }> = {
  'app/security/page.tsx': {
    count: 1,
    why: 'the DeepSeek line ("powering summaries and Copilot") is on a legal page, off limits until the founder decides the /security claims',
  },
}

/** True when a literal's text names the feature the old way. */
const saysCopilot = (text: string) => NAMES.some((name) => name.test(text))

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

const SOURCES = SCAN_DIRS.flatMap((dir) => walk(path.join(ROOT, dir))).map((file) => ({
  rel: path.relative(ROOT, file).split(path.sep).join('/'),
  sf: ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS),
}))

/** Every copy literal that says the old name, by file. */
function sites(): Map<string, string[]> {
  const out = new Map<string, string[]>()
  for (const { rel, sf } of SOURCES) {
    visit(sf, (n) => {
      const text = copyText(n)
      if (text === null || notCopy(n) || !saysCopilot(text)) return
      const line = sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1
      out.set(rel, [...(out.get(rel) ?? []), `${rel}:${line} ${JSON.stringify(text.trim().slice(0, 80))}`])
    })
  }
  return out
}

describe('one product name in copy (D-034)', () => {
  it('no shipped string or JSX text calls the feature "Copilot" or "the copilot" outside NAME_RESIDUE', () => {
    const offenders: string[] = []
    for (const [rel, found] of sites()) {
      const listed = NAME_RESIDUE[rel]
      if (!listed) offenders.push(...found)
      else if (found.length !== listed.count) offenders.push(`${rel}: ${found.length} sites, NAME_RESIDUE lists ${listed.count}: ${found.join(' | ')}`)
    }
    expect(offenders, 'say "Ask this Filing" as a name, "ask this filing" in a sentence').toEqual([])
  })

  it('NAME_RESIDUE holds no stale line: every listed file exists and still says the name', () => {
    const found = sites()
    const stale = Object.keys(NAME_RESIDUE).filter((rel) => !found.has(rel))
    expect(stale, 'a residue line whose site left: delete it').toEqual([])
    for (const [rel, { why }] of Object.entries(NAME_RESIDUE)) expect(why.length, rel).toBeGreaterThan(20)
  })

  it('the classifier flags the old name and leaves internal identifiers alone (self-check)', () => {
    for (const copy of ['Ask the Copilot', 'Tap a question to ask the Copilot.', 'Copilot questions', 'Open the copilot']) {
      expect(saysCopilot(copy), copy).toBe(true)
    }
    for (const id of ['copilot_question_asked', 'copilot_rail', 'copilot-answer tnum font-data', 'CopilotMessage', './CopilotTeaser', 'copilot:paneWidth', 'Ask this Filing', 'Sign in to ask this filing a question.']) {
      expect(saysCopilot(id), id).toBe(false)
    }
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
