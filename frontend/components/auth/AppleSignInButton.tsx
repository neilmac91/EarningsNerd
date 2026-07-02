'use client'

/**
 * Apple sign-in button, per Apple Human Interface Guidelines:
 * - Black surface (light theme) / white surface (dark theme) for contrast
 * - Apple logo + "Continue with Apple"
 * - Min height & corner radius matching sibling buttons (never subordinate)
 * The Apple glyph uses currentColor so it tracks the text color in each theme.
 */
export default function AppleSignInButton({
  apiBase,
  label = 'Continue with Apple',
}: {
  apiBase: string
  label?: string
}) {
  return (
    <a
      href={`${apiBase}/api/auth/apple`}
      className="flex w-full items-center justify-center gap-3 rounded-lg bg-black px-4 py-3 text-sm font-semibold text-white transition hover:bg-black/90 active:scale-[0.99] focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark dark:bg-white dark:text-black dark:hover:bg-white/90"
    >
      <AppleLogo />
      {label}
    </a>
  )
}

function AppleLogo() {
  return (
    <svg viewBox="0 0 24 24" className="h-[18px] w-[18px]" fill="currentColor" aria-hidden="true">
      <path d="M16.365 1.43c0 1.14-.42 2.2-1.12 3.01-.74.86-1.95 1.53-3.13 1.43-.14-1.12.43-2.31 1.1-3.06.74-.83 2.03-1.46 3.15-1.5.03.04.03.08.03.12zM20.9 17.16c-.57 1.32-.85 1.9-1.58 3.06-1.02 1.62-2.46 3.64-4.24 3.66-1.58.02-1.98-1.03-4.12-1.02-2.14.01-2.58 1.04-4.16 1.02-1.78-.02-3.14-1.84-4.16-3.46C-.27 17.4-.74 12.3 1.1 9.56c1.3-1.94 3.36-3.07 5.3-3.07 1.97 0 3.21 1.08 4.84 1.08 1.58 0 2.54-1.08 4.83-1.08 1.73 0 3.56.94 4.87 2.57-4.28 2.34-3.58 8.45.06 8.1z" />
    </svg>
  )
}
