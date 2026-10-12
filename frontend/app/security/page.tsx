import { CONTACT_ADDRESSES, contactMailto } from '@/lib/contactAddresses'
import { Metadata } from 'next'
import Link from 'next/link'
import { LEGAL_DATES } from '@/lib/legalDates'

export const metadata: Metadata = {
  title: 'Security | EarningsNerd',
  description: 'Security practices and data protection at EarningsNerd.',
}

export default function SecurityPage() {
  return (
    <main className="mx-auto max-w-4xl px-4 py-12 sm:px-6 lg:px-8">
      <div className="max-w-none">
        <h1 className="text-4xl font-semibold text-text-primary-light dark:text-text-primary-dark">
          Security
        </h1>
        <p className="text-lg text-text-secondary-light dark:text-text-secondary-dark">
          {/* Content-change date — lives in lib/legalDates.ts with the full rationale. */}
          Last updated: {LEGAL_DATES.security}
        </p>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            A Note from Neil
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            I run EarningsNerd as an individual founder. This page describes the security controls used by the
            product and how to contact me about a concern.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Data Protection
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            EarningsNerd uses the following controls for connections and accounts:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              <strong>HTTPS:</strong> Browser connections to EarningsNerd use HTTPS to encrypt traffic in transit.
            </li>
            <li>
              <strong>Passwords:</strong> Passwords created for EarningsNerd are stored as bcrypt hashes.
            </li>
            <li>
              <strong>Account Access:</strong> Account settings, account data export and account deletion require
              you to sign in. Public filing data, login, contact and security contact endpoints are available
              without an account.
            </li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Authentication and Access Control
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            Protected requests check the account session and its permissions:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              <strong>Signed Tokens:</strong> Access tokens are signed and checked when accessing protected
              account actions.
            </li>
            <li>
              <strong>Token Expiration:</strong> Access and refresh tokens expire. A session must be renewed to
              continue accessing protected actions.
            </li>
            <li>
              <strong>Permission Checks:</strong> Account, administrator and subscription checks apply to the
              actions that require them.
            </li>
            <li>
              <strong>Browser Sessions:</strong> Session cookies use HttpOnly and SameSite settings to limit
              access from scripts and cross-site requests.
            </li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Payment Security
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            Stripe processes card payments. Card details entered during checkout are handled by Stripe.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Hosting and Monitoring
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            I use managed hosting and monitoring services to operate EarningsNerd:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              <strong>Hosting:</strong> The website runs on Vercel and the backend runs on Google Cloud.
            </li>
            <li>
              <strong>Dependency Checks:</strong> Automated build checks include reports of known dependency
              vulnerabilities to support maintenance.
            </li>
            <li>
              <strong>Monitoring:</strong> Sentry provides error and performance reports. Application logs record
              selected account and security events to help investigate issues.
            </li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Application Security
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            The product uses input checks, browser headers and request limits:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              <strong>Input Validation:</strong> Account and contact forms check supported fields and formats.
            </li>
            <li>
              <strong>Browser Headers:</strong> Response headers restrict page framing and content sniffing.
            </li>
            <li>
              <strong>Request Limits:</strong> Selected actions, including sign-in, contact submissions and AI
              generation, limit request rates to reduce abuse.
            </li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Privacy and Account Data
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            Account settings provide data export and account deletion controls. Some billing, security and provider
            records can remain after account deletion. For how information is handled and how to make a privacy
            request, see the{' '}
            <Link href="/privacy" className="text-brand-strong hover:text-brand-emphasis dark:text-brand-strong-dark dark:hover:text-brand-strong-dark">
              Privacy Policy
            </Link>
            .
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Incident Response
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            I investigate reported security concerns. If an incident requires notification, I will inform affected
            users in accordance with the applicable requirements.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Best Practices for Users
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            You can help protect your account by following these security best practices:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>Use a strong, unique password for your EarningsNerd account</li>
            <li>Never share your password with anyone</li>
            <li>Log out of your account when using shared or public computers</li>
            <li>Keep your browser and operating system up to date</li>
            <li>Be cautious of phishing attempts and verify the URL before entering credentials</li>
            <li>Report suspicious activity or security concerns to me</li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Responsible Disclosure
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            If you discover a security vulnerability, please report it privately to me, Neil, EarningsNerd&apos;s founder,
            so I can investigate before it is publicly disclosed. I aim to reply within 2 business days.
          </p>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            To report a security vulnerability:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              Email me at{' '}
              <a href={contactMailto('security')} className="text-brand-strong hover:text-brand-emphasis dark:text-brand-strong-dark dark:hover:text-brand-strong-dark">
                {CONTACT_ADDRESSES.security}
              </a>
            </li>
            <li>Include the affected page or feature and steps to reproduce the vulnerability</li>
            <li>Allow me time to investigate before public disclosure</li>
            <li>Do not access or modify data that does not belong to you</li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Third-Party Services
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            These services support the product:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              <strong>Stripe:</strong> Payment processing
            </li>
            <li>
              <strong>Resend:</strong> Transactional email delivery
            </li>
            <li>
              <strong>DeepSeek:</strong> AI processing of filing material and financial context, the questions you
              type, and recent conversation history. Financial facts retrieved from filings to answer a question
              may also be included.
            </li>
            <li>
              <strong>Sentry:</strong> Error and performance reporting
            </li>
            <li>
              <strong>PostHog:</strong> Product usage analytics, including events associated with an account
            </li>
          </ul>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            Information you include in a question can be part of the AI request. Avoid entering passwords,
            sign-in codes or other sensitive personal information.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Contact Us
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            If you have a question about these practices or need to report a concern, contact me:
          </p>
          <ul className="list-none space-y-2 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              General inquiries:{' '}
              <a href={contactMailto('support')} className="text-brand-strong underline dark:text-brand-strong-dark">
                {CONTACT_ADDRESSES.support}
              </a>
            </li>
            <li>
              Security issues:{' '}
              <a href={contactMailto('security')} className="text-brand-strong hover:text-brand-emphasis dark:text-brand-strong-dark dark:hover:text-brand-strong-dark">
                {CONTACT_ADDRESSES.security}
              </a>
            </li>
          </ul>
        </section>

        <div className="mt-12 border-t border-border-light pt-8 dark:border-border-dark">
          <Link
            href="/"
            className="text-brand-strong hover:text-brand-emphasis dark:text-brand-strong-dark dark:hover:text-brand-strong-dark"
          >
            ← Back to Home
          </Link>
        </div>
      </div>
    </main>
  )
}
