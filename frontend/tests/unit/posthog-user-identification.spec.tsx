import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const getCurrentUserSafe = vi.fn()
const getSubscriptionStatus = vi.fn()
const getCookiePreferences = vi.fn()
const identify = vi.fn()

vi.mock('@/features/auth/api/auth-api', () => ({
  getCurrentUserSafe: () => getCurrentUserSafe(),
}))
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({
  getSubscriptionStatus: () => getSubscriptionStatus(),
}))
vi.mock('@/components/CookieConsent', () => ({
  getCookiePreferences: () => getCookiePreferences(),
}))
vi.mock('@/lib/analytics', () => ({
  analytics: { identify: (...args: unknown[]) => identify(...args) },
}))

import { usePostHogUserIdentification } from '@/hooks/usePostHogUserIdentification'

function Probe() {
  usePostHogUserIdentification()
  return null
}

function renderProbe() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <Probe />
    </QueryClientProvider>,
  )
}

describe('usePostHogUserIdentification (roadmap 2.4)', () => {
  beforeEach(() => {
    getCurrentUserSafe.mockReset()
    getSubscriptionStatus.mockReset()
    getCookiePreferences.mockReset()
    identify.mockReset()
    getCookiePreferences.mockReturnValue({ analytics: true })
  })

  it('identifies a free user with is_pro/plan once user + subscription resolve', async () => {
    getCurrentUserSafe.mockResolvedValue({ id: 7, email: 'u@x.com', is_pro: false })
    getSubscriptionStatus.mockResolvedValue({ is_pro: false })
    renderProbe()
    await waitFor(() =>
      expect(identify).toHaveBeenCalledWith('7', { is_pro: false, plan: 'free' }),
    )
  })

  it('identifies a pro subscriber as pro (subscription is authoritative over the mirror)', async () => {
    getCurrentUserSafe.mockResolvedValue({ id: 9, email: 'p@x.com', is_pro: false })
    getSubscriptionStatus.mockResolvedValue({ is_pro: true })
    renderProbe()
    await waitFor(() =>
      expect(identify).toHaveBeenCalledWith('9', { is_pro: true, plan: 'pro' }),
    )
  })

  it('does not identify without analytics consent', async () => {
    getCookiePreferences.mockReturnValue({ analytics: false })
    getCurrentUserSafe.mockResolvedValue({ id: 7, email: 'u@x.com', is_pro: false })
    getSubscriptionStatus.mockResolvedValue({ is_pro: false })
    renderProbe()
    await new Promise((r) => setTimeout(r, 50))
    expect(identify).not.toHaveBeenCalled()
  })

  it('does not identify a logged-out visitor', async () => {
    getCurrentUserSafe.mockResolvedValue(null)
    renderProbe()
    await new Promise((r) => setTimeout(r, 50))
    expect(identify).not.toHaveBeenCalled()
  })
})
