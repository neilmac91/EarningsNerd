/**
 * Planted forms for designSystemDoneGate.spec.ts's Source Voice Rule check (Newsreader sets only the filing's own
 * words: outside the reader, only a marked block, D-044): one component per form, each marked in the comment before
 * it. `flag` is a form the check must name; `clean` is a look-alike that must pass. The spec reads this file's strings
 * from its syntax tree and scores every form on every run. Outside the scan roots: the app scan never reads it.
 * Where a marked block may render (only on a passage the server located) is brandCopyRules.spec.ts rule 3's, with
 * its own forms (tests/unit/fixtures/brandRule3Forms.tsx).
 */
import { cx } from '@/components/ui'

const INK = 'text-text-primary-light dark:text-text-primary-dark'

/** V01 clean: a located quote's marked block in the filing's face. */
export function V01({ text }: { text: string }) {
  return <blockquote className={cx('en-marked px-3.5 py-2.5 font-editorial text-base leading-relaxed', INK)}>“{text}”</blockquote>
}

/** V02 flag: a quote the server did not locate, in the filing's face without the marked block. */
export function V02({ text }: { text: string }) {
  return <blockquote className="border-l-2 pl-3.5 font-editorial italic">“{text}”</blockquote>
}

/** V03 flag: the summary's own prose in the filing's face. */
export function V03({ text }: { text: string }) {
  return <p className="font-editorial leading-relaxed">{text}</p>
}

/** V04 flag: an Ask answer in the filing's face. */
export function V04({ answer }: { answer: string }) {
  return <div className="copilot-answer font-editorial text-sm">{answer}</div>
}

/** V05 flag: the reader's own class on another surface. */
export function V05({ text }: { text: string }) {
  return <div className="filing-reader">{text}</div>
}

/** V06 flag: the face's variable in an inline style. */
export function V06({ text }: { text: string }) {
  return <p style={{ fontFamily: 'var(--font-editorial)' }}>{text}</p>
}

/** V07 flag: the family by name. */
export function V07({ text }: { text: string }) {
  return <p style={{ fontFamily: 'Newsreader, serif' }}>{text}</p>
}

/** V08 clean: a selector that reads the reader and sets nothing. */
export function V08({ box }: { box: HTMLElement }) {
  return <span>{box.closest('.filing-reader') ? 'in the reader' : 'outside it'}</span>
}

/** V09 clean: a quote's speaker in the body face, inside a marked block. */
export function V09({ speaker }: { speaker: string }) {
  return <cite className="block font-sans text-sm not-italic">{speaker}</cite>
}

/** V10 clean: the word in copy is no face (a sentence that names the font). */
export function V10() {
  return <p>The filing reader sets the filing in Newsreader.</p>
}
