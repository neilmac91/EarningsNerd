import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { bindingResolver } from './astBindings'

/**
 * Data notes must not bring full-width status pills back into analysis figures.
 * Inspect syntax, not source text: comments do not count; string/template chunks
 * and imported aliases do. This is a source gate, not a substitute for browser
 * overflow, focus or contrast checks. Dynamically assembled utility names are
 * outside its scope (and outside Tailwind's supported literal-class discovery).
 */
const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const ANALYSIS = 'features/analysis/'
const COMPACT_SURFACES = [
  `${ANALYSIS}components/KpiStrip.tsx`,
  `${ANALYSIS}components/MetricsTable.tsx`,
]
const OLD_BADGE = `${ANALYSIS}components/ReconciliationBadge`
const SOURCE_BADGE = 'features/fundamentals/components/SourceCheckBadge'
// Shrink-only: remove a consumer when it migrates; never add a new badge surface.
const SOURCE_BADGE_CONSUMERS = new Set([
  'features/fundamentals/components/FundamentalsTrendChart.tsx',
  'features/peers/components/PeerComparisonPanel.tsx',
])

function parse(source: string, file = 'fixture.tsx'): ts.SourceFile {
  const kind = file.endsWith('.json') ? ts.ScriptKind.JSON
    : /\.[cm]?jsx$/.test(file) ? ts.ScriptKind.JSX
      : /\.[cm]?js$/.test(file) ? ts.ScriptKind.JS
        : file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS
  return ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, kind)
}

function visit(node: ts.Node, inspect: (node: ts.Node) => void): void {
  inspect(node)
  ts.forEachChild(node, (child) => visit(child, inspect))
}

function location(file: ts.SourceFile, node: ts.Node): string {
  return `${file.fileName}:${file.getLineAndCharacterOfPosition(node.getStart(file)).line + 1}`
}

/** @/ and relative imports resolve to the same module identity, with or without extensions. */
function modulePath(file: string, specifier: string): string | undefined {
  const absolute = specifier.startsWith('@/') ? resolve(ROOT, specifier.slice(2))
    : specifier.startsWith('.') ? resolve(ROOT, dirname(file), specifier) : undefined
  return absolute && relative(ROOT, absolute).replaceAll('\\', '/')
    .replace(/\.[cm]?[jt]sx?$/, '').replace(/\/index$/, '')
}

function moduleReferences(file: ts.SourceFile): Array<{ node: ts.Node; target: string }> {
  const found: Array<{ node: ts.Node; target: string }> = []
  visit(file, (node) => {
    let specifier: ts.Node | undefined
    if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) specifier = node.moduleSpecifier
    else if (ts.isExternalModuleReference(node)) specifier = node.expression
    else if (ts.isCallExpression(node) && (
      node.expression.kind === ts.SyntaxKind.ImportKeyword ||
      (ts.isIdentifier(node.expression) && node.expression.text === 'require')
    )) specifier = node.arguments[0]
    if (specifier && ts.isStringLiteralLike(specifier)) {
      const target = modulePath(file.fileName, specifier.text)
      if (target) found.push({ node, target })
    }
  })
  return found
}

function classViolations(file: ts.SourceFile, compact: boolean): string[] {
  const found: string[] = []
  visit(file, (node) => {
    if (!(ts.isStringLiteralLike(node) || ts.isTemplateHead(node) ||
      ts.isTemplateMiddle(node) || ts.isTemplateTail(node))) return
    for (const token of node.text.split(/\s+/)) {
      if (compact && /(?:^|:)!?(?:whitespace-nowrap|text-nowrap|truncate|text-ellipsis|line-clamp-(?!none)[^:]+)!?$/.test(token)) {
        found.push(`${location(file, node)}: ${token} prevents analysis content from reflowing in full`)
      }
      const pixels = /(?:^|:)!?text-\[([+-]?(?:\d+(?:\.\d*)?|\.\d+))px\](?:\/[^\s!]+)?!?$/.exec(token)
      if (pixels && Number(pixels[1]) < 11) {
        found.push(`${location(file, node)}: ${token} is below the 11px analysis text floor`)
      }
    }
  })
  return found
}

function badgeViolations(file: ts.SourceFile): string[] {
  const found = moduleReferences(file).filter(({ target }) => target === 'components/ui/Badge')
    .map(({ node }) => `${location(file, node)}: Badge import; use a compact data note mark`)
  const namespaces = new Set<string>()
  const resolveBinding = bindingResolver(file)
  for (const statement of file.statements) {
    if (ts.isImportEqualsDeclaration(statement) && ts.isExternalModuleReference(statement.moduleReference) &&
      statement.moduleReference.expression && ts.isStringLiteralLike(statement.moduleReference.expression) &&
      modulePath(file.fileName, statement.moduleReference.expression.text) === 'components/ui') {
      namespaces.add(statement.name.text)
    }
    if (!ts.isImportDeclaration(statement) || !ts.isStringLiteral(statement.moduleSpecifier)) continue
    const target = modulePath(file.fileName, statement.moduleSpecifier.text)
    const bindings = statement.importClause?.namedBindings
    if (target === 'components/ui' && bindings && ts.isNamedImports(bindings) &&
      bindings.elements.some((entry) => (entry.propertyName ?? entry.name).text === 'Badge')) {
      found.push(`${location(file, statement)}: Badge import; use a compact data note mark`)
    }
    if (target === 'components/ui' && bindings && ts.isNamespaceImport(bindings)) namespaces.add(bindings.name.text)
  }
  // Follow same-file namespace aliases without mistaking a shadowed local UI for the imported UI.
  function isUiNamespace(node: ts.Node, seen = new Set<ts.Node>()): boolean {
    if (seen.has(node)) return false
    seen.add(node)
    if (ts.isParenthesizedExpression(node) || ts.isAsExpression(node) ||
      ts.isSatisfiesExpression(node) || ts.isNonNullExpression(node) || ts.isAwaitExpression(node)) {
      return isUiNamespace(node.expression, seen)
    }
    if (ts.isCallExpression(node) && (node.expression.kind === ts.SyntaxKind.ImportKeyword ||
      (ts.isIdentifier(node.expression) && node.expression.text === 'require'))) {
      const specifier = node.arguments[0]
      return !!specifier && ts.isStringLiteralLike(specifier) && modulePath(file.fileName, specifier.text) === 'components/ui'
    }
    if (!ts.isIdentifier(node)) return false
    const binding = resolveBinding(node)
    return binding ? !!binding.init && isUiNamespace(binding.init, seen) : namespaces.has(node.text)
  }
  visit(file, (node) => {
    if (ts.isPropertyAccessExpression(node) && node.name.text === 'Badge' && isUiNamespace(node.expression)) {
      found.push(`${location(file, node)}: UI Badge use; use a compact data note mark`)
    } else if (ts.isElementAccessExpression(node) && ts.isStringLiteralLike(node.argumentExpression) &&
      node.argumentExpression.text === 'Badge' && isUiNamespace(node.expression)) {
      found.push(`${location(file, node)}: UI Badge use; use a compact data note mark`)
    } else if (ts.isBindingElement(node) && ts.isObjectBindingPattern(node.parent) &&
      (node.propertyName ?? node.name).getText(file).replace(/^['"]|['"]$/g, '') === 'Badge' &&
      ts.isVariableDeclaration(node.parent.parent) && node.parent.parent.initializer &&
      isUiNamespace(node.parent.parent.initializer)) {
      found.push(`${location(file, node)}: destructured UI Badge use; use a compact data note mark`)
    } else if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) &&
      ts.isIdentifier(node.tagName) && node.tagName.text === 'Badge') {
      found.push(`${location(file, node)}: Badge element; use a compact data note mark`)
    }
  })
  return found
}

function badgeBoundaryViolations(file: ts.SourceFile): string[] {
  return moduleReferences(file).flatMap(({ node, target }) => {
    if (target === OLD_BADGE) return [`${location(file, node)}: retired analysis ReconciliationBadge import/re-export`]
    if (target === SOURCE_BADGE && !SOURCE_BADGE_CONSUMERS.has(file.fileName)) {
      return [`${location(file, node)}: SourceCheckBadge is reserved for the two existing fundamentals/peers consumers`]
    }
    return []
  })
}

// Git owns discovery, including new, unignored source before staging. Read the
// working copy so a deleted tracked module is not mistaken for current source.
const files = [...new Set(execFileSync('git', ['ls-files', '--cached', '--others', '--exclude-standard', '-z'], {
  cwd: ROOT, encoding: 'utf8',
}).split('\0').filter((file) => /\.[cm]?[jt]sx?$/.test(file) || (file.startsWith(ANALYSIS) && file.endsWith('.json'))))]
  .filter((file) => !file.startsWith('tests/') && existsSync(resolve(ROOT, file)))
const sources = files.map((file) => parse(readFileSync(resolve(ROOT, file), 'utf8'), file))

describe('analysis data-note presentation gate', () => {
  it('keeps Badge, nowrap and truncation tokens out of KPI and metrics-table source', () => {
    const offenders = COMPACT_SURFACES.flatMap((file) => {
      const source = parse(readFileSync(resolve(ROOT, file), 'utf8'), file)
      return [...badgeViolations(source), ...classViolations(source, true)]
    })
    expect(offenders).toEqual([])
  })

  it('keeps every analysis source literal at or above the 11px text floor', () => {
    const analysis = sources.filter((source) => source.fileName.startsWith(ANALYSIS))
    expect(analysis.length, 'The analysis source discovery must not pass vacuously').toBeGreaterThan(10)
    expect(analysis.flatMap((source) => classViolations(source, false))).toEqual([])
  })

  it('keeps the relocated source badge behind a shrink-only consumer allowlist', () => {
    expect(SOURCE_BADGE_CONSUMERS.size).toBeLessThanOrEqual(2)
    expect([...SOURCE_BADGE_CONSUMERS].some((file) => file.startsWith(ANALYSIS))).toBe(false)
    expect(sources.length, 'The import boundary must inspect frontend source').toBeGreaterThan(100)
    expect(sources.flatMap(badgeBoundaryViolations)).toEqual([])
    const consumers = new Set(sources.filter((source) =>
      moduleReferences(source).some(({ target }) => target === SOURCE_BADGE)).map((source) => source.fileName))
    expect([...SOURCE_BADGE_CONSUMERS].filter((file) => !consumers.has(file)),
      'Remove stale allowlist entries when a consumer stops using SourceCheckBadge').toEqual([])
  })

  it('recognizes Badge aliases, namespace access and namespace-derived aliases', () => {
    for (const code of [
      "import { Badge as Status } from '@/components/ui'; const view = <Status />",
      "import Status from '@/components/ui/Badge'; const view = <Status />",
      "import { Badge as Status } from '../../../components/ui/index'; const view = <Status />",
      "import * as UI from '@/components/ui'; const view = <UI.Badge />",
      "import * as UI from '@/components/ui'; const Kit = UI; const Status = Kit.Badge; const view = <Status />",
      "import * as UI from '@/components/ui'; const { Badge: Status } = UI; const view = <Status />",
      "import * as UI from '@/components/ui'; const Status = UI['Badge']; const view = <Status />",
      "import UI = require('@/components/ui'); const view = <UI.Badge />",
      "const { Badge: Status } = await import('@/components/ui'); const view = <Status />",
      "const UI = require('@/components/ui'); const Status = UI.Badge; const view = <Status />",
      "const Status = import('@/components/ui/Badge')",
    ]) expect(badgeViolations(parse(code, COMPACT_SURFACES[0])), code).not.toEqual([])
    expect(badgeViolations(parse("import * as UI from '@/components/ui'; const view = <UI.Card />"))).toEqual([])
    expect(badgeViolations(parse("import * as UI from '@/components/ui'; function example(UI: any) { return <UI.Badge /> }"))).toEqual([])
    expect(badgeViolations(parse("// import { Badge } from '@/components/ui'\nconst view = <span />"))).toEqual([])
  })

  it('reads literal and template class tokens, without matching comments or larger text', () => {
    const source = parse([
      'const a = <span className="whitespace-nowrap text-[10px]" />',
      'const b = `md:whitespace-nowrap ${tone} text-[10.5px] ${extra} dark:text-[9px]`',
      'const c = cx({ "hover:!whitespace-nowrap": active }, "text-[.5px]/4")',
      'const d = `lg:text-nowrap ${tone} md:!truncate ${extra} text-ellipsis line-clamp-2`',
    ].join('\n'))
    expect(classViolations(source, true)).toHaveLength(11)
    expect(classViolations(source, false)).toHaveLength(4)
    expect(classViolations(parse([
      '// whitespace-nowrap text-[8px]',
      '/* text-[10px] */ const a = <span className="text-[11px] md:text-[12px] whitespace-normal" />',
      'const b = `text-data-xs ${tone} text-[11.5px]`',
    ].join('\n')), true)).toEqual([])
  })

  it('enforces badge ownership for relative imports, re-exports and lazy imports', () => {
    for (const code of [
      "import Status from './ReconciliationBadge'",
      "export { default as Status } from '@/features/analysis/components/ReconciliationBadge.tsx'",
      "const Status = import('@/features/fundamentals/components/SourceCheckBadge')",
      "export * from '../../fundamentals/components/SourceCheckBadge'",
    ]) expect(badgeBoundaryViolations(parse(code, COMPACT_SURFACES[0])), code).toHaveLength(1)
    const allowed = [...SOURCE_BADGE_CONSUMERS][0]
    expect(badgeBoundaryViolations(parse("import Status from './SourceCheckBadge'", allowed))).toEqual([])
    expect(badgeBoundaryViolations(parse("// import Status from './ReconciliationBadge'", COMPACT_SURFACES[0]))).toEqual([])
  })
})
