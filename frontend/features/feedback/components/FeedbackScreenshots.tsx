'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui'
import { RetryButton, useRetainedFailure } from '@/hooks/useRetainedFailure'
import { getCurrentUserSafe, type CurrentUser } from '@/features/auth/api/auth-api'
import { getSessionGeneration, isSessionGenerationCurrent } from '@/lib/api/session'
import { getErrorStatus } from '@/lib/api/types'
import { downloadBlob } from '@/lib/downloadBlob'
import { queryKeys } from '@/lib/queryKeys'
import { getFeedbackAttachment, type FeedbackAttachment } from '../api/feedback-api'
import { createFeedbackMediaLoader } from '../lib/feedbackMediaQueue'

interface Props { attachments: readonly FeedbackAttachment[] }

/** Mounted only inside open admin details. No object URL or image response survives its reader. */
export default function FeedbackScreenshots({ attachments }: Props) {
  const [loadAttachment] = useState(() => createFeedbackMediaLoader(getFeedbackAttachment))
  const { data: reader } = useQuery({ queryKey: queryKeys.currentUser(), queryFn: getCurrentUserSafe, staleTime: 60_000 })
  if (!reader?.is_admin) return null
  const generation = getSessionGeneration()
  return (
    <section className="ph-no-capture space-y-4" aria-label="Screenshots">
      <h3 className="text-sm font-semibold">Screenshots</h3>
      {attachments.map((attachment, index) => (
        <PrivateScreenshot key={`${reader.id}:${generation}:${attachment.id}`} attachment={attachment} number={index + 1} readerId={reader.id} generation={generation} loadAttachment={loadAttachment} />
      ))}
    </section>
  )
}

function PrivateScreenshot({ attachment, number, readerId, generation, loadAttachment }: {
  attachment: FeedbackAttachment; number: number; readerId: number; generation: number
  loadAttachment: (id: string, signal: AbortSignal) => Promise<Blob>
}) {
  const client = useQueryClient()
  const titleRef = useRef<HTMLParagraphElement>(null)
  const ownsMedia = useCallback(() => {
    const reader = client.getQueryData<CurrentUser | null>(queryKeys.currentUser())
    return isSessionGenerationCurrent(generation) && reader?.id === readerId && reader.is_admin
  }, [client, generation, readerId])
  const [objectUrl, setObjectUrl] = useState<string | null>(null)
  const key = queryKeys.adminFeedback.attachment(readerId, generation, attachment.id)
  const media = useQuery({
    queryKey: key,
    queryFn: async ({ signal }) => {
      const blob = await loadAttachment(attachment.id, signal)
      signal.throwIfAborted()
      if (!ownsMedia()) throw new DOMException('Account changed', 'AbortError')
      return blob
    },
    enabled: attachment.availability === 'available',
    retry: false,
    gcTime: 0,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  })
  const failure = useRetainedFailure(media, key)
  const unavailable = attachment.availability !== 'available' || [403, 404, 410].includes(getErrorStatus(media.error) ?? 0)
  useEffect(() => {
    if (!media.data || unavailable || !ownsMedia()) return
    const url = URL.createObjectURL(media.data)
    // eslint-disable-next-line react-hooks/set-state-in-effect -- publish the browser-owned resource allocated and revoked by this effect
    setObjectUrl(url)
    return () => { URL.revokeObjectURL(url); setObjectUrl(null) }
  }, [media.data, ownsMedia, unavailable])

  function handleDownload() {
    if (media.data && ownsMedia()) downloadBlob(media.data, `feedback-screenshot-${number}.png`)
  }

  return (
    <div className="space-y-2 border-t border-border-light pt-3 dark:border-white/10">
      <p ref={titleRef} tabIndex={-1} className="text-sm font-medium outline-none">Screenshot {number}</p>
      {unavailable ? (
        <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
          {attachment.availability === 'expired' ? 'This screenshot has expired.' : 'This screenshot is no longer available.'}
        </p>
      ) : failure.failed ? (
        <div role="alert" className="space-y-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
          <p>We could not load this screenshot.</p>
          <RetryButton failures={[failure]} focusTarget={titleRef} />
        </div>
      ) : objectUrl ? (
        <>
          {/* Authenticated blob only. Next's public image cache must not receive private feedback. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={objectUrl} alt={`Screenshot ${number}`} width={attachment.width} height={attachment.height} className="h-auto max-h-[24rem] w-full rounded-lg object-contain" />
          <Button variant="secondary" wrap onClick={handleDownload} aria-label={`Download screenshot ${number}`}>Download screenshot</Button>
        </>
      ) : <p role="status" className="text-sm text-text-secondary-light dark:text-text-secondary-dark">Loading screenshot…</p>}
    </div>
  )
}
