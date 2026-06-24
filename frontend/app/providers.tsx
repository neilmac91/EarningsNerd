'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { Toaster } from 'sonner'
import { IconContext, type IconProps } from '@phosphor-icons/react'
import { ThemeProvider } from '@/components/ThemeProvider'
import { PostHogProvider } from './posthog-provider'
import { GlobalErrorBoundary } from '@/components/GlobalErrorBoundary'

// App-wide Phosphor icon defaults. size:24 matches Lucide's former 24px default so any icon
// without an explicit Tailwind h-/w- class keeps its size (Phosphor would otherwise fall back
// to 1em). Per-icon `h-/w-` classes still win via CSS. Module-level constant so the provider
// value is referentially stable and never re-renders consumers.
const ICON_DEFAULTS: IconProps = { size: 24, weight: 'regular' }

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
    <IconContext.Provider value={ICON_DEFAULTS}>
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
    </IconContext.Provider>
  )
}
