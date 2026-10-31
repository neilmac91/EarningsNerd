import React from 'react'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi } from 'vitest'

vi.mock('next/navigation', () => ({ usePathname: () => '/admin/invites', useRouter: () => ({ replace: vi.fn() }) }))
vi.mock('@/features/auth/api/auth-api', () => ({
  getCurrentUserSafe: vi.fn().mockResolvedValue({ id: 1, email: 'admin@example.com', full_name: 'Admin', is_admin: true }),
}))

import AdminLayout from '@/app/admin/layout'

/**
 * The admin section nav wraps its tabs inside its own width (DESIGN_SYSTEM.md §4 "Admin pages"; the #1309 capture
 * review: at 390 under a 32px root font the Feedback tab ran past the nav's fill to x 443, so the page scrolled
 * sideways). The class is what a unit test can pin; the capture harness measures the layout in a real browser.
 */
describe('AdminLayout section nav', () => {
  it('wraps its tabs, so enlarged text never widens the page', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <AdminLayout>
          <p>Admin page</p>
        </AdminLayout>
      </QueryClientProvider>,
    )
    const nav = await screen.findByRole('navigation', { name: 'Admin sections' })
    const invites = screen.getByRole('link', { name: 'Invites' })
    const row = invites.parentElement!
    expect(row.parentElement).toBe(nav)
    expect(row).toContainElement(screen.getByRole('link', { name: 'Feedback' }))
    expect(row).toHaveClass('flex', 'flex-wrap')
    expect(invites).toHaveAttribute('aria-current', 'page')
  })
})
