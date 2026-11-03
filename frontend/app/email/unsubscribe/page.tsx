'use client'

import { useEffect, useRef, useState } from 'react'
import { Button, Card, Notice, primaryUnavailableClass } from '@/components/ui'
import AddressText from '@/features/auth/components/AddressText'
import { unsubscribeFromInvitations, unsubscribeTokenFrom } from '@/features/email/api/unsubscribe-api'
import { getErrorStatus } from '@/lib/api/types'
import { CONTACT_ADDRESSES, contactMailto } from '@/lib/contactAddresses'

/** What the server answered a press: done, a link it does not know, too many tries, or no answer it could give. */
type Outcome = 'unsubscribed' | 'invalid' | 'limited' | 'failed'

const LINK =
  'box-decoration-clone rounded-sm font-medium text-brand-strong underline underline-offset-4 focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark'
/** The answer that replaces the button takes focus from it, so it can show the ring a keyboard user expects. */
const ANSWER = 'rounded-lg focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark'
const NEEDS_LINK_ID = 'unsubscribe-needs-link'

function SupportAddress() {
  return (
    <a href={contactMailto('support')} className={LINK}>
      <AddressText address={CONTACT_ADDRESSES.support} />
    </a>
  )
}

/**
 * The page an invitation email's unsubscribe link opens: {FRONTEND_URL}/email/unsubscribe#token=<token>. It is safe
 * for a link scanner: loading it sends nothing. The token is read from the fragment, which no request carries, and
 * taken out of the address bar at once; only a press of Unsubscribe posts it (POST /api/email/unsubscribe). No login:
 * the token is the email's own. Account email the reader asks for (a password reset) is not affected.
 */
export default function UnsubscribePage() {
  // The email's token: undefined until the fragment is read after mount (the server renders none), null when the
  // address held none.
  const [token, setToken] = useState<string | null | undefined>(undefined)
  const [sending, setSending] = useState(false)
  const [outcome, setOutcome] = useState<Outcome | null>(null)
  const answerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const found = unsubscribeTokenFrom(window.location.hash)
    // Out of the address bar and this history entry: from here the token lives in this page's state alone, so no
    // bookmark, copied address or later visit carries it. Next's own history state is kept.
    if (window.location.hash) {
      window.history.replaceState(window.history.state, '', window.location.pathname + window.location.search)
    }
    // Development's StrictMode runs this twice, and the second run finds the fragment gone: it keeps the first read.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- the fragment is the browser's alone, read once after mount
    setToken((read) => read ?? found)
  }, [])

  // These two answers take the button away, so focus goes to the answer rather than falling to the page.
  const settled = outcome === 'unsubscribed' || outcome === 'invalid'
  useEffect(() => {
    if (settled) answerRef.current?.focus({ preventScroll: true })
  }, [settled])

  const unsubscribe = async () => {
    if (!token || sending || settled) return
    setSending(true)
    setOutcome(null)
    try {
      await unsubscribeFromInvitations(token)
      setOutcome('unsubscribed')
    } catch (err: unknown) {
      const status = getErrorStatus(err)
      setOutcome(status === 404 || status === 422 ? 'invalid' : status === 429 ? 'limited' : 'failed')
    } finally {
      setSending(false)
    }
  }

  const unavailable = !token
  return (
    // The gutter gives way under enlarged text as /delete-account's does: narrower than 13em of the layout's query
    // container (416px under 200% text) it is px-2, so at 320px under 200% text "Unsubscribe" holds whole beside the
    // page's edges. A word still wider than its line breaks inside it, the last resort (D-055).
    <main className="mx-auto max-w-xl px-4 py-12 sm:px-6 lg:px-8 [@container(max-width:13em)]:px-2">
      <h1 className="break-words text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
        Unsubscribe from invitation emails
      </h1>

      <Card className="mt-6 p-cap-6">
        {outcome === 'unsubscribed' ? (
          <div ref={answerRef} tabIndex={-1} className={ANSWER}>
            <Notice
              variant="success"
              title="You're unsubscribed"
              description="We won't send invitation emails to this address. Emails about an account you create, such as password resets, still arrive."
            />
          </div>
        ) : outcome === 'invalid' ? (
          <div ref={answerRef} tabIndex={-1} className={ANSWER}>
            <Notice
              variant="error"
              title="This link isn't valid"
              description={
                <>
                  It may be cut short or out of date. Write to <SupportAddress /> and we&apos;ll stop invitation emails
                  to your address.
                </>
              }
            />
          </div>
        ) : (
          <>
            <p className="text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
              Unsubscribe stops invitation emails to the address this link was sent to. Emails about an account you
              create, such as password resets, still arrive.
            </p>
            {token === null && (
              <div id={NEEDS_LINK_ID} className="mt-4">
                <Notice
                  variant="error"
                  title="This page needs the link from your email"
                  description={
                    <>
                      Open the unsubscribe link in the invitation email: it carries the code this page needs. If that
                      doesn&apos;t work, write to <SupportAddress /> and we&apos;ll stop invitation emails for you.
                    </>
                  }
                />
              </div>
            )}
            {outcome === 'limited' && (
              <div className="mt-4">
                {/* The route allows 20 tries an hour from one connection: the support address is the way on before
                    then (chief design on #1965). */}
                <Notice
                  variant="error"
                  title="Too many tries for now"
                  description={
                    <>
                      Try again in an hour, or write to <SupportAddress /> and we&apos;ll stop invitation emails to your
                      address.
                    </>
                  }
                />
              </div>
            )}
            {outcome === 'failed' && (
              <div className="mt-4">
                <Notice
                  variant="error"
                  title="We couldn't unsubscribe you just now"
                  description={
                    <>
                      Try again in a minute, or write to <SupportAddress /> and we&apos;ll stop invitation emails to your
                      address.
                    </>
                  }
                />
              </div>
            )}
            <div className="mt-6">
              {/* Unavailable without a token: aria-disabled and an early return, its reason the notice above. */}
              <Button
                onClick={unsubscribe}
                loading={sending}
                loadingText="Unsubscribing…"
                // Busy keeps Button's own aria-disabled: a value here replaces it, so it names `sending` too.
                aria-disabled={unavailable || sending || undefined}
                aria-describedby={token === null ? NEEDS_LINK_ID : undefined}
                className={unavailable && !sending ? primaryUnavailableClass : undefined}
              >
                Unsubscribe
              </Button>
            </div>
          </>
        )}
      </Card>
    </main>
  )
}
