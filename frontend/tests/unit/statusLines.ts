/**
 * Readers for a status line a press fills (role="status"), for the specs that press a copy control:
 * inviteCopyConfirmations.spec.tsx and waitlistSuccessCard.spec.tsx. A repeat press empties the line, so the same words
 * are said again, and until the press says its words the line keeps the words it last said, aria-hidden and invisible,
 * so it holds its room (chief design on #1793).
 */

/** What a status line says: its text outside any aria-hidden part, which a screen reader does not hear. */
export function saidBy(line: HTMLElement): string {
  const walk = (node: Node): string =>
    node instanceof Element && node.getAttribute('aria-hidden') === 'true'
      ? ''
      : node.nodeType === Node.TEXT_NODE
        ? (node.textContent ?? '')
        : [...node.childNodes].map(walk).join('')
  return walk(line)
}

export type Change = { said: string; held: string; stray?: string }
/** Each change to a status line: what it says, and the words its box holds unsaid, in aria-hidden parts that are
    invisible too, so they keep their room and show nothing. Words in the box that are neither (an aria-hidden part that
    shows) are recorded as stray. A second press that says the same is seen emptied in between, its last words held. */
export function changesOf(line: HTMLElement): Change[] {
  const changes: Change[] = []
  new MutationObserver(() => {
    const said = saidBy(line)
    const held = [...line.querySelectorAll('[aria-hidden="true"].invisible')].map((part) => part.textContent ?? '').join('')
    const whole = line.textContent ?? ''
    changes.push(whole === said + held ? { said, held } : { said, held, stray: whole })
  }).observe(line, { childList: true, characterData: true, subtree: true })
  return changes
}

/** A press's words said, then emptied while their room is held, then said again. */
export const saidTwice = (words: string): Change[] => [{ said: words, held: '' }, { said: '', held: words }, { said: words, held: '' }]
