// The legal pages' layout, in a module without 'use client' so their server components read it as a string
// (lessons/frontend-client-exports-need-next-build.md), as components/ui/markedCopyLayout.ts holds MarkedCopy's measure.

/**
 * A legal page's <main> (/security, /terms and /privacy), set inside a `[container-type:inline-size]` wrapper. Its side
 * gutter is rem (px-4, then sm:px-6 and lg:px-8), so it doubles with the reader's text and narrows the column: 32px a
 * side on a phone under 200% text. So the gutter gives way before a word breaks: narrower than 13em of the wrapper's
 * own text size (416px under 200% text, 208px at the default size, so on no phone at the default size and on no
 * tablet), the gutter is px-2, 16px under 200% text, as /analysis's main is. A query in em follows the reader's text
 * size, which `sm:` (px) never does. At 390px under 200% text the column is then 358px, where "Indemnification" holds
 * whole (it broke in the 326px column), and at 320px 288px, where the page title does. A word still wider than the
 * column breaks inside it, the last resort (D-055): `[overflow-wrap:anywhere]`, which every heading, paragraph and
 * address inherits. One string, so the three pages keep one rule (E131).
 */
export const legalPageMainClass =
  'mx-auto max-w-4xl px-4 py-12 [overflow-wrap:anywhere] sm:px-6 lg:px-8 [@container(max-width:13em)]:px-2'
