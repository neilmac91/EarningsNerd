'use client'

import { useLegalReadiness } from '../hooks/useLegalReadiness'
import { CONTACT_ADDRESSES, contactMailto } from '@/lib/contactAddresses'

const legalLinkClass = 'box-decoration-clone rounded-sm font-medium text-brand-strong underline underline-offset-4 focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark'

/** Operator details come only from the backend's explicitly public disclosure, never bundled configuration. */
export function LegalOperatorNotice() {
  const { readiness } = useLegalReadiness()
  const operator = readiness?.operator
  return (
    <section className="mt-8">
      <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">Service operator</h2>
      {operator ? <address className="whitespace-pre-line not-italic text-text-secondary-light dark:text-text-secondary-dark">
        {operator.legal_name}{'\n'}{operator.postal_address}{'\n'}{operator.country}{'\n'}{operator.contact_email}
      </address> : <p className="text-text-secondary-light dark:text-text-secondary-dark">
        Operator details are currently unavailable here. For existing account support, contact{' '}
        <a href={contactMailto('support')} className={legalLinkClass}>{CONTACT_ADDRESSES.support}</a>.{' '}
        For privacy requests, contact <a href={contactMailto('privacy')} className={legalLinkClass}>{CONTACT_ADDRESSES.privacy}</a>.
      </p>}
    </section>
  )
}
