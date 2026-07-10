'use client'

import { Suspense, useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { register } from '@/features/auth/api/auth-api'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import Link from 'next/link'
import { CircleNotchIcon, EnvelopeSimpleIcon } from '@/lib/icons'
import analytics from '@/lib/analytics'
import AuthShell from '@/features/auth/components/AuthShell'
import SocialAuthButtons from '@/features/auth/components/SocialAuthButtons'
import AuthDivider from '@/features/auth/components/AuthDivider'
import PasswordField from '@/features/auth/components/PasswordField'
import TurnstileWidget from '@/features/auth/components/TurnstileWidget'
import { TURNSTILE_ENABLED } from '@/lib/featureFlags'
import { loginHrefWithRedirect } from '@/lib/postAuthRedirect'
import { Button, Input, Notice } from '@/components/ui'

function RegisterContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  // Closed-beta magic link: /register?invite=<token>. Present → route the user straight to the
  // email flow (the invite is redeemed only by the email/password register endpoint; social signup
  // would bypass the gate), and pass the token through to the backend, which enforces it. We capture
  // it into state on mount so we can immediately strip it from the URL (keeping it out of history,
  // shoulder-surfing, and copy-pasted addresses) without losing it for the submit.
  const [inviteToken] = useState(() => searchParams.get('invite') ?? '')
  const isInvited = inviteToken.length > 0

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
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
      <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
        {isInvited
          ? 'Finish setting up to get full Pro. No credit card required.'
          : '5 free AI summaries a month. No credit card required.'}
      </p>

      {isInvited && (
        <div className="mt-6 rounded-xl border border-brand-strong/20 bg-brand-strong/5 p-4 dark:border-brand-strong-dark/25 dark:bg-brand-strong-dark/10">
          <p className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">
            You&apos;re invited to the private beta
          </p>
          <p className="mt-1 text-sm text-text-secondary-light dark:text-text-secondary-dark">
            Your invite includes full Pro access. Create your account with the email and password below.
          </p>
        </div>
      )}

      {error && (
        <div className="mt-6">
          <Notice variant="error" title="Registration failed" description={error} />
        </div>
      )}

      <div className="mt-8">
        {/* Social signup bypasses the invite gate (it doesn't hit /register), so hide it on the
            invited path and offer only the email flow that redeems the invite. */}
        {!isInvited && (
          <>
            <SocialAuthButtons apiBase={apiBase} appleLabel="Sign up with Apple" googleLabel="Sign up with Google" />
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
          <form onSubmit={handleSubmit} className="animate-fade-up space-y-4">
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
              minLength={12}
              showStrength
              hint="At least 12 characters. A longer passphrase is stronger. Breached passwords are rejected."
            />

            <TurnstileWidget onToken={setTurnstileToken} className="flex justify-center" />

            <Button
              type="submit"
              disabled={loading || (TURNSTILE_ENABLED && !turnstileToken)}
              className="w-full py-2.5 font-semibold active:scale-[0.99]"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <CircleNotchIcon className="h-4 w-4 animate-spin" />
                  Creating account…
                </span>
              ) : (
                'Create account'
              )}
            </Button>
          </form>
        )}
      </div>

      <p className="mt-6 text-center text-xs text-text-tertiary-light dark:text-text-secondary-dark">
        By creating an account you agree to our{' '}
        <Link href="/terms" className="underline hover:text-brand-strong dark:hover:text-brand-strong-dark">
          Terms
        </Link>{' '}
        and{' '}
        <Link href="/privacy" className="underline hover:text-brand-strong dark:hover:text-brand-strong-dark">
          Privacy Policy
        </Link>
        .
      </p>

      <p className="mt-6 text-center text-sm text-text-secondary-light dark:text-text-secondary-dark">
        Already have an account?{' '}
        <Link
          href={loginHrefWithRedirect(redirect)}
          className="font-medium text-brand-strong hover:underline dark:text-brand-strong-dark"
        >
          Sign in
        </Link>
      </p>
    </AuthShell>
  )
}

export default function RegisterPage() {
  return (
    <Suspense>
      <RegisterContent />
    </Suspense>
  )
}
