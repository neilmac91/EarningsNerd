'use client'

import { useState, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useQueryClient } from '@tanstack/react-query'
import { getCurrentUserSafe, login, type CurrentUser } from '@/features/auth/api/auth-api'
import { queryKeys } from '@/lib/queryKeys'
import { acceptLoginAndResetAccount } from '@/features/auth/lib/accountQueryState'
import { getExplicitSessionGeneration, assertExplicitSessionGeneration } from '@/lib/api/session'
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
import { consumePostAuthRedirect } from '@/lib/postAuthRedirect'
import { Button, Input, Notice } from '@/components/ui'

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
  const queryClient = useQueryClient()
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

    const explicitGeneration = getExplicitSessionGeneration()
    try {
      await login(email, password, turnstileToken)
      // Cancel the old identity and remove both account snapshots before resolving this login.
      // Reset leaves the active marker set by successful login intact.
      const acceptedGeneration = acceptLoginAndResetAccount(queryClient, explicitGeneration)
      void queryClient.invalidateQueries({ queryKey: queryKeys.subscription.all() })
      void queryClient.invalidateQueries({ queryKey: queryKeys.usage.all() })
      let user: CurrentUser | null | undefined
      try {
        user = await queryClient.fetchQuery({
          queryKey: queryKeys.currentUser(), queryFn: getCurrentUserSafe, staleTime: 0,
        })
      } catch {
        // A temporary identity error does not block login; ownership is checked below even
        // when cancellation/errors were caught, so a later logout cannot be overwritten.
      }
      assertExplicitSessionGeneration(acceptedGeneration)
      try {
        if (user?.id) analytics.loginCompleted(String(user.id))
      } catch {
        // Analytics must not block an otherwise current login.
      }
      // Return the user to where they were headed before the auth gate. Only honour internal,
      // single-slash-rooted paths: reject protocol-relative ("//evil") and backslash-prefixed
      // ("/\\evil") values, which some browsers normalise into open redirects to external sites.
      // Fallback: the signup gate's stashed destination (consume-once, validated, 1h TTL) — it
      // survives the verification email's new-tab hop, which the ?redirect= thread cannot.
      const dest = searchParams.get('redirect') ?? consumePostAuthRedirect()
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
      <h1 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
        Welcome back
      </h1>
      <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
        Sign in to continue to EarningsNerd.
      </p>

      {oauthError && (
        <div className="mt-6">
          <Notice
            variant="error"
            title="Sign-in failed"
            description={OAUTH_ERROR_MESSAGES[oauthError] ?? 'Sign-in failed. Please try again.'}
          />
        </div>
      )}

      {error && (
        <div className="mt-6">
          <Notice variant="error" title="Login failed" description={error} />
        </div>
      )}

      <div className="mt-8">
        <SocialAuthButtons apiBase={apiBase} />

        <AuthDivider />

        {!showEmail ? (
          <Button
            type="button"
            variant="ghost"
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
