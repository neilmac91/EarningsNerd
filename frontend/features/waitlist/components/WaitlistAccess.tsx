'use client'

import Link from 'next/link'
import { cx } from '@/components/ui/cx'
import { usePublicAccess, usePublicReadiness } from '@/features/marketing/components/PublicAccessProvider'
import WaitlistCounter from './WaitlistCounter'

export function WaitlistAccessStatus() {
  const { readiness } = usePublicReadiness()
  const access = usePublicAccess('invite')
  return readiness?.collection_available === true
    ? <WaitlistCounter />
    : <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">{access.line}</p>
}

export function WaitlistEntryLink({ className }: { className: string }) {
  const { readiness } = usePublicReadiness()
  const access = usePublicAccess('invite')
  const available = readiness?.collection_available === true
  return (
    <Link
      href={available ? '#waitlist' : access.href}
      className={cx('focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark', className)}
    >
      {available ? 'Join the waitlist' : access.cta}
    </Link>
  )
}
