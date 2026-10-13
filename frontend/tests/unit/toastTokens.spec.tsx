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
 * (no palette step, no hex, no arbitrary value), and the card slot sets the panel surface in both themes
 * and the overlay step of the elevation ladder (e4 in light, no shadow in dark).
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
const COLORS = config.theme.extend.colors
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
})
