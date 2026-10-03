'use client'

import { useState, useEffect } from 'react'
import { CheckCircleIcon, CookieIcon } from '@/lib/icons'
import Link from 'next/link'
import { Button, Modal, ModalBody, ModalFooter, ModalHeader } from '@/components/ui'

export interface CookiePreferences {
  essential: boolean
  analytics: boolean
  sessionRecording: boolean
  timestamp: string
}

const DEFAULT_PREFERENCES: CookiePreferences = {
  essential: true, // Always true - required for the site to function
  analytics: false,
  sessionRecording: false,
  timestamp: new Date().toISOString(),
}

const STORAGE_KEY = 'cookie_consent'

export function getCookiePreferences(): CookiePreferences | null {
  if (typeof window === 'undefined') return null

  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (!stored) return null

    const preferences = JSON.parse(stored) as CookiePreferences
    // Ensure essential is always true
    preferences.essential = true
    return preferences
  } catch (error) {
    console.error('Failed to load cookie preferences:', error)
    return null
  }
}

export function saveCookiePreferences(preferences: CookiePreferences): void {
  if (typeof window === 'undefined') return

  try {
    // Ensure essential is always true
    preferences.essential = true
    preferences.timestamp = new Date().toISOString()
    localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences))

    // Dispatch event so PostHog can react to changes
    window.dispatchEvent(new CustomEvent('cookieConsentChanged', { detail: preferences }))
  } catch (error) {
    console.error('Failed to save cookie preferences:', error)
  }
}

export function clearCookiePreferences(): void {
  if (typeof window === 'undefined') return
  localStorage.removeItem(STORAGE_KEY)
}

interface CookieConsentProps {
  onPreferencesChanged?: (preferences: CookiePreferences) => void
}

export default function CookieConsent({ onPreferencesChanged }: CookieConsentProps) {
  const [showBanner, setShowBanner] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [preferences, setPreferences] = useState<CookiePreferences>(DEFAULT_PREFERENCES)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    // Check if user has already set preferences
    const existingPreferences = getCookiePreferences()

    if (!existingPreferences) {
      // Check "Do Not Track" browser setting
      // Note: window.doNotTrack is non-standard but supported by some browsers
      const windowDoNotTrack = 'doNotTrack' in window ? (window as Window & { doNotTrack?: string }).doNotTrack : undefined
      const doNotTrack =
        navigator.doNotTrack === '1' ||
        windowDoNotTrack === '1'

      if (doNotTrack) {
        // Respect DNT by only enabling essential cookies
        const dntPreferences = { ...DEFAULT_PREFERENCES }
        saveCookiePreferences(dntPreferences)
        onPreferencesChanged?.(dntPreferences)
      } else {
        // Show banner for first-time visitors
        // eslint-disable-next-line react-hooks/set-state-in-effect -- mount-time init: banner visibility depends on localStorage/DNT, only readable client-side after hydration
        setShowBanner(true)
      }
    } else {
      // Use existing preferences
      setPreferences(existingPreferences)
      onPreferencesChanged?.(existingPreferences)
    }
  }, [onPreferencesChanged])

  const handleAcceptAll = () => {
    const newPreferences: CookiePreferences = {
      essential: true,
      analytics: true,
      sessionRecording: false, // Keep this opt-in only (more privacy-conscious default)
      timestamp: new Date().toISOString(),
    }
    saveCookiePreferences(newPreferences)
    setPreferences(newPreferences)
    onPreferencesChanged?.(newPreferences)
    setShowBanner(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 3000)
  }

  const handleRejectAll = () => {
    const newPreferences: CookiePreferences = {
      ...DEFAULT_PREFERENCES,
      timestamp: new Date().toISOString(),
    }
    saveCookiePreferences(newPreferences)
    setPreferences(newPreferences)
    onPreferencesChanged?.(newPreferences)
    setShowBanner(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 3000)
  }

  const handleSavePreferences = () => {
    saveCookiePreferences(preferences)
    onPreferencesChanged?.(preferences)
    setShowSettings(false)
    setShowBanner(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 3000)
  }

  // The banner stays mounted beneath the settings dialog, so Cancel / Escape / the X return focus to
  // the Customize button that opened it (Save still dismisses both).
  const handleOpenSettings = () => {
    setShowSettings(true)
  }

  if (!showBanner && !showSettings) {
    return saved ? (
      <div className="fixed bottom-4 right-4 z-50 bg-success-light dark:bg-success-dark text-white px-4 py-2 rounded-lg shadow-e2 flex items-center gap-2 animate-fade-up">
        <CheckCircleIcon className="h-5 w-5" />
        <span>Cookie preferences saved</span>
      </div>
    ) : null
  }

  // ui/Modal owns the dialog contract (focus in, Tab cycle, Escape, scroll lock, focus return);
  // Escape and the scrim close it exactly as Cancel does. The primitive also owns viewport
  // sizing and inner scrolling so all three categories stay reachable on a short screen.
  const settings = (
    <Modal
      open={showSettings}
      onClose={() => setShowSettings(false)}
      labelledBy="cookie-settings-title"
      size="lg"
    >
      <ModalHeader
        id="cookie-settings-title"
        icon={<CookieIcon className="h-5 w-5" />}
        onClose={() => setShowSettings(false)}
      >
        Cookie Preferences
      </ModalHeader>

      <ModalBody>
        <p className="text-text-secondary-light dark:text-text-secondary-dark mb-6">
          We use cookies to enhance your experience, analyze site traffic, and provide
          personalized content. Choose which cookies you&apos;re comfortable with.
        </p>

        <div className="space-y-4">
          {/* Essential Cookies */}
          <div className="border border-border-light dark:border-border-dark rounded-lg p-4">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h3
                  id="cookie-essential-title"
                  className="font-semibold text-text-primary-light dark:text-text-primary-dark mb-2"
                >
                  Essential Cookies
                </h3>
                <p id="cookie-essential-desc" className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                  Required for the website to function properly. These include authentication,
                  security, and basic functionality. Cannot be disabled.
                </p>
              </div>
              <div className="ml-4">
                <input
                  type="checkbox"
                  checked={true}
                  disabled
                  aria-labelledby="cookie-essential-title"
                  aria-describedby="cookie-essential-desc"
                  className="h-5 w-5 rounded border-border-light text-brand-strong focus:shadow-ring-brand opacity-50 cursor-not-allowed"
                />
              </div>
            </div>
          </div>

          {/* Analytics Cookies */}
          <div className="border border-border-light dark:border-border-dark rounded-lg p-4">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h3
                  id="cookie-analytics-title"
                  className="font-semibold text-text-primary-light dark:text-text-primary-dark mb-2"
                >
                  Analytics Cookies
                </h3>
                <p id="cookie-analytics-desc" className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                  Help us understand how visitors interact with our website by collecting
                  anonymous usage statistics (PostHog). This helps us improve the user
                  experience.
                </p>
              </div>
              <div className="ml-4">
                <input
                  type="checkbox"
                  checked={preferences.analytics}
                  onChange={(e) =>
                    setPreferences({ ...preferences, analytics: e.target.checked })
                  }
                  aria-labelledby="cookie-analytics-title"
                  aria-describedby="cookie-analytics-desc"
                  className="h-5 w-5 rounded border-border-light text-brand-strong focus:shadow-ring-brand"
                />
              </div>
            </div>
          </div>

          {/* Session Recording */}
          <div className="border border-border-light dark:border-border-dark rounded-lg p-4">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h3
                  id="cookie-recording-title"
                  className="font-semibold text-text-primary-light dark:text-text-primary-dark mb-2"
                >
                  Session Recording
                </h3>
                <p id="cookie-recording-desc" className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                  Records your interactions with the site to help us identify and fix bugs.
                  Sensitive information (passwords, payment details) is always masked. This is
                  more invasive and is opt-in only.
                </p>
              </div>
              <div className="ml-4">
                <input
                  type="checkbox"
                  checked={preferences.sessionRecording}
                  onChange={(e) =>
                    setPreferences({ ...preferences, sessionRecording: e.target.checked })
                  }
                  aria-labelledby="cookie-recording-title"
                  aria-describedby="cookie-recording-desc"
                  className="h-5 w-5 rounded border-border-light text-brand-strong focus:shadow-ring-brand"
                />
              </div>
            </div>
          </div>
        </div>

        <p className="mt-4 text-xs text-text-secondary-light dark:text-text-secondary-dark">
          For more information, see our{' '}
          <Link href="/privacy" className="text-brand-strong dark:text-brand-strong-dark hover:underline">
            Privacy Policy
          </Link>
          .
        </p>
      </ModalBody>

      <ModalFooter>
        <Button variant="secondary" onClick={() => setShowSettings(false)} className="w-full sm:w-auto">
          Cancel
        </Button>
        <Button onClick={handleSavePreferences} className="w-full sm:w-auto">
          Save Preferences
        </Button>
      </ModalFooter>
    </Modal>
  )

  if (!showBanner) return settings

  return (
    <>
      <div className="fixed bottom-0 left-0 right-0 z-50 bg-panel-light dark:bg-panel-dark border-t border-border-light dark:border-border-dark shadow-e5 dark:shadow-none">
        <div className="max-w-7xl mx-auto p-4 sm:p-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
            <div className="flex items-start gap-3 flex-1">
              <CookieIcon className="h-6 w-6 text-brand-strong dark:text-brand-strong-dark flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="font-semibold text-text-primary-light dark:text-text-primary-dark mb-1">
                  We value your privacy
                </h3>
                <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                  We use cookies to enhance your experience and analyze site usage. You can choose
                  which cookies to accept.{' '}
                  <Link href="/privacy" className="text-brand-strong dark:text-brand-strong-dark hover:underline">
                    Learn more
                  </Link>
                </p>
              </div>
            </div>

            <div className="flex flex-wrap gap-3 w-full sm:w-auto">
              <Button variant="secondary" onClick={handleOpenSettings}>
                Customize
              </Button>
              <Button variant="ghost" onClick={handleRejectAll}>
                Reject All
              </Button>
              <Button onClick={handleAcceptAll}>
                Accept All
              </Button>
            </div>
          </div>
        </div>
      </div>
      {settings}
    </>
  )
}
