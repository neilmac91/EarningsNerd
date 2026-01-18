'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { login } from '@/lib/api'
import Link from 'next/link'
import EarningsNerdLogo from '@/components/EarningsNerdLogo'
import { CheckCircle2 } from 'lucide-react'

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
    } catch (err: any) {
      console.error('Login error:', err)
      const errorMessage = err.response?.data?.detail || err.message || 'Login failed. Please check your credentials.'
      setError(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-slate-950 px-6 py-16">
      <div className="absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute -top-32 left-1/3 h-[420px] w-[420px] rounded-full bg-sky-500/10 blur-3xl" />
        <div className="absolute bottom-0 right-0 h-[360px] w-[360px] rounded-full bg-indigo-500/10 blur-3xl" />
      </div>
      <div className="max-w-md w-full rounded-3xl bg-white/90 dark:bg-slate-900/80 backdrop-blur-xl shadow-2xl p-8 border border-gray-200/60 dark:border-white/10">
        <div className="flex flex-col items-center gap-3 text-center mb-8">
          <EarningsNerdLogo variant="full" iconClassName="h-12 w-12" hideTagline />
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Welcome back</h1>
            <p className="mt-2 text-sm text-gray-600 dark:text-slate-300">
              Sign in to continue monitoring your latest filings.
            </p>
          </div>
        </div>
        
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 dark:bg-red-900/30 dark:border-red-800 dark:text-red-200 px-4 py-3 rounded mb-4">
            {error}
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
              className="w-full px-3 py-2 border border-gray-300 dark:border-slate-700 rounded-xl focus:outline-none focus:border-primary-500 dark:focus:border-primary-400 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100"
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
              className="w-full px-3 py-2 border border-gray-300 dark:border-slate-700 rounded-xl focus:outline-none focus:border-primary-500 dark:focus:border-primary-400 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-primary-600 text-white py-2 rounded-full hover:bg-primary-700 font-semibold disabled:opacity-50"
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
          <div className="flex justify-end">
            <a
              href="mailto:hello@earningsnerd.com?subject=Password%20reset"
              className="text-sm text-gray-500 dark:text-slate-400 hover:text-primary-600"
            >
              Forgot password?
            </a>
          </div>
        </form>

        <div className="mt-6 rounded-2xl border border-gray-200/60 dark:border-white/10 bg-gray-50/80 dark:bg-slate-950/50 p-4 text-sm text-gray-600 dark:text-slate-300">
          <div className="flex items-center gap-2 font-semibold text-gray-900 dark:text-white mb-2">
            <CheckCircle2 className="h-4 w-4 text-sky-500" />
            What you unlock
          </div>
          <ul className="space-y-2">
            <li className="flex items-start gap-2">
              <CheckCircle2 className="mt-0.5 h-4 w-4 text-sky-500" />
              Live SEC filing summaries and risk highlights.
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle2 className="mt-0.5 h-4 w-4 text-sky-500" />
              Watchlists and saved summaries across teams.
            </li>
          </ul>
        </div>

        <p className="mt-6 text-center text-gray-600 dark:text-slate-300">
          Don't have an account?{' '}
          <Link href="/register" className="text-primary-600 hover:underline">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  )
}

