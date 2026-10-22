// Design gates from the 2026-10 design critique (docs: frontend/DESIGN_SYSTEM.md §4 "Callout" and
// "Filing identity"), each pinned by tests/unit/designRules.spec.ts:
//
//   no-side-stripe      (P-08) A thick left border on a rounded container is the side-tab stripe
//                       card, the strongest generic tell the critique found. Callouts are inset wells
//                       (features/summaries/components/Callout.tsx) whose tone lives in the label
//                       word; a quotation keeps its 2px bar, but never with rounded corners. The rule
//                       evaluates whole class strings the way responsive-grid-base-track does (every
//                       helper argument and template chunk together, each conditional branch with the
//                       text that is always there around it), so `border-l-4 ${tone} … rounded-xl`
//                       is caught although no single literal holds both classes. A primitive that
//                       always rounds itself (Card) needs no rounded-* beside the stripe.
//   no-four-up-grid     (D-045) The landing page lays nothing out four across: every section after the
//                       hero is one ruled row (features/marketing/components/LandingRow.tsx), and the
//                       four-up stat strip and the four-up extras grid were the template skeleton tell T4
//                       names (docs/brand/09-stress-test.md §2). The rule fails a class token that sets
//                       four column tracks or more under any variant, at any breakpoint and on any element
//                       it styles: `grid-cols-N` with N of 4 or more, and an arbitrary template
//                       (`grid-cols-[…]`, `[grid-template-columns:…]`) or shorthand (`[grid-template:…]`,
//                       `[grid:…]`: the track list after the `/`, or the cells of the first area string)
//                       whose tracks count to 4 or more, a `repeat(N, …)` counted N times its tracks and a
//                       line name `[a]` not counted; a template whose count only the width decides
//                       (`repeat(auto-fill, …)`, `repeat(auto-fit, …)`) or the scan cannot read (`var(…)`)
//                       fails too, since it can open four, and so does a column flow (`grid-flow-col`,
//                       `[grid-auto-flow:column]`, the `grid` shorthand's `auto-flow` after its `/`), which
//                       gives every item a column of its own. CSS multi-column counts the same way:
//                       `columns-N` with N of 4 or more, `[columns:…]` and `[column-count:…]` by their
//                       count, and a column width (`columns-xs`, `columns-[18rem]`) as the width's count.
//                       It reads class strings as no-side-stripe does, a constant and a
//                       ternary's arm included. It runs on the landing's own composition only
//                       (LANDING_GRID_FILES below, eslint.config.mjs): the route, the marketing modules
//                       and the sections the route mounts from other features, which
//                       tests/unit/landing-sections-mounted.spec.ts holds to the route's imports. The
//                       product screens the landing demos keep their own layouts (KpiStrip is four-up on
//                       the analysis page). Outside it (review-checked): a four-across row built with flex
//                       (`basis-1/4`, `w-1/4`), a table of four columns or more, and a template set in an
//                       inline style or a stylesheet rather than a class.
//   no-form-code-badge  (P-04) A form code (the form families EDGAR writes, 10-K, 10-Q, 8-K, SC 13D,
//                       S-1, DEF 14A and their kin, FORM_CODES, and the insider forms the product
//                       writes as words, Form 3, Form 4 and Form 5) is text in the data face, never a
//                       Badge: a blue chip on 10-Q spent the status colour on a category, and a
//                       neutral one still reads as a status. The rule flags a <Badge> (or ui.Badge)
//                       that reads a filing-type field, or holds a literal form code (string,
//                       template or text), in its children or in a prop that styles it. Descriptive
//                       props (title, alt, aria-*) may name the form: they describe, not display; and
//                       a prop that neither displays nor styles (key, ref, an event handler, data-*,
//                       id) is not read.
//                       It flags a hand-rolled chip by the same reading: an HTML element whose class
//                       text sets uppercase and tracking-eyebrow, written inline or held in a binding
//                       declared in the same file (`const EYEBROW = 'uppercase tracking-eyebrow'`
//                       read as `className={EYEBROW}`; the initializer a string, a template or a
//                       cx()/clsx() call), and whose content, read through its HTML wrappers since
//                       uppercase and letter-spacing inherit (`<span>{form}</span>`, or sibling spans
//                       `<span>{form}</span><span> · Filed {ago}</span>`), opens with text or an
//                       expression that reads a form field anywhere in it (`{hit.form ?? fallback}`,
//                       `{filing.form.toUpperCase()}`) or holds a code, or text opening with one
//                       before a separator (a middot, bullet or pipe, a comma, colon or semicolon,
//                       or a dash set off by a space: `{'10-Q · Filed'}`, `10-Q - Filed`), as in
//                       `{form} • Filed {ago}`. A component, a Badge or an element that resets the
//                       face before the lead ends the reading (it is judged by its own rule or sets
//                       its own face); nothing after the lead takes the chip's face off it. A class
//                       a fixed truthiness rules out never counts (`cx({ uppercase: false })`,
//                       `cx(false && 'uppercase')`), and one it guarantees always does
//                       (`cx({ 'normal-case': 1 })`); any other string in the class counts.
//   direction-text-tokens (D-030, DESIGN.md "Separate Signals") A delta or a direction chip is text, so its ink
//                       is the 700-level direction token (text-gain-text / text-loss-text, the -dark pair in
//                       dark: lib/financialTone's directionText and directionChip), never the 600 level and
//                       never sage. The rule bans text-gain, text-gain-light, text-loss and text-loss-light
//                       under any variant (the 600s are graphic tones: 3.0:1 and 3.9:1 as text on their tints),
//                       except where the class is written on a graphic: an icon (any export of the icon
//                       modules, or a trend glyph as read below) or an SVG element that draws one (never `text`
//                       or `tspan`, which set type), whose text colour strokes and fills it through
//                       currentColor, the 600s' own use (3:1 for non-text); held in a binding or a map, the
//                       class is read as text. It also bans a text-brand-* class where it colours a direction
//                       glyph: on a TrendUpIcon or TrendDownIcon; on every element above it, reached through
//                       `{…}` children, ternaries, `&&` and fragments, up to the first whose classes give it an
//                       ink on every render (the ink the glyph inherits); or anywhere in a value of an object
//                       that pairs one with its classes (a direction map such as
//                       { Icon: TrendUpIcon, cls: '…' }, the value a literal, a cx() call or a ternary). An
//                       element gives the glyph its ink with a text colour that has no variant, in text that
//                       always renders or in both arms of a ternary, or with a class part the rule cannot read
//                       (a lookup such as directionChip[tone], a variable, another call), which may hold one. A
//                       text colour is `text-` and a colour token of tailwind.config.js's resolved theme, never
//                       a size (text-sm, text-data-xs), an alignment, a wrap or an overflow mode, so a layout
//                       or type wrapper passes the ink through, as does a colour set only under a variant
//                       (dark:, hover:, md:) or in one branch.
//                       A glyph is known by its spelling, its import and its bindings, read through ESLint's
//                       scopes: a name spelled TrendUpIcon or TrendDownIcon wherever it comes from; a binding
//                       an import from the icon modules makes (`import { TrendUpIcon as Up }`, Phosphor's
//                       unsuffixed `TrendUp`, a namespace whose trend members are glyphs: `<Ph.TrendUp />`,
//                       `{ Icon: icons.TrendUpIcon }`); and a binding of the file, which holds every value
//                       written to it (its initialiser, a default, a later assignment), read through an alias
//                       (`const Up = TrendUpIcon`, `const Up = Icons.TrendUpIcon`), a destructured member
//                       (`const { TrendUp: Up } = Ph`), a ternary's arms, a logical operand (the right of `&&`
//                       alone) and a lookup in an object or array literal, by its key or, for a key the scan
//                       cannot read, in every value: the what-changed chip's
//                       `const Icon = GLYPH[item.direction] ?? GLYPH.flat` then `<Icon />` is read so. The icon
//                       modules are `@/lib/icons`, by its alias or a path relative to the file, and the
//                       Phosphor package at any entry, as tests/unit/iconModules.ts reads them for the glyph
//                       and heading gates. A glyph re-exported through another app module, or a map of glyphs
//                       imported from one, is out of reach.
//                       Known limits: a glyph that reaches a binding from outside the file's writes (a
//                       parameter or a prop past its default, a loop variable, a call's result:
//                       `{xs.map((Icon) => <Icon />)}`, `const Icon = pick(d)`), a glyph returned from a
//                       callback (`{xs.map((x) => <TrendUpIcon />)}`: the walk up stops at the arrow function),
//                       and a glyph passed as a JSX prop (`icon={<TrendUpIcon />}`, valid by design: the
//                       element that draws it is elsewhere) are data-flow, out of scope as below. A delta or a
//                       figure in sage with no glyph (`+4.2%`, a chip's `{item.display}`) is not read here:
//                       tests/unit/brandCopyRules.spec.ts rule 2 (sage never colours a number, D-030) fails it,
//                       a figure field such as `display` or `change_display` included.
//                       tests/unit/whatChangedChip.spec.tsx holds what no lint can see on the what-changed
//                       chip: that its colour is directionChip for the tone the server sent, not for the
//                       direction.
//                       On the walk, an unread part that holds no colour (`${size}`) stops it as an ink
//                       would, while a colour set only by a clsx object key ({ 'text-x': up }) or by a
//                       variant that styles the glyph from its parent (`[&>svg]:text-x`) does not, so
//                       sage above either is flagged.
//   no-unguarded-animation (P-09) Every Tailwind animation utility stops under reduced motion
//                       (WCAG 2.3.3): `motion-safe:animate-x`, or `animate-x` beside a
//                       `motion-reduce:animate-none` with the same variants in the class text that
//                       always renders with it. Same variants, because a variant can raise the
//                       animation's specificity (`dark:`, `group-hover:`) or move it later in the
//                       stylesheet (`md:`), and then a bare guard loses: `[&>:last-child]:after:
//                       animate-pulse` needs `motion-reduce:[&>:last-child]:after:animate-none`. A
//                       spinner becomes its static glyph, a skeleton a static bone, an entrance
//                       shows at once. The globals.css classes that stop themselves in a
//                       reduced-motion block (SELF_GUARDED_ANIMATIONS) need no guard; the spec holds
//                       each of them, and every other animation globals.css declares, to that block.
//   locale-pinned-numbers  A number or a time reads in one locale (en-US) whatever the viewer's browser
//                       says, so `x.toLocaleString()`, `x.toLocaleTimeString()` and
//                       `Intl.NumberFormat()`, with `new` or without it (both return the formatter),
//                       with no locale, with `undefined` for it or with an empty list (`[]`), each the
//                       browser's own locale, are banned everywhere, lib/format.ts included: it owns the
//                       formatters and pins 'en-US' itself (getFormatter), so the rule reads it as it reads
//                       the app, and a bare call added there fails too.
//                       `x.toLocaleDateString()` is not read here: eslint.config.mjs's date rule
//                       (no-restricted-syntax) bans every call of it, pinned or not, and names
//                       formatLocalDate, so reading it here too would report one call twice. The receiver's type is not read, so a Date's
//                       toLocaleString() is caught too: the message names lib/format generally (fmtCount
//                       and fmtDecimal for a number, a date helper for a date), or pass 'en-US'. A
//                       locale other than the literal 'en-US' (or a list of it) is reported too: another
//                       locale ('de-DE'), or one the scan cannot read (a variable, which may be the
//                       browser's), since the product formats numbers and times in en-US alone.
//                       `Intl.NumberFormat` reached under another name (`const { NumberFormat } = Intl`,
//                       `globalThis.Intl`) passes, which no file writes today, and so does a computed
//                       member (`n['toLocaleString']()`, `Intl['NumberFormat']`): no one writes it by
//                       accident, and a deliberate way round the rule belongs in review (an eslint-disable
//                       with its reason), not in the rule. `Intl.DateTimeFormat` is not
//                       read (its one call site, features/calendar/lib/dates.ts, pins 'en-CA').
//   no-hand-rolled-toggle-group (CO-15, CO-22, CO-25) One single-choice toggle group app-wide: the
//                       SegmentedControl (components/ui). The rule reads an element whose role is the literal
//                       "group" (role="group" or role={'group'}) and walks the children written inside it, a
//                       .map callback and a conditional included, for a <button>, <Button> or <x.Button> tag
//                       with aria-pressed written on it; one found is that control rebuilt by hand, and three
//                       such rows on the company page had drifted from it (no focus ring, a hover that darkens).
//                       Two shapes are read beyond the group's own markup. A child tag that names a component
//                       declared in the same file (a function declaration, or a const bound to an arrow or a
//                       function expression, also inside memo or forwardRef) is read through what it renders:
//                       an arrow's expression body and every return statement's argument, conditionals and
//                       logical expressions included; the name resolves through ESLint's scopes, so a prop or
//                       a parameter of that name is not the same-file component. And the DS Button imported
//                       under another name (`import { Button as X }` from @/components/ui or
//                       @/components/ui/Button) is a <Button>. The reading is one level deep and follows
//                       syntax, not data: a wrapper imported from another file, a wrapper that renders yet
//                       another wrapper, a class component, aria-pressed reaching the button through spread
//                       props, and a row without role="group" stay unread (review-checked). The primitive's
//                       own file is exempt. The one site the wider reading finds is WordingChanges.tsx's review
//                       row (LabelToggle, features/filings): its toggle clears a label that is already set, so
//                       "pressed nowhere" is a valid state, which the SegmentedControl (always one selected
//                       value) cannot hold, and the group's line carries the disable with that reason: a mark
//                       a reader can clear stays a toggle group (D-046). A group of independent toggles (a multi-select
//                       filter row) is not this control either: disable the rule on that line with the reason.
//   elements-built-with-jsx  The app builds its elements in JSX alone, and the gates that read its elements (the
//                       password, preference and em-dash scans) read JSX, so an element built any other way is one
//                       no gate reads. Outside tests the rule refuses React's element factories: createElement,
//                       cloneElement and createFactory imported from React under any name (named, aliased or quoted,
//                       or read off its default or a namespace import: `React.createElement`, `R.cloneElement` under
//                       `import * as R`, `React['createElement']`, a key a pattern takes out of it), any value import
//                       from a JSX runtime (react/jsx-runtime and react/jsx-dev-runtime, whose jsx, jsxs and jsxDEV
//                       build elements), a re-export of any of these, and a createElement member, or a createElement
//                       key a pattern takes, whose object is not the DOM's global `document` (the key dotted,
//                       bracketed or a template). React's module is `react` at any entry, and the copy Next bundles
//                       (`next/dist/compiled/react`). The rule reads syntax and scopes, not data, so a use of React
//                       whose reach it cannot tell is refused too: its default or namespace import used other than
//                       through a member with a written key (held under another name, handed to a call, spread,
//                       returned or exported), a member by a key held in a name (`React[key]`), a pattern's rest or a
//                       key it cannot read, a `require` or a dynamic `import()` of React's module, and TypeScript's
//                       `import R = require('react')` (its `import h = React.createElement` is read as a member). A
//                       type-only import builds nothing and passes. It reads every
//                       script the gates parse, JavaScript included (eslint.config.mjs). ELEMENT_FACTORY_ALLOWLIST
//                       names the one file allowed a factory, with its reason. Out of reach: an element a library
//                       builds from data (react-markdown's tree, which lib/citationMarkers.tsx walks), and a module
//                       named by a value the rule cannot read (`import(name)`).
//   date-helpers-called-directly  The date rules in eslint.config.mjs (D-033, both directions) read a date helper's
//                       call by its callee, so the helpers they name (Date, parseISO, formatInstant, formatLocalDate:
//                       the config hands DATE_HELPERS in as the rule's option) are called by name where they format.
//                       Any other reference, by name or as a member in any key spelling, is refused where it is held,
//                       whatever calls it later: a binding under another name, a branch of a condition or a logical
//                       operand (`flag ? formatInstant : fallback`), an argument (`.map(formatInstant)`), a return, an
//                       object's or an array's entry, a spread, a prop, a cast, a member read off it (call, apply,
//                       bind), an assignment or a default export. A call or a `new`, the helper's own import or export
//                       specifier, `typeof`, a type, and a binding of its own name (`{ Date = globalThis.Date }`)
//                       pass; the global Date keeps its statics and `instanceof`, and as a member it is the global
//                       object's only, so a data row's key named Date is no helper. What holds a helper fails closed
//                       rather than have its key resolved (chief design on Codex's finding on 5f548e18, the stance
//                       elements-built-with-jsx takes on React's import): a namespace import of a date module (the
//                       config hands DATE_HELPER_MODULES in: date-fns's barrels and parseISO's own entries, and
//                       lib/format by its alias or a relative path) is used only through a member with a written key
//                       (`fmt.formatInstant(…)`, `fmt['formatInstant'](…)`, `fmt.fmtPercent`) or `typeof`. Any other
//                       use fails where it stands, the binding named: a member by a key the rule cannot read
//                       (`fmt[key]`, held or called: a key held in a const is not resolved, since the namespace is
//                       what escapes), the namespace held, handed to a call (`Object.values(fmt)`,
//                       `Reflect.get(fmt, key)`), spread, returned or exported, and a pattern's rest or a key it
//                       cannot read. The global object holds Date, so a member of it by a key the rule cannot read
//                       (`globalThis[key]`), and such a pattern over it, fail too; its other uses pass. A `require`
//                       or a dynamic `import()` of a date module and an `export * as` of one fail, and TypeScript's
//                       `import fi = fmt.formatInstant` is a helper held under another name. Out of reach: the global
//                       object under another name (held, handed on, or one of its own members: `window.self`), a
//                       helper re-exported through another app module (`export { formatInstant } from …`,
//                       `export * from …`), whose namespace the rule does not know as a date module's, and a module
//                       named by a value the rule cannot read. tsc refuses a date module's default export (none
//                       declares one) and `import x = require(…)`. Its cases are planted beside the date rules' own,
//                       through the repository config, in tests/unit/calendarFieldLint.spec.ts.
//   surface-padding-cap (E120, chief design 2026-10-19) Under enlarged text a surface's inset stops growing at narrow
//                       widths: its padding step N is the capped token (`p-cap-6`, `sm:px-cap-8`), min(N × 0.25rem,
//                       N vw), the steps tailwind.config.js defines (PADDING_CAP_STEPS, read here from the resolved
//                       theme). An uncapped p-6 is 48px a side at 320px under 200% text, where the cap leaves 19.2px. A
//                       surface carries no padding of step 5 or more that is not capped, on any side (p, px, py, ps,
//                       pe, pt, pr, pb, pl), under any variant, important or not; a frame inside a dialog's body none
//                       from step 4. A step is read from the padding scale the theme resolves, so a configured key
//                       (`p-gutter`, 1.5rem) and an arbitrary length (`p-[24px]`) count by their size, and an arbitrary
//                       value the rule cannot read as a length (`p-[calc(…)]`, `p-[env(…)]`) fails closed. A surface is:
//                       a <Card> (any element named Card, `ui.Card`, or a local name an import from @/components/ui or
//                       its Card or Modal module binds to Card: `Card as Panel`), whose recipe draws a border and a
//                       radius; the Card's and the dialog's sections, <CardHeader>, <CardBody>, <CardFooter>,
//                       <ModalHeader>, <ModalBody> and <ModalFooter>, imported under any name, at a call site and in
//                       their own source (a class written inside the function that declares one, bare, in memo() or
//                       forwardRef() or as React.memo() or React.forwardRef(), or the Card recipe), and a <Modal>'s
//                       className, its panel; a native <dialog> and each element directly inside it; a frame, an element
//                       whose class text draws a full border (`border`, `border-2`; never `border-0`) and a radius
//                       (`rounded`, `rounded-*` but `-none`) in the same branch, the Card recipe copied by hand and the
//                       wells inside a card, but never a form field (input, textarea, select), whose padding reserves
//                       room for a glyph (an icon field's pl-11, a select's pr-9); and a section of a surface, an element
//                       written directly inside a Card, a Modal or a frame whose class does not pad every render (only
//                       padding of some length in its unconditional text, a binding's read where it is named, under no
//                       variant and reset to zero under none, does; `p-0`, padding set only under a condition or a
//                       variant such as `sm:`, or a reset to zero under one or a condition (`p-cap-6 sm:p-0`), leaves the
//                       inset to the children, failing closed), through `{…}` children, conditionals and a callback
//                       written there, as the Card's sections are: the hero example's wrapper, the admin lists' rows. A
//                       frame inside a dialog's body (written inside <ModalBody> or a native <dialog> in the same file, a
//                       Card included) caps from step 4: the dialog's own inset already halves the measure there, and at
//                       320px under 200% text the cookie dialog's category cards left their text 92px and broke its
//                       longest words. A class a same-file binding holds, named in any class attribute
//                       (`className={PAD}`, `cx(SHELL, 'p-6')`, `${SHELL} p-6`; the initializer a string, a template or a
//                       cx()/clsx() call), is read with it in the branch where it is named (`framed ? FRAME : PAD`
//                       renders one or the other), and as text that is always there where the collector does not walk to
//                       it (`merge(PAD)`), for its frame and its padding alike, and a constant that draws a frame is read
//                       on its own too, failing closed where it cannot see the element it lands on (a constant drawing a
//                       select's frame beside its pr-9 reads as a frame; keep a field's inset on it). A capped key the
//                       theme does not define (`p-cap-7`, `scroll-py-cap-7`) fails anywhere, under any variant, since it
//                       ships unstyled. Out of reach (review-checked, the reachable ones planted as gaps in
//                       tests/unit/designRules.spec.ts): a class a component receives as a prop and passes to a Card or a
//                       frame elsewhere, an imported constant, an object of recipes (`S.pad`), a binding a ternary or a
//                       later assignment sets, a class through a helper other than cx()/clsx() (`merge(…)`), an inset set
//                       in an inline style or a stylesheet, a token whose variant styles another element (`[&>div]:p-6`),
//                       a frame drawn without a border utility (a fill, a shadow or a ring alone, or a stylesheet class
//                       such as `.glass-card`), a section of a surface that sets padding on one axis only (a `py-2`
//                       Card's `px-6` rows), and a section held in a variable or rendered by another component (the
//                       stacked metric cards' list in FinancialMetricsTable, TableScroll's hint, the filings index's
//                       skeleton), which carry the cap by hand.
//
// Out of scope, as for every class-string rule here: a class name assembled from fragments at
// runtime, a form code reaching a Badge through a renamed variable (data-flow, not syntax), a
// Badge imported under another name, and an animation set outside a class utility (an arbitrary
// `[animation:…]` property, an inline style). The chip check resolves a class binding declared in
// the same file only: an imported constant, a class passed in as a prop, an object of recipes
// (`styles.eyebrow`), a function's return value and a later assignment to the binding stay unread.

import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  branchTexts,
  classUnitVisitors,
  collectStaticText,
  isHelperCall,
  isPassThrough,
  parseClassToken,
  splitClassToken,
} from './eslint.gridBaseTrack.mjs'

const STRIPE_WIDTH = /^border-[ls]-(2|4|8|\[[^\]]+\])$/
const ROUNDED = /^rounded(-|$)/
const NOT_ROUNDED = /(^|-)none$/

/** Primitives that always round themselves (Card's recipe sets its radius): a stripe class on one
 *  is the stripe card with no rounded-* in sight. */
const ROUNDED_PRIMITIVES = new Set(['Card'])

/** The JSX element a class attribute sits on ("Card" for <Card> and <ui.Card>), else null. */
function elementName(node) {
  const name = node.type === 'JSXAttribute' ? node.parent?.name : null
  if (name?.type === 'JSXIdentifier') return name.name
  if (name?.type === 'JSXMemberExpression') return name.property.name
  return null
}

/** The stripe token in `classText` when it also rounds the container, else null. */
export function sideStripe(classText) {
  const tokens = classText.split(/\s+/).filter(Boolean)
  const parsed = tokens.map((raw) => ({ raw, token: parseClassToken(raw) })).filter((t) => t.token)
  const stripe = parsed.find((t) => STRIPE_WIDTH.test(t.token.utility))
  const rounded = parsed.some((t) => ROUNDED.test(t.token.utility) && !NOT_ROUNDED.test(t.token.utility))
  return stripe && rounded ? stripe.raw : null
}

export const noSideStripe = {
  meta: {
    type: 'problem',
    docs: { description: 'No side-tab stripe: a thick left border on a rounded container.' },
    schema: [],
    messages: {
      stripe:
        '{{token}} on a rounded container is the side-tab stripe card. Use the Callout inset well ' +
        '(tone in the label word) or a hairline section; a quotation keeps a 2px bar without rounding.',
    },
  },
  create(context) {
    return classUnitVisitors((node, pieces) => {
      const rounds = ROUNDED_PRIMITIVES.has(elementName(node))
      for (const text of branchTexts(pieces)) {
        const token = sideStripe(rounds ? `${text} rounded` : text)
        if (token !== null) {
          context.report({ node, messageId: 'stripe', data: { token } })
          return
        }
      }
    })
  },
}

/** The landing's own composition, which no-four-up-grid reads (eslint.config.mjs): the route, every marketing module,
 *  and the sections the route mounts from other features. A section mounted from elsewhere joins
 *  LANDING_SECTIONS_ELSEWHERE in the same change (tests/unit/landing-sections-mounted.spec.ts fails until it does). */
export const LANDING_SECTIONS_ELSEWHERE = [
  'features/calendar/components/ReportingThisWeek.tsx',
  'features/filings/components/NotableFilings.tsx',
]
export const LANDING_GRID_FILES = ['app/page.tsx', 'features/marketing/**/*.{ts,tsx}', ...LANDING_SECTIONS_ELSEWHERE]

/** Top-level parts of a CSS value, split on `separator` outside parentheses and brackets. */
function topLevel(text, separator) {
  const parts = []
  let depth = 0
  let start = 0
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]
    if (ch === '(' || ch === '[') depth++
    else if ((ch === ')' || ch === ']') && depth > 0) depth--
    else if (depth === 0 && separator.test(ch)) {
      parts.push(text.slice(start, i))
      start = i + 1
    }
  }
  parts.push(text.slice(start))
  return parts.map((part) => part.trim()).filter(Boolean)
}

/** The column tracks a grid template declares (Tailwind's `_` for a space): a `repeat(N, …)` counts N times its
 *  tracks, a line name (`[full-start]`) none. Infinity where the count is the width's (auto-fill, auto-fit) or
 *  the scan cannot read it (a `var(…)`), since either can open four. */
export function templateTrackCount(template) {
  let count = 0
  for (const part of topLevel(template.replace(/_/g, ' '), /\s/)) {
    if (part.startsWith('[')) continue
    const repeat = part.match(/^repeat\((.*)\)$/s)
    if (repeat) {
      const [times, ...tracks] = topLevel(repeat[1], /,/)
      if (!/^\d+$/.test(times ?? '')) return Infinity
      count += Number(times) * templateTrackCount(tracks.join(' '))
      continue
    }
    if (/\bvar\(/.test(part)) return Infinity
    count += 1
  }
  return count
}

/** The columns a grid shorthand declares (`grid-template` or `grid`, Tailwind's `_` for a space): the track list
 *  after the top-level `/`, or, with no slash, the cells of the first area string (none: rows alone, or `none`).
 *  The `grid` shorthand's `auto-flow` after the slash is a column flow, every item a column: Infinity. */
function shorthandColumnCount(value) {
  const text = value.replace(/_/g, ' ')
  const [, columns] = topLevel(text, /\//)
  if (columns !== undefined) return /\bauto-flow\b/.test(columns) ? Infinity : templateTrackCount(columns)
  const area = text.match(/["']([^"']*)["']/)
  return area ? area[1].trim().split(/\s+/).filter(Boolean).length : null
}

// Tailwind's column-width scale for `columns-*` (3xs to 7xl): the container's width decides the count.
const MULTICOL_WIDTHS = /^(?:3xs|2xs|xs|sm|md|lg|xl|[2-7]xl)$/

/** The columns a multi-column value lays out: a count where it names one, Infinity for a column width alone (the
 *  container's width turns it into a count), null for `auto`. */
function multicolCount(value) {
  const parts = value.replace(/_/g, ' ').trim().split(/\s+/).filter(Boolean)
  const count = parts.find((part) => /^\d+$/.test(part))
  if (count !== undefined) return Number(count)
  return parts.every((part) => part === 'auto') ? null : Infinity
}

/** The columns a class utility lays its items out in, or null for one that sets none of its own (`grid-cols-none`,
 *  `grid-cols-subgrid`, `columns-auto`, anything that is not a column template, a column flow or multi-column). */
export function gridColumnCount(utility) {
  const numbered = utility.match(/^grid-cols-(\d+)$/)
  if (numbered) return Number(numbered[1])
  const arbitrary = utility.match(/^grid-cols-\[(.*)\]$/s) ?? utility.match(/^\[grid-template-columns:(.*)\]$/s)
  if (arbitrary) return templateTrackCount(arbitrary[1])
  if (/^grid-cols-\(/.test(utility)) return Infinity
  const shorthand = utility.match(/^\[grid(?:-template)?:(.*)\]$/s)
  if (shorthand) return shorthandColumnCount(shorthand[1])
  if (/^grid-flow-col(?:-dense)?$/.test(utility) || /^\[grid-auto-flow:(?:dense_)?column(?:_dense)?\]$/.test(utility)) return Infinity
  const multicol = utility.match(/^columns-(.+)$/s)
  if (multicol) {
    const value = multicol[1]
    if (/^\d+$/.test(value)) return Number(value)
    if (value === 'auto') return null
    if (MULTICOL_WIDTHS.test(value) || /^\(/.test(value)) return Infinity
    const bracket = value.match(/^\[(.*)\]$/s)
    return bracket ? multicolCount(bracket[1]) : null
  }
  const multicolProperty = utility.match(/^\[(?:columns|column-count):(.*)\]$/s)
  if (multicolProperty) return multicolCount(multicolProperty[1])
  return null
}

/** The first token in `classText` that sets four column tracks or more, under any variant, else null. */
export function fourUpGrid(classText) {
  for (const raw of classText.split(/\s+/)) {
    if (!raw) continue
    const count = gridColumnCount(splitClassToken(raw).utility)
    if (count !== null && count >= 4) return raw
  }
  return null
}

export const noFourUpGrid = {
  meta: {
    type: 'problem',
    docs: { description: 'The landing page lays nothing out four across (D-045).' },
    schema: [],
    messages: {
      fourUp:
        '{{token}} lays its items out four or more across: the landing has no four-up grids (D-045, tell T4). ' +
        "Put at most three across, or make the items a ruled list in the row's content column.",
    },
  },
  create(context) {
    // Every piece of class text the unit renders is read, whatever branch it sits on: a four-up grid on any
    // render is one.
    return classUnitVisitors((node, pieces) => {
      const token = fourUpGrid(pieces.map((piece) => piece.text).join(' '))
      if (token !== null) context.report({ node, messageId: 'fourUp', data: { token } })
    })
  },
}

const FORM_FIELD = /^(filing_type|filingType|form_type|formType|form)$/
// Props that describe an element rather than display it: a tooltip, alt text, an accessible name. They may name the form.
const DESCRIPTIVE_PROP = /^(title|alt|aria-[a-z]+)$/
// Props that neither display nor style anything: React's key and ref, an event handler, a data attribute, an id. A form
// field read there puts no form on the badge (`<Badge key={filing.form}>Current</Badge>`); every other prop is read,
// so a prop the Badge renders or styles by (children, icon, variant, className, style) counts and the gate fails closed.
const UNRENDERED_PROP = /^(key|ref|id|on[A-Z]\w*|data-[\w-]+)$/
const isBadge = (name) =>
  (name?.type === 'JSXIdentifier' && name.name === 'Badge') ||
  (name?.type === 'JSXMemberExpression' && name.property.name === 'Badge')
// The form families the product renders, written as EDGAR writes them: the periodic and current reports
// (10-K and 10-Q with their transition forms 10-KT and 10-QT, 20-F, 40-F, 11-K and 11-KT, 8-K, 6-K, 1-A, 1-K,
// 1-U), the registration statements (S-1 to
// S-11 and S-20, SF-1 and SF-3, F-1 to F-10 and F-80, read as ranges, so a number EDGAR retired, S-2 or
// F-5, counts as a code too; the 424B prospectuses), the ownership and tender families (SC 13D, SC 13G,
// SC TO, SC 14D9, 13F-HR, 13F-NT), the proxy family (DEF 14A, DEFA14A, DEFM14A, PRE 14A), the fund reports
// (N-CSR, N-Q, N-PX, N-1A, N-2) and the insider forms written as words (the search's chip labels the
// code 4 "Form 4"). The letters after a dash are each family's own, so "10-year", "Top 10" and "F-150" are
// not forms, and neither is a pairing EDGAR does not write (40-K, 20-Q, 11-F).
const FORM_CODES = String.raw`10-[KQ]T?|[24]0-F|11-KT?|[86]-K|1-[AKU]|13F-(?:HR|NT)|SC 13[DG]|SC TO-[ICT]|SC 14D9|(?:DEF|DEFA|DEFM|PRE) ?14A|S-(?:[1-9]|1[01]|20)|SF-[13]|F-(?:[1-9]|10|80)|424B\d|N-(?:CSR|Q|PX|1A|2)|Form\s[345]`
const FORM_CODE = new RegExp(String.raw`^\s*(${FORM_CODES})(\/A)?\s*$`, 'i')
// A text child that opens with a form code and then only a separator: a middot, bullet or pipe, a comma, colon or
// semicolon, or a dash set off by a space (`10-Q · Filed `, `8-K, filed`, `10-Q - Filed`); never prose (`10-K filings`,
// `10-K's cover page`), and a hyphen joined to the code is a word (`S-1-style`).
const FORM_CODE_LEAD = new RegExp(String.raw`^\s*(${FORM_CODES})(\/A)?(?:\s*(?:$|[·•|,:;–—])|\s+-)`, 'i')
const CHIP_CLASS = /^(class|className)$/
// The eyebrow recipe, under a variant or not, with Tailwind 3's important modifier or not (`!uppercase`, `sm:!uppercase`:
// the same declarations, marked !important).
const EYEBROW_CHIP = [/(^|:)!?uppercase$/, /(^|:)!?tracking-eyebrow$/]
// The helpers a class binding may call: `const EYEBROW = cx('uppercase', 'tracking-eyebrow')`.
const CLASS_HELPER = /^(cx|clsx)$/

// Values whose truthiness their text fixes: an array, object, function or class expression is truthy.
const TRUTHY_SHAPE = /^(?:ArrayExpression|ObjectExpression|FunctionExpression|ArrowFunctionExpression|ClassExpression)$/

/** An expression's truthiness whatever runs: true or false, or undefined when it depends on what runs. A literal by its
 *  value (a regex is truthy); a template truthy once a chunk has text, falsy when empty with no substitution; an array,
 *  object, function or class expression truthy; the globals `undefined` and `NaN` falsy, `Infinity` truthy; `void x`
 *  falsy, `typeof x` truthy, `!x` the opposite of x; `&&`, `||`, `??` (a truthy left is never null or undefined), a
 *  conditional and a comma sequence by JavaScript's rules over their parts. Anything else is undefined. */
function staticTruth(raw) {
  const node = unwrapTs(raw)
  if (!node) return undefined
  if (node.type === 'Literal') return node.regex ? true : node.value === null && node.bigint !== undefined ? undefined : !!node.value
  if (node.type === 'TemplateLiteral') {
    if (node.quasis.some((q) => (q.value.cooked ?? q.value.raw) !== '')) return true
    return node.expressions.length === 0 ? false : undefined
  }
  if (TRUTHY_SHAPE.test(node.type)) return true
  if (node.type === 'Identifier') return node.name === 'undefined' || node.name === 'NaN' ? false : node.name === 'Infinity' ? true : undefined
  if (node.type === 'UnaryExpression') {
    if (node.operator === 'void') return false
    if (node.operator === 'typeof') return true
    const argument = node.operator === '!' ? staticTruth(node.argument) : undefined
    return argument === undefined ? undefined : !argument
  }
  if (node.type === 'LogicalExpression') {
    const left = staticTruth(node.left)
    const right = staticTruth(node.right)
    if (node.operator === '&&') return left === false ? false : left === true ? right : right === false ? false : undefined
    if (node.operator === '||') return left === true ? true : left === false ? right : right === true ? true : undefined
    return left === true ? true : left === false && right === false ? false : undefined
  }
  if (node.type === 'ConditionalExpression') {
    const test = staticTruth(node.test)
    const [yes, no] = [staticTruth(node.consequent), staticTruth(node.alternate)]
    return test === true ? yes : test === false ? no : yes === no ? yes : undefined
  }
  if (node.type === 'SequenceExpression') return staticTruth(node.expressions[node.expressions.length - 1])
  return undefined
}

/** The operand of a logical or conditional expression that never renders because its truthiness is fixed: the right of
 *  `&&` after a falsy left, of `||` or `??` after a truthy one, the arm a fixed test never takes; else null. */
function untaken(node) {
  if (node.type === 'LogicalExpression') {
    const left = staticTruth(node.left)
    return (node.operator === '&&' ? left === false : left === true) ? node.right : null
  }
  if (node.type === 'ConditionalExpression') {
    const test = staticTruth(node.test)
    return test === undefined ? null : test ? node.alternate : node.consequent
  }
  return null
}

/** Every string an attribute's value can contribute (literals and template chunks), joined. An identifier
 *  contributes what `binding` reads for it: the class text of a binding declared in the same file. A class helper's
 *  object form names its classes by key (`cx({ uppercase: active })`), so a bare key contributes its name, as a quoted
 *  key contributes its text. A part that never renders contributes nothing: an entry whose value is falsy whatever runs
 *  (`cx({ uppercase: false })`), and an operand a fixed truthiness leaves untaken (`cx(false && 'uppercase')`). Every
 *  other string counts wherever it stands, a condition's included, so the reading fails closed. */
function attributeText(node, keys, binding, out = []) {
  if (!node || typeof node.type !== 'string') return out
  if (node.type === 'Property' && staticTruth(node.value) === false) return out
  if (node.type === 'Literal' && typeof node.value === 'string') out.push(node.value)
  if (node.type === 'Property' && !node.computed && node.key.type === 'Identifier') out.push(node.key.name)
  if (node.type === 'TemplateElement') out.push(node.value.cooked ?? node.value.raw)
  if (node.type === 'Identifier') out.push(...binding(node))
  const skipped = untaken(node)
  for (const key of keys[node.type] ?? []) {
    for (const child of [node[key]].flat()) if (child !== skipped) attributeText(child, keys, binding, out)
  }
  return out
}

/** The expression under TypeScript's wrappers, which change its type and not its text: `as const`,
 *  `satisfies`, a non-null `!` and the angle-bracket assertion. */
const unwrapTs = (node) => {
  while (node && /^TS(?:As|Satisfies|NonNull|TypeAssertion)Expression$|^TSTypeAssertion$/.test(node.type)) node = node.expression
  return node
}
/** A binding initializer read as class text: a string, a template, or a cx()/clsx() call, under TypeScript's
 *  wrappers or not (`'uppercase tracking-eyebrow' as const`). An object of recipes, a function or any other
 *  expression is not, so `styles.data` never reads `styles.chip`. */
const isClassShaped = (raw) => {
  const init = unwrapTs(raw)
  return (
    (init?.type === 'Literal' && typeof init.value === 'string') ||
    init?.type === 'TemplateLiteral' ||
    (init?.type === 'CallExpression' && init.callee.type === 'Identifier' && CLASS_HELPER.test(init.callee.name))
  )
}

/** The variable an identifier reads, from ESLint's scope analysis; null for a name that is not a
 *  reference (a property key) and for a global. */
function resolvedVariable(sourceCode, identifier) {
  for (let scope = sourceCode.getScope(identifier); scope; scope = scope.upper) {
    const reference = scope.references.find((r) => r.identifier === identifier)
    if (reference) return reference.resolved
  }
  return null
}

/** The first node in `node` that names or spells a form, else null: a form field wherever it sits (`form`,
 *  `hit.form ?? fallback`, `filing.form.toUpperCase()`, `hit['form']`), or text (JSX text, a string, a template chunk) that
 *  `code` matches. A descriptive prop and one that neither displays nor styles are skipped, and a nested Badge is
 *  checked on its own visit. */
/** A computed member key's text when it is written out: a string, or a template with no substitution. */
const staticKey = (key) =>
  key?.type === 'Literal' && typeof key.value === 'string'
    ? key.value
    : key?.type === 'TemplateLiteral' && key.expressions.length === 0
      ? key.quasis[0].value.cooked
      : undefined

function formNode(node, keys, code = FORM_CODE) {
  if (!node || typeof node.type !== 'string') return null
  if (node.type === 'JSXAttribute' && (DESCRIPTIVE_PROP.test(node.name?.name ?? '') || UNRENDERED_PROP.test(node.name?.name ?? ''))) return null
  if (node.type === 'JSXElement' && isBadge(node.openingElement.name)) return null
  if (node.type === 'Identifier' && FORM_FIELD.test(node.name)) return node
  // A form field read by bracket notation (`hit['form']`, `filing?.[\`filing_type\`]`) is the field too.
  if (node.type === 'MemberExpression' && node.computed && FORM_FIELD.test(staticKey(node.property) ?? '')) return node
  if (node.type === 'JSXText' && code.test(node.value)) return node
  if (node.type === 'Literal' && typeof node.value === 'string' && code.test(node.value)) return node
  if (node.type === 'TemplateElement' && code.test(node.value.cooked ?? '')) return node
  for (const key of keys[node.type] ?? []) {
    for (const child of [node[key]].flat()) {
      const found = formNode(child, keys, code)
      if (found) return found
    }
  }
  return null
}

const meaningfulChildren = (node) =>
  node.children.filter(
    (c) =>
      !(c.type === 'JSXText' && c.value.trim() === '') &&
      !(c.type === 'JSXExpressionContainer' && c.expression.type === 'JSXEmptyExpression'),
  )
const classTokens = (node, keys, binding) => {
  const classAttr = node.openingElement.attributes.find((a) => a.type === 'JSXAttribute' && CHIP_CLASS.test(a.name?.name ?? ''))
  return classAttr ? attributeText(classAttr.value, keys, binding).join(' ').split(/\s+/) : []
}
// An inner element that resets the recipe is a face of its own, when it resets it unconditionally. Either half resets
// it: a text-transform other than uppercase (`normal-case`, `lowercase`, `capitalize`, `[text-transform:none]`) or a
// letter-spacing of its own (another tracking utility, an arbitrary one such as `tracking-[0.02em]`,
// `[letter-spacing:0]`). A reset under a variant (`sm:normal-case`, `dark:tracking-normal`) leaves the chip's face on
// in the other branches (a phone, the light theme), and so does one on a single path of its class value
// (`plain ? 'normal-case' : ''`, `cx(plain && 'normal-case')`), so neither ends the reading. An important reset
// (`!normal-case`) is a reset. A face set by an inline style is not read, so a wrapper that resets it that way is
// reported: the gate fails closed there.
const RESETS_EYEBROW = /^!?(?:normal-case|lowercase|capitalize|tracking-(?!eyebrow$)\S+|\[text-transform:(?!uppercase\])[^\]]+\]|\[letter-spacing:[^\]]+\])$/
/** Whether a class value resets the eyebrow face on every path it can take. Each path needs a reset, not the same one
 *  (`plain ? 'normal-case' : 'tracking-normal'` cancels one half of the recipe on each path): a string's tokens, a
 *  template's whole static tokens, both arms of a conditional, both sides of `||` and `??`, any argument of a cx()/clsx()
 *  call (an object's key only when its value is truthy whatever runs), and a same-file binding by its class-shaped
 *  initializer (`init`). A fixed truthiness picks the path (staticTruth): the arm a fixed test takes, the right of `&&`
 *  after a truthy left, the side of `||` or `??` a fixed left decides. `a && b` otherwise, and anything else, resets
 *  nothing; `seen` holds the bindings on the current path, so it stops a binding that reads itself while a sibling
 *  branch reads the same binding in full. */
function resetsOnEveryPath(raw, init, seen = new Set()) {
  const node = unwrapTs(raw)
  const resets = (tokens) => tokens.some((token) => RESETS_EYEBROW.test(token))
  const words = (text) => text.split(/\s+/).filter(Boolean)
  if (!node) return false
  if (node.type === 'JSXExpressionContainer') return resetsOnEveryPath(node.expression, init, seen)
  if (node.type === 'Literal') return typeof node.value === 'string' && resets(words(node.value))
  if (node.type === 'TemplateLiteral') {
    return node.quasis.some((quasi, i) => {
      const text = quasi.value.cooked ?? quasi.value.raw
      const parts = words(text)
      // A token that touches a substitution is not whole.
      if (i > 0 && !/^\s/.test(text)) parts.shift()
      if (i < node.quasis.length - 1 && !/\s$/.test(text)) parts.pop()
      return resets(parts)
    })
  }
  if (node.type === 'ConditionalExpression') {
    const test = staticTruth(node.test)
    if (test !== undefined) return resetsOnEveryPath(test ? node.consequent : node.alternate, init, seen)
    return resetsOnEveryPath(node.consequent, init, seen) && resetsOnEveryPath(node.alternate, init, seen)
  }
  if (node.type === 'LogicalExpression') {
    const left = staticTruth(node.left)
    if (node.operator === '&&') return left === true && resetsOnEveryPath(node.right, init, seen)
    if (left === true) return resetsOnEveryPath(node.left, init, seen)
    if (left === false && node.operator === '||') return resetsOnEveryPath(node.right, init, seen)
    return resetsOnEveryPath(node.left, init, seen) && resetsOnEveryPath(node.right, init, seen)
  }
  if (node.type === 'CallExpression' && node.callee.type === 'Identifier' && CLASS_HELPER.test(node.callee.name)) {
    return node.arguments.some((arg) => {
      const value = unwrapTs(arg)
      // An object argument resets on every path only by a key whose value is truthy whatever runs.
      if (value?.type === 'ObjectExpression') {
        return value.properties.some((p) => p.type === 'Property' && !p.computed && staticTruth(p.value) === true
          && resets(words(p.key.type === 'Identifier' ? p.key.name : String(p.key.value))))
      }
      return resetsOnEveryPath(arg, init, seen)
    })
  }
  if (node.type === 'Identifier') {
    const target = init(node)
    if (!target || seen.has(target)) return false
    // The bindings on this path alone: a sibling branch that reads the same binding reads it in full.
    return resetsOnEveryPath(target, init, new Set([...seen, target]))
  }
  return false
}
/** Whether an element's class resets the eyebrow face on every path (resetsOnEveryPath). */
const resetsFace = (element, init) => {
  const classAttr = element.openingElement.attributes.find((a) => a.type === 'JSXAttribute' && CHIP_CLASS.test(a.name?.name ?? ''))
  return !!classAttr && resetsOnEveryPath(classAttr.value, init)
}
/** An expression that renders only whitespace (`{' '}`): passed over in looking for the lead. */
const isBlank = (expression) => {
  const node = unwrapTs(expression)
  return (
    (node?.type === 'Literal' && typeof node.value === 'string' && node.value.trim() === '') ||
    (node?.type === 'TemplateLiteral' && node.expressions.length === 0 && (node.quasis[0].value.cooked ?? '').trim() === '')
  )
}
/** An expression that renders nothing on one of its paths: `cond && x`, a conditional with an empty arm (`cond ?
 *  'New · ' : null`), a fallback that may be empty (`label || null`, `note ?? ''`: `||` renders its right side when
 *  the left is empty, `??` only when the left is null or undefined, so a left of `''` or `false` renders nothing,
 *  as in `(isNew && 'New') ?? 'Latest'`; a value the scan cannot read is taken to render, so `label ?? 'Latest'` with
 *  `label` unread passes, as `{label}` does, a gap the spec plants), or an empty value itself (null, a boolean,
 *  undefined, a blank string). */
const mayRenderNothing = (expression) => {
  const node = unwrapTs(expression)
  if (!node || isBlank(node)) return true
  if (node.type === 'Literal' && (node.value === null || typeof node.value === 'boolean')) return true
  if (node.type === 'Identifier' && node.name === 'undefined') return true
  if (node.type === 'LogicalExpression' && node.operator === '&&') return true
  if (node.type === 'LogicalExpression' && node.operator === '??') return mayBeKeptBlank(node.left) || mayRenderNothing(node.right)
  if (node.type === 'LogicalExpression') return mayRenderNothing(node.right)
  if (node.type === 'ConditionalExpression') return mayRenderNothing(node.consequent) || mayRenderNothing(node.alternate)
  return false
}
/** Whether a value may be blank without being null or undefined (a blank string, a boolean, a falsy `&&`): what `??`
 *  keeps and renders as nothing, where `||` would take its right side. A value the scan cannot read is taken to render. */
const mayBeKeptBlank = (expression) => {
  const node = unwrapTs(expression)
  if (!node) return false
  if (isBlank(node) || (node.type === 'Literal' && typeof node.value === 'boolean')) return true
  if (node.type === 'LogicalExpression' && node.operator === '&&') return true
  if (node.type === 'LogicalExpression' && node.operator === '||') return mayBeKeptBlank(node.right)
  if (node.type === 'LogicalExpression') return mayBeKeptBlank(node.left) || mayBeKeptBlank(node.right)
  if (node.type === 'ConditionalExpression') return mayBeKeptBlank(node.consequent) || mayBeKeptBlank(node.alternate)
  return false
}

/** The lead of an element's content: its first text or expression in document order, read through its HTML
 *  wrappers and fragments at any depth, siblings included, since uppercase and letter-spacing inherit (`<span>{form}</span><span>
 *  · Filed {ago}</span>` inside the chip renders in its face; an empty wrapper, an icon's <i>, is passed over).
 *  A blank expression (`{' '}`) is passed over too, and so is one that renders nothing on one path (mayRenderNothing:
 *  `{isNew && 'New · '}`) unless it can render a form itself. Null when a component or a Badge (judged by its own rule) or an
 *  element that resets the recipe on every path (resetsFace: a face of its own) comes first; undefined when the
 *  content holds no text at all. What follows the lead does not change the face the lead is set in. */
function leadChild(node, keys, init) {
  for (const child of meaningfulChildren(node)) {
    if (child.type === 'JSXExpressionContainer' && isBlank(child.expression)) continue
    // An expression that renders nothing on one path (`{isNew && 'New · '}`) leads only on its other paths, so unless
    // it can render a form itself the reading goes on to what leads when it renders nothing.
    if (child.type === 'JSXExpressionContainer' && mayRenderNothing(child.expression) && !formNode(child.expression, keys, FORM_CODE_LEAD)) continue
    if (child.type === 'JSXText' || child.type === 'JSXExpressionContainer') return child
    // A fragment renders its children in place: read through it as through a plain wrapper.
    if (child.type === 'JSXFragment') {
      const lead = leadChild(child, keys, init)
      if (lead !== undefined) return lead
      continue
    }
    if (child.type !== 'JSXElement') return null
    const name = child.openingElement.name
    if (name.type !== 'JSXIdentifier' || !/^[a-z]/.test(name.name)) return null
    if (resetsFace(child, init)) return null
    const lead = leadChild(child, keys, init)
    if (lead !== undefined) return lead
  }
  return undefined
}

/** A hand-rolled chip around a form: an HTML element set in eyebrow type (uppercase, tracking-eyebrow, in
 *  its class text or a same-file binding it reads) whose lead (leadChild: the first text or expression of its
 *  content, read through its HTML wrappers, siblings included) shows a form by formNode's reading (its strings
 *  tested with FORM_CODE_LEAD, so `{'10-Q · Filed'}` counts), as the Notable filings line's `{form} · filed {date}`
 *  does. A Badge by another hand. A sentence that names a form later (`Latest {filing.filing_type}`) or opens
 *  with one as prose (`10-K filings`) is copy; a component, a Badge or a face-resetting element before the lead
 *  ends the reading, and nothing after it does. The children are read first, so a class binding is resolved
 *  only around a form. */
function isEyebrowFormChip(node, keys, binding, init) {
  const name = node.openingElement.name
  if (name.type !== 'JSXIdentifier' || !/^[a-z]/.test(name.name)) return false
  const lead = leadChild(node, keys, init)
  if (!lead || !formNode(lead, keys, FORM_CODE_LEAD)) return false
  const tokens = classTokens(node, keys, binding)
  return EYEBROW_CHIP.every((pattern) => tokens.some((token) => pattern.test(token)))
}

export const noFormCodeBadge = {
  meta: {
    type: 'problem',
    docs: { description: 'Form codes are text in the data face, never a Badge.' },
    schema: [],
    messages: {
      badge:
        'A form code inside <Badge> — set it as text in the data face (font-data font-semibold), as ' +
        'the filing identity strip does. Badges are for states, not document categories.',
      chip:
        'A form code in a hand-rolled eyebrow chip (uppercase, tracking-eyebrow): set it as text in the ' +
        'data face (font-data), as the filing identity strip does. Eyebrow type is for metric labels.',
    },
  },
  create(context) {
    const { sourceCode } = context
    const keys = sourceCode.visitorKeys
    // The class text of the binding an identifier in a class attribute names (`className={EYEBROW}`,
    // `cx(EYEBROW, 'mt-1')`): a same-file declaration whose initializer is class-shaped, read as an inline
    // class is. An import, a parameter or prop and a destructured name give nothing; `seen` stops a binding
    // that reads itself.
    const bindingClassText = (identifier, seen = new Set()) => {
      const def = resolvedVariable(sourceCode, identifier)?.defs[0]
      const init = def?.type === 'Variable' && def.node.id.type === 'Identifier' ? def.node.init : null
      if (!isClassShaped(init) || seen.has(init)) return []
      seen.add(init)
      return attributeText(init, keys, (inner) => bindingClassText(inner, seen))
    }
    // The same binding's class-shaped initializer itself, for the reading of what a class sets on every path.
    const bindingInit = (identifier) => {
      const def = resolvedVariable(sourceCode, identifier)?.defs[0]
      const init = def?.type === 'Variable' && def.node.id.type === 'Identifier' ? def.node.init : null
      return isClassShaped(init) ? init : null
    }
    return {
      JSXElement(node) {
        if (isEyebrowFormChip(node, keys, bindingClassText, bindingInit)) {
          return context.report({ node: node.openingElement, messageId: 'chip' })
        }
        if (!isBadge(node.openingElement.name)) return
        for (const part of [...node.openingElement.attributes, ...node.children]) {
          const found = formNode(part, keys)
          if (found) return context.report({ node: found, messageId: 'badge' })
        }
      },
    }
  },
}

const DIRECTION_600_TEXT = /^text-(gain|loss)(-light)?(\/\S+)?$/
const BRAND_TEXT = /^text-brand(-|\/|$)/
const TREND_ICON = /^Trend(Up|Down)Icon$/
const CLASS_ATTR = /^(class|className|\w+ClassName)$/

/** The first token of `classText` whose utility matches `pattern`, under any variant, else null. */
const firstToken = (classText, pattern) =>
  classText.split(/\s+/).find((raw) => raw && pattern.test(splitClassToken(raw).utility)) ?? null

/** The first 600-level direction colour used as text in `classText`, else null. */
export const direction600Text = (classText) => firstToken(classText, DIRECTION_600_TEXT)
/** The first sage text class in `classText`, else null. */
export const brandText = (classText) => firstToken(classText, BRAND_TEXT)

const cjs = createRequire(import.meta.url)
/** The colours a `text-` class can name, as Tailwind names them (`brand-strong`, `text-secondary-light`,
 *  `white`; a DEFAULT is its bare family): tailwind.config.js resolved with Tailwind's own palette. `inherit`
 *  and `current` are left out, since they hand the element its parent's ink. */
const flatColours = (colours, prefix = '') =>
  Object.entries(colours).flatMap(([key, value]) => {
    const name = key === 'DEFAULT' ? prefix : prefix ? `${prefix}-${key}` : key
    return value && typeof value === 'object' ? flatColours(value, name) : [name]
  })
const RESOLVED_THEME = cjs('tailwindcss/resolveConfig')(cjs('./tailwind.config.js')).theme
const TEXT_COLOURS = new Set(
  flatColours(RESOLVED_THEME.textColor).filter(
    (name) => name !== 'inherit' && name !== 'current',
  ),
)
/** An arbitrary value Tailwind reads as a colour: a `color:` hint, a hex, a colour function or a bare
 *  `var()` (Tailwind's default for `text-[var(--x)]`); a length or anything else is not one. */
const ARBITRARY_COLOUR = /^\[(?:color:|#|(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(|var\()/
const OPACITY_MODIFIER = /\/(?:[\w.]+|\[[^\]]*\])$/

/** Whether a utility sets a text colour: `text-` and a colour of the theme, an opacity modifier allowed.
 *  The colours are read from the theme, not the other utilities denied by name, so no size (text-sm,
 *  text-data-xs, text-sm/6), alignment, wrap or overflow mode, nor a `text-` utility a later Tailwind adds,
 *  is ever read as one. */
export const isTextColour = (utility) => {
  if (!utility.startsWith('text-')) return false
  const value = utility.slice('text-'.length)
  return value.startsWith('[') ? ARBITRARY_COLOUR.test(value) : TEXT_COLOURS.has(value.replace(OPACITY_MODIFIER, ''))
}

/** Whether `classText` sets a text colour with no variant: the element's ink at rest, in light and at every
 *  width. */
const restingColour = (classText) =>
  classText.split(/\s+/).some((raw) => {
    if (!raw) return false
    const { variants, utility } = splitClassToken(raw)
    return variants.length === 0 && isTextColour(utility)
  })

/** Whether a class value gives its element an ink of its own on every render, so a glyph inside inherits
 *  nothing from above: a resting text colour in text that always renders (a string, a template, any class
 *  helper argument or array element), in both arms of a ternary or both operands of `||`/`??`; or a part
 *  the rule cannot read (a lookup such as directionChip[tone], a variable, another call), which may hold
 *  one, as the recipes the messages point to do. An `&&` operand and a clsx object key render only
 *  sometimes. */
function ownInk(node) {
  if (!node) return false
  switch (node.type) {
    case 'Literal':
      return typeof node.value === 'string' && restingColour(node.value)
    case 'TemplateLiteral':
      return restingColour(node.quasis.map((q) => q.value.cooked ?? q.value.raw).join(' ')) || node.expressions.some(ownInk)
    case 'JSXExpressionContainer':
    case 'TSAsExpression':
    case 'TSSatisfiesExpression':
    case 'TSNonNullExpression':
    case 'ChainExpression':
      return ownInk(node.expression)
    case 'JSXEmptyExpression':
    case 'ObjectExpression':
      return false
    case 'Identifier':
      return node.name !== 'undefined'
    case 'SpreadElement':
      return ownInk(node.argument)
    case 'ConditionalExpression':
      return ownInk(node.consequent) && ownInk(node.alternate)
    case 'LogicalExpression':
      return node.operator !== '&&' && ownInk(node.left) && ownInk(node.right)
    case 'BinaryExpression':
      return node.operator === '+' && (ownInk(node.left) || ownInk(node.right))
    case 'ArrayExpression':
      return node.elements.some(ownInk)
    case 'CallExpression':
      if (isHelperCall(node)) return node.arguments.some(ownInk)
      if (isPassThrough(node)) return ownInk(node.callee.object)
      return true
    default:
      return true
  }
}

/** A trend glyph's exported names: Phosphor exports each glyph with and without the Icon suffix, the barrel the
 *  suffixed name alone. */
const TREND_GLYPH = /^Trend(Up|Down)(Icon)?$/
/** The SVG elements that draw a graphic; `text` and `tspan` set type, so a colour on them is a text colour. */
const SVG_GRAPHICS = new Set(['svg', 'g', 'path', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'rect', 'use', 'symbol'])
const PHOSPHOR = '@phosphor-icons/react'

/** Whether an import draws from the icon modules: `@/lib/icons` (by its alias or a path relative to the file) and
 *  the Phosphor package at any entry, read as tests/unit/iconModules.ts reads them for the glyph and heading gates. */
const isIconModule = (source, filename, cwd) => {
  if (source === PHOSPHOR || source.startsWith(`${PHOSPHOR}/`)) return true
  const target = source.startsWith('@/')
    ? source.slice(2)
    : source.startsWith('.')
      ? path.relative(cwd, path.resolve(path.dirname(filename), source)).split(path.sep).join('/')
      : source
  return target.replace(/\.tsx?$/, '').replace(/\/index$/, '') === 'lib/icons'
}

/** What the glyph reading can tell a value holds: a trend glyph, a namespace import of the icon modules, or (the
 *  node itself) an object or array literal, whose values a lookup reads. */
const A_GLYPH = 'glyph'
const AN_ICON_NAMESPACE = 'icon namespace'

/** A member's or a destructured property's key when it is written out (`GLYPH.up`, `GLYPH['up']`, `GLYPHS[0]`,
 *  `{ up: Up }`), else null. */
const writtenKey = (key, computed) =>
  !computed ? (key.name ?? String(key.value)) : key.type === 'Literal' ? String(key.value) : (staticKey(key) ?? null)

/** The keys a destructuring pattern reads on its way from `source`, the value written, down to `identifier`:
 *  `const { TrendUp: Up } = Ph` reads ['TrendUp'], `const Up = TrendUpIcon` and a default (`Up = TrendUpIcon`)
 *  none. A key the scan cannot read is null; a shape the reading does not follow (a rest element, a loop's
 *  variable) gives undefined. */
function patternKeys(identifier, source) {
  const keys = []
  for (let node = identifier; node.parent; node = node.parent) {
    const { parent } = node
    if (parent.type === 'VariableDeclarator') return parent.init === source ? keys : undefined
    if (parent.type === 'AssignmentExpression') return parent.right === source ? keys : undefined
    if (parent.type === 'AssignmentPattern' && parent.right === source) return keys
    if (parent.type === 'Property' && parent.parent?.type === 'ObjectPattern') keys.unshift(writtenKey(parent.key, parent.computed))
    else if (parent.type === 'ArrayPattern') keys.unshift(String(parent.elements.indexOf(node)))
    else if (parent.type !== 'AssignmentPattern' && parent.type !== 'ObjectPattern') return undefined
  }
  return undefined
}

/** Reads whether a JSX tag or an expression names a trend glyph. A name spelled TrendUpIcon or TrendDownIcon is one
 *  wherever it comes from. Any other name is read through ESLint's scopes to its binding: one an import from the
 *  icon modules makes (`TrendUpIcon as Up`, Phosphor's unsuffixed `TrendUp`, or a namespace, whose trend members are
 *  glyphs: `Ph.TrendUp`), or one of the file, which holds every value written to it (its initialiser, a default, a
 *  later assignment). A value is read through an alias, a member of a namespace or of an object or array literal (by
 *  its key: `GLYPH.up`; by every value for a key the scan cannot read: `GLYPH[d]`), a ternary's arms, a logical
 *  operator's operands (the right of `&&` alone), a destructuring pattern's keys and TypeScript's wrappers. A binding
 *  read again on its own path gives nothing more, so a cycle ends. `tag` reads a JSX tag (a lower-case name is an
 *  HTML element, never a binding), `value` an expression (a direction map's value). */
function glyphReader(context) {
  const { sourceCode, filename, cwd } = context
  const bindingOf = (node) => {
    for (let scope = sourceCode.getScope(node); scope; scope = scope.upper) {
      const variable = scope.set.get(node.name)
      if (variable) return variable
    }
    return null
  }
  const reading = new Set()
  const ofBinding = (variable) => {
    if (reading.has(variable)) return []
    reading.add(variable)
    try {
      const found = []
      for (const def of variable.defs) {
        if (def.type !== 'ImportBinding' || !isIconModule(String(def.parent.source.value), filename, cwd)) continue
        if (def.node.type === 'ImportNamespaceSpecifier') found.push(AN_ICON_NAMESPACE)
        if (def.node.type === 'ImportSpecifier' && TREND_GLYPH.test(def.node.imported.name ?? def.node.imported.value)) {
          found.push(A_GLYPH)
        }
      }
      for (const ref of variable.references) {
        const keys = ref.writeExpr ? patternKeys(ref.identifier, ref.writeExpr) : undefined
        if (keys) found.push(...keys.reduce((values, key) => values.flatMap((value) => member(value, key)), holds(ref.writeExpr)))
      }
      return found
    } finally {
      reading.delete(variable)
    }
  }
  // What an expression or a JSX tag may hold: A_GLYPH, AN_ICON_NAMESPACE, or an object or array literal.
  const holds = (node) => {
    switch (node?.type) {
      case 'Identifier':
      case 'JSXIdentifier': {
        const variable = bindingOf(node)
        return [...(TREND_ICON.test(node.name) ? [A_GLYPH] : []), ...(variable ? ofBinding(variable) : [])]
      }
      case 'MemberExpression':
      case 'JSXMemberExpression': {
        const key = writtenKey(node.property, node.computed)
        return key !== null && TREND_ICON.test(key) ? [A_GLYPH] : holds(node.object).flatMap((value) => member(value, key))
      }
      case 'ConditionalExpression':
        return [...holds(node.consequent), ...holds(node.alternate)]
      case 'LogicalExpression':
        return node.operator === '&&' ? holds(node.right) : [...holds(node.left), ...holds(node.right)]
      case 'ChainExpression':
      case 'TSAsExpression':
      case 'TSSatisfiesExpression':
      case 'TSNonNullExpression':
      case 'TSTypeAssertion':
        return holds(node.expression)
      case 'ObjectExpression':
      case 'ArrayExpression':
        return [node]
      default:
        return []
    }
  }
  // What `value[key]` may hold: a namespace's trend member, or a literal's values at that key (every value for a key
  // the scan cannot read), a spread read at the same key.
  const member = (value, key) => {
    if (value === AN_ICON_NAMESPACE) return key !== null && TREND_GLYPH.test(key) ? [A_GLYPH] : []
    if (value === A_GLYPH) return []
    const spread = (node, at) => holds(node.argument).flatMap((inner) => member(inner, at))
    if (value.type === 'ArrayExpression') {
      const exact = key !== null && !value.elements.some((e) => e?.type === 'SpreadElement')
      const items = exact ? [value.elements[Number(key)]] : value.elements
      return items.flatMap((e) => (!e ? [] : e.type === 'SpreadElement' ? spread(e, null) : holds(e)))
    }
    return value.properties.flatMap((p) =>
      p.type === 'SpreadElement'
        ? spread(p, key)
        : key === null || [key, null].includes(writtenKey(p.key, p.computed))
          ? holds(p.value)
          : [],
    )
  }
  return {
    tag: (name) => (name.type !== 'JSXIdentifier' || /^[A-Z]/.test(name.name)) && holds(name).includes(A_GLYPH),
    value: (node) => holds(node).includes(A_GLYPH),
    // Whether a JSX tag names an icon of the icon modules, any of them: a named import or a namespace's member.
    icon: (name) => {
      let root = name
      while (root.type === 'JSXMemberExpression') root = root.object
      if (root.type !== 'JSXIdentifier' || !/^[A-Z]/.test(root.name)) return false
      const variable = bindingOf(root)
      return !!variable?.defs.some(
        (def) => def.type === 'ImportBinding' && isIconModule(String(def.parent.source.value), filename, cwd),
      )
    },
  }
}

/** The nodes a glyph's ink passes through on its way up to the element that sets it: a `{…}` child,
 *  a ternary or `&&` around it, a fragment, and an element (which the walk reads for sage and passes when
 *  its classes give it no ink on every render: ownInk). */
const PASS_THROUGH = new Set(['JSXExpressionContainer', 'ConditionalExpression', 'LogicalExpression', 'JSXFragment', 'JSXElement'])

/** Every class text an expression can render, one per branch (see branchTexts). */
const textsOf = (node) => branchTexts(collectStaticText(node, new WeakSet()))

export const directionTextTokens = {
  meta: {
    type: 'problem',
    docs: { description: 'Direction text uses the 700-level gain/loss tokens, never the 600 level or sage.' },
    schema: [],
    messages: {
      light:
        '{{token}} is the 600-level direction colour, a graphic tone that fails as text. Use the 700 level ' +
        '(text-gain-text / text-loss-text, dark:text-gain-dark / dark:text-loss-dark), or directionText / ' +
        'directionChip from lib/financialTone.',
      brand:
        '{{token}} colours a direction in sage, and sage never marks a gain, a loss or a figure (D-030). Use ' +
        'directionText / directionChip from lib/financialTone, or the neutral ink with the glyph carrying it.',
    },
  },
  create(context) {
    const reportBrand = (node, texts) => {
      for (const text of texts) {
        const token = brandText(text)
        if (token !== null) return context.report({ node, messageId: 'brand', data: { token } })
      }
    }
    const classAttrs = (opening) =>
      opening.attributes.filter((a) => a.type === 'JSXAttribute' && a.name.type === 'JSXIdentifier' && CLASS_ATTR.test(a.name.name))
    const glyph = glyphReader(context)
    // An icon or an SVG element that draws a graphic takes its stroke and fill from its text colour (currentColor), so a
    // 600-level class written on one colours a graphic, the 600s' own use, and is not text.
    const isGraphic = (opening) => {
      const { name } = opening
      if (name.type === 'JSXIdentifier' && /^[a-z]/.test(name.name)) return SVG_GRAPHICS.has(name.name)
      return glyph.tag(name) || glyph.icon(name)
    }
    return {
      ...classUnitVisitors((node, pieces) => {
        if (node.type === 'JSXAttribute' && isGraphic(node.parent)) return
        for (const text of branchTexts(pieces)) {
          const token = direction600Text(text)
          if (token !== null) return context.report({ node, messageId: 'light', data: { token } })
        }
      }),
      // A glyph and the elements whose ink it may inherit: each one above it, through a `{…}` child, a
      // ternary or a `&&`, read for sage under any variant and in any branch, up to the first whose
      // classes give it an ink on every render (ownInk). A wrapper that sets no text colour (`flex
      // gap-1`, `text-sm`), or sets one only under a variant or in one branch, passes the ink through.
      JSXElement(node) {
        if (!glyph.tag(node.openingElement.name)) return
        for (const attr of classAttrs(node.openingElement)) reportBrand(attr, textsOf(attr.value))
        for (let up = node.parent; up && PASS_THROUGH.has(up.type); up = up.parent) {
          if (up.type !== 'JSXElement') continue
          const attrs = classAttrs(up.openingElement)
          for (const attr of attrs) reportBrand(attr, textsOf(attr.value))
          if (attrs.some((attr) => ownInk(attr.value))) break
        }
      },
      // A direction map: an object that holds a trend glyph (read as glyphReader reads one: by its name, its
      // import or a binding the file writes it to) beside the classes it is drawn with. Every value is read,
      // whatever builds it (a literal, a template, a cx() call, a ternary).
      ObjectExpression(node) {
        const props = node.properties.filter((p) => p.type === 'Property')
        if (!props.some((p) => glyph.value(p.value))) return
        for (const p of props) reportBrand(p.value, textsOf(p.value))
      },
    }
  },
}

/** globals.css classes that stop themselves in a `prefers-reduced-motion: reduce` block, so a use
 *  site needs no guard. tests/unit/designRules.spec.ts reads globals.css to hold each one to it. */
export const SELF_GUARDED_ANIMATIONS = new Set(['animate-fadeIn', 'animate-check-pop', 'animate-on-scroll'])

const MOTION_REDUCE = 'motion-reduce'
const isAnimation = (utility) =>
  utility.startsWith('animate-') && utility !== 'animate-none' && !SELF_GUARDED_ANIMATIONS.has(utility)
// In order: stacked selector variants compose the selector in sequence (`group-hover:peer-focus:`
// and `peer-focus:group-hover:` select different elements), so only the same sequence is the same.
const sameVariants = (a, b) => a.length === b.length && a.every((v, i) => v === b[i])

/** The first animation in `classText` that keeps moving under reduced motion, with the guard that
 *  stops it and its motion-safe spelling (`{ token, guard, safe }`), else null. A guard stops an
 *  animation when it carries the same variants in the same order (`motion-reduce` anywhere among
 *  them) and is at least as important: an `!important` animation beats a plain guard. */
export function unguardedAnimation(classText) {
  const tokens = classText.split(/\s+/).filter(Boolean).map((raw) => ({ raw, ...splitClassToken(raw) }))
  const guards = tokens
    .filter((t) => t.utility === 'animate-none' && t.variants.includes(MOTION_REDUCE))
    .map((t) => ({ variants: t.variants.filter((v) => v !== MOTION_REDUCE), important: t.important }))
  for (const t of tokens) {
    if (!isAnimation(t.utility) || t.variants.includes('motion-safe')) continue
    if (guards.some((g) => sameVariants(g.variants, t.variants) && (g.important || !t.important))) continue
    const variants = t.variants.filter((v) => v !== MOTION_REDUCE)
    const bang = t.important ? '!' : ''
    return {
      token: t.raw,
      guard: [MOTION_REDUCE, ...variants, `${bang}animate-none`].join(':'),
      safe: ['motion-safe', ...variants, `${bang}${t.utility}`].join(':'),
    }
  }
  return null
}

export const noUnguardedAnimation = {
  meta: {
    type: 'problem',
    docs: { description: 'Every animation utility stops under reduced motion.' },
    schema: [],
    messages: {
      unguarded:
        '{{token}} keeps moving under reduced motion (WCAG 2.3.3). Add {{guard}} in the class text that ' +
        'always renders with it, or write {{safe}}: a spinner becomes its static glyph, a skeleton a ' +
        'static bone, an entrance shows at once.',
    },
  },
  create(context) {
    return classUnitVisitors((node, pieces) => {
      for (const text of branchTexts(pieces)) {
        const found = unguardedAnimation(text)
        if (found) {
          context.report({ node, messageId: 'unguarded', data: found })
          return
        }
      }
    })
  },
}

/** The methods that format in the browser's locale when given none. */
const LOCALE_METHODS = new Set(['toLocaleString', 'toLocaleTimeString'])

/** Whether a call's locale argument is missing, the literal `undefined` or an empty list (`[]`): each is the browser's
    own locale. */
const unpinnedLocale = (args) =>
  args.length === 0 ||
  (args[0].type === 'Identifier' && args[0].name === 'undefined') ||
  (args[0].type === 'ArrayExpression' && args[0].elements.length === 0)

/** The one locale the product formats numbers and times in; lib/format.ts pins it for every helper. */
const PINNED_LOCALE = 'en-US'
const isPinnedLiteral = (node) => node.type === 'Literal' && node.value === PINNED_LOCALE
/** Whether a call's locale argument is present but not 'en-US' (or a list of it): another locale, or one the rule
    cannot read (a variable, a call), which may be the browser's. */
const otherLocale = (args) =>
  !unpinnedLocale(args) &&
  !isPinnedLiteral(args[0]) &&
  !(args[0].type === 'ArrayExpression' && args[0].elements.every((element) => element && isPinnedLiteral(element)))

/** Whether a callee is `Intl.NumberFormat`, which returns the same formatter called with `new` or without it. */
const isIntlNumberFormat = (callee) =>
  callee.type === 'MemberExpression' &&
  !callee.computed &&
  callee.object.type === 'Identifier' &&
  callee.object.name === 'Intl' &&
  callee.property.name === 'NumberFormat'

export const localePinnedNumbers = {
  meta: {
    type: 'problem',
    docs: { description: 'Numbers are formatted in a pinned locale, through lib/format.' },
    schema: [],
    messages: {
      unpinned:
        '{{call}} with no locale renders in the viewer\'s browser locale. Format the value through the ' +
        "lib/format.ts helper made for it (fmtCount or fmtDecimal for a number, a date helper for a date), " +
        "or pass 'en-US'.",
      other:
        "{{call}} pins {{locale}}, not 'en-US', the one locale the product formats numbers and times in " +
        "(lib/format.ts). Format the value through the lib/format.ts helper made for it, or pass 'en-US'.",
    },
  },
  create(context) {
    const report = (node, args, call) => {
      if (unpinnedLocale(args)) context.report({ node, messageId: 'unpinned', data: { call } })
      else if (otherLocale(args)) context.report({ node, messageId: 'other', data: { call, locale: context.sourceCode.getText(args[0]) } })
    }
    return {
      CallExpression(node) {
        const callee = node.callee
        if (isIntlNumberFormat(callee)) {
          report(node, node.arguments, 'Intl.NumberFormat()')
          return
        }
        if (callee.type !== 'MemberExpression' || callee.computed || !LOCALE_METHODS.has(callee.property.name)) return
        report(node, node.arguments, `${callee.property.name}()`)
      },
      NewExpression(node) {
        if (isIntlNumberFormat(node.callee)) report(node, node.arguments, 'new Intl.NumberFormat()')
      },
    }
  },
}

const isGroupRole = (attr) =>
  attr.type === 'JSXAttribute' &&
  attr.name?.name === 'role' &&
  ((attr.value?.type === 'Literal' && attr.value.value === 'group') ||
    (attr.value?.type === 'JSXExpressionContainer' &&
      attr.value.expression.type === 'Literal' &&
      attr.value.expression.value === 'group'))
const isButtonName = (name) =>
  (name?.type === 'JSXIdentifier' && (name.name === 'button' || name.name === 'Button')) ||
  (name?.type === 'JSXMemberExpression' && name.property.name === 'Button')
const hasPressed = (opening) =>
  opening.attributes.some((attr) => attr.type === 'JSXAttribute' && attr.name?.name === 'aria-pressed')
/** The SegmentedControl's own file: the one place a group of pressed buttons is built. */
const TOGGLE_GROUP_HOME = /(^|[\\/])components[\\/]ui[\\/]SegmentedControl\.tsx$/
/** The modules the DS Button is imported from: a local name bound to their `Button` export is a <Button>. */
const DS_BUTTON_SOURCES = new Set(['@/components/ui', '@/components/ui/Button'])
/** React's component wrappers: `memo(fn)` and `forwardRef(fn)`, bare or as `React.x`, render `fn`. */
const COMPONENT_WRAPPERS = new Set(['memo', 'forwardRef'])
const FUNCTION_TYPES = new Set(['FunctionDeclaration', 'FunctionExpression', 'ArrowFunctionExpression'])

/** The local names a file binds to the DS Button's `Button` export, `Button` itself included. */
function dsButtonNames(program) {
  const names = new Set()
  for (const statement of program.body) {
    if (statement.type !== 'ImportDeclaration' || !DS_BUTTON_SOURCES.has(statement.source.value)) continue
    for (const spec of statement.specifiers) {
      if (spec.type === 'ImportSpecifier' && (spec.imported.name ?? spec.imported.value) === 'Button') names.add(spec.local.name)
    }
  }
  return names
}

const calleeName = (callee) =>
  callee.type === 'Identifier' ? callee.name : callee.type === 'MemberExpression' && !callee.computed ? callee.property.name : null

/** The function a same-file binding declares as a component: a function declaration, or a const bound to an
 *  arrow or a function expression (through memo, forwardRef, `as` and `satisfies`); else null. */
function componentFunction(variable) {
  for (const def of variable.defs) {
    if (def.type === 'FunctionName' && def.node.body) return def.node
    if (def.type !== 'Variable' || def.parent?.kind !== 'const') continue
    let init = def.node.init
    while (init) {
      if (init.type === 'TSAsExpression' || init.type === 'TSSatisfiesExpression') init = init.expression
      else if (init.type === 'CallExpression' && COMPONENT_WRAPPERS.has(calleeName(init.callee))) init = init.arguments[0]
      else break
    }
    if (init?.type === 'ArrowFunctionExpression' || init?.type === 'FunctionExpression') return init
  }
  return null
}

/** What a component function renders: an arrow's expression body, or the argument of every return statement in
 *  its own body (a nested function's returns are that function's). */
function renderedBy(fn, keys) {
  if (fn.body.type !== 'BlockStatement') return [fn.body]
  const rendered = []
  const visit = (node) => {
    if (!node || typeof node.type !== 'string' || FUNCTION_TYPES.has(node.type)) return
    if (node.type === 'ReturnStatement') {
      if (node.argument) rendered.push(node.argument)
      return
    }
    for (const key of keys[node.type] ?? []) for (const child of [node[key]].flat()) visit(child)
  }
  for (const statement of fn.body.body) visit(statement)
  return rendered
}

export const noHandRolledToggleGroup = {
  meta: {
    type: 'problem',
    docs: { description: 'A single-choice toggle group is the SegmentedControl, never a hand-rolled row.' },
    schema: [],
    messages: {
      handRolled:
        'A role="group" of aria-pressed buttons is a single-choice toggle group: compose <SegmentedControl ' +
        'label options value onChange> from @/components/ui (the ring, the pressed colorway and the wrapping ' +
        'come with it). A group of independent toggles is not this control: disable the rule with the reason.',
    },
  },
  create(context) {
    if (TOGGLE_GROUP_HOME.test(context.filename ?? '')) return {}
    const { sourceCode } = context
    const keys = sourceCode.visitorKeys
    const buttonNames = dsButtonNames(sourceCode.ast)
    const isButton = (name) => isButtonName(name) || (name?.type === 'JSXIdentifier' && buttonNames.has(name.name))
    // The same-file component a capitalised tag names, resolved from the tag's own scope outwards, else null.
    const componentOf = (opening) => {
      const { name } = opening
      if (name.type !== 'JSXIdentifier' || !/^[A-Z]/.test(name.name)) return null
      for (let scope = sourceCode.getScope(opening); scope; scope = scope.upper) {
        const variable = scope.set.get(name.name)
        if (variable) return componentFunction(variable)
      }
      return null
    }
    // The first <button>/<Button> with aria-pressed under `node`, else null. With `follow`, a tag naming a
    // same-file component is read through what that component renders, one level deep (no further `follow`).
    const pressedButton = (node, follow) => {
      if (!node || typeof node.type !== 'string') return null
      if (node.type === 'JSXOpeningElement') {
        if (isButton(node.name)) {
          if (hasPressed(node)) return node
        } else if (follow) {
          const component = componentOf(node)
          if (component && renderedBy(component, keys).some((rendered) => pressedButton(rendered, false))) return node
        }
      }
      for (const key of keys[node.type] ?? []) {
        for (const child of [node[key]].flat()) {
          const found = pressedButton(child, follow)
          if (found) return found
        }
      }
      return null
    }
    return {
      JSXElement(node) {
        if (!node.openingElement.attributes.some(isGroupRole)) return
        for (const child of node.children) {
          if (pressedButton(child, true)) return context.report({ node: node.openingElement, messageId: 'handRolled' })
        }
      },
    }
  },
}

/** React's element factories: each builds an element with no JSX, where no gate that reads elements sees it. */
const ELEMENT_FACTORIES = new Set(['createElement', 'cloneElement', 'createFactory'])
/** React's module at any entry (`react`, `react/index.js`, a file inside the package), and the copy Next bundles, which
 *  `react` resolves to in its app router. */
const REACT_MODULE = /^(?:next\/dist\/compiled\/)?react(?:-experimental)?(?:\/|$)/
/** A JSX runtime among React's entries (react/jsx-runtime, react/jsx-dev-runtime, a build of either inside the package):
 *  every value it exports builds an element (jsx, jsxs, jsxDEV) or is Fragment. */
const JSX_RUNTIME = /jsx-(?:dev-)?runtime/
/** The frontend's root, which the allowlist's paths start from: this file's directory. */
const FRONTEND_ROOT = path.dirname(fileURLToPath(import.meta.url))

/** The files allowed one of React's element factories, by their path from the frontend root, each with the factories it
 *  may use, and why it needs one above the entry. tests/unit/designRules.spec.ts holds each entry to its file: the rule
 *  must find each factory there with the entry set aside, so an entry its file no longer needs fails. */
export const ELEMENT_FACTORY_ALLOWLIST = new Map([
  // injectCitationMarkers walks the tree react-markdown builds from a model's answer and gives each element back with
  // the citation chips set into its children: an element whose type and props the library wrote, which JSX cannot
  // rebuild without knowing them.
  ['lib/citationMarkers.tsx', new Set(['cloneElement'])],
])

/** Whether the file binds `name` where `node` reads it: a global (the DOM's `document`, Node's `require`, the global
 *  object's `globalThis`) has no declaration in the file. */
const bindsName = (sourceCode, node, name) => {
  for (let scope = sourceCode.getScope(node); scope; scope = scope.upper) {
    const variable = scope.set.get(name)
    if (variable) return variable.defs.length > 0
  }
  return false
}

/** The node a value reaches through TypeScript's wrappers, which change its type and not the value. */
const outermostTs = (node) => {
  let at = node
  while (/^TS(?:As|Satisfies|NonNull)Expression$|^TSTypeAssertion$/.test(at.parent?.type ?? '') && at.parent.expression === at) at = at.parent
  return at
}

export const elementsBuiltWithJsx = {
  meta: {
    type: 'problem',
    docs: { description: "Elements are built in JSX: React's element factories build one no gate reads." },
    schema: [],
    messages: {
      factory:
        "{{form}}: React's element factories build an element without JSX, which the gates that read the app's " +
        'elements cannot see (they read JSX). Write the element in JSX; a file that must rebuild an element it did ' +
        'not write goes in ELEMENT_FACTORY_ALLOWLIST (eslint.designRules.mjs) with its reason.',
      unreadable:
        "{{form}}: the rule cannot tell whether this reaches React's element factories (createElement, " +
        'cloneElement, createFactory), which build an element no gate reads. Import React statically, and read it ' +
        'through the names you import or a member with a written key (React.useState).',
    },
  },
  create(context) {
    const { sourceCode } = context
    const relative = path.relative(FRONTEND_ROOT, context.filename).split(path.sep).join('/')
    const allowed = ELEMENT_FACTORY_ALLOWLIST.get(relative) ?? new Set()
    // A form two readings reach (`React.createElement` is a member of React's import and a createElement member) is
    // reported once.
    const reported = new WeakSet()
    const report = (node, messageId, form) => {
      if (reported.has(node)) return
      reported.add(node)
      context.report({ node, messageId, data: { form } })
    }
    const factory = (node, name, form) => {
      if (!allowed.has(name)) report(node, 'factory', form)
    }
    const text = (node) => sourceCode.getText(node)
    const declared = (node, name) => bindsName(sourceCode, node, name)
    const isDocument = (node) => {
      const object = unwrapTs(node)
      return object?.type === 'Identifier' && object.name === 'document' && !declared(object, 'document')
    }
    /** The keys a pattern takes out of React's default or namespace import: a factory's is the factory, and a rest or
        a key the rule cannot read may hold one. */
    const takenOut = (pattern, from) => {
      for (const property of pattern.properties) {
        const key = property.type === 'RestElement' ? null : writtenKey(property.key, property.computed)
        if (key === null) report(property, 'unreadable', `${text(property)}, taken out of ${from}`)
        else if (ELEMENT_FACTORIES.has(key)) factory(property, key, `${key}, taken out of ${from}`)
      }
    }
    /** Every use of React's default or namespace import: a member by a written key, or a pattern over it. A type names
        no value (`React.ReactNode`, `typeof React.createElement` in a type), and the reference typescript-eslint makes
        to the import's own name for a file's JSX (its jsxPragma) is no use; any other use is one the rule cannot
        follow. TypeScript's `import h = React.createElement` aliases a member's value, as a const would. */
    const readNamespace = (specifier) => {
      for (const variable of sourceCode.getDeclaredVariables(specifier)) {
        for (const reference of variable.references) {
          if (reference.isValueReference === false || variable.identifiers.includes(reference.identifier)) continue
          const at = outermostTs(reference.identifier)
          const parent = at.parent
          if (parent.type === 'TSQualifiedName' && parent.left === at) {
            let name = parent
            while (name.parent?.type === 'TSQualifiedName') name = name.parent
            const alias = name.parent?.type === 'TSImportEqualsDeclaration' && name.parent.moduleReference === name
            if (alias && ELEMENT_FACTORIES.has(parent.right.name)) factory(parent, parent.right.name, text(name.parent))
            continue
          }
          if (parent.type === 'TSTypeQuery') continue
          if ((parent.type === 'MemberExpression' || parent.type === 'JSXMemberExpression') && parent.object === at) {
            const key = parent.type === 'JSXMemberExpression' ? parent.property.name : writtenKey(parent.property, parent.computed)
            if (key === null) report(parent, 'unreadable', `${text(parent)}, a member of ${variable.name} by a key held in a name`)
            else if (ELEMENT_FACTORIES.has(key)) factory(parent, key, text(parent))
          } else if (parent.type === 'VariableDeclarator' && parent.init === at && parent.id.type === 'ObjectPattern') {
            takenOut(parent.id, variable.name)
          } else if (/^Assignment(?:Expression|Pattern)$/.test(parent.type) && parent.right === at && parent.left.type === 'ObjectPattern') {
            takenOut(parent.left, variable.name)
          } else {
            report(reference.identifier, 'unreadable', `${variable.name}, React's import, used other than through a member with a written key`)
          }
        }
      }
    }
    const fromReact = (node) => !!node.source && REACT_MODULE.test(String(node.source.value))
    return {
      ImportDeclaration(node) {
        if (!fromReact(node) || node.importKind === 'type') return
        const source = String(node.source.value)
        const values = node.specifiers.filter((specifier) => specifier.importKind !== 'type')
        if (JSX_RUNTIME.test(source)) {
          if (values.length || !node.specifiers.length) report(node, 'factory', `An import from ${source}`)
          return
        }
        for (const specifier of values) {
          // A default or a namespace import, or `{ default as React }`, is React's object: every use of it is read.
          const imported = specifier.type === 'ImportSpecifier' ? (specifier.imported.name ?? specifier.imported.value) : 'default'
          if (ELEMENT_FACTORIES.has(imported)) factory(specifier, imported, `${imported}, imported from ${source}`)
          else if (imported === 'default') readNamespace(specifier)
        }
      },
      ExportNamedDeclaration(node) {
        if (!fromReact(node) || node.exportKind === 'type') return
        const source = String(node.source.value)
        if (JSX_RUNTIME.test(source)) return report(node, 'factory', `A re-export from ${source}`)
        for (const specifier of node.specifiers) {
          if (specifier.exportKind === 'type') continue
          const local = specifier.local.name ?? specifier.local.value
          if (ELEMENT_FACTORIES.has(local)) factory(specifier, local, `${local}, re-exported from ${source}`)
          else if (local === 'default') report(specifier, 'unreadable', `React's default import, re-exported from ${source}`)
        }
      },
      ExportAllDeclaration(node) {
        if (fromReact(node) && node.exportKind !== 'type') report(node, 'factory', `${text(node)}, which re-exports every factory`)
      },
      ImportExpression(node) {
        const source = staticKey(node.source)
        if (source !== undefined && REACT_MODULE.test(source)) report(node, 'unreadable', `${text(node)}, a dynamic import of React`)
      },
      CallExpression(node) {
        if (node.callee.type !== 'Identifier' || node.callee.name !== 'require' || declared(node.callee, 'require')) return
        const source = staticKey(node.arguments[0])
        if (source !== undefined && REACT_MODULE.test(source)) report(node, 'unreadable', `${text(node)}, a require of React`)
      },
      TSImportEqualsDeclaration(node) {
        const reference = node.moduleReference
        const source = reference.type === 'TSExternalModuleReference' ? staticKey(reference.expression) : undefined
        if (node.importKind !== 'type' && source !== undefined && REACT_MODULE.test(source)) {
          report(node, 'unreadable', `${text(node)}, a require of React`)
        }
      },
      // The DOM's own `document.createElement` builds a DOM node, not an element; any other object's createElement
      // member is React's under another name, or may be.
      MemberExpression(node) {
        if (writtenKey(node.property, node.computed) === 'createElement' && !isDocument(node.object)) factory(node, 'createElement', text(node))
      },
      'ObjectPattern > Property'(node) {
        if (writtenKey(node.key, node.computed) !== 'createElement') return
        const holder = node.parent.parent
        const source =
          holder.type === 'VariableDeclarator' && holder.id === node.parent ? holder.init
            : /^Assignment(?:Expression|Pattern)$/.test(holder.type) && holder.left === node.parent ? holder.right
              : undefined
        if (!source || !isDocument(source)) {
          factory(node, 'createElement', `createElement, taken out of ${source ? text(source) : "a value the rule cannot tell is the DOM's document"}`)
        }
      },
    }
  },
}

/** The global object's names, through which the global Date is a member (`globalThis.Date`, `window['Date']`). */
const GLOBAL_OBJECT = new Set(['globalThis', 'window', 'self', 'global'])
/** How a date helper is held, by the node that holds it, for the message. */
const HELD_AS = {
  ConditionalExpression: 'held in a branch of a condition',
  LogicalExpression: 'held in a logical operand',
  VariableDeclarator: 'held in a binding under another name',
  AssignmentExpression: 'assigned to a name',
  AssignmentPattern: 'held as a default under another name',
  CallExpression: 'handed to a call',
  NewExpression: 'handed to a call',
  ReturnStatement: 'returned',
  ArrowFunctionExpression: 'returned',
  Property: 'held in an object',
  ArrayExpression: 'held in an array',
  SpreadElement: 'spread',
  JSXExpressionContainer: 'handed to a component',
  MemberExpression: 'read for a member (call, apply or bind)',
  ExportDefaultDeclaration: 'exported as a default',
  TSAsExpression: 'held behind a cast',
  TSSatisfiesExpression: 'held behind a cast',
  TSNonNullExpression: 'held behind a cast',
  TSTypeAssertion: 'held behind a cast',
}

/** The calendar-date and billing-instant rules (eslint.config.mjs) read a date helper's call by its callee, so a helper
 *  used any other way hides the call it ends up in: `const held = flag ? formatInstant : fallback` then
 *  `held(filing.filing_date)` (Codex on #1370's 08a94b87). This rule refuses every reference to a helper the config
 *  names (its `helpers` option), by its name or as a member (`fmt.formatInstant`, `globalThis.Date`, any key
 *  spelling), that is not one of the uses that keep the call in sight: the callee of a call or a `new`, its own export
 *  specifier (a rename is the alias rule's), `typeof`, and the initializer or default of a binding of its own name
 *  (`const { Date = globalThis.Date } = globalThis`). The global Date also keeps its statics (`Date.now()`) and a type
 *  test (`x instanceof Date`); as a member it is the global object's only, so a data row's key named Date is no
 *  helper. A type holds no value and passes. Anything else is refused where it is held, whatever calls it later: a
 *  binding under another name, a branch of a condition or a logical operand, an argument, a return, an object's or an
 *  array's entry, a spread, a prop, a cast, a member read off it (call, apply, bind), an assignment, a default
 *  export.
 *  What holds a helper fails closed rather than have its key resolved (chief design on Codex's finding on 5f548e18, as
 *  elements-built-with-jsx reads React's import). A namespace import of a date module (the `modules` option) is used
 *  only through a member with a written key, so the helper's own checks read it, or by `typeof`; any other use fails
 *  where it stands, the binding named: a member by a key the rule cannot read (`fmt[key]`, held or called), the
 *  namespace held, handed to a call (`Object.values(fmt)`, `Reflect.get(fmt, key)`), spread, returned or exported,
 *  and a pattern's rest or a key it cannot read. The global object holds Date, so a member of it by a key the rule
 *  cannot read, and such a pattern over it, fail too; its other uses pass (the app tests it: `'doNotTrack' in
 *  window`). A `require` or a dynamic `import()` of a date module and an `export * as` of one fail, and TypeScript's
 *  `import fi = fmt.formatInstant` is a helper held under another name. */
export const dateHelpersCalledDirectly = {
  meta: {
    type: 'problem',
    docs: { description: 'A date helper is called by its name where it formats, never held or handed on as a value.' },
    schema: [
      {
        type: 'object',
        properties: { helpers: { type: 'array', items: { type: 'string' } }, modules: { type: 'array', items: { type: 'string' } } },
        additionalProperties: false,
      },
    ],
    messages: {
      held:
        "{{name}}, {{how}}: the calendar-date and billing-instant rules (eslint.config.mjs) read a date helper's call by " +
        'its callee, so a helper held as a value hides what it is handed later. Call {{name}} directly, by its name ' +
        'or as a namespace member, where the value is formatted.',
      unreadable:
        '{{form}}: a module or an object that holds a date helper is read only through a member with a written key ' +
        "(`fmt.formatInstant(…)`, `fmt['formatInstant'](…)`), since the calendar-date and billing-instant rules " +
        '(eslint.config.mjs) read a helper by its name or a written key, and a key the rule cannot read is not ' +
        'followed. Write the key, or import the helper by its own name.',
    },
  },
  create(context) {
    const helpers = new Set(context.options[0]?.helpers ?? [])
    const modules = new Set(context.options[0]?.modules ?? [])
    const { sourceCode } = context
    const text = (node) => sourceCode.getText(node)
    /** Whether an import names a date module as the `modules` option names it: an app file by its `@/` alias, whether
        the import writes the alias or a path relative to the file, with or without an extension or an index file; a
        package as written. */
    const dateModule = (source) => {
      if (typeof source !== 'string') return false
      const app = source.startsWith('@/')
        ? path.posix.normalize(source.slice(2))
        : /^\.\.?(?:\/|$)/.test(source)
          ? path.relative(FRONTEND_ROOT, path.resolve(path.dirname(context.filename), source)).split(path.sep).join('/')
          : null
      return modules.has(app === null ? source : `@/${app.replace(/\.[cm]?[jt]sx?$/, '').replace(/\/index$/, '')}`)
    }
    /** Whether a helper's node (its name, or a member that reads it) keeps the call the rules read in sight. */
    const inSight = (node, name) => {
      const { parent } = node
      if ((parent.type === 'CallExpression' || parent.type === 'NewExpression') && parent.callee === node) return true
      if (parent.type === 'ExportSpecifier' || (parent.type === 'UnaryExpression' && parent.operator === 'typeof')) return true
      const ownName = (target) => target.type === 'Identifier' && target.name === name
      if (parent.type === 'VariableDeclarator' && parent.init === node && ownName(parent.id)) return true
      if (parent.type === 'AssignmentPattern' && parent.right === node && ownName(parent.left)) return true
      if (name !== 'Date') return false
      return (parent.type === 'MemberExpression' && parent.object === node) ||
        (parent.type === 'BinaryExpression' && parent.operator === 'instanceof' && parent.right === node)
    }
    const report = (node, name) => context.report({ node, messageId: 'held', data: { name, how: HELD_AS[node.parent.type] ?? 'used as a value' } })
    const unreadable = (node, form) => context.report({ node, messageId: 'unreadable', data: { form } })
    /** One use of `who`, which holds date helpers: a namespace import of a date module (`strict`), or the global
        object, which holds Date. A member by a written key and a pattern's written keys pass, for the helper's own
        checks and the rename selectors to read; a member by a key the rule cannot read, and a pattern's rest or a key
        it cannot read, fail. A namespace's every other use fails too; the global object's pass. */
    const readHolder = (identifier, who, strict) => {
      const at = outermostTs(identifier)
      const { parent } = at
      if (parent.type === 'TSQualifiedName' && parent.left === at) {
        // A type names no value (`typeof fmt.formatInstant`); TypeScript's `import fi = fmt.formatInstant` holds the
        // member's value under the alias's name, so a helper it names keeps the name or is held under another.
        let name = parent
        while (name.parent?.type === 'TSQualifiedName') name = name.parent
        const alias = name.parent?.type === 'TSImportEqualsDeclaration' && name.parent.moduleReference === name ? name.parent : null
        const key = parent.right.name
        if (alias && helpers.has(key) && (name !== parent || alias.id.name !== key)) {
          context.report({ node: alias, messageId: 'held', data: { name: key, how: `aliased by ${text(alias)}` } })
        }
        return
      }
      if (parent.type === 'TSTypeQuery' || (parent.type === 'UnaryExpression' && parent.operator === 'typeof')) return
      if ((parent.type === 'MemberExpression' || parent.type === 'JSXMemberExpression') && parent.object === at) {
        const key = parent.type === 'JSXMemberExpression' ? parent.property.name : writtenKey(parent.property, parent.computed)
        if (key === null) unreadable(parent, `${text(parent)}, a member of ${who} by a key the rule cannot read`)
        return
      }
      const pattern =
        parent.type === 'VariableDeclarator' && parent.init === at
          ? parent.id
          : /^Assignment(?:Expression|Pattern)$/.test(parent.type) && parent.right === at
            ? parent.left
            : null
      if (pattern?.type === 'ObjectPattern') {
        for (const property of pattern.properties) {
          if (property.type === 'RestElement') unreadable(property, `${text(property)}, the rest of ${who}`)
          else if (writtenKey(property.key, property.computed) === null) {
            unreadable(property, `${text(property)}, taken out of ${who} by a key the rule cannot read`)
          }
        }
        return
      }
      if (strict) unreadable(identifier, `${who}, ${parent.type === 'ExportSpecifier' ? 'exported' : (HELD_AS[parent.type] ?? 'used as a value')}`)
    }
    return {
      // Every reference to a helper by its name, in any scope: a declaration's own name and a type are not uses. A
      // reference to the global object, by a name the file does not bind, is read as a holder of Date.
      'Program:exit'() {
        for (const scope of sourceCode.scopeManager.scopes) {
          for (const reference of scope.references) {
            const id = reference.identifier
            if (id.type !== 'Identifier' || reference.init || reference.isValueReference === false) continue
            if (helpers.has(id.name)) {
              if (id.parent.type !== 'TSQualifiedName' && id.parent.type !== 'TSTypeQuery' && !inSight(id, id.name)) report(id, id.name)
            } else if (GLOBAL_OBJECT.has(id.name) && !reference.resolved?.defs.length) {
              readHolder(id, `${id.name} (the global object)`, false)
            }
          }
        }
      },
      // A namespace import of a date module, read through every use; a type-only import holds no value.
      ImportDeclaration(node) {
        const source = String(node.source.value)
        if (node.importKind === 'type' || !dateModule(source)) return
        for (const specifier of node.specifiers) {
          if (specifier.type !== 'ImportNamespaceSpecifier') continue
          for (const variable of sourceCode.getDeclaredVariables(specifier)) {
            for (const reference of variable.references) {
              if (reference.isValueReference === false || variable.identifiers.includes(reference.identifier)) continue
              readHolder(reference.identifier, `${variable.name} (${source}'s namespace)`, true)
            }
          }
        }
      },
      // A date module held where the rule cannot read it: a dynamic import, a require, its namespace exported.
      ImportExpression(node) {
        if (dateModule(staticKey(node.source))) unreadable(node, `${text(node)}, a dynamic import of a date module`)
      },
      CallExpression(node) {
        if (node.callee.type !== 'Identifier' || node.callee.name !== 'require' || bindsName(sourceCode, node.callee, 'require')) return
        if (dateModule(staticKey(node.arguments[0]))) unreadable(node, `${text(node)}, a require of a date module`)
      },
      ExportAllDeclaration(node) {
        if (node.exported && node.exportKind !== 'type' && dateModule(String(node.source.value))) {
          unreadable(node, `${text(node)}, a date module's namespace exported`)
        }
      },
      MemberExpression(node) {
        const name = writtenKey(node.property, node.computed)
        if (name === null || !helpers.has(name)) return
        const object = unwrapTs(node.object)
        if (name === 'Date' && !(object.type === 'Identifier' && GLOBAL_OBJECT.has(object.name) && !bindsName(sourceCode, object, object.name))) return
        if (!inSight(node, name)) report(node, name)
      },
    }
  },
}

/** The padding and scroll-padding scales the theme resolves (`6` → `1.5rem`, `gutter` → `1.5rem`, `cap-6` →
 *  `min(1.5rem, 6vw)`), so a step is read by its size and a capped key is one tailwind.config.js defines. */
const PADDING_SCALE = RESOLVED_THEME.padding
const SCROLL_PADDING_SCALE = RESOLVED_THEME.scrollPadding
const PADDING = /^(p|px|py|ps|pe|pt|pr|pb|pl)-(.+)$/
const SCROLL_PADDING = /^scroll-(?:p|px|py|ps|pe|pt|pr|pb|pl)-(.+)$/
const CAPPED_KEY = /^cap-(.+)$/
/** A surface caps its inset from this step; a frame inside a dialog's body from the next. */
export const SURFACE_STEP = 5
export const DIALOG_WELL_STEP = 4
/** The components whose className and own source carry a surface's inset (components/ui/Card.tsx, Modal.tsx). */
const SURFACE_COMPONENTS = new Set(['Card', 'CardHeader', 'CardBody', 'CardFooter', 'Modal', 'ModalHeader', 'ModalBody', 'ModalFooter'])
/** The modules the Card and the Modal and their sections are imported from: a local name bound to one of those exports
 *  is that component (`import { Card as Panel }`). */
const SURFACE_SOURCES = /^(?:@\/components\/ui(?:\/(?:Card|Modal))?|\.\/(?:Card|Modal))$/
/** The primitives whose panel leaves its inset to the elements written inside it when it sets no padding itself. */
const SECTIONED_COMPONENTS = new Set(['Card', 'Modal'])
/** A dialog's body: a frame written inside one caps from DIALOG_WELL_STEP. */
const DIALOG_BODIES = new Set(['ModalBody', 'dialog'])
/** Form fields: their border and radius draw a control, and their padding reserves room for a glyph (an icon field's
 *  pl-11, a select's pr-9), so they are never a frame. */
const FORM_FIELDS = new Set(['input', 'textarea', 'select'])
/** A border on every side: `border`, `border-2`, `border-[1.5px]`; never `border-0`, which draws none. */
const FULL_BORDER = /^border(?:-(?!0$)\d+|-\[\d[^\]]*\])?$/

/** A padding value's step on the 0.25rem scale (`1.5rem` → 6, `24px` → 6, `0` → 0), or null for a value that is not a
 *  plain length (a calc(), a var(), an env()). */
function lengthStep(value) {
  const v = String(value).trim()
  if (v === '0') return 0
  const m = v.match(/^(\d*\.?\d+)(rem|px)$/)
  if (!m) return null
  return m[2] === 'rem' ? Number(m[1]) * 4 : Number(m[1]) / 4
}

/** A padding token's step on the 0.25rem scale (`p-6` → 6, `p-0` → 0, `p-[24px]` → 6), null for a value the rule
 *  cannot read as a length, or undefined for a token that sets no padding: another utility, or a key the theme does
 *  not define (`p-typo`), which styles nothing, as uncappedInset reads it. */
function paddingStep(raw) {
  const token = raw && parseClassToken(raw)
  const m = token && PADDING.exec(token.utility)
  if (!m) return undefined
  const key = m[2]
  const value = key.startsWith('[') && key.endsWith(']') ? key.slice(1, -1).replace(/_/g, ' ') : PADDING_SCALE[key]
  return value === undefined ? undefined : lengthStep(value)
}

/** Whether a class token sets padding of some length: `p-6`, `px-cap-5`, `p-[24px]`, and a value the rule cannot read
 *  as a length; never a zero one (`p-0`, `px-0`, `p-[0px]`) nor a key the theme does not define. */
function setsPadding(raw) {
  const step = paddingStep(raw)
  return step !== undefined && step !== 0
}

/** The capped key tailwind.config.js does not define in `classText` (`p-cap-7`, `scroll-py-cap-7`, `[&>div]:p-cap-7`),
 *  which ships unstyled, else null. */
export function undefinedCap(classText) {
  for (const raw of classText.split(/\s+/)) {
    if (!raw) continue
    const { utility } = splitClassToken(raw)
    const padding = PADDING.exec(utility)
    if (padding && CAPPED_KEY.test(padding[2]) && !(padding[2] in PADDING_SCALE)) return raw
    const scroll = SCROLL_PADDING.exec(utility)
    if (scroll && CAPPED_KEY.test(scroll[1]) && !(scroll[1] in SCROLL_PADDING_SCALE)) return raw
  }
  return null
}

/** Whether `classText` draws a frame: a full border and a radius, under any variant. */
export function drawsFrame(classText) {
  const utilities = classText.split(/\s+/).filter(Boolean).map(parseClassToken).filter(Boolean).map((t) => t.utility)
  return utilities.some((u) => FULL_BORDER.test(u)) && utilities.some((u) => ROUNDED.test(u) && !NOT_ROUNDED.test(u))
}

/** The first padding token in `classText` a surface may not carry from `threshold` up, else null: a step of
 *  `threshold` or more by its resolved size (p-6, sm:px-8, !pt-5, p-gutter, p-[24px]), or an arbitrary value the rule
 *  cannot read as a length. `fix` is the capped token to write instead, variants and `!` kept, or null when the theme
 *  defines no cap for the step (`step` says which) or the value is unreadable. A capped key passes at any step; a token
 *  whose variant styles another element (`[&>div]:p-6`) is not this element's inset. */
export function uncappedInset(classText, threshold) {
  for (const raw of classText.split(/\s+/)) {
    const token = raw && parseClassToken(raw)
    const m = token && PADDING.exec(token.utility)
    if (!m || CAPPED_KEY.test(m[2])) continue
    const [utility, side, key] = m
    const arbitrary = key.startsWith('[') && key.endsWith(']')
    const value = arbitrary ? key.slice(1, -1).replace(/_/g, ' ') : PADDING_SCALE[key]
    // A key the theme does not define styles nothing: not an inset.
    if (value === undefined) continue
    const step = lengthStep(value)
    if (step !== null && step < threshold) continue
    const capped = step !== null && `cap-${step}` in PADDING_SCALE
    // The utility is the token's last part, after its variants and an important `!` (or before a trailing one).
    const at = raw.lastIndexOf(utility)
    const fix = capped ? `${raw.slice(0, at)}${side}-cap-${step}${raw.slice(at + utility.length)}` : null
    return { token: raw, step, fix }
  }
  return null
}

/** The name a function is declared or bound under (`function CardBody`, `const CardBody = (…) =>`, inside memo() or
 *  forwardRef(), bare or as `React.x`), else null. */
function functionName(fn) {
  if (fn.type === 'FunctionDeclaration') return fn.id?.name ?? null
  let holder = fn.parent
  while (holder?.type === 'CallExpression' && COMPONENT_WRAPPERS.has(calleeName(holder.callee))) holder = holder.parent
  if (holder?.type === 'VariableDeclarator' && holder.id.type === 'Identifier') return holder.id.name
  return fn.type === 'FunctionExpression' ? fn.id?.name ?? null : null
}

/** The JSX element an element is written in, through `{…}` children, conditionals, fragments and a callback written
 *  there (`{rows.map((row) => <li … />)}`), else null. A fragment renders no box, written `<>`, `<Fragment>` or
 *  `<React.Fragment>` (a keyed fragment in a map). */
function enclosingElement(element, fragments = FRAGMENTS) {
  for (let node = element.parent; node; node = node.parent) if (node.type === 'JSXElement' && !isFragment(node, fragments)) return node
  return null
}

/** The names a fragment is written under: `Fragment`, and in a rule that reads the file's imports, React's Fragment
 *  under another name (`Fragment as F`). */
const FRAGMENTS = new Set(['Fragment'])
const isFragment = (element, fragments) => {
  const name = element.openingElement.name
  return name.type === 'JSXIdentifier' ? fragments.has(name.name) : name.type === 'JSXMemberExpression' && name.property.name === 'Fragment'
}

/** The identifiers an attribute's value names, outside a callback's body and a member's or a key's written name. */
function identifiersIn(node, keys, out = []) {
  if (!node || typeof node.type !== 'string') return out
  if (node.type === 'Identifier') out.push(node)
  if (FUNCTION_TYPES.has(node.type)) return out
  for (const key of keys[node.type] ?? []) {
    if (key === 'property' && node.type === 'MemberExpression' && !node.computed) continue
    if (key === 'key' && node.type === 'Property' && !node.computed) continue
    for (const child of [node[key]].flat()) identifiersIn(child, keys, out)
  }
  return out
}

const classAttribute = (element) =>
  element.openingElement.attributes.find(
    (a) => a.type === 'JSXAttribute' && a.name.type === 'JSXIdentifier' && /^(class|className)$/.test(a.name.name),
  )

export const surfacePaddingCap = {
  meta: {
    type: 'problem',
    docs: { description: "A surface's inset stops growing at narrow widths under enlarged text: its padding is the capped token." },
    schema: [],
    messages: {
      uncapped:
        "{{token}} on {{surface}} keeps growing with the text: under enlarged text a surface's inset stops growing at " +
        'narrow widths (E120). Write {{fix}}, min(N × 0.25rem, N vw) (tailwind.config.js PADDING_CAP_STEPS).',
      noStep:
        "{{token}} on {{surface}} keeps growing with the text (E120), and tailwind.config.js defines no cap-{{step}}: " +
        'add {{step}} to PADDING_CAP_STEPS and write the capped token, or use a step it defines.',
      unreadable:
        "{{token}} on {{surface}} is an inset the rule cannot read as a length: write it as a capped step (p-cap-N, " +
        "tailwind.config.js PADDING_CAP_STEPS), so it stops growing at narrow widths under enlarged text (E120).",
      undefinedCap:
        '{{token}} names a capped step tailwind.config.js does not define (PADDING_CAP_STEPS), so it ships unstyled.',
    },
  },
  create(context) {
    const sourceCode = context.sourceCode
    const keys = sourceCode.visitorKeys
    // The local names the file binds to the Card's and the Modal's exports, under their own names or another, and to
    // React's Fragment, which renders no box.
    const aliases = new Map()
    const fragments = new Set(FRAGMENTS)
    for (const statement of sourceCode.ast.body) {
      if (statement.type !== 'ImportDeclaration') continue
      const source = String(statement.source.value)
      for (const spec of statement.specifiers) {
        const imported = spec.type === 'ImportSpecifier' ? spec.imported.name ?? spec.imported.value : null
        if (SURFACE_SOURCES.test(source) && SURFACE_COMPONENTS.has(imported)) aliases.set(spec.local.name, imported)
        if (source === 'react' && imported === 'Fragment') fragments.add(spec.local.name)
      }
    }
    /** An element's name, an alias of a DS surface read as the surface (`<Panel>` for `Card as Panel`). */
    const nameOf = (element) => {
      const name = element?.openingElement?.name
      if (name?.type === 'JSXIdentifier') return aliases.get(name.name) ?? name.name
      if (name?.type === 'JSXMemberExpression') return name.property.name
      return null
    }
    /** The class text a same-file binding holds where an attribute names it (`className={PAD}`, `cx(SHELL, 'p-6')`,
     *  `${SHELL} p-6`): its initializer a string, a template or a cx()/clsx() call, read as the binding's own text. */
    const boundTexts = (attribute, read = () => true) =>
      identifiersIn(attribute.value, keys).filter(read).flatMap((identifier) => {
        const def = resolvedVariable(sourceCode, identifier)?.defs?.[0]
        const init = def?.node?.type === 'VariableDeclarator' ? def.node.init : null
        return init && isClassShaped(init) ? branchTexts(collectStaticText(unwrapTs(init), new WeakSet())) : []
      })
    /** A same-file binding a class attribute names, as its initializer when that is a string, a template or a
     *  cx()/clsx() call, so the collector reads it where it is named (`padded && PAD` is PAD's text in that arm). */
    const resolveBinding = (identifier) => {
      const def = resolvedVariable(sourceCode, identifier)?.defs?.[0]
      const init = def?.node?.type === 'VariableDeclarator' ? def.node.init : null
      return init && isClassShaped(init) ? unwrapTs(init) : null
    }
    /** Whether a surface leaves its inset to the elements written directly inside it: a Card, a Modal or a frame whose
     *  class text does not pad it in every render, as the Card leaves its inset to its sections. Only padding of some
     *  length in the unconditional text (a binding's read where it is named), under no variant and reset to zero under
     *  none, pads every render; one set only under a condition (`padded ? 'p-cap-6' : 'p-0'`, `padded && PAD`) or a
     *  variant (`sm:p-cap-6` has none below sm; `hover:`, `dark:`), or reset under one or a condition (`p-cap-6 sm:p-0`,
     *  `reset && 'sm:p-0'`), leaves the inset to the children, failing closed, and so does `p-0`. A value the rule
     *  cannot read as a length counts as padding. */
    const leavesInsetToSections = (element) => {
      if (FORM_FIELDS.has(nameOf(element))) return false
      const attribute = classAttribute(element)
      const root = { parent: null }
      const pieces = attribute ? collectStaticText(attribute.value, new WeakSet(), [], root, resolveBinding) : []
      const always = pieces.filter((piece) => piece.branch === root).map((piece) => piece.text).join(' ')
      const tokens = always.split(/\s+/).filter(Boolean)
      const base = (raw) => splitClassToken(raw).variants.length === 0
      // A zero reset under a variant, or in any conditional piece (`reset && 'sm:p-0'`), leaves the inset somewhere.
      const reset = pieces.some((piece) =>
        piece.text.split(/\s+/).some((raw) => paddingStep(raw) === 0 && (piece.branch !== root || !base(raw))),
      )
      if (!reset && tokens.some((raw) => base(raw) && setsPadding(raw))) return false
      return SECTIONED_COMPONENTS.has(nameOf(element)) || [always, ...branchTexts(pieces)].some(drawsFrame)
    }
    /** What makes a class unit a surface whatever its text says, and the element it sits on. */
    const surfaceOf = (node) => {
      const element = node.type === 'JSXAttribute' ? node.parent.parent : null
      const name = element ? nameOf(element) : null
      if (name === 'Card') return { surface: 'a Card', card: true, element }
      if (SURFACE_COMPONENTS.has(name)) return { surface: `<${name}>`, card: false, element }
      if (name === 'dialog') return { surface: 'a native <dialog>', card: false, element }
      const holder = element ? enclosingElement(element, fragments) : null
      if (holder && nameOf(holder) === 'dialog') return { surface: 'a section of a native <dialog>', card: false, element }
      // An element written directly inside a Card, a Modal or a frame whose class does not pad every render carries that
      // surface's inset, as the Card's own sections do (the hero example's wrapper, the filings index's header).
      if (holder && leavesInsetToSections(holder)) {
        const of = SECTIONED_COMPONENTS.has(nameOf(holder)) ? `a ${nameOf(holder)}` : 'a frame'
        return { surface: `a section of ${of} whose class does not pad every render`, card: false, element }
      }
      for (let at = node.parent; at; at = at.parent) {
        if (!FUNCTION_TYPES.has(at.type)) continue
        const fn = functionName(at)
        if (fn === null) continue
        if (SURFACE_COMPONENTS.has(fn)) return { surface: `${fn}'s own source`, card: fn === 'Card', element }
        break
      }
      return { surface: null, card: false, element }
    }
    const inDialogBody = (element) => {
      for (let at = enclosingElement(element, fragments); at; at = enclosingElement(at, fragments)) if (DIALOG_BODIES.has(nameOf(at))) return true
      return false
    }
    const report = (node, found, surface) => {
      const data = { token: found.token, surface, fix: found.fix, step: found.step }
      const messageId = found.fix ? 'uncapped' : found.step === null ? 'unreadable' : 'noStep'
      context.report({ node, messageId, data })
    }
    return classUnitVisitors((node, pieces) => {
      // A class a same-file binding holds is read with the attribute that names it, in the branch where it is named
      // (`framed ? FRAME : PAD` renders one or the other); a binding the collector does not walk to (`merge(PAD)`)
      // is read as text that is always there.
      let own = pieces
      let always = ''
      if (node.type === 'JSXAttribute') {
        const named = new Set()
        own = collectStaticText(node.value, new WeakSet(), [], { parent: null }, (identifier) => {
          named.add(identifier)
          return resolveBinding(identifier)
        })
        always = boundTexts(node, (identifier) => !named.has(identifier)).join(' ')
      }
      const texts = branchTexts(own).map((text) => `${text} ${always}`)
      if (texts.length === 0 && always) texts.push(always)
      for (const text of texts) {
        const token = undefinedCap(text)
        if (token !== null) {
          context.report({ node, messageId: 'undefinedCap', data: { token } })
          return
        }
      }
      const { surface, card, element } = surfaceOf(node)
      const field = element !== null && FORM_FIELDS.has(nameOf(element))
      const well = element !== null && inDialogBody(element)
      for (const text of texts) {
        const framed = card || (!field && drawsFrame(text))
        const threshold = framed && well ? DIALOG_WELL_STEP : surface || framed ? SURFACE_STEP : null
        if (threshold === null) continue
        const found = uncappedInset(text, threshold)
        if (found) {
          report(node, found, surface ?? (well ? "a frame inside a dialog's body" : 'a frame (a full border and a radius)'))
          return
        }
      }
    })
  },
}

const plugin = {
  rules: {
    'surface-padding-cap': surfacePaddingCap,
    'direction-text-tokens': directionTextTokens,
    'no-side-stripe': noSideStripe,
    'no-four-up-grid': noFourUpGrid,
    'no-form-code-badge': noFormCodeBadge,
    'no-unguarded-animation': noUnguardedAnimation,
    'locale-pinned-numbers': localePinnedNumbers,
    'no-hand-rolled-toggle-group': noHandRolledToggleGroup,
    'elements-built-with-jsx': elementsBuiltWithJsx,
    'date-helpers-called-directly': dateHelpersCalledDirectly,
  },
}
export default plugin
