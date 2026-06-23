'use client'

import { useState } from 'react'
import { forgotPassword } from '@/features/auth/api/auth-api'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import Link from 'next/link'
import { CircleNotchIcon, EnvelopeSimpleOpenIcon } from '@/lib/icons'
import StateCard from '@/components/StateCard'
import AuthShell from '@/components/auth/AuthShell'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'

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
              <Input
                type="email"
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                autoFocus
              />
            </div>

            <Button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 font-semibold active:scale-[0.99]"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <CircleNotchIcon className="h-4 w-4 animate-spin" />
                  Sending…
                </span>
              ) : (
                'Send reset link'
              )}
            </Button>
          </form>
        </>
      ) : (
        <div className="text-center">
          <div className="mb-4 flex justify-center">
            <div className="animate-check-pop rounded-full bg-brand-strong/10 p-4 dark:bg-brand-dark/15">
              <EnvelopeSimpleOpenIcon className="h-8 w-8 text-brand-strong dark:text-brand-strong-dark" />
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
