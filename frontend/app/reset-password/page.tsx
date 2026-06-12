'use client'

import { useState, Suspense } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { resetPassword } from '@/features/auth/api/auth-api'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import Link from 'next/link'
import { Loader2, CheckCircle } from 'lucide-react'
import SecondaryHeader from '@/components/SecondaryHeader'
import StateCard from '@/components/StateCard'

function ResetPasswordContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const token = searchParams.get('token') ?? ''
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }

    if (!token) {
      setError('Invalid or missing reset token. Please request a new password reset link.')
      return
    }

    setLoading(true)
    try {
      await resetPassword(token, password)
      setSuccess(true)
      setTimeout(() => router.push('/login'), 3000)
    } catch (err: unknown) {
      setError(isApiError(err) ? getErrorMessage(err) : 'Reset failed. The link may have expired.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background-light dark:bg-background-dark">
      <SecondaryHeader backHref="/login" backLabel="Back to Login" />

      <div className="flex min-h-[calc(100vh-80px)] items-center justify-center px-4 py-10">
        <div className="w-full max-w-md rounded-2xl border border-border-light bg-panel-light p-8 shadow-lg dark:border-border-dark dark:bg-panel-dark">
          {!success ? (
            <>
              <h1 className="text-2xl font-bold text-center text-text-primary-light dark:text-text-primary-dark mb-3">
                Choose a new password
              </h1>
              <p className="text-sm text-center text-text-secondary-light dark:text-text-secondary-dark mb-8">
                At least 8 characters.
              </p>

              {error && (
                <div className="mb-6">
                  <StateCard variant="error" title="Error" message={error} />
                </div>
              )}

              {!token && (
                <div className="mb-6">
                  <StateCard
                    variant="error"
                    title="Invalid link"
                    message="This reset link is invalid. Please request a new one."
                  />
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label htmlFor="password" className="block text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark mb-1">
                    New password
                  </label>
                  <input
                    type="password"
                    id="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={8}
                    disabled={!token}
                    className="w-full px-3 py-2 border border-border-light rounded-lg bg-background-light text-text-primary-light placeholder:text-text-tertiary-light focus:outline-none focus:ring-2 focus:ring-mint-500/50 focus:border-mint-500 dark:border-border-dark dark:bg-background-dark dark:text-text-primary-dark dark:placeholder:text-text-tertiary-dark disabled:opacity-50"
                  />
                </div>

                <div>
                  <label htmlFor="confirm" className="block text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark mb-1">
                    Confirm new password
                  </label>
                  <input
                    type="password"
                    id="confirm"
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    required
                    minLength={8}
                    disabled={!token}
                    className="w-full px-3 py-2 border border-border-light rounded-lg bg-background-light text-text-primary-light placeholder:text-text-tertiary-light focus:outline-none focus:ring-2 focus:ring-mint-500/50 focus:border-mint-500 dark:border-border-dark dark:bg-background-dark dark:text-text-primary-dark dark:placeholder:text-text-tertiary-dark disabled:opacity-50"
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading || !token}
                  className="w-full bg-mint-500 text-slate-950 py-2.5 rounded-lg hover:bg-mint-400 font-semibold disabled:opacity-50 transition-colors focus:outline-none focus:ring-2 focus:ring-mint-500 focus:ring-offset-2 dark:focus:ring-offset-gray-900"
                >
                  {loading ? (
                    <span className="flex items-center justify-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Resetting…
                    </span>
                  ) : (
                    'Reset password'
                  )}
                </button>
              </form>

              <p className="mt-6 text-center text-sm text-text-secondary-light dark:text-text-secondary-dark">
                Need a new link?{' '}
                <Link href="/forgot-password" className="text-mint-600 hover:underline dark:text-mint-400">
                  Request reset
                </Link>
              </p>
            </>
          ) : (
            <div className="text-center">
              <CheckCircle className="h-10 w-10 text-mint-500 mx-auto mb-4" />
              <h1 className="text-2xl font-bold text-text-primary-light dark:text-text-primary-dark mb-2">
                Password updated!
              </h1>
              <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark mb-6">
                Redirecting you to login…
              </p>
              <Link href="/login" className="text-mint-600 hover:underline dark:text-mint-400 text-sm">
                Go to login
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetPasswordContent />
    </Suspense>
  )
}
