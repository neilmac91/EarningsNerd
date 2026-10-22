import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { ESLint, RuleTester } from 'eslint'
import { describe, expect, it } from 'vitest'
import {
  DIALOG_WELL_STEP,
  drawsFrame,
  ELEMENT_FACTORY_ALLOWLIST,
  elementsBuiltWithJsx,
  fourUpGrid,
  LANDING_GRID_FILES,
  localePinnedNumbers,
  noFormCodeBadge,
  noFourUpGrid,
  noHandRolledToggleGroup,
  noSideStripe,
  noUnguardedAnimation,
  SELF_GUARDED_ANIMATIONS,
  sideStripe,
  SURFACE_STEP,
  surfacePaddingCap,
  templateTrackCount,
  uncappedInset,
  undefinedCap,
  unguardedAnimation,
} from '../../eslint.designRules.mjs'

/**
 * Pins the 2026-10 critique's design gates (eslint.designRules.mjs):
 *  - no-side-stripe (P-08): a thick left border on a rounded container is the side-tab stripe card.
 *    Evaluated on whole class strings, so a stripe split across template chunks or cx() arguments
 *    is caught, while a quotation's unrounded 2px bar and the Callout's full hairline pass.
 *  - no-four-up-grid (D-045): the landing lays nothing out four across. A token that sets four column tracks or
 *    more, under any variant, fails: grid-cols-N with N of 4 or more, an arbitrary template or grid shorthand whose
 *    tracks count to 4 or more (repeat() counted out, line names not; the shorthand's columns after its slash), a
 *    template the width or a variable decides, a column flow, and CSS multi-column by its count or column width.
 *    It runs on the landing's own files only (LANDING_GRID_FILES), never on the product screens the landing demos.
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
 *  - surface-padding-cap (E120): under enlarged text a surface's inset stops growing at narrow widths, so a Card, a
 *    Modal's panel, a frame (a full border and a radius), the Card's and the dialog's sections, a native <dialog>'s
 *    sections and what is written directly inside a Card, a Modal or a frame whose class does not pad every render
 *    (no padding, p-0, padding set only under a condition or a variant, or reset under one) carry no padding of step
 *    5 or more that is not a capped token (p-cap-N, tailwind.config.js), and a frame inside a dialog's body none from
 *    step 4. A step is read by its resolved size (a configured key, an arbitrary length), a value the rule cannot
 *    read fails closed, a class a same-file binding holds is read with the attribute that names it, a Card or a
 *    section imported under another name is read as itself, a form field is never a frame, and a capped key the theme
 *    does not define fails anywhere. The shapes out of its reach are planted as stated gaps.
 *  - elements-built-with-jsx: the app builds its elements in JSX, which the gates that read elements see, so React's
 *    element factories are refused under any name (Codex's two forms on #1370's 44229515 among them), a use of React
 *    the rule cannot follow is refused as unreadable, and the DOM's document.createElement, JSX, a type and the one
 *    allowlisted file pass. Each allowlist entry is held to its file: set aside, the rule finds its factories there.
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

describe('fourUpGrid', () => {
  it('counts a template the way a browser lays it out: repeat() counted out, line names not', () => {
    expect(templateTrackCount('14rem_minmax(0,1fr)')).toBe(2)
    expect(templateTrackCount('repeat(4,minmax(0,1fr))')).toBe(4)
    expect(templateTrackCount('repeat(2,1fr_2fr)')).toBe(4)
    expect(templateTrackCount('[full-start]_1fr_[full-end]')).toBe(1)
    expect(templateTrackCount('auto_repeat(3,_1fr)')).toBe(4)
    expect(templateTrackCount('repeat(auto-fill,minmax(10rem,1fr))')).toBe(Infinity)
    expect(templateTrackCount('var(--cols)')).toBe(Infinity)
  })

  it('flags four tracks or more under any variant, at any breakpoint and on any element a variant styles', () => {
    expect(fourUpGrid('grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4')).toBe('lg:grid-cols-4')
    expect(fourUpGrid('grid grid-cols-4')).toBe('grid-cols-4')
    expect(fourUpGrid('md:grid-cols-6')).toBe('md:grid-cols-6')
    expect(fourUpGrid('[@media(min-width:48rem)]:grid-cols-[repeat(4,minmax(0,1fr))]')).toBe('[@media(min-width:48rem)]:grid-cols-[repeat(4,minmax(0,1fr))]')
    expect(fourUpGrid('lg:[grid-template-columns:1fr_1fr_1fr_1fr]')).toBe('lg:[grid-template-columns:1fr_1fr_1fr_1fr]')
    expect(fourUpGrid('lg:[&>div>dl]:!grid-cols-4')).toBe('lg:[&>div>dl]:!grid-cols-4')
    expect(fourUpGrid('grid-cols-[repeat(auto-fit,minmax(12rem,1fr))]')).toBe('grid-cols-[repeat(auto-fit,minmax(12rem,1fr))]')
    expect(fourUpGrid('grid-cols-(--landing-cols)')).toBe('grid-cols-(--landing-cols)')
    // The grid shorthands: the columns after the slash, or the cells of the first area string.
    expect(fourUpGrid('[grid-template:auto/repeat(4,1fr)]')).toBe('[grid-template:auto/repeat(4,1fr)]')
    expect(fourUpGrid('lg:[grid:auto-flow/1fr_1fr_1fr_1fr]')).toBe('lg:[grid:auto-flow/1fr_1fr_1fr_1fr]')
    expect(fourUpGrid("[grid-template:'a_b_c_d']")).toBe("[grid-template:'a_b_c_d']")
    // A column flow gives every item a column of its own.
    expect(fourUpGrid('grid grid-flow-col')).toBe('grid-flow-col')
    expect(fourUpGrid('[grid:auto/auto-flow]')).toBe('[grid:auto/auto-flow]')
    expect(fourUpGrid('[grid-auto-flow:column_dense]')).toBe('[grid-auto-flow:column_dense]')
    // CSS multi-column: a count of four or more, or a column width the container's width turns into a count.
    expect(fourUpGrid('columns-1 md:columns-4')).toBe('md:columns-4')
    expect(fourUpGrid('columns-xs')).toBe('columns-xs')
    expect(fourUpGrid('columns-[18rem]')).toBe('columns-[18rem]')
    expect(fourUpGrid('[column-count:5]')).toBe('[column-count:5]')
    expect(fourUpGrid('[columns:4_10rem]')).toBe('[columns:4_10rem]')
  })

  it('passes three tracks or fewer, and utilities that set no tracks of their own', () => {
    expect(fourUpGrid('grid grid-cols-1 [@media(min-width:40rem)]:grid-cols-2 lg:grid-cols-3')).toBeNull()
    expect(fourUpGrid('[@media(min-width:64rem)]:grid-cols-[14rem_minmax(0,1fr)]')).toBeNull()
    expect(fourUpGrid('lg:[&>div>dl]:grid-cols-3 grid-cols-[auto_1fr] grid-cols-none grid-cols-subgrid col-span-4 gap-4')).toBeNull()
    expect(fourUpGrid('[grid-template:auto/1fr_1fr] [grid:repeat(2,auto)/repeat(3,1fr)] [grid-template:none] grid-flow-row [grid-auto-flow:row]')).toBeNull()
    expect(fourUpGrid('columns-3 columns-auto [column-count:2] [columns:auto] [grid-template-rows:repeat(4,auto)]')).toBeNull()
  })
})

ruleTester.run('no-four-up-grid', noFourUpGrid, {
  valid: [
    '<dl className="grid grid-cols-1 gap-6 [@media(min-width:40rem)]:grid-cols-2" />',
    "<ol className={cx('grid grid-cols-1 sm:grid-cols-2', wide && 'lg:grid-cols-3')} />",
    // A span of four columns is not four columns.
    '<div className="col-span-4 lg:col-span-4" />',
    '<div className="grid [grid-template:auto/repeat(2,1fr)] columns-2" />',
  ],
  invalid: [
    { code: '<dl className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4 lg:gap-10" />', errors: [{ messageId: 'fourUp' }] },
    // Either arm of a ternary renders on some visit.
    { code: "<ul className={cx('grid grid-cols-1 sm:grid-cols-2', analysis ? 'lg:grid-cols-4' : 'lg:grid-cols-3')} />", errors: [{ messageId: 'fourUp' }] },
    // A template chunk, a class constant and an arbitrary template are read as class text.
    { code: '<div className={`grid ${gap} md:grid-cols-4`} />', errors: [{ messageId: 'fourUp' }] },
    { code: "const TILES = 'grid grid-cols-2 md:grid-cols-4'", errors: [{ messageId: 'fourUp' }] },
    { code: '<div className="grid grid-cols-1 lg:grid-cols-[repeat(4,minmax(0,1fr))]" />', errors: [{ messageId: 'fourUp' }] },
    // The grid shorthands and multi-column lay items out across as grid-cols does.
    { code: '<div className="grid [grid-template:auto/repeat(4,1fr)]" />', errors: [{ messageId: 'fourUp' }] },
    { code: '<div className="grid lg:[grid:auto-flow/repeat(4,minmax(0,1fr))]" />', errors: [{ messageId: 'fourUp' }] },
    { code: '<ul className="columns-2 lg:columns-4" />', errors: [{ messageId: 'fourUp' }] },
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

const CITATION_MARKERS = path.join(frontendRoot, 'lib/citationMarkers.tsx')
ruleTester.run('elements-built-with-jsx', elementsBuiltWithJsx, {
  valid: [
    // An element in JSX, and the DOM's own createElement, dotted, bracketed, optional or taken out by a pattern.
    'const field = <input type="password" autoComplete="new-password" />',
    "const link = document.createElement('a')",
    "const box = document?.['createElement']('div')",
    'const { createElement } = document',
    // A helper of the DOM's under the same name is no React factory.
    "const createElement = (tag) => document.createElement(tag)\nconst made = createElement('a')",
    // React's other members, imported, dotted or taken out of its default or a namespace import.
    "import React, { useState, Children } from 'react'\nconst [on] = useState(false)\nconst n = React.Children.count(kids) + Children.count(kids)\nconst { Fragment, memo } = React",
    "import * as R from 'react'\nR.useEffect(() => {}, [])",
    // The allowlisted file and its factory.
    { code: "import { cloneElement } from 'react'\nexport const marked = (el) => cloneElement(el, undefined, 'x')", filename: CITATION_MARKERS },
  ],
  invalid: [
    { code: "import { createElement } from 'react'", errors: [{ messageId: 'factory', data: { form: 'createElement, imported from react' } }] },
    // Codex on 44229515, passwordRulesLockstep: createElement under another name.
    {
      code: "import { createElement as h } from 'react'\nconst field = h('input', { type: 'password', autoComplete: 'off' })",
      errors: [{ messageId: 'factory', line: 1, data: { form: 'createElement, imported from react' } }],
    },
    { code: "import { 'cloneElement' as clone } from 'react'", errors: [{ messageId: 'factory', data: { form: 'cloneElement, imported from react' } }] },
    { code: "import { createFactory } from 'react'", errors: [{ messageId: 'factory' }] },
    // Codex on 44229515, notificationPreferencesConsumed: a member of React's default import.
    {
      code: "import React from 'react'\nconst row = React.createElement(Reader, { source: prefs })",
      errors: [{ messageId: 'factory', line: 2, data: { form: 'React.createElement' } }],
    },
    { code: "import * as R from 'react'\nR.cloneElement(el, { autoComplete: 'off' })", errors: [{ messageId: 'factory', data: { form: 'R.cloneElement' } }] },
    { code: "import React from 'react'\nReact['createElement']('input')", errors: [{ messageId: 'factory', data: { form: "React['createElement']" } }] },
    { code: "import React from 'react'\nReact[`cloneElement`](el)", errors: [{ messageId: 'factory' }] },
    { code: "import { default as React } from 'react'\nReact.createFactory('input')", errors: [{ messageId: 'factory' }] },
    { code: "import React from 'react'\nconst { createElement: h, useState } = React", errors: [{ messageId: 'factory', data: { form: 'createElement, taken out of React' } }] },
    // The JSX runtimes, whatever is taken from them; a re-export of a factory or of every export.
    { code: "import { jsx } from 'react/jsx-runtime'", errors: [{ messageId: 'factory', data: { form: 'An import from react/jsx-runtime' } }] },
    { code: "import * as dev from 'react/jsx-dev-runtime'", errors: [{ messageId: 'factory' }] },
    {
      code: "import { jsx } from 'react/cjs/react-jsx-runtime.production.js'",
      errors: [{ messageId: 'factory', data: { form: 'An import from react/cjs/react-jsx-runtime.production.js' } }],
    },
    { code: "export { cloneElement as clone } from 'react'", errors: [{ messageId: 'factory', data: { form: 'cloneElement, re-exported from react' } }] },
    { code: "export * from 'react'", errors: [{ messageId: 'factory' }] },
    // React at another entry, and the copy Next bundles.
    { code: "import { createElement } from 'react/index.js'", errors: [{ messageId: 'factory' }] },
    { code: "import { createElement } from 'next/dist/compiled/react'", errors: [{ messageId: 'factory' }] },
    // A createElement member or key whose object is not the DOM's global document, a document the file binds included.
    { code: "const el = ui.createElement('input')", errors: [{ messageId: 'factory', data: { form: 'ui.createElement' } }] },
    { code: "const el = kit?.['createElement']('input')", errors: [{ messageId: 'factory' }] },
    { code: "function make({ createElement }) { return createElement('input') }", errors: [{ messageId: 'factory' }] },
    { code: "function make(document) { return document.createElement('input') }", errors: [{ messageId: 'factory' }] },
    // A use of React whose reach the rule cannot tell.
    { code: "import React from 'react'\nconst R = React", errors: [{ messageId: 'unreadable', line: 2 }] },
    { code: "import React from 'react'\nrender(React)", errors: [{ messageId: 'unreadable', line: 2 }] },
    { code: "import React from 'react'\nReact[name]('input')", errors: [{ messageId: 'unreadable', data: { form: 'React[name], a member of React by a key held in a name' } }] },
    { code: "import React from 'react'\nconst { ...all } = React", errors: [{ messageId: 'unreadable', data: { form: '...all, taken out of React' } }] },
    { code: "export { default } from 'react'", errors: [{ messageId: 'unreadable' }] },
    { code: "const R = require('react')", errors: [{ messageId: 'unreadable', data: { form: "require('react'), a require of React" } }] },
    {
      code: "const { createElement: h } = await import('react')",
      errors: [{ messageId: 'factory', column: 9 }, { messageId: 'unreadable', data: { form: "import('react'), a dynamic import of React" } }],
    },
    // The allowlist names a file's factory, not every factory.
    { code: "import { createElement } from 'react'", filename: CITATION_MARKERS, errors: [{ messageId: 'factory' }] },
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

describe('uncappedInset', () => {
  it('reads a step by its resolved size, under any variant, important or not', () => {
    expect(uncappedInset('rounded-xl border p-6', SURFACE_STEP)).toEqual({ token: 'p-6', step: 6, fix: 'p-cap-6' })
    expect(uncappedInset('p-4 sm:p-6', SURFACE_STEP)).toEqual({ token: 'sm:p-6', step: 6, fix: 'sm:p-cap-6' })
    // The fix keeps the token's variants and its important mark.
    expect(uncappedInset('!pt-8', SURFACE_STEP)).toEqual({ token: '!pt-8', step: 8, fix: '!pt-cap-8' })
    expect(uncappedInset('md:!px-10', SURFACE_STEP)).toEqual({ token: 'md:!px-10', step: 10, fix: 'md:!px-cap-10' })
    // A configured key and an arbitrary length count by their size.
    expect(uncappedInset('p-gutter', SURFACE_STEP)).toEqual({ token: 'p-gutter', step: 6, fix: 'p-cap-6' })
    expect(uncappedInset('px-[20px]', SURFACE_STEP)).toEqual({ token: 'px-[20px]', step: 5, fix: 'px-cap-5' })
    // A step the theme defines no cap for, and a value the rule cannot read as a length.
    expect(uncappedInset('p-12', SURFACE_STEP)).toEqual({ token: 'p-12', step: 12, fix: null })
    expect(uncappedInset('pb-[calc(1rem+env(safe-area-inset-bottom))]', SURFACE_STEP)).toEqual({
      token: 'pb-[calc(1rem+env(safe-area-inset-bottom))]',
      step: null,
      fix: null,
    })
    // A frame inside a dialog's body caps from step 4.
    expect(uncappedInset('rounded-lg border p-4', DIALOG_WELL_STEP)).toEqual({ token: 'p-4', step: 4, fix: 'p-cap-4' })
  })

  it('passes a capped token, a step under the threshold and a token that styles another element', () => {
    expect(uncappedInset('p-cap-6 sm:p-cap-8 px-cap-5 scroll-py-6', SURFACE_STEP)).toBeNull()
    expect(uncappedInset('p-4 px-4.5 py-3.5 p-px', SURFACE_STEP)).toBeNull()
    expect(uncappedInset('p-3', DIALOG_WELL_STEP)).toBeNull()
    expect(uncappedInset('[&>div]:p-6 *:px-8', SURFACE_STEP)).toBeNull()
    // Not padding: a gap, a margin, a space or a scroll padding.
    expect(uncappedInset('gap-6 m-6 space-y-6 scroll-py-6', SURFACE_STEP)).toBeNull()
  })

  it('knows a frame by a full border and a radius, and a capped key the theme does not define', () => {
    expect(drawsFrame('rounded-xl border bg-panel-light')).toBe(true)
    expect(drawsFrame('sm:rounded-2xl border-2')).toBe(true)
    expect(drawsFrame('rounded-xl border-t')).toBe(false)
    expect(drawsFrame('border border-border-light')).toBe(false)
    expect(drawsFrame('rounded-none border')).toBe(false)
    // A zero-width border draws none.
    expect(drawsFrame('rounded-xl border-0')).toBe(false)
    expect(undefinedCap('p-cap-7')).toBe('p-cap-7')
    expect(undefinedCap('sm:px-cap-12')).toBe('sm:px-cap-12')
    // Scroll padding takes the same steps, and a variant that styles another element still ships the class unstyled.
    expect(undefinedCap('scroll-py-cap-7')).toBe('scroll-py-cap-7')
    expect(undefinedCap('[&>div]:p-cap-7')).toBe('[&>div]:p-cap-7')
    expect(undefinedCap('scroll-py-cap-6')).toBeNull()
    expect(undefinedCap('p-cap-6 px-cap-3')).toBeNull()
  })
})

ruleTester.run('surface-padding-cap', surfacePaddingCap, {
  valid: [
    '<Card className="p-cap-6" />',
    // A Card under step 5, and the KPI strip's two small steps.
    '<Card className="p-4" />',
    '<Card className="p-3 sm:p-4" />',
    '<div className="rounded-xl border bg-panel-light p-cap-5 shadow-e2" />',
    // Not a frame: a side border alone, a zero-width border, or no radius; a page gutter is no surface.
    '<header className="border-b px-6 py-4" />',
    '<div className="rounded-xl border-0 p-6" />',
    '<section className="mx-auto max-w-7xl px-6 py-12" />',
    // A Notice-sized frame and a field.
    '<div className="rounded-lg border px-4 py-3.5" />',
    '<ModalBody className="space-y-4" />',
    '<ModalBody><div className="rounded-lg border p-cap-4" /></ModalBody>',
    '<ModalBody><textarea className="rounded-lg border px-3 py-2" /></ModalBody>',
    // A form field is never a frame: its padding reserves room for a glyph, in a dialog's body or on a page.
    '<ModalBody><input className="rounded-lg border px-4 py-2" /></ModalBody>',
    '<input className="rounded-lg border pl-11 pr-3" />',
    // A frame outside a dialog's body keeps step 4.
    '<Card><div className="rounded-lg border p-4" /></Card>',
    // Out of reach (review-checked), planted as stated gaps: a token whose variant styles another element; a frame drawn
    // without a border utility; an object of recipes; a binding a ternary sets; a class through a helper other than
    // cx() or clsx(); a section of a surface that sets padding on one axis only.
    '<Card className="[&>div]:p-6" />',
    '<div className="rounded-xl bg-panel-light p-6 shadow-e2" />',
    "const S = { pad: 'p-6' }\nexport const x = <Card className={S.pad} />",
    "const PAD = wide ? 'p-6' : 'p-4'\nexport const x = <Card className={PAD} />",
    "export const x = <Card className={merge(cx('p-6'))} />",
    '<Card className="py-2"><div className="px-6" /></Card>',
    '<dialog className="rounded-2xl border p-0"><header className="border-b px-cap-5 py-4" /></dialog>',
    // A constant that draws no frame and sits on no surface.
    "const PAD = 'p-6'\nexport const x = <section className={PAD} />",
    'function ModalHeader() { return <div className="px-cap-6 pt-cap-6" /> }',
    // A surface that sets its own padding: what is written inside it is content, not its sections.
    '<Card className="p-cap-6"><div className="p-6" /></Card>',
    '<Card className="p-0"><div className="p-cap-6" /></Card>',
    // Padding under no variant pads every render.
    '<Card className="p-cap-4 sm:p-cap-6"><div className="px-6" /></Card>',
    // Bindings named in opposite arms render one or the other, never a padded frame (Codex's review of 82dd27ea).
    "const FRAME = 'rounded-xl border'\nconst PAD = 'p-6'\nexport const x = <div className={framed ? FRAME : PAD} />",
    // A binding named unconditionally pads every render, read where it is named.
    "const PAD = 'p-cap-6'\nexport const x = <Card className={cx(PAD, 'mt-6')}><div className=\"p-6\" /></Card>",
    // A binding is read each time it is named, so its unconditional read counts after a conditional one (Codex's review
    // of 310ec1f0).
    "const PAD = 'p-cap-6'\nexport const x = <Card className={cx(wide && PAD, PAD)}><div className=\"p-6\" /></Card>",
    '<section className="rounded-2xl border p-cap-6"><p className="px-6" /></section>',
    // A section of a surface that carries the cap, or a step under 5.
    '<Card><div className="px-4 pt-4 sm:px-cap-6 sm:pt-cap-6" /></Card>',
    '<Modal><div className="p-4" /></Modal>',
  ],
  invalid: [
    { code: '<Card className="p-6" />', errors: [{ messageId: 'uncapped', data: { token: 'p-6', surface: 'a Card', fix: 'p-cap-6', step: 6 } }] },
    { code: '<Card className="p-4 sm:p-6" />', errors: [{ messageId: 'uncapped' }] },
    { code: "<ui.Card className={cx('min-w-0 p-5', wide && 'md:col-span-2')} />", errors: [{ messageId: 'uncapped' }] },
    { code: '<Card className="!pt-8" />', errors: [{ messageId: 'uncapped' }] },
    { code: '<Card className="p-gutter" />', errors: [{ messageId: 'uncapped' }] },
    { code: '<Card className="p-[24px]" />', errors: [{ messageId: 'uncapped' }] },
    { code: '<Card className="p-12" />', errors: [{ messageId: 'noStep' }] },
    { code: '<Card className="p-[calc(1rem+2px)]" />', errors: [{ messageId: 'unreadable' }] },
    // The Card recipe copied by hand, a frame's branch, and a constant that draws a frame on its own.
    { code: '<div className="rounded-xl border bg-panel-light p-6 shadow-e2" />', errors: [{ messageId: 'uncapped' }] },
    { code: "<div className={cx('rounded-xl border', wide ? 'p-6' : 'p-4')} />", errors: [{ messageId: 'uncapped' }] },
    { code: "<div className={cx('p-6', framed && 'rounded-xl border')} />", errors: [{ messageId: 'uncapped' }] },
    { code: "const SHELL = 'rounded-2xl border p-8'", errors: [{ messageId: 'uncapped' }] },
    // A Card's class held in a same-file binding.
    { code: "const PAD = 'p-6'\nexport const x = <Card className={PAD} />", errors: [{ messageId: 'uncapped' }] },
    { code: "const PAD = cx('min-w-0', 'sm:p-8')\nexport const x = <Card className={cx(PAD, 'mt-6')} />", errors: [{ messageId: 'uncapped' }] },
    // The dialog's sections, at a call site and in their own source.
    { code: '<ModalBody className="px-8" />', errors: [{ messageId: 'uncapped' }] },
    { code: 'function ModalHeader() { return <div className="flex px-6 pt-6" /> }', errors: [{ messageId: 'uncapped' }] },
    { code: "const CardBody = forwardRef(function Body() { return <div className={cx('px-5 py-4')} /> })", errors: [{ messageId: 'uncapped' }] },
    // A frame inside a dialog's body caps from step 4, through a callback written there; a Card there too.
    { code: '<ModalBody><div className="rounded-lg border p-4" /></ModalBody>', errors: [{ messageId: 'uncapped' }] },
    { code: '<ModalBody>{rows.map((r) => <div key={r} className="rounded-lg border p-4" />)}</ModalBody>', errors: [{ messageId: 'uncapped' }] },
    { code: '<ModalBody><Card className="p-4" /></ModalBody>', errors: [{ messageId: 'uncapped' }] },
    // A native dialog's sections, and a frame in its body.
    { code: '<dialog className="rounded-2xl border p-0"><header className="border-b px-5 py-4" /></dialog>', errors: [{ messageId: 'uncapped' }] },
    { code: '<dialog><div className="px-3"><p className="rounded-lg border p-4" /></div></dialog>', errors: [{ messageId: 'uncapped' }] },
    // A Card, a Modal or a frame that sets no padding of its own leaves its inset to what is written directly inside it,
    // through a conditional and a callback written there.
    { code: '<Card><div className="p-5" /></Card>', errors: [{ messageId: 'uncapped' }] },
    { code: '<Card as="section">{open ? <div className="sm:px-6" /> : null}</Card>', errors: [{ messageId: 'uncapped' }] },
    // Through a fragment, written <> or as an element (Codex's review of 26ca7368): a keyed fragment in a map adds no box.
    { code: '<Card><><div className="p-6" /></></Card>', errors: [{ messageId: 'uncapped' }] },
    { code: '<Card><React.Fragment><div className="p-6" /></React.Fragment></Card>', errors: [{ messageId: 'uncapped' }] },
    { code: '<Card>{rows.map((row) => <Fragment key={row}><div className="px-5" /></Fragment>)}</Card>', errors: [{ messageId: 'uncapped' }] },
    { code: '<ModalBody><Fragment><div className="rounded-lg border p-4" /></Fragment></ModalBody>', errors: [{ messageId: 'uncapped' }] },
    // React's Fragment under another name (Codex's review of d113034f).
    { code: "import { Fragment as F } from 'react'\nexport const x = <Card><F><div className=\"p-6\" /></F></Card>", errors: [{ messageId: 'uncapped' }] },
    { code: '<section className="rounded-2xl border"><ul>{rows}</ul><p className="border-t px-6 py-3" /></section>', errors: [{ messageId: 'uncapped' }] },
    { code: '<Card className="divide-y">{rows.map((row) => <article key={row} className="p-4 sm:p-5" />)}</Card>', errors: [{ messageId: 'uncapped' }] },
    { code: '<Modal><div className="p-6" /></Modal>', errors: [{ messageId: 'uncapped' }] },
    // A surface reset to zero padding leaves its inset to them too (Codex's review of eee09cb8).
    { code: '<Card className="p-0"><div className="p-6" /></Card>', errors: [{ messageId: 'uncapped' }] },
    { code: '<Modal className="p-0"><div className="px-6" /></Modal>', errors: [{ messageId: 'uncapped' }] },
    { code: '<div className="rounded-xl border px-0 py-[0px]"><div className="px-5" /></div>', errors: [{ messageId: 'uncapped' }] },
    // Padding set only under a condition does not pad every render (Codex's reviews of 1efdf90f and af82fc10), through
    // a ternary, cx() or a binding named in one arm.
    { code: "<Card className={padded ? 'p-cap-6' : 'p-0'}><div className=\"p-6\" /></Card>", errors: [{ messageId: 'uncapped' }] },
    { code: "<div className={cx('rounded-xl border', open ? 'p-cap-5' : 'p-0')}><div className=\"px-5\" /></div>", errors: [{ messageId: 'uncapped' }] },
    { code: "const PAD = 'p-cap-6'\nexport const x = <Card className={padded && PAD}><div className=\"p-6\" /></Card>", errors: [{ messageId: 'uncapped' }] },
    // Padding under a variant pads only some renders (Codex's review of d113034f): below sm, on hover, in one theme.
    { code: '<Card className="sm:p-cap-6"><div className="px-6" /></Card>', errors: [{ messageId: 'uncapped' }] },
    { code: '<div className="rounded-xl border dark:p-cap-5"><div className="p-5" /></div>', errors: [{ messageId: 'uncapped' }] },
    // A key the theme does not define styles nothing, so it pads no render (Codex's review of a1866702).
    { code: '<Card className="p-typo"><div className="p-6" /></Card>', errors: [{ messageId: 'uncapped' }] },
    // A base inset reset to zero under a variant leaves it to the children there (Codex's review of 0c7a2f2b).
    { code: '<Card className="p-cap-6 sm:p-0"><div className="p-6" /></Card>', errors: [{ messageId: 'uncapped' }] },
    { code: '<div className="rounded-xl border p-cap-5 md:px-0"><div className="px-5" /></div>', errors: [{ messageId: 'uncapped' }] },
    // So does a reset in a conditional piece (Codex's review of 82dd27ea).
    { code: "<Card className={cx('p-cap-6', reset && 'sm:p-0')}><div className=\"p-6\" /></Card>", errors: [{ messageId: 'uncapped' }] },
    // A binding the collector does not walk to is read as text that is always there.
    { code: "const PAD = 'p-6'\nexport const x = <Card className={merge(PAD)} />", errors: [{ messageId: 'uncapped' }] },
    // A binding named in two arms is read in both: the second renders an uncapped frame (Codex's review of 310ec1f0).
    {
      code: "const SHELL = 'rounded-xl border'\nexport const x = <div className={wide ? cx(SHELL, 'p-4') : cx(SHELL, 'p-6')} />",
      errors: [{ messageId: 'uncapped' }],
    },
    // A binding that reads itself is read once, not without end.
    { code: "const SHELL = cx('rounded-xl border', SHELL)\nexport const x = <div className={cx(SHELL, 'p-6')} />", errors: [{ messageId: 'uncapped' }] },
    // A stated limit, failing closed: only unconditional padding pads every render, so a surface whose every arm pads it
    // still reads its children as sections; capping them is never wrong.
    { code: "<Card className={padded ? 'p-cap-6' : 'p-4'}><div className=\"p-6\" /></Card>", errors: [{ messageId: 'uncapped' }] },
    { code: "<div className={cx('rounded-xl border', wide ? 'p-cap-5' : 'p-cap-6')}><div className=\"p-6\" /></div>", errors: [{ messageId: 'uncapped' }] },
    // A Modal's className is its panel's.
    { code: '<Modal className="p-6" />', errors: [{ messageId: 'uncapped' }] },
    // A class a same-file binding holds is read with the attribute that names it, for a frame's border as for its padding.
    { code: "const PAD = 'p-6'\nexport const x = <div className={cx('rounded-xl border', PAD)} />", errors: [{ messageId: 'uncapped' }] },
    { code: "const SHELL = 'rounded-xl border bg-panel-light'\nexport const x = <div className={cx(SHELL, 'p-6')} />", errors: [{ messageId: 'uncapped' }] },
    { code: "const SHELL = 'rounded-xl border bg-panel-light'\nexport const x = <div className={`${SHELL} p-6`} />", errors: [{ messageId: 'uncapped' }] },
    { code: "const WELL = 'rounded-lg border p-4'\nexport const x = <ModalBody><div className={WELL} /></ModalBody>", errors: [{ messageId: 'uncapped' }] },
    // A Card or a section imported under another name, and a section declared through React.forwardRef or React.memo.
    { code: "import { Card as Panel } from '@/components/ui'\nexport const x = <Panel className=\"p-6\" />", errors: [{ messageId: 'uncapped' }] },
    { code: "import { ModalBody as Body } from '@/components/ui/Modal'\nexport const x = <Body className=\"px-8\" />", errors: [{ messageId: 'uncapped' }] },
    { code: "const CardBody = React.forwardRef(function Body() { return <div className=\"px-5\" /> })", errors: [{ messageId: 'uncapped' }] },
    { code: 'const ModalBody = React.memo(() => <div className="px-6" />)', errors: [{ messageId: 'uncapped' }] },
    // A stated limit, failing closed: a class constant read on its own cannot see the element it lands on, so one that
    // draws a field's frame beside a glyph inset of step 5 or more reads as a frame; the inset belongs on the field.
    { code: "const FIELD = 'rounded-lg border pr-9'\nexport const x = <select className={FIELD} />", errors: [{ messageId: 'noStep' }] },
    // The fix keeps the token's variants and its important mark.
    { code: '<Card className="sm:!p-6" />', errors: [{ messageId: 'uncapped', data: { token: 'sm:!p-6', surface: 'a Card', fix: 'sm:!p-cap-6', step: 6 } }] },
    // A capped key the theme does not define ships unstyled, on any element, as scroll padding or for another element.
    { code: '<span className="p-cap-7" />', errors: [{ messageId: 'undefinedCap' }] },
    { code: '<span className="scroll-py-cap-7" />', errors: [{ messageId: 'undefinedCap' }] },
    { code: '<span className="[&>div]:p-cap-7" />', errors: [{ messageId: 'undefinedCap' }] },
  ],
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

  const factoryFindings = (messages: ESLint.LintResult['messages']) =>
    messages.filter((m) => m.ruleId === 'earningsnerd/elements-built-with-jsx').map((m) => `${m.line} ${m.message.slice(0, m.message.indexOf(': '))}`)

  it('refuses an element factory on app code through the app parser, in TypeScript and JavaScript, and passes a type, the DOM and JSX (typescript-eslint)', async () => {
    const eslint = new ESLint({ cwd: frontendRoot })
    const [result] = await eslint.lintText(
      [
        "import React, { type ReactNode } from 'react'",
        "import type { createElement as Typed } from 'react'",
        "import { createElement as h } from 'react'",
        'export function Probe({ children }: { children: ReactNode }): React.ReactNode {',
        "  const made: ReturnType<typeof React.createElement> = h('input', { type: 'password', autoComplete: 'off' })",
        "  const link = (document as Document).createElement('a')",
        '  return <React.Fragment>{made}{(React as typeof React).cloneElement(<b />)}{link.href}{children}</React.Fragment>',
        '}',
        "import R = require('react')",
        'export type Made = Typed',
        "import * as Ns from 'react'",
        'import alias = Ns.createElement',
        'export const aliased = alias',
        '',
      ].join('\n'),
      { filePath: path.join(frontendRoot, 'app/element-factory-probe.tsx') },
    )
    expect(result.messages.filter((m) => m.fatal)).toEqual([])
    // A type-only import, a type, JSX, the import JSX makes typescript-eslint reference and the DOM behind a cast pass;
    // TypeScript's two import forms are read, `import x = require()` refused and `import x = Ns.member` as a member.
    expect(factoryFindings(result.messages)).toEqual([
      '3 createElement, imported from react',
      '7 (React as typeof React).cloneElement',
      "9 import R = require('react'), a require of React",
      '12 import alias = Ns.createElement',
    ])
    expect(result.messages.every((m) => m.ruleId !== 'earningsnerd/elements-built-with-jsx' || m.severity === 2)).toBe(true)
    // The password scan parses JavaScript too, so the rule reads it.
    const [script] = await eslint.lintText("import { createElement as h } from 'react'\nexport const field = h('input', { type: 'password' })\n", {
      filePath: path.join(frontendRoot, 'features/auth/components/element-factory-probe.jsx'),
    })
    expect(factoryFindings(script.messages)).toEqual(['1 createElement, imported from react'])
  })

  it('holds each allowlisted file to its factories: it passes as itself, and anywhere else the rule finds them there', async () => {
    const eslint = new ESLint({ cwd: frontendRoot })
    expect([...ELEMENT_FACTORY_ALLOWLIST.keys()]).toEqual(['lib/citationMarkers.tsx'])
    for (const [file, factories] of ELEMENT_FACTORY_ALLOWLIST) {
      const source = readFileSync(path.join(frontendRoot, file), 'utf8')
      const [own] = await eslint.lintText(source, { filePath: path.join(frontendRoot, file) })
      expect(factoryFindings(own.messages), file).toEqual([])
      const [elsewhere] = await eslint.lintText(source, { filePath: path.join(frontendRoot, path.dirname(file), 'element-factory-allowlist-probe.tsx') })
      expect(factoryFindings(elsewhere.messages).map((finding) => finding.split(',')[0].replace(/^\d+ /, '')), `${file} still needs its entry`).toEqual([...factories])
    }
  })

  it('runs surface-padding-cap as an error on app code', async () => {
    const eslint = new ESLint({ cwd: frontendRoot })
    const [result] = await eslint.lintText(
      [
        "import { Card } from '@/components/ui'",
        'export function Probe() {',
        '  return <Card className="p-6">Probe</Card>',
        '}',
        '',
      ].join('\n'),
      { filePath: path.join(frontendRoot, 'features/probe/components/Probe.tsx') },
    )
    expect(result.messages.map((m) => `${m.line} ${m.ruleId} ${m.severity}`)).toEqual(['3 earningsnerd/surface-padding-cap 2'])
  })

  it('runs no-four-up-grid on the landing\'s own files (LANDING_GRID_FILES) and on no product screen', async () => {
    const eslint = new ESLint({ cwd: frontendRoot })
    // A class constant, so the same probe parses as .ts and as .tsx.
    const probe = "export const TILES = 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4'\n"
    const rules = async (file: string) =>
      (await eslint.lintText(probe, { filePath: path.join(frontendRoot, file) }))[0].messages.map((m) => m.ruleId)
    expect(LANDING_GRID_FILES).toEqual([
      'app/page.tsx',
      'features/marketing/**/*.{ts,tsx}',
      'features/calendar/components/ReportingThisWeek.tsx',
      'features/filings/components/NotableFilings.tsx',
    ])
    for (const file of [
      'app/page.tsx',
      'features/marketing/components/Probe.tsx',
      'features/marketing/lib/probe.ts',
      'features/calendar/components/ReportingThisWeek.tsx',
      'features/filings/components/NotableFilings.tsx',
    ]) {
      expect(await rules(file), file).toEqual(['earningsnerd/no-four-up-grid'])
    }
    // The analysis page's KPI strip is four-up on its own page; the landing demos it inside a three-column override.
    for (const file of ['features/analysis/components/Probe.tsx', 'features/calendar/components/MonthView.tsx', 'app/pricing/page.tsx']) {
      expect(await rules(file), file).toEqual([])
    }
  })
})
