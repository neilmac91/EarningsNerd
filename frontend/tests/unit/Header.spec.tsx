import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}))

// Stub chrome/children so the test isolates Header's auth-state branching.
// The toggle renders its className so the placement test below can read where it shows.
vi.mock('@/components/ThemeToggle', () => ({
  ThemeToggle: ({ className = '' }: { className?: string }) => <button type="button" data-testid="theme-toggle" className={className} aria-label="Switch theme" />,
}))
vi.mock('@/components/EarningsNerdLogo', () => ({ default: () => null }))
vi.mock('@/features/notifications/components/NotificationBell', () => ({
  default: () => <div data-testid="notification-bell" />,
}))
vi.mock('@/features/auth/components/UserMenu', () => ({
  default: ({ user }: { user: { email: string } }) => <div data-testid="user-menu">{user.email}</div>,
}))

vi.mock('@/features/auth/api/auth-api', () => ({
  getCurrentUserSafe: vi.fn(),
  logout: vi.fn(),
}))

import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import Header, { SITE_HEADER_HEIGHT_PROPERTY } from '@/components/Header'
import { ACCESS_COPY } from '@/features/marketing/lib/access'

const mockUser = {
  id: 1,
  email: 'neil@earningsnerd.io',
  full_name: 'Neil Mac',
  is_pro: true,
  is_beta: false,
  is_admin: true,
  email_verified: true,
}

function renderHeader() {
  // retry:false so a thrown queryFn surfaces as an error immediately (no backoff in tests).
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <Header />
    </QueryClientProvider>,
  )
  return { queryClient, ...utils }
}

describe('Header auth state', () => {
  beforeEach(() => {
    vi.mocked(getCurrentUserSafe).mockReset()
  })

  it('shows the user menu (avatar) when logged in', async () => {
    vi.mocked(getCurrentUserSafe).mockResolvedValue(mockUser)
    renderHeader()

    expect(await screen.findByTestId('user-menu')).toHaveTextContent('neil@earningsnerd.io')
    expect(screen.getByTestId('notification-bell')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /log in/i })).not.toBeInTheDocument()
  })

  it('shows Log in / the account CTA only on a definitive logged-out (null)', async () => {
    vi.mocked(getCurrentUserSafe).mockResolvedValue(null)
    renderHeader()

    expect(await screen.findByRole('link', { name: /log in/i })).toBeInTheDocument()
    // No accessMode prop = the conservative invite copy (never advertise a signup the API rejects).
    expect(screen.getByRole('link', { name: ACCESS_COPY.invite.cta })).toHaveAttribute('href', ACCESS_COPY.invite.href)
    expect(screen.queryByTestId('user-menu')).not.toBeInTheDocument()
  })

  it('advertises open registration only when the access mode is public', async () => {
    vi.mocked(getCurrentUserSafe).mockResolvedValue(null)
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
        <Header accessMode="public" />
      </QueryClientProvider>,
    )

    expect(await screen.findByRole('link', { name: ACCESS_COPY.public.cta })).toHaveAttribute('href', '/register')
    expect(screen.getByRole('link', { name: ACCESS_COPY.public.ctaShort })).toHaveAttribute('href', '/register')
    expect(screen.queryByRole('link', { name: ACCESS_COPY.invite.cta })).not.toBeInTheDocument()
  })

  // While the auth check is still in flight (pending, including retry backoff) we hold the
  // skeleton — never flash the logged-out CTAs to a user who may actually be signed in.
  it('holds the skeleton while the auth check is pending', () => {
    // A promise that never resolves keeps the query pending.
    vi.mocked(getCurrentUserSafe).mockReturnValue(new Promise<never>(() => {}))
    const { container } = renderHeader()

    // The auth-loading bone is the DS <Skeleton> (shimmer sweep), not a raw animate-pulse.
    expect(container.querySelector('.animate-shimmer')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /log in/i })).not.toBeInTheDocument()
    expect(screen.queryByTestId('user-menu')).not.toBeInTheDocument()
  })

  // Safety net: once the check has *settled* into an error (non-401 failure, all retries
  // exhausted), the header degrades to the logged-out CTAs so the user is never trapped on a
  // dead placeholder circle — the bug that hid the account menu behind a stuck skeleton.
  it('falls back to the logged-out CTAs once the auth check settles in error', async () => {
    // The query retries with backoff (retry: 3); drive fake timers to exhaust the retries so we
    // assert the settled *error* state, not the (still-skeleton) pending state.
    vi.useFakeTimers()
    try {
      vi.mocked(getCurrentUserSafe).mockRejectedValue(new Error('timeout of 30000ms exceeded'))
      const { queryClient, container } = renderHeader()

      await vi.advanceTimersByTimeAsync(30_000) // past the full retry backoff (~1s+2s+4s)

      expect(queryClient.getQueryState(['current-user'])?.status).toBe('error')
      expect(screen.getByRole('link', { name: /log in/i })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: ACCESS_COPY.invite.cta })).toBeInTheDocument()
      expect(container.querySelector('.animate-shimmer')).not.toBeInTheDocument()
      expect(screen.queryByTestId('user-menu')).not.toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })
})

// Below a 24rem viewport (a phone with enlarged text, or a 360px or 375px phone) the bar keeps one row:
// the theme toggle, a preference rather than a next step, leaves the bar for the mobile menu's first row,
// so the bar is the logo, the account link and the menu button. Above 24rem it stays in the bar and the
// menu has none. jsdom applies no media query, so this reads the classes and the order that place it; the
// geometry is tests/e2e/reflow-200.spec.ts's one-row and 390x664 cases.
describe('Header theme toggle placement', () => {
  const NARROW_HIDDEN = '[@media(max-width:24rem)]:hidden'
  const NARROW_SHOWN = '[@media(max-width:24rem)]:flex'

  it('sits in the bar above 24rem and inside the mobile menu below it', async () => {
    vi.mocked(getCurrentUserSafe).mockResolvedValue(null)
    renderHeader()
    await screen.findByRole('link', { name: ACCESS_COPY.invite.ctaShort })

    // Menu closed: the desktop group's toggle and the mobile bar's, which yields below 24rem.
    const [desktop, bar] = screen.getAllByTestId('theme-toggle')
    expect(screen.getAllByTestId('theme-toggle')).toHaveLength(2)
    expect(desktop.className.split(' ')).not.toContain(NARROW_HIDDEN)
    expect(bar.className.split(' ')).toContain(NARROW_HIDDEN)
    expect(bar.parentElement).toContainElement(screen.getByRole('link', { name: ACCESS_COPY.invite.ctaShort }))

    // Menu open: a third toggle inside the mobile navigation, in a row shown only below 24rem.
    fireEvent.click(screen.getByRole('button', { name: 'Open menu' }))
    const menu = screen.getByRole('navigation', { name: 'Mobile navigation' })
    const inMenu = within(menu).getByTestId('theme-toggle')
    expect(inMenu.className.split(' ')).not.toContain(NARROW_HIDDEN)
    const row = inMenu.parentElement!.className.split(' ')
    expect(row).toContain('hidden')
    expect(row).toContain(NARROW_SHOWN)
    expect(screen.getAllByTestId('theme-toggle')).toHaveLength(3)
  })

  // The Theme row is the menu's first row, ahead of the nav links, so it opens directly under the bar, in
  // view before the open menu is scrolled (the menu scrolls inside the viewport below the bar; the 390x664
  // and 360x640 cases in tests/e2e/reflow-200.spec.ts), and its toggle is the menu's first Tab stop.
  it.each([
    ['a guest', null],
    ['a signed-in reader', mockUser],
  ] as const)('puts the Theme row first in the open menu, for %s', async (_who, user) => {
    vi.mocked(getCurrentUserSafe).mockResolvedValue(user)
    renderHeader()
    if (user) await screen.findByTestId('user-menu')
    else await screen.findByRole('link', { name: ACCESS_COPY.invite.ctaShort })

    fireEvent.click(screen.getByRole('button', { name: 'Open menu' }))
    const menu = screen.getByRole('navigation', { name: 'Mobile navigation' })
    const row = within(menu).getByTestId('theme-toggle').parentElement!
    const items = [...menu.children]
    const firstLink = within(menu).getAllByRole('link')[0]
    expect(items.indexOf(row), "the Theme row is the menu's first row").toBe(0)
    expect(items.indexOf(row), 'the Theme row precedes the first nav link').toBeLessThan(items.indexOf(firstLink))
    expect(menu.querySelector('a[href], button')?.getAttribute('data-testid') ?? null, "the menu's first Tab stop is its theme toggle").toBe('theme-toggle')
  })
})

// The header's rendered height is the one offset under it (DESIGN_SYSTEM.md §4 Stacking): published
// on <html> as --site-header-h before the first paint, rounded up to a whole pixel, followed on
// every resize, and cleared when the header leaves (the auth routes), so 4rem is the fallback.
describe('Header publishes its height', () => {
  it('sets --site-header-h from its own box, follows a resize and clears it on unmount', () => {
    vi.mocked(getCurrentUserSafe).mockReturnValue(new Promise<never>(() => {}))
    let height = 238.4
    let resize: (() => void) | undefined
    vi.stubGlobal('ResizeObserver', class {
      constructor(callback: () => void) { resize = callback }
      observe() {}
      disconnect() {}
    })
    const rect = vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
      return { height: this.tagName === 'HEADER' ? height : 0 } as DOMRect
    })
    try {
      const { unmount } = renderHeader()
      const root = document.documentElement
      expect(root.style.getPropertyValue(SITE_HEADER_HEIGHT_PROPERTY)).toBe('239px')
      height = 151
      resize?.()
      expect(root.style.getPropertyValue(SITE_HEADER_HEIGHT_PROPERTY)).toBe('151px')
      unmount()
      expect(root.style.getPropertyValue(SITE_HEADER_HEIGHT_PROPERTY)).toBe('')
    } finally {
      rect.mockRestore()
      vi.unstubAllGlobals()
    }
  })
})

// The open mobile menu is a disclosure (E167, chief design's ruling on #1521): it closes when focus leaves the
// header, and Escape closes it. Under 200% text on a phone the open menu fills the screen, and it stayed open when
// a Tab left it, so the next control was scrolled into view under the menu, past the screen's foot. The browser
// scrolls a newly focused control into view after its focus event, reading the document's scroll padding, which reads
// --site-header-h; so by that focus event the menu is gone and the closed bar's height is published. The geometry is
// tests/e2e/header-covers-nothing.spec.ts's open-menu walk.
describe('Header mobile menu closes as a disclosure', () => {
  const OPEN_HEIGHT = 844
  const CLOSED_HEIGHT = 64.5

  function renderWithPage() {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    return render(
      <QueryClientProvider client={queryClient}>
        <Header />
        <main>
          <button type="button">A control on the page</button>
        </main>
      </QueryClientProvider>,
    )
  }

  /** The header's box: the open menu's height while the menu is mounted, the bar's otherwise. No ResizeObserver
      fires, so only a publish in the commit itself moves the property. */
  function measureByMenu() {
    vi.stubGlobal('ResizeObserver', class {
      observe() {}
      disconnect() {}
    })
    return vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
      if (this.tagName !== 'HEADER') return { height: 0 } as DOMRect
      return { height: this.querySelector('nav[aria-label="Mobile navigation"]') ? OPEN_HEIGHT : CLOSED_HEIGHT } as DOMRect
    })
  }

  async function openMenu() {
    await screen.findByRole('link', { name: ACCESS_COPY.invite.ctaShort })
    fireEvent.click(screen.getByRole('button', { name: 'Open menu' }))
    return screen.getByRole('navigation', { name: 'Mobile navigation' })
  }

  const menuOpen = () => screen.queryByRole('navigation', { name: 'Mobile navigation' }) !== null
  const published = () => document.documentElement.style.getPropertyValue(SITE_HEADER_HEIGHT_PROPERTY)

  beforeEach(() => {
    vi.mocked(getCurrentUserSafe).mockReset()
    vi.mocked(getCurrentUserSafe).mockResolvedValue(null)
  })

  it("closes when focus moves to a control outside the header, before that control's focus event", async () => {
    const rect = measureByMenu()
    try {
      renderWithPage()
      const menu = await openMenu()
      expect(published(), 'the commit that opens the menu publishes its height').toBe(`${OPEN_HEIGHT}px`)
      const last = within(menu).getAllByRole('link').at(-1)!
      act(() => last.focus())

      const onPage = screen.getByRole('button', { name: 'A control on the page' })
      let atFocus: { menuOpen: boolean; published: string } | undefined
      onPage.addEventListener('focus', () => {
        atFocus = { menuOpen: menuOpen(), published: published() }
      })
      act(() => onPage.focus())
      expect(atFocus, 'the menu closed, and the closed bar was published, inside the focusout').toEqual({ menuOpen: false, published: '65px' })
      expect(document.activeElement).toBe(onPage)
    } finally {
      rect.mockRestore()
      vi.unstubAllGlobals()
    }
  })

  it('stays open while focus moves inside the header, and when focus leaves with no next target', async () => {
    renderWithPage()
    const menu = await openMenu()
    const [first, second] = within(menu).getAllByRole('link')
    act(() => first.focus())
    act(() => second.focus())
    expect(menuOpen(), 'a Tab from one menu link to the next').toBe(true)
    act(() => screen.getByRole('button', { name: 'Close menu' }).focus())
    expect(menuOpen(), 'a Shift+Tab back to the toggle').toBe(true)
    // Another window, or a tap on text: focus goes nowhere in particular, so the menu stays as the reader left it.
    fireEvent.blur(screen.getByRole('button', { name: 'Close menu' }), { relatedTarget: null })
    expect(menuOpen(), 'a blur with no next target').toBe(true)
  })

  it('closes on Escape and returns a focus inside the menu to its toggle', async () => {
    renderWithPage()
    const menu = await openMenu()
    const link = within(menu).getAllByRole('link')[0]
    act(() => link.focus())
    fireEvent.keyDown(link, { key: 'Escape' })
    expect(menuOpen()).toBe(false)
    expect(document.activeElement, 'the menu left with the focus, so the focus goes back to its toggle').toBe(screen.getByRole('button', { name: 'Open menu' }))
  })

  it('closes on Escape and leaves a focus elsewhere in the bar where it is', async () => {
    renderWithPage()
    await openMenu()
    const home = screen.getByRole('link', { name: 'EarningsNerd home' })
    act(() => home.focus())
    fireEvent.keyDown(home, { key: 'Escape' })
    expect(menuOpen()).toBe(false)
    expect(document.activeElement).toBe(home)
  })
})
