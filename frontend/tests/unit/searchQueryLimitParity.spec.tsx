import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createElement } from 'react'
import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import FullTextSearch from '@/features/search/components/FullTextSearch'
import { SEARCH_QUERY_MAX } from '@/features/search/lib/queryLimit'

/**
 * The full-text search field stops where the server stops (CLAUDE.md rule 12; audit SRCH-03). The
 * backend's `full_text_search` (backend/app/routers/search.py) bounds the query with
 * `q: str = Query(..., max_length=N)`; a longer query came back as a 422 the reader could not act
 * on. This spec reads N from the Python, never a retyped literal, and holds `SEARCH_QUERY_MAX` and the
 * rendered field's clamp to it, in code points as Python's `len` counts: a native `maxLength` counts
 * UTF-16 units and would cut an emoji-heavy query at half the bound the server accepts.
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

  it('the field holds the query to the backend bound in code points, where a native maxLength would count UTF-16 units', () => {
    const bound = queryMaxLength(router)
    expect(bound).toBeGreaterThan(0)
    expect(SEARCH_QUERY_MAX).toBe(bound)
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(createElement(QueryClientProvider, { client: qc }, createElement(FullTextSearch)))
    const field = screen.getByLabelText<HTMLInputElement>(/Search the full text/i)
    expect(field).not.toHaveAttribute('maxLength')
    // An emoji is one code point and two UTF-16 units: the server accepts `bound` of them, and so must the field.
    const emoji = String.fromCodePoint(0x1f600)
    fireEvent.change(field, { target: { value: emoji.repeat(bound) } })
    expect(Array.from(field.value)).toHaveLength(bound)
    expect(field.value.length).toBe(bound * 2)
    fireEvent.change(field, { target: { value: emoji.repeat(bound + 1) } })
    expect(Array.from(field.value)).toHaveLength(bound)
  })
})
