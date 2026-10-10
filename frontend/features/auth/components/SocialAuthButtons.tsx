'use client'

import GoogleSignInButton from './GoogleSignInButton'
import AppleSignInButton from './AppleSignInButton'
import { ENABLE_APPLE_SIGNIN } from '@/lib/featureFlags'

/**
 * Social-first auth block. Apple appears above Google when enabled (it ships
 * behind a flag until the backend exchange + Apple Developer setup are live).
 * `invite` (the closed-beta token from the magic link) rides along to the
 * backend start endpoints, which redeem it when they create the account.
 */
export default function SocialAuthButtons({
  apiBase,
  invite,
  appleLabel,
  googleLabel,
}: {
  apiBase: string
  invite?: string
  appleLabel?: string
  googleLabel?: string
}) {
  return (
    <div className="space-y-3">
      {ENABLE_APPLE_SIGNIN && <AppleSignInButton apiBase={apiBase} invite={invite} label={appleLabel} />}
      <GoogleSignInButton apiBase={apiBase} invite={invite} label={googleLabel} />
    </div>
  )
}
