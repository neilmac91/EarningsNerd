import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { RAW_FETCH_ALLOWLIST } from '../../eslint.rawFetchAllowlist.mjs'

/**
 * Two-directional guard for the raw-`fetch(` ESLint gate (eslint.config.mjs, RAW_FETCH_RULES).
 *
 * The lint rule alone is one-directional: it stops NEW files from calling fetch, but a sanctioned
 * file could grow extra raw calls unnoticed, and a file that stopped using fetch would stay
 * allow-listed forever. This spec closes both gaps against the SAME list the lint rule reads
 * (eslint.rawFetchAllowlist.mjs — one source of truth):
 *   (a) every allow-listed file still exists and still contains at least one raw fetch call;
 *   (b) each file's raw fetch call count equals its pinned `fetchCalls` — adding a call fails until
 *       the pin is bumped AND the PR justifies it (SSE reader or Next server/ISR fetch only);
 *   (c) the list is shrink-only (MAX_ALLOWLIST_SIZE is a frozen ceiling — lower it when a file is
 *       removed, never raise it).
 * Call sites are counted with the TypeScript AST using exactly the shapes the ESLint selectors
 * forbid — `fetch(...)` and `<expr>.fetch(...)` — so comments and `refetch()` never count.
 */
const MAX_ALLOWLIST_SIZE = 5

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')

function countRawFetchCalls(source: string, fileName: string): number {
  const sourceFile = ts.createSourceFile(
    fileName,
    source,
    ts.ScriptTarget.Latest,
    true,
    fileName.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  )
  let count = 0
  const visit = (node: ts.Node): void => {
    if (ts.isCallExpression(node)) {
      const callee = node.expression
      const bare = ts.isIdentifier(callee) && callee.text === 'fetch'
      const member = ts.isPropertyAccessExpression(callee) && callee.name.text === 'fetch'
      if (bare || member) count += 1
    }
    ts.forEachChild(node, visit)
  }
  visit(sourceFile)
  return count
}

describe('raw fetch allow-list (two-directional rule-12 gate)', () => {
  it('counter mirrors the ESLint selectors: bare + member calls only, not comments or refetch()', () => {
    const fixture = [
      '// a comment mentioning fetch( must not count',
      "const a = fetch('/x')",
      "const b = window.fetch('/y')",
      "const c = globalThis.fetch('/z')",
      'const d = refetch()',
      'const e = queryClient.fetchQuery({})',
      "const f = 'fetch(' + 'in a string'",
    ].join('\n')
    expect(countRawFetchCalls(fixture, 'fixture.ts')).toBe(3)
  })

  it('is shrink-only: the entry count never exceeds the frozen ceiling', () => {
    expect(
      RAW_FETCH_ALLOWLIST.length,
      `RAW_FETCH_ALLOWLIST has ${RAW_FETCH_ALLOWLIST.length} entries but the ceiling is ${MAX_ALLOWLIST_SIZE}. ` +
        'Raw fetch is sanctioned only for SSE readers and Next server/ISR fetches — route new HTTP through ' +
        'lib/api/client.ts instead of adding an entry.',
    ).toBeLessThanOrEqual(MAX_ALLOWLIST_SIZE)
  })

  it('every entry names an existing file with a stated reason', () => {
    for (const entry of RAW_FETCH_ALLOWLIST) {
      expect(existsSync(path.join(frontendRoot, entry.file)), `${entry.file} is allow-listed but does not exist`).toBe(true)
      expect(entry.reason.trim().length, `${entry.file} needs a reason (SSE reader or Next server/ISR fetch)`).toBeGreaterThan(0)
      expect(entry.fetchCalls, `${entry.file} pins fewer than 1 fetch call — remove it from the allow-list instead`).toBeGreaterThanOrEqual(1)
    }
  })

  it.each(RAW_FETCH_ALLOWLIST.map((entry) => [entry.file, entry.fetchCalls] as const))(
    '%s still has exactly %i raw fetch call site(s)',
    (file, pinned) => {
      const actual = countRawFetchCalls(readFileSync(path.join(frontendRoot, file), 'utf8'), file)
      expect(
        actual,
        actual === 0
          ? `${file} no longer calls fetch — remove it from eslint.rawFetchAllowlist.mjs (the list is shrink-only).`
          : `${file} has ${actual} raw fetch call(s) but eslint.rawFetchAllowlist.mjs pins ${pinned}. ` +
              'If the new call is a genuine SSE reader / Next server fetch, update the pin AND justify it in the PR; ' +
              'otherwise route it through lib/api/client.ts.',
      ).toBe(pinned)
    },
  )
})
