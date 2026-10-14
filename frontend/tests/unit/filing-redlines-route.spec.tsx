import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('next/navigation', () => ({ notFound: () => { throw new Error('NEXT_NOT_FOUND') } }))

afterEach(() => { vi.unstubAllEnvs(); vi.resetModules() })

describe('filing redlines route gate', () => {
  it.each([undefined, 'false', 'TRUE', '1'])('returns not found unless explicitly enabled (%s)', async (flag) => {
    vi.stubEnv('NEXT_PUBLIC_ENABLE_FILING_REDLINES', flag)
    vi.resetModules()
    const { default: Layout } = await import('@/app/labs/filing-redlines/layout')
    expect(() => Layout({ children: 'private prototype' })).toThrow('NEXT_NOT_FOUND')
  })

  it('renders the route when explicitly enabled', async () => {
    vi.stubEnv('NEXT_PUBLIC_ENABLE_FILING_REDLINES', 'true')
    vi.resetModules()
    const { default: Layout } = await import('@/app/labs/filing-redlines/layout')
    expect(Layout({ children: 'enabled prototype' }).props.children).toBe('enabled prototype')
  })
})
