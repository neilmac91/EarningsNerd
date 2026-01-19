'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { login } from '@/lib/api'
import Link from 'next/link'
import { AlertCircle, Loader2 } from 'lucide-react'
import EarningsNerdLogoIcon from '@/components/EarningsNerdLogoIcon'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await login(email, password)
      router.push('/')
      router.refresh()
    } catch (err: unknown) {
      console.error('Login error:', err)
      const axiosErr = err as { response?: { data?: { detail?: string } }; message?: string }
      const errorMessage = axiosErr.response?.data?.detail || axiosErr.message || 'Login failed. Please check your credentials.'
      setError(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4 py-10 dark:bg-slate-950">
      <div className="w-full max-w-md rounded-2xl border border-gray-200/70 bg-white p-8 shadow-lg dark:border-white/10 dark:bg-slate-900">
        <div className="flex flex-col items-center gap-3">
          <Link href="/" className="flex items-center gap-2 text-slate-700 dark:text-slate-200">
            <EarningsNerdLogoIcon className="h-9 w-9" />
            <span className="text-sm font-semibold">EarningsNerd</span>
          </Link>
        </div>
        <h1 className="mt-4 text-3xl font-bold text-center text-gray-900 dark:text-white mb-3">Login</h1>
        <p className="text-sm text-center text-gray-600 dark:text-slate-300 mb-8">
          Welcome back — sign in to continue.
        </p>

        {error && (
          <div
            className="mb-5 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-200"
            role="alert"
            aria-live="polite"
          >
            <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 dark:text-slate-200 mb-1">
              Email
            </label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white text-gray-900 placeholder:text-gray-400 focus:outline-none focus:border-primary-500 dark:border-slate-700 dark:bg-slate-950 dark:text-white"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 dark:text-slate-200 mb-1">
              Password
            </label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white text-gray-900 placeholder:text-gray-400 focus:outline-none focus:border-primary-500 dark:border-slate-700 dark:bg-slate-950 dark:text-white"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-primary-600 text-white py-2.5 rounded-lg hover:bg-primary-700 font-semibold disabled:opacity-50"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Logging in...
              </span>
            ) : (
              'Login'
            )}
          </button>
        </form>

        <p className="mt-6 text-center text-gray-600 dark:text-slate-300">
          Don&apos;t have an account?{' '}
          <Link href="/register" className="text-primary-600 hover:underline dark:text-primary-400">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  )
}

