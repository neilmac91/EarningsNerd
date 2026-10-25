'use client'

import Link from 'next/link'
import type { ReactNode, Ref } from 'react'
import { buttonVariants, type ButtonSize, type ButtonVariant } from '@/components/ui'
import analytics from '@/lib/analytics'

/**
 * A marketing link styled as a design-system button. Server sections can't call
 * `buttonVariants()` (a client export), so this thin client boundary composes it for them.
 * Passing `placement` fires the activation-funnel `example_cta_clicked` event (the same contract
 * as ExampleCtaLink) for "see a live example" CTAs; account CTAs pass no placement.
 */
export default function MarketingCta({
  href,
  variant = 'primary',
  size = 'lg',
  placement,
  className,
  linkRef,
  children,
}: {
  href: string
  variant?: ButtonVariant
  size?: ButtonSize
  placement?: string
  className?: string
  linkRef?: Ref<HTMLAnchorElement>
  children: ReactNode
}) {
  return (
    <Link
      ref={linkRef}
      href={href}
      className={buttonVariants({ variant, size, className })}
      onClick={placement ? () => analytics.exampleCtaClicked(placement, href) : undefined}
    >
      {children}
    </Link>
  )
}
