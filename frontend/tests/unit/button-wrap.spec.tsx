import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Button, buttonVariants, type ButtonSize } from '@/components/ui/Button'

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
})
