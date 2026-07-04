'use client'

import { useMemo, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { CheckIcon, CircleNotchIcon, CopyIcon } from '@/lib/icons'
import { getApiUrl } from '@/lib/api/client'
import TurnstileWidget from '@/components/auth/TurnstileWidget'
import { TURNSTILE_ENABLED } from '@/lib/featureFlags'
import { Button } from '@/components/ui/Button'
import { inputClasses } from '@/components/ui/Input'

type WaitlistSuccess = {
  message?: string
  position: number
  referral_code: string
  referral_link: string
}

type WaitlistFormProps = {
  source?: string
}

const twitterCopy =
  'I just joined the waitlist for @EarningsNerd - AI-powered SEC filing summaries for retail investors. Join me:'
const linkedInCopy =
  'Excited to get early access to EarningsNerd, a tool that uses AI to summarize SEC filings. Join the waitlist:'

export default function WaitlistForm({ source = 'homepage' }: WaitlistFormProps) {
  const searchParams = useSearchParams()
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [honeypot, setHoneypot] = useState('')
  const [turnstileToken, setTurnstileToken] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<WaitlistSuccess | null>(null)
  const [copied, setCopied] = useState(false)

  // Derived during render from the URL — referralCode is read-only (only ever
  // submitted, never user-edited), so no state/effect is needed (per PR review).
  // Guard on the raw param (like the prior effect) so a blank ref stays null.
  const refParam = searchParams.get('ref')
  const referralCode = refParam ? refParam.trim().toLowerCase() : null

  const referralLink = success?.referral_link

  const shareLinks = useMemo(() => {
    if (!referralLink) return null
    const twitterText = `${twitterCopy} ${referralLink}`
    const linkedInText = `${linkedInCopy} ${referralLink}`
    return {
      twitter: `https://twitter.com/intent/tweet?text=${encodeURIComponent(twitterText)}`,
      linkedIn: `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(
        referralLink
      )}&summary=${encodeURIComponent(linkedInText)}`,
      whatsapp: `https://wa.me/?text=${encodeURIComponent(twitterText)}`,
    }
  }, [referralLink])

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    setCopied(false)

    if (!email.trim()) {
      setError('Please enter a valid email address.')
      return
    }

    setIsSubmitting(true)
    try {
      const response = await fetch(`${getApiUrl()}/api/waitlist/join`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(turnstileToken ? { 'cf-turnstile-response': turnstileToken } : {}),
        },
        body: JSON.stringify({
          email: email.trim(),
          name: name.trim() || null,
          referral_code: referralCode,
          source,
          honeypot,
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        const detail =
          typeof data?.detail === 'string'
            ? data.detail
            : typeof data?.message === 'string'
            ? data.message
            : null
        setError(detail || 'Something went wrong. Please try again.')
        return
      }

      if (data?.success === false && data?.error === 'already_registered') {
        setSuccess({
          message: data.message,
          position: data.position,
          referral_code: data.referral_code,
          referral_link: data.referral_link,
        })
        return
      }

      if (!data?.success) {
        setError(data?.message || 'Unable to join the waitlist right now.')
        return
      }

      setSuccess({
        message: data.message,
        position: data.position,
        referral_code: data.referral_code,
        referral_link: data.referral_link,
      })
    } catch {
      setError('Network error. Please try again in a moment.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleCopy = async () => {
    if (!referralLink) return
    try {
      await navigator.clipboard.writeText(referralLink)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
    }
  }

  if (success) {
    return (
      <div className="rounded-2xl border border-brand-border bg-panel-light p-6 shadow-e2 dark:shadow-none backdrop-blur-sm transition duration-base dark:border-brand-dark/40 dark:bg-panel-dark">
        <div className="flex items-center gap-2 text-brand-strong dark:text-brand-strong-dark">
          <CheckIcon className="h-5 w-5" />
          <span className="text-sm font-semibold uppercase tracking-wide">You&apos;re in</span>
        </div>
        <h3 className="mt-3 text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
          {success.message || 'You&apos;re on the waitlist!'}
        </h3>
        <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
          Your current position is <span className="font-semibold">#{success.position}</span>.
        </p>

        <div className="mt-5 rounded-xl border border-border-light bg-background-light px-4 py-3 dark:border-border-dark dark:bg-background-dark">
          <div className="text-xs uppercase tracking-wide text-text-tertiary-light dark:text-text-secondary-dark">
            Your referral link
          </div>
          <div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <span className="text-sm font-medium text-text-primary-light dark:text-text-primary-dark">
              {success.referral_link}
            </span>
            <button
              type="button"
              onClick={handleCopy}
              className="inline-flex items-center justify-center gap-2 rounded-full border border-brand-border bg-panel-light px-4 py-2 text-sm font-semibold text-brand-strong transition hover:border-brand-border hover:text-brand-emphasis dark:border-brand-dark/40 dark:bg-panel-dark dark:text-brand-strong-dark"
            >
              {copied ? <CheckIcon className="h-4 w-4" /> : <CopyIcon className="h-4 w-4" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
        </div>

        <div className="mt-5 text-sm text-text-secondary-light dark:text-text-secondary-dark">
          Move up the list by sharing — each referral bumps you up 5 spots.
        </div>

        {shareLinks && (
          <div className="mt-4 flex flex-wrap gap-3">
            <a
              href={shareLinks.twitter}
              target="_blank"
              rel="noreferrer"
              className="rounded-full border border-border-light bg-background-light px-4 py-2 text-sm font-medium text-text-primary-light transition hover:border-brand-border dark:border-border-dark dark:bg-background-dark dark:text-text-primary-dark"
            >
              Share on Twitter
            </a>
            <a
              href={shareLinks.linkedIn}
              target="_blank"
              rel="noreferrer"
              className="rounded-full border border-border-light bg-background-light px-4 py-2 text-sm font-medium text-text-primary-light transition hover:border-brand-border dark:border-border-dark dark:bg-background-dark dark:text-text-primary-dark"
            >
              Share on LinkedIn
            </a>
            <a
              href={shareLinks.whatsapp}
              target="_blank"
              rel="noreferrer"
              className="rounded-full border border-border-light bg-background-light px-4 py-2 text-sm font-medium text-text-primary-light transition hover:border-brand-border dark:border-border-dark dark:bg-background-dark dark:text-text-primary-dark"
            >
              Share on WhatsApp
            </a>
          </div>
        )}
      </div>
    )
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-2xl border border-border-light bg-panel-light p-6 shadow-e2 dark:shadow-none backdrop-blur-sm dark:border-border-dark dark:bg-panel-dark"
    >
      <div className="flex flex-col gap-4">
        <div>
          <label
            htmlFor="waitlist-email"
            className="text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark"
          >
            Email address
          </label>
          {/* Raw input + inputClasses(): geometry overrides target the field itself,
              which the v2 <Input> shell no longer exposes via className. */}
          <input
            id="waitlist-email"
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@company.com"
            className={inputClasses({ className: 'mt-2 rounded-xl px-4 py-3 text-sm' })}
          />
        </div>

        <div>
          <label
            htmlFor="waitlist-name"
            className="text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark"
          >
            Full name (optional)
          </label>
          <input
            id="waitlist-name"
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Jane Doe"
            className={inputClasses({ className: 'mt-2 rounded-xl px-4 py-3 text-sm' })}
          />
        </div>

        <input
          type="text"
          tabIndex={-1}
          autoComplete="off"
          aria-hidden="true"
          className="hidden"
          value={honeypot}
          onChange={(event) => setHoneypot(event.target.value)}
        />

        {error && (
          <div className="rounded-xl border border-error-light/40 dark:border-error-dark/40 bg-error-light/10 dark:bg-error-dark/10 px-4 py-3 text-sm text-error-light dark:text-error-dark">
            {error}
          </div>
        )}

        <TurnstileWidget onToken={setTurnstileToken} />

        <Button
          type="submit"
          disabled={isSubmitting || (TURNSTILE_ENABLED && !turnstileToken)}
          className="w-full rounded-full px-6 py-3 font-semibold"
        >
          {isSubmitting && <CircleNotchIcon className="h-4 w-4 animate-spin" />}
          {isSubmitting ? 'Joining waitlist...' : 'Join the waitlist'}
        </Button>
      </div>
    </form>
  )
}
