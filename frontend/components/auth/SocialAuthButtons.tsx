'use client'

import GoogleSignInButton from './GoogleSignInButton'
import AppleSignInButton from './AppleSignInButton'
import { ENABLE_APPLE_SIGNIN } from '@/lib/featureFlags'

/**
 * Social-first auth block. Apple appears above Google when enabled (it ships
 * behind a flag until the backend exchange + Apple Developer setup are live).
 */
export default function SocialAuthButtons({
  apiBase,
  appleLabel,
  googleLabel,
}: {
  apiBase: string
  appleLabel?: string
  googleLabel?: string
}) {
  return (
    <div className="space-y-3">
      {ENABLE_APPLE_SIGNIN && <AppleSignInButton apiBase={apiBase} label={appleLabel} />}
      <GoogleSignInButton apiBase={apiBase} label={googleLabel} />
    </div>
  )
}
