import { Metadata } from 'next'
import ContactForm from '@/features/contact/components/ContactForm'

export const metadata: Metadata = {
  title: 'Contact | EarningsNerd',
  description: 'Questions, feedback or support for EarningsNerd.',
  alternates: { canonical: '/contact' },
}

export default function ContactPage() {
  return (
    <main className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-3xl">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-4xl font-semibold text-text-primary-light dark:text-text-primary-dark sm:text-5xl">
            Contact us
          </h1>
          <p className="mt-4 text-lg text-text-secondary-light dark:text-text-secondary-dark">
            Questions, feedback or a problem with your account: write to us here.
          </p>
        </div>

        {/* Contact Form */}
        <div className="mt-12">
          <ContactForm />
        </div>

        {/* Contact Information */}
        <div className="mt-12 rounded-lg border border-border-light bg-panel-light p-6 shadow-e2 dark:border-white/10 dark:bg-panel-dark dark:shadow-none">
          <h2 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">
            What to expect
          </h2>
          <div className="mt-4 space-y-3 text-text-secondary-light dark:text-text-secondary-dark">
            <div>
              <span className="font-medium">Response time:</span> typically within 1–2 business days
            </div>
            <div>
              <span className="font-medium">Support hours:</span> Monday–Friday, 9:00 AM–5:00 PM ET
            </div>
          </div>
        </div>

        {/* FAQ Hint */}
        <div className="mt-8 text-center">
          <p className="text-sm text-text-tertiary-light dark:text-text-secondary-dark">
            Looking for quick answers? Check out our{' '}
            <a
              href="/privacy"
              className="rounded-sm font-medium text-brand-strong underline underline-offset-4 focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark"
            >
              Privacy Policy
            </a>{' '}
            or{' '}
            <a
              href="/security"
              className="rounded-sm font-medium text-brand-strong underline underline-offset-4 focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark"
            >
              Security
            </a>{' '}
            page.
          </p>
        </div>
      </div>
    </main>
  )
}
