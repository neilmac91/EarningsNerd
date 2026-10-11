import { FOUNDER_NOTE } from '@/features/marketing/lib/founderNote'

/**
 * The human on the page: the founder's approved sentence, signed with a first name, set as a
 * marked aside under the hero example. Renders nothing while `FOUNDER_NOTE` is null (the slot is
 * built, the words are the founder's to supply), so the page never shows a placeholder.
 */
export default function FounderNote() {
  if (!FOUNDER_NOTE) return null
  return (
    <figure className="mt-5 border-l-2 border-brand-border pl-4 dark:border-brand-border-dark">
      <blockquote className="text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
        {FOUNDER_NOTE.sentence}
      </blockquote>
      <figcaption className="mt-1.5 font-data text-xs text-text-tertiary-light dark:text-text-secondary-dark">
        {FOUNDER_NOTE.name} · EarningsNerd
      </figcaption>
    </figure>
  )
}
