'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { register } from '@/features/auth/api/auth-api'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import Link from 'next/link'
import { Loader2, Mail } from 'lucide-react'
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

export default function RegisterPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showEmail, setShowEmail] = useState(false)
  const [turnstileToken, setTurnstileToken] = useState('')

  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? ''

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    analytics.signupStarted('register_page')

    try {
      // Verify-first signup: register returns an opaque message and sets no session (so we
      // can't reveal whether the email already existed). The user finishes via the email link
      // or by signing in. Always route to the same "check your email" page.
      await register(email, password, fullName, turnstileToken)
      analytics.signupSubmitted()
      router.push(`/check-email?email=${encodeURIComponent(email)}`)
    } catch (err: unknown) {
      const errorMessage = isApiError(err) ? getErrorMessage(err) : 'Registration failed'
      setError(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell>
      <h1 className="text-2xl font-bold text-text-primary-light dark:text-text-primary-dark">
        Create your account
      </h1>
      <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
        5 free AI summaries a month — no credit card required.
      </p>

      {error && (
        <div className="mt-6">
          <StateCard variant="error" title="Registration failed" message={error} />
        </div>
      )}

      <div className="mt-8">
        <SocialAuthButtons apiBase={apiBase} appleLabel="Sign up with Apple" googleLabel="Sign up with Google" />

        <AuthDivider />

        {!showEmail ? (
          <Button
            type="button"
            variant="tertiary"
            onClick={() => setShowEmail(true)}
            className="w-full py-3 active:scale-[0.99]"
          >
            <Mail className="h-4 w-4" />
            Sign up with email
          </Button>
        ) : (
          <form onSubmit={handleSubmit} className="animate-fade-up space-y-4">
            <div>
              <label
                htmlFor="fullName"
                className="mb-1 block text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark"
              >
                Full name <span className="text-text-tertiary-light dark:text-text-tertiary-dark">(optional)</span>
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
              hint="At least 12 characters — a longer passphrase is stronger. Breached passwords are rejected."
            />

            <TurnstileWidget onToken={setTurnstileToken} className="flex justify-center" />

            <Button
              type="submit"
              disabled={loading || (TURNSTILE_ENABLED && !turnstileToken)}
              className="w-full py-2.5 font-semibold active:scale-[0.99]"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Creating account…
                </span>
              ) : (
                'Create account'
              )}
            </Button>
          </form>
        )}
      </div>

      <p className="mt-6 text-center text-xs text-text-tertiary-light dark:text-text-tertiary-dark">
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
        <Link href="/login" className="font-medium text-brand-strong hover:underline dark:text-brand-strong-dark">
          Sign in
        </Link>
      </p>
    </AuthShell>
  )
}
