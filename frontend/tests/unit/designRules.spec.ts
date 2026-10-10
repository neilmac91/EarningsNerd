import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { ESLint, RuleTester } from 'eslint'
import { describe, expect, it } from 'vitest'
import {
  noFormCodeBadge,
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
 *  - no-form-code-badge (P-04): a form code is text in the data face, never a <Badge>.
 *  - no-unguarded-animation (P-09): every animation utility stops under reduced motion, through
 *    motion-safe: or a motion-reduce:animate-none with the same variants that always renders with it.
 *    The globals.css classes it exempts must stop themselves there, and so must every other animation
 *    globals.css declares.
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
  ],
  invalid: [
    { code: '<Badge variant="neutral">{filing.filing_type}</Badge>', errors: [{ messageId: 'badge' }] },
    { code: '<Badge variant="neutral">{data.filingType}</Badge>', errors: [{ messageId: 'badge' }] },
    {
      code: "<Badge variant={/10-Q|6-K/i.test(filing.filing_type) ? 'info' : 'neutral'}>{form}</Badge>",
      errors: [{ messageId: 'badge' }],
    },
    { code: '<Badge>10-Q</Badge>', errors: [{ messageId: 'badge' }] },
    { code: "<Badge>{'20-F/A'}</Badge>", errors: [{ messageId: 'badge' }] },
    // A form field by its short name, a template literal, and the member-expression spelling.
    { code: '<Badge>{f.form}</Badge>', errors: [{ messageId: 'badge' }] },
    { code: '<Badge>{`10-K`}</Badge>', errors: [{ messageId: 'badge' }] },
    { code: '<ui.Badge variant="neutral">{filing.filing_type}</ui.Badge>', errors: [{ messageId: 'badge' }] },
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

/** Building ESLint from the real config takes about 3.5s here and over 7s cold or on a loaded runner; 5s is too tight. */
const SLOW = { timeout: 30_000 }

describe('the repository config', SLOW, () => {
  it('runs the three rules as errors on app code', async () => {
    const eslint = new ESLint({ cwd: frontendRoot })
    const [result] = await eslint.lintText(
      [
        "import { Badge } from '@/components/ui'",
        'export function Probe({ form, tone }: { form: { filing_type: string }; tone: string }) {',
        '  return (',
        '    <div className={`border-l-4 ${tone} rounded-xl p-4`}>',
        '      <Badge variant="neutral">{form.filing_type}</Badge>',
        '      <span className="animate-spin" />',
        '    </div>',
        '  )',
        '}',
        '',
      ].join('\n'),
      { filePath: path.join(frontendRoot, 'app/design-rules-probe.tsx') },
    )
    expect(result.messages.map((m) => m.ruleId).sort()).toEqual([
      'earningsnerd/no-form-code-badge',
      'earningsnerd/no-side-stripe',
      'earningsnerd/no-unguarded-animation',
    ])
    expect(result.messages.every((m) => m.severity === 2)).toBe(true)
  })
})
