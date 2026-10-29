import { createRequire } from 'node:module'
import { act, render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ToasterProps } from 'sonner'
import { ThemeProvider } from '@/components/ThemeProvider'
// Imported statically: vi.mock('sonner') below is hoisted above this import, so the provider graph
// loads once at collection and no test body pays for it against the 5s timeout.
import { ThemedToaster } from '@/app/providers'

/**
 * chrome/F4: every toast is a panel card on the tokens, in the theme the reader chose. Sonner's
 * `theme="system"` read prefers-color-scheme, not the site's own toggle (ThemeProvider, stored in
 * localStorage), so a reader who chose light on a dark OS got dark toasts; `richColors` painted success
 * and error toasts in Sonner's own greens and reds. app/providers.tsx renders the Toaster from
 * ThemedToaster, which passes ThemeProvider's theme, and styles every slot with token classes.
 *
 * Holds: the Toaster takes the ThemeProvider theme in both themes and never 'system'; richColors is off;
 * every colour, border and shadow class in toastOptions.classNames names a token in tailwind.config.js
 * or white (no palette step, no hex, no arbitrary value), and the card slot sets the panel surface in both themes
 * and the overlay step of the elevation ladder (e4 in light, no shadow in dark). The close button keeps a
 * hover in both themes: its forced rest outranks Sonner's own hover, so its hover is forced too (no slot
 * holds a hover its own rest outranks), and its fills are opaque, since it overhangs the card's corner.
 * Each of Sonner's four status toasts (success, error, warning, info) colours its icon and nothing else,
 * in its own status ink in each theme, and the ink clears 3:1 on the panel (WCAG 1.4.11): without
 * richColors the icon is the status signal, and a type with no slot would be drawn in the neutral ink.
 */

const captured = vi.hoisted(() => [] as ToasterProps[])
vi.mock('sonner', () => ({
  Toaster: (props: ToasterProps) => {
    captured.push(props)
    return null
  },
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}))

const config = createRequire(import.meta.url)('../../tailwind.config.js') as {
  theme: { extend: { colors: Record<string, unknown>; boxShadow: Record<string, string> } }
}
// White is the one Tailwind default the design system names as a token (DESIGN.md's snapshot; designSnapshotParity.spec.ts
// reads it the same way): the dark hover ink of a control that rests in the secondary ink (DESIGN_SYSTEM.md §2).
const COLORS = { ...config.theme.extend.colors, white: (createRequire(import.meta.url)('tailwindcss/colors') as { white: string }).white }
const SHADOWS = config.theme.extend.boxShadow

/** A colour path such as `text-primary-light` resolved through the token tree, or undefined. */
function tokenColor(path: string, tree: unknown = COLORS): string | undefined {
  if (typeof tree === 'string') return path === '' ? tree : undefined
  if (!tree || typeof tree !== 'object') return undefined
  const node = tree as Record<string, unknown>
  if (path === '' && typeof node.DEFAULT === 'string') return node.DEFAULT
  for (const key of Object.keys(node)) {
    if (path === key) {
      const hit = tokenColor('', node[key])
      if (hit) return hit
    }
    if (path.startsWith(`${key}-`)) {
      const hit = tokenColor(path.slice(key.length + 1), node[key])
      if (hit) return hit
    }
  }
  return undefined
}

/** Why a class is not a token class, or null when it is one. Variants (`dark:`, `[&_x]:`) are stripped. */
function offToken(cls: string): string | null {
  const utility = cls.slice(cls.lastIndexOf(':') + 1).replace(/^!/, '')
  if (/#|\[|rgb|hsl/.test(utility)) return 'an arbitrary value'
  if (['outline-none', 'shadow-none'].includes(utility)) return null
  const shadow = utility.match(/^shadow-(.+)$/)
  if (shadow) return shadow[1] in SHADOWS ? null : 'not a shadow token'
  const color = utility.match(/^(?:bg|text|border)-(.+?)(?:\/\d+)?$/)
  if (color) return tokenColor(color[1]) ? null : 'not a colour token'
  return 'not a colour, border or shadow utility'
}

/** A slot's hovers that never show: a hover without `!` on what the slot forces at rest (fill, ink or border). */
function deadHovers(value: string): string[] {
  const classes = value.split(/\s+/).filter(Boolean)
  const forced = new Set(classes.filter((cls) => !cls.includes('hover:')).flatMap((cls) => cls.match(/(?:^|:)!(bg|text|border)-/)?.[1] ?? []))
  return classes.filter((cls) => forced.has(cls.match(/hover:(bg|text|border)-/)?.[1] ?? ''))
}

/** The fills that are not opaque: an opacity modifier, or a token whose value is not a hex colour. */
function translucentFills(classes: string[]): string[] {
  return classes.filter((cls) => {
    const fill = cls.slice(cls.lastIndexOf(':') + 1).replace(/^!/, '').match(/^bg-(.+)$/)
    return fill !== null && (fill[1].includes('/') || !/^#[0-9a-f]{6}$/i.test(tokenColor(fill[1]) ?? ''))
  })
}

/** WCAG contrast of two hex colours. */
function contrast(a: string, b: string): number {
  const lum = (h: string) => {
    const ch = (i: number) => {
      const s = parseInt(h.slice(1 + i * 2, 3 + i * 2), 16) / 255
      return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
    }
    return 0.2126 * ch(0) + 0.7152 * ch(1) + 0.0722 * ch(2)
  }
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x)
  return Math.round(((hi + 0.05) / (lo + 0.05)) * 100) / 100
}

async function renderToaster(stored: 'light' | 'dark') {
  localStorage.setItem('theme', stored)
  await act(async () => {
    render(
      <ThemeProvider>
        <ThemedToaster />
      </ThemeProvider>,
    )
  })
  return captured[captured.length - 1]
}

describe('the Toaster on tokens (chrome/F4)', () => {
  afterEach(() => {
    captured.length = 0
    localStorage.clear()
    document.documentElement.classList.remove('dark')
  })

  it.each(['light', 'dark'] as const)('takes the reader’s %s theme from ThemeProvider, never "system", with richColors off', async (theme) => {
    const props = await renderToaster(theme)
    expect(props.theme).toBe(theme)
    expect(props.richColors).toBeFalsy()
  })

  it('styles every class slot with token classes only', async () => {
    const props = await renderToaster('light')
    const classNames = (props.toastOptions?.classNames ?? {}) as Record<string, string>
    const offenders = Object.entries(classNames).flatMap(([slot, value]) =>
      value
        .split(/\s+/)
        .filter(Boolean)
        .map((cls) => [slot, cls, offToken(cls)] as const)
        .filter(([, , why]) => why)
        .map(([s, cls, why]) => `${s}: ${cls} (${why})`),
    )
    expect(offenders).toEqual([])
    // Anti-vacuity: the card slot paints the panel surface and its ink in both themes, and floats on
    // the ladder's overlay step (e4/e5 menus & overlays), not the card step e2.
    expect(classNames.toast.split(/\s+/)).toEqual(
      expect.arrayContaining(['!bg-panel-light', 'dark:!bg-panel-dark', '!text-text-primary-light', 'dark:!text-text-primary-dark', '!shadow-e4', 'dark:!shadow-none']),
    )
    expect(classNames.toast).not.toMatch(/(?:^|\s)!shadow-e[123](?:\s|$)/)
    expect(offToken('bg-gray-800')).toBe('not a colour token')
    expect(offToken('!shadow-e9')).toBe('not a shadow token')
    expect(offToken('!bg-[#111]')).toBe('an arbitrary value')
  })

  it.each(['success', 'error', 'warning', 'info'] as const)(
    'the %s toast colours only its icon, in its status ink in both themes, at 3:1 on the panel',
    async (status) => {
      const props = await renderToaster('light')
      const classNames = (props.toastOptions?.classNames ?? {}) as Record<string, string>
      const slot = (classNames[status] ?? '').split(/\s+/).filter(Boolean)
      expect(slot, `the ${status} slot`).toEqual([`[&_[data-icon]]:text-${status}-light`, `dark:[&_[data-icon]]:text-${status}-dark`])
      expect(contrast(tokenColor(`${status}-light`)!, tokenColor('panel-light')!), 'light icon on the panel').toBeGreaterThanOrEqual(3)
      expect(contrast(tokenColor(`${status}-dark`)!, tokenColor('panel-dark')!), 'dark icon on the panel').toBeGreaterThanOrEqual(3)
    },
  )

  it('keeps a hover on the close button, forced as its rest is, on opaque fills', async () => {
    const props = await renderToaster('light')
    const classNames = (props.toastOptions?.classNames ?? {}) as Record<string, string>
    const close = classNames.closeButton.split(/\s+/)
    // The forced rest outranks Sonner's own hover, so the slot states one: the quiet controls' tint and the
    // primary ink in light; in dark white over the panel it keeps, since dark primary sits 1.24:1 from the
    // dark secondary rest, a hover dark barely shows (themePairs.spec.ts, faint hovers).
    expect(close).toEqual(
      expect.arrayContaining(['hover:!bg-brand-weak', 'hover:!text-text-primary-light', 'dark:hover:!bg-panel-dark', 'dark:hover:!text-white']),
    )
    expect(Object.entries(classNames).flatMap(([slot, value]) => deadHovers(value).map((cls) => `${slot}: ${cls}`))).toEqual([])
    // Sonner translates the button -35% over the card's corner, so a translucent fill (the dark tint
    // brand-weak-dark among them) would show the page through its overhang: every fill it takes is opaque.
    expect(translucentFills(close)).toEqual([])
    // Anti-vacuity: each check refuses what it is for.
    expect(deadHovers('!bg-panel-light hover:bg-brand-weak hover:!text-text-primary-light')).toEqual(['hover:bg-brand-weak'])
    expect(translucentFills(['dark:hover:!bg-brand-weak-dark', 'hover:!bg-panel-light/90', 'dark:!bg-panel-dark'])).toEqual([
      'dark:hover:!bg-brand-weak-dark',
      'hover:!bg-panel-light/90',
    ])
  })
})
