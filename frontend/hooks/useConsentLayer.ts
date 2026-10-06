'use client'

import { useSyncExternalStore } from 'react'
import { isConsentLayerVisible, subscribeConsentLayer } from '@/lib/consentLayer'

const serverSnapshot = () => false

/**
 * Whether the cookie-consent bar is on screen. `false` on the server and during hydration (the bar
 * mounts only after it, from localStorage), then live through lib/consentLayer's event. Consumers
 * that only need the bar's height use the `--consent-inset` CSS variable instead of this hook.
 */
export function useConsentLayer(): boolean {
  return useSyncExternalStore(subscribeConsentLayer, isConsentLayerVisible, serverSnapshot)
}

export default useConsentLayer
