'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { getCurrentUser, register } from '@/features/auth/api/auth-api'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import Link from 'next/link'
import { Loader2 } from 'lucide-react'
import SecondaryHeader from '@/components/SecondaryHeader'
import StateCard from '@/components/StateCard'
import analytics from '@/lib/analytics'

export default function RegisterPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    analytics.signupStarted('register_page')

    try {
      await register(email, password, fullName)
      try {
        const user = await getCurrentUser()
        if (user?.id && user?.email) {
          analytics.signupCompleted(String(user.id), user.email)
        }
      } catch {
        // Ignore analytics errors to avoid blocking signup
      }
      router.push('/')
    } catch (err: unknown) {
      const errorMessage = isApiError(err)
        ? getErrorMessage(err)
        : 'Registration failed'
      setError(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background-light dark:bg-background-dark">
      <SecondaryHeader
        backHref="/"
        backLabel="Back to Home"
      />

      <div className="flex min-h-[calc(100vh-80px)] items-center justify-center px-4 py-10">
        <div className="w-full max-w-md rounded-2xl border border-border-light bg-panel-light p-8 shadow-lg dark:border-border-dark dark:bg-panel-dark">
          <h1 className="text-3xl font-bold text-center text-text-primary-light dark:text-text-primary-dark mb-3">Create account</h1>
          <p className="text-sm text-center text-text-secondary-light dark:text-text-secondary-dark mb-8">
            Start your free trial and unlock AI summaries.
          </p>

          {error && (
            <div className="mb-6">
              <StateCard
                variant="error"
                title="Registration Failed"
                message={error}
              />
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="fullName" className="block text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark mb-1">
                Full Name (Optional)
              </label>
              <input
                type="text"
                id="fullName"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="w-full px-3 py-2 border border-border-light rounded-lg bg-background-light text-text-primary-light placeholder:text-text-tertiary-light focus:outline-none focus:ring-2 focus:ring-mint-500/50 focus:border-mint-500 dark:border-border-dark dark:bg-background-dark dark:text-text-primary-dark dark:placeholder:text-text-tertiary-dark"
              />
            </div>

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

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark mb-1">
                Password
              </label>
              <input
                type="password"
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={12}
                className="w-full px-3 py-2 border border-border-light rounded-lg bg-background-light text-text-primary-light placeholder:text-text-tertiary-light focus:outline-none focus:ring-2 focus:ring-mint-500/50 focus:border-mint-500 dark:border-border-dark dark:bg-background-dark dark:text-text-primary-dark dark:placeholder:text-text-tertiary-dark"
              />
              <p className="mt-2 text-xs text-text-tertiary-light dark:text-text-tertiary-dark">
                Use at least 12 characters with upper/lowercase letters and a number.
              </p>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-mint-500 text-white py-2.5 rounded-lg hover:bg-mint-600 font-semibold disabled:opacity-50 transition-colors focus:outline-none focus:ring-2 focus:ring-mint-500 focus:ring-offset-2 dark:focus:ring-offset-gray-900"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Creating account...
                </span>
              ) : (
                'Sign Up'
              )}
            </button>
          </form>

          <p className="mt-6 text-center text-text-secondary-light dark:text-text-secondary-dark">
            Already have an account?{' '}
            <Link href="/login" className="text-mint-600 hover:underline dark:text-mint-400">
              Login
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
