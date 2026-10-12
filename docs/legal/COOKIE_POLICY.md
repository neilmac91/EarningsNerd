# Cookie choices — implementation review

Reviewed **12 October 2026**. This is a source inventory, not a separate customer notice or a statement of legal compliance. The maintained website disclosure is the [privacy page](../../frontend/app/privacy/page.tsx). The proposed controls remain unmerged and undeployed.

## Browser choices

[CookieConsent.tsx](../../frontend/components/CookieConsent.tsx) stores choices in local storage under `cookie_consent`. Optional PostHog browser analytics and recording require an enabling choice. Recording has a separate switch and also requires browser analytics. Accept All enables analytics, not recording; Reject All disables both. Saved choices take precedence over Do Not Track. If there is no saved choice, Do Not Track supplies essential-only defaults.

The Cookie settings button in the footer and privacy page reopens the existing shared preferences dialog. Cancel/Escape do not save edited choices; Save Preferences writes them and dispatches the existing consent-change event. Essential storage cannot be disabled through this optional-analytics control.

[posthog-provider.tsx](../../frontend/app/posthog-provider.tsx) applies those changes to browser capture and recording. [postHogPrivacy.ts](../../frontend/lib/postHogPrivacy.ts) configures input masking and telemetry sanitization; displayed page content can still appear in recordings. Masking is not a guarantee that every sensitive detail is absent.

## Separate processing

The browser switches do not turn off account/quota records, server-side usage/cost telemetry, security/error reporting or cookieless Vercel traffic measurements. Do not label every analytics/diagnostic flow as consent-gated or anonymous. The privacy page distinguishes these uses.

Authentication cookies and functional storage support sign-in, session state and social sign-in. Their implementation is in [the auth router](../../backend/app/routers/auth.py) and [refresh token service](../../backend/app/services/refresh_token_service.py). Verify actual deployed names, flags, durations and storage behaviour before publishing an itemised table; do not assume every functional cookie is HttpOnly or that every provider has the same lifecycle.

## Verification and further review

The new reopening/withdrawal regression test covers saved choices, Cancel, focus return, saving both optional choices off and persistence on reopening. Final local lint/type checking, 1,991 frontend tests, build and backend gates pass. Revised preview rendering and saved-choice cancellation/withdrawal passed in the in-app browser in both themes and mobile views. No existing cookies, privacy settings, account data or provider settings are changed by this document.

Confirm applicable consent/notice duties, actual production cookies and provider retention settings before asserting a complete cookie inventory. Privacy questions go to **privacy@earningsnerd.io**. Full personal identity details, an address, an entity or jurisdiction are not added.
