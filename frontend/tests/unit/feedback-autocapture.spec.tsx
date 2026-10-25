import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { PostHog } from 'posthog-js'
import { afterEach, expect, it, vi } from 'vitest'
import { queryKeys } from '@/lib/queryKeys'
import FeedbackWidget from '@/features/feedback/components/FeedbackWidget'
import FeedbackRow from '@/features/admin/components/FeedbackRow'

vi.mock('@/features/admin/api/admin-api', () => ({ updateFeedbackStatus: vi.fn() }))
vi.mock('@/features/feedback/api/feedback-api', () => ({ submitFeedback: vi.fn() }))

let analytics: PostHog | undefined
afterEach(async () => {
  cleanup()
  await analytics?.shutdown()
  analytics = undefined
  vi.restoreAllMocks()
})

it('the real PostHog SDK captures ordinary controls but excludes feedback rows and portalled composer/details', () => {
  analytics = new PostHog()
  vi.spyOn(analytics, '_send_request').mockImplementation((request) => {
    request.callback?.({ statusCode: 200, json: {} })
  })
  const events: unknown[] = []
  analytics.on('eventCaptured', (event) => events.push(event))
  analytics.init('phc_synthetic_feedback_project', {
    api_host: 'https://example.invalid',
    autocapture: true, capture_pageview: false, capture_pageleave: false,
    disable_session_recording: true, disable_external_dependency_loading: true,
    request_batching: false, advanced_disable_flags: true,
    persistence: 'memory',
  })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  client.setQueryData(queryKeys.currentUser(), {
    id: 42, email: 'reader@example.test', full_name: null, is_pro: false,
    is_beta: true, is_admin: true, email_verified: true,
  })
  render(
    <QueryClientProvider client={client}>
      <button>Ordinary control</button>
      <FeedbackWidget />
      <table><tbody><FeedbackRow feedback={{
        id: 1, user_id: 42, user_email: 'reader@example.test', type: 'bug',
        message: 'Private report https://evidence.example.test/private-report',
        page_url: '/filing/123', status: 'new', created_at: '2026-10-25T00:00:00Z',
      }} /></tbody></table>
    </QueryClientProvider>,
  )
  fireEvent.click(screen.getByRole('button', { name: 'Ordinary control' }))
  expect(JSON.stringify(events)).toContain('$autocapture')

  fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
  events.length = 0
  const composer = screen.getByRole('dialog', { name: 'Send feedback' })
  fireEvent.input(within(composer).getByLabelText('Feedback message'), { target: { value: 'Private composer https://example.test/secret-note' } })
  fireEvent.click(within(composer).getByRole('button', { name: 'Bug' }))
  fireEvent.click(within(composer).getByRole('button', { name: 'Close' }))
  fireEvent.click(screen.getByRole('button', { name: 'View details for feedback 1' }))
  const details = screen.getByRole('dialog', { name: 'Feedback details' })
  const link = within(details).getByRole('link')
  link.addEventListener('click', (event) => event.preventDefault())
  fireEvent.click(link)
  fireEvent.click(within(details).getByRole('button', { name: 'Close' }))
  expect(events).toEqual([])
})
