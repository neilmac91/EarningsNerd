import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createElement } from 'react'
import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import FullTextSearch from '@/features/search/components/FullTextSearch'

/**
 * The full-text search field stops where the server stops (CLAUDE.md rule 12; audit SRCH-03). The
 * backend's `full_text_search` (backend/app/routers/search.py) bounds the query with
 * `q: str = Query(..., max_length=N)`; a longer query came back as a 422 the reader could not act
 * on. This spec reads N from the Python, never a retyped literal, and holds the rendered field's
 * maxLength to it.
 */

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const router = readFileSync(path.resolve(frontendDir, '../backend/app/routers/search.py'), 'utf8')

/** `max_length` of the `q` parameter's `Query(...)` declaration in a router's source. */
function queryMaxLength(source: string): number {
  const decl = source.match(/^\s+q: str = Query\(([\s\S]*?)\n\s{4}\),?\s*$/m)?.[1]
  if (!decl) throw new Error('full_text_search has no `q: str = Query(...)` parameter')
  const value = decl.match(/\bmax_length=(\d+)/)?.[1]
  if (!value) throw new Error("the q parameter's Query(...) has no max_length")
  return Number(value)
}

afterEach(cleanup)

describe('the search field limit equals the backend Query bound', () => {
  it('reads the bound from a declaration, and refuses one without it (self-check)', () => {
    const declared = 'async def f(\n    q: str = Query(\n        ...,\n        min_length=1,\n        max_length=123,\n    ),\n):\n'
    expect(queryMaxLength(declared)).toBe(123)
    expect(() => queryMaxLength(declared.replace('        max_length=123,\n', ''))).toThrow(/no max_length/)
    expect(() => queryMaxLength('async def f(\n    term: str = Query(...),\n):\n')).toThrow(/no `q: str = Query/)
  })

  it('the field applies the backend bound as its maxLength', () => {
    const bound = queryMaxLength(router)
    expect(bound).toBeGreaterThan(0)
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(createElement(QueryClientProvider, { client: qc }, createElement(FullTextSearch)))
    expect(screen.getByLabelText(/Search the full text/i)).toHaveAttribute('maxLength', String(bound))
  })
})
