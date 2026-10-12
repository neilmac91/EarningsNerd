import { CONTACT_ADDRESSES, contactMailto } from '@/lib/contactAddresses'
import CookieSettingsButton from '@/components/CookieSettingsButton'
import { Metadata } from 'next'
import Link from 'next/link'
import { LEGAL_DATES } from '@/lib/legalDates'

export const metadata: Metadata = {
  title: 'Privacy Policy | EarningsNerd',
  description: 'How Neil handles account data, AI questions, analytics and privacy requests at EarningsNerd.',
}

export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-4xl px-4 py-12 sm:px-6 lg:px-8">
      <div className="max-w-none">
        <h1 className="text-4xl font-semibold text-text-primary-light dark:text-text-primary-dark">
          Privacy Policy
        </h1>
        <p className="text-lg text-text-secondary-light dark:text-text-secondary-dark">
          Last updated: {LEGAL_DATES.privacy}
        </p>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">Who handles your information</h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            I&apos;m Neil, the founder of EarningsNerd, and I run the service as an individual. I&apos;m responsible
            for how EarningsNerd handles the personal information described here. For questions or requests, email me at{' '}
            <a href={contactMailto('privacy')} className="text-brand-strong underline dark:text-brand-strong-dark">
              {CONTACT_ADDRESSES.privacy}
            </a>.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">Information collected</h2>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li><strong>Account details:</strong> Your email address, name if provided, password hash and account preferences.</li>
            <li><strong>Waitlist details:</strong> Your email address and any name you choose to provide when requesting access.</li>
            <li><strong>Product activity:</strong> Searches, filing references, saved summaries, watchlists and usage counts.</li>
            <li><strong>Questions and conversations:</strong> The text you submit to Copilot and recent conversation context used to answer it.</li>
            <li><strong>Support and feedback:</strong> Contact details and the messages you send through forms or email.</li>
            <li>
              <strong>Payments:</strong> Stripe processes payment details. EarningsNerd keeps account, subscription
              and payment references; it does not store complete card numbers.
            </li>
            <li>
              <strong>Operational records:</strong> Requests and errors can include account identifiers, account email,
              IP addresses, browser/device details, page URLs and query strings. These records help manage access,
              measure usage, investigate failures and protect the service.
            </li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">AI questions and filing analysis</h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            EarningsNerd currently uses DeepSeek for AI summaries and analysis. Requests include selected SEC filing
            content and financial context. Copilot also sends the question you type, recent conversation text and
            relevant filing information gathered to answer it.
          </p>
          <p className="mt-4 text-text-secondary-light dark:text-text-secondary-dark">
            Questions and conversation text are forwarded without automatic removal of personal or confidential
            information. Please leave out passwords, financial account details and other sensitive information.
            Model requests do not automatically attach your account email or account ID, but anything you type
            into a question can be included. Account-linked usage records are processed separately.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">How information is used and shared</h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            I use this information to provide the service, manage accounts and subscriptions, answer support
            requests, send service messages, investigate errors and limit abuse. Optional browser analytics help
            me understand how the site is used.
          </p>
          <ul className="mt-4 list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li><strong>Google Cloud and Vercel:</strong> Backend and website hosting, including requests and operational logs.</li>
            <li><strong>DeepSeek:</strong> Filing analysis and Copilot inputs described above.</li>
            <li><strong>Stripe:</strong> Payments, billing and subscription management.</li>
            <li><strong>Google and Apple:</strong> If you choose social sign-in, the chosen provider handles authentication and supplies account identifiers, email and any name made available.</li>
            <li><strong>Cloudflare Turnstile:</strong> Where enabled, bot checks process a challenge token and IP address.</li>
            <li><strong>Have I Been Pwned:</strong> Where enabled, password breach checks send only the first five characters of a password hash; the comparison happens on the backend.</li>
            <li><strong>Resend and Google Workspace:</strong> Service email delivery and correspondence, including recipient addresses and message content.</li>
            <li><strong>PostHog:</strong> Optional browser analytics and session recording, plus separate server-side usage and cost events that can be linked to an account.</li>
            <li><strong>Sentry:</strong> Error and performance reporting, including selected account identifiers and diagnostic details.</li>
            <li><strong>Vercel Web Analytics:</strong> Website traffic measurements; Vercel describes this service as using no analytics cookies.</li>
          </ul>
          <p className="mt-4 text-text-secondary-light dark:text-text-secondary-dark">
            Information may also be disclosed to meet a legal requirement, investigate abuse or handle a legal
            claim. If the service is transferred to another operator, relevant account information may be part
            of that transfer, subject to applicable law.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">Cookies, analytics and your choices</h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            Essential browser storage supports sign-in and basic functionality. Optional PostHog browser analytics
            and session recording start only after an enabling choice. Browser analytics can include page URLs
            and may be linked to your account when you sign in. Browser telemetry is configured to remove URL
            query strings and fragments.
          </p>
          <p className="mt-4 text-text-secondary-light dark:text-text-secondary-dark">
            Session recording has a separate preference and also requires browser analytics to be enabled. Input masking is configured, but this does not guarantee
            that every detail displayed on a page is removed. You can review or withdraw optional browser choices
            at any time using <CookieSettingsButton /> here or in the footer.
          </p>
          <p className="mt-4 text-text-secondary-light dark:text-text-secondary-dark">
            For a new visitor without saved preferences, Do Not Track starts with optional browser analytics and
            session recording off. Saved cookie choices take precedence. These browser choices do not switch off
            server-side usage metrics, security logs, error reporting or cookieless Vercel traffic analytics.
            For questions about these records or your preferences, email{' '}
            <a href={contactMailto('privacy')} className="text-brand-strong underline dark:text-brand-strong-dark">
              {CONTACT_ADDRESSES.privacy}
            </a>.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">Processing purposes and legal grounds</h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            Where the GDPR or UK GDPR applies, the grounds for processing depend on the activity:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li><strong>Providing the service:</strong> Account management, requested AI features and payments are processed to provide the service you request.</li>
            <li><strong>Your consent:</strong> Optional PostHog browser analytics and session recording use your saved choices; you can withdraw them through Cookie settings.</li>
            <li><strong>Legitimate interests:</strong> Operational usage records, troubleshooting, security and abuse prevention support running and protecting the service, subject to applicable rights and requirements.</li>
            <li><strong>Legal obligations:</strong> Information may be retained or disclosed where applicable accounting, tax or other legal duties require it.</li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">Where information is processed</h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            The backend runs on Google Cloud in the United States. DeepSeek&apos;s{' '}
            <a href="https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html" target="_blank" rel="noopener noreferrer" className="text-brand-strong underline dark:text-brand-strong-dark">
              published privacy policy
            </a>{' '}
            describes processing and storage in China. Its general policy does not replace this notice for
            EarningsNerd&apos;s use of its API.
          </p>
          <p className="mt-4 text-text-secondary-light dark:text-text-secondary-dark">
            Service email is dispatched through Resend&apos;s Ireland region. Resend&apos;s{' '}
            <a href="https://resend.com/docs/dashboard/domains/regions" target="_blank" rel="noopener noreferrer" className="text-brand-strong underline dark:text-brand-strong-dark">
              region documentation
            </a>{' '}
            states that account data, including email metadata, logs and API records, is stored in the United States
            regardless of sending region. Other providers may process information in additional countries through
            their services and subprocessors.
          </p>
          <p className="mt-4 text-text-secondary-light dark:text-text-secondary-dark">
            Provider-specific processing locations, retention settings and international transfer arrangements
            are still being verified. Contact me at the privacy address if you need
            more information about a transfer affecting your data.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">Retention and deletion</h2>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li><strong>Accounts and saved records:</strong> Account details and associated saved records remain while the account exists, unless removed through an available deletion action or a privacy request. There is no scheduled deletion solely because an account is inactive.</li>
            <li><strong>Search history and contact submissions:</strong> Records older than 365 days become eligible for scheduled cleanup. This is not a promise that every record disappears on that exact day.</li>
            <li><strong>Waitlist entries:</strong> Entries remain in the waitlist until removed; there is no scheduled expiry. You can request removal at the privacy address.</li>
            <li><strong>Billing:</strong> Stripe customer and payment records may remain after account deletion for payment administration and applicable accounting, tax or dispute requirements; retention depends on the record and the applicable obligation.</li>
            <li><strong>Operational records:</strong> Usage and audit records can remain after account deletion. Audit entries can retain an account identifier and email so account and security events remain traceable.</li>
            <li><strong>Provider logs and backups:</strong> These have separate provider and account settings. Their retention periods are still being verified.</li>
          </ul>
          <p className="mt-4 text-text-secondary-light dark:text-text-secondary-dark">
            Account deletion removes the account and associated records handled by that process from the active
            application database and clears sign-in cookies. It does not instantly erase every billing record,
            audit entry, provider log or backup copy. The application sends a deletion event to PostHog where
            configured, but this does not confirm erasure of its historical records. Clearing Sentry account
            context affects future events and does not erase historical events. Please contact me if you need help checking a deletion request.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">Your rights and requests</h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            Depending on applicable law, you may have rights to access, correct, delete or receive a portable
            copy of personal information, restrict or object to processing, withdraw consent and complain to a
            data protection authority. These rights can have exceptions, including required record retention.
          </p>
          <ul className="mt-4 list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              Use{' '}
              <Link href="/dashboard/settings" className="text-brand-strong underline dark:text-brand-strong-dark">Account Settings</Link>{' '}
              for available account updates, deletion and a JSON export. The export covers the records provided
              by that feature; it is not a complete export of every provider&apos;s logs or backups.
            </li>
            <li>
              For another access, correction, deletion, objection or restriction request, email{' '}
              <a href={contactMailto('privacy')} className="text-brand-strong underline dark:text-brand-strong-dark">{CONTACT_ADDRESSES.privacy}</a>.
              I may ask for proportionate verification before releasing or deleting account information.
            </li>
            <li>You can withdraw optional PostHog browser analytics and recording choices through Cookie settings. Contact me about other processing or unwanted correspondence.</li>
            <li>
              You can raise a concern with your local data protection authority. The{' '}
              <a href="https://edpb.europa.eu/about-edpb/board/members_en" target="_blank" rel="noopener noreferrer" className="text-brand-strong underline dark:text-brand-strong-dark">EDPB directory</a>{' '}
              lists EU authorities.
            </li>
          </ul>
          <p className="mt-4 text-text-secondary-light dark:text-text-secondary-dark">
            I aim to reply within 2 business days. Formal data-rights requests follow the deadlines in applicable
            law, including one month where the GDPR requires it; I will explain any permitted extension.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">Security and external services</h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            The website and API use HTTPS, and password sign-in stores password hashes. My{' '}
            <Link href="/security" className="text-brand-strong underline dark:text-brand-strong-dark">security page</Link>{' '}
            describes the current application controls. No internet service can guarantee absolute security.
            External providers have their own policies; links to their services do not make those policies
            EarningsNerd&apos;s policy.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">Children and policy changes</h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            EarningsNerd is intended for people who have reached the age of majority in their jurisdiction,
            as described in the{' '}
            <Link href="/terms" className="text-brand-strong underline dark:text-brand-strong-dark">Terms</Link>.
            If you believe a child has supplied personal information, contact me so I can review and address it.
          </p>
          <p className="mt-4 text-text-secondary-light dark:text-text-secondary-dark">
            I will post policy changes here and update the content date. Where applicable law requires another
            notice, I will provide it.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">Contact me</h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            For privacy questions or data requests, email{' '}
            <a href={contactMailto('privacy')} className="text-brand-strong underline dark:text-brand-strong-dark">{CONTACT_ADDRESSES.privacy}</a>.
            For product help, email{' '}
            <a href={contactMailto('support')} className="text-brand-strong underline dark:text-brand-strong-dark">{CONTACT_ADDRESSES.support}</a>.
          </p>
        </section>

        <div className="mt-12 border-t border-border-light pt-8 dark:border-border-dark">
          <Link href="/" className="text-brand-strong hover:text-brand-emphasis dark:text-brand-strong-dark dark:hover:text-brand-strong-dark">
            ← Back to Home
          </Link>
        </div>
      </div>
    </main>
  )
}
