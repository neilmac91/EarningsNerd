import { beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * The insider page's route (app/company/[ticker]/insiders/page.tsx): it exists only on a build that shows insider
 * activity, has one address per company, and is a reader's page that names no company to a crawler.
 */

const flags = vi.hoisted(() => ({ ENABLE_INSIDER_ACTIVITY: true }))
vi.mock('@/lib/featureFlags', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/featureFlags')>()),
  get ENABLE_INSIDER_ACTIVITY() {
    return flags.ENABLE_INSIDER_ACTIVITY
  },
}))
const nav = vi.hoisted(() => ({
  notFound: vi.fn(() => {
    throw new Error('NEXT_NOT_FOUND')
  }),
  permanentRedirect: vi.fn((to: string) => {
    throw new Error(`NEXT_REDIRECT ${to}`)
  }),
}))
vi.mock('next/navigation', () => nav)
vi.mock('@/app/company/[ticker]/insiders/page-client', () => ({ default: () => null }))

import InsidersPage, { metadata } from '@/app/company/[ticker]/insiders/page'

const open = (ticker: string) => InsidersPage({ params: Promise.resolve({ ticker }) })

beforeEach(() => {
  flags.ENABLE_INSIDER_ACTIVITY = true
  nav.notFound.mockClear()
  nav.permanentRedirect.mockClear()
})

describe('the insider page’s route', () => {
  it('answers 404 on a build without the insider flag, before anything else', async () => {
    flags.ENABLE_INSIDER_ACTIVITY = false
    await expect(open('aapl')).rejects.toThrow('NEXT_NOT_FOUND')
    expect(nav.permanentRedirect).not.toHaveBeenCalled()
  })

  it('renders for the upper-case ticker, with no redirect', async () => {
    await expect(open('BRK-B')).resolves.toBeTruthy()
    expect(nav.notFound).not.toHaveBeenCalled()
    expect(nav.permanentRedirect).not.toHaveBeenCalled()
  })

  it('redirects any other casing to the one address the company has', async () => {
    await expect(open('brk-b')).rejects.toThrow('NEXT_REDIRECT /company/BRK-B/insiders')
  })

  it('is kept out of the index, under a title that ends with the brand', () => {
    expect(metadata.robots).toEqual({ index: false, follow: true })
    expect(metadata.title).toBe('Insider activity | EarningsNerd')
  })
})
