import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider, onlineManager } from '@tanstack/react-query'
import ContactForm from '@/features/contact/components/ContactForm'
import FeedbackWidget from '@/features/feedback/components/FeedbackWidget'
import WaitlistForm from '@/features/waitlist/components/WaitlistForm'
import PricingPage from '@/app/pricing/page'
import { queryKeys } from '@/lib/queryKeys'
import { ApiError } from '@/lib/api/client'
import { advanceSessionGeneration } from '@/lib/api/session'
import type { CurrentUser } from '@/features/auth/api/auth-api'
import type { SubscriptionStatus, Usage } from '@/features/subscriptions/api/subscriptions-api'

/**
 * Public/app forms keep keyboard focus while their own submit is in flight. The submit Button is
 * `loading` (aria-busy + aria-disabled + click guard) and the contact fields are readOnly — never
 * natively `disabled`: Chromium blurs a focused control that turns `disabled` to <body>, including
 * the field a user pressed Enter in. jsdom does not blur disabled elements, so these specs pin the
 * attributes, that focus is never moved off the control, and that a second activation (click,
 * Enter in a field, a direct submit) sends no second request.
 */

const api = vi.hoisted(() => ({
  submitContactForm: vi.fn(),
  submitFeedback: vi.fn(),
  getFeedbackCapabilities: vi.fn(),
  getFeedbackSubmission: vi.fn(),
  joinWaitlist: vi.fn(),
  getCurrentUserSafe: vi.fn(),
  // The pricing page reads the public registration gate for its guest CTA; public here keeps the
  // Retry cases below about the account, subscription and usage queries only.
  getRegistrationConfig: vi.fn(async () => ({ mode: 'public' as const, beta_promo_enabled: false })),
  getSubscriptionStatus: vi.fn(),
  getUsage: vi.fn(),
  createCheckoutSession: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}))
vi.mock('@/features/contact/api/contact-api', () => ({ submitContactForm: api.submitContactForm }))
vi.mock('@/features/feedback/api/feedback-api', () => ({ submitFeedback: api.submitFeedback, getFeedbackCapabilities: api.getFeedbackCapabilities, getFeedbackSubmission: api.getFeedbackSubmission }))
vi.mock('@/features/waitlist/api/waitlist-api', () => ({ joinWaitlist: api.joinWaitlist }))
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: api.getCurrentUserSafe }))
vi.mock('@/features/marketing/api/access-api', () => ({ getRegistrationConfig: api.getRegistrationConfig }))
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({
  getSubscriptionStatus: api.getSubscriptionStatus,
  getUsage: api.getUsage,
  createCheckoutSession: api.createCheckoutSession,
}))
const nav = vi.hoisted(() => ({ router: { push: () => {}, refresh: () => {} }, searchParams: new URLSearchParams() }))
vi.mock('next/navigation', () => ({ useRouter: () => nav.router, useSearchParams: () => nav.searchParams }))
vi.mock('posthog-js/react', () => ({ useFeatureFlagVariantKey: () => undefined }))
vi.mock('posthog-js', () => ({ default: { capture: () => {} } }))
vi.mock('@/lib/analytics', () => ({
  default: { pricingViewed: () => {}, billingCycleToggled: () => {}, checkoutStarted: () => {} },
}))
vi.mock('sonner', () => ({ toast: { success: api.toastSuccess, error: api.toastError } }))
vi.mock('@/lib/api/session', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api/session')>()),
  hasActiveSession: () => true,
}))
// Deterministic flags: no Turnstile gate (each form's wait for a token is aria-disabled, held for the sign-in, register
// and contact forms in turnstileRenewal.spec.tsx and for the waitlist in waitlistSuccessCard.spec.tsx), and the
// feedback launcher on.
vi.mock('@/lib/featureFlags', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/featureFlags')>()),
  TURNSTILE_SITE_KEY: '',
  TURNSTILE_ENABLED: false,
  ENABLE_FEEDBACK_WIDGET: true,
}))

const deferred = <T,>() => {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

/** Let any re-entrant submit reach its request before counting requests. */
const settle = () => act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) })

/** In flight: announced busy + unavailable, still focusable, and still the focused element. */
/** Busy is announced (aria-busy + aria-disabled) and the control keeps focus. That a busy flag
    never turns it natively disabled is the rule-12 gate's job (busyControlsStayFocusable.spec.ts). */
function expectBusyAndFocused(control: HTMLElement) {
  expect(control).toHaveAttribute('aria-busy', 'true')
  expect(control).toHaveAttribute('aria-disabled', 'true')
  expect(document.activeElement).toBe(control)
}

beforeEach(() => {
  sessionStorage.clear()
  api.getFeedbackCapabilities.mockResolvedValue({ attachments_enabled: false })
  api.getFeedbackSubmission.mockImplementation(async (key: string) => ({ submission_id: key, state: 'retryable', retry_after_seconds: null, feedback: null }))
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:feedback-test') })
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
})

afterEach(() => {
  cleanup()
  Object.values(api).forEach((mock) => mock.mockReset())
})

describe('ContactForm', () => {
  function fill() {
    fireEvent.change(screen.getByLabelText(/^Name/), { target: { value: 'Ada Lovelace' } })
    fireEvent.change(screen.getByLabelText(/^Email/), { target: { value: 'ada@example.test' } })
    fireEvent.change(screen.getByLabelText('Subject'), { target: { value: 'Hello' } })
    fireEvent.change(screen.getByLabelText(/^Message/), { target: { value: 'A message long enough.' } })
  }

  it('Send keeps focus through its request and settle, and refuses a repeat click or submit', async () => {
    const post = deferred<unknown>()
    api.submitContactForm.mockReturnValue(post.promise)
    render(<ContactForm />)
    fill()

    const send = screen.getByRole('button', { name: 'Send message' })
    const form = send.closest('form')!
    send.focus()
    fireEvent.click(send)
    await waitFor(() => expect(send).toHaveTextContent('Sending…'))
    expectBusyAndFocused(send)
    fireEvent.click(send)
    fireEvent.submit(form) // Enter in a field while the request is in flight
    await settle()
    expect(api.submitContactForm).toHaveBeenCalledTimes(1)
    expect(document.activeElement).toBe(send)

    await act(async () => post.reject(new ApiError(503, 'Server unavailable')))
    expect(await screen.findByText("We couldn't send your message. Try again in a minute.")).toBeInTheDocument()
    expect(send).toHaveTextContent('Send message')
    expect(send).not.toHaveAttribute('aria-disabled')
    expect(send).not.toHaveAttribute('aria-busy')
    expect(send).not.toBeDisabled()
    expect(document.activeElement).toBe(send)
  })

  it('a successful send hands focus to "Message sent", and "Send another message" hands it to Name', async () => {
    api.submitContactForm.mockResolvedValue({})
    render(<ContactForm />)
    fill()

    // The success panel replaces the form, and the focused Send with it: focus must not stay on <body>.
    const send = screen.getByRole('button', { name: 'Send message' })
    send.focus()
    fireEvent.click(send)
    const heading = await screen.findByRole('heading', { name: 'Message sent' })
    expect(send.isConnected).toBe(false)
    expect(document.activeElement).toBe(heading)

    // 'Send another message' unmounts itself as the form comes back.
    const again = screen.getByRole('button', { name: 'Send another message' })
    again.focus()
    fireEvent.click(again)
    await waitFor(() => expect(again.isConnected).toBe(false))
    expect(document.activeElement).toBe(screen.getByLabelText(/^Name/))
  })

  it('a field submitted with Enter stays focused and readOnly (not disabled), and a second Enter sends nothing', async () => {
    const post = deferred<unknown>()
    api.submitContactForm.mockReturnValue(post.promise)
    const user = userEvent.setup()
    render(<ContactForm />)
    fill()

    const name = screen.getByLabelText(/^Name/)
    const send = screen.getByRole('button', { name: 'Send message' })
    const form = send.closest('form')!
    name.focus()
    await user.keyboard('{Enter}')
    await waitFor(() => expect(send).toHaveAttribute('aria-busy', 'true'))
    expect(api.submitContactForm).toHaveBeenCalledTimes(1)

    // Every field holds its value read-only while the form sends (that a busy flag never disables it
    // is the rule-12 gate's job).
    for (const field of [name, screen.getByLabelText(/^Email/), screen.getByLabelText('Subject'), screen.getByLabelText(/^Message/)]) {
      expect(field).toHaveAttribute('readonly')
    }
    expect(document.activeElement).toBe(name)
    await user.type(name, 'x', { skipClick: true })
    expect(name).toHaveValue('Ada Lovelace')

    await user.keyboard('{Enter}')
    fireEvent.submit(form)
    await settle()
    expect(api.submitContactForm).toHaveBeenCalledTimes(1)
    expect(document.activeElement).toBe(name)

    await act(async () => post.reject(new ApiError(503, 'Server unavailable')))
    expect(await screen.findByText("We couldn't send your message. Try again in a minute.")).toBeInTheDocument()
    expect(name).not.toHaveAttribute('readonly')
    expect(document.activeElement).toBe(name)
  })
})

describe('FeedbackWidget', () => {
  const reader = (id: number): CurrentUser => ({
    id, email: `${id}@example.test`, full_name: null, is_pro: false,
    is_beta: true, is_admin: false, email_verified: true,
  })
  function mountFeedback(user: CurrentUser | null | undefined = reader(1)) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } })
    if (user !== undefined) client.setQueryData(queryKeys.currentUser(), user)
    render(<QueryClientProvider client={client}><FeedbackWidget /></QueryClientProvider>)
    return client
  }

  it('Send keeps focus through its request and settle, and refuses a repeat click or submit', async () => {
    const post = deferred<unknown>()
    api.submitFeedback.mockReturnValue(post.promise)
    mountFeedback()

    fireEvent.click(await screen.findByRole('button', { name: 'Send feedback' }))
    const message = await screen.findByLabelText('Feedback message')
    expect(message).toHaveAccessibleDescription('Describe what happened. You can paste a web link here too.')
    expect(message.closest('[role="dialog"]')).toHaveClass('ph-no-capture')
    const send = screen.getByRole('button', { name: 'Send feedback' })
    // Too short is a kept availability state: set by the textarea, never by Send's own activation.
    expect(send).toBeDisabled()
    fireEvent.change(message, { target: { value: 'The chart is off by one.' } })
    expect(send).not.toBeDisabled()

    const form = send.closest('form')!
    send.focus()
    fireEvent.click(send)
    await waitFor(() => expect(send).toHaveTextContent('Sending…'))
    expectBusyAndFocused(send)
    fireEvent.click(send)
    fireEvent.submit(form)
    await settle()
    expect(api.submitFeedback).toHaveBeenCalledTimes(1)
    expect(document.activeElement).toBe(send)

    await act(async () => post.reject(new Error('offline')))
    await waitFor(() => expect(api.toastError).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(send).toHaveTextContent('Send feedback'))
    expect(send).not.toHaveAttribute('aria-disabled')
    expect(send).not.toHaveAttribute('aria-busy')
    expect(send).not.toBeDisabled()
    expect(document.activeElement).toBe(send)
    expect(message).toHaveValue('The chart is off by one.')
  })

  it('keeps screenshot bytes local, preserves mixed paste, and removes a selected file with focus hand-off', async () => {
    api.getFeedbackCapabilities.mockResolvedValue({ attachments_enabled: true })
    mountFeedback()
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    await screen.findByRole('button', { name: 'Add screenshots' })
    const image = new File(['image'], 'private-account.png', { type: 'image/png' })
    fireEvent.change(screen.getByLabelText('Screenshot files'), { target: { files: [image] } })
    expect(screen.getByText('private-account.png')).toBeInTheDocument()
    expect(api.submitFeedback).not.toHaveBeenCalled()
    const text = screen.getByLabelText('Feedback message')
    const pasted = fireEvent.paste(text, { clipboardData: {
      items: [{ kind: 'file', getAsFile: () => new File(['second'], 'paste.png', { type: 'image/png' }) }],
      getData: () => 'A note with https://example.test',
    } })
    expect(pasted).toBe(true) // native text paste was not prevented or replaced
    expect(screen.getAllByRole('img')).toHaveLength(2)
    const remove = screen.getByRole('button', { name: 'Remove screenshot 1' })
    remove.focus()
    fireEvent.click(remove)
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:feedback-test')
    expect(screen.queryByText('private-account.png')).not.toBeInTheDocument()
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Add screenshots' }))
  })

  it('freezes the complete upload snapshot, closes without cancelling, and checks an uncertain receipt before reusing the key', async () => {
    api.getFeedbackCapabilities.mockResolvedValue({ attachments_enabled: true })
    api.getFeedbackSubmission.mockImplementation(async (key: string) => ({ submission_id: key, state: 'not_found', retry_after_seconds: null, feedback: null }))
    const post = deferred<unknown>()
    const second = deferred<unknown>()
    api.submitFeedback.mockReturnValueOnce(post.promise).mockReturnValueOnce(second.promise)
    mountFeedback()
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    await screen.findByRole('button', { name: 'Add screenshots' })
    const image = new File(['image'], 'private.png', { type: 'image/png' })
    fireEvent.change(screen.getByLabelText('Screenshot files'), { target: { files: [image] } })
    fireEvent.change(screen.getByLabelText('Feedback message'), { target: { value: 'Screenshot explains this problem' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    const [input, options] = api.submitFeedback.mock.calls[0]
    expect(options.files).toEqual([image])
    expect(screen.getByLabelText('Feedback message')).toHaveAttribute('readonly')
    fireEvent.change(screen.getByLabelText('Feedback message'), { target: { value: 'Must not replace snapshot' } })
    expect(screen.getByLabelText('Feedback message')).toHaveValue(input.message)
    act(() => options.onUploadProgress(100))
    expect(screen.getByRole('button', { name: 'Saving…' })).toHaveAttribute('aria-busy', 'true')
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    expect(screen.getByRole('button', { name: 'Saving…' })).toHaveAttribute('aria-busy', 'true')
    await act(async () => post.reject(new ApiError(0, 'network interrupted')))
    await screen.findByText('We could not confirm the submission. Send this same draft again to check it safely.')
    expect(api.getFeedbackSubmission).toHaveBeenCalledWith(options.submissionId, expect.any(AbortSignal))
    expect(JSON.parse(sessionStorage.getItem('en_feedback_pending')!)).toEqual({ owner: 1, key: options.submissionId })
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    act(() => {
      api.submitFeedback.mock.calls[1][1].onUploadProgress(20)
      options.onUploadProgress(100) // a stale progress event from the first transport
    })
    expect(screen.getByRole('progressbar', { name: 'Screenshot upload' })).toHaveAttribute('value', '20')
    await act(async () => second.resolve({ id: 7 }))
    await waitFor(() => expect(api.toastSuccess).toHaveBeenCalledTimes(1))
    expect(api.submitFeedback.mock.calls[1][0]).toEqual(input)
    expect(api.submitFeedback.mock.calls[1][1]).toMatchObject({ submissionId: options.submissionId, files: [image], readerId: 1 })
    expect(sessionStorage.getItem('en_feedback_pending')).toBeNull()
    expect(URL.revokeObjectURL).toHaveBeenCalled()
  })

  it('keeps an uncertain submission identity when a later resend is rejected before the earlier attempt settles', async () => {
    const receipt = deferred<unknown>()
    api.submitFeedback.mockRejectedValueOnce(new ApiError(0, 'network interrupted'))
    api.submitFeedback.mockRejectedValueOnce(new ApiError(429, 'Please wait.'))
    api.getFeedbackSubmission.mockImplementationOnce(async (key: string) => ({ submission_id: key, state: 'not_found', retry_after_seconds: null, feedback: null }))
    api.getFeedbackSubmission.mockReturnValueOnce(receipt.promise)
    mountFeedback()
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    fireEvent.change(screen.getByLabelText('Feedback message'), { target: { value: 'An uncertain original submission' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    await screen.findByText('We could not confirm the submission. Send this same draft again to check it safely.')
    const key = api.submitFeedback.mock.calls[0][1].submissionId
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    await waitFor(() => expect(api.getFeedbackSubmission).toHaveBeenCalledTimes(2))
    expect(JSON.parse(sessionStorage.getItem('en_feedback_pending')!).key).toBe(key)
    expect(screen.getByLabelText('Feedback message')).toHaveAttribute('readonly')
    fireEvent.submit(screen.getByRole('button', { name: 'Checking…' }).closest('form')!)
    expect(api.submitFeedback).toHaveBeenCalledTimes(2)
    await act(async () => receipt.resolve({ submission_id: key, state: 'submitted', retry_after_seconds: null, feedback: { id: 11 } }))
    await waitFor(() => expect(api.toastSuccess).toHaveBeenCalledTimes(1))
    expect(api.submitFeedback.mock.calls[1][1].submissionId).toBe(key)
    expect(sessionStorage.getItem('en_feedback_pending')).toBeNull()
  })

  it('restarts a receipt check under a retained reader’s new session generation and ignores its old answer', async () => {
    const oldReceipt = deferred<unknown>()
    const freshReceipt = deferred<unknown>()
    api.getFeedbackCapabilities.mockResolvedValue({ attachments_enabled: true })
    api.submitFeedback.mockRejectedValueOnce(new ApiError(0, 'network interrupted'))
    api.getFeedbackSubmission.mockReturnValueOnce(oldReceipt.promise).mockReturnValueOnce(freshReceipt.promise)
    mountFeedback()
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    await screen.findByRole('button', { name: 'Add screenshots' })
    fireEvent.change(screen.getByLabelText('Screenshot files'), { target: { files: [new File(['private'], 'retained.png', { type: 'image/png' })] } })
    fireEvent.change(screen.getByLabelText('Feedback message'), { target: { value: 'Keep this screenshot through a failed logout' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    await waitFor(() => expect(api.getFeedbackSubmission).toHaveBeenCalledTimes(1))
    const key = api.submitFeedback.mock.calls[0][1].submissionId
    advanceSessionGeneration()
    await act(async () => oldReceipt.resolve({ submission_id: key, state: 'submitted', retry_after_seconds: null, feedback: { id: 12 } }))
    await waitFor(() => expect(api.getFeedbackSubmission).toHaveBeenCalledTimes(2))
    expect(api.toastSuccess).not.toHaveBeenCalled()
    expect(screen.getByText('retained.png')).toBeInTheDocument()
    expect(screen.getByLabelText('Feedback message')).toHaveValue('Keep this screenshot through a failed logout')
    expect(JSON.parse(sessionStorage.getItem('en_feedback_pending')!).key).toBe(key)
    await act(async () => freshReceipt.resolve({ submission_id: key, state: 'submitted', retry_after_seconds: null, feedback: { id: 12 } }))
    await waitFor(() => expect(api.toastSuccess).toHaveBeenCalledTimes(1))
    expect(api.submitFeedback).toHaveBeenCalledTimes(1)
    expect(sessionStorage.getItem('en_feedback_pending')).toBeNull()
  })

  it('releases a reconstructed conflicting draft only after the older receipt is fenced as retryable', async () => {
    const key = '00000000-0000-4000-8000-000000000001'
    sessionStorage.setItem('en_feedback_pending', JSON.stringify({ owner: 1, key }))
    api.getFeedbackSubmission.mockImplementationOnce(async () => ({ submission_id: key, state: 'not_found', retry_after_seconds: null, feedback: null }))
    api.submitFeedback.mockRejectedValueOnce(new ApiError(409, 'Submission differs.'))
    api.submitFeedback.mockReturnValueOnce(new Promise(() => {}))
    mountFeedback()
    await waitFor(() => expect(api.getFeedbackSubmission).toHaveBeenCalledTimes(1))
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    await screen.findByText('We could not confirm your earlier submission. Re-enter the note and select the screenshots; we will check the same submission.')
    fireEvent.change(screen.getByLabelText('Feedback message'), { target: { value: 'A reconstructed different note' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    await screen.findByText('Your earlier feedback was not saved. Your current draft is ready to send.')
    expect(screen.getByLabelText('Feedback message')).toHaveValue('A reconstructed different note')
    expect(screen.getByLabelText('Feedback message')).not.toHaveAttribute('readonly')
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    expect(api.submitFeedback.mock.calls[0][1].submissionId).toBe(key)
    expect(api.submitFeedback.mock.calls[1][1].submissionId).not.toBe(key)
  })

  it('starts a fresh submission after an image validation rejection and allows the rejected draft to be corrected', async () => {
    api.getFeedbackCapabilities.mockResolvedValue({ attachments_enabled: true })
    api.submitFeedback.mockRejectedValueOnce(new ApiError(422, 'Crop this screenshot and try again.'))
    api.submitFeedback.mockReturnValueOnce(new Promise(() => {}))
    mountFeedback()
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    await screen.findByRole('button', { name: 'Add screenshots' })
    const original = new File(['large image'], 'original.png', { type: 'image/png' })
    fireEvent.change(screen.getByLabelText('Screenshot files'), { target: { files: [original] } })
    fireEvent.change(screen.getByLabelText('Feedback message'), { target: { value: 'The original screenshot' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    await screen.findByText('Crop this screenshot and try again.')
    expect(screen.getByLabelText('Feedback message')).not.toHaveAttribute('readonly')
    expect(sessionStorage.getItem('en_feedback_pending')).toBeNull()
    expect(api.getFeedbackSubmission).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Remove screenshot 1' }))
    const cropped = new File(['cropped image'], 'cropped.png', { type: 'image/png' })
    fireEvent.change(screen.getByLabelText('Screenshot files'), { target: { files: [cropped] } })
    fireEvent.change(screen.getByLabelText('Feedback message'), { target: { value: 'A corrected screenshot and note' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    expect(api.submitFeedback.mock.calls[1][1].submissionId).not.toBe(api.submitFeedback.mock.calls[0][1].submissionId)
    expect(api.submitFeedback.mock.calls[1][1].files).toEqual([cropped])
    expect(api.submitFeedback.mock.calls[1][0].message).toBe('A corrected screenshot and note')
  })

  it('clears selected images on an account switch and ignores old upload progress and receipt', async () => {
    api.getFeedbackCapabilities.mockResolvedValue({ attachments_enabled: true })
    const post = deferred<unknown>()
    api.submitFeedback.mockReturnValue(post.promise)
    const client = mountFeedback()
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    await screen.findByRole('button', { name: 'Add screenshots' })
    fireEvent.change(screen.getByLabelText('Screenshot files'), { target: { files: [new File(['private'], 'A-only.png', { type: 'image/png' })] } })
    fireEvent.change(screen.getByLabelText('Feedback message'), { target: { value: 'Private A screenshot' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    const options = api.submitFeedback.mock.calls[0][1]
    act(() => client.setQueryData(queryKeys.currentUser(), reader(2)))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(URL.revokeObjectURL).toHaveBeenCalled()
    expect(sessionStorage.getItem('en_feedback_pending')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    act(() => options.onUploadProgress(100))
    await act(async () => post.resolve({ id: 8 }))
    expect(screen.getByLabelText('Feedback message')).toHaveValue('')
    expect(screen.queryByText('A-only.png')).not.toBeInTheDocument()
    expect(api.toastSuccess).not.toHaveBeenCalled()
  })

  it('recovers a saved receipt after reload without persisting note text or sending again', async () => {
    sessionStorage.setItem('en_feedback_pending', JSON.stringify({ owner: 1, key: '00000000-0000-4000-8000-000000000001' }))
    api.getFeedbackSubmission.mockResolvedValue({ submission_id: '00000000-0000-4000-8000-000000000001', state: 'submitted', retry_after_seconds: null, feedback: { id: 9 } })
    mountFeedback()
    await waitFor(() => expect(api.toastSuccess).toHaveBeenCalledTimes(1))
    expect(api.submitFeedback).not.toHaveBeenCalled()
    expect(sessionStorage.getItem('en_feedback_pending')).toBeNull()
  })

  it('follows login and logout without remounting, and never carries a draft between readers', async () => {
    // hasActiveSession is true in this harness: the advisory marker alone must not show feedback.
    const client = mountFeedback(null)
    expect(screen.queryByRole('button', { name: 'Send feedback' })).not.toBeInTheDocument()
    act(() => client.setQueryData(queryKeys.currentUser(), reader(1)))
    fireEvent.click(await screen.findByRole('button', { name: 'Send feedback' }))
    fireEvent.change(screen.getByLabelText('Feedback message'), { target: { value: 'Private note from A' } })

    act(() => client.setQueryData(queryKeys.currentUser(), reader(2)))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    expect(screen.getByLabelText('Feedback message')).toHaveValue('')
    fireEvent.change(screen.getByLabelText('Feedback message'), { target: { value: 'Private note from B' } })

    act(() => client.setQueryData(queryKeys.currentUser(), null))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'Send feedback' })).not.toBeInTheDocument()
    act(() => client.setQueryData(queryKeys.currentUser(), reader(1)))
    fireEvent.click(await screen.findByRole('button', { name: 'Send feedback' }))
    expect(screen.getByLabelText('Feedback message')).toHaveValue('')
  })

  it('waits for identity and keeps the known reader and draft when a background identity read fails', async () => {
    const identity = deferred<CurrentUser>()
    api.getCurrentUserSafe.mockReturnValue(identity.promise)
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } })
    render(<QueryClientProvider client={client}><FeedbackWidget /></QueryClientProvider>)
    expect(screen.queryByRole('button', { name: 'Send feedback' })).not.toBeInTheDocument()
    await act(async () => identity.resolve(reader(1)))
    fireEvent.click(await screen.findByRole('button', { name: 'Send feedback' }))
    const message = screen.getByLabelText('Feedback message')
    fireEvent.change(message, { target: { value: 'Keep this draft through a network outage' } })
    api.getCurrentUserSafe.mockRejectedValue(new Error('offline'))
    await act(async () => { await client.invalidateQueries({ queryKey: queryKeys.currentUser() }) })
    expect(client.getQueryState(queryKeys.currentUser())?.status).toBe('error')
    expect(message).toHaveValue('Keep this draft through a network outage')
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it.each(['success', 'failure'] as const)('a late A %s cannot close, clear or release B’s pending feedback', async (outcome) => {
    const a = deferred<unknown>()
    const b = deferred<unknown>()
    api.submitFeedback.mockReturnValueOnce(a.promise).mockReturnValueOnce(b.promise)
    const client = mountFeedback()
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    fireEvent.change(screen.getByLabelText('Feedback message'), { target: { value: 'A private draft' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    // /me may discover a different reader without an in-tab generation change.
    act(() => client.setQueryData(queryKeys.currentUser(), reader(2)))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    fireEvent.change(screen.getByLabelText('Feedback message'), { target: { value: 'B private draft' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    await act(async () => outcome === 'success' ? a.resolve({}) : a.reject(new Error('offline')))
    expect(api.toastSuccess).not.toHaveBeenCalled()
    expect(api.toastError).not.toHaveBeenCalled()
    expect(screen.getByLabelText('Feedback message')).toHaveValue('B private draft')
    expect(screen.getByRole('button', { name: 'Sending…' })).toHaveAttribute('aria-busy', 'true')
    await act(async () => b.resolve({}))
    expect(api.toastSuccess).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('refuses dispatch after the cache reader changes, even before React renders that change', () => {
    const client = mountFeedback()
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    fireEvent.change(screen.getByLabelText('Feedback message'), { target: { value: 'A private draft' } })
    const form = screen.getByRole('button', { name: 'Send feedback' }).closest('form')!
    act(() => {
      client.setQueryData(queryKeys.currentUser(), reader(2))
      fireEvent.submit(form)
    })
    expect(api.submitFeedback).not.toHaveBeenCalled()
  })

  it('ignores a superseded session result without discarding a retained same-reader draft', async () => {
    const post = deferred<unknown>()
    api.submitFeedback.mockReturnValueOnce(post.promise).mockResolvedValueOnce({})
    mountFeedback()
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    fireEvent.change(screen.getByLabelText('Feedback message'), { target: { value: 'Retained after failed logout' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    advanceSessionGeneration()
    await act(async () => post.resolve({}))
    expect(api.toastSuccess).not.toHaveBeenCalled()
    expect(screen.getByLabelText('Feedback message')).toHaveValue('Retained after failed logout')
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    await waitFor(() => expect(api.toastSuccess).toHaveBeenCalledTimes(1))
  })
})

describe('WaitlistForm (already `loading` + submit guard — pinned so it cannot regress)', () => {
  it('Join keeps focus through its request and settle, and refuses a repeat click or submit', async () => {
    const post = deferred<unknown>()
    api.joinWaitlist.mockReturnValue(post.promise)
    render(<WaitlistForm />)
    fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'ada@example.test' } })

    const join = screen.getByRole('button', { name: 'Join the waitlist' })
    const form = join.closest('form')!
    join.focus()
    fireEvent.click(join)
    await waitFor(() => expect(join).toHaveTextContent('Joining waitlist...'))
    expectBusyAndFocused(join)
    fireEvent.click(join)
    fireEvent.submit(form)
    await settle()
    expect(api.joinWaitlist).toHaveBeenCalledTimes(1)

    await act(async () => post.reject(new Error('offline')))
    expect(await screen.findByText('Network error. Please try again in a moment.')).toBeInTheDocument()
    expect(join).not.toHaveAttribute('aria-disabled')
    expect(join).not.toBeDisabled()
    expect(document.activeElement).toBe(join)
  })
})

describe('Pricing page Retry buttons (a failure keeps its Notice through any refetch until data replaces it)', () => {
  // Every Retry reads the one verb (D-032), so a case is named for the read it retries: the account Notice's
  // Retry, or the details Notice's one Retry over the subscription and usage reads.
  afterEach(() => onlineManager.setOnline(true))
  const user1 = { id: 1, email: 'ada@example.test' }
  const freeSub: SubscriptionStatus = {
    is_pro: false,
    stripe_customer_id: null,
    stripe_subscription_id: null,
    subscription_status: null,
    plan: 'free',
    status: null,
    trial_end: null,
    current_period_end: null,
    cancel_at_period_end: false,
  }
  const usage = { summaries_used: 1, summaries_limit: 5, is_pro: false, month: '2026-10' } as Usage

  function renderPricing() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <PricingPage />
      </QueryClientProvider>,
    )
    return client
  }

  const intro = () => screen.getByText(/Summaries are generated once per filing and shared/)

  const cases = [
    {
      name: 'the account check',
      request: api.getCurrentUserSafe,
      key: queryKeys.currentUser(),
      message: 'network down',
      // Identity failed with no data; subscription and usage never ran.
      arrange: () => {
        api.getCurrentUserSafe.mockRejectedValueOnce(new Error('network down'))
        api.getSubscriptionStatus.mockResolvedValue(freeSub)
        api.getUsage.mockResolvedValue(usage)
      },
      success: user1 as unknown,
    },
    {
      name: 'the subscription read',
      request: api.getSubscriptionStatus,
      key: queryKeys.subscription.byUser(1),
      message: 'subscription unavailable',
      // Initial subscription read failed with no data; usage is fine.
      arrange: () => {
        api.getCurrentUserSafe.mockResolvedValue(user1)
        api.getSubscriptionStatus.mockRejectedValueOnce(new Error('subscription unavailable'))
        api.getUsage.mockResolvedValue(usage)
      },
      success: freeSub as unknown,
    },
    {
      name: 'the usage read',
      request: api.getUsage,
      key: queryKeys.usage.byUser(1),
      message: 'usage unavailable',
      // Initial usage read failed with no data; the subscription is fine.
      arrange: () => {
        api.getCurrentUserSafe.mockResolvedValue(user1)
        api.getSubscriptionStatus.mockResolvedValue(freeSub)
        api.getUsage.mockRejectedValueOnce(new Error('usage unavailable'))
      },
      success: usage as unknown,
    },
  ]

  // React Query puts a query with no data back to `pending` (error: null) the moment it refetches.
  // The Notice must not read that as "no longer failed": unmounting it removes the focused Retry
  // button before its `loading` renders, and focus falls to <body>.
  it.each(cases)('the Retry of $name keeps focus through its retry and a failed settle, and lands on the intro once it succeeds', async ({ request, message, arrange, success }) => {
    const user = userEvent.setup()
    arrange()
    renderPricing()

    const retry = await screen.findByRole('button', { name: 'Try again' })
    expect(screen.getByText(message)).toBeInTheDocument()
    const first = deferred<unknown>()
    request.mockReturnValueOnce(first.promise)
    retry.focus()
    await user.keyboard('{Enter}')
    await waitFor(() => expect(request).toHaveBeenCalledTimes(2))

    // In flight: the same button, still in the document, busy and focused; the Notice keeps its copy.
    expect(retry.isConnected).toBe(true)
    expectBusyAndFocused(retry)
    expect(screen.getByText(message)).toBeInTheDocument()
    await user.keyboard('{Enter}')
    fireEvent.click(retry)
    await settle()
    expect(request).toHaveBeenCalledTimes(2)

    // A failed retry settles with the Notice and the focused button in place.
    await act(async () => first.reject(new Error('still down')))
    expect(await screen.findByText('still down')).toBeInTheDocument()
    expect(retry.isConnected).toBe(true)
    expect(retry).not.toHaveAttribute('aria-busy')
    expect(retry).not.toHaveAttribute('aria-disabled')
    expect(document.activeElement).toBe(retry)

    // A successful retry removes the Notice; focus lands on the intro line above it, not <body>.
    request.mockResolvedValue(success)
    await user.keyboard('{Enter}')
    await waitFor(() => expect(retry.isConnected).toBe(false))
    expect(request).toHaveBeenCalledTimes(3)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(document.activeElement).toBe(intro())
  })

  it('a retry that succeeds while focus has moved on leaves focus where the user put it', async () => {
    api.getCurrentUserSafe.mockResolvedValue(user1)
    api.getSubscriptionStatus.mockRejectedValueOnce(new Error('subscription unavailable'))
    api.getUsage.mockResolvedValue(usage)
    renderPricing()

    const retry = await screen.findByRole('button', { name: 'Try again' })
    const pending = deferred<unknown>()
    api.getSubscriptionStatus.mockReturnValueOnce(pending.promise)
    fireEvent.click(retry)
    await waitFor(() => expect(retry).toHaveAttribute('aria-busy', 'true'))
    const toggle = screen.getByRole('switch', { name: /^yearly/i })
    toggle.focus()

    await act(async () => pending.resolve(freeSub))
    await waitFor(() => expect(retry.isConnected).toBe(false))
    expect(document.activeElement).toBe(toggle)
  })

  it('a refetch nobody pressed keeps the Notice and a focused Retry, busy, then hands focus to the intro when it lands', async () => {
    api.getCurrentUserSafe.mockResolvedValue(user1)
    api.getSubscriptionStatus.mockRejectedValueOnce(new Error('subscription unavailable'))
    api.getUsage.mockResolvedValue(usage)
    const client = renderPricing()
    const retry = await screen.findByRole('button', { name: 'Try again' })
    retry.focus()

    // A refetch nobody pressed (reconnect, window focus, an invalidation) puts the data-less query back
    // to pending. The failure stays shown until data replaces it, so the focused Retry is not unmounted.
    const background = deferred<unknown>()
    api.getSubscriptionStatus.mockReturnValueOnce(background.promise)
    act(() => { void client.refetchQueries({ queryKey: queryKeys.subscription.all() }) })
    await waitFor(() => expect(api.getSubscriptionStatus).toHaveBeenCalledTimes(2))
    expect(retry).toHaveAttribute('aria-busy', 'true')
    expect(document.activeElement).toBe(retry)
    expect(screen.getByText('subscription unavailable')).toBeInTheDocument()

    await act(async () => background.resolve(freeSub))
    await waitFor(() => expect(retry.isConnected).toBe(false))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(document.activeElement).toBe(intro())
  })

  it('a Notice that clears while its Retry does not hold focus moves no focus', async () => {
    api.getCurrentUserSafe.mockResolvedValue(user1)
    api.getSubscriptionStatus.mockRejectedValueOnce(new Error('subscription unavailable'))
    api.getSubscriptionStatus.mockResolvedValue(freeSub)
    api.getUsage.mockResolvedValue(usage)
    const client = renderPricing()
    await screen.findByRole('button', { name: 'Try again' })
    expect(document.activeElement).toBe(document.body)

    // A background refetch (window focus, reconnect) recovers the subscription on its own.
    await act(async () => { await client.refetchQueries() })
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
    expect(document.activeElement).toBe(document.body)
  })

  it.each(cases)('the Retry of $name pressed offline waits paused, busy and focused, and a second press sends nothing', async ({ request, arrange }) => {
    arrange()
    renderPricing()
    const retry = await screen.findByRole('button', { name: 'Try again' })
    retry.focus()
    onlineManager.setOnline(false)
    fireEvent.click(retry)
    await settle()
    expectBusyAndFocused(retry)
    expect(retry).toHaveAccessibleName('Trying again…')
    fireEvent.click(retry)
    await settle()
    expect(request).toHaveBeenCalledTimes(1)
  })

  it.each(cases)('the Retry of $name: after a press fails again and the user moves off, a recovery nobody pressed moves no focus', async ({ request, arrange, key, success }) => {
    arrange()
    const client = renderPricing()
    const retry = await screen.findByRole('button', { name: 'Try again' })
    retry.focus()
    request.mockRejectedValueOnce(new Error('still down'))
    fireEvent.click(retry)
    expect(await screen.findByText('still down')).toBeInTheDocument()
    await waitFor(() => expect(retry).not.toHaveAttribute('aria-busy'))
    retry.blur()
    const background = deferred<unknown>()
    request.mockReturnValueOnce(background.promise)
    act(() => { void client.refetchQueries({ queryKey: key }) })
    await waitFor(() => expect(request).toHaveBeenCalledTimes(3))
    await settle()
    expect(document.activeElement).toBe(document.body)
    await act(async () => background.resolve(success))
    await waitFor(() => expect(retry.isConnected).toBe(false))
    await settle()
    expect(document.activeElement).toBe(document.body)
  })

  it.each(cases)('the Retry of $name: a refetch nobody pressed keeps it focused and busy under its own label; its success hands focus to the intro', async ({ request, arrange, key, success }) => {
    arrange()
    const client = renderPricing()
    const retry = await screen.findByRole('button', { name: 'Try again' })
    retry.focus()
    const background = deferred<unknown>()
    request.mockReturnValueOnce(background.promise)
    act(() => { void client.refetchQueries({ queryKey: key }) })
    await waitFor(() => expect(request).toHaveBeenCalledTimes(2))
    await settle()
    expectBusyAndFocused(retry)
    expect(retry).toHaveAccessibleName('Try again')
    await act(async () => background.resolve(success))
    await waitFor(() => expect(retry.isConnected).toBe(false))
    await settle()
    expect(document.activeElement).toBe(intro())
  })

  it('a Retry never outlives its Notice: when the account Notice gives way to the details Notice, its focused Retry goes too', async () => {
    // The plan check of user 1 failed earlier with data on screen (a stale failure), and is still cached.
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    client.setQueryData(queryKeys.subscription.byUser(1), freeSub)
    client.setQueryData(queryKeys.usage.byUser(1), usage)
    await client
      .fetchQuery({ queryKey: queryKeys.subscription.byUser(1), queryFn: () => Promise.reject(new Error('plan refresh failed')) })
      .catch(() => {})
    expect(client.getQueryState(queryKeys.subscription.byUser(1))?.status).toBe('error')
    api.getCurrentUserSafe.mockRejectedValueOnce(new Error('network down'))
    const planRefresh = deferred<SubscriptionStatus>()
    api.getSubscriptionStatus.mockReturnValue(planRefresh.promise)
    api.getUsage.mockResolvedValue(usage)
    render(<QueryClientProvider client={client}><PricingPage /></QueryClientProvider>)

    const accountRetry = await screen.findByRole('button', { name: 'Try again' })
    accountRetry.focus()
    api.getCurrentUserSafe.mockResolvedValueOnce(user1)
    fireEvent.click(accountRetry, { detail: 0 })
    // The account resolves, and in the same render the cached plan failure shows the details Notice. Unkeyed,
    // React reused the account Retry as the details Notice's: the same focused node, still pressed (it read
    // "Trying again…" there while the plan refreshed).
    const details = (await screen.findByText("We couldn't refresh your plan details")).closest('[role="alert"]') as HTMLElement
    const planRetry = within(details).getByRole('button', { name: 'Try again' })
    expect(planRetry).not.toBe(accountRetry)
    expect(accountRetry.isConnected).toBe(false)
    await settle()
    expect(document.activeElement).toBe(intro())
    await act(async () => planRefresh.resolve(freeSub))
  })
})

// These cases exercise the form after release; legalReadiness.spec.tsx holds the closed and stale gates.
vi.mock('@/features/legal/hooks/useLegalReadiness', async () => {
  const { readyLegalHook } = await import('./fixtures/legalReady')
  return { useLegalReadiness: () => readyLegalHook }
})
