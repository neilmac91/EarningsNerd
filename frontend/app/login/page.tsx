'use client'

import { useState, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { getCurrentUser, login } from '@/features/auth/api/auth-api'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import Link from 'next/link'
import { CircleNotchIcon, EnvelopeSimpleIcon } from '@/lib/icons'
import StateCard from '@/components/StateCard'
import analytics from '@/lib/analytics'
import AuthShell from '@/components/auth/AuthShell'
import SocialAuthButtons from '@/components/auth/SocialAuthButtons'
import AuthDivider from '@/components/auth/AuthDivider'
import PasswordField from '@/components/auth/PasswordField'
import TurnstileWidget from '@/components/auth/TurnstileWidget'
import { TURNSTILE_ENABLED } from '@/lib/featureFlags'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'

const OAUTH_ERROR_MESSAGES: Record<string, string> = {
  google_denied: 'Google sign-in was cancelled.',
  google_invalid: 'Google sign-in failed. Please try again.',
  oauth_state_mismatch: 'Sign-in session expired. Please try again.',
  google_token_failed: 'Could not complete Google sign-in. Please try again.',
  google_userinfo_failed: 'Could not retrieve your Google account info. Please try again.',
  google_missing_claims: 'Google did not return an email address. Please try again.',
  google_account_conflict: 'An account conflict occurred. Please contact support.',
  apple_denied: 'Apple sign-in was cancelled.',
  apple_invalid: 'Apple sign-in failed. Please try again.',
}

function LoginContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const oauthError = searchParams.get('error')

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showEmail, setShowEmail] = useState(false)
  const [turnstileToken, setTurnstileToken] = useState('')

  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? ''

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await login(email, password, turnstileToken)
      try {
        const user = await getCurrentUser()
        if (user?.id) {
          analytics.loginCompleted(String(user.id))
        }
      } catch {
        // Ignore analytics errors to avoid blocking login
      }
      // Return the user to where they were headed before the auth gate. Only honour internal,
      // single-slash-rooted paths: reject protocol-relative ("//evil") and backslash-prefixed
      // ("/\\evil") values, which some browsers normalise into open redirects to external sites.
      const dest = searchParams.get('redirect')
      const safe =
        dest && dest.startsWith('/') && !dest.startsWith('//') && !dest.startsWith('/\\')
          ? dest
          : '/'
      router.push(safe)
      router.refresh()
    } catch (err: unknown) {
      const errorMessage = isApiError(err)
        ? getErrorMessage(err)
        : 'Login failed. Please check your credentials.'
      setError(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell>
      <h1 className="text-2xl font-bold text-text-primary-light dark:text-text-primary-dark">
        Welcome back
      </h1>
      <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
        Sign in to continue to EarningsNerd.
      </p>

      {oauthError && (
        <div className="mt-6">
          <StateCard
            variant="error"
            title="Sign-in failed"
            message={OAUTH_ERROR_MESSAGES[oauthError] ?? 'Sign-in failed. Please try again.'}
          />
        </div>
      )}

      {error && (
        <div className="mt-6">
          <StateCard variant="error" title="Login failed" message={error} />
        </div>
      )}

      <div className="mt-8">
        <SocialAuthButtons apiBase={apiBase} />

        <AuthDivider />

        {!showEmail ? (
          <Button
            type="button"
            variant="tertiary"
            onClick={() => setShowEmail(true)}
            className="w-full py-3 active:scale-[0.99]"
          >
            <EnvelopeSimpleIcon className="h-4 w-4" />
            Continue with email
          </Button>
        ) : (
          <form onSubmit={handleSubmit} className="animate-fade-up space-y-4">
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
                autoFocus
              />
            </div>

            <PasswordField
              id="password"
              label="Password"
              value={password}
              onChange={setPassword}
              autoComplete="current-password"
              required
              labelAction={
                <Link
                  href="/forgot-password"
                  className="text-xs text-brand-strong hover:underline dark:text-brand-strong-dark"
                >
                  Forgot password?
                </Link>
              }
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
                  Signing in…
                </span>
              ) : (
                'Sign in'
              )}
            </Button>
          </form>
        )}
      </div>

      <p className="mt-8 text-center text-sm text-text-secondary-light dark:text-text-secondary-dark">
        Don&apos;t have an account?{' '}
        <Link href="/register" className="font-medium text-brand-strong hover:underline dark:text-brand-strong-dark">
          Sign up
        </Link>
      </p>
    </AuthShell>
  )
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginContent />
    </Suspense>
  )
}
