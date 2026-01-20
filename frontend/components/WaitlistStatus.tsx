'use client'

import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { getApiUrl } from '@/lib/api'

type StatusData = {
  position: number
  referral_code: string
  referral_link: string
  referrals_count: number
  positions_gained: number
  email_verified: boolean
}

export default function WaitlistStatus() {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState<StatusData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    setStatus(null)
    if (!email.trim()) {
      setError('Please enter the email you used to sign up.')
      return
    }

    setLoading(true)
    try {
      const response = await fetch(
        `${getApiUrl()}/api/waitlist/status/${encodeURIComponent(email.trim())}`
      )
      const data = await response.json()
      if (!response.ok) {
        setError(data?.detail || 'Unable to find that email.')
        return
      }
      setStatus(data)
    } catch {
      setError('Network error. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-2xl border border-border-light bg-white/90 p-6 shadow-lg dark:border-border-dark dark:bg-slate-900/70">
      <h3 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">
        Check your waitlist status
      </h3>
      <form onSubmit={handleSubmit} className="mt-4 space-y-4">
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="you@company.com"
          className="w-full rounded-xl border border-border-light bg-background-light px-4 py-3 text-sm text-text-primary-light focus:border-mint-300 focus:outline-none dark:border-border-dark dark:bg-background-dark dark:text-text-primary-dark"
        />
        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}
        <button
          type="submit"
          disabled={loading}
          className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-mint-500 px-6 py-3 text-sm font-semibold text-slate-900 transition hover:bg-mint-400 disabled:cursor-not-allowed disabled:opacity-70"
        >
          {loading && <Loader2 className="h-4 w-4 animate-spin" />}
          {loading ? 'Checking...' : 'Check status'}
        </button>
      </form>

      {status && (
        <div className="mt-6 space-y-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
          <div>
            Position: <span className="font-semibold">#{status.position}</span>
          </div>
          <div>
            Referrals: <span className="font-semibold">{status.referrals_count}</span>
          </div>
          <div>
            Positions gained:{' '}
            <span className="font-semibold">{status.positions_gained}</span>
          </div>
          <div>
            Email verified:{' '}
            <span className="font-semibold">
              {status.email_verified ? 'Yes' : 'Not yet'}
            </span>
          </div>
          <div className="pt-2 text-xs uppercase tracking-wide text-text-tertiary-light dark:text-text-tertiary-dark">
            Your referral link
          </div>
          <div className="text-sm font-medium text-text-primary-light dark:text-text-primary-dark">
            {status.referral_link}
          </div>
        </div>
      )}
    </div>
  )
}
