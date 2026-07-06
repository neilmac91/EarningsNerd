'use client'

import { useState } from 'react'
import { ApiError } from '@/lib/api/client'
import { getWaitlistStatus } from '@/features/waitlist/api/waitlist-api'
import { Button, Card, Input, Notice } from '@/components/ui'

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
    // The Button uses `loading` (aria-disabled, not native disabled), so Enter can still fire this
    // mid-request — guard against a concurrent status check.
    if (loading) return
    setError(null)
    setStatus(null)
    if (!email.trim()) {
      setError('Please enter the email you used to sign up.')
      return
    }

    setLoading(true)
    try {
      const data = await getWaitlistStatus(email.trim())
      setStatus(data)
    } catch (err) {
      // An HTTP error (status !== 0) carries the backend detail; status 0 = no response (network).
      setError(
        err instanceof ApiError && err.status !== 0
          ? err.detail
          : 'Network error. Please try again.',
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="p-6">
      <h3 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">
        Check your waitlist status
      </h3>
      <form onSubmit={handleSubmit} className="mt-4 space-y-4">
        <Input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="you@company.com"
        />
        {error && <Notice variant="error" title={error} />}
        <Button type="submit" loading={loading} loadingText="Checking..." className="w-full">
          Check status
        </Button>
      </form>

      {status && (
        <div className="mt-6 space-y-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
          <div>
            Position: <span className="tnum font-data font-semibold">#{status.position}</span>
          </div>
          <div>
            Referrals: <span className="tnum font-data font-semibold">{status.referrals_count}</span>
          </div>
          <div>
            Positions gained:{' '}
            <span className="tnum font-data font-semibold">{status.positions_gained}</span>
          </div>
          <div>
            Email verified:{' '}
            <span className="font-semibold">
              {status.email_verified ? 'Yes' : 'Not yet'}
            </span>
          </div>
          <div className="pt-2 text-xs uppercase tracking-wide text-text-tertiary-light dark:text-text-secondary-dark">
            Your referral link
          </div>
          <div className="break-all text-sm font-medium text-text-primary-light dark:text-text-primary-dark">
            {status.referral_link}
          </div>
        </div>
      )}
    </Card>
  )
}
