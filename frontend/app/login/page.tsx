'use client'

import { useState, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getCurrentUserSafe, login, type CurrentUser } from '@/features/auth/api/auth-api'
import { getRegistrationConfig } from '@/features/marketing/api/access-api'
import { ACCESS_COPY, resolveAccessMode } from '@/features/marketing/lib/access'
import { queryKeys } from '@/lib/queryKeys'
import { acceptLoginAndResetAccount } from '@/features/auth/lib/accountQueryState'
import { getExplicitSessionGeneration, assertExplicitSessionGeneration } from '@/lib/api/session'
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
import { consumePostAuthRedirect } from '@/lib/postAuthRedirect'
import { Button, Input, Notice, cx, primaryUnavailableClass } from '@/components/ui'

/**
 * Google or Apple returned an email an existing EarningsNerd account holds, and the two were not linked
 * (`backend/app/services/oauth_account_service.py`): the email is unverified on the account or at the
 * provider, or this first sign-in lost a race to a parallel one that created the account. The account
 * may have no password (made through a provider), so the sentence sends the reader back the way it was
 * made. Verifying links nothing by itself: `resolve_google_user` / `resolve_apple_user` link on a later
 * provider sign-in, once both sides have verified the email, so the sentence names that next step.
 */
const accountConflict = (provider: 'Google' | 'Apple') =>
  `This email already has an EarningsNerd account, and the two could not be linked. Log in the way you created that account and verify your email. Once the email is verified on EarningsNerd and ${provider}, try ${provider} again.`

const OAUTH_ERROR_MESSAGES: Record<string, string> = {
  google_denied: 'Google login was cancelled.',
  google_invalid: 'Google login failed. Please try again.',
  oauth_state_mismatch: 'Login session expired. Please try again.',
  google_token_failed: 'Could not complete Google login. Please try again.',
  google_userinfo_failed: 'Could not retrieve your Google account info. Please try again.',
  google_missing_claims: 'Google did not return an email address. Please try again.',
  google_account_conflict: accountConflict('Google'),
  apple_denied: 'Apple login was cancelled.',
  apple_invalid: 'Apple login failed. Please try again.',
  apple_missing_claims: 'Apple did not return an email address. Please try again.',
  apple_account_conflict: accountConflict('Apple'),
  invite_required:
    'EarningsNerd is in private beta: creating an account needs an invite. Log in with an existing account, or open your invite link to sign up.',
  email_unverified:
    'Your login provider has not verified that email address. Verify it with the provider, or sign up with an email and password.',
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
  // A new key mounts a new Turnstile widget, which issues a new token (see handleSubmit's finally).
  const [turnstileKey, setTurnstileKey] = useState(0)
  // With Turnstile on, a login waits for a token: when the email form opens, while a new one is issued after each
  // login the form sends, and after one expires.
  const tokenPending = TURNSTILE_ENABLED && !turnstileToken

  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? ''

  // The link for a visitor without an account follows the one access decision (features/marketing/lib/
  // access.ts), read from the registration payload as /pricing and the calendar's bell read it: "Request an
  // invite" to /waitlist while registration is by invite, the free account when it is public. Until the
  // payload answers, and when it cannot, it fails closed to the invite.
  const { data: registration } = useQuery({
    queryKey: queryKeys.registrationConfig(),
    queryFn: getRegistrationConfig,
    retry: false,
    staleTime: 60 * 60 * 1000,
  })
  const account = ACCESS_COPY[resolveAccessMode(registration ?? null)]

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    // The wait for a Turnstile token is aria-disabled, as `loading` is, so a press or Enter sends nothing until it comes.
    if (loading || tokenPending) return
    setError('')
    setLoading(true)

    const explicitGeneration = getExplicitSessionGeneration()
    try {
      await login(email, password, turnstileToken)
      // Cancel the old identity and remove every account family before resolving this login.
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
      // Consume even when the explicit destination wins, so a completed login cannot leave a
      // stale signup destination waiting for a later, unrelated login.
      const stashedDestination = consumePostAuthRedirect()
      const dest = searchParams.get('redirect') ?? stashedDestination
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
      // Cloudflare verifies a Turnstile token once (siteverify answers timeout-or-duplicate after), and the route
      // checks it right after the rate limit, so a sent login may have spent its token whatever it answered. The form
      // renews it after every one, as WaitlistForm does: it drops the token and mounts a new widget, and the button
      // waits for the new token. A login that succeeds renews it too: until the page leaves, a second press then
      // waits for the new token rather than sending the spent one, which the route would refuse with a 403.
      setTurnstileToken('')
      setTurnstileKey((key) => key + 1)
    }
  }

  return (
    <AuthShell>
      <h1 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
        Welcome back
      </h1>
      <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
        Log in to continue to EarningsNerd.
      </p>

      {oauthError && (
        <div className="mt-6">
          <Notice
            variant="error"
            title="Login failed"
            description={OAUTH_ERROR_MESSAGES[oauthError] ?? 'Login failed. Please try again.'}
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
            className="w-full active:scale-[0.99]"
          >
            <EnvelopeSimpleIcon className="h-4 w-4" />
            Continue with email
          </Button>
        ) : (
          <form onSubmit={handleSubmit} className="animate-fade-up motion-reduce:animate-none space-y-4">
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
                  className="rounded-sm focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark text-xs text-brand-strong hover:underline dark:text-brand-strong-dark"
                >
                  Forgot password?
                </Link>
              }
            />

            <TurnstileWidget key={turnstileKey} onToken={setTurnstileToken} className="flex justify-center" />

            {/* The wait for a token is aria-disabled with handleSubmit's guard, never native disabled: the token renews
                after every login the form sends, while the button that sent it has focus, and Chromium moves focus to
                <body> from a focused button that turns disabled (lessons/frontend-busy-controls-stay-focusable.md (e)). */}
            <Button
              type="submit"
              loading={loading}
              loadingText="Logging in…"
              aria-disabled={loading || tokenPending || undefined}
              className={cx('w-full', tokenPending && !loading && primaryUnavailableClass)}
            >
              Log in
            </Button>
          </form>
        )}
      </div>

      <p className="mt-8 text-center text-sm text-text-secondary-light dark:text-text-secondary-dark">
        Don&apos;t have an account?{' '}
        <Link href={account.href} className="inline-block rounded-sm focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark font-medium text-brand-strong hover:underline dark:text-brand-strong-dark">
          {account.cta}
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
