import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { ESLint, RuleTester } from 'eslint'
import { describe, expect, it } from 'vitest'
import {
  SCREENS,
  clearedTrack,
  gridBaseTrackProblem,
  parseClassToken,
  responsiveGridBaseTrack,
} from '../../eslint.gridBaseTrack.mjs'

/**
 * Pins the responsive-grid base-track gate (eslint.gridBaseTrack.mjs;
 * lessons/frontend-variable-text-must-not-size-a-wrapping-row.md). The rule must evaluate a whole
 * class string (every helper argument and template chunk together, and each conditional branch with
 * the text that is always there around it, never with a sibling branch), check on its own any text it
 * does not walk, and understand variant prefixes, so the cases below cover both directions: shapes
 * that set a base track must pass, and every spelling of a missing one must fail.
 */

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')

describe('parseClassToken', () => {
  it('splits variants on top-level colons only', () => {
    expect(parseClassToken('md:hover:grid-cols-3')).toEqual({ variants: ['md', 'hover'], utility: 'grid-cols-3' })
    expect(parseClassToken('supports-[display:grid]:grid-cols-2')).toEqual({
      variants: ['supports-[display:grid]'],
      utility: 'grid-cols-2',
    })
    expect(parseClassToken('grid-cols-[repeat(2,minmax(0,1fr))]')).toEqual({
      variants: [],
      utility: 'grid-cols-[repeat(2,minmax(0,1fr))]',
    })
  })

  it('strips the important modifier in every position', () => {
    expect(parseClassToken('md:!grid-cols-3')?.utility).toBe('grid-cols-3')
    expect(parseClassToken('md:grid-cols-3!')?.utility).toBe('grid-cols-3')
    expect(parseClassToken('!md:grid-cols-3')).toEqual({ variants: ['md'], utility: 'grid-cols-3' })
  })

  it('ignores tokens whose variant styles other elements', () => {
    expect(parseClassToken('lg:[&>div]:grid-cols-3')).toBeNull()
    expect(parseClassToken('[&_li]:grid-cols-2')).toBeNull()
    expect(parseClassToken('*:grid-cols-2')).toBeNull()
    // Self-targeting arbitrary variants still count.
    expect(parseClassToken('[&:hover]:grid-cols-2')).not.toBeNull()
    expect(parseClassToken('[.dark_&]:grid-cols-2')).not.toBeNull()
    // A combinator inside :has() still styles this element.
    expect(parseClassToken('[&:has(>img)]:grid-cols-2')).not.toBeNull()
    expect(parseClassToken('[&:has(+aside:not(.x))]:grid-cols-2')).not.toBeNull()
    // …but a `&` inside them keeps its combinator: this styles the child div.
    expect(parseClassToken('[:where(&)>div]:grid-cols-2')).toBeNull()
  })
})

describe('gridBaseTrackProblem', () => {
  it.each([
    'grid gap-4',
    'grid grid-cols-2',
    'grid grid-cols-1 gap-6 md:grid-cols-3',
    'md:grid-cols-3 grid gap-6 grid-cols-1',
    'grid grid-cols-[auto] md:grid-cols-2',
    'grid grid-cols-1 md:!grid-cols-3',
    'lg:grid lg:grid-cols-2',
    'flex md:grid md:grid-cols-2',
    'hidden sm:grid sm:grid-cols-1 lg:grid-cols-4',
    // A min-width screen's columns still apply at every larger screen (Tailwind's cascade).
    'hidden md:grid sm:grid-cols-2',
    'hidden xl:grid md:grid-cols-2 2xl:grid-cols-3',
    'hidden dark:lg:grid sm:grid-cols-2',
    'grid-cols-1 lg:grid lg:grid-cols-3',
    'grid grid-cols-1 [&:has(>img)]:grid-cols-2',
    'grid [grid-template-columns:minmax(0,1fr)] md:grid-cols-2',
    'grid lg:[&>div]:grid-cols-3',
    'grid *:grid-cols-2',
  ])('passes %j', (classes) => {
    expect(gridBaseTrackProblem(classes)).toBeNull()
  })

  it.each([
    ['grid gap-6 md:grid-cols-3', ''],
    ['inline-grid md:grid-cols-2', ''],
    ['grid md:!grid-cols-3', ''],
    ['grid md:grid-cols-3!', ''],
    ['grid group-hover/card:grid-cols-2', ''],
    ['grid min-[600px]:grid-cols-2', ''],
    ['grid grid-cols-none md:grid-cols-3', ''],
    ['grid dark:grid-cols-1 md:grid-cols-2', ''],
    ['grid md:grid-cols-2 lg:grid', ''],
    ['md:grid-cols-2', ''],
    ['hidden sm:grid lg:grid-cols-4', 'sm:'],
    ['md:grid lg:grid-cols-3', 'md:'],
    // Only a smaller or equal screen covers, and only a named screen: other variants must match.
    ['hidden sm:grid md:grid-cols-2', 'sm:'],
    ['hidden md:grid sm:dark:grid-cols-2', 'md:'],
    ['hidden md:grid min-[600px]:grid-cols-2', 'md:'],
    // Columns set by an arbitrary property or under a self-targeting :has() variant count too.
    ['grid md:[grid-template-columns:1fr_1fr]', ''],
    ['grid [&:has(>img)]:grid-cols-2', ''],
    ['grid [grid-template-columns:none] md:grid-cols-2', ''],
  ])('flags %j (missing %j base)', (classes, prefix) => {
    expect(gridBaseTrackProblem(classes)).toBe(prefix)
  })
})

describe('screen order', () => {
  it("mirrors Tailwind's default min-width screens, which tailwind.config.js does not override", () => {
    const require = createRequire(import.meta.url)
    const config = require('../../tailwind.config.js')
    expect(config.theme?.screens).toBeUndefined()
    expect(config.theme?.extend?.screens).toBeUndefined()
    expect(Object.keys(require('tailwindcss/defaultTheme').screens)).toEqual(SCREENS)
  })
})

describe('clearedTrack', () => {
  it('finds a column reset under a variant, which overrides the base below it', () => {
    expect(clearedTrack('grid grid-cols-1 sm:grid-cols-none md:grid-cols-2')).toBe('sm:grid-cols-none')
    expect(clearedTrack('grid grid-cols-1 md:[grid-template-columns:none]')).toBe('md:[grid-template-columns:none]')
  })

  it('leaves an unprefixed reset to the base check', () => {
    expect(clearedTrack('grid grid-cols-none')).toBeNull()
    expect(clearedTrack('grid grid-cols-1 md:grid-cols-2')).toBeNull()
  })
})

RuleTester.describe = describe
RuleTester.it = it
RuleTester.itOnly = it.only

const ruleTester = new RuleTester({
  languageOptions: { ecmaVersion: 'latest', sourceType: 'module', parserOptions: { ecmaFeatures: { jsx: true } } },
})

const missing = (fix = 'grid-cols-1') => [{ messageId: 'missing', data: { fix } }]

ruleTester.run('responsive-grid-base-track', responsiveGridBaseTrack, {
  valid: [
    '<div className="grid grid-cols-1 gap-4 md:grid-cols-3" />',
    '<div className="lg:grid lg:grid-cols-[minmax(0,1fr)_13rem]" />',
    '<div className="hidden md:grid sm:grid-cols-2" />',
    '<div className="grid lg:[&>div]:grid-cols-3" />',
    '<div className={`grid grid-cols-1 ${gap} md:grid-cols-2`} />',
    // The base is always there, in a different helper argument from the variant columns, or in the
    // same branch as them.
    "<div className={cx('grid grid-cols-1', wide && 'md:grid-cols-2')} />",
    "<div className={cx('grid', wide ? 'grid-cols-1 md:grid-cols-3' : 'grid-cols-2')} />",
    "<div className={cx('grid', wide ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1')} />",
    "<div className={clsx('grid grid-cols-1', { 'md:grid-cols-2': wide })} />",
    "const c = cx('grid', 'grid-cols-1', 'md:grid-cols-2')",
    "<div className={cx('grid md:grid-cols-2', 'grid-cols-1')} />",
    "<div className={cx('grid', wide && ['grid-cols-1', 'md:grid-cols-2'])} />",
    // A branch inside a branch sees the text that is always there in the branch around it.
    "<div className={cx('grid', wide && `grid-cols-1 ${three ? 'md:grid-cols-3' : 'md:grid-cols-2'}`)} />",
    "const GRID = 'grid grid-cols-1 gap-4 md:grid-cols-2'",
    '<Panel bodyClassName="grid grid-cols-1 sm:grid-cols-2" />',
    "<NavLink className={({ isActive }) => cx('grid grid-cols-1', isActive && 'md:grid-cols-2')} />",
    // A spread counts as written in place, so it can rely on the base that is always there.
    "<div className={cx('grid grid-cols-1', ...(wide ? ['md:grid-cols-2'] : []))} />",
    // A lookup on an inline map is checked value by value, like a map constant: each value carries
    // its own base.
    "<div className={cx('grid gap-4', { 2: 'grid-cols-1 md:grid-cols-2', 3: 'grid-cols-1 md:grid-cols-3' }[cols])} />",
    // A pass-through string method keeps its receiver whole.
    "<div className={['grid grid-cols-1', wide && 'md:grid-cols-2'].filter(Boolean).join(' ')} />",
    // Not a class: a non-grid string is never parsed as a grid.
    "const label = 'Pricing'",
  ],
  invalid: [
    { code: '<div className="grid gap-6 md:grid-cols-3" />', errors: missing() },
    { code: '<div className="hidden sm:grid lg:grid-cols-4" />', errors: missing('sm:grid-cols-1') },
    { code: '<div className={`grid ${gap} md:grid-cols-2`} />', errors: missing() },
    { code: "<div className={cx('grid gap-4', wide && 'md:grid-cols-2')} />", errors: missing() },
    { code: "<div className={wide ? 'grid md:grid-cols-3' : 'flex'} />", errors: missing() },
    // A branch that is a grid on its own can't borrow the other branch's base.
    {
      code: "<div className={wide ? 'grid grid-cols-1 md:grid-cols-2' : 'grid md:grid-cols-3'} />",
      errors: missing(),
    },
    // Variant columns in a branch can't borrow a sibling branch's base…
    { code: "<div className={cx('grid gap-4', wide ? 'md:grid-cols-2' : 'grid-cols-1')} />", errors: missing() },
    { code: "<div className={cx('grid', wide && 'md:grid-cols-2', !wide && 'grid-cols-1')} />", errors: missing() },
    { code: "<div className={clsx('grid', { 'grid-cols-1': !wide, 'md:grid-cols-2': wide })} />", errors: missing() },
    { code: "<div className={`grid ${wide ? 'md:grid-cols-2' : 'grid-cols-1'}`} />", errors: missing() },
    { code: "<div className={clsx('grid', { [`md:grid-cols-${n}`]: wide })} />", errors: missing() },
    // …and a base that is only sometimes there can't stand in for one that is always there.
    { code: "<div className={cx('grid md:grid-cols-2', narrow && 'grid-cols-1')} />", errors: missing() },
    { code: "<div className={cx('grid md:grid-cols-2', custom || 'grid-cols-1')} />", errors: missing() },
    { code: "<div className={cx('grid md:grid-cols-2', custom ?? 'grid-cols-1')} />", errors: missing() },
    { code: "<div className={clsx('grid md:grid-cols-2', { 'grid-cols-1': narrow })} />", errors: missing() },
    {
      code: "<div className={cx('grid', wide && `md:grid-cols-2 ${narrow ? 'grid-cols-1' : ''}`)} />",
      errors: missing(),
    },
    // A function's return value is a class string of its own.
    {
      code: "<NavLink className={({ isActive }) => cx('grid', isActive && 'md:grid-cols-2')} />",
      errors: missing(),
    },
    { code: "const tile = () => 'grid gap-4 md:grid-cols-2'", errors: missing() },
    { code: "<div className={clsx('grid', { 'md:grid-cols-2': wide })} />", errors: missing() },
    { code: '<Panel bodyClassName="grid md:grid-cols-2" />', errors: missing() },
    { code: "const GRID = 'grid gap-4 md:grid-cols-2'", errors: missing() },
    { code: "const c = cx('grid', 'gap-4', `md:grid-cols-${n}`)", errors: missing() },
    // A fragment joined to a grid elsewhere must carry its own base.
    { code: "const COLS = { two: 'md:grid-cols-2' }", errors: missing() },
    // A spread is evaluated in place, not skipped.
    { code: "<div className={cx('grid', ...(wide ? ['md:grid-cols-2'] : []))} />", errors: missing() },
    { code: "<div className={cx(...['grid', 'md:grid-cols-2'])} />", errors: missing() },
    // Text in a shape the unit does not walk is checked on its own, never skipped: an inline map
    // lookup (one report per value, as for a map constant), a sequence, a tagged template.
    {
      code: "<div className={cx('grid gap-4', { 2: 'md:grid-cols-2', 3: 'md:grid-cols-3' }[cols])} />",
      errors: [...missing(), ...missing()],
    },
    { code: "<div className={(0, 'grid md:grid-cols-2')} />", errors: missing() },
    { code: "<div className={cx('grid', tw`md:grid-cols-2`)} />", errors: missing() },
    // Any other call may drop or pick among its inputs, so they are checked on their own and can't
    // lend a base: a plain function, an array method, a filter with a predicate.
    {
      code: "<div className={cx('grid', choose(wide, 'md:grid-cols-2', 'grid-cols-1'))} />",
      errors: missing(),
    },
    { code: "<div className={cx('grid md:grid-cols-2', withDefault(custom, 'grid-cols-1'))} />", errors: missing() },
    { code: "<div className={cx('grid', ['md:grid-cols-2', 'grid-cols-1'].at(i))} />", errors: missing() },
    {
      code: "<div className={['grid md:grid-cols-2', 'grid-cols-1'].filter((c) => c !== 'grid-cols-1').join(' ')} />",
      errors: missing(),
    },
    { code: '<div className={`grid md:grid-cols-2 ${f(\'grid-cols-1\')}`} />', errors: missing() },
    // Columns set by an arbitrary property or under a self-targeting :has() variant count too.
    { code: '<div className="grid md:[grid-template-columns:1fr_1fr]" />', errors: missing() },
    { code: '<div className="grid [&:has(>img)]:grid-cols-2" />', errors: missing() },
    // A reset under a variant clears the tracks from there up, whatever base sits below it.
    {
      code: '<div className="grid grid-cols-1 sm:grid-cols-none md:grid-cols-2" />',
      errors: [{ messageId: 'cleared', data: { token: 'sm:grid-cols-none' } }],
    },
    {
      code: '<div className="hidden md:grid sm:grid-cols-2 md:grid-cols-none" />',
      errors: [{ messageId: 'cleared', data: { token: 'md:grid-cols-none' } }],
    },
    // One report per element, however many chunks carry the variant columns.
    { code: "<div className={cx('grid', 'md:grid-cols-2', `lg:grid-cols-${n}`)} />", errors: missing() },
  ],
})

describe('eslint.config.mjs wiring', () => {
  it('runs the rule on app code through the real config, including TypeScript syntax', async () => {
    const eslint = new ESLint({ cwd: frontendRoot })
    const [result] = await eslint.lintText(
      [
        "import { cx } from '@/components/ui/cx'",
        'export function Probe({ wide }: { wide: boolean }) {',
        "  return <div className={cx('grid gap-4', (wide ? 'md:grid-cols-2' : '') as string)} />",
        '}',
        '',
      ].join('\n'),
      { filePath: path.join(frontendRoot, 'app/grid-base-track-probe.tsx') },
    )
    expect(result.messages.map((m) => m.ruleId)).toEqual(['earningsnerd/responsive-grid-base-track'])
    expect(result.messages[0].severity).toBe(2)
  })
})
