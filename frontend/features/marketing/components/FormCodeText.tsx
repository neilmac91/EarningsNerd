import { Fragment } from 'react'

/** A form code ("10-K", "8-K", "20-F"), its plural or possessive included ("8-Ks"), captured so split() keeps it. */
const FORM_CODE = /(\b\d+-[A-Z]+(?:s|['’]s)?\b)/

/**
 * A line of copy whose form codes stay whole: each code is one whitespace-nowrap run, so a line that wraps never
 * breaks "10-Q" at its hyphen (lessons/frontend-check-brand-layouts-at-200-percent-text.md). The words around a code
 * wrap as before, and the text reads the same (the string's own words, in one textContent), so a line shared with
 * /pricing, such as FILING_FORMS_LINE, keeps its wording. tests/e2e/reflow-200.spec.ts holds the landing's rows to it
 * on the built page.
 */
export default function FormCodeText({ text }: { text: string }) {
  return (
    <>
      {text.split(FORM_CODE).map((part, index) =>
        index % 2 === 1 ? (
          <span key={index} className="whitespace-nowrap">
            {part}
          </span>
        ) : (
          <Fragment key={index}>{part}</Fragment>
        ),
      )}
    </>
  )
}
