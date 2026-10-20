import { createContext, useContext } from 'react'

/**
 * Whether PostHog may take an identity now: the visitor allows analytics (through getCookiePreferences) and the SDK
 * has loaded, or no PostHog key is configured and there is nothing to wait for.
 * app/posthog-provider.tsx sets it as it applies each consent change, and account identification
 * (hooks/usePostHogUserIdentification.ts) waits on it, so a reader already signed in is identified once a first allow
 * from the footer's Cookie settings has loaded the SDK, however late its `loaded` callback comes. Outside the
 * provider it reads true, leaving the consent check to the reader.
 */
export const PostHogReadyContext = createContext(true)

export const usePostHogReady = (): boolean => useContext(PostHogReadyContext)
