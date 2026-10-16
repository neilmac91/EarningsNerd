'use client'

import { Suspense, useEffect, useState } from 'react'
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
import { Button, Input, Notice } from '@/components/ui'
import { FREE_SUMMARY_LIMIT } from '@/lib/planLimits'
import { PASSWORD_MIN_LENGTH, PASSWORD_RULE } from '@/lib/passwordRules'

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

  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? ''

  // Pro is promised only while the beta promo is configured. Invite-only and uninvited: no subhead,
  // the private-beta Notice below carries the message.
  const subhead =
    isInvited && betaPromoActive
      ? 'Finish setting up to get full Pro. No credit card required.'
      : !inviteOnly
        ? `${FREE_SUMMARY_LIMIT} free AI summaries a month. No credit card required.`
        : isInvited
          ? 'Your invite opens an account during the private beta.'
          : null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    // In flight: the submit stays focusable (DS Button `loading` sets aria-disabled, never native
    // disabled), so a repeat Enter must be ignored here. lessons/frontend-busy-controls-stay-focusable.md
    if (loading) return
    setError('')
    setLoading(true)
    analytics.signupStarted(isInvited ? 'register_invite' : 'register_page')

    try {
      // Verify-first signup: register returns an opaque message and sets no session (so we
      // can't reveal whether the email already existed). The user finishes via the email link
      // or by signing in. Always route to the same "check your email" page.
      await register(email, password, fullName, turnstileToken, inviteToken)
      analytics.signupSubmitted()
      router.push(`/check-email?email=${encodeURIComponent(email)}${redirectQuery}`)
    } catch (err: unknown) {
      const errorMessage = isApiError(err) ? getErrorMessage(err) : 'Registration failed'
      setError(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell>
      <h1 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
        Create your account
      </h1>
      {subhead && (
        <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">{subhead}</p>
      )}

      {isInvited && (
        <div className="mt-6 rounded-xl border border-brand-strong/20 bg-brand-strong/5 p-4 dark:border-brand-strong-dark/25 dark:bg-brand-strong-dark/10">
          <p className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">
            You&apos;re invited to the private beta
          </p>
          <p className="mt-1 text-sm text-text-secondary-light dark:text-text-secondary-dark">
            {betaPromoActive ? 'Your invite includes full Pro access. Create your account below.' : 'Create your account below.'}
          </p>
        </div>
      )}

      {!isInvited && inviteOnly && (
        <div className="mt-6">
          <Notice
            variant="info"
            title="EarningsNerd is in private beta"
            description={
              <>
                Creating an account needs an invite right now.{' '}
                <Link
                  href="/waitlist"
                  className="rounded-sm focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark font-medium text-brand-strong underline dark:text-brand-strong-dark"
                >
                  Request an invite
                </Link>
                , or sign in if you already have an account.
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

      <div className="mt-8">
        {socialSignupOffered && (
          <>
            <SocialAuthButtons
              apiBase={apiBase}
              invite={inviteToken || undefined}
              appleLabel="Sign up with Apple"
              googleLabel="Sign up with Google"
            />
            <AuthDivider />
          </>
        )}

        {!showEmail ? (
          <Button
            type="button"
            variant="ghost"
            onClick={() => setShowEmail(true)}
            className="w-full py-3 active:scale-[0.99]"
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
                autoFocus
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

            <TurnstileWidget onToken={setTurnstileToken} className="flex justify-center" />

            <Button
              type="submit"
              loading={loading}
              loadingText="Creating account…"
              disabled={TURNSTILE_ENABLED && !turnstileToken}
              className="w-full py-2.5 font-semibold active:scale-[0.99]"
            >
              Create account
            </Button>
          </form>
        )}
      </div>

      <p className="mt-6 text-center text-xs text-text-tertiary-light dark:text-text-secondary-dark">
        By creating an account you agree to our{' '}
        <Link href="/terms" className="rounded-sm focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark underline hover:text-brand-strong dark:hover:text-brand-strong-dark">
          Terms
        </Link>{' '}
        and{' '}
        <Link href="/privacy" className="rounded-sm focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark underline hover:text-brand-strong dark:hover:text-brand-strong-dark">
          Privacy Policy
        </Link>
        .
      </p>

      <p className="mt-6 text-center text-sm text-text-secondary-light dark:text-text-secondary-dark">
        Already have an account?{' '}
        <Link
          href={loginHrefWithRedirect(redirect)}
          className="rounded-sm focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark font-medium text-brand-strong hover:underline dark:text-brand-strong-dark"
        >
          Sign in
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
