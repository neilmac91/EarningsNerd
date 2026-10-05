import { readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import * as ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * Rule-12 gate for the EN-01 acceptance clause "source access is plan-independent": the chip →
 * pane → document route behaves identically for anonymous, free and Pro visitors and introduces no
 * plan gate, while Ask entitlements stay where they are (the rail, the page, and
 * app/services/entitlements.py as the only truth).
 *
 * What it checks (TypeScript AST; comments never count):
 *  - Every route module: no static import, re-export, dynamic `import()` or `require()` of a plan or
 *    identity module (features/subscriptions, features/auth, anything named entitle…, lib/planLimits);
 *    no plan or identity identifier (isPro, is_pro, isAuthenticated, subscription, currentUser,
 *    getCurrentUserSafe, getCurrentUser, getSubscriptionStatus, getUsage, useAuth, useCurrentUser,
 *    usePlan, useSubscription, useEntitlements, isPaid, the CurrentUser / SubscriptionStatus types,
 *    the copilot free-taste fields); no identity string (`/api/auth/…`, `/api/subscriptions/…`,
 *    `en_session`).
 *  - One hop: a module a route module imports from `@/hooks`, `@/lib`, `@/components` or
 *    `@/features/filings`, or by a relative path, must not itself import a plan or identity module
 *    (its identifiers and strings are its own business; a second hop is not followed).
 *  - The page: `openPaneForSource` is exactly `useCallback(() => setCopilotOpen(true), [])` and is
 *    what `<FilingViewerProvider onRequestOpen>` receives, so the open decision carries no condition.
 *  A route module that needs to know who the visitor is must say so here, with its reason, which is
 *  the review the rule asks for. Generic names (plan, tier, usage) are not in the list on purpose: a
 *  false positive on an unrelated binding would train people to edit the list, not the code.
 *
 * Mutation proofs (committed state, lessons/ops-mutate-only-committed-state.md), recorded in the
 * EN-01 PR body: (1) `import { getSubscriptionStatus } from
 * '@/features/subscriptions/api/subscriptions-api'` added to FilingViewerContext.tsx fails the module
 * case naming the file and the import; (2) `const openPaneForSource = useCallback(() => { if (isPro)
 * setCopilotOpen(true) }, [isPro])` in page-client.tsx fails the page case; `git checkout --` each
 * file passes again.
 */

const FRONTEND = path.resolve(__dirname, '../..')

/** The modules on the chip → pane → document route. Listed, not globbed: a new module joins by name. */
const ROUTE_MODULES = [
  'features/filings/components/SourceTrace.tsx',
  'features/filings/components/MetricSourceLink.tsx',
  'features/filings/components/copilot/CitationChip.tsx',
  'features/filings/components/copilot/FilingViewerContext.tsx',
  'features/filings/components/copilot/FilingViewer.tsx',
  'features/filings/components/copilot/FilingWorkspace.tsx',
  'features/filings/components/copilot/SecondaryPaneTabs.tsx',
  'features/filings/components/copilot/useEvidencePopoverKeys.ts',
  'features/filings/components/copilot/useSheetFocusTrap.ts',
  'features/filings/lib/originalDocumentUrl.ts',
] as const

const PAGE_MODULE = 'app/filing/[id]/page-client.tsx'

const FORBIDDEN_IMPORT = /(^|\/)features\/(subscriptions|auth)(\/|$)|entitle|(^|\/)lib\/planLimits/i
const FORBIDDEN_IDENTIFIER = new Set([
  'isPro',
  'is_pro',
  'isPaid',
  'isAuthenticated',
  'subscription',
  'currentUser',
  'getCurrentUser',
  'getCurrentUserSafe',
  'getSubscriptionStatus',
  'getUsage',
  'useAuth',
  'useCurrentUser',
  'usePlan',
  'useSubscription',
  'useEntitlements',
  'CurrentUser',
  'SubscriptionStatus',
  'copilot_free_taste_used',
  'copilot_free_taste_total',
  'freeTasteTotal',
  'freeTasteRemaining',
])
const FORBIDDEN_STRING = /^\/api\/(auth|subscriptions)(\/|$)|en_session/
const HOP_PREFIXES = ['@/hooks/', '@/lib/', '@/components/', '@/features/filings/']

interface Offence {
  file: string
  kind: 'import' | 'export-from' | 'dynamic-import' | 'require' | 'identifier' | 'string'
  text: string
  line: number
}

function parse(file: string, source: string): ts.SourceFile {
  return ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, file.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
}

/** The module specifiers a file reaches, each with how (static import, re-export, dynamic import, require). */
function specifiers(sf: ts.SourceFile): Array<{ kind: Offence['kind']; text: string; node: ts.Node }> {
  const out: Array<{ kind: Offence['kind']; text: string; node: ts.Node }> = []
  const visit = (node: ts.Node): void => {
    if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) out.push({ kind: 'import', text: node.moduleSpecifier.text, node })
    if (ts.isExportDeclaration(node) && node.moduleSpecifier && ts.isStringLiteral(node.moduleSpecifier)) out.push({ kind: 'export-from', text: node.moduleSpecifier.text, node })
    if (ts.isCallExpression(node) && node.arguments.length > 0 && ts.isStringLiteralLike(node.arguments[0])) {
      if (node.expression.kind === ts.SyntaxKind.ImportKeyword) out.push({ kind: 'dynamic-import', text: node.arguments[0].text, node })
      if (ts.isIdentifier(node.expression) && node.expression.text === 'require') out.push({ kind: 'require', text: node.arguments[0].text, node })
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out
}

/**
 * Scans one module's source. `full` checks modules, identifiers and strings (a route module);
 * `false` checks only the modules it reaches (a one-hop neighbour).
 */
export function scanSource(file: string, source: string, full = true): Offence[] {
  const sf = parse(file, source)
  const lineOf = (node: ts.Node) => sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
  const offences: Offence[] = []
  for (const s of specifiers(sf)) {
    if (FORBIDDEN_IMPORT.test(s.text)) offences.push({ file, kind: s.kind, text: s.text, line: lineOf(s.node) })
  }
  if (!full) return offences
  const visit = (node: ts.Node): void => {
    if (ts.isIdentifier(node) && FORBIDDEN_IDENTIFIER.has(node.text)) offences.push({ file, kind: 'identifier', text: node.text, line: lineOf(node) })
    if ((ts.isStringLiteralLike(node) || ts.isTemplateLiteralToken(node)) && FORBIDDEN_STRING.test(node.text)) {
      offences.push({ file, kind: 'string', text: node.text, line: lineOf(node) })
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return offences.sort((a, b) => a.line - b.line || a.kind.localeCompare(b.kind))
}

function resolveModule(fromFile: string, spec: string): string | null {
  let base: string
  if (spec.startsWith('@/')) base = path.join(FRONTEND, spec.slice(2))
  else if (spec.startsWith('.')) base = path.resolve(path.dirname(path.join(FRONTEND, fromFile)), spec)
  else return null
  for (const candidate of [base, `${base}.ts`, `${base}.tsx`, path.join(base, 'index.ts'), path.join(base, 'index.tsx')]) {
    try {
      if (statSync(candidate).isFile()) return path.relative(FRONTEND, candidate)
    } catch {
      /* next candidate */
    }
  }
  return null
}

function scan(file: string): Offence[] {
  const source = readFileSync(path.join(FRONTEND, file), 'utf8')
  const own = scanSource(file, source)
  const hops: Offence[] = []
  for (const s of specifiers(parse(file, source))) {
    if (!(s.text.startsWith('.') || HOP_PREFIXES.some((p) => s.text.startsWith(p)))) continue
    const hop = resolveModule(file, s.text)
    if (!hop) continue
    for (const o of scanSource(hop, readFileSync(path.join(FRONTEND, hop), 'utf8'), false)) {
      hops.push({ ...o, file: `${hop} (via ${file})` })
    }
  }
  return [...own, ...hops]
}

const report = (offences: Offence[]) => offences.map((o) => `${o.file}:${o.line} ${o.kind} ${o.text}`).join('\n')

describe('source access is plan-independent (EN-01 gate)', () => {
  it('every route module exists (the list is the scope, a rename must update it)', () => {
    for (const file of [...ROUTE_MODULES, PAGE_MODULE]) {
      expect(() => readFileSync(path.join(FRONTEND, file), 'utf8'), file).not.toThrow()
    }
  })

  it('no route module reaches a plan or identity module, names a plan or identity binding, or carries an identity string', () => {
    const offences = ROUTE_MODULES.flatMap(scan)
    expect(offences, `plan or identity state reached the source route:\n${report(offences)}`).toEqual([])
  })

  it('the page opens the pane for a source with no condition and hands that to the provider', () => {
    const sf = parse(PAGE_MODULE, readFileSync(path.join(FRONTEND, PAGE_MODULE), 'utf8'))
    let initializer: string | null = null
    let unconditional = false
    let wired = false
    const visit = (node: ts.Node): void => {
      if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.name.text === 'openPaneForSource' && node.initializer) {
        initializer = node.initializer.getText(sf)
        const call = node.initializer
        if (ts.isCallExpression(call) && ts.isIdentifier(call.expression) && call.expression.text === 'useCallback') {
          const [fn, deps] = call.arguments
          const body = fn && ts.isArrowFunction(fn) && fn.parameters.length === 0 ? fn.body : null
          unconditional =
            !!body &&
            ts.isCallExpression(body) &&
            ts.isIdentifier(body.expression) &&
            body.expression.text === 'setCopilotOpen' &&
            body.arguments.length === 1 &&
            body.arguments[0].kind === ts.SyntaxKind.TrueKeyword &&
            !!deps &&
            ts.isArrayLiteralExpression(deps) &&
            deps.elements.length === 0
        }
      }
      if (ts.isJsxOpeningElement(node) && ts.isIdentifier(node.tagName) && node.tagName.text === 'FilingViewerProvider') {
        for (const attr of node.attributes.properties) {
          if (!ts.isJsxAttribute(attr) || !ts.isIdentifier(attr.name) || attr.name.text !== 'onRequestOpen') continue
          const init = attr.initializer
          wired = !!init && ts.isJsxExpression(init) && !!init.expression && ts.isIdentifier(init.expression) && init.expression.text === 'openPaneForSource'
        }
      }
      ts.forEachChild(node, visit)
    }
    visit(sf)
    expect(initializer, 'openPaneForSource is declared in page-client').not.toBeNull()
    expect(unconditional, `openPaneForSource must be useCallback(() => setCopilotOpen(true), []), found: ${initializer}`).toBe(true)
    expect(wired, '<FilingViewerProvider onRequestOpen={openPaneForSource}> is how a chip opens the pane').toBe(true)
  })

  it('the scanner sees what it guards (a probe with every forbidden shape is caught by scanSource itself)', () => {
    const probe = [
      "import { getSubscriptionStatus } from '@/features/subscriptions/api/subscriptions-api'",
      "import type { CurrentUser } from '@/features/auth/api/auth-api'",
      "import { plan } from '@/lib/entitlements'",
      "import { FREE_COPILOT_QUESTIONS } from '@/lib/planLimits'",
      "export { useAuth } from '@/features/auth/hooks/useAuth'",
      "const lazy = () => import('@/features/subscriptions/components/UpgradeModal')",
      "const legacy = require('@/features/auth/api/auth-api')",
      "const me = apiClient.get('/api/auth/me')",
      'const cookie = `en_session=${token}`',
      'export const gate = (user: { is_pro: boolean }) => user.is_pro && isPro',
    ].join('\n')
    const found = scanSource('probe.ts', probe).map((o) => `${o.line} ${o.kind} ${o.text}`)
    expect(found).toEqual([
      '1 identifier getSubscriptionStatus',
      '1 import @/features/subscriptions/api/subscriptions-api',
      '2 identifier CurrentUser',
      '2 import @/features/auth/api/auth-api',
      '3 import @/lib/entitlements',
      '4 import @/lib/planLimits',
      '5 export-from @/features/auth/hooks/useAuth',
      '5 identifier useAuth',
      '6 dynamic-import @/features/subscriptions/components/UpgradeModal',
      '7 require @/features/auth/api/auth-api',
      '8 string /api/auth/me',
      '9 string en_session=',
      '10 identifier is_pro',
      '10 identifier is_pro',
      '10 identifier isPro',
    ])
    // A neighbour is judged by the modules it reaches only.
    expect(scanSource('hop.ts', probe, false).map((o) => o.kind)).toEqual(['import', 'import', 'import', 'import', 'export-from', 'dynamic-import', 'require'])
  })
})
