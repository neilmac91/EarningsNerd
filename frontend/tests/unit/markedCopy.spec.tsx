import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { EnRef, MarkedCopy } from '@/components/ui/MarkedCopy'

/**
 * The margin twin sits on its marker's line at any text size (DESIGN.md › Graphic device). The
 * founder's review of PR #1226 measured it 8px low under a 32px root font: the placement assumed a
 * 16px twin, while `.en-margin-mark` sets `line-height: 1rem`, which grows with the root. The twin
 * is now anchored at the marker's measured midpoint and centres itself there with its own
 * `translateY(-50%)`. jsdom has no layout, so the boxes are given; a real browser draws the rest.
 */
const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')

function boxes({ bodyTop, markerTop, markerHeight }: { bodyTop: number; markerTop: number; markerHeight: number }) {
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
    const marker = this.dataset.enRef !== undefined
    const top = marker ? markerTop : bodyTop
    const height = marker ? markerHeight : 400
    return { top, height, bottom: top + height, left: 0, right: 100, width: 100, x: 0, y: top, toJSON: () => ({}) } as DOMRect
  })
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('MarkedCopy places each twin on its marker', () => {
  it.each([
    ['the default 16px root', 16, 48],
    ['a 20px root', 20, 50],
    ['a 32px root (200%)', 32, 56],
  ])('anchors the twin at the marker’s midpoint under %s', (_label, markerHeight, expectedTop) => {
    boxes({ bodyTop: 100, markerTop: 140, markerHeight })
    const { container } = render(
      <MarkedCopy>
        <p>
          Services net sales rose.
          <EnRef label="[1]" />
        </p>
      </MarkedCopy>,
    )
    const twin = container.querySelector<HTMLElement>('.en-margin-mark')
    expect(twin?.textContent).toBe('[1]')
    expect(twin?.closest('[aria-hidden="true"]')).not.toBeNull()
    expect(twin?.style.top).toBe(`${expectedTop}px`)
  })

  it('the twin centres itself on that point, whatever height it renders at', () => {
    const css = readFileSync(path.join(FRONTEND, 'app/globals.css'), 'utf8')
    const rule = css.match(/\.en-margin-mark\s*\{([^}]*)\}/)?.[1] ?? ''
    expect(rule).toMatch(/transform:\s*translateY\(-50%\)/)
  })
})
