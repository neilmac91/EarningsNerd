import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { ESLint, RuleTester } from 'eslint'
import { describe, expect, it } from 'vitest'
import {
  localePinnedNumbers,
  noFormCodeBadge,
  noHandRolledToggleGroup,
  noSideStripe,
  noUnguardedAnimation,
  SELF_GUARDED_ANIMATIONS,
  sideStripe,
  unguardedAnimation,
} from '../../eslint.designRules.mjs'

/**
 * Pins the 2026-10 critique's design gates (eslint.designRules.mjs):
 *  - no-side-stripe (P-08): a thick left border on a rounded container is the side-tab stripe card.
 *    Evaluated on whole class strings, so a stripe split across template chunks or cx() arguments
 *    is caught, while a quotation's unrounded 2px bar and the Callout's full hairline pass.
 *  - no-form-code-badge (P-04): a form code is text in the data face, never a <Badge> or a hand-rolled eyebrow chip.
 *  - no-unguarded-animation (P-09): every animation utility stops under reduced motion, through
 *    motion-safe: or a motion-reduce:animate-none with the same variants that always renders with it.
 *    The globals.css classes it exempts must stop themselves there, and so must every other animation
 *    globals.css declares.
 *  - locale-pinned-numbers: a number is formatted in en-US (lib/format's helpers, or the literal 'en-US'),
 *    never the browser's and never another locale, a variable included; lib/format.ts, which owns the
 *    formatters, is read too (its cache pins en-US).
 *  - the raw-colour selector (eslint.config.mjs DESIGN_HEX_RULE, BG-19) reads rgb[a]()/hsl[a]() in either
 *    case as well as a 6-digit hex, in a string, a template chunk or an arbitrary utility, and a 3- or 4-digit
 *    hex where it can only be a colour: inside an arbitrary utility or as the whole literal.
 *  - no-hand-rolled-toggle-group (CO-15): a role="group" of aria-pressed buttons is the SegmentedControl,
 *    composed from components/ui, never rebuilt in a feature (the primitive's own file is exempt). The pressed
 *    button is read in the group's own markup, through a same-file wrapper component (one level) and through
 *    the DS Button imported under another name; an imported wrapper and a wrapper of a wrapper stay unread.
 */

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')

describe('sideStripe', () => {
  it('flags a thick start border together with any rounding', () => {
    expect(sideStripe('rounded-r-lg border-l-4 shadow-e1')).toBe('border-l-4')
    expect(sideStripe('border-l-2 rounded-xl')).toBe('border-l-2')
    expect(sideStripe('border-s-8 rounded')).toBe('border-s-8')
    expect(sideStripe('dark:border-l-4 md:rounded-lg')).toBe('dark:border-l-4')
    expect(sideStripe('border-l-[3px] rounded-md')).toBe('border-l-[3px]')
  })

  it('passes a bar without rounding, a full hairline, and a hairline-width left border', () => {
    expect(sideStripe('border-l-2 border-border-light pl-3.5')).toBeNull()
    expect(sideStripe('rounded border border-border-light bg-panel-light')).toBeNull()
    expect(sideStripe('border-l rounded-lg')).toBeNull()
    expect(sideStripe('border-l-4 rounded-none')).toBeNull()
    expect(sideStripe('border-l-4 rounded-l-none')).toBeNull()
  })
})

RuleTester.describe = describe
RuleTester.it = it
RuleTester.itOnly = it.only

const ruleTester = new RuleTester({
  languageOptions: { ecmaVersion: 'latest', sourceType: 'module', parserOptions: { ecmaFeatures: { jsx: true } } },
})

ruleTester.run('no-side-stripe', noSideStripe, {
  valid: [
    '<blockquote className="border-l-2 border-border-light pl-3.5" />',
    '<div className="rounded border border-border-light bg-panel-light px-4 py-3.5" />',
    "<div className={cx('rounded-lg', quote && 'border-t')} />",
    // Siblings never combine: the stripe and the rounding are on different branches.
    "<div className={cx(a ? 'border-l-4' : 'rounded-xl')} />",
    // A hairline-width border on a Card is a divider, not a stripe; a stripe on an unrounded element passes.
    '<Card className="border-l p-4" />',
    '<Section className="border-l-4 p-4" />',
  ],
  invalid: [
    { code: '<div className="rounded-r-lg border-l-4 shadow-e1" />', errors: [{ messageId: 'stripe' }] },
    // Template chunks are one class string.
    { code: '<div className={`border-l-4 ${tone} border-r rounded-xl p-4`} />', errors: [{ messageId: 'stripe' }] },
    // Helper arguments are one class string, and a branch sees the text that is always there.
    { code: "<div className={cx('rounded-xl p-4', flagged && 'border-l-4')} />", errors: [{ messageId: 'stripe' }] },
    // A class constant is checked on its own.
    { code: "const CARD = 'border-l-8 rounded-lg'", errors: [{ messageId: 'stripe' }] },
    // Card rounds itself (its recipe sets the radius), so the stripe alone is the stripe card.
    { code: '<Card className="border-l-4 border-l-warning-light p-4" />', errors: [{ messageId: 'stripe' }] },
    { code: "<ui.Card className={cx('p-4', flagged && 'border-l-4')} />", errors: [{ messageId: 'stripe' }] },
  ],
})

ruleTester.run('no-form-code-badge', noFormCodeBadge, {
  valid: [
    '<Badge variant="brand">Full summary</Badge>',
    '<span className="font-data font-semibold">{filing.filing_type}</span>',
    '<Badge variant="warning">Partial</Badge>',
    // Descriptive props may name the form: they describe the badge, they are not its content.
    '<Badge variant="warning" title={`Amends the ${filing.filing_type}`}>Superseded</Badge>',
    '<Badge aria-label={`${filing.form_type} superseded`}>Superseded</Badge>',
    // Props that neither display nor style the badge are not its content (the review's case): React's key and ref, an
    // event handler, a data attribute and an id, on the badge or on an element inside it.
    '<Badge key={filing.form}>Current</Badge>',
    '<Badge ref={refs[filing.form]}>Current</Badge>',
    '<Badge onClick={() => open(filing.form)}>Current</Badge>',
    '<Badge data-form={filing.form}>Current</Badge>',
    '<Badge id={`badge-${filing.form}`}>Current</Badge>',
    '<Badge><span key={hit.form}>Current</span></Badge>',
    // The data face is the form code's place; eyebrow type on a label that is not a form passes.
    '<span className="font-data text-text-primary-light">{hit.form}</span>',
    '<span className="uppercase tracking-eyebrow text-text-tertiary-light">Revenue</span>',
    // The form is not the first child: a sentence that names the form is copy, not a chip.
    '<span className="uppercase tracking-eyebrow">Latest {filing.filing_type}</span>',
    '<p className="uppercase tracking-eyebrow">Filed {ago} with the {filing.form}</p>',
    '<span className="uppercase tracking-eyebrow">10-K filings this week</span>',
    // A nested wrapper that resets the recipe sets the code in a face of its own, and a component inside the
    // wrapper is judged by its own rule.
    '<p className="uppercase tracking-eyebrow"><span className="normal-case tracking-normal font-data">{filing.form}</span> · Filed {ago}</p>',
    '<span className="uppercase tracking-eyebrow"><Eyebrow>{form}</Eyebrow></span>',
    // Sibling wrappers whose lead is a word, not a form, are copy.
    '<span className="uppercase tracking-eyebrow"><span>Latest</span> <span>{filing.form}</span></span>',
    // A reset on every path of the class value sets a face of its own: both arms of a conditional, a cx() argument.
    "<span className=\"uppercase tracking-eyebrow\"><span className={plain ? 'normal-case tracking-normal' : 'normal-case'}>{form}</span></span>",
    "<span className=\"uppercase tracking-eyebrow\"><span className={cx('normal-case', size)}>{form}</span></span>",
    // Each path needs a reset, not the same one: one half of the recipe cancelled on each path.
    "<span className=\"uppercase tracking-eyebrow\"><span className={plain ? 'normal-case' : 'tracking-normal'}>{form}</span></span>",
    "<span className=\"uppercase tracking-eyebrow\"><span className={cx(plain ? 'normal-case' : 'tracking-normal', 'font-data')}>{form}</span></span>",
    "const CASE = 'normal-case'\nexport const C = ({ form }) => <span className=\"uppercase tracking-eyebrow\"><span className={CASE || 'tracking-normal'}>{form}</span></span>",
    // A bracket read of a field that is not a form is copy.
    "<span className=\"uppercase tracking-eyebrow\">{hit['title']}</span>",
    // A conditional whose arms both render a word leads on every path, and so does a fallback to a word.
    "<span className=\"uppercase tracking-eyebrow\">{label || 'Latest'} {form}</span>",
    "<span className=\"uppercase tracking-eyebrow\">{isNew ? 'New' : 'Latest'} {form}</span>",
    // A `??` whose left can only be null or undefined when it is empty falls to its right side, a word.
    "<span className=\"uppercase tracking-eyebrow\">{(isNew ? 'New' : null) ?? 'Latest'}{form}</span>",
    // A gap the rule's comment names: a left the scan cannot read is taken to render, as `{label}` is, so a `??` over
    // it passes though `label` may be '' (the review's case).
    "<span className=\"uppercase tracking-eyebrow\">{label ?? 'Latest'}{form}</span>",
    // A class helper's object form resets the face when the key's value is the literal true.
    "<span className=\"uppercase tracking-eyebrow\"><span className={cx({ 'normal-case tracking-normal': true })}>{form}</span></span>",
    // A helper's key whose value is falsy whatever runs never emits its class (the review's case, and the rest of the
    // family: null, 0, undefined, void, a falsy `&&`, a conditional with both arms falsy).
    "<span className={cx({ uppercase: false, 'tracking-eyebrow': false })}>{form}</span>",
    "<span className={cx({ uppercase: null, 'tracking-eyebrow': 0 })}>{form}</span>",
    "<span className={cx({ uppercase: undefined, 'tracking-eyebrow': true })}>{form}</span>",
    "<span className={cx({ uppercase: void 0, 'tracking-eyebrow': true })}>{form}</span>",
    "<span className={cx({ uppercase: dense && false, 'tracking-eyebrow': true })}>{form}</span>",
    "<span className={cx({ uppercase: dense ? false : '', 'tracking-eyebrow': true })}>{form}</span>",
    // The rest of the family a fixed truthiness decides (staticTruth): a negation of a value whose truthiness is fixed,
    // and an operand that never renders, the right of `&&` after a falsy left, of `||` and `??` after a truthy one, the
    // arm a fixed test never takes.
    "<span className={cx({ uppercase: !!0, 'tracking-eyebrow': true })}>{form}</span>",
    "<span className={cx({ uppercase: ![], 'tracking-eyebrow': true })}>{form}</span>",
    "<span className={cx(false && 'uppercase', 'tracking-eyebrow')}>{form}</span>",
    "<span className={cx('tracking-eyebrow', 'quiet' || 'uppercase')}>{form}</span>",
    "<span className={cx('tracking-eyebrow', 'quiet' ?? 'uppercase')}>{form}</span>",
    "<span className={cx('tracking-eyebrow', true ? 'font-medium' : 'uppercase')}>{form}</span>",
    // A reset a fixed truthiness guarantees is a reset on every path: a helper key truthy whatever runs, the arm a fixed
    // test takes, the right of `&&` after a truthy left, the side of `||` or `??` a fixed left decides.
    "<span className=\"uppercase tracking-eyebrow\"><span className={cx({ 'normal-case': 1 })}>{form}</span></span>",
    "<span className=\"uppercase tracking-eyebrow\"><span className={cx({ 'normal-case': !0 })}>{form}</span></span>",
    "<span className=\"uppercase tracking-eyebrow\"><span className={true ? 'normal-case' : ''}>{form}</span></span>",
    "<span className=\"uppercase tracking-eyebrow\"><span className={!0 && 'normal-case'}>{form}</span></span>",
    "<span className=\"uppercase tracking-eyebrow\"><span className={'' || 'normal-case'}>{form}</span></span>",
    "<span className=\"uppercase tracking-eyebrow\"><span className={'normal-case' ?? plain}>{form}</span></span>",
    // An important reset is a reset.
    '<span className="uppercase tracking-eyebrow"><span className="!normal-case !tracking-normal">{form}</span></span>',
    // Either half of the recipe reset is a reset, in any of its forms: another text-transform (the review's case
    // `lowercase`, and `capitalize`), an arbitrary letter-spacing with a decimal, and the arbitrary properties.
    '<span className="uppercase tracking-eyebrow"><span className="lowercase">{form}</span></span>',
    '<span className="uppercase tracking-eyebrow"><span className="capitalize">{form}</span></span>',
    '<span className="uppercase tracking-eyebrow"><span className="tracking-[0.02em]">{form}</span></span>',
    '<span className="uppercase tracking-eyebrow"><span className="[text-transform:none]">{form}</span></span>',
    '<span className="uppercase tracking-eyebrow"><span className="[letter-spacing:0]">{form}</span></span>',
    // A same-file binding's reset is read by its class-shaped initializer, in every branch that reads it.
    "const RESET = 'normal-case'\nexport const C = ({ form, dense }) => <span className=\"uppercase tracking-eyebrow\"><span className={dense ? RESET : cx(RESET, 'font-data')}>{form}</span></span>",
    "const PLAIN = 'normal-case tracking-normal'\nexport const Code = ({ form }) => <span className=\"uppercase tracking-eyebrow\"><span className={PLAIN}>{form}</span></span>",
    // A component is judged by its own rule (Badge above), not as a hand-rolled chip.
    '<Eyebrow className="uppercase tracking-eyebrow">{form}</Eyebrow>',
    // A same-file class binding is read as an inline class is: one that is not the eyebrow recipe passes
    // around a form, and the eyebrow recipe passes on a label that is not a form (FinancialMetricsTable's <dt>).
    "const DATA = 'font-data text-text-primary-light'\nexport const Code = ({ filing }) => <span className={DATA}>{filing.form}</span>",
    "const EYEBROW = 'text-xs uppercase tracking-eyebrow'\nexport const Label = () => <dt className={EYEBROW}>Change</dt>",
    // Prose that opens with an insider form's name is copy, as it is for a numbered code.
    '<p className="uppercase tracking-eyebrow">Form 4 filings this week</p>',
    // The letters after a dash are each form family's own: a span of years or a rank is not a form.
    '<span className="uppercase tracking-eyebrow">10-year</span>',
    // A hyphen joined to the code is a word, and a possessive is prose, not a separator.
    '<span className="uppercase tracking-eyebrow">S-1-style disclosures</span>',
    "<p className=\"uppercase tracking-eyebrow\">10-K's cover page</p>",
    '<Badge>Top 10</Badge>',
    // A model name is not a form: F-150 reads past the range.
    '<Badge>F-150</Badge>',
    // Each periodic family pairs its own number and letter: 40-K, 20-Q and 11-F are no form EDGAR writes.
    '<Badge>40-K</Badge>',
    '<Badge>20-Q</Badge>',
    '<span className="uppercase tracking-eyebrow">11-F</span>',
  ],
  invalid: [
    { code: '<Badge variant="neutral">{filing.filing_type}</Badge>', errors: [{ messageId: 'badge' }] },
    // A prop that displays or styles the badge still counts: its variant, class, style or icon read from the form, and
    // the children beside a handler and a data attribute.
    { code: "<Badge variant={filing.form === '10-Q' ? 'info' : 'neutral'}>Current</Badge>", errors: [{ messageId: 'badge' }] },
    { code: '<Badge className={TONE[filing.form]}>Current</Badge>', errors: [{ messageId: 'badge' }] },
    { code: '<Badge style={{ color: COLOR[hit.form] }}>Current</Badge>', errors: [{ messageId: 'badge' }] },
    { code: '<Badge icon={<b>{filing.form}</b>}>Current</Badge>', errors: [{ messageId: 'badge' }] },
    { code: '<Badge onClick={open} data-x="y">{filing.form}</Badge>', errors: [{ messageId: 'badge' }] },
    // The insider forms are written as words (the search's "Form 4" chip sends `4`): a code to this rule too.
    { code: '<Badge>Form 4</Badge>', errors: [{ messageId: 'badge' }] },
    { code: '<span className="uppercase tracking-eyebrow">Form 4</span>', errors: [{ messageId: 'chip' }] },
    // The other families the product renders: the ownership filings the notable-filing card shows, a fund's holdings report.
    { code: '<span className="uppercase tracking-eyebrow">SC 13D</span>', errors: [{ messageId: 'chip' }] },
    { code: '<Badge>13F-HR</Badge>', errors: [{ messageId: 'badge' }] },
    { code: '<span className="uppercase tracking-eyebrow">{"SC 13D/A · Filed"} {ago}</span>', errors: [{ messageId: 'chip' }] },
    // The registration families read as ranges: S-6, F-10 and SF-3 are forms EDGAR writes.
    { code: '<span className="uppercase tracking-eyebrow">S-6</span>', errors: [{ messageId: 'chip' }] },
    // The lead read through nested HTML wrappers: uppercase and letter-spacing inherit, so the inner span is the chip.
    { code: '<span className="uppercase tracking-eyebrow"><span>{form}</span></span>', errors: [{ messageId: 'chip' }] },
    { code: '<p className="uppercase tracking-eyebrow"><span><b>{filing.form}</b></span> · Filed {ago}</p>', errors: [{ messageId: 'chip' }] },
    // Sibling HTML wrappers are read in place: the face inherits into each of them.
    { code: '<span className="uppercase tracking-eyebrow"><span>{form}</span><span> · Filed {ago}</span></span>', errors: [{ messageId: 'chip' }] },
    { code: '<p className="uppercase tracking-eyebrow">{filing.form}<span> · Filed {ago}</span></p>', errors: [{ messageId: 'chip' }] },
    // What follows the lead does not take the chip's face off it: a component, a reset sibling, an empty icon wrapper first.
    { code: '<div className="uppercase tracking-eyebrow">{filing.form}<Badge>New</Badge></div>', errors: [{ messageId: 'chip' }] },
    { code: '<p className="uppercase tracking-eyebrow">{filing.form}<span className="normal-case tracking-normal">filed today</span></p>', errors: [{ messageId: 'chip' }] },
    { code: '<span className="uppercase tracking-eyebrow"><i className="h-3 w-3" />{form}</span>', errors: [{ messageId: 'chip' }] },
    // A reset under a variant leaves the face on in the other branch (a phone, the light theme), and wrappers
    // are read at any depth.
    { code: '<span className="uppercase tracking-eyebrow"><span className="sm:normal-case">{form}</span></span>', errors: [{ messageId: 'chip' }] },
    { code: '<span className="uppercase tracking-eyebrow"><span className="dark:tracking-normal">{form}</span></span>', errors: [{ messageId: 'chip' }] },
    // An uppercase transform written as an arbitrary property keeps the face, and a lowercase one under a variant does too.
    { code: '<span className="uppercase tracking-eyebrow"><span className="[text-transform:uppercase]">{form}</span></span>', errors: [{ messageId: 'chip' }] },
    { code: '<span className="uppercase tracking-eyebrow"><span className="sm:lowercase">{form}</span></span>', errors: [{ messageId: 'chip' }] },
    { code: '<span className="uppercase tracking-eyebrow"><span><span><span><span>{form}</span></span></span></span></span>', errors: [{ messageId: 'chip' }] },
    // A fragment renders its children in place.
    { code: '<span className="uppercase tracking-eyebrow"><>{form}</> · Filed {ago}</span>', errors: [{ messageId: 'chip' }] },
    // A reset on one path of the class value leaves the face on in the other; a blank expression is not the lead.
    { code: "<span className=\"uppercase tracking-eyebrow\"><span className={plain ? 'normal-case' : ''}>{form}</span></span>", errors: [{ messageId: 'chip' }] },
    { code: "<span className=\"uppercase tracking-eyebrow\"><span className={cx(plain && 'normal-case')}>{form}</span></span>", errors: [{ messageId: 'chip' }] },
    { code: "<span className=\"uppercase tracking-eyebrow\"><span className={size || 'normal-case'}>{form}</span></span>", errors: [{ messageId: 'chip' }] },
    // `??` keeps a left that is blank but not null or undefined (`false` from an `&&`, an empty arm): the form leads then.
    { code: "<span className=\"uppercase tracking-eyebrow\">{(isNew && 'New') ?? 'Latest'}{form}</span>", errors: [{ messageId: 'chip' }] },
    { code: "<span className=\"uppercase tracking-eyebrow\">{(plain ? '' : 'New') ?? 'Latest'}{form}</span>", errors: [{ messageId: 'chip' }] },
    { code: "const PLAIN = cx(plain && 'normal-case')\nexport const Code = ({ form }) => <span className=\"uppercase tracking-eyebrow\"><span className={PLAIN}>{form}</span></span>", errors: [{ messageId: 'chip' }] },
    { code: "<span className=\"uppercase tracking-eyebrow\">{' '}{form}</span>", errors: [{ messageId: 'chip' }] },
    // A class helper's object form names its classes by key, bare or quoted, inline or through a binding; a reset
    // keyed on a condition leaves the face on in the other branch.
    { code: "<span className={cx({ uppercase: true, 'tracking-eyebrow': true })}>{form}</span>", errors: [{ messageId: 'chip' }] },
    { code: "const EYEBROW = cx({ uppercase: true, 'tracking-eyebrow': active })\nexport const C = ({ form, active }) => <span className={EYEBROW}>{form}</span>", errors: [{ messageId: 'chip' }] },
    { code: "<span className=\"uppercase tracking-eyebrow\"><span className={cx({ 'normal-case': plain })}>{form}</span></span>", errors: [{ messageId: 'chip' }] },
    // A key whose value may be truthy keeps its class: an `||` or `??` with a side that may be truthy, a conditional with
    // an arm that may be, a negated falsy literal, an `&&` with no side always falsy, a template with an expression.
    { code: "<span className={cx({ uppercase: dense || false, 'tracking-eyebrow': true })}>{form}</span>", errors: [{ messageId: 'chip' }] },
    { code: "<span className={cx({ uppercase: dense ?? null, 'tracking-eyebrow': true })}>{form}</span>", errors: [{ messageId: 'chip' }] },
    { code: "<span className={cx({ uppercase: dense ? true : false, 'tracking-eyebrow': true })}>{form}</span>", errors: [{ messageId: 'chip' }] },
    { code: "<span className={cx({ uppercase: !0, 'tracking-eyebrow': true })}>{form}</span>", errors: [{ messageId: 'chip' }] },
    { code: "<span className={cx({ uppercase: dense && 'on', 'tracking-eyebrow': true })}>{form}</span>", errors: [{ messageId: 'chip' }] },
    { code: "<span className={cx({ uppercase: `${dense}`, 'tracking-eyebrow': true })}>{form}</span>", errors: [{ messageId: 'chip' }] },
    // An operand that may render keeps its class: the right of `&&` after a truthy left, of `||` after a falsy left or
    // one that may be, the arm a fixed test takes.
    { code: "<span className={cx(true && 'uppercase', 'tracking-eyebrow')}>{form}</span>", errors: [{ messageId: 'chip' }] },
    { code: "<span className={cx('tracking-eyebrow', false || 'uppercase')}>{form}</span>", errors: [{ messageId: 'chip' }] },
    { code: "<span className={cx('tracking-eyebrow', dense || 'uppercase')}>{form}</span>", errors: [{ messageId: 'chip' }] },
    { code: "<span className={cx('tracking-eyebrow', false ? 'font-medium' : 'uppercase')}>{form}</span>", errors: [{ messageId: 'chip' }] },
    // A reset a fixed truthiness leaves out on a path is no reset: a key falsy whatever runs, the arm a fixed test takes
    // without one, `??` after a falsy left that is never null or undefined.
    { code: "<span className=\"uppercase tracking-eyebrow\"><span className={cx({ 'normal-case': 0 })}>{form}</span></span>", errors: [{ messageId: 'chip' }] },
    { code: "<span className=\"uppercase tracking-eyebrow\"><span className={false ? 'normal-case' : ''}>{form}</span></span>", errors: [{ messageId: 'chip' }] },
    { code: "<span className=\"uppercase tracking-eyebrow\"><span className={'' ?? 'normal-case'}>{form}</span></span>", errors: [{ messageId: 'chip' }] },
    // A form field read by bracket notation is the field.
    { code: "<span className=\"uppercase tracking-eyebrow\">{hit['form']}</span>", errors: [{ messageId: 'chip' }] },
    { code: '<span className="uppercase tracking-eyebrow">{filing?.[`filing_type`]} · Filed {ago}</span>', errors: [{ messageId: 'chip' }] },
    // An expression that renders nothing on one path leaves the form leading there: a fallback to nothing too.
    { code: '<span className="uppercase tracking-eyebrow">{label || null}{form}</span>', errors: [{ messageId: 'chip' }] },
    { code: "<span className=\"uppercase tracking-eyebrow\">{note ?? ''}{filing.form} · Filed {ago}</span>", errors: [{ messageId: 'chip' }] },
    { code: "<span className=\"uppercase tracking-eyebrow\">{isNew && 'New · '}{form}</span>", errors: [{ messageId: 'chip' }] },
    { code: '<span className="uppercase tracking-eyebrow">{isNew ? <b>New</b> : null}{filing.form} · Filed {ago}</span>', errors: [{ messageId: 'chip' }] },
    // Tailwind 3's important modifier sets the same face, under a variant or not.
    { code: '<span className="!uppercase !tracking-eyebrow">{filing.form}</span>', errors: [{ messageId: 'chip' }] },
    { code: '<span className="sm:!uppercase tracking-eyebrow">{form} · Filed {ago}</span>', errors: [{ messageId: 'chip' }] },
    { code: '<Badge>F-10</Badge>', errors: [{ messageId: 'badge' }] },
    { code: '<span className="uppercase tracking-eyebrow">{"SF-3 · Filed"} {ago}</span>', errors: [{ messageId: 'chip' }] },
    // A meta line's separator may be a comma, a colon or semicolon, or a dash set off by a space, not only a middot.
    { code: '<span className="uppercase tracking-eyebrow">10-Q - Filed yesterday</span>', errors: [{ messageId: 'chip' }] },
    { code: '<span className="uppercase tracking-eyebrow">{"8-K, filed"} {ago}</span>', errors: [{ messageId: 'chip' }] },
    { code: '<p className="uppercase tracking-eyebrow">DEF 14A: Filed {ago}</p>', errors: [{ messageId: 'chip' }] },
    { code: '<p className="uppercase tracking-eyebrow">{`10-K – Filed ${ago}`}</p>', errors: [{ messageId: 'chip' }] },
    { code: '<Badge variant="neutral">{data.filingType}</Badge>', errors: [{ messageId: 'badge' }] },
    {
      code: "<Badge variant={/10-Q|6-K/i.test(filing.filing_type) ? 'info' : 'neutral'}>{form}</Badge>",
      errors: [{ messageId: 'badge' }],
    },
    { code: '<Badge>10-Q</Badge>', errors: [{ messageId: 'badge' }] },
    // The periodic families EDGAR writes, the transition forms among them.
    { code: '<Badge>10-QT</Badge>', errors: [{ messageId: 'badge' }] },
    { code: '<span className="uppercase tracking-eyebrow">11-KT</span>', errors: [{ messageId: 'chip' }] },
    { code: '<Badge>40-F</Badge>', errors: [{ messageId: 'badge' }] },
    { code: "<Badge>{'20-F/A'}</Badge>", errors: [{ messageId: 'badge' }] },
    // A form field by its short name, a template literal, and the member-expression spelling.
    { code: '<Badge>{f.form}</Badge>', errors: [{ messageId: 'badge' }] },
    { code: '<Badge>{`10-K`}</Badge>', errors: [{ messageId: 'badge' }] },
    { code: '<ui.Badge variant="neutral">{filing.filing_type}</ui.Badge>', errors: [{ messageId: 'badge' }] },
    // A hand-rolled chip: eyebrow type (uppercase, tracking-eyebrow) around a form field or a form code,
    // as the full-text search rows had it (audit SRCH-02).
    {
      code: '<span className="rounded border px-1.5 py-0.5 uppercase tracking-eyebrow">{hit.form}</span>',
      errors: [{ messageId: 'chip' }],
    },
    { code: '<span className={`uppercase ${tone} tracking-eyebrow`}>{filing?.filing_type}</span>', errors: [{ messageId: 'chip' }] },
    { code: "<div className={cx('uppercase', 'sm:tracking-eyebrow')}>10-K/A</div>", errors: [{ messageId: 'chip' }] },
    // The form leading a meta line, followed only by text or expressions: the notable-filing card had it.
    {
      code: '<div className="mt-1 text-xs uppercase tracking-eyebrow">\n  {filing.form}\n  {ago ? ` • Filed ${ago}` : \'\'}\n</div>',
      errors: [{ messageId: 'chip' }],
    },
    { code: '<span className="uppercase tracking-eyebrow">{/* code */}10-Q · Filed {ago}</span>', errors: [{ messageId: 'chip' }] },
    // The first child is read as a Badge's children are (formNode): a form field anywhere in the expression,
    // and a string that is a code or opens with one before a separator.
    { code: '<span className="uppercase tracking-eyebrow">{hit.form ?? "—"}</span>', errors: [{ messageId: 'chip' }] },
    { code: '<span className="uppercase tracking-eyebrow">{filing.form.toUpperCase()}</span>', errors: [{ messageId: 'chip' }] },
    { code: '<span className="uppercase tracking-eyebrow">{"10-Q · Filed"} {ago}</span>', errors: [{ messageId: 'chip' }] },
    // The eyebrow recipe held in a same-file binding, read through `className={EYEBROW}`, and one built with
    // cx() and read through a template.
    {
      code: "const EYEBROW = 'uppercase tracking-eyebrow'\nexport const Code = ({ filing }) => <span className={EYEBROW}>{filing.form}</span>",
      errors: [{ messageId: 'chip' }],
    },
    {
      code: "const EYEBROW = cx('text-xs uppercase', 'tracking-eyebrow')\nexport const Meta = ({ form, ago }) => <p className={`${EYEBROW} mt-1`}>{form} · Filed {ago}</p>",
      errors: [{ messageId: 'chip' }],
    },
  ],
})

ruleTester.run('no-hand-rolled-toggle-group', noHandRolledToggleGroup, {
  valid: [
    '<SegmentedControl label="Metric" value={metric} onChange={setMetric} options={options} />',
    // A group of plain actions (no pressed state) is not a toggle group.
    '<div role="group" aria-label="Recent period presets"><Button onClick={pick}>Last 4</Button></div>',
    // A lone toggle outside a group (the watchlist star, the alert bell).
    '<Button aria-pressed={on} onClick={toggle}>Watch</Button>',
    // The primitive builds the group itself.
    {
      code: '<div role="group" aria-label={label}>{options.map((o) => <button aria-pressed={o.value === value} />)}</div>',
      filename: '/repo/frontend/components/ui/SegmentedControl.tsx',
    },
    // A same-file wrapper that renders a plain button (no pressed state) is a group of actions.
    [
      'function Action({ onClick, children }) {',
      '  return <button type="button" onClick={onClick}>{children}</button>',
      '}',
      'const row = <div role="group" aria-label="Recent period presets"><Action onClick={pick}>Last 4</Action></div>',
    ].join('\n'),
    // A wrapper imported from another file is not read (one file at a time).
    "import { LabelToggle } from './LabelToggle'\nconst row = <div role=\"group\"><LabelToggle pressed /></div>",
    // One level: a wrapper that renders another wrapper is not followed into it.
    [
      'const Inner = ({ on }) => <button aria-pressed={on} />',
      'const Outer = ({ on }) => <Inner on={on} />',
      'const row = <div role="group"><Outer on /></div>',
    ].join('\n'),
    // The tag resolves through scopes: here <Toggle> is the parameter, not the same-file function.
    [
      'function Toggle({ on }) { return <button aria-pressed={on} /> }',
      'export function Row({ Toggle }) { return <div role="group"><Toggle on /></div> }',
    ].join('\n'),
  ],
  invalid: [
    // The company page's three rows: a mapped <button> with aria-pressed inside role="group".
    {
      code: '<div className="flex flex-wrap gap-2" role="group" aria-label="Select metric">{METRICS.map((m) => <button key={m.key} type="button" aria-pressed={m.key === metric}>{m.label}</button>)}</div>',
      filename: '/repo/frontend/features/peers/components/PeerComparisonPanel.tsx',
      errors: [{ messageId: 'handRolled' }],
    },
    // The DS Button, nested deeper, and role written as an expression.
    {
      code: "<section role={'group'}><span><Button aria-pressed={a}>A</Button><Button aria-pressed={!a}>B</Button></span></section>",
      errors: [{ messageId: 'handRolled' }],
    },
    { code: '<div role="group"><ui.Button aria-pressed="true">One</ui.Button></div>', errors: [{ messageId: 'handRolled' }] },
    // Only the SegmentedControl's own file is exempt, not its directory: another primitive rebuilding it fails.
    {
      code: '<div role="group" aria-label={label}>{options.map((o) => <button aria-pressed={o.value === value} />)}</div>',
      filename: '/repo/frontend/components/ui/FilterChips.tsx',
      errors: [{ messageId: 'handRolled' }],
    },
    // A same-file wrapper, a function declaration, returning the pressed button (WordingChanges' LabelToggle shape).
    {
      code: [
        'function LabelToggle({ pressed, onClick, children }) {',
        '  return (',
        '    <button type="button" aria-pressed={pressed} onClick={onClick}>',
        '      {children}',
        '    </button>',
        '  )',
        '}',
        'export function Row({ current, toggle }) {',
        '  return (',
        '    <div role="group" aria-label="Mark change">',
        "      {['reviewed', 'follow_up'].map((v) => <LabelToggle key={v} pressed={current === v} onClick={() => toggle(v)}>{v}</LabelToggle>)}",
        '    </div>',
        '  )',
        '}',
      ].join('\n'),
      errors: [{ messageId: 'handRolled', line: 10 }],
    },
    // A const arrow whose expression body is a conditional over the DS Button.
    {
      code: [
        'const Toggle = ({ on, label }) => (label ? <Button aria-pressed={on}>{label}</Button> : null)',
        'const row = <div role="group"><Toggle on label="A" /><Toggle label="B" /></div>',
      ].join('\n'),
      errors: [{ messageId: 'handRolled', line: 2 }],
    },
    // A const function expression: every return statement is read, a logical expression included.
    {
      code: [
        'const Toggle = function ({ on, label }) {',
        '  if (!label) return null',
        '  return on !== undefined && <button aria-pressed={on}>{label}</button>',
        '}',
        'const row = <div role="group"><Toggle on label="A" /></div>',
      ].join('\n'),
      errors: [{ messageId: 'handRolled', line: 5 }],
    },
    // React's own wrappers render the function they wrap.
    {
      code: [
        'const Toggle = memo(forwardRef(function Toggle({ on }, ref) { return <button ref={ref} aria-pressed={on} /> }))',
        'const row = <div role="group"><Toggle on /></div>',
      ].join('\n'),
      errors: [{ messageId: 'handRolled', line: 2 }],
    },
    // The DS Button imported under another name, from the barrel and from its own module.
    {
      code: "import { Button as B } from '@/components/ui'\nconst row = <div role=\"group\"><B aria-pressed={a}>A</B><B aria-pressed={!a}>B</B></div>",
      errors: [{ messageId: 'handRolled', line: 2 }],
    },
    {
      code: "import { Button as Choice } from '@/components/ui/Button'\nconst row = <div role=\"group\">{opts.map((o) => <Choice key={o} aria-pressed={o === v}>{o}</Choice>)}</div>",
      errors: [{ messageId: 'handRolled', line: 2 }],
    },
  ],
})

describe('unguardedAnimation', () => {
  it('passes motion-safe:, a same-variant guard, globals.css classes that guard themselves, and animate-none', () => {
    expect(unguardedAnimation('h-4 w-4 animate-spin motion-reduce:animate-none')).toBeNull()
    expect(unguardedAnimation('motion-safe:animate-content-in rounded-xl')).toBeNull()
    expect(unguardedAnimation('dark:motion-safe:animate-pulse')).toBeNull()
    expect(
      unguardedAnimation('[&>:last-child]:after:animate-pulse motion-reduce:[&>:last-child]:after:animate-none'),
    ).toBeNull()
    // motion-reduce may sit anywhere among the guard's variants; the others keep the animation's order.
    expect(unguardedAnimation('md:hover:animate-spin md:motion-reduce:hover:animate-none')).toBeNull()
    // An important guard covers a plain animation and an important one.
    expect(unguardedAnimation('animate-spin motion-reduce:!animate-none')).toBeNull()
    expect(unguardedAnimation('!animate-spin motion-reduce:!animate-none')).toBeNull()
    expect(unguardedAnimation('animate-fadeIn animate-check-pop animate-on-scroll animate-none')).toBeNull()
  })

  it('flags an animation with no guard, or a guard whose variants differ', () => {
    expect(unguardedAnimation('h-4 w-4 animate-spin')).toEqual({
      token: 'animate-spin',
      guard: 'motion-reduce:animate-none',
      safe: 'motion-safe:animate-spin',
    })
    // A variant raises specificity or moves the rule later, so the bare guard loses to it.
    expect(unguardedAnimation('dark:animate-pulse motion-reduce:animate-none')?.guard).toBe('motion-reduce:dark:animate-none')
    expect(unguardedAnimation('[&>:last-child]:after:animate-pulse motion-reduce:animate-none')?.token).toBe(
      '[&>:last-child]:after:animate-pulse',
    )
    expect(unguardedAnimation('animate-fade-up motion-safe:animate-none')?.token).toBe('animate-fade-up')
    expect(unguardedAnimation('!animate-shimmer')?.safe).toBe('motion-safe:!animate-shimmer')
    // An animation that runs only under reduced motion.
    expect(unguardedAnimation('motion-reduce:animate-bounce motion-reduce:animate-none')?.token).toBe('motion-reduce:animate-bounce')
  })

  it('flags a guard whose variants come in another order, or that is less important than the animation', () => {
    // Stacked selector variants compose in order, so this guard selects other elements.
    expect(
      unguardedAnimation('group-hover:peer-focus:animate-spin peer-focus:group-hover:motion-reduce:animate-none')?.guard,
    ).toBe('motion-reduce:group-hover:peer-focus:animate-none')
    expect(unguardedAnimation('hover:after:animate-pulse motion-reduce:after:hover:animate-none')?.token).toBe(
      'hover:after:animate-pulse',
    )
    // An !important animation wins the cascade over a plain guard.
    expect(unguardedAnimation('!animate-spin motion-reduce:animate-none')).toEqual({
      token: '!animate-spin',
      guard: 'motion-reduce:!animate-none',
      safe: 'motion-safe:!animate-spin',
    })
    expect(unguardedAnimation('md:!animate-spin motion-reduce:md:animate-none')?.guard).toBe('motion-reduce:md:!animate-none')
  })
})

ruleTester.run('no-unguarded-animation', noUnguardedAnimation, {
  valid: [
    '<CircleNotchIcon className="h-4 w-4 animate-spin motion-reduce:animate-none" />',
    '<div className="motion-safe:animate-fade-up" />',
    // The guard is always there around the branch that animates.
    "<div className={cx('motion-reduce:animate-none', streaming && 'animate-pulse')} />",
    "const CONTENT_IN = 'animate-content-in motion-reduce:animate-none'",
    '<div className="animate-check-pop" />',
  ],
  invalid: [
    { code: '<CircleNotchIcon className="h-8 w-8 animate-spin text-brand-strong" />', errors: [{ messageId: 'unguarded' }] },
    // A guard on one branch does not cover the animation that always renders.
    { code: "<div className={cx('animate-pulse', calm && 'motion-reduce:animate-none')} />", errors: [{ messageId: 'unguarded' }] },
    // Template chunks are one class string; the guard is missing from both.
    { code: '<form className={`animate-fade-up ${gap}`} />', errors: [{ messageId: 'unguarded' }] },
    // A class constant is checked on its own.
    { code: "const SPIN = 'animate-spin'", errors: [{ messageId: 'unguarded' }] },
  ],
})

ruleTester.run('locale-pinned-numbers', localePinnedNumbers, {
  valid: [
    "n.toLocaleString('en-US')",
    "n.toLocaleString('en-US', { maximumFractionDigits: 2 })",
    "new Intl.NumberFormat('en-US', { style: 'percent' })",
    // Without `new` it returns the same formatter, read the same way.
    "Intl.NumberFormat('en-US').format(n)",
    "new Intl.NumberFormat(['en-US'])",
    "d.toLocaleTimeString('en-US')",
    // Held by the date rule in eslint.config.mjs (every call, pinned or not), not reported twice.
    'd.toLocaleDateString()',
    "fmtCount(n)",
    // A computed member is not the method by name.
    'n[method]()',
  ],
  invalid: [
    { code: 'n.toLocaleString()', errors: [{ messageId: 'unpinned' }] },
    { code: 'Math.round(v).toLocaleString()', errors: [{ messageId: 'unpinned' }] },
    { code: 'value.toLocaleString(undefined, { maximumFractionDigits: 2 })', errors: [{ messageId: 'unpinned' }] },
    { code: 'new Intl.NumberFormat()', errors: [{ messageId: 'unpinned' }] },
    { code: 'new Date(t).toLocaleTimeString(undefined, { hour: "numeric" })', errors: [{ messageId: 'unpinned', data: { call: 'toLocaleTimeString()' } }] },
    { code: 'new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 })', errors: [{ messageId: 'unpinned' }] },
    // Called without `new`, and an empty locale list: both are the browser's own locale.
    { code: 'Intl.NumberFormat().format(n)', errors: [{ messageId: 'unpinned', data: { call: 'Intl.NumberFormat()' } }] },
    { code: 'new Intl.NumberFormat([])', errors: [{ messageId: 'unpinned', data: { call: 'new Intl.NumberFormat()' } }] },
    { code: 'Intl.NumberFormat([], { style: "percent" })', errors: [{ messageId: 'unpinned', data: { call: 'Intl.NumberFormat()' } }] },
    { code: 'n.toLocaleString([])', errors: [{ messageId: 'unpinned', data: { call: 'toLocaleString()' } }] },
    // Another locale, or one the rule cannot read (a variable, which may be the browser's): the product formats
    // in en-US alone.
    { code: "n.toLocaleString('de-DE')", errors: [{ messageId: 'other', data: { call: 'toLocaleString()', locale: "'de-DE'" } }] },
    { code: 'n.toLocaleString(locale)', errors: [{ messageId: 'other', data: { call: 'toLocaleString()', locale: 'locale' } }] },
    { code: "new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' })", errors: [{ messageId: 'other', data: { call: 'new Intl.NumberFormat()', locale: "'fr-FR'" } }] },
    { code: 'Intl.NumberFormat(navigator.language).format(n)', errors: [{ messageId: 'other', data: { call: 'Intl.NumberFormat()', locale: 'navigator.language' } }] },
    { code: "d.toLocaleTimeString(['en-GB'])", errors: [{ messageId: 'other', data: { call: 'toLocaleTimeString()', locale: "['en-GB']" } }] },
  ],
})

/** Every style rule in a stylesheet, with whether a `prefers-reduced-motion: reduce` query holds it. */
function cssRules(css: string, reduced = false): Array<{ selector: string; body: string; reduced: boolean }> {
  const rules: Array<{ selector: string; body: string; reduced: boolean }> = []
  const text = css.replace(/\/\*[\s\S]*?\*\//g, '')
  let i = 0
  while (i < text.length) {
    const open = text.indexOf('{', i)
    if (open < 0) break
    let depth = 1
    let close = open + 1
    for (; close < text.length && depth > 0; close++) {
      if (text[close] === '{') depth++
      else if (text[close] === '}') depth--
    }
    const prelude = text.slice(i, open).split(/[;}]/).pop()!.trim()
    const body = text.slice(open + 1, close - 1)
    if (prelude.startsWith('@media') || prelude.startsWith('@layer') || prelude.startsWith('@supports')) {
      rules.push(...cssRules(body, reduced || /prefers-reduced-motion:\s*reduce/.test(prelude)))
    } else if (!prelude.startsWith('@')) {
      rules.push({ selector: prelude, body, reduced })
    }
    i = close
  }
  return rules
}

describe('globals.css animations stop under reduced motion', () => {
  const rules = cssRules(readFileSync(path.join(frontendRoot, 'app/globals.css'), 'utf8'))
  const classes = (selector: string) => [...selector.matchAll(/\.([\w-]+)/g)].map((m) => m[1])
  const stopped = new Set(
    rules.filter((r) => r.reduced && /(animation|transition)\s*:\s*none/.test(r.body)).flatMap((r) => classes(r.selector)),
  )

  it('reads the stylesheet', () => {
    expect(rules.length).toBeGreaterThan(50)
    expect(stopped.size).toBeGreaterThan(0)
  })

  it('every class the rule exempts stops itself in a reduced-motion block', () => {
    expect([...SELF_GUARDED_ANIMATIONS].filter((name) => !stopped.has(name))).toEqual([])
  })

  it('every other animation it declares does too', () => {
    const animated = rules
      .filter((r) => !r.reduced && /(^|[;\s])animation(-name)?\s*:\s*(?!none)/.test(r.body))
      .flatMap((r) => classes(r.selector))
    expect(animated.length).toBeGreaterThan(0)
    expect(animated.filter((name) => !stopped.has(name))).toEqual([])
  })
})

/** Building ESLint from the real config takes 2-3.5s warm and over 7s cold or on a loaded runner; 5s is too tight. */
const SLOW = { timeout: 30_000 }

describe('the repository config', SLOW, () => {
  it('runs the four rules as errors on app code', async () => {
    const eslint = new ESLint({ cwd: frontendRoot })
    const [result] = await eslint.lintText(
      [
        "import { Badge } from '@/components/ui'",
        'export function Probe({ form, tone }: { form: { filing_type: string }; tone: string }) {',
        '  return (',
        '    <div className={`border-l-4 ${tone} rounded-xl p-4`}>',
        '      <Badge variant="neutral">{form.filing_type}</Badge>',
        '      <span className="animate-spin" />',
        '      <div role="group" aria-label="Window"><button type="button" aria-pressed={tone === "a"}>A</button></div>',
        '    </div>',
        '  )',
        '}',
        '',
      ].join('\n'),
      { filePath: path.join(frontendRoot, 'app/design-rules-probe.tsx') },
    )
    expect(result.messages.map((m) => m.ruleId).sort()).toEqual([
      'earningsnerd/no-form-code-badge',
      'earningsnerd/no-hand-rolled-toggle-group',
      'earningsnerd/no-side-stripe',
      'earningsnerd/no-unguarded-animation',
    ])
    expect(result.messages.every((m) => m.severity === 2)).toBe(true)
  })

  it('reads a raw colour in rgba()/hsla() in either case and an unpinned or other-locale number, time or date format on app code, and in lib/format.ts', async () => {
    const eslint = new ESLint({ cwd: frontendRoot })
    const probe = [
      'export function Probe({ n }: { n: number }) {',
      '  return (',
      '    <div className="shadow-e3 dark:shadow-[0_20px_50px_rgba(15,23,42,0.45)]">',
      '      <span style={{ color: `hsla(120, 20%, 40%, 0.5)` }}>{n.toLocaleString()}</span>',
      '      <time>{new Date(n).toLocaleTimeString()} {new Date(n).toLocaleDateString()}</time>',
      "      <i className=\"bg-[#fff]\" style={{ background: 'RGB(15 23 42)', fill: '#000a', outlineColor: `HSLA(120 20% 40% / 0.5)` }}>{n.toLocaleString('de-DE')}</i>",
      '      <b title="PR #619 and #abcd inside copy stay">{n}</b>',
      '      <u className="[color:#fff] [background:#000a] shadow-[0_0_0_1px_#abc]">{n}</u>',
      '    </div>',
      '  )',
      '}',
      '',
    ].join('\n')
    const [app] = await eslint.lintText(probe, { filePath: path.join(frontendRoot, 'app/design-rules-probe.tsx') })
    expect(app.messages.map((m) => `${m.line} ${m.ruleId}`).sort()).toEqual([
      '3 no-restricted-syntax',
      '4 earningsnerd/locale-pinned-numbers',
      '4 no-restricted-syntax',
      // A time through this rule, a date through the date rule: each call reported once.
      '5 earningsnerd/locale-pinned-numbers',
      '5 no-restricted-syntax',
      // A short hex in an arbitrary utility and as a whole literal, a colour function in capitals in a string
      // and in a template chunk, and a locale that is not en-US; a short hex inside copy (line 7) is not read.
      '6 earningsnerd/locale-pinned-numbers',
      '6 no-restricted-syntax',
      '6 no-restricted-syntax',
      '6 no-restricted-syntax',
      '6 no-restricted-syntax',
      // A short hex inside an arbitrary property or after a separator in an arbitrary value is a colour too.
      '8 no-restricted-syntax',
    ])
    // The formatter module is the one place a formatter is built and pins en-US itself, so the rule reads it
    // like any other file: a bare call added there fails.
    const [format] = await eslint.lintText('export const raw = (n: number) => n.toLocaleString()\n', {
      filePath: path.join(frontendRoot, 'lib/format.ts'),
    })
    expect(format.messages.map((m) => m.ruleId)).toEqual(['earningsnerd/locale-pinned-numbers'])
  })

  it('reads the eyebrow recipe behind `as const` or `satisfies` through the app parser (typescript-eslint)', async () => {
    const eslint = new ESLint({ cwd: frontendRoot })
    const [result] = await eslint.lintText(
      [
        "const EYEBROW = 'uppercase tracking-eyebrow' as const",
        "const META = 'text-xs uppercase tracking-eyebrow' satisfies string",
        "const DATA = 'font-data text-text-primary-light' as const",
        'export function Probe({ form, ago }: { form: string; ago: string }) {',
        '  return (',
        '    <>',
        '      <span className={EYEBROW}>{form}</span>',
        '      <p className={`${META} mt-1`}>{form} · Filed {ago}</p>',
        '      <span className={DATA}>{form}</span>',
        '    </>',
        '  )',
        '}',
        '',
      ].join('\n'),
      { filePath: path.join(frontendRoot, 'app/design-rules-probe.tsx') },
    )
    expect(result.messages.map((m) => `${m.line} ${m.ruleId}`)).toEqual(['7 earningsnerd/no-form-code-badge', '8 earningsnerd/no-form-code-badge'])
  })

  it('reads a same-file wrapper and the DS Button under another name through the app parser (typescript-eslint)', async () => {
    const eslint = new ESLint({ cwd: frontendRoot })
    const [result] = await eslint.lintText(
      [
        "import { Button as Choice } from '@/components/ui'",
        '',
        'function LabelToggle({ pressed, children }: { pressed: boolean; children: string }) {',
        '  return <button type="button" aria-pressed={pressed}>{children}</button>',
        '}',
        'const Pill = ({ on }: { on: boolean }) => (on ? <Choice aria-pressed>On</Choice> : null)',
        '',
        'export function Probe({ value }: { value: string }) {',
        '  return (',
        '    <>',
        "      <div role=\"group\" aria-label=\"Mark\">{['a', 'b'].map((v) => <LabelToggle key={v} pressed={v === value}>{v}</LabelToggle>)}</div>",
        "      <div role=\"group\" aria-label=\"Pick\"><Choice aria-pressed={value === 'a'}>A</Choice></div>",
        "      <div role=\"group\" aria-label=\"Pill\"><Pill on={value === 'b'} /></div>",
        '    </>',
        '  )',
        '}',
        '',
      ].join('\n'),
      { filePath: path.join(frontendRoot, 'app/toggle-group-probe.tsx') },
    )
    expect(result.messages.filter((m) => m.fatal)).toEqual([])
    expect(
      result.messages.filter((m) => m.ruleId === 'earningsnerd/no-hand-rolled-toggle-group').map((m) => m.line),
    ).toEqual([11, 12, 13])
  })
})
