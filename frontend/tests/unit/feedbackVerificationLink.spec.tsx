import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import FeedbackMessage from '@/features/feedback/components/FeedbackMessage'
import { LINK, LINK_NAME } from '../../../ops/feedback_media/live_browser.mjs'

// The live verification suite finds the admin view's link by its exact accessible name. If the name the component gives
// it changes, this fails here rather than in a live run that strands a two-hour verification lease.
describe('the live verification suite and the feedback message', () => {
  it('names the message link exactly as live_browser.mjs looks for it', () => {
    render(<FeedbackMessage message={`Synthetic live feedback light.\n${LINK}`} />)
    const link = screen.getByRole('link', { name: LINK_NAME })
    expect(link.getAttribute('href')).toBe(LINK)
    expect(link.getAttribute('rel')).toBe('noopener noreferrer')
    expect(link.getAttribute('target')).toBe('_blank')
    expect(link.textContent).toBe(LINK)
  })
})
