import { describe, expect, it } from 'vitest'
import { render, renderHook } from '@testing-library/react'
import { CONTENT_IN, useContentIn } from '@/hooks/useContentIn'

/**
 * The skeleton→content handoff (DESIGN_SYSTEM.md §11): the class arrives on the render where loading turns
 * false and leaves when it turns true again; a view that never loaded never gets it.
 */
describe('useContentIn', () => {
  it('is reduced-motion safe', () => {
    expect(CONTENT_IN.split(' ')).toEqual(['animate-content-in', 'motion-reduce:animate-none'])
  })

  it('never animates a view that paints without loading', () => {
    const { result, rerender } = renderHook(({ loading }) => useContentIn(loading), { initialProps: { loading: false } })
    expect(result.current).toBeUndefined()
    rerender({ loading: false })
    expect(result.current).toBeUndefined()
  })

  it('fades in on each loading → loaded flip, and drops the class while loading', () => {
    const { result, rerender } = renderHook(({ loading }) => useContentIn(loading), { initialProps: { loading: true } })
    expect(result.current).toBeUndefined()
    rerender({ loading: false })
    expect(result.current).toBe(CONTENT_IN)
    rerender({ loading: false })
    expect(result.current).toBe(CONTENT_IN)
    rerender({ loading: true })
    expect(result.current).toBeUndefined()
    rerender({ loading: false })
    expect(result.current).toBe(CONTENT_IN)
  })

  it('puts the class on the same commit as the content it reveals', () => {
    // An effect would commit the content at full opacity first and add the class a render later.
    const commits: Array<string | null> = []
    function View({ loading }: { loading: boolean }) {
      const enter = useContentIn(loading)
      return loading ? <p>bones</p> : <p ref={(node) => { if (node) commits.push(node.className || null) }} className={enter}>content</p>
    }
    const { rerender } = render(<View loading />)
    rerender(<View loading={false} />)
    expect(commits[0]).toBe(CONTENT_IN)
  })
})
