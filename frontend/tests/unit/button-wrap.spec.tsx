import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Button, RESERVE_LABEL, RESERVE_ROW, buttonVariants, type ButtonSize } from '@/components/ui/Button'

describe('Button label wrapping', () => {
  it('makes wrapping an opt-in state shared by buttons and links without conflicting sizing classes', () => {
    const sizes: ButtonSize[] = ['sm', 'md', 'lg', 'icon-sm']
    const { rerender } = render(<Button>Open report</Button>)
    for (const [index, size] of sizes.entries()) {
      rerender(<Button size={size}>Open report</Button>)
      const button = screen.getByRole('button', { name: 'Open report' })
      const height = [8, 10, 12, 8][index]
      expect(button).toHaveClass(`h-${height}`, 'whitespace-nowrap')
      rerender(<Button size={size} wrap>Open report</Button>)
      expect(button).not.toHaveAttribute('wrap')
      expect(button.className).toBe(buttonVariants({ size, wrap: true }))
      if (size === 'icon-sm') {
        expect(button).toHaveClass('h-8', 'w-8', 'p-0', 'whitespace-nowrap')
      } else {
        expect(button).toHaveClass(`min-h-${height}`, 'whitespace-normal')
        expect(button.className.split(/\s+/).filter(token => /^!?h-|^!?whitespace-nowrap$|^!/.test(token))).toEqual([])
      }
    }
  })

  it('below 24rem the narrow state keeps a caller\'s own min-h and py, through <Button> and buttonVariants alike', () => {
    const narrow = (className: string) => className.split(/\s+/).filter((token) => token.startsWith('[@media(max-width:24rem)]:'))
    const bare = buttonVariants({ size: 'md' })
    expect(narrow(bare)).toEqual(expect.arrayContaining(['[@media(max-width:24rem)]:h-auto', '[@media(max-width:24rem)]:min-h-10', '[@media(max-width:24rem)]:py-2', '[@media(max-width:24rem)]:whitespace-normal']))
    const own = buttonVariants({ size: 'md', className: 'min-h-11 py-3' })
    expect(narrow(own)).not.toEqual(expect.arrayContaining(['[@media(max-width:24rem)]:min-h-10']))
    expect(narrow(own)).not.toEqual(expect.arrayContaining(['[@media(max-width:24rem)]:py-2']))
    expect(narrow(own)).toEqual(expect.arrayContaining(['[@media(max-width:24rem)]:h-auto', '[@media(max-width:24rem)]:whitespace-normal']))
    expect(narrow(buttonVariants({ size: 'md', className: 'sm:py-3' }))).toEqual(expect.arrayContaining(['[@media(max-width:24rem)]:py-2']))
    render(<Button className="min-h-11">Open report</Button>)
    expect(screen.getByRole('button', { name: 'Open report' }).className.split(/\s+/)).not.toContain('[@media(max-width:24rem)]:min-h-10')
    expect(narrow(buttonVariants({ size: 'icon-sm', className: 'min-h-11' }))).toEqual([])
  })

  it('reserveLoadingText lays what shows over the loading state in one cell, the loading state invisible and hidden from assistive tech', () => {
    const { rerender } = render(<Button reserveLoadingText="Trying again…">Try again</Button>)
    const button = screen.getByRole('button', { name: 'Try again' })
    expect(button.children).toHaveLength(1)
    const cell = button.firstElementChild as HTMLElement
    expect(cell).toHaveClass('grid', 'place-items-center')
    const [shown, room] = [...cell.children] as HTMLElement[]
    expect(shown).toHaveClass('col-start-1', 'row-start-1', 'inline-flex')
    expect(shown).toHaveTextContent('Try again')
    // The room: the spinner's box at the button's size, then the loading label, laid out but never seen or read.
    expect(room).toHaveClass('invisible', 'col-start-1', 'row-start-1', 'inline-flex')
    expect(room).toHaveAttribute('aria-hidden', 'true')
    expect(room).toHaveTextContent('Trying again…')
    expect(room.firstElementChild).toHaveClass('inline-block', 'shrink-0', 'h-4', 'w-4')
    // Loading swaps what shows, in the same cell; the name follows it.
    rerender(<Button loading loadingText="Trying again…" reserveLoadingText="Trying again…">Try again</Button>)
    expect(screen.getByRole('button', { name: 'Trying again…' })).toBe(button)
    expect(button.firstElementChild).toBe(cell)
    expect(shown.querySelector('svg')).not.toBeNull()
    rerender(<Button size="sm" reserveLoadingText="Trying again…">Try again</Button>)
    expect(room.firstElementChild).toHaveClass('h-3', 'w-3')
    // Without it, a button's children are its own content, as before.
    rerender(<Button>Try again</Button>)
    expect(button.querySelector('[aria-hidden="true"]')).toBeNull()
    expect(button.firstElementChild).toBeNull()
  })

  // At 200% text a Retry in a cramped card (a Notice inside a card) is narrower than the spinner, the gap and
  // "again…": each row wraps, its label based at its longest word, so the spinner goes above the label only there,
  // and the room kept at rest is never wider than that word with the button's padding (#1380; the rendered case is
  // the company page's comparison card in tests/e2e/reflow-200.spec.ts).
  it('reserveLoadingText rows wrap, each label based at its longest word, so the spinner goes above it only where that word cannot sit beside it', () => {
    const { rerender } = render(<Button reserveLoadingText="Trying again…">Try again</Button>)
    const button = screen.getByRole('button', { name: 'Try again' })
    const [shown, room] = [...(button.firstElementChild as HTMLElement).children] as HTMLElement[]
    expect(shown.className).toBe(RESERVE_ROW)
    expect(room.className).toBe(`invisible ${RESERVE_ROW}`)
    for (const row of [shown, room]) expect(row).toHaveClass('inline-flex', 'flex-wrap', 'items-center', 'justify-center')
    const label = (row: HTMLElement) => [...row.children].find((child) => child.textContent?.trim()) as HTMLElement
    expect(label(shown)).toHaveTextContent('Try again')
    expect(label(room)).toHaveTextContent('Trying again…')
    for (const row of [shown, room]) expect(label(row).className).toBe(RESERVE_LABEL)
    expect(RESERVE_LABEL.split(' ')).toEqual(['grow', 'basis-[min-content]'])
    // Busy, the spinner and the loading label sit in the shown row as the room lays them out.
    rerender(<Button loading loadingText="Trying again…" reserveLoadingText="Trying again…">Try again</Button>)
    expect(shown.firstElementChild?.tagName.toLowerCase()).toBe('svg')
    expect(label(shown)).toHaveTextContent('Trying again…')
    expect(label(shown).className).toBe(RESERVE_LABEL)
  })
})
