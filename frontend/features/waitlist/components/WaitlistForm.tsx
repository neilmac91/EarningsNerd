'use client'

import { useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { CheckIcon, CopyIcon } from '@/lib/icons'
import { ApiError } from '@/lib/api/client'
import { joinWaitlist } from '@/features/waitlist/api/waitlist-api'
import { REFERRAL_BONUS } from '@/features/waitlist/lib/referral'
import TurnstileWidget from '@/features/auth/components/TurnstileWidget'
import { TURNSTILE_ENABLED } from '@/lib/featureFlags'
import { Button, Card, Input, Notice, buttonVariants, cx, primaryUnavailableClass } from '@/components/ui'

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
  'I just joined the waitlist for @EarningsNerd, AI summaries of SEC filings for investors who still check the source. Join me:'
const linkedInCopy =
  'Excited to get early access to EarningsNerd, a tool that uses AI to summarize SEC filings. Join the waitlist:'
// The router's invalid_referral (a 400 carrying its code): no signup holds the ?ref= this page was opened with.
// One phrase for the Notice's title, the second sentence its description (lessons/frontend-a-notice-title-is-one-phrase.md).
const unknownReferralTitle = "We can't find this referral code on the waitlist"
const unknownReferralDescription = 'Check the link with whoever shared it.'
// Wrapping pills (DESIGN_SYSTEM.md, Wrapping button): at 200% text "Share on WhatsApp" is wider than the card, and
// "Join without the code" than its Notice.
const pillLinkClass = buttonVariants({ variant: 'secondary', size: 'sm', wrap: true, className: 'max-w-full' })

export default function WaitlistForm({ source = 'homepage' }: WaitlistFormProps) {
  const searchParams = useSearchParams()
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [honeypot, setHoneypot] = useState('')
  const [turnstileToken, setTurnstileToken] = useState('')
  // A new key mounts a new Turnstile widget, which issues a new token (see handleSubmit's finally).
  const [turnstileKey, setTurnstileKey] = useState(0)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [referralRefused, setReferralRefused] = useState(false)
  // The code "Join without the code" dropped (joinWithoutCode), so a submit before the URL loses it sends none.
  const [droppedReferral, setDroppedReferral] = useState<string | null>(null)
  const [success, setSuccess] = useState<WaitlistSuccess | null>(null)
  const [copied, setCopied] = useState(false)

  // Derived during render from the URL: the code is only ever submitted, never typed. Guard on the raw param so a
  // blank ref stays null. A code the reader dropped is not sent, even while the URL still holds it.
  const refParam = searchParams.get('ref')
  const urlReferral = refParam ? refParam.trim().toLowerCase() : null
  const referralCode = urlReferral === droppedReferral ? null : urlReferral
  const emailRef = useRef<HTMLInputElement>(null)
  // With Turnstile on, a join waits for a token: on the first load, while a new one is issued after each join the
  // form sends (handleSubmit's finally), and after one expires.
  const tokenPending = TURNSTILE_ENABLED && !turnstileToken

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
    // The wait for a Turnstile token is aria-disabled too, so a press or Enter sends nothing until the token comes.
    if (isSubmitting || tokenPending) return
    setError(null)
    setReferralRefused(false)
    setCopied(false)

    if (!email.trim()) {
      setError('Please enter a valid email address.')
      return
    }

    setIsSubmitting(true)
    try {
      const data = await joinWaitlist(
        {
          email: email.trim(),
          name: name.trim() || null,
          referral_code: referralCode,
          source,
          honeypot,
        },
        turnstileToken || undefined,
      )

      if (data?.success === false && data?.error === 'already_registered') {
        setSuccess({
          message: data.message,
          position: data.position,
          referral_code: data.referral_code,
          referral_link: data.referral_link,
        })
        return
      }

      if (data?.success === false && data?.error === 'invalid_referral') {
        setReferralRefused(true)
        return
      }

      if (!data?.success) {
        setError(data?.message || data?.detail || 'Unable to join the waitlist right now.')
        return
      }

      setSuccess({
        message: data.message,
        position: data.position,
        referral_code: data.referral_code,
        referral_link: data.referral_link,
      })
    } catch (err) {
      // An HTTP error (status !== 0) carries the backend detail; status 0 = no response (network).
      setError(
        err instanceof ApiError && err.status !== 0
          ? err.detail
          : 'Network error. Please try again in a moment.',
      )
    } finally {
      setIsSubmitting(false)
      // Cloudflare verifies a Turnstile token once (siteverify answers timeout-or-duplicate after), and the router
      // checks it before the honeypot, the referral code and the signup. A sent join may have spent its token (only
      // the rate limit answers before the check, and a lost request cannot say), so the form renews it after every
      // one: it drops the token and mounts a new widget, and the button waits for the new token. After a join that
      // lands, the form is gone.
      setTurnstileToken('')
      setTurnstileKey((key) => key + 1)
    }
  }

  // "Join without the code" navigates to /waitlist, with no ?ref=. Search params do not remount a page in the App
  // Router, so the form keeps what was typed. It drops the code here, as the link is followed: the URL keeps its
  // ?ref= until the router commits the navigation, and Enter in the email field can come first. The refusal clears,
  // and the focused link with it, so focus goes to the email field, where Enter submits. Link runs this as
  // onNavigate, only for a navigation in this tab: a Ctrl or Cmd click opens /waitlist in a new tab and leaves this
  // one, and its ?ref=, as they were.
  const joinWithoutCode = () => {
    setDroppedReferral(urlReferral)
    setReferralRefused(false)
    emailRef.current?.focus()
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
      <Card className="p-cap-6">
        <div className="flex items-center gap-2 text-brand-strong dark:text-brand-strong-dark">
          <CheckIcon className="h-5 w-5" />
          <span className="text-sm font-semibold uppercase tracking-eyebrow">You&apos;re in</span>
        </div>
        <h2 className="mt-3 text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
          {success.message || "You're on the waitlist."}
        </h2>
        <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
          Your current position is <span className="tnum font-data font-semibold">#{success.position}</span>.
        </p>

        <div className="mt-5 rounded-xl border border-border-light bg-background-light px-4 py-3 dark:border-border-dark dark:bg-background-dark">
          <div className="text-xs uppercase tracking-eyebrow text-text-tertiary-light dark:text-text-secondary-dark">
            Your referral link
          </div>
          <div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            {/* The data face: Inter's contextual alternates draw the x of a code such as p4x8n2wd as a
                multiplication sign; Geist Mono has none, so the link reads as Copy copies it. */}
            <span className="break-all font-data text-sm font-medium text-text-primary-light dark:text-text-primary-dark">
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
          Each person who joins with your link moves you up {REFERRAL_BONUS} spots.
        </div>

        {shareLinks && (
          <div className="mt-4 flex flex-wrap gap-3">
            <a href={shareLinks.twitter} target="_blank" rel="noreferrer" className={pillLinkClass}>
              Share on Twitter
            </a>
            <a href={shareLinks.linkedIn} target="_blank" rel="noreferrer" className={pillLinkClass}>
              Share on LinkedIn
            </a>
            <a href={shareLinks.whatsapp} target="_blank" rel="noreferrer" className={pillLinkClass}>
              Share on WhatsApp
            </a>
          </div>
        )}
      </Card>
    )
  }

  return (
    <Card as="form" onSubmit={handleSubmit} className="p-cap-6">
      <div className="flex flex-col gap-4">
        <div>
          <label
            htmlFor="waitlist-email"
            className="text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark"
          >
            Email address
          </label>
          <Input
            ref={emailRef}
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

        {referralRefused && (
          <Notice
            variant="error"
            title={unknownReferralTitle}
            description={unknownReferralDescription}
            action={
              // scroll={false}: the reader stays at the form, where focus goes.
              <Link href="/waitlist" scroll={false} onNavigate={joinWithoutCode} className={pillLinkClass}>
                Join without the code
              </Link>
            }
          />
        )}

        {error && <Notice variant="error" title={error} />}

        <TurnstileWidget key={turnstileKey} onToken={setTurnstileToken} />

        {/* The wait for a token is aria-disabled with handleSubmit's guard, never native disabled: the token renews
            after every join the form sends, while the button that sent it has focus, and Chromium moves focus to
            <body> from a focused button that turns disabled (lessons/frontend-busy-controls-stay-focusable.md (e)). */}
        <Button
          type="submit"
          loading={isSubmitting}
          loadingText="Joining waitlist..."
          aria-disabled={isSubmitting || tokenPending || undefined}
          // Refused while the token comes, so the browser's own validation never starts either: an empty required
          // field would take focus from a control announced unavailable. Enter in a field submits through this click.
          onClick={(event) => {
            if (tokenPending) event.preventDefault()
          }}
          className={cx('w-full', tokenPending && !isSubmitting && primaryUnavailableClass)}
        >
          Join the waitlist
        </Button>
      </div>
    </Card>
  )
}
