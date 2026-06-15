'use client'

import { useState } from 'react'
import { forgotPassword } from '@/features/auth/api/auth-api'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import Link from 'next/link'
import { Loader2, MailCheck } from 'lucide-react'
import StateCard from '@/components/StateCard'
import AuthShell from '@/components/auth/AuthShell'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await forgotPassword(email)
      setSubmitted(true)
    } catch (err: unknown) {
      setError(isApiError(err) ? getErrorMessage(err) : 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell>
      {!submitted ? (
        <>
          <h1 className="text-2xl font-bold text-text-primary-light dark:text-text-primary-dark">
            Reset your password
          </h1>
          <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
            Enter your email and we&apos;ll send you a reset link.
          </p>

          {error && (
            <div className="mt-6">
              <StateCard variant="error" title="Error" message={error} />
            </div>
          )}

          <form onSubmit={handleSubmit} className="mt-8 space-y-4">
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

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-mint-500 py-2.5 font-semibold text-slate-950 transition-all hover:bg-mint-400 active:scale-[0.99] disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mint-500"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Sending…
                </span>
              ) : (
                'Send reset link'
              )}
            </button>
          </form>
        </>
      ) : (
        <div className="text-center">
          <div className="mb-4 flex justify-center">
            <div className="animate-check-pop rounded-full bg-mint-500/10 p-4">
              <MailCheck className="h-8 w-8 text-mint-500" />
            </div>
          </div>
          <h1 className="text-2xl font-bold text-text-primary-light dark:text-text-primary-dark">
            Check your email
          </h1>
          <p className="mt-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">
            If an account exists for{' '}
            <span className="font-medium text-text-primary-light dark:text-text-primary-dark">{email}</span>, a
            password reset link is on its way. It expires in 1 hour.
          </p>
        </div>
      )}

      <p className="mt-8 text-center text-sm">
        <Link href="/login" className="text-text-secondary-light hover:underline dark:text-text-secondary-dark">
          Back to login
        </Link>
      </p>
    </AuthShell>
  )
}
