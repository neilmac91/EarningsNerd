'use client'

import { useState } from 'react'
import { forgotPassword } from '@/features/auth/api/auth-api'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import Link from 'next/link'
import { Loader2 } from 'lucide-react'
import SecondaryHeader from '@/components/SecondaryHeader'
import StateCard from '@/components/StateCard'

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
    <div className="min-h-screen bg-background-light dark:bg-background-dark">
      <SecondaryHeader backHref="/login" backLabel="Back to Login" />

      <div className="flex min-h-[calc(100vh-80px)] items-center justify-center px-4 py-10">
        <div className="w-full max-w-md rounded-2xl border border-border-light bg-panel-light p-8 shadow-lg dark:border-border-dark dark:bg-panel-dark">
          <h1 className="text-2xl font-bold text-center text-text-primary-light dark:text-text-primary-dark mb-3">
            Reset your password
          </h1>

          {!submitted ? (
            <>
              <p className="text-sm text-center text-text-secondary-light dark:text-text-secondary-dark mb-8">
                Enter your email and we&apos;ll send you a reset link.
              </p>

              {error && (
                <div className="mb-6">
                  <StateCard variant="error" title="Error" message={error} />
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label htmlFor="email" className="block text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark mb-1">
                    Email
                  </label>
                  <input
                    type="email"
                    id="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="w-full px-3 py-2 border border-border-light rounded-lg bg-background-light text-text-primary-light placeholder:text-text-tertiary-light focus:outline-none focus:ring-2 focus:ring-mint-500/50 focus:border-mint-500 dark:border-border-dark dark:bg-background-dark dark:text-text-primary-dark dark:placeholder:text-text-tertiary-dark"
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-mint-500 text-slate-950 py-2.5 rounded-lg hover:bg-mint-400 font-semibold disabled:opacity-50 transition-colors focus:outline-none focus:ring-2 focus:ring-mint-500 focus:ring-offset-2 dark:focus:ring-offset-gray-900"
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
              <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark mb-2">
                If an account exists for
              </p>
              <p className="text-sm font-medium text-text-primary-light dark:text-text-primary-dark mb-6">
                {email}
              </p>
              <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark mb-8">
                you&apos;ll receive a reset link shortly. The link expires in 1 hour.
              </p>
            </div>
          )}

          <p className="mt-6 text-center text-sm text-text-secondary-light dark:text-text-secondary-dark">
            <Link href="/login" className="text-mint-600 hover:underline dark:text-mint-400">
              Back to login
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
