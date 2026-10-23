# Let the cookie banner be the only analytics control: never read a browser privacy signal, and move /privacy's sentence with any change to that

Date: 2026-10-19, updated 2026-10-23 · Area: frontend / privacy

**Context.** /privacy said "We respect the 'Do Not Track' browser setting and will not track users who
have enabled it." CookieConsent read Do Not Track only on a first visit, where it stored "essential only"
without showing the bar, so a visitor whose browser sent the signal never saw the choice, and one who had
allowed analytics before turning the signal on was still tracked. The footer's "Cookie settings" then made
/privacy's withdrawal sentence true ("You can withdraw consent for analytics and session recording at any
time through our cookie consent banner or settings."), and #1399 first made Do Not Track win while the
browser sent it, at the two consent functions and in the dialog. The founder decided otherwise (D-049): the
banner is the only control, for every visitor. The masks, the disabled boxes and the first-visit decline
went, and /privacy's sentence changed in the same PR. The founder then scoped that sentence to the browser
(2026-10-20), since the API's account events do not wait for the choice.

**Rule.**

(a) The cookie banner (the bar, its dialog and the footer's Cookie settings) is the only analytics control.
Browser analytics stays off until the visitor allows it there. Session recording is disabled under the
founder-authorized initial-release policy (2026-10-23). No browser privacy signal (Do Not Track by any spelling, Global Privacy Control, their request headers, an SDK option that reads one)
turns them off, stands in for a first choice or hides the bar.

(b) App code reads no such signal. A change that reads one changes /privacy's sentence ("Analytics in your browser stays off until you allow it, and you can change your choice at any
time in Cookie settings. Session recording is disabled. We don't change this based on your browser's
Do Not Track setting.") in the same PR,
under a decision of the founder's.

(c) A spec that sends a signal checks both states: a first visit, where the bar shows, and a choice already
stored, which reads back as written.

**Evidence.** `frontend/components/CookieConsent.tsx`; `frontend/tests/unit/cookieSettingsReopen.spec.tsx`
(the no-reader scan over every module the app runs and the markup it serves, the code its strings carry
included, /privacy's sentence pinned beside it both ways, and the cases with the signals sent);
`consentLayer.spec.tsx` and `frontend/tests/e2e/consent-bar-yields.spec.ts` (a first visit with Do Not Track
shows the bar). A `navigator.doNotTrack` read planted in CookieConsent.tsx fails the scan, and so does one
planted in app/layout.tsx's inline theme script, a string the page runs before hydration; main's first-visit
decline put back fails consentLayer; and /privacy's old sentence, in place of the founder's or beside it,
fails the pin. Partly gated: a signal's name assembled at run time, a header's name in a string with a space
in it that is not code and not handed to `RegExp` (copy names the headers that way), and the API
(`backend/`), are review-checked.
