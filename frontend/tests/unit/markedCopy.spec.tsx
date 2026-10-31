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

/**
 * Below its measure the margin gives way, and a word still longer than what is left breaks inside the marked
 * block, never past it. On the landing's card at 320px under 200% text the block kept 115px of 32px serif (about
 * 139px since its side padding narrows below the measure), and without `overflow-wrap` seven words of the evidence
 * row ran up to 49px past it. The block adds no hyphen to the
 * filing's words: CI's Chromium carries a hyphenation dictionary, and under auto hyphenation it hyphenated ordinary
 * words at every width ("re-sults" at 1440px), which risk-evidence-rows.spec.ts reads as words broken mid-word on
 * the filing page. CI renders the landing with no evidence row, so this reads the rules, comments aside.
 */
describe('a marked block keeps a word longer than its measure inside itself', () => {
  it('breaks it anywhere inside the block, and never hyphenates the filing\'s words', () => {
    const css = readFileSync(path.join(FRONTEND, 'app/globals.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')
    const rule = css.match(/^\.en-marked\s*\{([^}]*)\}/m)?.[1] ?? ''
    expect(rule, 'the marked block rule (anti-vacuity)').toMatch(/border-left:\s*3px solid/)
    expect(rule).toMatch(/(?<![-\w])hyphens:\s*manual/)
    expect(rule).toMatch(/overflow-wrap:\s*anywhere/)
    // No rule that reaches a marked block, or anything inside one, turns hyphenation back on.
    const reaching = [...css.matchAll(/([^{}]+)\{([^}]*)\}/g)].filter(([, selector]) => selector.includes('.en-marked'))
    expect(reaching.length, 'rules naming .en-marked (anti-vacuity)').toBeGreaterThanOrEqual(2)
    for (const [, selector, body] of reaching) expect(body, selector.trim()).not.toMatch(/hyphens:\s*auto/)
  })
})
