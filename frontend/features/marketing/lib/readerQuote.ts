/**
 * A reader's words on the landing page (docs/brand/01-interview.md §2, "What must stay honest", and
 * A5): the slot is built, and it renders nothing until a real reader supplies a quote and approves its
 * use. No placeholder testimonial ever ships. Set both fields to render it, as with founderNote.ts.
 */
export interface ReaderQuote {
  /** The reader's words, verbatim, with no exclamation mark and no em-dash. */
  quote: string
  /** How the reader is named, as they approved it: a name and what they invest in. */
  attribution: string
}

export const READER_QUOTE: ReaderQuote | null = null
