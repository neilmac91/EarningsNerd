'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import { ShimmeringLoader } from '@/components/ShimmeringLoader'

/**
 * Admin section gate. Mirrors the dashboard's redirect-if-not-logged-in pattern but adds an
 * is_admin check on top: anonymous visitors go to /login, signed-in non-admins go to
 * /dashboard. Real enforcement still lives on the backend (_require_admin); this is a UX
 * guard so non-admins never see a flash of admin chrome.
 */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()

  const { data: user, isLoading } = useQuery({
    queryKey: ['current-user'],
    queryFn: getCurrentUserSafe,
    retry: false,
    staleTime: 60_000,
  })

  const isAdmin = Boolean(user?.is_admin)

  useEffect(() => {
    if (isLoading) return
    if (!user) {
      router.replace('/login')
    } else if (!isAdmin) {
      router.replace('/dashboard')
    }
  }, [isLoading, user, isAdmin, router])

  if (isLoading) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <ShimmeringLoader className="h-8 w-48" />
        <div className="mt-6 space-y-3">
          <ShimmeringLoader className="h-40 w-full" />
          <ShimmeringLoader className="h-64 w-full" />
        </div>
      </div>
    )
  }

  // While the redirect effect runs, render nothing rather than flashing admin content.
  if (!user || !isAdmin) {
    return null
  }

  return <div className="min-h-screen bg-background-light dark:bg-background-dark">{children}</div>
}
