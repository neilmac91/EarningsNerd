'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { WarningCircleIcon } from '@/lib/icons'
import { Button, Modal, ModalBody, ModalFooter, ModalHeader } from '@/components/ui'
import { getCurrentUserSafe, resendVerification } from '@/features/auth/api/auth-api'
import { EMAIL_VERIFICATION_REQUIRED_EVENT } from '@/lib/api/client'
import { queryKeys } from '@/lib/queryKeys'

/**
 * Global, graceful intercept of the backend's "verify your email" 403. The axios
 * interceptor dispatches EMAIL_VERIFICATION_REQUIRED_EVENT when an unverified user
 * hits a gated action (generate / checkout); this modal turns that into a friendly
 * resend prompt instead of a raw error toast.
 *
 * v3 (DS-04): composed on ui/Modal — the focus trap, Escape, focus return, scroll lock
 * and the overlay / z-modal tokens come from the primitive; actions are <Button>s.
 */
export default function EmailVerificationModal() {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [resent, setResent] = useState(false)
  const router = useRouter()
  const queryClient = useQueryClient()

  const { data: user } = useQuery({
    queryKey: queryKeys.currentUser(),
    queryFn: getCurrentUserSafe,
    retry: false,
    staleTime: 60_000,
  })

  useEffect(() => {
    const handler = () => {
      setResent(false)
      setOpen(true)
    }
    window.addEventListener(EMAIL_VERIFICATION_REQUIRED_EVENT, handler)
    return () => window.removeEventListener(EMAIL_VERIFICATION_REQUIRED_EVENT, handler)
  }, [])

  const close = () => setOpen(false)

  const handleResend = async () => {
    if (!user?.email || loading || resent) return
    setLoading(true)
    try {
      await resendVerification(user.email)
      setResent(true)
    } catch {
      // best-effort
    } finally {
      setLoading(false)
    }
  }

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.currentUser() })
    queryClient.invalidateQueries({ queryKey: queryKeys.currentUser() })
    router.refresh()
    setOpen(false)
  }

  return (
    <Modal open={open} onClose={close} labelledBy="verify-modal-title" size="md">
      <ModalHeader id="verify-modal-title" onClose={close} icon={<WarningCircleIcon className="h-5 w-5" />} tone="warning">
        Verify your email to continue
      </ModalHeader>
      <ModalBody>
        <p className="text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
          {resent ? (
            <>
              We sent a fresh link to{' '}
              <span className="font-medium text-text-primary-light dark:text-text-primary-dark">
                {user?.email}
              </span>
              . Click it, then come back and refresh.
            </>
          ) : (
            <>
              Generating summaries and subscribing require a verified email. We sent a link to{' '}
              <span className="font-medium text-text-primary-light dark:text-text-primary-dark">
                {user?.email}
              </span>
              .
            </>
          )}
        </p>
      </ModalBody>
      <ModalFooter>
        <Button
          variant="secondary"
          onClick={handleResend}
          loading={loading}
          disabled={resent}
          className="w-full sm:w-auto"
        >
          {resent ? 'Link sent' : 'Resend link'}
        </Button>
        <Button onClick={handleRefresh} className="w-full sm:w-auto">
          I&apos;ve verified
        </Button>
      </ModalFooter>
    </Modal>
  )
}
