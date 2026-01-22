'use client'

import { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import { getSubscriptionStatus } from '@/features/subscriptions/api/subscriptions-api'
import Link from 'next/link'
import { Lock, Sparkles } from 'lucide-react'

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
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
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
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-6">
        <div className="flex items-start space-x-4">
          <div className="flex-shrink-0">
            <Lock className="h-6 w-6 text-amber-600" />
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-amber-900 mb-2">
              Pro Feature
            </h3>
            <p className="text-amber-800 mb-4">
              This feature is available for Pro subscribers. Upgrade to unlock unlimited summaries, 
              advanced comparisons, and export capabilities.
            </p>
            <Link
              href="/pricing"
              className="inline-flex items-center px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-colors font-medium"
            >
              <Sparkles className="h-4 w-4 mr-2" />
              Upgrade to Pro
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return <>{children}</>
}

