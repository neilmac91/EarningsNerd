'use client'

import { useState, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { getCurrentUser, login } from '@/features/auth/api/auth-api'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import Link from 'next/link'
import { Loader2, Mail } from 'lucide-react'
import StateCard from '@/components/StateCard'
import analytics from '@/lib/analytics'
import AuthShell from '@/components/auth/AuthShell'
import SocialAuthButtons from '@/components/auth/SocialAuthButtons'
import AuthDivider from '@/components/auth/AuthDivider'
import PasswordField from '@/components/auth/PasswordField'

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

  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? ''

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await login(email, password)
      try {
        const user = await getCurrentUser()
        if (user?.id && user?.email) {
          analytics.loginCompleted(String(user.id), user.email)
        }
      } catch {
        // Ignore analytics errors to avoid blocking login
      }
      router.push('/')
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
          <button
            type="button"
            onClick={() => setShowEmail(true)}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-border-light bg-transparent px-4 py-3 text-sm font-medium text-text-primary-light transition-all hover:bg-panel-light active:scale-[0.99] dark:border-border-dark dark:text-text-primary-dark dark:hover:bg-panel-dark focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mint-500"
          >
            <Mail className="h-4 w-4" />
            Continue with email
          </button>
        ) : (
          <form onSubmit={handleSubmit} className="animate-fade-up space-y-4">
            <div>
              <label
                htmlFor="email"
                className="mb-1 block text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark"
              >
                Email
              </label>
              <input
                type="email"
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                autoFocus
                className="w-full rounded-lg border border-border-light bg-background-light px-3 py-2 text-text-primary-light placeholder:text-text-tertiary-light focus:border-mint-500 focus:outline-none focus:ring-2 focus:ring-mint-500/50 dark:border-border-dark dark:bg-background-dark dark:text-text-primary-dark dark:placeholder:text-text-tertiary-dark"
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
                  className="text-xs text-mint-600 hover:underline dark:text-mint-400"
                >
                  Forgot password?
                </Link>
              }
            />

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-mint-500 py-2.5 font-semibold text-slate-950 transition-all hover:bg-mint-400 active:scale-[0.99] disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mint-500"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Signing in…
                </span>
              ) : (
                'Sign in'
              )}
            </button>
          </form>
        )}
      </div>

      <p className="mt-8 text-center text-sm text-text-secondary-light dark:text-text-secondary-dark">
        Don&apos;t have an account?{' '}
        <Link href="/register" className="font-medium text-mint-600 hover:underline dark:text-mint-400">
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
