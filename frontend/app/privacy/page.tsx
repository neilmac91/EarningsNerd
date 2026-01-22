import { Metadata } from 'next'
import Link from 'next/link'

export const metadata: Metadata = {
  title: 'Privacy Policy | EarningsNerd',
  description: 'Privacy policy for EarningsNerd - Learn how we collect, use, and protect your data.',
}

export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-4xl px-4 py-12 sm:px-6 lg:px-8">
      <div className="prose prose-slate dark:prose-invert max-w-none">
        <h1 className="text-4xl font-bold text-text-primary-light dark:text-text-primary-dark">
          Privacy Policy
        </h1>
        <p className="text-lg text-text-secondary-light dark:text-text-secondary-dark">
          Last updated: {new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
        </p>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Introduction
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            EarningsNerd (&quot;we,&quot; &quot;our,&quot; or &quot;us&quot;) is committed to protecting your privacy. This Privacy Policy explains
            how we collect, use, disclose, and safeguard your information when you visit our website and use our
            services. Please read this privacy policy carefully.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Information We Collect
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            We collect information that you provide directly to us, including:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              <strong>Account Information:</strong> When you register for an account, we collect your name, email
              address, and password.
            </li>
            <li>
              <strong>Waitlist Information:</strong> When you join our waitlist, we collect your email address and
              optionally your full name.
            </li>
            <li>
              <strong>Payment Information:</strong> When you subscribe to our services, payment information is
              processed securely through our payment processor (Stripe). We do not store complete credit card numbers.
            </li>
            <li>
              <strong>Usage Data:</strong> We automatically collect information about your interactions with our
              services, including the companies you search for, filings you view, and features you use.
            </li>
            <li>
              <strong>Device and Browser Information:</strong> We collect information about the device and browser you
              use to access our services, including IP address, browser type, operating system, and referring URLs.
            </li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            How We Use Your Information
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            We use the information we collect to:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>Provide, maintain, and improve our services</li>
            <li>Create and manage your account</li>
            <li>Process your transactions and send related information</li>
            <li>Send you technical notices, updates, security alerts, and administrative messages</li>
            <li>Respond to your comments, questions, and customer service requests</li>
            <li>Communicate with you about products, services, and events</li>
            <li>Monitor and analyze trends, usage, and activities in connection with our services</li>
            <li>Detect, investigate, and prevent fraudulent transactions and other illegal activities</li>
            <li>Personalize and improve your experience</li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Analytics and Tracking
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            We use analytics services to help us understand how our services are used:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              <strong>PostHog:</strong> We use PostHog for product analytics and user behavior tracking. This helps us
              understand how users interact with our platform and improve the user experience.
            </li>
            <li>
              <strong>Sentry:</strong> We use Sentry for error tracking and performance monitoring to identify and fix
              technical issues quickly.
            </li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Cookies and Similar Technologies
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            We use cookies and similar tracking technologies to collect and store information. Cookies are small data
            files stored on your device that help us improve our services and your experience.
          </p>
          <p className="mt-4 text-text-secondary-light dark:text-text-secondary-dark">
            <strong>Cookie Categories:</strong>
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              <strong>Essential Cookies:</strong> Required for the website to function (authentication, security, session management). These cannot be disabled.
            </li>
            <li>
              <strong>Analytics Cookies:</strong> Help us understand how visitors use our site (PostHog). You can opt-in or opt-out via our cookie consent banner.
            </li>
            <li>
              <strong>Session Recording:</strong> Records your interactions to help identify bugs (PostHog). This is opt-in only and masks sensitive information like passwords.
            </li>
          </ul>
          <p className="mt-4 text-text-secondary-light dark:text-text-secondary-dark">
            You can manage your cookie preferences at any time through our cookie consent banner (shown on first visit) or through your browser settings. Note that disabling cookies may limit certain features. We respect the &quot;Do Not Track&quot; browser setting and will not track users who have enabled it.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Information Sharing and Disclosure
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            We may share your information in the following circumstances:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              <strong>Service Providers:</strong> We share information with third-party service providers who perform
              services on our behalf, such as payment processing (Stripe), email delivery (Resend), analytics
              (PostHog), and error tracking (Sentry).
            </li>
            <li>
              <strong>Legal Requirements:</strong> We may disclose your information if required to do so by law or in
              response to valid requests by public authorities.
            </li>
            <li>
              <strong>Business Transfers:</strong> If we are involved in a merger, acquisition, or sale of assets, your
              information may be transferred as part of that transaction.
            </li>
            <li>
              <strong>With Your Consent:</strong> We may share your information with third parties when you give us
              consent to do so.
            </li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Data Security
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            We implement appropriate technical and organizational security measures to protect your information against
            unauthorized access, alteration, disclosure, or destruction. However, no method of transmission over the
            internet or electronic storage is 100% secure, and we cannot guarantee absolute security.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Legal Basis for Processing (GDPR)
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            If you are located in the European Economic Area (EEA), UK, or Switzerland, we process your personal data under the following legal bases:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              <strong>Contract:</strong> Processing is necessary to perform our contract with you (account creation, service delivery, payment processing).
            </li>
            <li>
              <strong>Consent:</strong> You have given explicit consent for analytics tracking, marketing communications, and session recording (opt-in).
            </li>
            <li>
              <strong>Legitimate Interest:</strong> Processing is necessary for fraud prevention, security, and improving our services.
            </li>
            <li>
              <strong>Legal Obligation:</strong> Processing is required to comply with legal obligations (tax records, payment history).
            </li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Data Retention Periods
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            We retain different types of information for specific periods:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              <strong>Active Accounts:</strong> Your account data (email, name, password) is retained until you delete your account or after 2 years of inactivity.
            </li>
            <li>
              <strong>Search History:</strong> Retained for 1 year from the search date, then automatically deleted.
            </li>
            <li>
              <strong>Saved Summaries & Watchlist:</strong> Retained until you manually delete them or delete your account.
            </li>
            <li>
              <strong>Contact Form Submissions:</strong> Retained for 1 year from submission date.
            </li>
            <li>
              <strong>Waitlist Signups (unconverted):</strong> Retained for 1 year from signup date.
            </li>
            <li>
              <strong>Payment & Billing Data:</strong> Retained for 7 years from transaction date (required by tax law).
            </li>
            <li>
              <strong>Analytics Data (PostHog):</strong> Retained for 90 days, then automatically deleted.
            </li>
            <li>
              <strong>Error Logs (Sentry):</strong> Retained for 90 days, then automatically deleted.
            </li>
            <li>
              <strong>Inactive Accounts:</strong> If you don&apos;t log in for 24 months, we&apos;ll send warning emails at 18, 22, and 23 months. Your account will be automatically deleted at 24 months unless you log in.
            </li>
          </ul>
          <p className="mt-4 text-text-secondary-light dark:text-text-secondary-dark">
            When data is deleted, it is permanently removed from our active systems. Data may persist in encrypted backups for up to 12 months for disaster recovery purposes but is inaccessible for operational use.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Your Rights and Choices
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            You have the following rights regarding your personal information:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              <strong>Right to Access:</strong> You can access and view your account information at any time through your{' '}
              <Link href="/dashboard" className="text-mint-600 hover:text-mint-700 dark:text-mint-400 dark:hover:text-mint-300">
                account dashboard
              </Link>
              .
            </li>
            <li>
              <strong>Right to Rectification:</strong> You can update your account information (email, name, password) through your account settings.
            </li>
            <li>
              <strong>Right to Erasure (GDPR Article 17):</strong> You can delete your account and all associated data instantly through your{' '}
              <Link href="/dashboard/settings" className="text-mint-600 hover:text-mint-700 dark:text-mint-400 dark:hover:text-mint-300">
                account settings page
              </Link>
              . This will permanently delete your profile, search history, saved summaries, watchlist, and usage data. Payment records will be retained for 7 years for tax compliance.
            </li>
            <li>
              <strong>Right to Data Portability (GDPR Article 20):</strong> You can download a complete copy of your data in JSON format from your{' '}
              <Link href="/dashboard/settings" className="text-mint-600 hover:text-mint-700 dark:text-mint-400 dark:hover:text-mint-300">
                account settings page
              </Link>
              . This includes your profile, search history, saved summaries, watchlist, and usage statistics.
            </li>
            <li>
              <strong>Right to Object:</strong> You can object to processing of your data for direct marketing purposes by unsubscribing from emails or by contacting us.
            </li>
            <li>
              <strong>Right to Restrict Processing:</strong> You can request that we limit how we use your data by contacting us at{' '}
              <a href="mailto:privacy@earningsnerd.com" className="text-mint-600 hover:text-mint-700 dark:text-mint-400 dark:hover:text-mint-300">
                privacy@earningsnerd.com
              </a>
              .
            </li>
            <li>
              <strong>Right to Withdraw Consent:</strong> You can withdraw consent for analytics and session recording at any time through our cookie consent banner or settings.
            </li>
            <li>
              <strong>Opt-Out of Marketing:</strong> You can opt out of receiving promotional emails by following the unsubscribe link in those emails.
            </li>
          </ul>
          <p className="mt-4 text-text-secondary-light dark:text-text-secondary-dark">
            <strong>For EEA, UK, and Swiss Residents:</strong> If you believe we have not adequately addressed your privacy concerns, you have the right to lodge a complaint with your local data protection supervisory authority. A list of EU supervisory authorities can be found at{' '}
            <a href="https://edpb.europa.eu/about-edpb/board/members_en" target="_blank" rel="noopener noreferrer" className="text-mint-600 hover:text-mint-700 dark:text-mint-400 dark:hover:text-mint-300">
              EDPB Members
            </a>
            .
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Third-Party Services
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            Our services may contain links to third-party websites or services that are not owned or controlled by
            EarningsNerd. We are not responsible for the privacy practices of these third parties. We encourage you to
            review the privacy policies of any third-party services you visit.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Children&apos;s Privacy
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            Our services are not directed to individuals under the age of 13 (or 16 in the EEA). We do not knowingly collect personal
            information from children under these ages. If you become aware that a child has provided us with personal
            information without parental consent, please contact us at{' '}
            <a href="mailto:privacy@earningsnerd.com" className="text-mint-600 hover:text-mint-700 dark:text-mint-400 dark:hover:text-mint-300">
              privacy@earningsnerd.com
            </a>
            , and we will take immediate steps to delete such information.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            International Data Transfers
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            Your information may be transferred to and processed in countries other than your own, including the United States. These countries may have data protection laws that differ from your country&apos;s laws. When we transfer data from the EEA, UK, or Switzerland to other countries, we use Standard Contractual Clauses (SCCs) approved by the European Commission or other appropriate safeguards to protect your data.
          </p>
          <p className="mt-4 text-text-secondary-light dark:text-text-secondary-dark">
            Our third-party service providers (Stripe, Resend, PostHog, Sentry) are located in the United States and have Data Processing Agreements in place that include appropriate safeguards for international data transfers.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Changes to This Privacy Policy
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            We may update this Privacy Policy from time to time. We will notify you of any changes by posting the new
            Privacy Policy on this page and updating the &quot;Last updated&quot; date. You are advised to review this Privacy
            Policy periodically for any changes.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Contact Us
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            If you have any questions about this Privacy Policy, our privacy practices, or wish to exercise your data protection rights, please contact us at:
          </p>
          <ul className="list-none space-y-2 text-text-secondary-light dark:text-text-secondary-dark mt-4">
            <li>
              <strong>Privacy Inquiries:</strong>{' '}
              <a href="mailto:privacy@earningsnerd.com" className="text-mint-600 hover:text-mint-700 dark:text-mint-400 dark:hover:text-mint-300">
                privacy@earningsnerd.com
              </a>
            </li>
            <li>
              <strong>General Support:</strong>{' '}
              <a href="mailto:hello@earningsnerd.com" className="text-mint-600 hover:text-mint-700 dark:text-mint-400 dark:hover:text-mint-300">
                hello@earningsnerd.com
              </a>
            </li>
            <li>
              <strong>Data Deletion or Export:</strong> Use your{' '}
              <Link href="/dashboard/settings" className="text-mint-600 hover:text-mint-700 dark:text-mint-400 dark:hover:text-mint-300">
                account settings
              </Link>
              {' '}for instant self-service
            </li>
          </ul>
          <p className="mt-4 text-text-secondary-light dark:text-text-secondary-dark">
            We will respond to your privacy requests within 30 days (or as required by applicable law).
          </p>
        </section>

        <div className="mt-12 border-t border-border-light pt-8 dark:border-border-dark">
          <Link
            href="/"
            className="text-mint-600 hover:text-mint-700 dark:text-mint-400 dark:hover:text-mint-300"
          >
            ← Back to Home
          </Link>
        </div>
      </div>
    </main>
  )
}
