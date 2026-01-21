import Link from 'next/link'

export default function Footer() {
  return (
    <footer className="border-t border-border-light bg-background-light dark:border-border-dark dark:bg-background-dark">
      <div className="mx-auto flex max-w-7xl flex-col gap-8 px-6 py-12 text-sm text-text-secondary-light dark:text-text-secondary-dark md:flex-row md:items-center md:justify-between">
        <div className="font-medium text-text-tertiary-light dark:text-text-tertiary-dark">
          &copy; {new Date().getFullYear()} EarningsNerd. All rights reserved.
        </div>
        <div className="flex flex-wrap items-center gap-6">
          <Link
            href="/privacy"
            className="font-medium transition-colors hover:text-text-primary-light dark:hover:text-text-primary-dark"
          >
            Privacy
          </Link>
          <Link
            href="/security"
            className="font-medium transition-colors hover:text-text-primary-light dark:hover:text-text-primary-dark"
          >
            Security
          </Link>
          <Link
            href="/contact"
            className="font-medium transition-colors hover:text-text-primary-light dark:hover:text-text-primary-dark"
          >
            Contact
          </Link>
        </div>
      </div>
    </footer>
  )
}
