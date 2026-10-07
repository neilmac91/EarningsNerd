import { CONTACT_ADDRESSES, contactMailto } from '@/lib/contactAddresses'
import { Metadata } from 'next'
import ContactForm from '@/features/contact/components/ContactForm'
import { Card } from '@/components/ui/Card'

export const metadata: Metadata = {
  title: 'Contact | EarningsNerd',
  description: "Contact Neil, EarningsNerd's founder, for support, billing, privacy, or security questions.",
  alternates: { canonical: '/contact' },
}

export default function ContactPage() {
  return (
    <main className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-3xl">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-4xl font-semibold text-text-primary-light dark:text-text-primary-dark sm:text-5xl">
            Contact
          </h1>
          <p className="mt-4 text-lg text-text-secondary-light dark:text-text-secondary-dark">
            I&apos;m Neil, EarningsNerd&apos;s founder. Send me a question or feedback.
          </p>
        </div>

        <Card as="section" className="mt-8 p-6">
          <h2 className="text-lg font-semibold">Email me directly</h2>
          <dl className="mt-4 space-y-4 text-sm text-text-secondary-light dark:text-text-secondary-dark">
            {([
              ['support', 'Product help, feedback and general questions'],
              ['billing', 'Subscriptions, payments and invoices'],
              ['privacy', 'Personal data and privacy requests'],
              ['security', 'Private vulnerability and security reports'],
            ] as const).map(([role, purpose]) => (
              <div key={role}>
                <dt>
                  <a href={contactMailto(role)} className="break-all font-medium text-brand-strong underline underline-offset-4 dark:text-brand-strong-dark">
                    {CONTACT_ADDRESSES[role]}
                  </a>
                </dt>
                <dd className="mt-1">{purpose}</dd>
              </div>
            ))}
          </dl>
        </Card>

        {/* Contact Form */}
        <div className="mt-12">
          <ContactForm />
        </div>

        {/* Contact Information */}
        <div className="mt-12 rounded-lg border border-border-light bg-panel-light p-6 shadow-e2 dark:border-white/10 dark:bg-panel-dark dark:shadow-none">
          <h2 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">
            What to Expect
          </h2>
          <div className="mt-4 space-y-3 text-text-secondary-light dark:text-text-secondary-dark">
            <div>
              <span className="font-medium">Response time:</span> I aim to reply within 2 business days.
            </div>
            <div>
              I read every message myself. EarningsNerd is a solo-founder product.
            </div>
            <div>
              You can use the form or email me directly at the addresses above.
            </div>
          </div>
        </div>

        {/* FAQ Hint */}
        <div className="mt-8 text-center">
          <p className="text-sm text-text-tertiary-light dark:text-text-secondary-dark">
            Looking for quick answers? Check out our{' '}
            <a
              href="/privacy"
              className="font-medium text-brand-strong underline-offset-4 hover:underline dark:text-brand-strong-dark"
            >
              Privacy Policy
            </a>{' '}
            or{' '}
            <a
              href="/security"
              className="font-medium text-brand-strong underline-offset-4 hover:underline dark:text-brand-strong-dark"
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
