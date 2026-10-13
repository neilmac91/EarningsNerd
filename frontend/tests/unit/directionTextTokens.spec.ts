import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { ESLint, RuleTester } from 'eslint'
import { describe, expect, it } from 'vitest'
import { brandText, direction600Text, directionTextTokens } from '../../eslint.designRules.mjs'

/**
 * Pins earningsnerd/direction-text-tokens (eslint.designRules.mjs; D-030, DESIGN.md "Separate Signals"):
 * a delta or a direction chip is text in the 700-level gain/loss inks (lib/financialTone's directionText
 * and directionChip), never the 600-level graphic tones and never sage. Until this rule the 700-level
 * clause of CLAUDE.md rule 11 was review-checked only, and the dashboard's what-changed chips shipped a
 * gain in sage (audit DSW-08, filing/F03).
 */

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')

describe('the class scans', () => {
  it('find a 600-level direction colour under any variant, and pass the 700 level and the dark pair', () => {
    expect(direction600Text('text-xs text-gain-light')).toBe('text-gain-light')
    expect(direction600Text('dark:text-loss')).toBe('dark:text-loss')
    expect(direction600Text('hover:text-gain/80')).toBe('hover:text-gain/80')
    expect(direction600Text('text-gain-text dark:text-gain-dark bg-gain-soft border-gain-light/20')).toBeNull()
    expect(direction600Text('text-loss-text dark:text-loss-dark')).toBeNull()
  })

  it('find a sage text class, and pass sage grounds and the neutral inks', () => {
    expect(brandText('text-brand-strong dark:text-brand-strong-dark')).toBe('text-brand-strong')
    expect(brandText('dark:text-brand-dark')).toBe('dark:text-brand-dark')
    expect(brandText('bg-brand-weak text-text-secondary-light')).toBeNull()
  })
})

RuleTester.describe = describe
RuleTester.it = it
RuleTester.itOnly = it.only

const ruleTester = new RuleTester({
  languageOptions: { ecmaVersion: 'latest', sourceType: 'module', parserOptions: { ecmaFeatures: { jsx: true } } },
})

ruleTester.run('direction-text-tokens', directionTextTokens, {
  valid: [
    // The 700-level inks and financialTone's recipes.
    '<span className="text-gain-text dark:text-gain-dark">+4.2%</span>',
    '<span className={`inline-flex border ${directionChip[tone]}`}><TrendUpIcon aria-hidden="true" />Revenue</span>',
    // The 600 levels stay graphic: a border, a fill, a chart stroke.
    '<span className="border-gain-light/20 bg-gain-soft fill-loss-light" />',
    // Sage away from a direction glyph is the accent, not a direction.
    '<a className="text-brand-strong">See all companies</a>',
    '<span className="text-brand-strong"><ArrowRightIcon /></span>',
    // A direction map in the neutral ink, the glyph carrying direction.
    "const DIRECTION = { up: { Icon: TrendUpIcon, cls: 'text-text-secondary-light' } }",
    // An object with sage classes but no trend glyph.
    "const LINK = { Icon: ArrowRightIcon, cls: 'text-brand-strong' }",
    // The walk stops at the nearest element that sets a class: a neutral one shields the sage link above it.
    '<a className="text-brand-strong"><span className="text-text-secondary-light">{up ? <TrendUpIcon /> : <TrendDownIcon />}</span></a>',
    // A glyph passed as a prop is not a child: its ink is wherever the prop renders it.
    '<Stat className="text-brand-strong" icon={<TrendUpIcon />} />',
    // A direction map whose computed values stay neutral.
    "const DIRECTION = { up: { Icon: TrendUpIcon, cls: cx('text-text-secondary-light', big && 'text-base') } }",
  ],
  invalid: [
    { code: '<span className="text-gain-light">+4.2%</span>', errors: [{ messageId: 'light' }] },
    { code: "<span className={cx('text-xs', up ? 'text-gain' : 'text-loss-text')} />", errors: [{ messageId: 'light' }] },
    { code: "const TONE = { down: 'dark:text-loss-light' }", errors: [{ messageId: 'light' }] },
    // Sage on the glyph, on the element that renders it, or in a direction map that pairs them.
    { code: '<TrendUpIcon className="h-4 w-4 text-brand-strong" />', errors: [{ messageId: 'brand' }] },
    {
      code: '<span className="inline-flex dark:text-brand-strong-dark"><TrendDownIcon />Net income</span>',
      errors: [{ messageId: 'brand' }],
    },
    {
      code: "const DIRECTION = { up: { Icon: TrendUpIcon, cls: 'text-brand-strong dark:text-brand-strong-dark bg-brand-weak' } }",
      errors: [{ messageId: 'brand' }],
    },
    { code: '<icons.TrendUpIcon className={`${size} text-brand-strong`} />', errors: [{ messageId: 'brand' }] },
    // A conditional glyph, through a ternary or a `&&`, inherits the ink of the element around it.
    {
      code: '<span className="text-brand-strong">{up ? <TrendUpIcon /> : <TrendDownIcon />}</span>',
      errors: [{ messageId: 'brand' }, { messageId: 'brand' }],
    },
    { code: '<span className="dark:text-brand-strong-dark">{up && <TrendUpIcon />}</span>', errors: [{ messageId: 'brand' }] },
    // Class-less wrappers and fragments pass the ink through to the nearest element that sets one.
    { code: '<span className="text-brand-strong"><span><TrendUpIcon /></span></span>', errors: [{ messageId: 'brand' }] },
    { code: '<p className="text-brand-strong"><>{up && <span><TrendDownIcon /></span>}</></p>', errors: [{ messageId: 'brand' }] },
    // A direction map's value built by a call or a ternary is read whole.
    { code: "const DIRECTION = { up: { Icon: TrendUpIcon, cls: cx('text-brand-strong') } }", errors: [{ messageId: 'brand' }] },
    { code: "const DIRECTION = { up: { Icon: TrendUpIcon, cls: x ? 'text-brand-strong' : 'text-xs' } }", errors: [{ messageId: 'brand' }] },
  ],
})

/** Building ESLint from the real config takes 2-3.5s warm and over 7s cold or on a loaded runner. */
const SLOW = { timeout: 30_000 }

describe('the repository config', SLOW, () => {
  it('runs direction-text-tokens as an error on app code', async () => {
    const eslint = new ESLint({ cwd: frontendRoot })
    const [result] = await eslint.lintText(
      [
        "import { TrendUpIcon } from '@/lib/icons'",
        "const DIRECTION = { up: { Icon: TrendUpIcon, cls: 'text-brand-strong' } }",
        'export function Probe({ up }: { up: boolean }) {',
        '  return (',
        '    <span className="text-gain-light">',
        '      <span className="text-brand-strong">{up && <TrendUpIcon />}</span>',
        '      {DIRECTION.up.cls}',
        '    </span>',
        '  )',
        '}',
        '',
      ].join('\n'),
      { filePath: path.join(frontendRoot, 'features/dashboard/components/direction-probe.tsx') },
    )
    expect(result.messages.map((m) => `${m.line} ${m.ruleId}`).sort()).toEqual([
      '2 earningsnerd/direction-text-tokens',
      '5 earningsnerd/direction-text-tokens',
      '6 earningsnerd/direction-text-tokens',
    ])
    expect(result.messages.every((m) => m.severity === 2)).toBe(true)
  })
})
