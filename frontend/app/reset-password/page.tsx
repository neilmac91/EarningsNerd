'use client'

import { useState, Suspense } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { resetPassword } from '@/features/auth/api/auth-api'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import Link from 'next/link'
import { CheckCircleIcon, CircleNotchIcon } from '@/lib/icons'
import AuthShell from '@/components/auth/AuthShell'
import PasswordField from '@/components/auth/PasswordField'
import { Button, Notice } from '@/components/ui'

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

  if (success) {
    return (
      <AuthShell>
        <div className="text-center">
          <div className="mb-4 flex justify-center">
            <CheckCircleIcon className="animate-check-pop h-12 w-12 text-brand-strong dark:text-brand-strong-dark" />
          </div>
          <h1 className="text-2xl font-bold text-text-primary-light dark:text-text-primary-dark">
            Password updated!
          </h1>
          <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
            Redirecting you to login…
          </p>
          <Link href="/login" className="mt-6 inline-block text-sm font-medium text-brand-strong hover:underline dark:text-brand-strong-dark">
            Go to login
          </Link>
        </div>
      </AuthShell>
    )
  }

  return (
    <AuthShell>
      <h1 className="text-2xl font-bold text-text-primary-light dark:text-text-primary-dark">
        Choose a new password
      </h1>
      <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
        At least 12 characters, with upper- and lowercase letters and a number.
      </p>

      {error && (
        <div className="mt-6">
          <Notice variant="error" title="Error" description={error} />
        </div>
      )}

      {!token && (
        <div className="mt-6">
          <Notice
            variant="error"
            title="Invalid link"
            description="This reset link is invalid. Please request a new one."
          />
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-8 space-y-4">
        <PasswordField
          id="password"
          label="New password"
          value={password}
          onChange={setPassword}
          autoComplete="new-password"
          required
          minLength={12}
          showStrength
          autoFocus={!!token}
        />

        <PasswordField
          id="confirm"
          label="Confirm new password"
          value={confirm}
          onChange={setConfirm}
          autoComplete="new-password"
          required
          minLength={12}
        />

        <Button
          type="submit"
          disabled={loading || !token}
          className="w-full py-2.5 font-semibold active:scale-[0.99]"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <CircleNotchIcon className="h-4 w-4 animate-spin" />
              Resetting…
            </span>
          ) : (
            'Reset password'
          )}
        </Button>
      </form>

      <p className="mt-8 text-center text-sm text-text-secondary-light dark:text-text-secondary-dark">
        Need a new link?{' '}
        <Link href="/forgot-password" className="font-medium text-brand-strong hover:underline dark:text-brand-strong-dark">
          Request reset
        </Link>
      </p>
    </AuthShell>
  )
}

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetPasswordContent />
    </Suspense>
  )
}
