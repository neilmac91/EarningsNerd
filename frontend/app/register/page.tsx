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

function GoogleLogo() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z" fill="#4285F4"/>
      <path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34A853"/>
      <path d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#FBBC05"/>
      <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
    </svg>
  )
}

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
      router.push(`/check-email?email=${encodeURIComponent(email)}`)
    } catch (err: unknown) {
      const errorMessage = isApiError(err)
        ? getErrorMessage(err)
        : 'Registration failed'
      setError(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? ''

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

          {/* Google sign-in */}
          <a
            href={`${apiBase}/api/auth/google`}
            className="flex w-full items-center justify-center gap-3 rounded-lg border border-border-light bg-background-light px-4 py-2.5 text-sm font-medium text-text-primary-light transition-colors hover:bg-panel-light dark:border-border-dark dark:bg-background-dark dark:text-text-primary-dark dark:hover:bg-panel-dark"
          >
            <GoogleLogo />
            Continue with Google
          </a>

          <div className="my-6 flex items-center gap-3">
            <div className="h-px flex-1 bg-border-light dark:bg-border-dark" />
            <span className="text-xs text-text-tertiary-light dark:text-text-tertiary-dark">or</span>
            <div className="h-px flex-1 bg-border-light dark:bg-border-dark" />
          </div>

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
                minLength={8}
                className="w-full px-3 py-2 border border-border-light rounded-lg bg-background-light text-text-primary-light placeholder:text-text-tertiary-light focus:outline-none focus:ring-2 focus:ring-mint-500/50 focus:border-mint-500 dark:border-border-dark dark:bg-background-dark dark:text-text-primary-dark dark:placeholder:text-text-tertiary-dark"
              />
              <p className="mt-2 text-xs text-text-tertiary-light dark:text-text-tertiary-dark">
                At least 8 characters.
              </p>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-mint-500 text-slate-950 py-2.5 rounded-lg hover:bg-mint-400 font-semibold disabled:opacity-50 transition-colors focus:outline-none focus:ring-2 focus:ring-mint-500 focus:ring-offset-2 dark:focus:ring-offset-gray-900"
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
