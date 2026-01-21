import { Metadata } from 'next'
import ContactForm from '@/components/ContactForm'

export const metadata: Metadata = {
  title: 'Contact Us | EarningsNerd',
  description: 'Get in touch with the EarningsNerd team. We&apos;re here to help with questions, feedback, or support.',
}

export default function ContactPage() {
  return (
    <main className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-3xl">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-4xl font-bold tracking-tight text-text-primary-light dark:text-text-primary-dark sm:text-5xl">
            Contact Us
          </h1>
          <p className="mt-4 text-lg text-text-secondary-light dark:text-text-secondary-dark">
            Have a question or feedback? We&apos;d love to hear from you.
          </p>
        </div>

        {/* Contact Form */}
        <div className="mt-12">
          <ContactForm />
        </div>

        {/* Contact Information */}
        <div className="mt-12 rounded-lg border border-border-light bg-background-light p-6 dark:border-border-dark dark:bg-slate-900/50">
          <h2 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">
            What to Expect
          </h2>
          <div className="mt-4 space-y-3 text-text-secondary-light dark:text-text-secondary-dark">
            <div>
              <span className="font-medium">Response Time:</span> We typically respond within 1-2 business days
            </div>
            <div>
              <span className="font-medium">Support Hours:</span> Monday - Friday, 9:00 AM - 5:00 PM EST
            </div>
            <div>
              <span className="font-medium">Confirmation:</span> You&apos;ll receive an automated confirmation email immediately after submission
            </div>
          </div>
        </div>

        {/* FAQ Hint */}
        <div className="mt-8 text-center">
          <p className="text-sm text-text-tertiary-light dark:text-text-tertiary-dark">
            Looking for quick answers? Check out our{' '}
            <a
              href="/privacy"
              className="font-medium text-mint-600 hover:text-mint-700 dark:text-mint-400 dark:hover:text-mint-300"
            >
              Privacy Policy
            </a>{' '}
            or{' '}
            <a
              href="/security"
              className="font-medium text-mint-600 hover:text-mint-700 dark:text-mint-400 dark:hover:text-mint-300"
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
