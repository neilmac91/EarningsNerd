'use client'

import { useMemo, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { CheckIcon, CopyIcon } from '@/lib/icons'
import { getApiUrl } from '@/lib/api/client'
import TurnstileWidget from '@/components/auth/TurnstileWidget'
import { TURNSTILE_ENABLED } from '@/lib/featureFlags'
import { Button, Card, Input, Notice, buttonVariants } from '@/components/ui'

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
    // The submit Button uses `loading` (aria-disabled, not native disabled) to keep its resting
    // fill, so Enter in a field can still fire this while a request is in flight — guard explicitly.
    if (isSubmitting) return
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
      <Card className="p-6">
        <div className="flex items-center gap-2 text-brand-strong dark:text-brand-strong-dark">
          <CheckIcon className="h-5 w-5" />
          <span className="text-sm font-semibold uppercase tracking-wide">You&apos;re in</span>
        </div>
        <h3 className="mt-3 text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
          {success.message || 'You&apos;re on the waitlist!'}
        </h3>
        <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
          Your current position is <span className="tnum font-data font-semibold">#{success.position}</span>.
        </p>

        <div className="mt-5 rounded-xl border border-border-light bg-background-light px-4 py-3 dark:border-border-dark dark:bg-background-dark">
          <div className="text-xs uppercase tracking-wide text-text-tertiary-light dark:text-text-secondary-dark">
            Your referral link
          </div>
          <div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <span className="break-all text-sm font-medium text-text-primary-light dark:text-text-primary-dark">
              {success.referral_link}
            </span>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={handleCopy}
              leftIcon={copied ? <CheckIcon className="h-4 w-4" /> : <CopyIcon className="h-4 w-4" />}
              className="shrink-0"
            >
              {copied ? 'Copied' : 'Copy'}
            </Button>
          </div>
        </div>

        <div className="mt-5 text-sm text-text-secondary-light dark:text-text-secondary-dark">
          Move up the list by sharing — each referral bumps you up 5 spots.
        </div>

        {shareLinks && (
          <div className="mt-4 flex flex-wrap gap-3">
            <a href={shareLinks.twitter} target="_blank" rel="noreferrer" className={buttonVariants({ variant: 'secondary', size: 'sm' })}>
              Share on Twitter
            </a>
            <a href={shareLinks.linkedIn} target="_blank" rel="noreferrer" className={buttonVariants({ variant: 'secondary', size: 'sm' })}>
              Share on LinkedIn
            </a>
            <a href={shareLinks.whatsapp} target="_blank" rel="noreferrer" className={buttonVariants({ variant: 'secondary', size: 'sm' })}>
              Share on WhatsApp
            </a>
          </div>
        )}
      </Card>
    )
  }

  return (
    <Card as="form" onSubmit={handleSubmit} className="p-6">
      <div className="flex flex-col gap-4">
        <div>
          <label
            htmlFor="waitlist-email"
            className="text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark"
          >
            Email address
          </label>
          <Input
            id="waitlist-email"
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@company.com"
            className="mt-2"
          />
        </div>

        <div>
          <label
            htmlFor="waitlist-name"
            className="text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark"
          >
            Full name (optional)
          </label>
          <Input
            id="waitlist-name"
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Jane Doe"
            className="mt-2"
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

        {error && <Notice variant="error" title={error} />}

        <TurnstileWidget onToken={setTurnstileToken} />

        <Button
          type="submit"
          loading={isSubmitting}
          loadingText="Joining waitlist..."
          disabled={TURNSTILE_ENABLED && !turnstileToken}
          className="w-full"
        >
          Join the waitlist
        </Button>
      </div>
    </Card>
  )
}
