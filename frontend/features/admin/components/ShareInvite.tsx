'use client'

import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import {
  ChatTextIcon,
  CopyIcon,
  EnvelopeSimpleIcon,
  LinkedinLogoIcon,
  ShareNetworkIcon,
  WarningIcon,
  WhatsappLogoIcon,
} from '@/lib/icons'
import { inputClasses } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
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

  const externalLinkClasses =
    'inline-flex items-center gap-1.5 rounded-lg border border-border-light bg-panel-light px-2.5 py-1.5 text-xs font-medium text-text-primary-light transition-colors hover:bg-brand-weak dark:border-white/10 dark:bg-panel-dark dark:text-text-primary-dark dark:hover:bg-white/5'

  return (
    <div className="inline-flex flex-col items-end gap-2">
      <div className="inline-flex items-center gap-2">
        {canNativeShare && (
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={handleNativeShare}
            aria-label="Share invite"
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
          aria-label={open ? 'Hide share options' : 'Show share options'}
        >
          {canNativeShare ? 'More' : 'Share invite'}
        </Button>
      </div>

      {open && (
        <div className="w-full min-w-[16rem] max-w-sm space-y-3 rounded-lg border border-border-light bg-panel-light p-3 shadow-e2 dark:border-white/10 dark:bg-panel-dark dark:shadow-none">
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

          {unbound && (
            <p className="flex items-start gap-1.5 rounded border border-warning-light/40 bg-warning-light/10 px-2.5 py-1.5 text-xs text-warning-light dark:border-warning-dark/40 dark:bg-warning-dark/15 dark:text-warning-dark">
              <WarningIcon className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
              <span>
                Not bound to an email: anyone with this link can redeem it. Share only with the
                intended person.
              </span>
            </p>
          )}

          <div className="flex flex-wrap gap-2">
            <a
              href={deepLinks.whatsapp}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Share invite via WhatsApp"
              className={externalLinkClasses}
            >
              <WhatsappLogoIcon className="h-3.5 w-3.5" />
              WhatsApp
            </a>
            <a
              href={deepLinks.sms}
              aria-label="Share invite via Messages"
              className={externalLinkClasses}
            >
              <ChatTextIcon className="h-3.5 w-3.5" />
              Messages
            </a>
            <a
              href={deepLinks.mailto}
              aria-label="Share invite via email"
              className={externalLinkClasses}
            >
              <EnvelopeSimpleIcon className="h-3.5 w-3.5" />
              Email
            </a>
            <button
              type="button"
              onClick={handleCopyMessage}
              aria-label="Copy invite message and link for a DM or LinkedIn"
              className={externalLinkClasses}
            >
              <LinkedinLogoIcon className="h-3.5 w-3.5" />
              Copy for DM/LinkedIn
            </button>
            <button
              type="button"
              onClick={handleCopyMessage}
              aria-label="Copy invite message and link"
              className={externalLinkClasses}
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
