import { useEffect, useRef, useState } from 'react'
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

// The route the header renders on; a test changes it and rerenders to navigate.
let mockPathname = '/'
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  usePathname: () => mockPathname,
}))

// Stub chrome/children so the test isolates Header's auth-state branching.
// The toggle renders its className so the placement test below can read where it shows.
vi.mock('@/components/ThemeToggle', () => ({
  ThemeToggle: ({ className = '' }: { className?: string }) => <button type="button" data-testid="theme-toggle" className={className} aria-label="Switch theme" />,
}))
vi.mock('@/components/EarningsNerdLogo', () => ({ default: () => null }))
vi.mock('@/features/notifications/components/NotificationBell', () => ({
  // A press asks to toggle the panel; data-open shows a held panel's state (absent where the bell holds its own).
  default: ({ className = '', open, onOpenChange }: { className?: string; open?: boolean; onOpenChange?: (open: boolean) => void }) => (
    <button type="button" data-testid="notification-bell" data-open={open === undefined ? undefined : String(open)} className={className} onClick={() => onOpenChange?.(!open)} />
  ),
}))
vi.mock('@/features/auth/components/UserMenu', () => ({
  default: ({ user }: { user: { email: string } }) => <div data-testid="user-menu">{user.email}</div>,
}))

vi.mock('@/features/auth/api/auth-api', () => ({
  getCurrentUserSafe: vi.fn(),
  logout: vi.fn(),
}))

// Header layout/auth cases run with collection released. publicAccess.spec.tsx holds the real reader.
vi.mock('@/features/marketing/components/PublicAccessProvider', async () => {
  const { ACCESS_COPY } = await import('@/features/marketing/lib/access')
  return { usePublicAccess: (mode: keyof typeof ACCESS_COPY) => ACCESS_COPY[mode] }
})

import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import Header, { SITE_HEADER_HEIGHT_PROPERTY } from '@/components/Header'
import { ACCESS_COPY, accountLabels } from '@/features/marketing/lib/access'

const mockUser = {
  id: 1,
  email: 'neil@earningsnerd.io',
  full_name: 'Neil Mac',
  is_pro: true,
  is_beta: false,
  is_admin: true,
  email_verified: true,
}

function renderHeader(props: React.ComponentProps<typeof Header> = {}) {
  // retry:false so a thrown queryFn surfaces as an error immediately (no backoff in tests).
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <Header {...props} />
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
    // One bell in each bar: the full bar's, and the compact bar's at every width below 72rem (E176), with the compact
    // bar's 44px target, after its theme toggle and before the menu button, where a guest's link sits. Before, a
    // wrapper hid the compact bar's below lg, so a phone kept the unread state behind the menu.
    const bells = screen.getAllByTestId('notification-bell')
    expect(bells).toHaveLength(2)
    expect(bells[1]).toHaveClass('min-h-11', 'min-w-11')
    expect(bells[1].previousElementSibling).toHaveAttribute('data-testid', 'theme-toggle')
    expect(bells[1].nextElementSibling).toBe(screen.getByRole('button', { name: 'Open menu' }))
    expect(bells[1].parentElement, "the compact bar's own group, shown at every width below 72rem").toHaveClass('[@media(min-width:72rem)]:hidden')
    expect(bells[1].parentElement).not.toHaveClass('hidden')
    expect(screen.queryByRole('link', { name: /log in/i })).not.toBeInTheDocument()
  })

  it("keeps a copy of a guest's controls in the full bar's cell for a reader, which nothing can focus or read", async () => {
    vi.mocked(getCurrentUserSafe).mockResolvedValue(mockUser)
    const { container } = renderHeader()
    await screen.findByTestId('user-menu')
    // The cell keeps a guest's width whatever the check shows, so the nav keeps its place (E175): the copy shares the
    // live controls' grid cell, which sets them at its right edge.
    const copy = container.querySelector('span[aria-hidden="true"].invisible')
    expect(copy).not.toBeNull()
    expect(copy).toHaveTextContent(new RegExp(`^Log in${accountLabels('invite').join('')}$`))
    expect(copy!.querySelectorAll('a, button, input, select, textarea, [tabindex]')).toHaveLength(0)
    const live = copy!.nextElementSibling as HTMLElement
    expect([copy, live].map((el) => el!.className.includes('col-start-1 row-start-1'))).toEqual([true, true])
    expect(live).toHaveClass('justify-end')
    expect(within(live).getByTestId('user-menu')).toBeInTheDocument()
  })

  it("keeps the copy in step with a guest's own controls in either access mode, holding every account label", async () => {
    vi.mocked(getCurrentUserSafe).mockResolvedValue(null)
    for (const accessMode of ['invite', 'public'] as const) {
      const { container, unmount } = renderHeader({ accessMode })
      await screen.findByRole('link', { name: /log in/i })
      // The copy's account link holds every label the live one can print in the build's mode, the mode's own and the
      // live example's, in one cell, so its width is a guest's in either mode whatever readiness answers (E220).
      const copy = container.querySelector('span[aria-hidden="true"].invisible')!
      const labels = [...copy.querySelectorAll('.col-start-1.row-start-1')].map((cell) => cell.textContent)
      expect(labels, accessMode).toEqual(accountLabels(accessMode))
      expect(copy.textContent, accessMode).toBe(`Log in${accountLabels(accessMode).join('')}`)
      expect(copy.nextElementSibling!.textContent, accessMode).toBe(`Log in${ACCESS_COPY[accessMode].cta}`)
      unmount()
    }
  })

  it('shows Log in / the account CTA only on a definitive logged-out (null)', async () => {
    vi.mocked(getCurrentUserSafe).mockResolvedValue(null)
    renderHeader()

    expect(await screen.findByRole('link', { name: /log in/i })).toBeInTheDocument()
    // No accessMode prop = the conservative invite copy (never advertise a signup the API rejects).
    expect(screen.getByRole('link', { name: ACCESS_COPY.invite.cta })).toHaveAttribute('href', ACCESS_COPY.invite.href)
    expect(screen.queryByTestId('user-menu')).not.toBeInTheDocument()
    expect(screen.queryByTestId('notification-bell')).not.toBeInTheDocument()
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

  // The compact bar's bell panel and its menu: one is open at a time, opening either closes the other.
  it("keeps one of the compact bar's bell panel and its menu open at a time", async () => {
    vi.mocked(getCurrentUserSafe).mockResolvedValue(mockUser)
    renderHeader()
    await screen.findByTestId('user-menu')
    const bell = screen.getAllByTestId('notification-bell')[1]
    expect(bell).toHaveAttribute('data-open', 'false')

    fireEvent.click(screen.getByRole('button', { name: 'Open menu' }))
    expect(screen.getByRole('navigation', { name: 'Mobile navigation' })).toBeInTheDocument()
    fireEvent.click(bell)
    expect(bell, 'the panel opens').toHaveAttribute('data-open', 'true')
    expect(screen.queryByRole('navigation', { name: 'Mobile navigation' }), 'and closes the menu').not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Open menu' }))
    expect(screen.getByRole('navigation', { name: 'Mobile navigation' }), 'the menu opens').toBeInTheDocument()
    expect(bell, 'and closes the panel').toHaveAttribute('data-open', 'false')
  })

  // Below 72rem the compact menu is the only menu, so it holds an admin's links, after Settings and before Log out, as
  // the account menu orders them (E176, chief design on #1565, comment 6380050139); a reader who is no admin gets none.
  it.each([
    ['an admin', true],
    ['a reader who is no admin', false],
  ] as const)("holds the admin links in the compact menu for %s, as the account menu orders them", async (_who, isAdmin) => {
    vi.mocked(getCurrentUserSafe).mockResolvedValue({ ...mockUser, is_admin: isAdmin })
    renderHeader()
    await screen.findByTestId('user-menu')
    fireEvent.click(screen.getByRole('button', { name: 'Open menu' }))
    const menu = screen.getByRole('navigation', { name: 'Mobile navigation' })
    const stops = [...menu.querySelectorAll('a[href], button')].map((el) => el.textContent?.trim())
    const settings = stops.indexOf('Settings')
    const admin = isAdmin ? ['Admin · Invites', 'Admin · Feedback'] : []
    expect(settings, 'Settings is in the menu').toBeGreaterThan(-1)
    expect(stops.slice(settings, settings + admin.length + 2), 'Settings, the admin links, then Log out').toEqual(['Settings', ...admin, 'Log out'])
    for (const [label, href] of [['Admin · Invites', '/admin/invites'], ['Admin · Feedback', '/admin/feedback']] as const) {
      const link = within(menu).queryByRole('link', { name: label })
      if (isAdmin) expect(link).toHaveAttribute('href', href)
      else expect(link).toBeNull()
    }
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

  it('leaves the menu open when a layer above already took Escape', async () => {
    renderWithPage()
    const menu = await openMenu()
    const link = within(menu).getAllByRole('link')[0]
    act(() => link.focus())
    // A layer's own capture handler takes the key first, as the Ask sheet's does: one press closes one layer.
    const take = (event: KeyboardEvent) => {
      if (event.key === 'Escape') event.preventDefault()
    }
    document.addEventListener('keydown', take, true)
    try {
      fireEvent.keyDown(link, { key: 'Escape' })
      expect(menuOpen()).toBe(true)
    } finally {
      document.removeEventListener('keydown', take, true)
    }
  })

  // A press moves focus on its mousedown, before its release: to what it presses, or to the page's main region
  // (tabindex -1) when it presses text. The header is in the page's flow, so a close on that focusout moved the page
  // under the pointer at the top of a page and the release landed elsewhere: a tap on a link below the open menu
  // followed nothing. A reader who presses can see where, so a press leaves the menu open, as before (chief design's
  // ruling on #1542); the e2e's tap case holds the link followed in a browser.
  it('leaves the menu open when a press moves focus out of the header, after the press too', async () => {
    renderWithPage()
    await openMenu()
    // A tap on the toggle focused it.
    act(() => screen.getByRole('button', { name: 'Close menu' }).focus())
    const onPage = screen.getByRole('button', { name: 'A control on the page' })
    fireEvent.mouseDown(onPage)
    act(() => onPage.focus())
    fireEvent.mouseUp(onPage)
    fireEvent.click(onPage)
    expect(menuOpen(), 'the press moved focus out of the header').toBe(true)
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0))
    })
    expect(menuOpen(), 'and the task after it').toBe(true)
  })

  // From lg the open menu lies over the page (lg:absolute), so a press outside the header closes it, as it closes the
  // bar's other menus: the header keeps the bar's height, so the press lands where it was aimed (E182, chief design on
  // #1565, comment 6380050139). jsdom applies no stylesheet, so the menu's position is set inline here, and the cases
  // around this one, with no position set, hold the in-flow menu open; the e2e press case holds both in a browser.
  it('closes the menu on a press outside the header where the open menu lies over the page, and keeps it on a press inside', async () => {
    renderWithPage()
    await openMenu()
    const nav = screen.getByRole('navigation', { name: 'Mobile navigation' })
    ;(nav.parentElement as HTMLElement).style.position = 'absolute'
    fireEvent.mouseDown(within(nav).getByRole('link', { name: 'Pricing' }))
    expect(menuOpen(), 'a press inside the header keeps it').toBe(true)
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0))
    })
    fireEvent.mouseDown(screen.getByRole('button', { name: 'A control on the page' }))
    expect(menuOpen(), 'a press on the page closes it').toBe(false)
  })

  it('leaves the menu open when a press on text moves focus to the page region', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
        <Header />
        <div id="main" tabIndex={-1} data-testid="page-region">
          <p>Some text on the page</p>
        </div>
      </QueryClientProvider>,
    )
    await openMenu()
    act(() => screen.getByRole('button', { name: 'Close menu' }).focus())
    const region = screen.getByTestId('page-region')
    fireEvent.mouseDown(screen.getByText('Some text on the page'))
    act(() => region.focus())
    expect(menuOpen()).toBe(true)
  })

  it("ends a press's mark with its task, so a later keyboard or script focus still closes the menu", async () => {
    renderWithPage()
    await openMenu()
    act(() => screen.getByRole('button', { name: 'Close menu' }).focus())
    const onPage = screen.getByRole('button', { name: 'A control on the page' })
    fireEvent.mouseDown(document.body)
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0))
    })
    act(() => onPage.focus())
    expect(menuOpen()).toBe(false)
  })

  it('closes on a navigation, so a press on a page link never opens the next page under the menu', async () => {
    mockPathname = '/'
    try {
      const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
      const tree = () => (
        <QueryClientProvider client={queryClient}>
          <Header />
        </QueryClientProvider>
      )
      const { rerender } = render(tree())
      await openMenu()
      rerender(tree())
      expect(menuOpen(), 'a render on the same route keeps it').toBe(true)
      mockPathname = '/company/AAPL'
      rerender(tree())
      expect(menuOpen(), 'the next route opens with it closed').toBe(false)
    } finally {
      mockPathname = '/'
    }
  })

  it('closes without a synchronous flush when a modal layer takes the focus from an effect', async () => {
    // A layer that traps focus moves it from its own effect, inside React's commit, where React refuses flushSync.
    function Sheet() {
      const first = useRef<HTMLButtonElement>(null)
      useEffect(() => first.current?.focus(), [])
      return (
        <div role="dialog" aria-modal="true" aria-label="A sheet">
          <button ref={first} type="button">In the sheet</button>
        </div>
      )
    }
    function PageWithSheet() {
      const [open, setOpen] = useState(false)
      return (
        <main>
          <button type="button" onClick={() => setOpen(true)}>Open the sheet</button>
          {open && <Sheet />}
        </main>
      )
    }
    const errors = vi.spyOn(console, 'error').mockImplementation(() => {})
    try {
      const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
      render(
        <QueryClientProvider client={queryClient}>
          <Header />
          <PageWithSheet />
        </QueryClientProvider>,
      )
      const menu = await openMenu()
      act(() => within(menu).getAllByRole('link')[0].focus())
      fireEvent.click(screen.getByRole('button', { name: 'Open the sheet' }))
      expect(document.activeElement).toBe(screen.getByRole('button', { name: 'In the sheet' }))
      expect(menuOpen()).toBe(false)
      expect(errors.mock.calls.map((call) => String(call[0])).filter((message) => /flushSync/.test(message))).toEqual([])
    } finally {
      errors.mockRestore()
    }
  })
})
