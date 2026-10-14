import { CONTACT_ADDRESSES, contactMailto } from '@/lib/contactAddresses'
import { Metadata } from 'next'
import Link from 'next/link'
import { LEGAL_DATES } from '@/lib/legalDates'

export const metadata: Metadata = {
  title: 'Security | EarningsNerd',
  description: 'Account security and private vulnerability reporting for EarningsNerd.',
}

export default function SecurityPage() {
  return (
    <main className="mx-auto max-w-4xl px-4 py-12 sm:px-6 lg:px-8">
      <h1 className="text-4xl font-semibold text-text-primary-light dark:text-text-primary-dark">Security</h1>
      <p className="text-lg text-text-secondary-light dark:text-text-secondary-dark">Last updated: {LEGAL_DATES.security}</p>

      <section className="mt-8">
        <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">Account and payment protection</h2>
        <p className="text-text-secondary-light dark:text-text-secondary-dark">
          EarningsNerd uses HTTPS for connections, password hashes for password sign-in, and session and
          permission checks for protected account actions. Stripe handles card payments. Use a unique
          password, keep sign-in codes private and sign out on shared devices. No internet service can
          guarantee absolute security.
        </p>
      </section>

      <section className="mt-8">
        <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">Report a security concern</h2>
        <p className="text-text-secondary-light dark:text-text-secondary-dark">
          Report suspected vulnerabilities privately to{' '}
          <a href={contactMailto('security')} className="break-all text-brand-strong underline dark:text-brand-strong-dark">{CONTACT_ADDRESSES.security}</a>.
          Include the affected feature and steps to reproduce the issue. Allow time for investigation before
          public disclosure, and avoid accessing or changing anyone else&apos;s data. The aim is to reply within
          2 business days. Required incident notifications follow applicable law.
        </p>
      </section>

      <section className="mt-8">
        <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">Privacy and account help</h2>
        <p className="text-text-secondary-light dark:text-text-secondary-dark">
          The{' '}
          <Link href="/privacy" className="text-brand-strong underline dark:text-brand-strong-dark">Privacy Policy</Link>{' '}
          explains data handling and available rights. For sign-in or product help, email{' '}
          <a href={contactMailto('support')} className="break-all text-brand-strong underline dark:text-brand-strong-dark">{CONTACT_ADDRESSES.support}</a>.
        </p>
      </section>

      <div className="mt-12 border-t border-border-light pt-8 dark:border-border-dark">
        <Link href="/" className="text-brand-strong hover:text-brand-emphasis dark:text-brand-strong-dark dark:hover:text-brand-strong-dark">← Back to Home</Link>
      </div>
    </main>
  )
}
