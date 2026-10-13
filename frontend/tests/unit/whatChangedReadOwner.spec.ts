import { readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * Structural gate: the change report has ONE client reader, `useWhatChanged` (CLAUDE.md rule 12).
 *
 * The report differs by viewer (a Pro reader gets every Item 1A wording change, everyone else the
 * teaser) and its endpoint reads the user optionally, so a Pro reader whose access token has expired
 * is served the teaser with a 200 and nothing in that response triggers the client's token refresh.
 * `features/summaries/hooks/useWhatChanged.ts` is where that is handled: the read waits for /me (cold
 * or being re-read), carries the signed-in reader's id in its key, re-reads once when a Pro reader is
 * served the teaser, and keeps the anonymous seed in place while the reader's own read runs or fails.
 * A second `useQuery` on the endpoint, or a second writer of the viewer-keyed entry, would carry none
 * of that (lessons/frontend-auth-optional-reads-wait-for-the-session-read.md). PR B moved the three
 * readers that existed (the summary section, the standalone card, the company page's Compare periods
 * card) onto the hook; this spec keeps the next one there.
 *
 * Every production module under app/, features/, components/, lib/ and hooks/ is parsed and five forms
 * are collected: the HTTP call `getWhatChanged` and the server seed `fetchWhatChangedServer` (as
 * identifiers, so an import, a call or a re-export all count), the endpoint path `/what-changed` in a
 * string or template literal (a second `api.get` of it), the viewer-keyed entry
 * `queryKeys.whatChanged.byViewer` (by property or element access, or destructured), and any other use
 * of the `queryKeys.whatChanged` family that is not `.all()` handed to invalidateQueries, removeQueries,
 * cancelQueries, refetchQueries or resetQueries (a reader or writer of the whole family, such as
 * setQueriesData, would overwrite every viewer's entry). A (file, form) outside the allow-list fails
 * with file:line; an allow-listed (file, form) that disappears fails too, so the list cannot go stale.
 */
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SOURCE_DIRS = ['app', 'features', 'components', 'lib', 'hooks'] as const

type Form = 'getWhatChanged' | 'fetchWhatChangedServer' | 'path' | 'byViewer' | 'family'
const INVALIDATION = new Set(['invalidateQueries', 'removeQueries', 'cancelQueries', 'refetchQueries', 'resetQueries'])

/** File (relative to frontend/) -> the forms it may name, and why. */
const ALLOWED: Record<string, { forms: Form[]; why: string }> = {
  'features/summaries/api/summaries-api.ts': { forms: ['getWhatChanged', 'path'], why: 'defines getWhatChanged (the HTTP call)' },
  'features/summaries/hooks/useWhatChanged.ts': {
    forms: ['getWhatChanged', 'byViewer'],
    why: 'the one reader: waits for /me, keys by viewer, reconciles a Pro teaser',
  },
  'lib/serverApi.ts': { forms: ['fetchWhatChangedServer', 'path'], why: 'the server seed: the anonymous report, fetched on the server for the filing page' },
  'app/filing/[id]/page.tsx': { forms: ['fetchWhatChangedServer'], why: 'fetches the seed and hands it to useWhatChanged through SummaryDisplay' },
}

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry)
    if (entry === 'node_modules' || entry.startsWith('.')) continue
    if (statSync(full).isDirectory()) walk(full, out)
    else if (/\.(ts|tsx)$/.test(entry) && !/\.d\.ts$/.test(entry)) out.push(full)
  }
  return out
}

/** Every reference to the read, the seed, the endpoint path or the query-key family, with its form. */
export function readReferences(source: string, fileName = 'x.tsx'): Array<{ line: number; form: Form }> {
  // A .ts file parsed as TSX reads `f<T>(x)` as a JSX tag and loses what follows: pick the kind by extension.
  const kind = fileName.endsWith('.ts') ? ts.ScriptKind.TS : ts.ScriptKind.TSX
  const sf = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, kind)
  const out: Array<{ line: number; form: Form }> = []
  const line = (node: ts.Node) => sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
  const add = (node: ts.Node, form: Form) => out.push({ line: line(node), form })
  const isQueryKeys = (node: ts.Node) => ts.isIdentifier(node) && node.text === 'queryKeys'
  /** The member a property or element access names (`x.name` or `x['name']`). */
  const memberName = (node: ts.Node | undefined): string | undefined => {
    if (!node) return undefined
    if (ts.isPropertyAccessExpression(node)) return node.name.text
    if (ts.isElementAccessExpression(node) && ts.isStringLiteralLike(node.argumentExpression)) return node.argumentExpression.text
    return undefined
  }
  /** `queryKeys.whatChanged`, by property or element access. */
  const isFamily = (node: ts.Node): node is ts.PropertyAccessExpression | ts.ElementAccessExpression =>
    (ts.isPropertyAccessExpression(node) || ts.isElementAccessExpression(node)) && isQueryKeys(node.expression) && memberName(node) === 'whatChanged'
  /** Is this family reference `.all()` handed to an invalidate / remove / cancel / refetch / reset call? */
  const isInvalidation = (family: ts.Node): boolean => {
    const member = family.parent
    if (memberName(member) !== 'all') return false
    const call = member.parent
    if (!call || !ts.isCallExpression(call) || call.expression !== member) return false
    for (let up: ts.Node | undefined = call.parent; up; up = up.parent) {
      if (ts.isCallExpression(up)) {
        const callee = memberName(up.expression)
        return callee !== undefined && INVALIDATION.has(callee)
      }
    }
    return false
  }
  const visit = (node: ts.Node) => {
    if (ts.isIdentifier(node) && node.text === 'getWhatChanged') add(node, 'getWhatChanged')
    if (ts.isIdentifier(node) && node.text === 'fetchWhatChangedServer') add(node, 'fetchWhatChangedServer')
    if ((ts.isStringLiteralLike(node) || ts.isTemplateLiteralToken(node)) && node.text.includes('/what-changed')) add(node, 'path')
    if (isFamily(node)) {
      if (memberName(node.parent) === 'byViewer') add(node, 'byViewer')
      else if (!isInvalidation(node)) add(node, 'family')
    }
    // `const { whatChanged } = queryKeys`
    if (ts.isVariableDeclaration(node) && ts.isObjectBindingPattern(node.name) && node.initializer && isQueryKeys(node.initializer)) {
      if (node.name.elements.some((element) => (element.propertyName ?? element.name).getText(sf) === 'whatChanged')) add(node, 'family')
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out.sort((a, b) => a.line - b.line || a.form.localeCompare(b.form))
}

describe('the change report has one client reader (useWhatChanged)', () => {
  const files = SOURCE_DIRS.flatMap((dir) => walk(path.join(frontendRoot, dir)))
  const found: Array<{ rel: string; line: number; form: Form }> = []
  for (const file of files) {
    const rel = path.relative(frontendRoot, file).split(path.sep).join('/')
    for (const ref of readReferences(readFileSync(file, 'utf8'), file)) found.push({ rel, ...ref })
  }
  const allowed = (rel: string, form: Form) => ALLOWED[rel]?.forms.includes(form) ?? false

  it('scans the source tree', () => {
    expect(files.length).toBeGreaterThan(200)
  })

  it('names the read, the seed, the endpoint or its key family only where the allow-list says', () => {
    const unexpected = found.filter(({ rel, form }) => !allowed(rel, form)).map(({ rel, line, form }) => `${rel}:${line} (${form})`)
    expect(
      unexpected,
      `the change report is read or keyed outside useWhatChanged: ${unexpected.join(', ')}. ` +
        'Read the change report through useWhatChanged(filingId, seed): it waits for /me, keys the entry by the ' +
        'signed-in reader and re-reads once when a Pro reader is served the teaser; the family key may only be ' +
        'invalidated, removed, cancelled, refetched or reset. A new reader that must not use the hook is a design ' +
        'change: say so in the PR and list it here with its forms and reason.',
    ).toEqual([])
  })

  it('still finds every allow-listed (file, form) pair (the list cannot go stale)', () => {
    const stale = Object.entries(ALLOWED).flatMap(([rel, { forms }]) =>
      forms.filter((form) => !found.some((ref) => ref.rel === rel && ref.form === form)).map((form) => `${rel} (${form})`),
    )
    expect(stale, `allow-listed pairs no longer found: ${stale.join(', ')}; prune them`).toEqual([])
  })

  it('finder sees every form, and not strings, invalidation or a plain whatChanged variable', () => {
    const refs = readReferences(
      [
        "import { getWhatChanged } from '@/features/summaries/api/summaries-api'",
        'const q = useQuery({ queryKey: queryKeys.whatChanged.byViewer(id, viewer), queryFn: () => getWhatChanged(id) })',
        'void client.invalidateQueries({ queryKey: queryKeys.whatChanged.all() })',
        'client.setQueriesData({ queryKey: queryKeys.whatChanged.all() }, patch)',
        "const k = queryKeys.whatChanged['byViewer'](id, viewer)",
        'const { byViewer } = queryKeys.whatChanged',
        'const { whatChanged } = queryKeys',
        'const raw = api.get(`/api/summaries/filing/${id}/what-changed`)',
        'const seed = await fetchWhatChangedServer(id)',
        "const note = 'getWhatChanged byViewer'",
        'const other = keys.byViewer(1)',
        'const whatChanged = report',
        "export const WHAT_CHANGED_ID = 'what-changed'",
        'await client.refetchQueries({ queryKey: queryKeys.whatChanged.all() })',
      ].join('\n'),
    )
    expect(refs).toEqual([
      { line: 1, form: 'getWhatChanged' },
      { line: 2, form: 'byViewer' },
      { line: 2, form: 'getWhatChanged' },
      { line: 4, form: 'family' },
      { line: 5, form: 'byViewer' },
      { line: 6, form: 'family' },
      { line: 7, form: 'family' },
      { line: 8, form: 'path' },
      { line: 9, form: 'fetchWhatChangedServer' },
    ])
  })
})
