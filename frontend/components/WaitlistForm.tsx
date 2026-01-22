'use client'

import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { Check, Copy, Loader2 } from 'lucide-react'
import { getApiUrl } from '@/lib/api/client'

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
  const [referralCode, setReferralCode] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<WaitlistSuccess | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    const ref = searchParams.get('ref')
    if (ref) {
      setReferralCode(ref.trim().toLowerCase())
    }
  }, [searchParams])

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
        headers: { 'Content-Type': 'application/json' },
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
      <div className="rounded-2xl border border-mint-200/70 bg-white/80 p-6 shadow-lg backdrop-blur-sm transition-all duration-300 dark:border-mint-500/30 dark:bg-slate-900/60">
        <div className="flex items-center gap-2 text-mint-600 dark:text-mint-300">
          <Check className="h-5 w-5" />
          <span className="text-sm font-semibold uppercase tracking-wide">You&apos;re in</span>
        </div>
        <h3 className="mt-3 text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
          {success.message || 'You&apos;re on the waitlist!'}
        </h3>
        <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
          Your current position is <span className="font-semibold">#{success.position}</span>.
        </p>

        <div className="mt-5 rounded-xl border border-border-light bg-background-light px-4 py-3 dark:border-border-dark dark:bg-background-dark">
          <div className="text-xs uppercase tracking-wide text-text-tertiary-light dark:text-text-tertiary-dark">
            Your referral link
          </div>
          <div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <span className="text-sm font-medium text-text-primary-light dark:text-text-primary-dark">
              {success.referral_link}
            </span>
            <button
              type="button"
              onClick={handleCopy}
              className="inline-flex items-center justify-center gap-2 rounded-full border border-mint-200 bg-white px-4 py-2 text-sm font-semibold text-mint-700 transition hover:border-mint-300 hover:text-mint-800 dark:border-mint-500/40 dark:bg-slate-900 dark:text-mint-200"
            >
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
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
              className="rounded-full border border-border-light bg-background-light px-4 py-2 text-sm font-medium text-text-primary-light transition hover:border-mint-200 dark:border-border-dark dark:bg-background-dark dark:text-text-primary-dark"
            >
              Share on Twitter
            </a>
            <a
              href={shareLinks.linkedIn}
              target="_blank"
              rel="noreferrer"
              className="rounded-full border border-border-light bg-background-light px-4 py-2 text-sm font-medium text-text-primary-light transition hover:border-mint-200 dark:border-border-dark dark:bg-background-dark dark:text-text-primary-dark"
            >
              Share on LinkedIn
            </a>
            <a
              href={shareLinks.whatsapp}
              target="_blank"
              rel="noreferrer"
              className="rounded-full border border-border-light bg-background-light px-4 py-2 text-sm font-medium text-text-primary-light transition hover:border-mint-200 dark:border-border-dark dark:bg-background-dark dark:text-text-primary-dark"
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
      className="rounded-2xl border border-border-light bg-white/90 p-6 shadow-lg backdrop-blur-sm dark:border-border-dark dark:bg-slate-900/70"
    >
      <div className="flex flex-col gap-4">
        <div>
          <label
            htmlFor="waitlist-email"
            className="text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark"
          >
            Email address
          </label>
          <input
            id="waitlist-email"
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@company.com"
            className="mt-2 w-full rounded-xl border border-border-light bg-background-light px-4 py-3 text-sm text-text-primary-light focus:border-mint-300 focus:outline-none dark:border-border-dark dark:bg-background-dark dark:text-text-primary-dark"
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
            className="mt-2 w-full rounded-xl border border-border-light bg-background-light px-4 py-3 text-sm text-text-primary-light focus:border-mint-300 focus:outline-none dark:border-border-dark dark:bg-background-dark dark:text-text-primary-dark"
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
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={isSubmitting}
          className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-mint-500 px-6 py-3 text-sm font-semibold text-slate-900 transition hover:bg-mint-400 disabled:cursor-not-allowed disabled:opacity-70"
        >
          {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
          {isSubmitting ? 'Joining waitlist...' : 'Join the waitlist'}
        </button>
      </div>
    </form>
  )
}
