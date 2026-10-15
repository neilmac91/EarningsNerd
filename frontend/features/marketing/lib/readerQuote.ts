/**
 * A reader's words on the landing page (docs/brand/01-interview.md §2, "What must stay honest", and
 * A5): the slot is built, and it renders nothing until a real reader supplies a quote and approves its
 * exact wording, and how they are named, in writing. No placeholder testimonial ever ships. Set both
 * fields to render it. The voice half of that promise is held by #1288's voice rules
 * (brandVoiceRules.spec.ts walks every .ts file under features/), so it is a gate only once #1288 merges;
 * tests/unit/readerQuoteSlot.spec.tsx holds the empty slot and the shipped value's punctuation.
 */
export interface ReaderQuote {
  /** The reader's words, verbatim, with no exclamation mark and no em-dash. */
  quote: string
  /** How the reader is named, as they approved it in writing: a name and what they invest in. */
  attribution: string
}

export const READER_QUOTE: ReaderQuote | null = null
