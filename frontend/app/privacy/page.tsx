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
            files stored on your device that help us improve our services and your experience. You can configure your
            browser to refuse cookies, but this may limit your ability to use certain features of our services.
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
            Data Retention
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            We retain your information for as long as necessary to provide our services, comply with legal obligations,
            resolve disputes, and enforce our agreements. When we no longer need your information, we will securely
            delete or anonymize it.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Your Rights and Choices
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            You have certain rights regarding your personal information:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              <strong>Access and Update:</strong> You can access and update your account information at any time
              through your account settings.
            </li>
            <li>
              <strong>Delete:</strong> You can request deletion of your account and personal information by contacting
              us at{' '}
              <a href="mailto:hello@earningsnerd.com" className="text-mint-600 hover:text-mint-700 dark:text-mint-400 dark:hover:text-mint-300">
                hello@earningsnerd.com
              </a>
              .
            </li>
            <li>
              <strong>Opt-Out:</strong> You can opt out of receiving promotional emails by following the unsubscribe
              instructions in those emails.
            </li>
            <li>
              <strong>Data Portability:</strong> You can request a copy of your personal information in a structured,
              commonly used format.
            </li>
          </ul>
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
            Our services are not directed to individuals under the age of 18. We do not knowingly collect personal
            information from children under 18. If you become aware that a child has provided us with personal
            information, please contact us, and we will take steps to delete such information.
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
            If you have any questions about this Privacy Policy or our privacy practices, please contact us at:
          </p>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            Email:{' '}
            <a href="mailto:hello@earningsnerd.com" className="text-mint-600 hover:text-mint-700 dark:text-mint-400 dark:hover:text-mint-300">
              hello@earningsnerd.com
            </a>
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
