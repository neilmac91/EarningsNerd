import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import FeedbackMessage from '@/features/feedback/components/FeedbackMessage'
import { LINK, LINK_NAME, checkSafeLink } from '../../../ops/feedback_media/live_browser.mjs'

// A Playwright-shaped view over the rendered DOM: getByRole finds by exact accessible name, as the suite asks.
function dom() {
  return {
    getByRole(role: string, { name, exact }: { name: string, exact: boolean }) {
      expect(exact).toBe(true)
      const element = screen.getByRole(role, { name })
      return { getAttribute: async (attribute: string) => element.getAttribute(attribute), textContent: async () => element.textContent }
    },
  }
}

// A locator that answers fixed attributes, to show which of them the check reads.
function answering(attributes: Record<string, string>, text: string) {
  return { getByRole: () => ({ getAttribute: async (attribute: string) => attributes[attribute] ?? null, textContent: async () => text }) }
}

// The live verification suite finds the admin view's link by its exact accessible name. If the name the component gives
// it, or the name the suite looks for, changes, this fails here rather than in a live run that strands a two-hour lease.
describe('the live verification suite and the feedback message', () => {
  it('names the message link exactly as live_browser.mjs looks for it', () => {
    render(<FeedbackMessage message={`Synthetic live feedback light.\n${LINK}`} />)
    const link = screen.getByRole('link', { name: LINK_NAME })
    expect(link.getAttribute('href')).toBe(LINK)
    expect(link.getAttribute('rel')).toBe('noopener noreferrer')
    expect(link.getAttribute('target')).toBe('_blank')
    expect(link.textContent).toBe(LINK)
  })

  it("passes the suite's own check against the rendered component", async () => {
    render(<FeedbackMessage message={`Synthetic live feedback light.\n${LINK}`} />)
    await expect(checkSafeLink(dom())).resolves.toBeUndefined()
  })

  it.each([
    ['another destination', { href: 'https://other.example.invalid/', rel: 'noopener noreferrer', target: '_blank' }, LINK],
    ['without noopener', { href: LINK, rel: 'noreferrer', target: '_blank' }, LINK],
    ['in the same tab', { href: LINK, rel: 'noopener noreferrer', target: '_self' }, LINK],
    ['with other text', { href: LINK, rel: 'noopener noreferrer', target: '_blank' }, 'Open the chart'],
  ])('refuses a link %s', async (_case, attributes, text) => {
    await expect(checkSafeLink(answering(attributes, text))).rejects.toThrow('admin-safe-link')
  })
})
