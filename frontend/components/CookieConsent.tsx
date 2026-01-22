'use client'

import { useState, useEffect } from 'react'
import { X, Cookie, CheckCircle2 } from 'lucide-react'
import Link from 'next/link'

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
      const doNotTrack =
        navigator.doNotTrack === '1' ||
        (window as unknown as { doNotTrack?: string }).doNotTrack === '1'

      if (doNotTrack) {
        // Respect DNT by only enabling essential cookies
        const dntPreferences = { ...DEFAULT_PREFERENCES }
        saveCookiePreferences(dntPreferences)
        onPreferencesChanged?.(dntPreferences)
      } else {
        // Show banner for first-time visitors
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

  const handleOpenSettings = () => {
    setShowSettings(true)
    setShowBanner(false)
  }

  if (!showBanner && !showSettings) {
    return saved ? (
      <div className="fixed bottom-4 right-4 z-50 bg-green-600 text-white px-4 py-2 rounded-lg shadow-lg flex items-center gap-2 animate-slide-up">
        <CheckCircle2 className="h-5 w-5" />
        <span>Cookie preferences saved</span>
      </div>
    ) : null
  }

  if (showSettings) {
    return (
      <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
        <div className="bg-white dark:bg-slate-800 rounded-lg shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
          <div className="p-6">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <Cookie className="h-6 w-6 text-blue-600" />
                <h2 className="text-2xl font-bold text-slate-900 dark:text-white">
                  Cookie Preferences
                </h2>
              </div>
              <button
                onClick={() => setShowSettings(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
              >
                <X className="h-6 w-6" />
              </button>
            </div>

            <p className="text-slate-600 dark:text-slate-400 mb-6">
              We use cookies to enhance your experience, analyze site traffic, and provide
              personalized content. Choose which cookies you&apos;re comfortable with.
            </p>

            <div className="space-y-4">
              {/* Essential Cookies */}
              <div className="border border-slate-200 dark:border-slate-700 rounded-lg p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="font-semibold text-slate-900 dark:text-white mb-2">
                      Essential Cookies
                    </h3>
                    <p className="text-sm text-slate-600 dark:text-slate-400">
                      Required for the website to function properly. These include authentication,
                      security, and basic functionality. Cannot be disabled.
                    </p>
                  </div>
                  <div className="ml-4">
                    <input
                      type="checkbox"
                      checked={true}
                      disabled
                      className="h-5 w-5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 opacity-50 cursor-not-allowed"
                    />
                  </div>
                </div>
              </div>

              {/* Analytics Cookies */}
              <div className="border border-slate-200 dark:border-slate-700 rounded-lg p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="font-semibold text-slate-900 dark:text-white mb-2">
                      Analytics Cookies
                    </h3>
                    <p className="text-sm text-slate-600 dark:text-slate-400">
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
                      className="h-5 w-5 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                    />
                  </div>
                </div>
              </div>

              {/* Session Recording */}
              <div className="border border-slate-200 dark:border-slate-700 rounded-lg p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="font-semibold text-slate-900 dark:text-white mb-2">
                      Session Recording
                    </h3>
                    <p className="text-sm text-slate-600 dark:text-slate-400">
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
                      className="h-5 w-5 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-6 flex gap-3">
              <button
                onClick={handleSavePreferences}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition-colors"
              >
                Save Preferences
              </button>
              <button
                onClick={() => setShowSettings(false)}
                className="px-4 py-2 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
              >
                Cancel
              </button>
            </div>

            <p className="mt-4 text-xs text-slate-500 dark:text-slate-400">
              For more information, see our{' '}
              <Link href="/privacy" className="text-blue-600 hover:underline">
                Privacy Policy
              </Link>
              .
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-700 shadow-2xl">
      <div className="max-w-7xl mx-auto p-4 sm:p-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
          <div className="flex items-start gap-3 flex-1">
            <Cookie className="h-6 w-6 text-blue-600 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-1">
                We value your privacy
              </h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                We use cookies to enhance your experience and analyze site usage. You can choose
                which cookies to accept.{' '}
                <Link href="/privacy" className="text-blue-600 hover:underline">
                  Learn more
                </Link>
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-3 w-full sm:w-auto">
            <button
              onClick={handleOpenSettings}
              className="px-4 py-2 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors border border-slate-300 dark:border-slate-600"
            >
              Customize
            </button>
            <button
              onClick={handleRejectAll}
              className="px-4 py-2 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
            >
              Reject All
            </button>
            <button
              onClick={handleAcceptAll}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium"
            >
              Accept All
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
