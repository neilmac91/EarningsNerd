import { readFileSync } from 'node:fs'
import path from 'node:path'
import * as ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * Rule-12 gate for the EN-01 acceptance clause "source access is plan-independent": the chip →
 * pane → document route behaves identically for anonymous, free and Pro visitors and introduces no
 * plan gate, while Ask entitlements stay where they are (the rail, the page, and
 * app/services/entitlements.py as the only truth).
 *
 * The scan reads each route module's TypeScript AST (comments never count) and fails when one
 * imports a plan or identity module (features/subscriptions, features/auth, anything named
 * entitlement) or names a plan or identity binding (isPro, is_pro, isAuthenticated, subscription,
 * currentUser, getCurrentUserSafe, getSubscriptionStatus). A route module that needs to know who
 * the visitor is must say so here, with its reason, which is the review the rule asks for.
 *
 * Mutation proof (committed state, lessons/ops-mutate-only-committed-state.md): add
 * `import { getSubscriptionStatus } from '@/features/subscriptions/api/subscriptions-api'` to
 * FilingViewerContext.tsx → this gate fails naming the file and the import; `git checkout --` the
 * file → it passes again. Recorded in the EN-01 PR body.
 */

const FRONTEND = path.resolve(__dirname, '../..')

/** The modules on the chip → pane → document route. Listed, not globbed: a new module joins by name. */
const ROUTE_MODULES = [
  'features/filings/components/SourceTrace.tsx',
  'features/filings/components/MetricSourceLink.tsx',
  'features/filings/components/copilot/FilingViewerContext.tsx',
  'features/filings/components/copilot/FilingViewer.tsx',
  'features/filings/components/copilot/FilingWorkspace.tsx',
  'features/filings/components/copilot/useEvidencePopoverKeys.ts',
  'features/filings/components/copilot/useSheetFocusTrap.ts',
  'features/filings/lib/originalDocumentUrl.ts',
] as const

const FORBIDDEN_IMPORT = /(^|\/)features\/(subscriptions|auth)(\/|$)|entitlement/i
const FORBIDDEN_IDENTIFIER = new Set([
  'isPro',
  'is_pro',
  'isAuthenticated',
  'subscription',
  'currentUser',
  'getCurrentUserSafe',
  'getSubscriptionStatus',
])

interface Offence {
  file: string
  kind: 'import' | 'identifier'
  text: string
  line: number
}

function scan(file: string): Offence[] {
  const source = readFileSync(path.join(FRONTEND, file), 'utf8')
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, file.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const offences: Offence[] = []
  const lineOf = (node: ts.Node) => sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
  const visit = (node: ts.Node): void => {
    if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) {
      const spec = node.moduleSpecifier.text
      if (FORBIDDEN_IMPORT.test(spec)) offences.push({ file, kind: 'import', text: spec, line: lineOf(node) })
    }
    if (ts.isIdentifier(node) && FORBIDDEN_IDENTIFIER.has(node.text)) {
      offences.push({ file, kind: 'identifier', text: node.text, line: lineOf(node) })
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return offences
}

describe('source access is plan-independent (EN-01 gate)', () => {
  it('every route module exists (the list is the scope, a rename must update it)', () => {
    for (const file of ROUTE_MODULES) {
      expect(() => readFileSync(path.join(FRONTEND, file), 'utf8'), file).not.toThrow()
    }
  })

  it('no route module imports a plan or identity module, or names a plan or identity binding', () => {
    const offences = ROUTE_MODULES.flatMap(scan)
    const report = offences.map((o) => `${o.file}:${o.line} ${o.kind} ${o.text}`).join('\n')
    expect(offences, `plan or identity state reached the source route:\n${report}`).toEqual([])
  })

  it('the scan sees what it guards (a probe with the forbidden shapes is caught)', () => {
    const probe = [
      "import { getSubscriptionStatus } from '@/features/subscriptions/api/subscriptions-api'",
      "import { getCurrentUserSafe } from '@/features/auth/api/auth-api'",
      "import { plan } from '@/lib/entitlements'",
      'export const gate = (user: { is_pro: boolean }) => user.is_pro && isPro',
    ].join('\n')
    const sf = ts.createSourceFile('probe.ts', probe, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
    const found: string[] = []
    const visit = (node: ts.Node): void => {
      if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier) && FORBIDDEN_IMPORT.test(node.moduleSpecifier.text)) found.push(`import ${node.moduleSpecifier.text}`)
      if (ts.isIdentifier(node) && FORBIDDEN_IDENTIFIER.has(node.text)) found.push(node.text)
      ts.forEachChild(node, visit)
    }
    visit(sf)
    expect(found).toEqual([
      'import @/features/subscriptions/api/subscriptions-api',
      'getSubscriptionStatus',
      'import @/features/auth/api/auth-api',
      'getCurrentUserSafe',
      'import @/lib/entitlements',
      'is_pro',
      'is_pro',
      'isPro',
    ])
  })
})
