'use client'

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getCurrentUserSafe, exportUserData, deleteUserAccount } from '@/features/auth/api/auth-api'
import { useRouter } from 'next/navigation'
import { ArrowLeftIcon, CheckCircleIcon, CircleNotchIcon, DownloadSimpleIcon, TrashIcon, WarningCircleIcon } from '@/lib/icons'
import Link from 'next/link'
import analytics from '@/lib/analytics'
import ConnectedAccounts from '@/features/settings/components/ConnectedAccounts'
import NotificationPreferencesForm from '@/features/settings/components/NotificationPreferencesForm'
import ProfileForm from '@/features/settings/components/ProfileForm'
import BillingPanel from '@/features/settings/components/BillingPanel'
import ChangePasswordForm from '@/features/settings/components/ChangePasswordForm'
import { Button } from '@/components/ui/Button'
import { inputClasses } from '@/components/ui/Input'
import { Card } from '@/components/ui/Card'
import { queryKeys } from '@/lib/queryKeys'

export default function SettingsPage() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteConfirmText, setDeleteConfirmText] = useState('')

  const { data: user, isLoading: userLoading } = useQuery({
    queryKey: queryKeys.currentUser(),
    queryFn: getCurrentUserSafe,
    retry: false,
  })

  const exportMutation = useMutation({
    mutationFn: exportUserData,
    onSuccess: () => {
      if (user?.id) {
        analytics.dataExported(String(user.id))
      }
    },
    onError: (error) => {
      console.error('Export failed:', error)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteUserAccount,
    onSuccess: () => {
      if (user?.id) {
        analytics.accountDeleted(String(user.id))
      }
      // Logout and redirect to home
      queryClient.clear()
      router.push('/')
    },
    onError: (error) => {
      console.error('Delete failed:', error)
    },
  })

  const handleExportData = () => {
    exportMutation.mutate()
  }

  const handleDeleteAccount = () => {
    if (deleteConfirmText.toLowerCase() === 'delete my account') {
      deleteMutation.mutate()
    }
  }

  if (userLoading) {
    return (
      <div className="min-h-screen bg-background-light dark:bg-background-dark flex items-center justify-center">
        <CircleNotchIcon className="h-8 w-8 animate-spin text-brand-strong dark:text-brand-strong-dark" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background-light dark:bg-background-dark">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Header */}
        <div className="mb-8">
          <Link
            href="/dashboard"
            className="inline-flex items-center text-sm text-text-secondary-light dark:text-text-secondary-dark hover:text-text-primary-light dark:hover:text-text-primary-dark mb-4"
          >
            <ArrowLeftIcon className="h-4 w-4 mr-1" />
            Back to dashboard
          </Link>
          <h1 className="text-3xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Account settings
          </h1>
          <p className="text-text-secondary-light dark:text-text-secondary-dark mt-2">
            Manage your account and data
          </p>
        </div>

        {/* Profile — email (read-only) + editable display name */}
        <ProfileForm />

        {/* Billing — plan, usage, trial countdown, renew/cancel, manage portal */}
        <BillingPanel />

        {/* Connected accounts & sessions */}
        <ConnectedAccounts />

        {/* Set / change password (OAuth-only users can set one here) */}
        <ChangePasswordForm />

        {/* New-filing alert preferences */}
        <NotificationPreferencesForm />

        {/* Data Export */}
        <Card className="p-6 mb-6">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark mb-2">
                Export your data
              </h2>
              <p className="text-text-secondary-light dark:text-text-secondary-dark mb-4">
                Download a complete copy of your data including your profile, search history,
                saved summaries, watchlist, and usage statistics in JSON format.
              </p>
              <p className="text-sm text-text-tertiary-light dark:text-text-secondary-dark mb-4">
                This is your right under GDPR Article 20 (Data Portability).
              </p>
            </div>
          </div>

          <Button
            onClick={handleExportData}
            loading={exportMutation.isPending}
            loadingText="Exporting..."
            leftIcon={<DownloadSimpleIcon className="h-4 w-4" />}
          >
            Download my data
          </Button>

          {exportMutation.isSuccess && (
            <div className="mt-4 flex items-center text-sm text-success-light dark:text-success-dark">
              <CheckCircleIcon className="h-4 w-4 mr-2" />
              Your data has been downloaded successfully
            </div>
          )}

          {exportMutation.isError && (
            <div className="mt-4 flex items-center text-sm text-error-light dark:text-error-dark">
              <WarningCircleIcon className="h-4 w-4 mr-2" />
              Failed to export data. Please try again or contact support.
            </div>
          )}
        </Card>

        {/* Delete Account — Card with the border overridden to the loss hairline */}
        <Card className="border-loss-light/40 p-6 dark:border-loss-dark/30">
          <div className="flex items-start justify-between mb-4">
            <div className="flex-1">
              <h2 className="text-xl font-semibold text-error-light dark:text-error-dark mb-2">
                Delete account
              </h2>
              <p className="text-text-secondary-light dark:text-text-secondary-dark mb-4">
                Permanently delete your account and all associated data. This action cannot be undone.
              </p>
            </div>
          </div>

          {!showDeleteConfirm ? (
            <Button variant="destructive" onClick={() => setShowDeleteConfirm(true)} leftIcon={<TrashIcon className="h-4 w-4" />}>
              Delete my account
            </Button>
          ) : (
            <div className="space-y-4">
              <div className="bg-loss-soft dark:bg-loss-soft-dark border border-loss-light/30 dark:border-loss-dark/30 rounded-lg p-4">
                <div className="flex items-start">
                  <WarningCircleIcon className="h-5 w-5 text-error-light dark:text-error-dark mr-3 flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <h3 className="font-semibold text-error-light dark:text-error-dark mb-2">
                      Warning: This action is permanent
                    </h3>
                    <p className="text-sm text-error-light dark:text-error-dark mb-2">
                      Deleting your account will:
                    </p>
                    <ul className="text-sm text-error-light dark:text-error-dark list-disc list-inside space-y-1 mb-4">
                      <li>Permanently delete your profile and account</li>
                      <li>Delete all your search history</li>
                      <li>Delete all your saved summaries and notes</li>
                      <li>Delete your watchlist</li>
                      <li>Cancel any active subscriptions</li>
                      <li>Remove all your usage data</li>
                    </ul>
                    <p className="text-sm text-error-light dark:text-error-dark font-medium">
                      This action cannot be undone and your data cannot be recovered.
                    </p>
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark mb-2">
                  Type &quot;delete my account&quot; to confirm:
                </label>
                {/* Raw input + inputClasses(): the destructive-confirm field keeps its
                    error-toned focus, which must style the field, not the v2 shell. */}
                <input
                  type="text"
                  value={deleteConfirmText}
                  onChange={(e) => setDeleteConfirmText(e.target.value)}
                  className={inputClasses({ className: 'focus:border-error-light focus:shadow-ring-error' })}
                  placeholder="delete my account"
                  disabled={deleteMutation.isPending}
                />
              </div>

              <div className="flex gap-3">
                {/* `loading` (not disabled) while pending — loading keeps the resting
                    fill and refuses activation; disabled is only for the unmet confirm text. */}
                <Button
                  variant="destructive"
                  onClick={handleDeleteAccount}
                  disabled={deleteConfirmText.toLowerCase() !== 'delete my account'}
                  loading={deleteMutation.isPending}
                  loadingText="Deleting..."
                  leftIcon={<TrashIcon className="h-4 w-4" />}
                >
                  Confirm Deletion
                </Button>

                <Button
                  variant="secondary"
                  onClick={() => {
                    setShowDeleteConfirm(false)
                    setDeleteConfirmText('')
                  }}
                  disabled={deleteMutation.isPending}
                >
                  Cancel
                </Button>
              </div>

              {deleteMutation.isError && (
                <div className="flex items-center text-sm text-error-light dark:text-error-dark">
                  <WarningCircleIcon className="h-4 w-4 mr-2" />
                  Failed to delete account. Please contact support.
                </div>
              )}
            </div>
          )}
        </Card>

        {/* Privacy Notice */}
        <div className="mt-8 text-sm text-text-tertiary-light dark:text-text-secondary-dark text-center">
          <p>
            For more information about how we handle your data, please read our{' '}
            <Link href="/privacy" className="text-brand-strong dark:text-brand-strong-dark hover:underline">
              Privacy Policy
            </Link>
            .
          </p>
        </div>
      </div>
    </div>
  )
}
