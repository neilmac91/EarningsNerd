'use client'

import { QueryClient, QueryClientProvider, type DefaultOptions } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Toaster } from 'sonner'
import { IconContext, type IconProps } from '@phosphor-icons/react'
import { ThemeProvider, useTheme } from '@/components/ThemeProvider'
import { PostHogProvider } from './posthog-provider'
import { GlobalErrorBoundary } from '@/components/GlobalErrorBoundary'
import FeedbackWidget from '@/features/feedback/components/FeedbackWidget'
import { subscribeAccountQueryReset } from '@/features/auth/lib/accountQueryState'
import { usePostHogUserIdentification } from '@/hooks/usePostHogUserIdentification'

// Sets `is_pro`/`plan` PostHog person properties app-wide once the user + subscription resolve
// (roadmap 2.4). Renders nothing; lives inside the Query + PostHog providers so the hook has both.
function UserIdentificationSync() {
  usePostHogUserIdentification()
  return null
}

// App-wide Phosphor icon defaults. size:24 matches Lucide's former 24px default so any icon
// without an explicit Tailwind h-/w- class keeps its size (Phosphor would otherwise fall back
// to 1em). Per-icon `h-/w-` classes still win via CSS. Module-level constant so the provider
// value is referentially stable and never re-renders consumers.
const ICON_DEFAULTS: IconProps = { size: 24, weight: 'regular' }

// The DS focus ring on Sonner's focusable toasts and their buttons. Sonner injects its own grey
// `:focus-visible` shadow at runtime with equal or higher specificity, so the shadow needs `!`.
// siteChromeFocusRing.spec.ts pins every class slot below.
const TOAST_RING = 'focus-visible:outline-none focus-visible:!shadow-ring-brand dark:focus-visible:!shadow-ring-brand-dark'
// Every toast is a panel card on the tokens, in both themes. Sonner's own surface rules
// (`[data-sonner-toast][data-styled=true]`, two attributes) outrank a single utility class, so the
// surface takes `!` as the ring does; the focus ring still wins on focus (it adds a pseudo-class).
// Without richColors a status toast keeps the panel ground and its icon carries the status ink: each of
// Sonner's four status types (success, error, warning, info) has its slot, so a type the app calls is
// never left in the neutral ink (the admin invites page calls toast.warning).
// The card floats over the page, so it takes the ladder's overlay step (e4, as the popovers do), and
// no shadow in dark like every other overlay.
// The close button's forced rest outranks Sonner's own hover too, so the slot states its hover, forced
// as well: the quiet controls' tint (brand-weak) and the primary ink in light; in dark the primary ink
// over the panel it keeps, since the button overhangs the card's corner and a translucent tint there
// would show the page through it.
// toastTokens.spec.tsx holds these slots to token classes. Each slot is one literal, written whole,
// so the ring gate and the token gate read it as it ships.
const TOAST_CARD =
  '!border-border-light !bg-panel-light !text-text-primary-light !shadow-e4 dark:!border-border-dark dark:!bg-panel-dark dark:!text-text-primary-dark dark:!shadow-none focus-visible:outline-none focus-visible:!shadow-ring-brand dark:focus-visible:!shadow-ring-brand-dark'
const TOAST_CLOSE =
  '!border-border-light !bg-panel-light !text-text-secondary-light hover:!bg-brand-weak hover:!text-text-primary-light dark:!border-border-dark dark:!bg-panel-dark dark:!text-text-secondary-dark dark:hover:!bg-brand-weak-dark dark:hover:!text-white focus-visible:outline-none focus-visible:!shadow-ring-brand dark:focus-visible:!shadow-ring-brand-dark'
export const TOAST_OPTIONS = {
  classNames: {
    toast: TOAST_CARD,
    description: '!text-text-secondary-light dark:!text-text-secondary-dark',
    success: '[&_[data-icon]]:text-success-light dark:[&_[data-icon]]:text-success-dark',
    error: '[&_[data-icon]]:text-error-light dark:[&_[data-icon]]:text-error-dark',
    warning: '[&_[data-icon]]:text-warning-light dark:[&_[data-icon]]:text-warning-dark',
    info: '[&_[data-icon]]:text-info-light dark:[&_[data-icon]]:text-info-dark',
    closeButton: TOAST_CLOSE,
    actionButton: TOAST_RING,
    cancelButton: TOAST_RING,
  },
}

// Transient action feedback. The theme comes from ThemeProvider (the site's own toggle, stored in
// localStorage), not "system": Sonner's "system" reads prefers-color-scheme, so a reader who chose
// light on a dark OS got dark toasts. No richColors: those are Sonner's own palette, not the tokens.
export function ThemedToaster() {
  const { theme } = useTheme()
  return <Toaster theme={theme} closeButton position="top-center" toastOptions={TOAST_OPTIONS} />
}

/** The app's QueryClient defaults. Exported so a spec that models the app's cache builds its client from them
 *  (failedLogoutChecksSession.spec.tsx). */
export const QUERY_CLIENT_DEFAULTS: DefaultOptions = {
  queries: {
    staleTime: 60 * 1000, // 1 minute
    refetchOnWindowFocus: false,
  },
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({ defaultOptions: QUERY_CLIENT_DEFAULTS }))

  useEffect(() => subscribeAccountQueryReset(queryClient), [queryClient])

  return (
    <IconContext.Provider value={ICON_DEFAULTS}>
      <GlobalErrorBoundary>
        <PostHogProvider>
          <QueryClientProvider client={queryClient}>
            <ThemeProvider>
              <UserIdentificationSync />
              {children}
              {/* Beta feedback launcher — renders only for logged-in users (client-side session check). */}
              <FeedbackWidget />
              <ThemedToaster />
            </ThemeProvider>
          </QueryClientProvider>
        </PostHogProvider>
      </GlobalErrorBoundary>
    </IconContext.Provider>
  )
}
