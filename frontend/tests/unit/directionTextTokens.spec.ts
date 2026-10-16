import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { ESLint, RuleTester } from 'eslint'
import { describe, expect, it } from 'vitest'
import { brandText, direction600Text, directionTextTokens, isTextColour } from '../../eslint.designRules.mjs'

/**
 * Pins earningsnerd/direction-text-tokens (eslint.designRules.mjs; D-030, DESIGN.md "Separate Signals"):
 * a delta or a direction chip is text in the 700-level gain/loss inks (lib/financialTone's directionText
 * and directionChip), never the 600-level graphic tones and never sage. Until this rule the 700-level
 * clause of CLAUDE.md rule 11 was review-checked only, and the dashboard's what-changed chips shipped a
 * gain in sage (audit DSW-08, filing/F03). The walk up from a glyph reads every element to the first that
 * gives it an ink on every render, so a layout or type wrapper never shields the sage above it (the
 * principal review of #1290). A glyph is known by its import as well as its spelling (Codex on 6aa1baa9): a local
 * name an import from the icon modules binds to one, a namespace member and Phosphor's unsuffixed name, in JSX
 * and in a direction map.
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

  it('read a text colour from the theme, never a size, an alignment, a wrap or an overflow mode', () => {
    for (const utility of ['text-brand-strong', 'text-text-secondary-light', 'text-white/70', 'text-gain-text', 'text-[var(--ink)]']) {
      expect(isTextColour(utility), utility).toBe(true)
    }
    for (const utility of [
      'text-xs', 'text-sm', 'text-sm/6', 'text-6xl', 'text-data-xs', 'text-left', 'text-end', 'text-nowrap', 'text-balance',
      'text-ellipsis', 'text-clip', 'text-[13px]', 'text-[length:var(--x)]', 'text-inherit', 'text-current', 'text-shadow-sm',
    ]) {
      expect(isTextColour(utility), utility).toBe(false)
    }
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
    // An import is a trend glyph only from the icon modules, and only under a trend glyph's name.
    "import { TrendUp } from './charts';\n<span className=\"text-brand-strong\"><TrendUp /></span>",
    "import { ArrowRightIcon as Up } from '@/lib/icons';\n<span className=\"text-brand-strong\"><Up /></span>",
    "import * as Ph from '@phosphor-icons/react';\n<span className=\"text-brand-strong\"><Ph.ArrowRight /></span>",
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
    // The walk stops at the nearest element that sets a text colour: a neutral one shields the sage link above it.
    '<a className="text-brand-strong"><span className="text-text-secondary-light">{up ? <TrendUpIcon /> : <TrendDownIcon />}</span></a>',
    // A glyph passed as a prop is not a child: its ink is wherever the prop renders it.
    '<Stat className="text-brand-strong" icon={<TrendUpIcon />} />',
    // A direction map whose computed values stay neutral.
    "const DIRECTION = { up: { Icon: TrendUpIcon, cls: cx('text-text-secondary-light', big && 'text-base') } }",
    // A nearer text colour wins over the sage above it, past the layout and type wrapper between them.
    '<a className="text-brand-strong"><span className="text-text-secondary-light dark:text-text-secondary-dark"><span className="inline-flex items-center gap-1 text-sm"><TrendUpIcon />Revenue</span></span></a>',
    // So does a ternary whose arms both set the ink, and a class part the rule cannot read (the recipe's lookup).
    '<a className="text-brand-strong"><span className={up ? "text-gain-text" : "text-loss-text"}><TrendUpIcon /></span></a>',
    '<a className="text-brand-strong"><span className={`inline-flex gap-1 ${directionChip[tone]}`}><TrendUpIcon /></span></a>',
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
    // Class-less wrappers and fragments pass the ink through to the nearest element that sets a text colour.
    { code: '<span className="text-brand-strong"><span><TrendUpIcon /></span></span>', errors: [{ messageId: 'brand' }] },
    { code: '<p className="text-brand-strong"><>{up && <span><TrendDownIcon /></span>}</></p>', errors: [{ messageId: 'brand' }] },
    // A wrapper whose classes set no text colour passes the sage above it through: layout classes, a type size.
    {
      code: '<span className="text-brand-strong"><span className="flex items-center gap-1"><TrendUpIcon />Revenue</span></span>',
      errors: [{ messageId: 'brand' }],
    },
    {
      code: '<p className="text-brand-strong dark:text-brand-strong-dark"><span className="text-sm font-medium">{up && <TrendDownIcon />}</span></p>',
      errors: [{ messageId: 'brand' }],
    },
    // So does a colour set only under a variant (light still inherits the sage) or in one branch, and text-current.
    {
      code: '<span className="text-brand-strong"><span className="dark:text-text-secondary-dark"><TrendUpIcon /></span></span>',
      errors: [{ messageId: 'brand' }],
    },
    {
      code: `<span className="text-brand-strong"><span className={cx('flex', muted && 'text-text-secondary-light')}><TrendUpIcon /></span></span>`,
      errors: [{ messageId: 'brand' }],
    },
    {
      code: '<span className="text-brand-strong"><span className={up ? "text-gain-text" : undefined}><TrendUpIcon /></span></span>',
      errors: [{ messageId: 'brand' }],
    },
    { code: '<span className="text-brand-strong"><span className="text-current"><TrendUpIcon /></span></span>', errors: [{ messageId: 'brand' }] },
    // A direction map's value built by a call or a ternary is read whole.
    { code: "const DIRECTION = { up: { Icon: TrendUpIcon, cls: cx('text-brand-strong') } }", errors: [{ messageId: 'brand' }] },
    { code: "const DIRECTION = { up: { Icon: TrendUpIcon, cls: x ? 'text-brand-strong' : 'text-xs' } }", errors: [{ messageId: 'brand' }] },
    // A glyph known by its import (Codex on 6aa1baa9): any local name, Phosphor's unsuffixed names, a namespace
    // member, in JSX and in a direction map, by the barrel's alias or a relative path to it.
    {
      code: "import { TrendUpIcon as Up } from '@/lib/icons';\n<span className=\"text-brand-strong\"><Up /></span>",
      errors: [{ messageId: 'brand' }],
    },
    {
      code: "import { TrendDown } from '@phosphor-icons/react';\n<span className=\"text-brand-strong\"><TrendDown /></span>",
      errors: [{ messageId: 'brand' }],
    },
    {
      code: "import * as Ph from '@phosphor-icons/react/dist/ssr';\n<span className=\"text-brand-strong\"><Ph.TrendUp /></span>",
      errors: [{ messageId: 'brand' }],
    },
    {
      code: "import { TrendDownIcon as Down } from '@/lib/icons';\nconst DIRECTION = { down: { Icon: Down, cls: 'text-brand-strong' } }",
      errors: [{ messageId: 'brand' }],
    },
    { code: "const DIRECTION = { up: { Icon: icons.TrendUpIcon, cls: 'text-brand-strong' } }", errors: [{ messageId: 'brand' }] },
    {
      code: "import { TrendUpIcon as Up } from '../../../lib/icons';\n<span className=\"text-brand-strong\"><Up /></span>",
      filename: path.join(frontendRoot, 'features/dashboard/components/probe.tsx'),
      errors: [{ messageId: 'brand' }],
    },
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
