import { LegalOperatorNotice } from '@/features/legal/components/LegalOperatorNotice'
import { CONTACT_ADDRESSES, contactMailto } from '@/lib/contactAddresses'
import { ACCOUNT_EVENTS_DISCLOSURE, ANALYTICS_CONSENT_CLAUSE } from '@/lib/consentCopy'
import { Metadata } from 'next'
import Link from 'next/link'
import { LEGAL_DATES } from '@/lib/legalDates'
import { legalPageMainClass } from '@/lib/legalPageLayout'

export const metadata: Metadata = {
  title: 'Privacy policy | EarningsNerd',
  description: 'How EarningsNerd handles personal information, AI inputs, cookies and privacy requests.',
}

export default function PrivacyPage() {
  return (
    <div className="[container-type:inline-size]">
      <main className={legalPageMainClass}>
      <div className="max-w-none">
        <h1 className="text-4xl font-semibold text-text-primary-light dark:text-text-primary-dark">Privacy policy</h1>
        <p className="text-lg text-text-secondary-light dark:text-text-secondary-dark">Last updated: {LEGAL_DATES.privacy}</p>
        <LegalOperatorNotice />
        <p className="mt-8 text-text-secondary-light dark:text-text-secondary-dark">
          This policy explains how personal information is handled through the EarningsNerd website and service.
          For privacy questions, requests or complaints, contact{' '}
          <a href={contactMailto('privacy')} className="text-brand-strong underline dark:text-brand-strong-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">{CONTACT_ADDRESSES.privacy}</a>.
        </p>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">Information collected</h2>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li><strong>Accounts and access requests:</strong> Email address, any name supplied, password hash, preferences and waitlist details.</li>
            <li><strong>Product use:</strong> Searches, saved summaries, watchlists, usage records, AI questions and conversation text.</li>
            <li><strong>Correspondence:</strong> Contact details and messages sent through forms or email.</li>
            <li><strong>Billing:</strong> Subscription and payment references. Stripe handles payment details; EarningsNerd does not store complete card numbers.</li>
            <li><strong>Technical information:</strong> Browser, device, IP address and request information, account identifiers, diagnostic and security records. Some records include account email.</li>
          </ul>
          <p className="mt-4 text-text-secondary-light dark:text-text-secondary-dark">
            Information comes from you, use of the service, your chosen Google or Apple login provider, and
            payment providers. Public SEC filings and related financial sources can include information about
            people named in those records. Account email and login details, relevant billing details and
            required contact-form details are needed to complete those requests. Optional fields can be left blank.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">Purposes and legal grounds</h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            Information is used to deliver requested features, manage accounts and payments, answer messages,
            send service communications, measure usage, investigate problems and protect against abuse.
            Where EU or UK data protection law applies, the grounds are:
          </p>
          <ul className="mt-4 list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li><strong>Contract:</strong> Providing requested accounts, features and subscriptions.</li>
            <li><strong>Consent:</strong> Optional browser analytics and session recording; consent can be withdrawn in Cookie settings.</li>
            <li><strong>Legitimate interests:</strong> Operating and improving the service, responding to enquiries, managing usage, troubleshooting, security and preventing abuse, subject to your rights.</li>
            <li><strong>Legal obligations:</strong> Applicable accounting, tax, lawful disclosure and other recordkeeping duties.</li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">AI processing</h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            DeepSeek processes selected filing and financial information for AI analysis. Filing questions and recent
            conversation text are also sent to DeepSeek. Personal information in that text is not
            automatically removed. Avoid submitting passwords, financial account details or other sensitive
            information. Account-linked usage records are processed separately.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">Service providers and disclosures</h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">Information is shared as needed with providers supporting these functions:</p>
          <ul className="mt-4 list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li><strong>Hosting and content delivery:</strong> Google Cloud, Vercel and, where enabled, Logo.dev for company images.</li>
            <li><strong>AI and payments:</strong> DeepSeek for the inputs described above; Stripe for billing and subscriptions.</li>
            <li><strong>Login and security:</strong> Google or Apple for chosen social login; Cloudflare Turnstile for bot checks and Have I Been Pwned for partial password-hash breach checks, where enabled.</li>
            <li><strong>Email:</strong> Resend and Google Workspace for recipient details, service messages and correspondence.</li>
            <li><strong>Analytics and diagnostics:</strong> PostHog for optional browser analytics/recording and separate account-linked operational usage; Sentry for errors and performance; Vercel Web Analytics for cookieless traffic measurement.</li>
          </ul>
          <p className="mt-4 text-text-secondary-light dark:text-text-secondary-dark">
            Information may also be disclosed to comply with law, investigate abuse or protect legal rights.
            A transfer of the service may include relevant account information, subject to applicable law.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">International processing</h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            Information is processed outside some users&apos; countries. Backend hosting is in the United States;
            DeepSeek describes processing and storage in China. Resend dispatches service emails from Ireland
            and stores account data, including email metadata and logs, in the United States. Other providers
            and their subprocessors may process information in additional countries.
          </p>
          <p className="mt-4 text-text-secondary-light dark:text-text-secondary-dark">
            Privacy laws and protections differ between countries, and information may be accessible to
            authorities under local law. Contact the privacy address to request information about processing
            locations and any safeguards applicable to a transfer of your information.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">Cookies and choices</h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            Essential browser storage supports login and site functionality. Optional PostHog and Vercel
            browser analytics require an enabling choice. PostHog recording has a separate preference
            and also requires analytics. These activities can be linked to your account; recording can include
            displayed page content despite input masking. Review or withdraw choices using Cookie settings in the footer.
          </p>
          <p className="mt-4 text-text-secondary-light dark:text-text-secondary-dark">
            Analytics and session recording in your browser stay off until you allow them, and you can change your choice at any time in Cookie settings. We don&apos;t change this based on your browser&apos;s Do Not Track setting.
          </p>
          <ul className="mt-4 list-disc pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li><strong>Analytics Cookies:</strong>{' '}{ANALYTICS_CONSENT_CLAUSE}</li>
          </ul>
          <p className="mt-4 text-text-secondary-light dark:text-text-secondary-dark">{ACCOUNT_EVENTS_DISCLOSURE}</p>
          <p className="mt-4 text-text-secondary-light dark:text-text-secondary-dark">
            These controls do not disable operational usage records, security logs or error reporting.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">Retention and deletion</h2>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li><strong>Account and saved records:</strong> Kept while your account exists, unless removed through available controls or a privacy request. Inactivity alone does not trigger deletion.</li>
            <li><strong>Search history and contact submissions:</strong> Records older than 365 days are eligible for scheduled cleanup.</li>
            <li><strong>Waitlist:</strong> Entries remain until removed; request removal at the privacy address.</li>
            <li><strong>Billing, usage and security records:</strong> Some remain after account deletion. Retention depends on the record&apos;s purpose, payment or dispute administration, security investigations and applicable legal obligations. Audit records can retain account identifiers and email.</li>
            <li><strong>Provider records and backups:</strong> Separate provider retention and backup settings apply. Contact the privacy address for information about a particular record or deletion request.</li>
          </ul>
          <p className="mt-4 text-text-secondary-light dark:text-text-secondary-dark">
            Account deletion removes the account and associated records covered by that process from the active
            application database. It does not instantly erase every billing, audit or provider record or backup.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">Your rights and complaints</h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            Email{' '}
            <a href={contactMailto('privacy')} className="text-brand-strong underline dark:text-brand-strong-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">{CONTACT_ADDRESSES.privacy}</a>{' '}
            to request access or correction, withdraw consent, or raise a privacy complaint. Depending on
            applicable law, you may also request deletion, a portable copy or restriction, or object to processing.
            Rights have conditions and exceptions.
          </p>
          <p className="mt-4 text-text-secondary-light dark:text-text-secondary-dark">
            Where EU or UK law applies, you can object to processing based on legitimate interests.
          </p>
          <p className="mt-4 text-text-secondary-light dark:text-text-secondary-dark">
            Available account updates, deletion and a JSON export are in{' '}
            <Link href="/dashboard/settings" className="text-brand-strong underline dark:text-brand-strong-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">Account Settings</Link>.
            The export covers records available through that feature, rather than every provider&apos;s records.
            Requests may require proportionate identity verification. Requests and complaints are reviewed,
            investigated as appropriate, and answered within applicable legal deadlines, with an explanation
            of any permitted extension or refusal and available appeal route.
          </p>
          <ul className="mt-4 list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li><strong>EU/EEA and UK:</strong> Applicable rights include access, correction, deletion, portability, restriction, objection and consent withdrawal. You can complain to your local data protection authority.</li>
            <li><strong>Switzerland:</strong> Where Swiss law applies, you can request information or correction and may seek deletion, restriction or object to processing. Portability applies to eligible data processed automatically based on consent or contract.</li>
            <li><strong>United States:</strong> Where state privacy law applies, rights may include access, correction, deletion, portability, appeal, authorised-agent requests and opting out of sale or sharing, targeted advertising or certain profiling. Contact the privacy address to exercise an applicable right; exercising it will not result in unlawful discrimination.</li>
            <li><strong>Canada and Mexico:</strong> Applicable rights can include access, correction, consent withdrawal and complaints; Mexican law may also provide cancellation and objection rights.</li>
            <li><strong>Singapore:</strong> Applicable access rights include information about use and disclosure during the preceding year, alongside correction and consent withdrawal.</li>
            <li><strong>Australia, New Zealand and South Africa:</strong> Applicable rights include access, correction and complaints; South African law may also provide objection and deletion rights.</li>
          </ul>
          <p className="mt-4 text-text-secondary-light dark:text-text-secondary-dark">
            You may contact the relevant regulator directly, including an{' '}
            <a href="https://www.edpb.europa.eu/about-edpb/our-members_en" className="text-brand-strong underline dark:text-brand-strong-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">EU authority</a>,{' '}
            <a href="https://ico.org.uk/make-a-complaint/" className="text-brand-strong underline dark:text-brand-strong-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">UK ICO</a>,{' '}
            <a href="https://www.edoeb.admin.ch/en" className="text-brand-strong underline dark:text-brand-strong-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">Swiss FDPIC</a>,{' '}
            <a href="https://www.priv.gc.ca/en/report-a-concern/" className="text-brand-strong underline dark:text-brand-strong-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">Canadian privacy commissioner</a>,{' '}
            <a href="https://www.pdpc.gov.sg/" className="text-brand-strong underline dark:text-brand-strong-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">Singapore PDPC</a>,{' '}
            <a href="https://www.oaic.gov.au/privacy/privacy-complaints" className="text-brand-strong underline dark:text-brand-strong-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">Australian OAIC</a>,{' '}
            <a href="https://www.privacy.org.nz/your-rights/making-a-complaint-to-the-privacy-commissioner/" className="text-brand-strong underline dark:text-brand-strong-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">New Zealand privacy commissioner</a>{' '}
            or the{' '}
            <a href="https://inforegulator.org.za/complaints/" className="text-brand-strong underline dark:text-brand-strong-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">South African Information Regulator</a>.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">Security, eligibility and changes</h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            Connections use HTTPS and passwords are stored as hashes. See{' '}
            <Link href="/security" className="text-brand-strong underline dark:text-brand-strong-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">Security</Link>{' '}
            to report a concern. No internet service can guarantee absolute security.
          </p>
          <p className="mt-4 text-text-secondary-light dark:text-text-secondary-dark">
            Accounts are available only to people who are at least 18 and legally adults where they live, as required by the{' '}
            <Link href="/terms" className="text-brand-strong underline dark:text-brand-strong-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">Terms</Link>.
            Contact the privacy address if a child has supplied personal information. Policy changes are posted
            here with an updated date; additional notice will be provided where required by law.
          </p>
        </section>

        <div className="mt-12 border-t border-border-light pt-8 dark:border-border-dark">
          <Link href="/" className="text-brand-strong hover:text-brand-emphasis dark:text-brand-strong-dark dark:hover:text-brand-strong-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">← Back to Home</Link>
        </div>
      </div>
      </main>
    </div>
  )
}
