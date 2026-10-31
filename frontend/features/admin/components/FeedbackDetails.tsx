'use client'

import { Modal, ModalBody, ModalHeader } from '@/components/ui/Modal'
import type { FeedbackRecord } from '@/features/admin/api/admin-api'
import FeedbackMessage from '@/features/feedback/components/FeedbackMessage'
import FeedbackScreenshots from '@/features/feedback/components/FeedbackScreenshots'

interface FeedbackDetailsProps {
  feedback: FeedbackRecord
  open: boolean
  onClose: () => void
}

export default function FeedbackDetails({ feedback, open, onClose }: FeedbackDetailsProps) {
  const titleId = `feedback-details-${feedback.id}`
  return (
    <Modal open={open} onClose={onClose} labelledBy={titleId} size="lg" className="ph-no-capture">
      <ModalHeader id={titleId} onClose={onClose}>Feedback details</ModalHeader>
      <ModalBody className="space-y-4">
        <FeedbackMessage message={feedback.message} />
        <dl className="space-y-3 border-t border-border-light pt-4 text-sm dark:border-white/10">
          <div>
            <dt className="font-medium text-text-secondary-light dark:text-text-secondary-dark">Sent from</dt>
            <dd className="[overflow-wrap:anywhere] text-text-primary-light dark:text-text-primary-dark">{feedback.page_url ?? 'No page recorded'}</dd>
          </div>
          <div>
            <dt className="font-medium text-text-secondary-light dark:text-text-secondary-dark">Reporter</dt>
            <dd className="[overflow-wrap:anywhere] text-text-primary-light dark:text-text-primary-dark">{feedback.user_email ?? 'Anonymous'}</dd>
          </div>
        </dl>
        {open && !!feedback.attachments?.length && <FeedbackScreenshots attachments={feedback.attachments} />}
      </ModalBody>
    </Modal>
  )
}
