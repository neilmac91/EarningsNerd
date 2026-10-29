'use client'

import { useEffect, useId, useState } from 'react'
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
import { cx } from '@/components/ui/cx'
import { Modal, ModalBody, ModalFooter, ModalHeader } from '@/components/ui/Modal'
import { Notice } from '@/components/ui/Notice'
import AddressText from '@/features/auth/components/AddressText'
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
  /**
   * Where the share options open: in place, under the buttons (the resend dialog's body), or in a dialog of their own,
   * shaped like the resend dialog, for a bulk summary row: under 200% text the options cannot be narrower than their
   * WhatsApp button and frame, 197px at 320px, and the row there is 110px (E242, chief design on #1784).
   */
  optionsIn?: 'place' | 'dialog'
  /**
   * The status line of the dialog this sits in (the resend dialog's), which says a share sheet that could not open. The
   * page's toast region lies outside an aria-modal dialog, which hides it from VoiceOver, so from inside one a toast is
   * never heard (chief design on #1793). A share empties the line as the sheet opens (''), so a second failure is said
   * again, and the line keeps its room while the sheet is open; a share that ends with nothing to say, shared or
   * dismissed, empties it for good (null). Without it, the failure is said in the toast region.
   */
  onStatus?: (message: string | null) => void
}

/**
 * Social-sharing surface for a single invite link. Primary path is the native Web Share API
 * (mobile/PWA); a desktop-friendly fallback menu always renders WhatsApp / Messages / Email /
 * Copy, in place or in a dialog of its own (`optionsIn`). Free text is URL-encoded by the
 * deep-link builders; the link/token is never logged.
 */
export default function ShareInvite({ link, email, defaultMessage, optionsIn = 'place', onStatus }: ShareInviteProps) {
  const [open, setOpen] = useState(false)
  const titleId = useId()
  // Editable, fully-substituted message. `{name}` collapses cleanly when no name is supplied.
  const [message, setMessage] = useState(() =>
    buildInviteMessage({ template: defaultMessage ?? DEFAULT_INVITE_MESSAGE, link }),
  )

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
    // Emptied first, so a second failure is said again.
    onStatus?.('')
    let failed = false
    try {
      await navigator.share({
        title: 'Your EarningsNerd beta invite',
        // Avoid duplicating the raw URL: it travels in the dedicated `url` field below.
        text: messageWithoutLink(message, link),
        url: link,
      })
    } catch (err) {
      // The user dismissing the share sheet throws AbortError — that's not a failure.
      failed = !(err instanceof DOMException && err.name === 'AbortError')
    }
    if (!failed) onStatus?.(null)
    else if (onStatus) onStatus('Could not open the share sheet.')
    else toast.error('Could not open the share sheet.')
  }

  const options = (
    <ShareOptions link={link} message={message} onMessage={setMessage} unbound={unbound} optionsIn={optionsIn} />
  )

  return (
    <div className="inline-flex flex-col items-end gap-2">
      {/* The pair wraps: beside the browser's own share sheet, "Share invite" and "More" side by side ran past a bulk
          summary row and the resend dialog's body under 200% text (E242, chief design on #1791). */}
      <div className="inline-flex flex-wrap items-center justify-end gap-2">
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
          aria-haspopup={optionsIn === 'dialog' ? 'dialog' : undefined}
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

      {open && optionsIn === 'place' && options}
      {optionsIn === 'dialog' && (
        // The address at the top, the options open on arrival, Done at the foot: the resend dialog's shape, so an invite
        // has one share surface in both flows. Closing returns focus to the opener (ui/Modal).
        <Modal open={open} onClose={() => setOpen(false)} labelledBy={titleId} size="md">
          <ModalHeader id={titleId} onClose={() => setOpen(false)} icon={<ShareNetworkIcon className="h-5 w-5" />}>
            Share invite
          </ModalHeader>
          <ModalBody>
            {email && !unbound && (
              <p className="mb-4 text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
                The invite link for{' '}
                {/* The address breaks after its @ (AddressText), and inside a part only where the part is longer than
                    the line, as the verify-email dialog sets one. */}
                <span className="break-words font-medium text-text-primary-light dark:text-text-primary-dark">
                  <AddressText address={email} />
                </span>{' '}
                works once, and only for that address.
              </p>
            )}
            {options}
          </ModalBody>
          <ModalFooter>
            <Button variant="secondary" onClick={() => setOpen(false)} className="w-full">
              Done
            </Button>
          </ModalFooter>
        </Modal>
      )}
    </div>
  )
}

interface ShareOptionsProps {
  link: string
  message: string
  onMessage: (message: string) => void
  unbound: boolean
  optionsIn: 'place' | 'dialog'
}

// The buttons' and the panel's insets take E120's cap (E240): in the resend dialog at 320px under 200% text the
// body's column is about 216px, and "WhatsApp" alone is 200px at its narrowest inside uncapped insets.
const externalLinkClasses =
  'inline-flex items-center gap-1.5 rounded-lg border border-border-light bg-panel-light px-cap-2.5 py-1.5 text-xs font-medium text-text-primary-light transition-colors hover:bg-brand-weak dark:border-white/10 dark:bg-panel-dark dark:text-text-primary-dark dark:hover:bg-white/5'

/**
 * The share options: the message, the warning a link anyone can redeem carries, and the channels. Copy for DM/LinkedIn
 * and Copy message say a press in the options' own status line, under their buttons: the options open only inside a
 * dialog (the resend dialog's body, or their own), and the page's toast region lies outside it, which aria-modal hides
 * from VoiceOver (chief design on #1793). The line goes with the options when they close. While a repeat press empties
 * it, it keeps the words it last said, invisible and hidden from the accessibility tree, so it holds its room and the
 * dialog around it holds still, as the resend dialog's line does.
 */
function ShareOptions({ link, message, onMessage, unbound, optionsIn }: ShareOptionsProps) {
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle')
  // What the line last said, kept in the render that empties it (see ResendShareModal).
  const [held, setHeld] = useState<'copied' | 'failed' | null>(null)
  if (copyState !== 'idle' && copyState !== held) setHeld(copyState)
  const words = (state: 'copied' | 'failed') => (state === 'copied' ? 'Invite message copied.' : 'Could not copy the message.')
  const deepLinks = buildShareDeepLinks(message)

  const handleCopyMessage = async () => {
    // Emptied first, so a second press that says the same is said again.
    setCopyState('idle')
    try {
      await navigator.clipboard.writeText(message)
      setCopyState('copied')
    } catch {
      setCopyState('failed')
    }
  }

  // Its minimum stops at its container, so under 200% text it no longer holds the resend dialog wider than a phone (E240).
  // In place it stops at 24rem; in a dialog of its own it takes the body's width, as the Done under it does (E242).
  return (
    <div
      className={cx(
        'w-full min-w-[min(16rem,100%)] space-y-3 rounded-lg border border-border-light bg-panel-light p-cap-3 shadow-e2 dark:border-white/10 dark:bg-panel-dark dark:shadow-none',
        optionsIn === 'place' && 'max-w-sm',
      )}
    >
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
          onChange={(e) => onMessage(e.target.value)}
          rows={4}
          className={inputClasses()}
        />
      </div>

      {/* A link anyone can redeem is a risk the sender weighs before sharing: the warning Notice (E196 (2)). The
          panel opens inside a dialog's body, the resend dialog's (ResendShareModal) or its own (E242), where a
          Notice's own px-4 is at the dialog's threshold and takes the cap (E229; surface-padding-cap cannot read it
          across files, so inviteOutcomeEmailed.spec.tsx holds it). */}
      {unbound && (
        <Notice
          variant="warning"
          className="px-cap-4"
          title="Not bound to an email"
          description="Anyone with this link can redeem it. Share only with the intended person."
        />
      )}

      <div>
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
        {/* Always in place while the options are open, so the line is a live region before a press fills it; empty before a
            first press, it takes no room. */}
        <p
          role="status"
          className={cx('text-xs text-text-secondary-light dark:text-text-secondary-dark', held && 'mt-2')}
        >
          {copyState !== 'idle' ? words(copyState) : held && <span aria-hidden="true" className="invisible">{words(held)}</span>}
        </p>
      </div>
    </div>
  )
}
