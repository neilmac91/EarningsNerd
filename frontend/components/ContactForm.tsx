'use client'

import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { submitContactForm } from '@/features/contact/api/contact-api'

export default function ContactForm() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [subject, setSubject] = useState('')
  const [message, setMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

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
      await submitContactForm({
        name: name.trim(),
        email: email.trim(),
        subject: subject.trim() || null,
        message: message.trim(),
      })

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
      <div className="rounded-2xl border border-border-light bg-white p-8 shadow-lg dark:border-border-dark dark:bg-slate-900/70">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-mint-100 dark:bg-mint-900/30">
            <svg
              className="h-6 w-6 text-mint-600 dark:text-mint-400"
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
            Message Sent!
          </h3>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            Thank you for contacting us. We&apos;ve received your message and will get back to you within 1-2 business
            days.
          </p>
          <button
            onClick={() => setSuccess(false)}
            className="mt-6 text-sm font-medium text-mint-600 hover:text-mint-700 dark:text-mint-400 dark:hover:text-mint-300"
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
      className="rounded-2xl border border-border-light bg-white p-8 shadow-lg dark:border-border-dark dark:bg-slate-900/70"
    >
      <div className="space-y-6">
        {/* Name Field */}
        <div>
          <label
            htmlFor="name"
            className="block text-sm font-medium text-text-primary-light dark:text-text-primary-dark"
          >
            Name <span className="text-red-500">*</span>
          </label>
          <input
            id="name"
            name="name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            disabled={isSubmitting}
            className="mt-2 w-full rounded-lg border border-border-light bg-white px-4 py-3 text-text-primary-light placeholder-gray-400 transition-colors focus:border-mint-500 focus:outline-none focus:ring-2 focus:ring-mint-500/20 disabled:cursor-not-allowed disabled:opacity-50 dark:border-border-dark dark:bg-slate-800 dark:text-text-primary-dark dark:placeholder-gray-500"
            placeholder="Your name"
          />
        </div>

        {/* Email Field */}
        <div>
          <label
            htmlFor="email"
            className="block text-sm font-medium text-text-primary-light dark:text-text-primary-dark"
          >
            Email <span className="text-red-500">*</span>
          </label>
          <input
            id="email"
            name="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            disabled={isSubmitting}
            className="mt-2 w-full rounded-lg border border-border-light bg-white px-4 py-3 text-text-primary-light placeholder-gray-400 transition-colors focus:border-mint-500 focus:outline-none focus:ring-2 focus:ring-mint-500/20 disabled:cursor-not-allowed disabled:opacity-50 dark:border-border-dark dark:bg-slate-800 dark:text-text-primary-dark dark:placeholder-gray-500"
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
          <input
            id="subject"
            name="subject"
            type="text"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            disabled={isSubmitting}
            className="mt-2 w-full rounded-lg border border-border-light bg-white px-4 py-3 text-text-primary-light placeholder-gray-400 transition-colors focus:border-mint-500 focus:outline-none focus:ring-2 focus:ring-mint-500/20 disabled:cursor-not-allowed disabled:opacity-50 dark:border-border-dark dark:bg-slate-800 dark:text-text-primary-dark dark:placeholder-gray-500"
            placeholder="How can we help?"
          />
        </div>

        {/* Message Field */}
        <div>
          <label
            htmlFor="message"
            className="block text-sm font-medium text-text-primary-light dark:text-text-primary-dark"
          >
            Message <span className="text-red-500">*</span>
          </label>
          <textarea
            id="message"
            name="message"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            required
            disabled={isSubmitting}
            rows={6}
            className="mt-2 w-full rounded-lg border border-border-light bg-white px-4 py-3 text-text-primary-light placeholder-gray-400 transition-colors focus:border-mint-500 focus:outline-none focus:ring-2 focus:ring-mint-500/20 disabled:cursor-not-allowed disabled:opacity-50 dark:border-border-dark dark:bg-slate-800 dark:text-text-primary-dark dark:placeholder-gray-500"
            placeholder="Tell us more about your inquiry..."
          />
          <p className="mt-2 text-sm text-text-tertiary-light dark:text-text-tertiary-dark">
            Minimum 10 characters
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="rounded-lg bg-red-50 p-4 dark:bg-red-900/20">
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          </div>
        )}

        {/* Submit Button */}
        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full rounded-lg bg-mint-600 px-6 py-3 font-medium text-white transition-colors hover:bg-mint-700 focus:outline-none focus:ring-2 focus:ring-mint-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-mint-500 dark:hover:bg-mint-600"
        >
          {isSubmitting ? (
            <span className="flex items-center justify-center">
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              Sending...
            </span>
          ) : (
            'Send Message'
          )}
        </button>
      </div>
    </form>
  )
}
