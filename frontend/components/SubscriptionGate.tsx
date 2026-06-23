'use client'

import { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import { getSubscriptionStatus } from '@/features/subscriptions/api/subscriptions-api'
import Link from 'next/link'
import { LockSimpleIcon, SparkleIcon } from '@/lib/icons'

interface SubscriptionGateProps {
  children: ReactNode
  fallback?: ReactNode
  requirePro?: boolean
}

export default function SubscriptionGate({ 
  children, 
  fallback,
  requirePro = false 
}: SubscriptionGateProps) {
  const { data: user, isLoading: userLoading } = useQuery({
    queryKey: ['current-user'],
    queryFn: getCurrentUserSafe,
    retry: false,
  })

  const { data: subscription, isLoading } = useQuery({
    queryKey: ['subscription', user?.id],
    queryFn: getSubscriptionStatus,
    retry: false,
    enabled: Boolean(user),
  })

  if (user && (isLoading || userLoading)) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-strong dark:border-brand-dark"></div>
      </div>
    )
  }

  if (!user) {
    return <>{fallback ?? children}</>
  }

  // If Pro is required and user is not Pro, show upgrade prompt
  if (requirePro && !subscription?.is_pro) {
    if (fallback) {
      return <>{fallback}</>
    }

    return (
      <div className="rounded-lg border border-warning-light/40 bg-warning-light/10 p-6 dark:border-warning-dark/40 dark:bg-warning-dark/15">
        <div className="flex items-start space-x-4">
          <div className="flex-shrink-0">
            <LockSimpleIcon className="h-6 w-6 text-warning-light dark:text-warning-dark" />
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-warning-light dark:text-warning-dark mb-2">
              Pro Feature
            </h3>
            <p className="text-text-secondary-light dark:text-text-secondary-dark mb-4">
              This feature is available for Pro subscribers. Upgrade to unlock unlimited summaries,
              advanced comparisons, and export capabilities.
            </p>
            <Link
              href="/pricing"
              className="inline-flex items-center px-4 py-2 bg-brand-strong text-white rounded-lg hover:bg-brand-light dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark focus-visible:outline-brand-light transition-colors font-medium"
            >
              <SparkleIcon className="h-4 w-4 mr-2" />
              Upgrade to Pro
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return <>{children}</>
}

