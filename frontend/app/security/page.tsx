import { Metadata } from 'next'
import Link from 'next/link'
import { LEGAL_DATES } from '@/lib/legalDates'

export const metadata: Metadata = {
  title: 'Security | EarningsNerd',
  description: 'Security practices and data protection at EarningsNerd.',
}

// Every sentence below says what the code or its hosting does (D-046): a fact the repository cannot show, such as
// encryption at rest, is named as the provider's. tests/unit/legalTruth.spec.tsx holds the claims D-046 removed out
// and pins this page's text to LEGAL_DATES.security.
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
            Our commitment to security
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            This page lists what EarningsNerd&apos;s code, and the providers that host it, do to protect your account
            and your data.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Data protection
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            How your data is protected:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              <strong>Encryption in transit:</strong> Pages and API calls travel over HTTPS (TLS), which Vercel
              provides for the site and Google Cloud Run for the API. The API also tells browsers to reach it only
              over HTTPS for a year (HSTS).
            </li>
            <li>
              <strong>Encryption at rest:</strong> The database runs on Google Cloud SQL, which encrypts the data it
              stores by default.
            </li>
            <li>
              <strong>Passwords:</strong> Passwords are stored only as bcrypt hashes, never as the passwords
              themselves. When you set a password, we ask Have I Been Pwned whether it has appeared in a data breach,
              sending only the first five characters of its SHA-1 hash, and refuse one that has.
            </li>
            <li>
              <strong>Database access:</strong> The API reaches the database through Cloud Run&apos;s built-in Cloud
              SQL connection, which needs a Google Cloud service account granted access, and the database password
              is kept in Google Secret Manager. A scheduled job exports the database to a private Google Cloud
              Storage bucket on the first of each month.
            </li>
            <li>
              <strong>Your account&apos;s data:</strong> The API serves your profile, watchlist, alerts, saved
              summaries and billing only to your logged-in session. Search, company pages and the summaries already
              generated are open to everyone.
            </li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Authentication and access control
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            How you log in, and what each account can reach:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              <strong>Sessions:</strong> Your session is a signed token (a JWT) in an HttpOnly cookie, which the
              page&apos;s scripts cannot read, sent only over HTTPS.
            </li>
            <li>
              <strong>Token renewal:</strong> The session token expires after 30 minutes and is renewed from a refresh
              token that lasts 30 days. Each refresh token works once and is stored only as a hash; one presented a
              second time revokes all of that account&apos;s refresh tokens.
            </li>
            <li>
              <strong>Access:</strong> Administrator tools need an administrator account, and the API checks Pro
              features against your plan.
            </li>
            <li>
              <strong>Logging out:</strong> Logging out revokes that browser&apos;s refresh token. Logging out of all
              devices, from your account settings, revokes all of your refresh tokens, and so does changing or
              resetting your password; a session open elsewhere then ends within 30 minutes, when its session token
              expires.
            </li>
            <li>
              <strong>Failed logins:</strong> Ten failed logins for one email address, each within 15 minutes of the
              last, block password logins for that address for 15 minutes.
            </li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Payment security
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            Payments go through Stripe Checkout, on Stripe&apos;s own pages, so your card details never reach
            EarningsNerd&apos;s servers. We keep Stripe&apos;s references to your subscription and payments, with
            their amounts, dates and status. Stripe is certified to PCI DSS Level 1.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Infrastructure security
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            Where EarningsNerd runs, and how it is kept current:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              <strong>Hosting:</strong> The site runs on Vercel. The API and its scheduled jobs run on Google Cloud
              Run, and the database on Google Cloud SQL, in Google Cloud&apos;s us-west1 region.
            </li>
            <li>
              <strong>Updates:</strong> Dependabot checks the site&apos;s and the API&apos;s dependencies, and the
              build&apos;s own GitHub Actions, for updates every week.
            </li>
            <li>
              <strong>Monitoring:</strong> Errors from the site and the API are reported to Sentry, and can carry your
              internal account id when you are logged in. The site&apos;s reports leave out cookies, request bodies
              and URL query strings, and no session replays are recorded.
            </li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Application security
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            How the code guards against common attacks:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              <strong>Input validation:</strong> The API checks request bodies against schemas (Pydantic), and
              database queries take your input as bound parameters (SQLAlchemy), not as SQL text.
            </li>
            <li>
              <strong>Cross-site requests:</strong> The session cookies are set SameSite=Lax, so a browser does not
              send them with another site&apos;s form posts or background requests.
            </li>
            <li>
              <strong>Framing:</strong> The site sends X-Frame-Options DENY and a Content-Security-Policy of
              frame-ancestors &apos;none&apos;, so other sites cannot show its pages in a frame. The API&apos;s
              responses under /api carry a Content-Security-Policy of default-src &apos;none&apos;.
            </li>
            <li>
              <strong>Rate limits:</strong> The API caps how often logins, new accounts, password-reset and
              verification emails, summary generation, questions, filing-text searches and the contact, feedback and
              waitlist forms can be used. Each API server keeps its own count.
            </li>
            <li>
              <strong>Code checks:</strong> Automated checks scan the API&apos;s code for common security mistakes
              (Bandit), check the site&apos;s and the API&apos;s dependencies for known vulnerabilities (npm audit
              and pip-audit), and scan the repository for committed secrets (gitleaks).
            </li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Data privacy and compliance
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            What you can see and control:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>The Privacy Policy says what we collect, why, and how long we keep it</li>
            <li>You can download your data and delete your account from your account settings</li>
            <li>
              Registrations, logins, failed logins, logouts, data exports, account deletions and administrator actions
              are written to an audit log
            </li>
          </ul>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            For more information about how we handle your data, please see our{' '}
            <Link href="/privacy" className="text-brand-strong hover:text-brand-emphasis dark:text-brand-strong-dark dark:hover:text-brand-strong-dark">
              Privacy Policy
            </Link>
            .
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Incident response
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            If a security incident happens:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>A written runbook covers containing it, finding what it touched, gathering evidence and rotating keys</li>
            <li>When the law requires it, we notify the users affected and the data protection authority</li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Best practices for users
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
            <li>Report any suspicious activity or security concerns to us immediately</li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Responsible disclosure
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            If you discover a security vulnerability in our platform, we encourage responsible disclosure. Please
            report security issues to us privately so we can address them before they are publicly disclosed.
          </p>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            To report a security vulnerability:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              Email us at{' '}
              <a href="mailto:security@earningsnerd.io" className="text-brand-strong hover:text-brand-emphasis dark:text-brand-strong-dark dark:hover:text-brand-strong-dark">
                security@earningsnerd.io
              </a>
            </li>
            <li>Provide detailed information about the vulnerability, including steps to reproduce</li>
            <li>Allow us reasonable time to address the issue before public disclosure</li>
            <li>Do not access or modify data that does not belong to you</li>
          </ul>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            We appreciate the work of security researchers and will acknowledge responsible disclosures.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Third-party services
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            These providers do part of the work:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              <strong>Stripe:</strong> PCI-DSS Level 1 certified payment processing
            </li>
            <li>
              <strong>Resend:</strong> Sends account and alert emails
            </li>
            <li>
              <strong>DeepSeek:</strong> AI provider (OpenAI-compatible API) powering summaries and Ask this Filing; only public filing text and the questions you type are sent
            </li>
            <li>
              <strong>Sentry:</strong> Error reports, as Monitoring above describes
            </li>
            <li>
              <strong>PostHog:</strong> Usage statistics, only after you allow analytics, and session recordings only if you allow those too
            </li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Contact us
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            If you have questions about our security practices or need to report a security concern:
          </p>
          <ul className="list-none space-y-2 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              General inquiries:{' '}
              <Link href="/contact" className="text-brand-strong hover:text-brand-emphasis dark:text-brand-strong-dark dark:hover:text-brand-strong-dark">
                Contact form
              </Link>
            </li>
            <li>
              Security issues:{' '}
              <a href="mailto:security@earningsnerd.io" className="text-brand-strong hover:text-brand-emphasis dark:text-brand-strong-dark dark:hover:text-brand-strong-dark">
                security@earningsnerd.io
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
