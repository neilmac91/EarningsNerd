'use client'

import { usePublicAccess } from './PublicAccessProvider'
import type { AccessMode } from '@/features/marketing/lib/access'

export default function PublicAccessLine({ accessMode }: { accessMode: AccessMode }) {
  const access = usePublicAccess(accessMode)
  return <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">{access.line}</p>
}
