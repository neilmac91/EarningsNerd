'use client'

import { useState } from 'react'
import { clsx } from 'clsx'
import { CircleNotchIcon } from '@/lib/icons'
import { submitContactForm } from '@/features/contact/api/contact-api'
import TurnstileWidget from '@/features/auth/components/TurnstileWidget'
import { TURNSTILE_ENABLED } from '@/lib/featureFlags'
import { Button } from '@/components/ui/Button'
import { Input, inputClasses } from '@/components/ui/Input'

export default function ContactForm() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [subject, setSubject] = useState('')
  const [message, setMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [turnstileToken, setTurnstileToken] = useState('')

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    setSuccess(false)

    // Client-side validation
    if (!name.trim()) {
      setError('Please enter your name.')
      return
    }
    if (!email.trim()) {
      setError('Please enter your email address.')
      return
    }
    if (!message.trim()) {
      setError('Please enter a message.')
      return
    }
    if (message.trim().length < 10) {
      setError('Message must be at least 10 characters long.')
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

      setSuccess(true)
      // Reset form
      setName('')
      setEmail('')
      setSubject('')
      setMessage('')
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to send message. Please try again.'
      if (errorMessage.includes('429')) {
        setError('Too many requests. Please try again in an hour.')
      } else {
        setError(errorMessage)
      }
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
          <h3 className="mb-2 text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Message sent
          </h3>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            Thank you for contacting us. We&apos;ve received your message and will get back to you within 1-2 business
            days.
          </p>
          <button
            onClick={() => setSuccess(false)}
            className="mt-6 text-sm font-medium text-brand-strong underline-offset-4 hover:underline dark:text-brand-strong-dark"
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
            id="name"
            name="name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            disabled={isSubmitting}
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
            disabled={isSubmitting}
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
            disabled={isSubmitting}
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
            disabled={isSubmitting}
            rows={6}
            className={clsx(inputClasses(), 'mt-2')}
            placeholder="Tell us more about your inquiry..."
          />
          <p className="mt-2 text-sm text-text-tertiary-light dark:text-text-secondary-dark">
            Minimum 10 characters
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="rounded-lg bg-error-light/10 p-4 dark:bg-error-dark/15">
            <p className="text-sm text-error-light dark:text-error-dark">{error}</p>
          </div>
        )}

        <TurnstileWidget onToken={setTurnstileToken} />

        {/* Submit Button */}
        <Button
          type="submit"
          disabled={isSubmitting || (TURNSTILE_ENABLED && !turnstileToken)}
          className="w-full"
        >
          {isSubmitting ? (
            <span className="flex items-center justify-center">
              <CircleNotchIcon className="mr-2 h-5 w-5 animate-spin" />
              Sending...
            </span>
          ) : (
            'Send Message'
          )}
        </Button>
      </div>
    </form>
  )
}
