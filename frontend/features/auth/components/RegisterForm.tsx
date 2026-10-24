'use client'

import { Suspense, useEffect, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { register } from '@/features/auth/api/auth-api'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import Link from 'next/link'
import { EnvelopeSimpleIcon } from '@/lib/icons'
import analytics from '@/lib/analytics'
import AuthShell from '@/features/auth/components/AuthShell'
import SocialAuthButtons from '@/features/auth/components/SocialAuthButtons'
import AuthDivider from '@/features/auth/components/AuthDivider'
import PasswordField from '@/features/auth/components/PasswordField'
import TurnstileWidget from '@/features/auth/components/TurnstileWidget'
import { TURNSTILE_ENABLED } from '@/lib/featureFlags'
import { loginHrefWithRedirect } from '@/lib/postAuthRedirect'
import { Button, Checkbox, Input, Notice, cx, primaryUnavailableClass } from '@/components/ui'
import { FREE_SUMMARY_LIMIT } from '@/lib/planLimits'
import { PASSWORD_MIN_LENGTH, PASSWORD_RULE } from '@/lib/passwordRules'
import { useLegalReadiness } from '@/features/legal/hooks/useLegalReadiness'
import { CollectionUnavailable } from '@/features/legal/components/CollectionGate'
import { RegistrationLoading } from '@/features/legal/components/CollectionLoading'
import type { AccountAgreement } from '@/features/legal/api/legal-api'
import { ACCOUNT_TERMS_VERSION, ACCOUNT_ELIGIBILITY_VERSION, isAccountPolicyCurrent } from '@/features/legal/policy'

const legalLinkClass = 'box-decoration-clone rounded-sm font-medium text-brand-strong underline underline-offset-4 focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark'

export interface RegisterFormProps {
  /**
   * True while the backend's REGISTRATION_MODE is invite_only (or unknown — the page fails closed).
   * The backend enforces the gate on every creation path (email and social); this only decides
   * what to offer an uninvited visitor.
   */
  inviteOnly: boolean
  /**
   * True only while the closed beta runs with the server's 100%-off Pro promo configured
   * (`betaPricingActive` in features/marketing/lib/access.ts, from the same /api/auth/registration
   * read). An invited visitor is promised Pro only then. Presentation only: billing is unchanged.
   */
  betaPromoActive: boolean
}

function RegisterContent({ inviteOnly, betaPromoActive }: RegisterFormProps) {
  const router = useRouter()
  const { readiness, loading: checkingReadiness, recheck } = useLegalReadiness()
  const policyMismatch = readiness?.collection_available === true && !isAccountPolicyCurrent(readiness)
  const collectionAvailable = readiness?.collection_available === true && !policyMismatch
  const betaOfferAvailable = betaPromoActive && readiness?.checkout_available === true
  const [adultEligible, setAdultEligible] = useState(false)
  const [termsAccepted, setTermsAccepted] = useState(false)
  const agreementReady = adultEligible && termsAccepted
  const [requirementsError, setRequirementsError] = useState(false)
  const adultRef = useRef<HTMLInputElement>(null)
  const termsRef = useRef<HTMLInputElement>(null)
  const wasAvailable = useRef(false)
  const statusRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (wasAvailable.current && !collectionAvailable && document.activeElement === document.body) {
      statusRef.current?.focus({ preventScroll: true })
    }
    wasAvailable.current = collectionAvailable
  }, [collectionAvailable])
  const searchParams = useSearchParams()
  // Closed-beta magic link: /register?invite=<token>. Present → open the email form straight away
  // and pass the token through to every signup path: the register endpoint takes it in the body and
  // the social buttons carry it to /api/auth/google|apple, which redeem it when they create the
  // account. The backend enforces it either way. We capture it into state on mount so we can
  // immediately strip it from the URL (keeping it out of history, shoulder-surfing, and copy-pasted
  // addresses) without losing it for the submit.
  const [inviteToken] = useState(() => searchParams.get('invite') ?? '')
  const isInvited = inviteToken.length > 0
  // Uninvited visitors in invite-only mode get no social buttons: that sign-in would only bounce
  // back to /login?error=invite_required.
  const socialSignupOffered = isInvited || !inviteOnly

  // Where the visitor was headed before the signup gate (e.g. /filing/123). Forwarded through
  // check-email to login, which validates it (internal paths only) before navigating — so this
  // page only ever passes it along, never acts on it.
  const redirect = searchParams.get('redirect') ?? ''
  const redirectQuery = redirect ? `&redirect=${encodeURIComponent(redirect)}` : ''

  // Scrub only ?invite=<token> from the address bar once it's captured in state, preserving any
  // other query params (utm_*, ref, etc.).
  useEffect(() => {
    if (typeof window === 'undefined') return
    const params = new URLSearchParams(window.location.search)
    if (!params.has('invite')) return
    params.delete('invite')
    const search = params.toString()
    window.history.replaceState({}, '', window.location.pathname + (search ? `?${search}` : ''))
  }, [])

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showEmail, setShowEmail] = useState(isInvited)
  const [turnstileToken, setTurnstileToken] = useState('')
  // A new key mounts a new Turnstile widget, which issues a new token (see handleSubmit's finally).
  const [turnstileKey, setTurnstileKey] = useState(0)
  // With Turnstile on, a registration waits for a token: when the email form opens (at load, with an invite), while
  // a new one is issued after each one the form sends, and after one expires.
  const tokenPending = TURNSTILE_ENABLED && !turnstileToken

  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? ''

  // Pro is promised only while the beta promo is configured. Invite-only and uninvited: no subhead,
  // the private-beta Notice below carries the message.
  const subhead =
    isInvited && betaOfferAvailable
      ? 'Finish setting up to get full Pro. No credit card required.'
      : !inviteOnly
        ? `${FREE_SUMMARY_LIMIT} free AI summaries a month. No credit card required.`
        : isInvited
          ? 'Your invite opens an account during the private beta.'
          : null

  const confirmRequirements = () => {
    if (agreementReady) return true
    setRequirementsError(true)
    ;(adultEligible ? termsRef : adultRef).current?.focus()
    return false
  }

  const prepareAgreement = async (): Promise<AccountAgreement | null> => {
    if (!collectionAvailable || !readiness || !confirmRequirements()) return null
    const fresh = await recheck()
    if (!fresh?.collection_available) return null
    if (!isAccountPolicyCurrent(fresh)) {
      setAdultEligible(false)
      setTermsAccepted(false)
      return null
    }
    return { adult_eligible: true, terms_accepted: true, terms_version: ACCOUNT_TERMS_VERSION, eligibility_version: ACCOUNT_ELIGIBILITY_VERSION }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    // In flight: the submit stays focusable (DS Button `loading` sets aria-disabled, never native
    // disabled), so a repeat Enter must be ignored here. lessons/frontend-busy-controls-stay-focusable.md
    // The wait for a Turnstile token is aria-disabled too, so a press or Enter sends nothing until it comes.
    if (loading || !collectionAvailable || !confirmRequirements() || tokenPending) return
    setError('')
    setLoading(true)

    try {
      const agreement = await prepareAgreement()
      if (!agreement) return
      analytics.signupStarted(isInvited ? 'register_invite' : 'register_page')
      // Verify-first signup: register returns an opaque message and sets no session (so we
      // can't reveal whether the email already existed). The user finishes via the email link
      // or by signing in. Always route to the same "check your email" page.
      await register(email, password, fullName, turnstileToken, inviteToken, agreement)
      analytics.signupSubmitted()
      router.push(`/check-email?email=${encodeURIComponent(email)}${redirectQuery}`)
    } catch (err: unknown) {
      const errorMessage = isApiError(err) ? getErrorMessage(err) : 'Registration failed'
      setError(errorMessage)
    } finally {
      setLoading(false)
      // Cloudflare verifies a Turnstile token once (siteverify answers timeout-or-duplicate after), and the route
      // checks it right after the rate limit, so a sent registration may have spent its token whatever it answered. The form
      // renews it after every one, as WaitlistForm does: it drops the token and mounts a new widget, and the button
      // waits for the new token. A registration that succeeds renews it too: until the page leaves, a second press
      // then waits for the new token rather than sending the spent one, which the route would refuse with a 403.
      setTurnstileToken('')
      setTurnstileKey((key) => key + 1)
    }
  }

  return (
    <AuthShell alignTop>
      <h1 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
        Create your account
      </h1>
      {collectionAvailable && subhead && (
        <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">{subhead}</p>
      )}

      {collectionAvailable && isInvited && (
        <div className="mt-6 rounded-xl border border-brand-strong/20 bg-brand-strong/5 p-4 dark:border-brand-strong-dark/25 dark:bg-brand-strong-dark/10">
          <p className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">
            You&apos;re invited to the private beta
          </p>
          <p className="mt-1 text-sm text-text-secondary-light dark:text-text-secondary-dark">
            {betaOfferAvailable ? 'Your invite includes full Pro access. Create your account below.' : 'Create your account below.'}
          </p>
        </div>
      )}

      {collectionAvailable && !isInvited && inviteOnly && (
        <div className="mt-6">
          <Notice
            variant="info"
            title="EarningsNerd is in private beta"
            description={
              <>
                Creating an account needs an invite right now.{' '}
                <Link
                  href="/waitlist"
                  className="box-decoration-clone rounded-sm focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark font-medium text-brand-strong underline dark:text-brand-strong-dark"
                >
                  Request an invite
                </Link>
                , or log in if you already have an account.
              </>
            }
          />
        </div>
      )}

      {error && (
        <div className="mt-6">
          <Notice variant="error" title="Registration failed" description={error} />
        </div>
      )}

      {checkingReadiness ? (
        <RegistrationLoading invited={isInvited} emailVisible={showEmail} socialOffered={socialSignupOffered} />
      ) : !collectionAvailable ? (
        <div ref={statusRef} tabIndex={-1} className="mt-8 rounded-lg focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">
          <CollectionUnavailable
            title={policyMismatch ? 'Registration needs a refresh' : 'Registration is currently closed'}
            showLogin={false}
            description={policyMismatch ? 'The account requirements have changed. Refresh this page to load the current Terms and eligibility requirements before signing up.' : undefined}
          />
        </div>
      ) : <div className="mt-8">
        <fieldset className="mb-6 space-y-3" aria-describedby={requirementsError ? 'account-requirements-error' : undefined}>
          <legend className="mb-3 text-sm font-medium text-text-primary-light dark:text-text-primary-dark">Account requirements</legend>
          <label className="flex items-start gap-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">
            <Checkbox ref={adultRef} checked={adultEligible} aria-describedby={requirementsError ? 'account-requirements-error' : undefined} onChange={(event) => {
              setAdultEligible(event.target.checked)
              if (event.target.checked && termsAccepted) setRequirementsError(false)
            }} />
            <span>I am at least 18 and legally an adult where I live.</span>
          </label>
          <label className="flex items-start gap-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">
            <Checkbox ref={termsRef} checked={termsAccepted} aria-describedby={requirementsError ? 'account-requirements-error' : undefined} onChange={(event) => {
              setTermsAccepted(event.target.checked)
              if (event.target.checked && adultEligible) setRequirementsError(false)
            }} />
            <span>I agree to the{' '}<Link href="/terms" className={legalLinkClass}>Terms of Service</Link>.</span>
          </label>
          <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">Read how we handle personal data in our{' '}<Link href="/privacy" className={legalLinkClass}>Privacy Policy</Link>.</p>
          {requirementsError && <p id="account-requirements-error" role="alert" className="text-sm text-error-light dark:text-error-dark">Confirm both statements to create an account.</p>}
        </fieldset>
        {socialSignupOffered && (
          <>
            <SocialAuthButtons
              apiBase={apiBase}
              invite={inviteToken || undefined}
              signup={{ ready: !loading, prepare: prepareAgreement }}
            />
            <AuthDivider />
          </>
        )}

        {!showEmail ? (
          <Button
            type="button"
            variant="ghost"
            onClick={() => setShowEmail(true)}
            className="w-full active:scale-[0.99]"
          >
            <EnvelopeSimpleIcon className="h-4 w-4" />
            Sign up with email
          </Button>
        ) : (
          <form onSubmit={handleSubmit} className="animate-fade-up motion-reduce:animate-none space-y-4">
            <div>
              <label
                htmlFor="fullName"
                className="mb-1 block text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark"
              >
                Full name <span className="text-text-tertiary-light dark:text-text-secondary-dark">(optional)</span>
              </label>
              <Input
                type="text"
                id="fullName"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                autoComplete="name"
                autoFocus={!isInvited}
              />
            </div>

            <div>
              <label
                htmlFor="email"
                className="mb-1 block text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark"
              >
                Email
              </label>
              <Input
                type="email"
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>

            <PasswordField
              id="password"
              label="Password"
              value={password}
              onChange={setPassword}
              autoComplete="new-password"
              required
              minLength={PASSWORD_MIN_LENGTH}
              showStrength
              hint={PASSWORD_RULE}
            />

            <TurnstileWidget key={turnstileKey} onToken={setTurnstileToken} className="flex justify-center" />

            {/* The wait for a token is aria-disabled with handleSubmit's guard, never native disabled: the token renews
                after every registration the form sends, while the button that sent it has focus, and Chromium moves
                focus to <body> from a focused button that turns disabled (lessons/frontend-busy-controls-stay-focusable.md (e)). */}
            <Button
              type="submit"
              loading={loading}
              loadingText="Creating account…"
              aria-disabled={loading || tokenPending || undefined}
              // Refused while the token comes, so the browser's own validation never starts either: an empty required
              // field would take focus from a control announced unavailable. Enter in a field submits through this click.
              onClick={(event) => {
                if (!confirmRequirements() || tokenPending) event.preventDefault()
              }}
              className={cx('w-full py-2.5 font-semibold active:scale-[0.99]', tokenPending && !loading && primaryUnavailableClass)}
            >
              Create account
            </Button>
          </form>
        )}
      </div>}

      <p className="mt-6 text-center text-sm text-text-secondary-light dark:text-text-secondary-dark">
        Already have an account?{' '}
        <Link
          href={loginHrefWithRedirect(redirect)}
          className="rounded-sm focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark font-medium text-brand-strong hover:underline dark:text-brand-strong-dark"
        >
          Log in
        </Link>
      </p>
    </AuthShell>
  )
}

export default function RegisterForm({ inviteOnly, betaPromoActive }: RegisterFormProps) {
  return (
    <Suspense>
      <RegisterContent inviteOnly={inviteOnly} betaPromoActive={betaPromoActive} />
    </Suspense>
  )
}
