'use client'

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getCurrentUser, exportUserData, deleteUserAccount } from '@/features/auth/api/auth-api'
import { useRouter } from 'next/navigation'
import { Download, Trash2, AlertCircle, CheckCircle2, Loader2, ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import analytics from '@/lib/analytics'

export default function SettingsPage() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteConfirmText, setDeleteConfirmText] = useState('')

  const { data: user, isLoading: userLoading } = useQuery({
    queryKey: ['user'],
    queryFn: getCurrentUser,
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
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900 flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Header */}
        <div className="mb-8">
          <Link
            href="/dashboard"
            className="inline-flex items-center text-sm text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 mb-4"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back to Dashboard
          </Link>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white">
            Account Settings
          </h1>
          <p className="text-slate-600 dark:text-slate-400 mt-2">
            Manage your account and data
          </p>
        </div>

        {/* Account Info */}
        <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 p-6 mb-6">
          <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">
            Account Information
          </h2>
          <div className="space-y-3">
            <div>
              <label className="text-sm text-slate-600 dark:text-slate-400">Email</label>
              <p className="text-slate-900 dark:text-white font-medium">{user?.email}</p>
            </div>
            {user?.full_name && (
              <div>
                <label className="text-sm text-slate-600 dark:text-slate-400">Name</label>
                <p className="text-slate-900 dark:text-white font-medium">{user.full_name}</p>
              </div>
            )}
            <div>
              <label className="text-sm text-slate-600 dark:text-slate-400">Plan</label>
              <p className="text-slate-900 dark:text-white font-medium">
                {user?.is_pro ? 'Pro' : 'Free'}
              </p>
            </div>
          </div>
        </div>

        {/* Data Export */}
        <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 p-6 mb-6">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">
                Export Your Data
              </h2>
              <p className="text-slate-600 dark:text-slate-400 mb-4">
                Download a complete copy of your data including your profile, search history,
                saved summaries, watchlist, and usage statistics in JSON format.
              </p>
              <p className="text-sm text-slate-500 dark:text-slate-500 mb-4">
                This is your right under GDPR Article 20 (Data Portability).
              </p>
            </div>
          </div>

          <button
            onClick={handleExportData}
            disabled={exportMutation.isPending}
            className="inline-flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {exportMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Exporting...
              </>
            ) : (
              <>
                <Download className="h-4 w-4 mr-2" />
                Download My Data
              </>
            )}
          </button>

          {exportMutation.isSuccess && (
            <div className="mt-4 flex items-center text-sm text-green-600 dark:text-green-400">
              <CheckCircle2 className="h-4 w-4 mr-2" />
              Your data has been downloaded successfully
            </div>
          )}

          {exportMutation.isError && (
            <div className="mt-4 flex items-center text-sm text-red-600 dark:text-red-400">
              <AlertCircle className="h-4 w-4 mr-2" />
              Failed to export data. Please try again or contact support.
            </div>
          )}
        </div>

        {/* Delete Account */}
        <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-red-200 dark:border-red-900 p-6">
          <div className="flex items-start justify-between mb-4">
            <div className="flex-1">
              <h2 className="text-xl font-semibold text-red-600 dark:text-red-400 mb-2">
                Delete Account
              </h2>
              <p className="text-slate-600 dark:text-slate-400 mb-4">
                Permanently delete your account and all associated data. This action cannot be undone.
              </p>
            </div>
          </div>

          {!showDeleteConfirm ? (
            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="inline-flex items-center px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors"
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Delete My Account
            </button>
          ) : (
            <div className="space-y-4">
              <div className="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-4">
                <div className="flex items-start">
                  <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400 mr-3 flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <h3 className="font-semibold text-red-900 dark:text-red-300 mb-2">
                      Warning: This action is permanent
                    </h3>
                    <p className="text-sm text-red-800 dark:text-red-400 mb-2">
                      Deleting your account will:
                    </p>
                    <ul className="text-sm text-red-800 dark:text-red-400 list-disc list-inside space-y-1 mb-4">
                      <li>Permanently delete your profile and account</li>
                      <li>Delete all your search history</li>
                      <li>Delete all your saved summaries and notes</li>
                      <li>Delete your watchlist</li>
                      <li>Cancel any active subscriptions</li>
                      <li>Remove all your usage data</li>
                    </ul>
                    <p className="text-sm text-red-800 dark:text-red-400 font-medium">
                      This action cannot be undone and your data cannot be recovered.
                    </p>
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  Type &quot;delete my account&quot; to confirm:
                </label>
                <input
                  type="text"
                  value={deleteConfirmText}
                  onChange={(e) => setDeleteConfirmText(e.target.value)}
                  className="w-full px-4 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:ring-2 focus:ring-red-500 focus:border-transparent"
                  placeholder="delete my account"
                  disabled={deleteMutation.isPending}
                />
              </div>

              <div className="flex gap-3">
                <button
                  onClick={handleDeleteAccount}
                  disabled={
                    deleteMutation.isPending ||
                    deleteConfirmText.toLowerCase() !== 'delete my account'
                  }
                  className="inline-flex items-center px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {deleteMutation.isPending ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Deleting...
                    </>
                  ) : (
                    <>
                      <Trash2 className="h-4 w-4 mr-2" />
                      Confirm Deletion
                    </>
                  )}
                </button>

                <button
                  onClick={() => {
                    setShowDeleteConfirm(false)
                    setDeleteConfirmText('')
                  }}
                  disabled={deleteMutation.isPending}
                  className="px-4 py-2 bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-900 dark:text-white rounded-lg transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
              </div>

              {deleteMutation.isError && (
                <div className="flex items-center text-sm text-red-600 dark:text-red-400">
                  <AlertCircle className="h-4 w-4 mr-2" />
                  Failed to delete account. Please contact support.
                </div>
              )}
            </div>
          )}
        </div>

        {/* Privacy Notice */}
        <div className="mt-8 text-sm text-slate-500 dark:text-slate-400 text-center">
          <p>
            For more information about how we handle your data, please read our{' '}
            <Link href="/privacy" className="text-blue-600 hover:text-blue-700 dark:text-blue-400">
              Privacy Policy
            </Link>
            .
          </p>
        </div>
      </div>
    </div>
  )
}
