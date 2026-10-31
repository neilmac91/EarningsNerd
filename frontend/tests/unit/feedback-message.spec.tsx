import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import FeedbackMessage from '@/features/feedback/components/FeedbackMessage'
import { feedbackTextParts } from '@/features/feedback/lib/feedbackLinks'

describe('feedback web links preserve literal messages', () => {
  it.each([
    ['See https://example.test/a?quarter=1#chart.', ['https://example.test/a?quarter=1#chart']],
    ['(https://example.test/filing_(2026)).', ['https://example.test/filing_(2026)']],
    ['[http://[::1]:8000/report].', ['http://[::1]:8000/report']],
    ['https://example.test/one\nHTTPS://example.test/two', ['https://example.test/one', 'https://example.test/two']],
    ['Read https://例え.テスト/決算?year=2026#資料', ['https://xn--r8jz45g.xn--zckzah/%E6%B1%BA%E7%AE%97?year=2026#%E8%B3%87%E6%96%99']],
  ])('recognizes explicit web URLs in %s without changing any text', (message, hrefs) => {
    const parts = feedbackTextParts(message)
    expect(parts.map((part) => part.text).join('')).toBe(message)
    expect(parts.flatMap((part) => part.href ? [part.href] : [])).toEqual(hrefs)
  })

  it.each([
    'javascript:alert(1)', 'data:text/html,hello', 'file:///etc/passwd', '//example.test',
    'javascript:https://example.test', 'abchttps://example.test',
    'https:///example.test', 'https://?missing-host', 'https://example.test:invalid',
    'https://user:password@example.test', 'https://%75ser@example.test', 'https://@example.test',
    'https://example.test\\@other.test', 'https://exam\tple.test', 'https://example.test/\u0000path',
    'https://example.test/\u007fpath', 'https://example.test/\u0085path',
    'https://example.test/\u202epath', 'https://example.test/\u200bpath',
  ])('keeps an unsafe or malformed destination as text: %s', (message) => {
    expect(feedbackTextParts(message)).toEqual([{ text: message }])
  })

  it('renders HTML and Markdown literally, with no embedded media or nested controls', () => {
    const message = '<img src="https://example.test/image.png" onerror="alert(1)">\n**broken** [report](https://example.test/report)'
    const { container } = render(<FeedbackMessage message={message} />)
    expect(container.textContent).toBe(message)
    expect(container.querySelector('img,script,iframe,strong,button')).toBeNull()
    const links = screen.getAllByRole('link')
    expect(links.map((link) => link.getAttribute('href'))).toEqual(['https://example.test/image.png', 'https://example.test/report'])
    for (const link of links) {
      expect(link).toHaveAttribute('target', '_blank')
      expect(link).toHaveAttribute('rel', 'noopener noreferrer')
      expect(link).not.toHaveAttribute('title')
    }
    // Rendering alone produces only inert text and anchors: no resource or prefetch elements.
    expect(container.querySelector('link,video,audio,source,embed,object')).toBeNull()
  })
})
