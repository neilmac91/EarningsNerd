/**
 * PB-02: what may never describe a complimentary private-beta grant's access. Nothing expires on a grant's review date
 * (docs/ops/complimentary-access.md, "End date"), so the surfaces that name the access, Settings › Billing and the
 * dashboard's plan card, say nothing of an end, a renewal, an expiry, a trial, a price, a date or a countdown: an end,
 * renewal or lapse word, "through" or "until", a trial or cancellation, "end date", a dollar sign, a year, a month's
 * name beside a day, a numeric day and month (slashed or dotted), or a count of days, weeks, months or years, in figures
 * ("60 days", "60-day") or in words ("two more months", "a year"). It is a list of forms, so a form it does not name
 * stays a review check. Read by BillingPanel.spec.tsx and
 * busyControls.dashboard.spec.tsx over each surface's whole text, as {@link endClaimTexts} gives it.
 */
const MONTH = '(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|' +
  'oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\\.?'
export const COMPLIMENTARY_END_CLAIM = new RegExp([
  '\\b(?:ends?|ending|ended|expir\\w*|until|till|through|thru|renew\\w*|trial|cancel\\w*|laps(?:e|es|ed|ing))\\b',
  'end date',
  '\\$',
  '\\b(?:19|20)\\d{2}\\b',
  `\\b${MONTH}\\s+\\d{1,2}(?:st|nd|rd|th)?\\b`,
  `\\b\\d{1,2}(?:st|nd|rd|th)?\\s+(?:of\\s+)?${MONTH}(?!\\w)`,
  '\\b\\d{1,2}[/.]\\d{1,2}\\b',
  '\\b\\d+[-\\s](?:days?|weeks?|months?|years?)\\b',
  '\\b(?:a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\\s+(?:more\\s+)?(?:days?|weeks?|months?|years?)\\b',
  '\\b(?:days?|weeks?|months?|years?)\\s+(?:left|remaining|to go)\\b',
].join('|'), 'i')

/** What the end-claim check reads of a surface: its textContent, where React's split of "{month}/{day}" into three text
    nodes still reads "12/31"; its {@link spacedText}, where one element's last word and the next's first stay apart
    ("Pro" and "Renews monthly"); and its aria-label and title values. Each misses what another holds, so the specs test
    all three. */
export function endClaimTexts(root: Element): string[] {
  // An accessible name or a tooltip is read aloud or shown too, though it is no text node.
  const attributes = [...root.querySelectorAll('[aria-label], [title]')]
    .flatMap((el) => [el.getAttribute('aria-label'), el.getAttribute('title')])
    .filter((value): value is string => Boolean(value))
  return [root.textContent ?? '', spacedText(root), attributes.join(' ')]
}

/** A surface's text with a space between its text nodes, as a reader hears it: textContent runs the last word of one
    element into the first of the next ("Pro" and "Renews monthly" read "ProRenews"), which a word's \b misses. */
export function spacedText(root: Element): string {
  const SHOW_TEXT = 4
  const walker = root.ownerDocument.createTreeWalker(root, SHOW_TEXT)
  const parts: string[] = []
  for (let node = walker.nextNode(); node; node = walker.nextNode()) parts.push(node.textContent ?? '')
  return parts.join(' ')
}
