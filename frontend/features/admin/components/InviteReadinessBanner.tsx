'use client'

import type { RefObject } from 'react'
import { Notice } from '@/components/ui'
import { RetryButton, type RetainedFailure } from '@/hooks/useRetainedFailure'
import type { InviteReadiness } from '@/features/admin/api/admin-api'
import { heldCapabilities } from '@/features/admin/lib/inviteReadiness'

interface InviteReadinessBannerProps {
  /** The latest readiness answer; undefined while the read loads or after it failed. */
  readiness: InviteReadiness | undefined
  /** The first read is in flight. */
  checking: boolean
  /** The readiness read's retained failure (useRetainedFailure), which holds the failure notice through a Try again. */
  failure: RetainedFailure
  /** Where focus goes when the failure's Try again leaves while it holds focus. */
  focusTarget: RefObject<HTMLElement | null>
}

/**
 * The top of /admin/invites: what holds new invite links and invitation email, and who or what clears it. Each held
 * capability is its own info Notice (a mode of the system), so registration held reads apart from invitation email
 * held; a provider's refusal of one email shows in that invite's row instead. A failed read is an error Notice with
 * Try again, and both capabilities stay off until a read answers (fail closed); the list and Revoke never wait on it.
 * Loading is a run in progress, so it is words, never a Notice (DESIGN_SYSTEM.md §4 › Inline notice).
 */
export default function InviteReadinessBanner({ readiness, checking, failure, focusTarget }: InviteReadinessBannerProps) {
  if (failure.failed) {
    return (
      <Notice
        variant="error"
        title="Could not check what is available."
        description="Until the check answers, new invite links, Resend and invitation email stay off. The list and Revoke still work."
        action={<RetryButton size="sm" failures={[failure]} focusTarget={focusTarget} />}
      />
    )
  }
  if (!readiness) {
    return checking ? (
      <p role="status" className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
        Checking whether invite links and invitation email are available…
      </p>
    ) : null
  }
  const held = heldCapabilities(readiness)
  if (held.length === 0) return null
  return (
    <div className="space-y-3">
      {held.map((capability) => (
        <Notice key={capability.key} variant="info" title={capability.title} description={capability.description} />
      ))}
    </div>
  )
}
