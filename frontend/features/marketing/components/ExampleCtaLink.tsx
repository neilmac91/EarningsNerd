'use client'

import Link from 'next/link'
import type { ReactNode, Ref } from 'react'
import { cx } from '@/components/ui/cx'
import analytics from '@/lib/analytics'

/**
 * "See an example" CTA link that fires the activation-funnel
 * `example_cta_clicked` event (placement identifies which CTA was clicked).
 */
export default function ExampleCtaLink({
  href,
  placement,
  className,
  linkRef,
  children,
}: {
  href: string
  placement: string
  className?: string
  linkRef?: Ref<HTMLAnchorElement>
  children: ReactNode
}) {
  // Every Tab stop carries the brand ring (DESIGN_SYSTEM.md §4), so the link brings its own, written out
  // where the ring scan can read it; callers style the rest.
  return (
    <Link
      ref={linkRef}
      href={href}
      className={cx('focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark', className)}
      onClick={() => analytics.exampleCtaClicked(placement, href)}
    >
      {children}
    </Link>
  )
}
