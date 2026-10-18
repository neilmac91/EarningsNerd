# Apply a browser privacy signal where consent is read and written, never only when the first choice is stored

Date: 2026-10-18 · Area: frontend / privacy

**Context.** /privacy says "We respect the 'Do Not Track' browser setting and will not track users who
have enabled it." CookieConsent's mount effect read Do Not Track only while nothing was stored: it stored
"essential only" on a first visit and never looked at the signal again. A visitor who had allowed analytics
and turned Do Not Track on later was still tracked. Once the footer's "Cookie settings" reached every
visitor (D-046), a visitor sending Do Not Track could also tick Analytics, save, and have PostHog run. No
spec showed either: each Do Not Track case, unit and e2e, set the signal before a first visit.

**Rule.**

(a) A privacy signal the browser sends (Do Not Track, and any successor the site adopts) is applied in the
two consent functions every reader goes through. `getCookiePreferences()` reads the categories it covers as
off, a read-time mask that leaves storage as written, so a choice stored before the signal is back when it
stops, unless the visitor saved while it was sent. `saveCookiePreferences()` writes them off, so the `cookieConsentChanged` detail carries off too. Never
in a mount effect, a first-visit branch or a reader's own check.

(b) The signal has one reader (`browserSendsDoNotTrack()` in `frontend/components/CookieConsent.tsx`), and
the stored choice one module: a new consent reader calls `getCookiePreferences()`.

(c) The settings dialog shows what the signal holds (the boxes unticked and disabled, a note that says why),
never a choice the functions would overrule.

(d) A spec sets the signal with a choice already stored, not only before a first visit.

**Evidence.** `frontend/components/CookieConsent.tsx` and the Do Not Track block of
`frontend/tests/unit/cookieSettingsReopen.spec.tsx`: removing the read-time mask fails 3 cases, removing the
save-time mask fails 1, leaving the boxes enabled fails 1, and a second reader of the signal planted in
`frontend/app/posthog-provider.tsx` fails the one-reader scan. Partly gated: the cases and the scan hold Do
Not Track and the stored key; a new signal's adoption is review-checked.
