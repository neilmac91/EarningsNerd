/**
 * The founder's sentence on the landing page (docs/brand/01-interview.md, A5): one true
 * first-person line and a first name, under the hero example. Like the reader-quote slot, the
 * surface exists and renders nothing until the founder approves the exact words; no placeholder
 * ever ships. Set both fields to render it.
 */
export interface FounderNote {
  /** The approved sentence, verbatim, no exclamation mark. */
  sentence: string
  /** The first name it is signed with. */
  name: string
}

export const FOUNDER_NOTE: FounderNote | null = null
