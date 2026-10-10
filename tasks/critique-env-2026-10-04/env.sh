# Build/runtime env for the critique environment (source this file; see README.md). Flags mirror production (analysis + calendar on,
# quality badge on, full-text search OFF in prod but enabled here so the plan's /search surface can be
# inspected; the report flags the production 404). Example filing = 3 (the public Apple 10-K).
export NEXT_PUBLIC_API_BASE_URL=http://localhost:8010
export NEXT_PUBLIC_EXAMPLE_FILING_ID=3
export NEXT_PUBLIC_ENABLE_ANALYSIS=true
export NEXT_PUBLIC_ENABLE_CALENDAR=true
export NEXT_PUBLIC_ENABLE_FULLTEXT_SEARCH=true
export NEXT_PUBLIC_ENABLE_QUALITY_BADGE=true
export NEXT_PUBLIC_ENABLE_FINANCIAL_CHARTS=false
export NEXT_PUBLIC_ENABLE_PRO_TRIAL=false
export NEXT_PUBLIC_POSTHOG_KEY=
export NEXT_PUBLIC_SENTRY_DSN=
export SENTRY_DSN=
export WAITLIST_MODE=false
export NEXT_TELEMETRY_DISABLED=1
# Browser: an explicit CHROMIUM_PATH is preserved; otherwise the cloud image's preinstalled Chromium is offered when present,
# and browser.mjs falls back to Playwright's own browser or errors with the remedy.
if [ -z "${CHROMIUM_PATH:-}" ] && [ -x /opt/pw-browsers/chromium ]; then export CHROMIUM_PATH=/opt/pw-browsers/chromium; fi
