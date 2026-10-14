'use client'

import { useEffect, useRef, useState } from 'react'
import { clsx } from 'clsx'
import { submitContactForm } from '@/features/contact/api/contact-api'
import { CONTACT_LIMITS, isPlausibleEmail, trimmedLength } from '@/features/contact/lib/limits'
import TurnstileWidget from '@/features/auth/components/TurnstileWidget'
import { TURNSTILE_ENABLED } from '@/lib/featureFlags'
import { Button } from '@/components/ui/Button'
import { Input, inputClasses } from '@/components/ui/Input'
import { Notice } from '@/components/ui/Notice'
import { ApiError } from '@/lib/api/client'
import { getErrorStatus } from '@/lib/api/types'

const RATE_LIMITED = 'Too many messages from this connection. Try again in an hour.'
const CHECK_FIELDS = 'Check the fields and send again.'
const SEND_FAILED = "We couldn't send your message. Try again in a minute."

/** What a failed send tells the reader. The rate limit is read from the status, never from the
    message's words (the backend's 429 sentence has no "429" in it), and so is a 422, which asks the
    reader to check the fields. Otherwise the backend's own detail, or the surface's sentence when the
    body carried none: `backendDetail` is set only from a string `detail` in the body, never from
    the client's status fallbacks or axios's "Request failed with status code N". */
function sendErrorMessage(err: unknown): string {
  const status = getErrorStatus(err)
  if (status === 429) return RATE_LIMITED
  if (status === 422) return CHECK_FIELDS
  const detail = err instanceof ApiError ? err.backendDetail : undefined
  return typeof detail === 'string' && detail.trim() ? detail : SEND_FAILED
}

export default function ContactForm() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [subject, setSubject] = useState('')
  const [message, setMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [turnstileToken, setTurnstileToken] = useState('')
  // Swapping the form for the success panel (and back) unmounts whatever held focus: Send, the
  // field Enter was pressed in, or 'Send another message'. Hand focus to the panel's heading, or to
  // the first field, but only when it fell to <body>.
  const successHeadingRef = useRef<HTMLHeadingElement>(null)
  const nameRef = useRef<HTMLInputElement>(null)
  const swapped = useRef(false)
  useEffect(() => {
    if (!swapped.current) return
    swapped.current = false
    if (document.activeElement !== document.body) return
    ;(success ? successHeadingRef.current : nameRef.current)?.focus({ preventScroll: true })
  }, [success])

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    // Send uses `loading` (aria-disabled + click guard, not native disabled) and the fields go
    // readOnly, so everything stays focusable while the request is in flight — Enter in a field can
    // still land here, so refuse a second submit explicitly.
    if (isSubmitting) return
    setError(null)
    setSuccess(false)

    // Client-side validation
    if (!name.trim()) {
      setError('Please enter your name.')
      return
    }
    if (trimmedLength(name) < CONTACT_LIMITS.nameMin) {
      setError(`Your name needs at least ${CONTACT_LIMITS.nameMin} characters.`)
      return
    }
    if (!email.trim()) {
      setError('Please enter your email address.')
      return
    }
    if (!isPlausibleEmail(email.trim())) {
      setError('Please enter a valid email address.')
      return
    }
    if (!message.trim()) {
      setError('Please enter a message.')
      return
    }
    if (trimmedLength(message) < CONTACT_LIMITS.messageMin) {
      setError(`Your message needs at least ${CONTACT_LIMITS.messageMin} characters.`)
      return
    }

    setIsSubmitting(true)

    try {
      await submitContactForm(
        {
          name: name.trim(),
          email: email.trim(),
          subject: subject.trim() || null,
          message: message.trim(),
        },
        turnstileToken,
      )

      swapped.current = true
      setSuccess(true)
      // Reset form
      setName('')
      setEmail('')
      setSubject('')
      setMessage('')
    } catch (err: unknown) {
      setError(sendErrorMessage(err))
    } finally {
      setIsSubmitting(false)
    }
  }

  if (success) {
    return (
      <div className="rounded-2xl border border-border-light bg-panel-light p-8 shadow-e3 dark:border-white/10 dark:bg-panel-dark dark:shadow-none">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-success-light/10 dark:bg-success-dark/15">
            <svg
              className="h-6 w-6 text-success-light dark:text-success-dark"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
          <h2
            ref={successHeadingRef}
            tabIndex={-1}
            className="mb-2 text-xl font-semibold text-text-primary-light outline-none dark:text-text-primary-dark"
          >
            Message sent
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            We have your message and will reply within 1–2 business days.
          </p>
          <button
            onClick={() => {
              swapped.current = true
              setSuccess(false)
            }}
            className="mt-6 rounded-sm text-sm font-medium text-brand-strong underline-offset-4 hover:underline focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark"
          >
            Send another message
          </button>
        </div>
      </div>
    )
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-2xl border border-border-light bg-panel-light p-8 shadow-e3 dark:border-white/10 dark:bg-panel-dark dark:shadow-none"
    >
      <div className="space-y-6">
        {/* Name Field */}
        <div>
          <label
            htmlFor="name"
            className="block text-sm font-medium text-text-primary-light dark:text-text-primary-dark"
          >
            Name <span className="text-error-light dark:text-error-dark">*</span>
          </label>
          <Input
            ref={nameRef}
            id="name"
            name="name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={CONTACT_LIMITS.nameMax}
            readOnly={isSubmitting}
            className="mt-2"
            placeholder="Your name"
          />
        </div>

        {/* Email Field */}
        <div>
          <label
            htmlFor="email"
            className="block text-sm font-medium text-text-primary-light dark:text-text-primary-dark"
          >
            Email <span className="text-error-light dark:text-error-dark">*</span>
          </label>
          <Input
            id="email"
            name="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            readOnly={isSubmitting}
            className="mt-2"
            placeholder="you@company.com"
          />
        </div>

        {/* Subject Field */}
        <div>
          <label
            htmlFor="subject"
            className="block text-sm font-medium text-text-primary-light dark:text-text-primary-dark"
          >
            Subject
          </label>
          <Input
            id="subject"
            name="subject"
            type="text"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            maxLength={CONTACT_LIMITS.subjectMax}
            readOnly={isSubmitting}
            className="mt-2"
            placeholder="How can we help?"
          />
        </div>

        {/* Message Field */}
        <div>
          <label
            htmlFor="message"
            className="block text-sm font-medium text-text-primary-light dark:text-text-primary-dark"
          >
            Message <span className="text-error-light dark:text-error-dark">*</span>
          </label>
          <textarea
            id="message"
            name="message"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            required
            maxLength={CONTACT_LIMITS.messageMax}
            readOnly={isSubmitting}
            rows={6}
            className={clsx(inputClasses(), 'mt-2')}
            placeholder="What happened, or what you'd like to know"
          />
          <p className="mt-2 text-sm text-text-tertiary-light dark:text-text-secondary-dark">
            Minimum {CONTACT_LIMITS.messageMin} characters
          </p>
        </div>

        {/* Error Message */}
        {error && <Notice variant="error" title="Message not sent" description={error} />}

        <TurnstileWidget onToken={setTurnstileToken} />

        {/* Submit Button — `loading`, never native `disabled`, while sending: Chromium blurs a
            focused control that turns disabled (focus → <body>), and the fields above are readOnly
            for the same reason. Native `disabled` stays only for the missing Turnstile token, which
            the widget sets — never this button's own activation. */}
        <Button
          type="submit"
          loading={isSubmitting}
          loadingText="Sending…"
          disabled={TURNSTILE_ENABLED && !turnstileToken}
          className="w-full"
        >
          Send message
        </Button>
      </div>
    </form>
  )
}
