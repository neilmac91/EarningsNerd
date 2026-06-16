'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { getCurrentUser, register } from '@/features/auth/api/auth-api'
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
      await register(email, password, fullName, turnstileToken)
      try {
        const user = await getCurrentUser()
        if (user?.id && user?.email) {
          analytics.signupCompleted(String(user.id), user.email)
        }
      } catch {
        // Ignore analytics errors to avoid blocking signup
      }
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
        Start your free trial and unlock AI summaries.
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
          <button
            type="button"
            onClick={() => setShowEmail(true)}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-border-light bg-transparent px-4 py-3 text-sm font-medium text-text-primary-light transition-all hover:bg-panel-light active:scale-[0.99] dark:border-border-dark dark:text-text-primary-dark dark:hover:bg-panel-dark focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mint-500"
          >
            <Mail className="h-4 w-4" />
            Sign up with email
          </button>
        ) : (
          <form onSubmit={handleSubmit} className="animate-fade-up space-y-4">
            <div>
              <label
                htmlFor="fullName"
                className="mb-1 block text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark"
              >
                Full name <span className="text-text-tertiary-light dark:text-text-tertiary-dark">(optional)</span>
              </label>
              <input
                type="text"
                id="fullName"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                autoComplete="name"
                autoFocus
                className="w-full rounded-lg border border-border-light bg-background-light px-3 py-2 text-text-primary-light placeholder:text-text-tertiary-light focus:border-mint-500 focus:outline-none focus:ring-2 focus:ring-mint-500/50 dark:border-border-dark dark:bg-background-dark dark:text-text-primary-dark dark:placeholder:text-text-tertiary-dark"
              />
            </div>

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
                className="w-full rounded-lg border border-border-light bg-background-light px-3 py-2 text-text-primary-light placeholder:text-text-tertiary-light focus:border-mint-500 focus:outline-none focus:ring-2 focus:ring-mint-500/50 dark:border-border-dark dark:bg-background-dark dark:text-text-primary-dark dark:placeholder:text-text-tertiary-dark"
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

            <button
              type="submit"
              disabled={loading || (TURNSTILE_ENABLED && !turnstileToken)}
              className="w-full rounded-lg bg-mint-500 py-2.5 font-semibold text-slate-950 transition-all hover:bg-mint-400 active:scale-[0.99] disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mint-500"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Creating account…
                </span>
              ) : (
                'Create account'
              )}
            </button>
          </form>
        )}
      </div>

      <p className="mt-8 text-center text-sm text-text-secondary-light dark:text-text-secondary-dark">
        Already have an account?{' '}
        <Link href="/login" className="font-medium text-mint-600 hover:underline dark:text-mint-400">
          Sign in
        </Link>
      </p>
    </AuthShell>
  )
}
