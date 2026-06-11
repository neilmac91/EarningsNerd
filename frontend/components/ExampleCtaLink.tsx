'use client'

import Link from 'next/link'
import type { ReactNode } from 'react'
import analytics from '@/lib/analytics'

/**
 * "See an example" CTA link that fires the activation-funnel
 * `example_cta_clicked` event (placement identifies which CTA was clicked).
 */
export default function ExampleCtaLink({
  href,
  placement,
  className,
  children,
}: {
  href: string
  placement: string
  className?: string
  children: ReactNode
}) {
  return (
    <Link
      href={href}
      className={className}
      onClick={() => analytics.exampleCtaClicked(placement, href)}
    >
      {children}
    </Link>
  )
}
