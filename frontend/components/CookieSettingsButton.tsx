'use client'

export const OPEN_COOKIE_SETTINGS_EVENT = 'earningsnerd:open-cookie-settings'

export default function CookieSettingsButton() {
  return (
    <button type="button" className="min-h-11 text-left text-sm text-brand-strong underline underline-offset-2 dark:text-brand-strong-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark" onClick={() => window.dispatchEvent(new Event(OPEN_COOKIE_SETTINGS_EVENT))}>
      Cookie settings
    </button>
  )
}
