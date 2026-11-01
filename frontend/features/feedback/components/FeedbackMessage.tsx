import { Fragment } from 'react'
import { feedbackTextParts } from '@/features/feedback/lib/feedbackLinks'

/** Untrusted feedback stays literal text; only validated web destinations become links. */
export default function FeedbackMessage({ message }: { message: string }) {
  return (
    <p className="whitespace-pre-wrap [overflow-wrap:anywhere] text-sm text-text-primary-light dark:text-text-primary-dark">
      {feedbackTextParts(message).map((part, index) => part.href ? (
        <a
          key={index}
          href={part.href}
          target="_blank"
          rel="noopener noreferrer"
          // The message reads literally, so the link says it opens a new tab in its name alone, not in its text (E281).
          aria-label={`${part.text} (opens in a new tab)`}
          className="box-decoration-clone rounded-sm underline decoration-text-tertiary-light underline-offset-4 hover:text-brand-strong hover:decoration-brand-strong focus-visible:outline-none focus-visible:shadow-ring-brand dark:decoration-text-tertiary-dark dark:hover:text-brand-strong-dark dark:hover:decoration-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark"
        >
          {part.text}
        </a>
      ) : <Fragment key={index}>{part.text}</Fragment>)}
    </p>
  )
}
