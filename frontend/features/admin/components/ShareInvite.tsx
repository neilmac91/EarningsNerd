'use client'

import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import {
  ChatTextIcon,
  CopyIcon,
  EnvelopeSimpleIcon,
  LinkedinLogoIcon,
  ShareNetworkIcon,
  WhatsappLogoIcon,
} from '@/lib/icons'
import { inputClasses } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { Notice } from '@/components/ui/Notice'
import {
  DEFAULT_INVITE_MESSAGE,
  buildInviteMessage,
  buildShareDeepLinks,
  isUnboundInvite,
  messageWithoutLink,
} from '@/features/admin/lib/shareLinks'

interface ShareInviteProps {
  link: string
  email?: string | null
  /** Optional template override (defaults to the professional beta-invite copy). */
  defaultMessage?: string
}

/**
 * Social-sharing surface for a single invite link. Primary path is the native Web Share API
 * (mobile/PWA); a desktop-friendly fallback menu always renders WhatsApp / Messages / Email /
 * Copy. Free text is URL-encoded by the deep-link builders; the link/token is never logged.
 */
export default function ShareInvite({ link, email, defaultMessage }: ShareInviteProps) {
  const [open, setOpen] = useState(false)
  // Editable, fully-substituted message. `{name}` collapses cleanly when no name is supplied.
  const [message, setMessage] = useState(() =>
    buildInviteMessage({ template: defaultMessage ?? DEFAULT_INVITE_MESSAGE, link }),
  )

  const deepLinks = buildShareDeepLinks(message)
  const unbound = isUnboundInvite(email)

  // Native share is offered only when the platform supports it AND will accept this payload.
  // Detected after mount (navigator is undefined during SSR) to avoid a hydration mismatch.
  const [canNativeShare, setCanNativeShare] = useState(false)
  useEffect(() => {
    if (
      typeof navigator !== 'undefined' &&
      typeof navigator.share === 'function' &&
      (typeof navigator.canShare === 'function' ? navigator.canShare({ url: link }) : true)
    ) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- post-mount Web Share capability detection (navigator is undefined during SSR; deferred to avoid hydration mismatch)
      setCanNativeShare(true)
    }
  }, [link])

  const handleNativeShare = async () => {
    try {
      await navigator.share({
        title: 'Your EarningsNerd beta invite',
        // Avoid duplicating the raw URL: it travels in the dedicated `url` field below.
        text: messageWithoutLink(message, link),
        url: link,
      })
    } catch (err) {
      // The user dismissing the share sheet throws AbortError — that's not a failure.
      if (err instanceof DOMException && err.name === 'AbortError') return
      toast.error('Could not open the share sheet.')
    }
  }

  const handleCopyMessage = async () => {
    try {
      await navigator.clipboard.writeText(message)
      toast.success('Invite message copied')
    } catch {
      toast.error('Could not copy the message.')
    }
  }

  // The buttons' and the panel's insets take E120's cap (E240): in the resend dialog at 320px under 200% text the
  // body's column is about 216px, and "WhatsApp" alone is 200px at its narrowest inside uncapped insets.
  const externalLinkClasses =
    'inline-flex items-center gap-1.5 rounded-lg border border-border-light bg-panel-light px-cap-2.5 py-1.5 text-xs font-medium text-text-primary-light transition-colors hover:bg-brand-weak dark:border-white/10 dark:bg-panel-dark dark:text-text-primary-dark dark:hover:bg-white/5'

  return (
    <div className="inline-flex flex-col items-end gap-2">
      <div className="inline-flex items-center gap-2">
        {canNativeShare && (
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={handleNativeShare}
          >
            <ShareNetworkIcon className="h-3.5 w-3.5" />
            Share invite
          </Button>
        )}
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
        >
          {/* Each control here is named by the words it shows, which a voice command can say, and the toggle's state is
              aria-expanded's: a label that replaced them ("Show share options" on "Share invite") failed WCAG 2.5.3
              (E243). "More" takes a hidden tail, its own space first (lessons/frontend-hidden-name-tails-bring-their-
              own-space.md). */}
          {canNativeShare ? (
            <>
              More{' '}<span className="sr-only">share options</span>
            </>
          ) : (
            'Share invite'
          )}
        </Button>
      </div>

      {open && (
        // Its minimum stops at its container, so under 200% text it no longer holds the resend dialog wider than a
        // phone (E240).
        <div className="w-full min-w-[min(16rem,100%)] max-w-sm space-y-3 rounded-lg border border-border-light bg-panel-light p-cap-3 shadow-e2 dark:border-white/10 dark:bg-panel-dark dark:shadow-none">
          <div>
            <label
              htmlFor={`share-message-${link}`}
              className="mb-1 block text-xs font-medium text-text-secondary-light dark:text-text-secondary-dark"
            >
              Message
            </label>
            <textarea
              id={`share-message-${link}`}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={4}
              className={inputClasses()}
            />
          </div>

          {/* A link anyone can redeem is a risk the sender weighs before sharing: the warning Notice (E196 (2)). The
              panel opens inside the resend dialog's body (ResendShareModal), where a Notice's own px-4 is at the
              dialog's threshold and takes the cap (E229; surface-padding-cap cannot read it across files, so
              inviteOutcomeEmailed.spec.tsx holds it). On the bulk summary's page the cap bites only below 25rem. */}
          {unbound && (
            <Notice
              variant="warning"
              className="px-cap-4"
              title="Not bound to an email"
              description="Anyone with this link can redeem it. Share only with the intended person."
            />
          )}

          <div className="flex flex-wrap gap-2">
            <a
              href={deepLinks.whatsapp}
              target="_blank"
              rel="noopener noreferrer"
              className={`focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark ${externalLinkClasses}`}
            >
              <WhatsappLogoIcon className="h-3.5 w-3.5" />
              WhatsApp
            </a>
            <a
              href={deepLinks.sms}
              className={`focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark ${externalLinkClasses}`}
            >
              <ChatTextIcon className="h-3.5 w-3.5" />
              Messages
            </a>
            <a
              href={deepLinks.mailto}
              className={`focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark ${externalLinkClasses}`}
            >
              <EnvelopeSimpleIcon className="h-3.5 w-3.5" />
              Email
            </a>
            <button
              type="button"
              onClick={handleCopyMessage}
              className={`focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark ${externalLinkClasses}`}
            >
              <LinkedinLogoIcon className="h-3.5 w-3.5" />
              {/* A break after the slash: unbroken, "DM/LinkedIn" held the button at 224px under 200% text (E240). */}
              Copy for DM/<wbr />LinkedIn
            </button>
            <button
              type="button"
              onClick={handleCopyMessage}
              className={`focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark ${externalLinkClasses}`}
            >
              <CopyIcon className="h-3.5 w-3.5" />
              Copy message
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
