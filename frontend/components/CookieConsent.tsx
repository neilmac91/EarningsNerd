'use client'

import { CONTACT_ADDRESSES, contactMailto } from '@/lib/contactAddresses'
import { useCallback, useState, useEffect, useLayoutEffect, useRef } from 'react'
import { toast } from 'sonner'
import { CookieIcon } from '@/lib/icons'
import { OPEN_COOKIE_SETTINGS_EVENT } from '@/lib/cookieSettings'
import Link from 'next/link'
import { Button, Checkbox, Modal, ModalBody, ModalFooter, ModalHeader } from '@/components/ui'
import { isConsentLayerVisible, publishConsentLayer } from '@/lib/consentLayer'
import { ANALYTICS_CONSENT_CLAUSE } from '@/lib/consentCopy'
import { getCookiePreferences, saveCookiePreferences, subscribeCookiePreferences, type CookiePreferences } from '@/lib/browserConsent'

// Isomorphic layout effect (the repo's SSR-safe alias, as in ui/Input and useCountUp): useLayoutEffect
// in the browser, where the consent inset must land before the bar's first paint; useEffect on a server
// renderer, which never renders the bar anyway. The ladder gate reads the alias by its declaration.
const useIsoLayoutEffect = typeof window !== 'undefined' ? useLayoutEffect : useEffect

// Kept as re-exports for existing callers; the plain store is also usable at SDK send boundaries.
export { CONSENT_VERSION, getCookiePreferences, saveCookiePreferences, clearCookiePreferences, type CookiePreferences } from '@/lib/browserConsent'

const DEFAULT_PREFERENCES: CookiePreferences = {
  essential: true,
  analytics: false,
  sessionRecording: false,
  timestamp: new Date().toISOString(),
}

interface CookieConsentProps {
  onPreferencesChanged?: (preferences: CookiePreferences) => void
}

export default function CookieConsent({ onPreferencesChanged }: CookieConsentProps) {
  const [showBanner, setShowBanner] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [preferences, setPreferences] = useState<CookiePreferences>(DEFAULT_PREFERENCES)
  const barRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const followChoice = () => {
      const choice = getCookiePreferences()
      if (!choice) {
        if (!isConsentLayerVisible()) publishConsentLayer(0)
        setShowBanner(true)
        setPreferences(DEFAULT_PREFERENCES)
      } else {
        setShowBanner(false)
        setPreferences(choice)
        onPreferencesChanged?.(choice)
      }
    }
    followChoice()
    return subscribeCookiePreferences(followChoice)
  }, [onPreferencesChanged])

  // The consent layer (lib/consentLayer): while the bar is on screen its height is published as
  // `--consent-inset` + `data-consent-visible` on <html>, and the bottom-anchored research chrome
  // (launchers, coachmark, workspace sheets) adds that inset to its bottom offset instead of being
  // covered — the bar sits BENEATH that chrome on z-consent. A layout effect so the offset lands
  // before the bar's first paint; ResizeObserver follows reflow (text wrapping, orientation). The
  // cleanup clears the layer the moment the bar unmounts (a choice was made).
  useIsoLayoutEffect(() => {
    if (!showBanner) return
    const bar = barRef.current
    if (!bar) return
    const measure = () => publishConsentLayer(bar.getBoundingClientRect().height)
    measure()
    const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(measure) : null
    observer?.observe(bar)
    return () => {
      observer?.disconnect()
      publishConsentLayer(null)
    }
  }, [showBanner])

  // The confirmation is an ordinary top-centre toast (app/providers.tsx mounts the Toaster), not a
  // fixed corner element: it must not share the bottom-right corner with the "Ask this Filing"
  // launcher it used to cover.
  const applyChoice = (choice: CookiePreferences) => {
    const result = saveCookiePreferences(choice)
    setPreferences(result.preferences)
    setShowSettings(false)
    setShowBanner(false)
    if (result.persisted) toast.success('Cookie preferences saved')
    else toast.error('Cookie preferences could not be saved', {
      description: 'Your choice applies in this tab. Browser storage is unavailable, so check Cookie settings after reloading or opening another tab.',
      duration: 10000,
    })
  }

  const handleAllowAnalytics = () => applyChoice({ ...DEFAULT_PREFERENCES, analytics: true })
  const handleEssentialOnly = () => applyChoice(DEFAULT_PREFERENCES)
  const handleSavePreferences = () => applyChoice(preferences)

  // The banner stays mounted beneath the settings dialog, so Cancel / Escape / the X return focus to
  // the Customize button that opened it (Save still dismisses both). Its state stays mounted too, so
  // the draft starts from the saved choices on every open: a dismissed edit must not come back, or be
  // saved by a later Save.
  const handleOpenSettings = useCallback(() => {
    setPreferences(getCookiePreferences() ?? DEFAULT_PREFERENCES)
    setShowSettings(true)
  }, [])

  // After a first choice the bar is gone; the footer's "Cookie settings" (lib/cookieSettings.ts) opens this
  // same dialog on the stored choices, and Save writes them and fires cookieConsentChanged as the bar does,
  // so /privacy's analytics withdrawal sentence holds. ui/Modal returns focus to the control that opened it.
  useEffect(() => {
    window.addEventListener(OPEN_COOKIE_SETTINGS_EVENT, handleOpenSettings)
    return () => window.removeEventListener(OPEN_COOKIE_SETTINGS_EVENT, handleOpenSettings)
  }, [handleOpenSettings])

  if (!showBanner && !showSettings) return null

  // ui/Modal owns the dialog contract (focus in, Tab cycle, Escape, scroll lock, focus return);
  // Escape and the scrim close it exactly as Cancel does. The primitive also owns viewport
  // sizing and inner scrolling so every category stays reachable on a short screen.
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
        Cookie preferences
      </ModalHeader>

      <ModalBody>
        <p className="text-text-secondary-light dark:text-text-secondary-dark mb-6">
          Essential cookies keep you logged in and the site working. Analytics cookies are off until
          you allow them here. Session recording is disabled.
        </p>

        {/* Each category row takes the Notice's recipe (components/ui/Notice.tsx): it wraps, and its text keeps
            9rem beside the box or takes the card's width with the box under it, so at 200% text no box leaves
            its card (tests/e2e/reflow-200.spec.ts). At the default size the box stays beside its text. */}
        <div className="space-y-4">
          {/* Essential cookies */}
          <div className="border border-border-light dark:border-border-dark rounded-lg p-cap-4">
            <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-3">
              <div className="min-w-0 flex-[1_1_9rem] break-words">
                <h3
                  id="cookie-essential-title"
                  className="font-semibold text-text-primary-light dark:text-text-primary-dark mb-2"
                >
                  Essential cookies
                </h3>
                <p id="cookie-essential-desc" className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                  Required for the website to function properly. These include authentication,
                  security, and basic functionality. Cannot be disabled.
                </p>
              </div>
              <div>
                <Checkbox
                  checked={true}
                  disabled
                  aria-labelledby="cookie-essential-title"
                  aria-describedby="cookie-essential-desc"
                />
              </div>
            </div>
          </div>

          {/* Analytics cookies */}
          <div className="border border-border-light dark:border-border-dark rounded-lg p-cap-4">
            <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-3">
              <div className="min-w-0 flex-[1_1_9rem] break-words">
                <h3
                  id="cookie-analytics-title"
                  className="font-semibold text-text-primary-light dark:text-text-primary-dark mb-2"
                >
                  Analytics cookies
                </h3>
                <p id="cookie-analytics-desc" className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                  {ANALYTICS_CONSENT_CLAUSE}
                </p>
              </div>
              <div>
                <Checkbox
                  checked={preferences.analytics}
                  onChange={(e) =>
                    setPreferences({ ...preferences, analytics: e.target.checked })
                  }
                  aria-labelledby="cookie-analytics-title"
                  aria-describedby="cookie-analytics-desc"
                />
              </div>
            </div>
          </div>

          {/* Session recording */}
          <div className="border border-border-light dark:border-border-dark rounded-lg p-cap-4">
            <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-3">
              <div className="min-w-0 flex-[1_1_9rem] break-words">
                <h3
                  id="cookie-recording-title"
                  className="font-semibold text-text-primary-light dark:text-text-primary-dark mb-2"
                >
                  Session recording
                </h3>
                <p id="cookie-recording-desc" className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                  Disabled. We do not record browsing sessions.
                </p>
              </div>
              <div>
                <Checkbox
                  checked={false}
                  disabled
                  aria-labelledby="cookie-recording-title"
                  aria-describedby="cookie-recording-desc"
                />
              </div>
            </div>
          </div>
        </div>

        <p className="mt-4 text-xs text-text-secondary-light dark:text-text-secondary-dark">
          For more information, see our{' '}
          <Link href="/privacy" className="text-brand-strong dark:text-brand-strong-dark hover:underline focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">
            Privacy Policy
          </Link>. For cookie or privacy questions, email{' '}
          <a href={contactMailto('privacy')} className="break-all text-brand-strong underline dark:text-brand-strong-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">{CONTACT_ADDRESSES.privacy}</a>.
        </p>
      </ModalBody>

      <ModalFooter>
        <Button variant="secondary" onClick={() => setShowSettings(false)} className="w-full sm:w-auto">
          Cancel
        </Button>
        <Button onClick={handleSavePreferences} className="w-full sm:w-auto">
          Save preferences
        </Button>
      </ModalFooter>
    </Modal>
  )

  if (!showBanner) return settings

  return (
    <>
      {/* z-consent: above in-page sticky chrome, beneath the workspace sheets' scrims (z-scrim: an open
          sheet dims this bar and makes it inert, as any modal does) and the research chrome (sheets,
          launchers, coachmark), which yields its height via --consent-inset (see the layout effect
          above). pb-[env(safe-area-inset-bottom)] keeps the choices clear of the home indicator; the
          measured height includes it. A named region so assistive tech can find it. */}
      <div
        ref={barRef}
        role="region"
        aria-label="Cookie consent"
        className="fixed bottom-0 left-0 right-0 z-consent pb-[env(safe-area-inset-bottom)] bg-panel-light dark:bg-panel-dark border-t border-border-light dark:border-border-dark shadow-e5 dark:shadow-none"
      >
        <div className="max-w-7xl mx-auto p-4 sm:p-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
            <div className="flex items-start gap-3 flex-1">
              <CookieIcon className="h-6 w-6 text-brand-strong dark:text-brand-strong-dark flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="font-semibold text-text-primary-light dark:text-text-primary-dark mb-1">
                  Cookies on this site
                </h3>
                <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                  Essential cookies keep you logged in. Analytics cookies stay off until you allow
                  them. Session recording is disabled.{' '}
                  <Link href="/privacy" className="text-brand-strong dark:text-brand-strong-dark hover:underline focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">
                    Learn more
                  </Link>
                </p>
              </div>
            </div>

            <div className="flex flex-wrap gap-3 w-full sm:w-auto">
              <Button variant="ghost" onClick={handleOpenSettings}>
                Customize
              </Button>
              <Button variant="secondary" onClick={handleEssentialOnly}>
                Essential only
              </Button>
              <Button variant="secondary" onClick={handleAllowAnalytics}>
                Allow analytics
              </Button>
            </div>
          </div>
        </div>
      </div>
      {settings}
    </>
  )
}
