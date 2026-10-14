import { afterEach, describe, expect, it, vi } from 'vitest'
vi.mock('next/navigation', () => ({ notFound: () => { throw new Error('NEXT_NOT_FOUND') } }))
afterEach(() => { vi.unstubAllEnvs(); vi.resetModules() })

describe('Financial refresh review default-off route', () => {
  it.each([undefined, 'false', 'TRUE', '1'])('returns 404 with flag %s', async (flag) => {
    vi.stubEnv('NEXT_PUBLIC_ENABLE_FINANCIAL_REFRESH_REVIEW', flag)
    vi.resetModules()
    const { default: Layout } = await import('@/app/labs/financial-refresh-review/layout')
    expect(() => Layout({ children: 'private prototype' })).toThrow('NEXT_NOT_FOUND')
  })
  it('renders only for literal true and excludes the page from indexing', async () => {
    vi.stubEnv('NEXT_PUBLIC_ENABLE_FINANCIAL_REFRESH_REVIEW', 'true')
    vi.resetModules()
    const { default: Layout } = await import('@/app/labs/financial-refresh-review/layout')
    expect(Layout({ children: 'prototype' }).props.children).toBe('prototype')
    const { metadata } = await import('@/app/labs/financial-refresh-review/page')
    expect(metadata.robots).toEqual({ index: false, follow: false })
  })
})
