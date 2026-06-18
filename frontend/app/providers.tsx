'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { Toaster } from 'sonner'
import { ThemeProvider } from '@/components/ThemeProvider'
import { PostHogProvider } from './posthog-provider'
import { GlobalErrorBoundary } from '@/components/GlobalErrorBoundary'

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000, // 1 minute
        refetchOnWindowFocus: false,
      },
    },
  }))

  return (
    <GlobalErrorBoundary>
      <PostHogProvider>
        <QueryClientProvider client={queryClient}>
          <ThemeProvider>
            {children}
            {/* Transient action feedback. theme="system" follows the .dark class set by
                ThemeProvider; richColors gives semantic success/error styling. */}
            <Toaster theme="system" richColors closeButton position="top-center" />
          </ThemeProvider>
        </QueryClientProvider>
      </PostHogProvider>
    </GlobalErrorBoundary>
  )
}
