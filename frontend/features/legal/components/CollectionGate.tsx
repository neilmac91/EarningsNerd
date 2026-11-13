'use client'

import { useEffect, useRef, type ReactNode } from 'react'
import Link from 'next/link'
import { Notice } from '@/components/ui'
import { CONTACT_ADDRESSES, contactMailto } from '@/lib/contactAddresses'
import { CollectionLoading } from './CollectionLoading'
import { useLegalReadiness } from '../hooks/useLegalReadiness'
import type { LegalReadiness } from '../api/legal-api'
import { legalLinkClass } from '../lib/legalLinkClass'

export function CollectionUnavailable({ title, description, showLogin = true }: { title: string; description?: string; showLogin?: boolean }) {
  return <Notice variant="info" title={title} description={<>
    {description && <>{description}{' '}</>}
    Existing account support remains available at{' '}
    <a href={contactMailto('support')} className={legalLinkClass}>{CONTACT_ADDRESSES.support}</a>.{' '}
    For privacy requests, contact <a href={contactMailto('privacy')} className={legalLinkClass}>{CONTACT_ADDRESSES.privacy}</a>.
    {showLogin && <> You can still <Link href="/login" className={legalLinkClass}>log in</Link>.</>}
  </>} />
}

/** Do not mount fields or third-party CAPTCHA before the collection decision is available. */
export function CollectionGate({ title, surface, children }: {
  title: string
  surface: 'contact' | 'waitlist'
  children: (recheck: () => Promise<LegalReadiness | null>) => ReactNode
}) {
  const { readiness, loading, recheck } = useLegalReadiness()
  const available = readiness?.collection_available === true
  const wasAvailable = useRef(false)
  const statusRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (wasAvailable.current && !available && document.activeElement === document.body) {
      statusRef.current?.focus({ preventScroll: true })
    }
    wasAvailable.current = available
  }, [available])

  return loading ? <CollectionLoading surface={surface} /> : available ? children(recheck) : (
    <div ref={statusRef} tabIndex={-1} className="rounded-lg focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">
      <CollectionUnavailable title={title} />
    </div>
  )
}
