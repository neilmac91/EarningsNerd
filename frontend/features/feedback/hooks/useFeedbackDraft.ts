'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import type { CurrentUser } from '@/features/auth/api/auth-api'
import { getSessionGeneration, isSessionGenerationCurrent } from '@/lib/api/session'
import { getErrorMessage, getErrorStatus } from '@/lib/api/types'
import { queryKeys } from '@/lib/queryKeys'
import { useRetainedFailure } from '@/hooks/useRetainedFailure'
import { getFeedbackSubmission, submitFeedback, type FeedbackInput, type FeedbackType } from '../api/feedback-api'
import { clearPendingFeedback, feedbackFileError, readPendingFeedback, storePendingFeedback } from '../lib/feedbackFiles'

export interface FeedbackFile { id: string; file: File; preview: string }
interface Snapshot { input: FeedbackInput; files: readonly File[] }
interface Pending { key: string; snapshot?: Snapshot; uncertain: boolean }
type Phase = 'editing' | 'sending' | 'checking' | 'resend'

/** A submitted draft stays immutable until the server's receipt or a fenced failure settles it. */
export function useFeedbackDraft(readerId: number, onSaved: () => void) {
  const client = useQueryClient()
  const [type, setType] = useState<FeedbackType>('general')
  const [message, setMessage] = useState('')
  const [files, setFiles] = useState<FeedbackFile[]>([])
  const filesRef = useRef(files)
  const [pending, setPending] = useState<Pending | null>(() => {
    const marker = readPendingFeedback(readerId)
    return marker ? { key: marker.key, uncertain: true } : null
  })
  const [phase, setPhase] = useState<Phase>(pending ? 'checking' : 'editing')
  const [generation, setGeneration] = useState(getSessionGeneration)
  const [progress, setProgress] = useState(0)
  const [notice, setNotice] = useState('')
  const [editableFailure, setEditableFailure] = useState(false)
  const inFlight = useRef(false)
  const requestSequence = useRef(0)
  const mounted = useRef(false)
  const preserveDraft = useRef(false)
  const settledKey = useRef<string | null>(null)
  const onSavedRef = useRef(onSaved)
  useEffect(() => { onSavedRef.current = onSaved }, [onSaved])

  const owns = useCallback((atGeneration: number) => mounted.current
    && isSessionGenerationCurrent(atGeneration)
    && client.getQueryData<CurrentUser | null>(queryKeys.currentUser())?.id === readerId, [client, readerId])

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      filesRef.current.forEach(({ preview }) => URL.revokeObjectURL(preview))
      // A page refresh keeps the opaque receipt marker. A confirmed different reader never does.
      const reader = client.getQueryData<CurrentUser | null>(queryKeys.currentUser())
      if (reader === null || (reader && reader.id !== readerId)) clearPendingFeedback(readerId)
    }
  }, [client, readerId])

  const statusKey = queryKeys.feedback.submission(readerId, generation, pending?.key ?? null)
  const status = useQuery({
    queryKey: statusKey,
    queryFn: async ({ signal }) => {
      if (!pending || !owns(generation)) throw new DOMException('Account changed', 'AbortError')
      const result = await getFeedbackSubmission(pending.key, signal)
      if (!owns(generation)) throw new DOMException('Account changed', 'AbortError')
      return result
    },
    enabled: !!pending && phase === 'checking',
    retry: false,
    gcTime: 0,
    refetchOnWindowFocus: false,
    refetchInterval: (query) => query.state.data?.state === 'processing'
      ? Math.max(2_000, Math.min(10_000, (query.state.data.retry_after_seconds ?? 5) * 1_000))
      : false,
  })
  const statusFailure = useRetainedFailure(status, statusKey)

  const resetPending = useCallback(() => {
    clearPendingFeedback(readerId)
    setPending(null)
    setPhase('editing')
    setEditableFailure(false)
  }, [readerId])

  const acceptReceipt = useCallback((key: string) => {
    if (settledKey.current === key) return
    settledKey.current = key
    resetPending()
    if (preserveDraft.current) {
      preserveDraft.current = false
      setNotice('Your earlier feedback was saved. This draft is still here if you want to send another note.')
      return
    }
    filesRef.current.forEach(({ preview }) => URL.revokeObjectURL(preview))
    filesRef.current = []
    setFiles([])
    setMessage('')
    setType('general')
    setNotice('')
    toast.success('Thanks for the feedback', { description: 'We read every note. It really helps.' })
    onSavedRef.current()
  }, [resetPending])

  // A server receipt is an external state transition: reconcile it once into this private draft.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (phase !== 'checking') return
    // A failed account transition may retain this reader with a newer generation. Never
    // interpret the old request, but give receipt recovery a fresh, owned query to run.
    const currentGeneration = getSessionGeneration()
    if (generation !== currentGeneration && owns(currentGeneration)) {
      setGeneration(currentGeneration)
      return
    }
    if (status.isFetching || !status.data || !owns(generation)) return
    if (status.data.state === 'submitted' && pending) {
      acceptReceipt(pending.key)
    } else if (status.data.state === 'retryable') {
      if (preserveDraft.current) {
        // A reconstructed draft conflicted with the older fingerprint. Its failed receipt
        // now fences that attempt, so this different draft can safely receive a new key.
        preserveDraft.current = false
        resetPending()
        setNotice('Your earlier feedback was not saved. Your current draft is ready to send.')
      } else if (pending?.snapshot) {
        setPending({ ...pending, uncertain: false })
        setPhase('resend')
        setEditableFailure(true)
        setNotice('Your feedback was not saved. Send the same draft again, or edit it first.')
      } else {
        resetPending()
        setNotice('Your earlier feedback was not saved. Re-enter your note and select the screenshots again.')
      }
    } else if (status.data.state === 'not_found') {
      // A missing receipt cannot prove that a delayed POST will never arrive. Keep this key.
      setPhase(pending?.snapshot ? 'resend' : 'editing')
      setEditableFailure(false)
      setNotice(pending?.snapshot
        ? 'We could not confirm the submission. Send this same draft again to check it safely.'
        : 'We could not confirm your earlier submission. Re-enter the note and select the screenshots; we will check the same submission.')
    }
  }, [acceptReceipt, generation, owns, pending, phase, resetPending, status.data, status.isFetching])
  /* eslint-enable react-hooks/set-state-in-effect */

  const locked = phase === 'sending' || phase === 'checking' || phase === 'resend'
  const addFiles = (incoming: readonly File[]) => {
    if (locked || !owns(getSessionGeneration())) return
    const error = feedbackFileError(incoming, filesRef.current.length)
    if (error) { setNotice(error); return }
    const added = incoming.map((file) => ({ id: crypto.randomUUID(), file, preview: URL.createObjectURL(file) }))
    const next = [...filesRef.current, ...added]
    filesRef.current = next
    setFiles(next)
    setNotice(`${added.length === 1 ? 'Screenshot added' : 'Screenshots added'}. ${next.length} of 3 selected.`)
  }
  const removeFile = (id: string) => {
    if (locked || !owns(getSessionGeneration())) return
    const removed = filesRef.current.find((file) => file.id === id)
    if (removed) URL.revokeObjectURL(removed.preview)
    const next = filesRef.current.filter((file) => file.id !== id)
    filesRef.current = next
    setFiles(next)
    setNotice(`Screenshot removed. ${next.length} of 3 selected.`)
  }

  const submit = async () => {
    if (inFlight.current || phase === 'checking' || message.trim().length < 5) return
    const atGeneration = getSessionGeneration()
    if (!owns(atGeneration)) return
    const submission: Pending & { snapshot: Snapshot } = {
      key: pending?.key ?? crypto.randomUUID(),
      uncertain: pending?.uncertain ?? false,
      snapshot: pending?.snapshot ?? {
        input: { type, message: message.trim(), pageUrl: window.location.pathname },
        files: filesRef.current.map(({ file }) => file),
      },
    }
    inFlight.current = true
    const sequence = ++requestSequence.current
    setPending(submission)
    storePendingFeedback({ owner: readerId, key: submission.key })
    setGeneration(atGeneration)
    setPhase('sending')
    setNotice('')
    setProgress(0)
    setEditableFailure(false)
    client.removeQueries({ queryKey: queryKeys.feedback.submission(readerId, atGeneration, submission.key) })
    try {
      const result = await submitFeedback(submission.snapshot.input, {
        submissionId: submission.key, readerId, files: submission.snapshot.files,
        onUploadProgress: (percent) => { if (requestSequence.current === sequence && owns(atGeneration)) setProgress(percent) },
      })
      if (!owns(atGeneration)) return
      if ('state' in result) {
        setPending({ ...submission, uncertain: true })
        setPhase('checking')
      }
      else acceptReceipt(submission.key)
    } catch (error) {
      if (!owns(atGeneration)) return
      const code = getErrorStatus(error)
      // Validation and admission failures cannot have published this request. An uncertain
      // transport/server outcome always checks the original key before offering another Send.
      if (code && code >= 400 && code < 500 && code !== 409 && code !== 408 && !submission.uncertain) {
        resetPending()
        setNotice(getErrorMessage(error))
      } else {
        setPending({ ...submission, uncertain: true })
        preserveDraft.current = code === 409
        setPhase('checking')
        setNotice('Checking whether your feedback was saved…')
      }
      toast.error('Could not confirm your feedback. Your draft is still here.')
    } finally {
      inFlight.current = false
      // A failed logout can retain this reader after advancing the generation. Keep the snapshot
      // and receipt identity; a fresh activation checks under the current session.
      if (mounted.current && !isSessionGenerationCurrent(atGeneration)) {
        setPending({ ...submission, uncertain: true })
        setPhase('resend')
        setNotice('Your session changed while sending. Send this same draft again to check its receipt.')
      }
    }
  }

  return {
    type, setType, message, setMessage, files, addFiles, removeFile, submit,
    locked, busy: phase === 'sending' || phase === 'checking', phase, progress, notice,
    statusFailure, editableFailure,
    edit: () => { if (editableFailure && owns(getSessionGeneration())) { resetPending(); setNotice(''); preserveDraft.current = false } },
  }
}
