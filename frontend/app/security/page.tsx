import { Metadata } from 'next'
import Link from 'next/link'

export const metadata: Metadata = {
  title: 'Security | EarningsNerd',
  description: 'Security practices and data protection at EarningsNerd.',
}

export default function SecurityPage() {
  return (
    <main className="mx-auto max-w-4xl px-4 py-12 sm:px-6 lg:px-8">
      <div className="prose prose-slate dark:prose-invert max-w-none">
        <h1 className="text-4xl font-bold text-text-primary-light dark:text-text-primary-dark">
          Security
        </h1>
        <p className="text-lg text-text-secondary-light dark:text-text-secondary-dark">
          Last updated: {new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
        </p>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Our Commitment to Security
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            At EarningsNerd, we take the security of your data seriously. We implement industry-standard security
            measures to protect your personal information and ensure the integrity of our platform. This page outlines
            our security practices and how we safeguard your data.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Data Protection
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            We employ multiple layers of security to protect your data:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              <strong>Encryption in Transit:</strong> All data transmitted between your browser and our servers is
              encrypted using TLS (Transport Layer Security) protocols.
            </li>
            <li>
              <strong>Encryption at Rest:</strong> Sensitive data stored in our databases is encrypted to protect
              against unauthorized access.
            </li>
            <li>
              <strong>Password Security:</strong> User passwords are hashed using industry-standard cryptographic
              algorithms. We never store passwords in plain text.
            </li>
            <li>
              <strong>Database Security:</strong> Our PostgreSQL databases are configured with strict access controls
              and are regularly backed up to prevent data loss.
            </li>
            <li>
              <strong>API Security:</strong> All API endpoints are protected with authentication and authorization
              mechanisms to ensure only authorized users can access data.
            </li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Authentication and Access Control
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            We implement robust authentication and access control measures:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              <strong>JWT (JSON Web Tokens):</strong> We use JWT-based authentication to securely manage user sessions.
            </li>
            <li>
              <strong>Token Expiration:</strong> Authentication tokens have limited lifespans and must be renewed
              periodically to maintain access.
            </li>
            <li>
              <strong>Role-Based Access:</strong> User permissions are managed through role-based access control (RBAC)
              to ensure users only have access to appropriate resources.
            </li>
            <li>
              <strong>Session Management:</strong> We implement secure session management practices to prevent session
              hijacking and fixation attacks.
            </li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Payment Security
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            We use Stripe, a PCI-DSS compliant payment processor, to handle all payment transactions. We do not store
            complete credit card numbers on our servers. All payment information is processed securely through Stripe&apos;s
            infrastructure, which maintains the highest level of payment security certification.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Infrastructure Security
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            Our infrastructure is designed with security in mind:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              <strong>Hosting:</strong> Our application is hosted on secure, enterprise-grade cloud infrastructure with
              99.9% uptime guarantees.
            </li>
            <li>
              <strong>Network Security:</strong> We implement firewalls, intrusion detection systems, and other network
              security measures to protect against unauthorized access.
            </li>
            <li>
              <strong>Regular Updates:</strong> We keep our systems and dependencies up to date with the latest
              security patches.
            </li>
            <li>
              <strong>Monitoring:</strong> We use Sentry for real-time error tracking and monitoring to quickly
              identify and address potential security issues.
            </li>
            <li>
              <strong>Redis Security:</strong> Our Redis cache is configured with authentication and access controls to
              prevent unauthorized access.
            </li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Application Security
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            We follow secure coding practices to prevent common vulnerabilities:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              <strong>Input Validation:</strong> All user inputs are validated and sanitized to prevent injection
              attacks (SQL injection, XSS, etc.).
            </li>
            <li>
              <strong>CSRF Protection:</strong> We implement Cross-Site Request Forgery (CSRF) protection mechanisms.
            </li>
            <li>
              <strong>Content Security Policy:</strong> We use Content Security Policy (CSP) headers to prevent XSS
              attacks.
            </li>
            <li>
              <strong>Rate Limiting:</strong> API endpoints are rate-limited to prevent abuse and denial-of-service
              attacks.
            </li>
            <li>
              <strong>Dependency Scanning:</strong> We regularly scan our dependencies for known vulnerabilities and
              update them promptly.
            </li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Data Privacy and Compliance
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            We are committed to protecting your privacy and complying with applicable data protection regulations:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>We implement data minimization principles, collecting only necessary information</li>
            <li>We provide transparency about data collection and usage through our Privacy Policy</li>
            <li>We honor user rights including data access, correction, and deletion requests</li>
            <li>We maintain detailed audit logs for security and compliance purposes</li>
          </ul>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            For more information about how we handle your data, please see our{' '}
            <Link href="/privacy" className="text-mint-600 hover:text-mint-700 dark:text-mint-400 dark:hover:text-mint-300">
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
            In the event of a security incident:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>We have an incident response plan to quickly identify, contain, and remediate security issues</li>
            <li>We will notify affected users promptly in accordance with applicable regulations</li>
            <li>We conduct post-incident reviews to improve our security practices</li>
            <li>We work with security researchers and experts to address vulnerabilities</li>
          </ul>
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
            <li>Report any suspicious activity or security concerns to us immediately</li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Responsible Disclosure
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
              <a href="mailto:security@earningsnerd.com" className="text-mint-600 hover:text-mint-700 dark:text-mint-400 dark:hover:text-mint-300">
                security@earningsnerd.com
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
            Third-Party Services
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            We use trusted third-party services that maintain their own security standards:
          </p>
          <ul className="list-disc space-y-2 pl-6 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              <strong>Stripe:</strong> PCI-DSS Level 1 certified payment processing
            </li>
            <li>
              <strong>Resend:</strong> Secure email delivery service
            </li>
            <li>
              <strong>OpenAI:</strong> API access for AI-powered features with enterprise-grade security
            </li>
            <li>
              <strong>Sentry:</strong> Error tracking and monitoring with data encryption
            </li>
            <li>
              <strong>PostHog:</strong> Product analytics with privacy-focused data handling
            </li>
          </ul>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            We carefully vet all third-party services to ensure they meet our security standards.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Contact Us
          </h2>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            If you have questions about our security practices or need to report a security concern:
          </p>
          <ul className="list-none space-y-2 text-text-secondary-light dark:text-text-secondary-dark">
            <li>
              General inquiries:{' '}
              <a href="mailto:hello@earningsnerd.com" className="text-mint-600 hover:text-mint-700 dark:text-mint-400 dark:hover:text-mint-300">
                hello@earningsnerd.com
              </a>
            </li>
            <li>
              Security issues:{' '}
              <a href="mailto:security@earningsnerd.com" className="text-mint-600 hover:text-mint-700 dark:text-mint-400 dark:hover:text-mint-300">
                security@earningsnerd.com
              </a>
            </li>
          </ul>
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
