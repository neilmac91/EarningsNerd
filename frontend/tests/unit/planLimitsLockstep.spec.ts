import { readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { bindingResolver } from './astBindings'
import {
  ANALYSIS_MAX_ANNUAL_PERIODS,
  ANALYSIS_MAX_QUARTERLY_PERIODS,
  FREE_SUMMARY_LIMIT,
  FREE_EARNINGS_ALERT_LIMIT,
  FREE_COPILOT_QUESTIONS,
  PRO_SUMMARY_MONTHLY_CAP,
  TRIAL_DAYS,
} from '@/lib/planLimits'
import { REFERRAL_BONUS } from '@/features/waitlist/lib/referral'

/**
 * Structural gate for free-tier plan copy (CLAUDE.md rules 4 and 12).
 *
 * The free summary and earnings-alert caps are defined once on the server
 * (backend/app/services/entitlements.py). Guest-facing copy cannot read the usage response, so
 * frontend/lib/planLimits.ts mirrors the two numbers — and this spec keeps the mirror honest:
 * (1) the mirrored values equal the backend constants; (2) no source file spells the caps out as
 * bare literals again ("5 summaries", "300 new summaries", "3 companies"), which is how the copy drifted before.
 *
 * The Pro trial's length is a claim of the same kind, with one difference: the backend's
 * PRO_TRIAL_DAYS defaults to 0 (backend/app/config.py), so the trial exists only while the UI flag
 * ENABLE_PRO_TRIAL and that setting are flipped together. So (3) the length is written only through
 * TRIAL_DAYS: no copy says "7 days" or a trial of any other typed length (digits, a number word, days or
 * weeks), whether as a literal or as a value spliced into JSX, a template or a `+` chain, and a spliced
 * value the reader cannot resolve where a length would stand fails; (4) every read of TRIAL_DAYS, under
 * whatever binding the file gives it, sits under a guard, where a guard is ENABLE_PRO_TRIAL itself or an
 * `&&` chain with a guard operand (directly, or through a const so derived, resolved to the declaration
 * the name binds to), never a negation, an `||`, a `??`, a ternary's else, a comparison, a `let` or a
 * parameter, each of which can be true with the flag off; and (5) TRIAL_DAYS is the value the flag's own
 * documentation and the backend name for the flip. Clauses (3) and (4) read every .ts, .tsx, .js and .jsx
 * file under the cap walk's roots (an .md or .mdx file there is read as copy, line by line), one reader per
 * file (trialReader, below, says what it follows). Out of reach, review-checked: a length said another way
 * ("a week", "a fortnight"), TRIAL_DAYS re-exported under another name by another module, and a guard
 * applied by an early return (`if (!ENABLE_PRO_TRIAL) return null`), which fails closed.
 */
const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const entitlements = readFileSync(path.resolve(frontendDir, '../backend/app/services/entitlements.py'), 'utf8')

const backendConst = (name: string): number => {
  const match = entitlements.match(new RegExp(`^${name}\\s*=\\s*(\\d+)`, 'm'))
  if (!match) throw new Error(`${name} not found in backend/app/services/entitlements.py`)
  return Number(match[1])
}

// The waitlist's referral bonus is held the same way: REFERRAL_BONUS (features/waitlist/lib/referral.ts)
// equals the backend's, the success card reads it, and no copy types "5 spots" again (the page once said
// it twice while the referral link credited nobody).
const waitlistService = readFileSync(path.resolve(frontendDir, '../backend/app/services/waitlist_service.py'), 'utf8')

/** A field of the `_FREE = Entitlements(...)` literal, e.g. `copilot_free_taste=3,`. */
const freeEntitlementField = (name: string): number => {
  const block = entitlements.match(/_FREE = Entitlements\(([\s\S]*?)\n\)/)
  const match = block?.[1].match(new RegExp(`\\b${name}\\s*=\\s*(\\d+)`))
  if (!match) throw new Error(`${name} not found in the _FREE entitlements block`)
  return Number(match[1])
}

const SOURCE_ROOTS = ['app', 'features', 'components', 'lib', 'hooks']
const SUMMARY_CAP_LABEL = 'a summary cap spelled out'
const LITERAL_PATTERNS: Array<{ label: string; pattern: RegExp }> = [
  // Copy: the caps written out in prose. "new" is the Pro ceiling's form ("300 new summaries", PRO_FAIR_USE_LINE).
  { label: SUMMARY_CAP_LABEL, pattern: /\b\d+ (?:new )?(?:free )?(?:AI )?summar(?:y|ies)\b/i },
  { label: 'free summary cap as a numeric fallback', pattern: /summaries_limit\s*(?:\|\||\?\?)\s*\d+/ },
  { label: 'earnings-alert cap spelled out', pattern: /alerts for \d+ compan|\b\d+ earnings(?:-day)? alerts?\b/i },
  { label: 'free Copilot question taste spelled out', pattern: /\b\d+ (?:free )?Ask this Filing questions?\b|\bFree accounts get \d+ questions?\b/i },
  { label: 'free history retention spelled out', pattern: /\b\d+-day (?:summary )?history\b|\bFree keeps \d+ days\b/i },
  { label: 'waitlist referral bonus spelled out', pattern: /\b\d+ spots?\b/i },
  // Behaviour: a free-tier cap constant assigned a literal, or a count compared against one
  // (the calendar pre-flight and fixture checks drifted this way before the mirror existed).
  { label: 'free-tier cap constant assigned a literal', pattern: /\bFREE_[A-Z0-9_]*(?:LIMIT|CAP)\b\s*=\s*\d+/ },
  { label: 'count compared against a literal cap', pattern: /(?:currentCount\(\)|enabled\.size|alertCount|alertTickers\.size)\s*(?:>=|>|===|==)\s*\d+/ },
]

/** Files that enforce a cap functionally must take it from the mirror, not a local literal. */
const FUNCTIONAL_CAP_SITES = [
  'features/calendar/hooks/useCalendar.ts',
  'features/calendar/api/calendar-fixtures.ts',
  'features/calendar/components/AlertBell.tsx',
  'app/dashboard/page.tsx',
]

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = path.join(dir, entry)
    if (entry === 'node_modules' || entry === '.next') return []
    if (statSync(full).isDirectory()) return walk(full)
    return /\.(tsx?|jsx?|mdx?)$/.test(entry) ? [full] : []
  })
}

describe('free-tier plan limits move in lockstep with the backend', () => {
  it('mirrors FREE_TIER_SUMMARY_LIMIT', () => {
    expect(FREE_SUMMARY_LIMIT).toBe(backendConst('FREE_TIER_SUMMARY_LIMIT'))
  })

  it('mirrors FREE_EARNINGS_ALERT_LIMIT', () => {
    expect(FREE_EARNINGS_ALERT_LIMIT).toBe(backendConst('FREE_EARNINGS_ALERT_LIMIT'))
  })

  it('mirrors the free Copilot taste, and the Pro fair-use ceiling PRO_FAIR_USE_LINE states (E58)', () => {
    expect(FREE_COPILOT_QUESTIONS).toBe(freeEntitlementField('copilot_free_taste'))
    expect(PRO_SUMMARY_MONTHLY_CAP).toBe(settingDefault('PRO_SUMMARY_MONTHLY_CAP'))
  })

  it('finds no deploy map that overrides PRO_SUMMARY_MONTHLY_CAP, so production runs the default the page states', () => {
    const workflows = readdirSync(WORKFLOWS)
      .filter((file) => /\.ya?ml$/.test(file))
      .map((file) => [file, readFileSync(path.join(WORKFLOWS, file), 'utf8')] as const)
    // Anti-vacuity: the read reaches the deploy's maps (ci.yml's service and job maps among them).
    const ci = workflows.find(([file]) => file === 'ci.yml')?.[1] ?? ''
    expect((ci.match(/--update-env-vars=/g) ?? []).length).toBeGreaterThanOrEqual(3)
    expect(capOverrides(config, workflows), CAP_STAYS_DEFAULT).toEqual([])
  })

  it('reads a cap setting in every form a workflow writes one, and nothing else (planted forms)', () => {
    const settings = `class Settings(BaseSettings):\n    ${CAP}: int = 300\n`
    // ci.yml's service map, shortened: the form the gate exists for.
    const serviceMap = '            --update-env-vars=ENVIRONMENT=production,COOKIE_DOMAIN=.earningsnerd.io,DB_POOL_SIZE=4,ENABLE_INSIDER_ACTIVITY=false \\'
    const flagged: Record<string, string> = {
      'the service map with the cap added': serviceMap.replace('DB_POOL_SIZE=4', `DB_POOL_SIZE=4,${CAP}=100`),
      'a fresh map': `            --set-env-vars=${CAP}=0 \\`,
      'an env: key': `          ${CAP}: "100"`,
      'a value the deploy expands': `            --update-env-vars=DB_POOL_SIZE=3,${CAP}=\${PRO_CAP} \\`,
      'a secret mapped onto it': `            --update-secrets=${CAP}=PRO_CAP:latest \\`,
      "the default's own value": `            --update-env-vars=${CAP}=300 \\`,
      'a run line': `        run: echo "${CAP}=150" >> "$GITHUB_ENV"`,
    }
    const passing: Record<string, string> = {
      'a comment': `  # ${CAP} stays at config.py's default: never set it here`,
      'the service map as it is': serviceMap,
      'another cap': '          COPILOT_MONTHLY_QUESTION_CAP: "1000"',
      'a gap: an env file the read cannot open': '            --env-vars-file=deploy/production.env.yaml \\',
    }
    const read = (line: string) => capOverrides(settings, [['ci.yml', line]]).length
    expect(Object.keys(flagged).filter((name) => read(flagged[name]) !== 1), 'a form the read missed').toEqual([])
    expect(Object.keys(passing).filter((name) => read(passing[name]) !== 0), 'a look-alike the read flagged').toEqual([])
    expect(capOverrides(settings, [['ops.yaml', `jobs:\n  sync:\n    env:\n      ${CAP}: "5"\n`]])).toEqual([`ops.yaml:4 ${CAP}: "5"`])
    expect(() => capOverrides('class Settings(BaseSettings):\n    OTHER: int = 1\n', [])).toThrow(/0 times/)
    expect(() => capOverrides(settings + settings, [])).toThrow(/2 times/)
  })

  it('mirrors the waitlist REFERRAL_BONUS, which the referral sentence reads', () => {
    const match = waitlistService.match(/^REFERRAL_BONUS\s*=\s*(\d+)/m)
    if (!match) throw new Error('REFERRAL_BONUS not found in backend/app/services/waitlist_service.py')
    expect(REFERRAL_BONUS).toBe(Number(match[1]))
    const form = readFileSync(path.join(frontendDir, 'features/waitlist/components/WaitlistForm.tsx'), 'utf8')
    expect(form).toMatch(/import \{ REFERRAL_BONUS \} from '@\/features\/waitlist\/lib\/referral'/)
    expect(form).toMatch(/\{REFERRAL_BONUS\} spots/)
  })

  it('functional cap sites import the mirrored constants', () => {
    for (const rel of FUNCTIONAL_CAP_SITES) {
      const source = readFileSync(path.join(frontendDir, rel), 'utf8')
      expect(source, `${rel} must import from '@/lib/planLimits'`).toMatch(/from '@\/lib\/planLimits'/)
    }
  })

  it('no source file spells a free-tier cap out as a bare literal', () => {
    const offenders: string[] = []
    for (const root of SOURCE_ROOTS) {
      for (const file of walk(path.join(frontendDir, root))) {
        if (file.endsWith(path.join('lib', 'planLimits.ts'))) continue
        const lines = readFileSync(file, 'utf8').split('\n')
        lines.forEach((line, index) => {
          for (const { label, pattern } of LITERAL_PATTERNS) {
            if (pattern.test(line)) offenders.push(`${path.relative(frontendDir, file)}:${index + 1} (${label}): ${line.trim()}`)
          }
        })
      }
    }
    expect(offenders, 'use the mirrored constants (lib/planLimits; REFERRAL_BONUS from features/waitlist/lib/referral) instead').toEqual([])
  })

  it('reads a summary cap typed with or without "new", the Pro ceiling\'s form (planted forms)', () => {
    const { pattern } = LITERAL_PATTERNS.find(({ label }) => label === SUMMARY_CAP_LABEL)!
    for (const typed of ['5 summaries', '5 free summaries', '5 AI summaries', 'Pro accounts can generate up to 300 new summaries a month.']) {
      expect(pattern.test(typed), typed).toBe(true)
    }
    // A read of the cap types no number: summaryPlanClaims.spec.ts fails a read of it outside lib/planLimits.ts.
    for (const prose of ['Pro accounts can generate up to {PRO_SUMMARY_MONTHLY_CAP} new summaries a month.', 'New summaries are paused.', 'Unlimited summaries']) {
      expect(pattern.test(prose), prose).toBe(false)
    }
  })

  // Pro's Copilot questions are capped (COPILOT_MONTHLY_QUESTION_CAP, a fair-use 429 past it), so no copy
  // offers "unlimited" questions (ASK-03, D-034). The cap is read from the usage response (qa_limit), never
  // typed. The Copilot's own surfaces carry no "unlimited" at all; everywhere else under the source roots
  // (pricing, marketing, the upgrade surfaces, any page) "unlimited" stays off a question noun within one
  // literal (a string, JSX text, a template with its parts joined; a markdown file's paragraph) or one element's
  // inline children read together (`<li>Unlimited <strong>Ask this Filing</strong> questions</li>`), its
  // whitespace collapsed so a wrapped line reads as one. "Unlimited" heads a list read to the sentence end, and
  // an item of it that names a question, answer, Ask this Filing, Copilot or Q&A noun and no count of its own
  // fails ("unlimited follow-up questions", "Unlimited, cited answers", "unlimited 10-K and 10-Q analysis,
  // exports, and filing Q&A"), while an item with its own count passes ("Unlimited summaries and 1,000
  // questions a month"); so does such a noun up to 30 characters before "unlimited" in the same sentence
  // ("Answers: unlimited on Pro"). A claim split across separate literals (two array items, a template's
  // substitution) is out of its reach and review-checked (whether Pro summaries stay "unlimited" is a founder
  // decision, pub/F05, and F41 keeps it on the plan cards, so that clause is not here).
  const COPILOT_DIR = path.join('features', 'filings', 'components', 'copilot')
  const NOUN = String.raw`(?:questions?|answers?|copilot|ask this filing|q&a)(?![\w&])`
  const NOUN_THEN_UNLIMITED = new RegExp(String.raw`\b${NOUN}[^.]{0,30}\bunlimited\b`, 'i')
  const NAMES_NOUN = new RegExp(String.raw`\b${NOUN}`, 'i')
  /** True when a text offers unlimited questions: a question noun shortly before "unlimited", or a list "unlimited" heads,
      read to the end of its sentence, with an item that names a question noun and carries no count of its own. */
  const promisesUnlimited = (text: string) =>
    NOUN_THEN_UNLIMITED.test(text) ||
    text.split(/(?<=[.!?])\s+/).some((sentence) => {
      const at = sentence.search(/\bunlimited\b/i)
      if (at < 0) return false
      const items = sentence.slice(at + 'unlimited'.length).split(/[,;]|\b(?:and|or|plus|with)\b/i)
      return items.some((item) => NAMES_NOUN.test(item) && !/\d/.test(item))
    })

  interface Held {
    line: number
    text: string
    /** An element's run: the texts of its children, each read alone first, so the run reports only what no child says. */
    parts?: string[]
  }

  /** Each literal a file holds, whitespace collapsed, with the line it starts on: a string, JSX text or a template
      with its parts joined (a markdown file's paragraph), so neighbouring array items never join; and each element's
      inline children read together, JSX text, a nested element's run and a string an expression holds (any other
      expression reads as a space). */
  function literals(file: string, source: string): Held[] {
    if (/\.mdx?$/.test(file)) {
      let line = 1
      return source.split(/\n\s*\n/).map((paragraph) => {
        const at = { line, text: paragraph.replace(/\s+/g, ' ') }
        line += paragraph.split('\n').length + 1
        return at
      })
    }
    const kind = file.endsWith('.tsx') ? ts.ScriptKind.TSX : file.endsWith('.jsx') ? ts.ScriptKind.JSX : file.endsWith('.js') ? ts.ScriptKind.JS : ts.ScriptKind.TS
    const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, kind)
    const out: Held[] = []
    const lineOf = (n: ts.Node) => sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1
    const childText = (child: ts.JsxChild): string => {
      if (ts.isJsxText(child)) return child.text
      if (ts.isJsxElement(child)) return child.children.map(childText).join('')
      if (ts.isJsxExpression(child) && child.expression) {
        let value = child.expression
        while (ts.isParenthesizedExpression(value) || ts.isAsExpression(value)) value = value.expression
        if (ts.isStringLiteral(value) || ts.isNoSubstitutionTemplateLiteral(value)) return value.text
      }
      return ' '
    }
    const visit = (n: ts.Node) => {
      let text: string | null = null
      if (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n) || ts.isJsxText(n)) text = n.text
      else if (ts.isTemplateExpression(n)) text = [n.head.text, ...n.templateSpans.map((span) => span.literal.text)].join(' ')
      if (text !== null) out.push({ line: lineOf(n), text: text.replace(/\s+/g, ' ') })
      if (ts.isJsxElement(n) && n.children.length > 1) {
        const parts = n.children.map((child) => childText(child).replace(/\s+/g, ' '))
        out.push({ line: lineOf(n), text: parts.join('').replace(/\s+/g, ' '), parts })
      }
      ts.forEachChild(n, visit)
    }
    visit(sf)
    return out
  }

  /** The held texts that offer unlimited questions: a literal, or an element's run that no child of it says alone. */
  const offers = (held: Held[]) => held.filter(({ text, parts }) => promisesUnlimited(text) && !(parts ?? []).some(promisesUnlimited))

  // Every source file under the roots, read and parsed once, before any one test's timeout starts.
  const SCANNED = SOURCE_ROOTS.flatMap((root) => walk(path.join(frontendDir, root))).map((file) => {
    const source = readFileSync(file, 'utf8')
    return { file, rel: path.relative(frontendDir, file), source, literals: literals(file, source) }
  })

  it('no Copilot or plan surface promises unlimited questions', () => {
    const offenders: string[] = []
    const scanned = new Set<string>()
    let copilotFiles = 0
    for (const { rel, source, literals: held } of SCANNED) {
      scanned.add(rel.split(path.sep).join('/'))
      if (rel.startsWith(COPILOT_DIR + path.sep)) {
        copilotFiles += 1
        source.split('\n').forEach((line, index) => {
          if (/\bunlimited\b/i.test(line)) offenders.push(`${rel}:${index + 1}: ${line.trim()}`)
        })
      } else {
        for (const { line, text } of offers(held)) offenders.push(`${rel}:${line}: ${text.trim()}`)
      }
    }
    // The scan reaches the plan surfaces outside the Copilot and subscription directories, not only those two.
    expect(copilotFiles, 'the scan reads the Copilot directory').toBeGreaterThan(10)
    for (const rel of ['app/pricing/page.tsx', 'app/pricing/layout.tsx', 'features/marketing/components/PricingSection.tsx', 'features/subscriptions/components/UpgradeModal.tsx']) {
      expect(scanned.has(rel), rel).toBe(true)
    }
    expect(offenders, "say what the plan includes, from the usage response: `Pro includes ${usage.qa_limit} questions a month.`").toEqual([])
  })

  it('the question clause reads a literal or an element\'s run: modifiers, a comma, Q&A, answers, a list and a wrapped line (self-check)', () => {
    for (const claim of [
      'Pro includes unlimited follow-up questions.',
      'Unlimited filing Q&A with Pro',
      'Unlimited Ask this Filing questions',
      'Pro includes unlimited\n            questions a month.',
      'Ask this Filing: unlimited on Pro',
      // A comma, a third modifier, and an answer noun before "unlimited".
      'Unlimited, cited answers',
      'Pro includes unlimited plain-English follow-up filing questions.',
      'Answers are unlimited on Pro',
      // The forms the review of c30e4f6d planted, and the pricing metadata's two sentences as #1311 shipped them.
      'Answers: unlimited on Pro',
      'Unlimited summaries, filing Q&A and exports',
      'go Pro for unlimited 10-K and 10-Q analysis, exports, and filing Q&A.',
      'Unlimited AI summaries of SEC 10-K and 10-Q filings, multi-period analysis, filing Q&A, alerts, and exports.',
    ]) {
      expect(promisesUnlimited(literals('claim.ts', JSON.stringify(claim))[0].text), claim).toBe(true)
    }
    for (const allowed of [
      'Unlimited summaries', 'Pro includes 1,000 questions a month.', 'Unlimited Multi-Period Analysis', 'Watchlists are unlimited on both plans.',
      // An item with its own count, and the metadata as it now reads: filing Q&A in a sentence "unlimited" does not head.
      'Unlimited summaries and 1,000 questions a month.',
      'EarningsNerd plans: free AI summaries of SEC filings every month, or go Pro for unlimited 10-K and 10-Q analysis and exports. Pro also includes filing Q&A.',
    ]) {
      expect(promisesUnlimited(allowed), allowed).toBe(false)
    }
    // Neighbouring array items are separate literals: "Unlimited watchlist" beside the questions line is no claim. An
    // element's run reads as one text, reported once, at the innermost element no child of which says it alone.
    const planted = literals('planted.tsx', [
      'const PRO = [',
      "  'Ask this Filing questions, 1,000 a month',",
      "  'Unlimited watchlist',",
      "  `Unlimited ${'follow-up'} questions`,",
      ']',
      'export const L = () => <ul><li>Unlimited <strong>Ask this Filing</strong> questions</li><li>Unlimited watchlist</li></ul>',
    ].join('\n'))
    expect(offers(planted).map(({ line, text }) => `${line} ${text.trim()}`)).toEqual([
      '4 Unlimited questions',
      '6 Unlimited Ask this Filing questions',
    ])
  })
})

/**
 * Multi-Period Analysis period caps (the /analysis metadata and lead, the landing's feature row, the
 * /pricing Pro card). The backend's Settings defaults (backend/app/config.py: ANALYSIS_MAX_ANNUAL_PERIODS,
 * ANALYSIS_MAX_QUARTERLY_PERIODS) are the truth the picker reads from the coverage response; copy that
 * renders before it takes the mirror in lib/planLimits.ts. So (1) the mirror equals the defaults, and
 * (2) no copy types a count of years or quarters outside the few that state a different fact
 * (PERIOD_COUNT_OTHER_FACTS).
 *
 * Copy is what a .ts or .tsx file under SOURCE_ROOTS writes as text, read through the AST (comments are
 * not copy): each string, template and `+` chain, and each JSX tree's text as React renders it. A tree's
 * text children lose the whitespace JSX drops and have their entities decoded (`&nbsp;`), and its literal
 * children (`{10}`, `{'10'}`, `{' '}`) and nested elements' text (`<strong>10</strong>`) are joined in
 * order, so a count split across markup reads whole. A part that is not a literal (a name, a call, a
 * condition) reads as a hole no count spans, which is how `{ANALYSIS_MAX_ANNUAL_PERIODS} fiscal years`
 * passes. A typed count is digits, a "+" allowed after them, or a number word up to twelve; then spaces or
 * hyphens (a no-break space and the Unicode hyphens among them); an optional "fiscal" or "financial"; then
 * year, quarter or an abbreviation (yr, qtr, FY, FQ), singular or plural (TYPED_PERIOD_COUNT).
 *
 * Outside the gate, left to review, each planted as a gap in PLANTED_FORMS: a count spelled past twelve or
 * as a phrase ("fifteen years", "a decade", "a dozen quarters"); another word between the count and its
 * unit ("10 calendar years", "10 or more years"); another unit ("10 annual periods", the shorthand "10Y");
 * and a count held in a name or chosen by a condition (`{annual ? 10 : 12} fiscal years`), which reads as
 * a hole. Model-written text is not copy: the demo payload's sample narrative
 * (features/analysis/demo/demo-analysis.json) states its own window, "six fiscal years", as a model would.
 */
const config = readFileSync(path.resolve(frontendDir, '../backend/app/config.py'), 'utf8')
const settingDefault = (name: string): number => {
  const match = config.match(new RegExp(`^\\s+${name}\\s*:\\s*int\\s*=\\s*(\\d+)`, 'm'))
  if (!match) throw new Error(`${name} not found in backend/app/config.py`)
  return Number(match[1])
}

/**
 * Production runs the Pro cap the page states. The /pricing FAQ and the filing page's limit card state
 * PRO_SUMMARY_MONTHLY_CAP's Settings default through the mirror (lib/planLimits.ts), while the backend enforces
 * `settings.PRO_SUMMARY_MONTHLY_CAP`, which an environment value overrides. So no deploy map sets it. The read
 * takes the default from backend/app/config.py (declared once, or the read throws) and every executable line of
 * every workflow under .github/workflows: a comment line is skipped, and any other line that names the variable
 * counts, whatever its form (an --update-env-vars, --set-env-vars or --update-secrets entry, an env: key, a run
 * line) and whatever its value (the default's own value too: the map would keep it when the default moves). Its
 * planted forms score the read. Out of reach: a value set by hand on the Cloud Run service, which no file records,
 * an env file a deploy names (`--env-vars-file`, none today) and an image's own ENV (backend/Dockerfile sets
 * none of it).
 */
const CAP = 'PRO_SUMMARY_MONTHLY_CAP'
const WORKFLOWS = path.resolve(frontendDir, '../.github/workflows')
const CAP_STAYS_DEFAULT =
  `The /pricing FAQ and the filing page's limit card state config.py's ${CAP} default (lib/planLimits.ts mirrors ` +
  'it), so a deploy map that sets it leaves the page stating a ceiling the backend does not enforce. Change the ' +
  'default in backend/app/config.py, and the mirror follows; never override it in a deploy map.'

/** The executable workflow lines that name PRO_SUMMARY_MONTHLY_CAP, as `file:line text`. Throws unless config.py
    declares the cap's default once, so a renamed or moved field cannot leave the read holding nothing. */
function capOverrides(configSource: string, workflows: ReadonlyArray<readonly [string, string]>): string[] {
  const defaults = configSource.match(new RegExp(`^\\s*${CAP}\\s*:\\s*int\\s*=\\s*\\d+`, 'gm')) ?? []
  if (defaults.length !== 1) throw new Error(`config.py declares ${CAP}'s default ${defaults.length} times, not once`)
  return workflows.flatMap(([file, text]) =>
    text.split('\n').flatMap((line, i) => (line.trimStart().startsWith('#') || !line.includes(CAP) ? [] : [`${file}:${i + 1} ${line.trim()}`])),
  )
}

const NUMBER_WORDS = 'one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve'
/** Spaces (`\s` reads a no-break space as one) and hyphens, the Unicode hyphens and dashes among them. */
const SEPARATOR = '[-\\u2010-\\u2015\\s]+'
const UNITS = 'years?|yrs?|quarters?|qtrs?|FYs?|FQs?'
const TYPED_PERIOD_COUNT_SOURCE = `\\b(?:\\d+\\+?|${NUMBER_WORDS})${SEPARATOR}(?:(?:fiscal|financial)${SEPARATOR})?(?:${UNITS})\\b`
/** Digits (a "+" allowed after them) or a number word, a separator, an optional "fiscal" or "financial", then a unit. */
const TYPED_PERIOD_COUNT = new RegExp(TYPED_PERIOD_COUNT_SOURCE, 'i')
/** Cheap raw-text prefilter: a file whose source never spells a unit has no copy the scan can flag, so it
 * skips the parse. Every TYPED_PERIOD_COUNT hit ends in a unit. */
const MENTIONS_A_PERIOD = new RegExp(`(?:${UNITS})\\b`, 'i')

/**
 * Copy that types a count of years for a fact other than the analysis caps. Keyed by file and phrase;
 * shrink-only: an entry whose phrase no longer holds a typed count in its file's copy fails the spec
 * (delete it, and lower PERIOD_COUNT_OTHER_FACTS_MAX in the same commit), and the table's length equals
 * PERIOD_COUNT_OTHER_FACTS_MAX, an equality and never a ceiling (D-040;
 * lessons/test-allowlist-caps-are-equalities.md). A new hit is written from the mirror; one that states
 * another fact is argued in here with the cap raised in the same reviewed diff.
 */
const PERIOD_COUNT_OTHER_FACTS_MAX = 6
const PERIOD_COUNT_OTHER_FACTS: Array<{ file: string; phrase: string; why: string }> = [
  // The privacy policy's retention periods: how long data is kept, not how far back analysis reaches.
  // A legal page (it imports LEGAL_DATES), off limits without the founder.
  { file: 'app/privacy/page.tsx', phrase: 'after 2 years of inactivity', why: 'account-data retention period' },
  { file: 'app/privacy/page.tsx', phrase: 'Retained for 1 year from the search date', why: 'search-history retention period' },
  { file: 'app/privacy/page.tsx', phrase: 'Retained for 1 year from submission date', why: 'contact-form retention period' },
  { file: 'app/privacy/page.tsx', phrase: 'Retained for 1 year from signup date', why: 'waitlist retention period' },
  { file: 'app/privacy/page.tsx', phrase: 'Retained for 7 years from transaction date', why: 'billing-record retention (tax law)' },
  { file: 'app/privacy/page.tsx', phrase: 'retained for 7 years for tax compliance', why: 'billing-record retention (tax law)' },
]

/** Rendered copy: its text, and for each UTF-16 unit of it the source position it was read from. */
type Rendered = { text: string; at: number[] }
/** What a part that is not a literal renders as: no digit, letter, space or hyphen, so no count spans it. */
const HOLE = '\ufffc'
const join = (parts: readonly Rendered[]): Rendered =>
  ({ text: parts.map((part) => part.text).join(''), at: parts.flatMap((part) => part.at) })
/** A literal's text read from `from` on (an escape shifts the positions after it by a character or two). */
const literal = (text: string, from: number, last: number): Rendered =>
  ({ text, at: Array.from({ length: text.length }, (_, index) => Math.min(from + index, last)) })

const ENTITIES: Record<string, string> = {
  nbsp: '\u00a0', ensp: '\u2002', emsp: '\u2003', thinsp: '\u2009', hyphen: '\u2010', dash: '\u2010',
  ndash: '\u2013', mdash: '\u2014', amp: '&', lt: '<', gt: '>', quot: '"', apos: "'",
}
const ENTITY = /^&(?:#(\d{1,7})|#x([\da-f]{1,6})|([a-z]+));/i
/** JSX text or a JSX attribute string as written from source position `from`, its entities decoded. */
function decoded(text: string, from: number): Rendered {
  const out: Rendered = { text: '', at: [] }
  for (let index = 0; index < text.length;) {
    const entity = text[index] === '&' ? ENTITY.exec(text.slice(index)) : null
    const point = entity && (entity[1] ? Number(entity[1]) : entity[2] ? parseInt(entity[2], 16) : null)
    const char = !entity ? undefined
      : point !== null ? (point <= 0x10ffff ? String.fromCodePoint(point) : undefined)
        : ENTITIES[entity[3].toLowerCase()]
    const value = char ?? text[index]
    out.text += value
    for (let unit = 0; unit < value.length; unit++) out.at.push(from + index)
    index += char === undefined ? 1 : entity![0].length
  }
  return out
}

/** A JSX text child as React renders it (Babel's rule): each line trimmed where it meets a line break,
 * blank lines dropped, the rest joined by one space; its entities decoded. */
function jsxText(node: ts.JsxText, sf: ts.SourceFile): Rendered {
  const lines: Array<{ from: number; text: string }> = []
  let from = node.pos
  sf.text.slice(node.pos, node.end).split(/(\r\n|\n|\r)/).forEach((part, index) => {
    if (index % 2 === 0) lines.push({ from, text: part })
    from += part.length
  })
  const lastWithText = lines.reduce((found, line, index) => (/[^ \t]/.test(line.text) ? index : found), 0)
  const parts: Rendered[] = []
  lines.forEach((line, index) => {
    let start = 0
    let end = line.text.length
    if (index > 0) while (start < end && /[ \t]/.test(line.text[start])) start++
    if (index < lines.length - 1) while (end > start && /[ \t]/.test(line.text[end - 1])) end--
    if (start === end) return
    parts.push(decoded(line.text.slice(start, end), line.from + start))
    if (index !== lastWithText) parts.push({ text: ' ', at: [line.from + end] })
  })
  return join(parts)
}

type Wrapper = ts.ParenthesizedExpression | ts.AsExpression | ts.SatisfiesExpression | ts.NonNullExpression | ts.TypeAssertion
const isWrapper = (node: ts.Node): node is Wrapper => ts.isParenthesizedExpression(node) || ts.isAsExpression(node)
  || ts.isSatisfiesExpression(node) || ts.isNonNullExpression(node) || ts.isTypeAssertionExpression(node)
const isConcat = (node: ts.Node): node is ts.BinaryExpression =>
  ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken

/** What a node renders as text: its literals and JSX read through, any other part a hole. */
function rendered(node: ts.Node, sf: ts.SourceFile): Rendered {
  if (isWrapper(node)) return rendered(node.expression, sf)
  if (ts.isStringLiteral(node) && ts.isJsxAttribute(node.parent)) return decoded(node.text, node.getStart(sf) + 1)
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isTemplateHead(node)
    || ts.isTemplateMiddle(node) || ts.isTemplateTail(node)) return literal(node.text, node.getStart(sf) + 1, node.end - 1)
  if (ts.isNumericLiteral(node)) return literal(node.text, node.getStart(sf), node.end - 1)
  if (ts.isTemplateExpression(node)) {
    return join([node.head, ...node.templateSpans.flatMap((span) => [span.expression, span.literal])].map((part) => rendered(part, sf)))
  }
  if (isConcat(node)) return join([rendered(node.left, sf), rendered(node.right, sf)])
  if (ts.isJsxElement(node) || ts.isJsxFragment(node)) return join(node.children.map((child) => rendered(child, sf)))
  if (ts.isJsxText(node)) return jsxText(node, sf)
  if (ts.isJsxExpression(node)) return node.expression ? rendered(node.expression, sf) : { text: '', at: [] }
  return { text: HOLE, at: [node.getStart(sf)] }
}

/** A node its parent renders as part of its own text: a `+` operand, a template's substitution, or a JSX
 * tree's child, bare or in braces, through any parentheses or casts. So each part of copy is read once. */
function renderedByParent(node: ts.Node): boolean {
  let parent = node.parent
  while (parent && isWrapper(parent)) parent = parent.parent
  if (!parent) return false
  if (isConcat(parent) || ts.isTemplateSpan(parent) || ts.isJsxElement(parent) || ts.isJsxFragment(parent)) return true
  return ts.isJsxExpression(parent) && (ts.isJsxElement(parent.parent) || ts.isJsxFragment(parent.parent))
}

/** Every piece of copy in one source: each string, template, `+` chain and JSX tree that no other renders. */
function copyTexts(sf: ts.SourceFile): Rendered[] {
  const out: Rendered[] = []
  const visit = (node: ts.Node) => {
    if ((ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isTemplateExpression(node)
      || isConcat(node) || ts.isJsxElement(node) || ts.isJsxFragment(node)) && !renderedByParent(node)) {
      out.push(rendered(node, sf))
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out
}

/** Whether an occurrence of `phrase` in `text` spans the range [start, end). */
function covers(text: string, phrase: string, start: number, end: number): boolean {
  for (let at = text.indexOf(phrase); at >= 0 && at <= start; at = text.indexOf(phrase, at + 1)) {
    if (end <= at + phrase.length) return true
  }
  return false
}

/** Each typed count in one source's copy, as `file:line: context`, less those inside a phrase that
 * PERIOD_COUNT_OTHER_FACTS argues for the file; `argued` collects every entry that covers one. */
function typedPeriodCounts(source: string, rel: string, argued = new Set<number>()): string[] {
  if (!MENTIONS_A_PERIOD.test(source)) return []
  const sf = ts.createSourceFile(rel, source, ts.ScriptTarget.Latest, true, rel.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const found: string[] = []
  for (const copy of copyTexts(sf)) {
    for (const match of copy.text.matchAll(new RegExp(TYPED_PERIOD_COUNT_SOURCE, 'gi'))) {
      const start = match.index
      const end = start + match[0].length
      const covering = PERIOD_COUNT_OTHER_FACTS.flatMap((entry, index) =>
        (entry.file === rel && covers(copy.text, entry.phrase, start, end) ? [index] : []))
      covering.forEach((index) => argued.add(index))
      if (covering.length) continue
      const line = sf.getLineAndCharacterOfPosition(copy.at[start]).line + 1
      const context = copy.text.slice(Math.max(0, start - 40), end + 40).replaceAll(HOLE, '{…}').replace(/\s+/g, ' ').trim()
      found.push(`${rel}:${line}: ${context}`)
    }
  }
  return found
}

/**
 * The rule's forms, scored on every run (lessons/test-gates-must-be-as-wide-as-their-rule.md): a `flag`
 * source holds exactly one typed count, a `clean` look-alike none, and a `gap` breaks the rule in a form
 * the header leaves to review, so the scan reads none in it either. Each new form a review names joins here.
 */
const PLANTED_FORMS: Array<{ kind: 'flag' | 'clean' | 'gap'; form: string; source: string }> = [
  { kind: 'flag', form: 'a string', source: "export const copy = 'Compare up to 12 quarters'" },
  { kind: 'flag', form: 'JSX text', source: 'export const copy = <p>Up to 10 fiscal years</p>' },
  { kind: 'flag', form: 'JSX text over two lines', source: 'export const copy = (\n  <p>\n    Compare up to 10\n    fiscal years\n  </p>\n)' },
  { kind: 'flag', form: 'a JSX attribute string', source: 'export const copy = <Row description="Up to 10 fiscal years" />' },
  { kind: 'flag', form: "a template's static part", source: 'export const copy = `Up to ${n} companies and 10 years`' },
  { kind: 'flag', form: 'the count in emphasis markup', source: 'export const copy = <p>Up to <strong>10</strong> fiscal years</p>' },
  { kind: 'flag', form: 'a number word in markup, in a fragment', source: 'export const copy = <>Up to <em>ten</em> years</>' },
  { kind: 'flag', form: 'the qualifier in markup', source: 'export const copy = <p>Up to 10 <em>fiscal</em> years</p>' },
  { kind: 'flag', form: 'a hyphenated count in markup', source: 'export const copy = <p><span className="font-data">10</span>-year trends</p>' },
  { kind: 'flag', form: 'a numeric literal child', source: 'export const copy = <p>{10} fiscal years</p>' },
  { kind: 'flag', form: 'a string literal child', source: "export const copy = <p>Up to {'10'} fiscal years</p>" },
  { kind: 'flag', form: "a {' '} child between markup and the unit", source: "export const copy = <p>Up to <b>10</b>{' '}fiscal years</p>" },
  { kind: 'flag', form: 'a template child with a literal substitution', source: 'export const copy = <p>{`Up to ${10}`} fiscal years</p>' },
  { kind: 'flag', form: 'a parenthesized cast child', source: "export const copy = <p>{('10' as string)} years</p>" },
  { kind: 'flag', form: 'a + chain', source: "export const copy = 'Up to ' + 10 + ' fiscal years'" },
  { kind: 'flag', form: 'a template substitution of a literal', source: 'export const copy = `${12} quarters`' },
  { kind: 'flag', form: 'a no-break space entity', source: 'export const copy = <p>Up to 10&nbsp;years</p>' },
  { kind: 'flag', form: 'a numeric entity in an attribute', source: 'export const copy = <Row title="12&#160;quarters" />' },
  { kind: 'flag', form: 'a non-breaking hyphen', source: "export const copy = '10\\u2011year trends'" },
  { kind: 'flag', form: 'a count with a plus', source: 'export const copy = <p>10+ years of filings</p>' },
  { kind: 'flag', form: 'yrs', source: "export const copy = '10 yrs of history'" },
  { kind: 'flag', form: 'FYs', source: "export const copy = 'the last 10 FYs'" },
  { kind: 'flag', form: 'qtrs', source: "export const copy = 'the last 12 qtrs'" },
  { kind: 'flag', form: 'FQs', source: "export const copy = 'the last 12 FQs'" },
  { kind: 'flag', form: "a condition's literal branch", source: "export const copy = <p>{annual ? '10 fiscal years' : null}</p>" },
  { kind: 'flag', form: 'a tree behind &&', source: 'export const copy = <div>{open && <p>Up to 10 years</p>}</div>' },
  { kind: 'clean', form: 'the mirror in JSX', source: 'export const copy = <p>Up to {ANALYSIS_MAX_ANNUAL_PERIODS} fiscal years</p>' },
  { kind: 'clean', form: 'the mirror in a template', source: 'export const copy = `Unlimited Multi-Period Analysis: ${ANALYSIS_MAX_ANNUAL_PERIODS}-year trends`' },
  { kind: 'clean', form: 'the mirror in markup', source: 'export const copy = <p>Up to <strong>{ANALYSIS_MAX_QUARTERLY_PERIODS}</strong> quarters</p>' },
  { kind: 'clean', form: 'a live count', source: 'export const copy = <p>Showing {shown} of {total} quarters</p>' },
  { kind: 'clean', form: 'period labels', source: 'export const copy = <p>FY2025 results · Q3 2025 · Q1 FY 2025</p>' },
  { kind: 'clean', form: 'form names', source: "export const copy = '10-K and 10-Q filings'" },
  { kind: 'clean', form: 'units with no count', source: 'export const copy = <p>Fiscal year · year-over-year · quarterly deltas · yearly billing</p>' },
  { kind: 'clean', form: 'a comment', source: '// Up to 10 fiscal years\nexport const copy = null' },
  { kind: 'clean', form: 'a count and a unit in blocks on their own lines', source: 'export const copy = (\n  <ul>\n    <li>10</li>\n    <li>years</li>\n  </ul>\n)' },
  { kind: 'clean', form: 'a count of something else', source: "export const copy = '10 filings a year, $10 per year'" },
  { kind: 'gap', form: 'a number word past twelve', source: "export const copy = 'fifteen years of filings'" },
  { kind: 'gap', form: 'a decade', source: "export const copy = 'a decade of filings'" },
  { kind: 'gap', form: 'a dozen', source: "export const copy = 'a dozen quarters'" },
  { kind: 'gap', form: 'another word between count and unit', source: "export const copy = '10 calendar years, 10 or more years'" },
  { kind: 'gap', form: 'another unit', source: "export const copy = '10 annual periods'" },
  { kind: 'gap', form: 'finance shorthand', source: "export const copy = '10Y revenue trend'" },
  { kind: 'gap', form: 'a count held in a name', source: 'const N = 10\nexport const copy = <p>{N} fiscal years</p>' },
  { kind: 'gap', form: 'a count chosen by a condition', source: 'export const copy = <p>{annual ? 10 : 12} fiscal years</p>' },
]

describe('Multi-Period Analysis period caps move in lockstep with the backend', () => {
  it('mirrors ANALYSIS_MAX_ANNUAL_PERIODS and ANALYSIS_MAX_QUARTERLY_PERIODS', () => {
    expect(ANALYSIS_MAX_ANNUAL_PERIODS).toBe(settingDefault('ANALYSIS_MAX_ANNUAL_PERIODS'))
    expect(ANALYSIS_MAX_QUARTERLY_PERIODS).toBe(settingDefault('ANALYSIS_MAX_QUARTERLY_PERIODS'))
  })

  it('the pattern reads every way a period count is typed, and only those', () => {
    for (const typed of ['10 fiscal years', 'up to ten fiscal years', '12 quarters', 'twelve fiscal quarters',
      '10-year trends', '10-fiscal-year window', 'ten-year', '12-quarter view', '5 years', '1 year', '3 financial years',
      '10+ years', '10 yrs', '1 yr', '10 FYs', '12 qtrs', '12 FQs', '10\u00a0years', '10\u2011year trends']) {
      expect(TYPED_PERIOD_COUNT.test(typed), typed).toBe(true)
      expect(MENTIONS_A_PERIOD.test(typed), `prefilter keeps ${typed}`).toBe(true)
    }
    for (const prose of ['fiscal years', 'quarterly deltas', 'Fiscal year', 'year-over-year', '10-K and 10-Q',
      '-year trends, quarterly deltas', 'FY2025', 'Q3 2025', 'Q1 FY 2025', 'yearly billing', 'often years', 'canine years']) {
      expect(TYPED_PERIOD_COUNT.test(prose), prose).toBe(false)
    }
  })

  it('scores the planted forms: one typed count in each form it names, none in a look-alike or a named gap', () => {
    const misread = PLANTED_FORMS.flatMap(({ kind, form, source }) => {
      const hits = typedPeriodCounts(source, 'planted.tsx')
      return hits.length === (kind === 'flag' ? 1 : 0) ? [] : [`${kind} (${form}): ${JSON.stringify(hits)}`]
    })
    expect(misread).toEqual([])
    for (const kind of ['flag', 'clean', 'gap'] as const) expect(PLANTED_FORMS.some((form) => form.kind === kind), kind).toBe(true)
  })

  it('no copy types a count of years or quarters', () => {
    const offenders: string[] = []
    const argued = new Set<number>()
    let read = 0
    for (const root of SOURCE_ROOTS) {
      for (const file of walk(path.join(frontendDir, root))) {
        if (!/\.tsx?$/.test(file) || /\.(spec|test)\.tsx?$|\.d\.ts$/.test(file)) continue
        read++
        const rel = path.relative(frontendDir, file).split(path.sep).join('/')
        offenders.push(...typedPeriodCounts(readFileSync(file, 'utf8'), rel, argued))
      }
    }
    expect(read, 'the scan reads the source tree').toBeGreaterThan(100)
    expect(offenders, 'write the caps from ANALYSIS_MAX_ANNUAL_PERIODS / ANALYSIS_MAX_QUARTERLY_PERIODS in lib/planLimits').toEqual([])
    const stale = PERIOD_COUNT_OTHER_FACTS.filter((_, index) => !argued.has(index)).map((entry) => `${entry.file}: ${entry.phrase}`)
    expect(stale, 'PERIOD_COUNT_OTHER_FACTS is shrink-only: delete the entries whose phrase holds no typed count').toEqual([])
    expect(PERIOD_COUNT_OTHER_FACTS.length, 'PERIOD_COUNT_OTHER_FACTS_MAX equals the table: lower it with a deleted entry; write a new count from the mirror')
      .toBe(PERIOD_COUNT_OTHER_FACTS_MAX)
  })

  it('the scan reads the files that state the caps', () => {
    for (const rel of ['app/analysis/page.tsx', 'features/analysis/components/AnalysisPageClient.tsx', 'features/marketing/components/ProDepth.tsx']) {
      expect(readFileSync(path.join(frontendDir, rel), 'utf8'), `${rel} states the caps from the mirror`).toMatch(/ANALYSIS_MAX_ANNUAL_PERIODS[\s\S]*ANALYSIS_MAX_QUARTERLY_PERIODS/)
    }
    // The /pricing Pro card lists ANALYSIS_LINES.pricingPro, typed once in lib/planLimits.ts (D-040).
    expect(readFileSync(path.join(frontendDir, 'lib/planLimits.ts'), 'utf8'), 'the Pro card states the annual cap from the mirror')
      .toMatch(/pricingPro: \{ text: `[^`]*\$\{ANALYSIS_MAX_ANNUAL_PERIODS\}-year trends/)
  })
})

/** A gap for an expression whose value the file does not state: never a digit, never a word. */
const GAP = '\u0000'

/**
 * One reader for both trial clauses, per file, following bindings rather than names:
 *  - TRIAL_DAYS is the import of `TRIAL_DAYS` from lib/planLimits under any local name, a namespace import's
 *    member (`P.TRIAL_DAYS`, `P['TRIAL_DAYS']`), one destructured from it, and a const holding any of those.
 *    A local declaration of the same name shadows it, as the language does.
 *  - A guard is ENABLE_PRO_TRIAL (imported, or a namespace member), an `&&` chain with a guard operand, or a
 *    `const` whose initializer is a guard, resolved to the declaration a name binds to: a same-named const in
 *    another function is that function's own, and a `let` or a parameter is never a guard (it can be
 *    reassigned, or holds what a caller hands it).
 *  - Copy: every string literal and template, every `+` chain with a string in it, and each JSX root's whole
 *    text, read in order through its child elements, its `{…}` children (both branches of a ternary, the
 *    right side of `&&`, `||` and `??`) and the JSX entities and spaces it is written with. A spliced value
 *    reads as what it holds: a number (arithmetic and `String(…)` / `.toString()` / `Number(…)` evaluated), a
 *    string, a same-file const, TRIAL_DAYS itself (never a typed length), or, for anything the reader cannot
 *    resolve, a gap that fails where a trial length would stand (`{PLAN.trialDays}-day free trial`).
 */
const TRIAL = '\u0001'
const SPACE_FORMS = /&nbsp;|&#0*160;|&#x0*a0;|[\u00a0\u2007\u2009\u202f]/gi
const HYPHEN_FORMS = /&#0*8209;|&#x0*2011;|[\u2010\u2011\u2012\u2013\u2212]/gi
const TRIAL_NUMBER_WORDS = 'one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|twenty|thirty'
/** A length: digits or a number word at a word's start, or a value the reader could not resolve. */
const LENGTH = `(?:\\b(?:\\d+|${TRIAL_NUMBER_WORDS})|${GAP})`

const normalized = (raw: string) => raw.replace(SPACE_FORMS, ' ').replace(HYPHEN_FORMS, '-').replace(/\s+/g, ' ')
/** Where a piece of copy types a trial length (an index in its normalized text), or -1: the trial's own
    "7 days", or any length in days or weeks (digits, a number word, or a value the reader could not
    resolve) beside "trial" or "days free". A count of what is left ("{n} days left in your Pro trial", the
    billing countdown) is not a length. */
function trialLengthAt(raw: string): number {
  const text = normalized(raw)
  const own = text.search(new RegExp(`\\b${TRIAL_DAYS}[- ]days?\\b`, 'i'))
  if (own >= 0) return own
  if (!/\btrial\b|\bdays? free\b|\bweeks? free\b/i.test(text)) return -1
  return text.search(new RegExp(`${LENGTH}[- ](?:days?|weeks?)\\b(?! (?:left|remaining|ago)\\b)`, 'i'))
}
const typesTrialLength = (raw: string) => trialLengthAt(raw) >= 0
/** The words around the length a piece of copy types, for a failure message. */
const aroundLength = (raw: string) => {
  const text = normalized(raw)
  const at = trialLengthAt(raw)
  return `${at > 30 ? '…' : ''}${text.slice(Math.max(0, at - 30), at + 50).trim()}${at + 50 < text.length ? '…' : ''}`
}

const PLAN_LIMITS = /(?:^|\/)planLimits$/
const FEATURE_FLAGS = /(?:^|\/)featureFlags$/

interface TrialReader {
  /** Every read of TRIAL_DAYS in the file, with whether a guard holds over it. */
  reads: Array<{ line: number; guarded: boolean }>
  /** The copy the file writes that types a trial length. */
  typed: Array<{ line: number; text: string }>
}

const unwrapExpr = (e: ts.Expression): ts.Expression => {
  while (ts.isParenthesizedExpression(e) || ts.isAsExpression(e) || ts.isNonNullExpression(e) || ts.isSatisfiesExpression(e) || ts.isTypeAssertionExpression(e)) e = e.expression
  return e
}
const isConst = (decl: ts.Node): decl is ts.VariableDeclaration =>
  ts.isVariableDeclaration(decl) && !!(decl.parent.flags & ts.NodeFlags.Const)
/** An identifier in a reading position (not a declaration's or a property's name). */
const isReference = (id: ts.Identifier): boolean => {
  const p = id.parent
  if (ts.isImportSpecifier(p) || ts.isImportClause(p) || ts.isNamespaceImport(p) || ts.isImportEqualsDeclaration(p)) return false
  if ((ts.isPropertyAccessExpression(p) && p.name === id) || (ts.isQualifiedName(p) && p.right === id)) return false
  if ((ts.isPropertyAssignment(p) || ts.isPropertyDeclaration(p) || ts.isMethodDeclaration(p) || ts.isPropertySignature(p)) && p.name === id) return false
  if ((ts.isVariableDeclaration(p) || ts.isParameter(p) || ts.isFunctionDeclaration(p) || ts.isClassDeclaration(p)) && p.name === id) return false
  if (ts.isBindingElement(p) && (p.name === id || p.propertyName === id)) return false
  if (ts.isJsxAttribute(p) || ts.isExportSpecifier(p)) return false
  return true
}

export function trialReader(sf: ts.SourceFile): TrialReader {
  const resolve = bindingResolver(sf)
  const trialImports = new Set<string>()
  const flagImports = new Set<string>()
  const planNamespaces = new Set<string>()
  const flagNamespaces = new Set<string>()
  for (const statement of sf.statements) {
    if (!ts.isImportDeclaration(statement) || !statement.importClause || !ts.isStringLiteral(statement.moduleSpecifier)) continue
    const from = statement.moduleSpecifier.text
    const bindings = statement.importClause.namedBindings
    if (bindings && ts.isNamespaceImport(bindings)) {
      if (PLAN_LIMITS.test(from)) planNamespaces.add(bindings.name.text)
      if (FEATURE_FLAGS.test(from)) flagNamespaces.add(bindings.name.text)
    }
    if (bindings && ts.isNamedImports(bindings)) {
      for (const spec of bindings.elements) {
        const imported = (spec.propertyName ?? spec.name).text
        if (imported === 'TRIAL_DAYS' && PLAN_LIMITS.test(from)) trialImports.add(spec.name.text)
        if (imported === 'ENABLE_PRO_TRIAL') flagImports.add(spec.name.text)
      }
    }
  }
  const line = (node: ts.Node) => sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
  const memberOf = (e: ts.Expression, namespaces: Set<string>, name: string): boolean => {
    const x = unwrapExpr(e)
    if (ts.isPropertyAccessExpression(x)) return ts.isIdentifier(x.expression) && namespaces.has(x.expression.text) && x.name.text === name
    if (ts.isElementAccessExpression(x)) return ts.isIdentifier(x.expression) && namespaces.has(x.expression.text) && ts.isStringLiteralLike(x.argumentExpression) && x.argumentExpression.text === name
    return false
  }

  /** Whether an expression is TRIAL_DAYS itself: its import, a namespace member, or a const holding either. */
  const isTrial = (expr: ts.Expression, seen = new Set<ts.Node>()): boolean => {
    const e = unwrapExpr(expr)
    if (memberOf(e, planNamespaces, 'TRIAL_DAYS')) return true
    if (!ts.isIdentifier(e)) return false
    const binding = resolve(e)
    if (!binding) return trialImports.has(e.text)
    if (seen.has(binding.decl)) return false
    seen.add(binding.decl)
    // `const { TRIAL_DAYS: n } = P`: destructured from the namespace.
    if (ts.isBindingElement(binding.decl)) {
      const key = (binding.decl.propertyName ?? binding.decl.name).getText()
      const pattern = binding.decl.parent
      const holder = ts.isVariableDeclaration(pattern.parent) ? pattern.parent : undefined
      return key === 'TRIAL_DAYS' && !!holder?.initializer && isConst(holder) && ts.isIdentifier(unwrapExpr(holder.initializer)) &&
        planNamespaces.has((unwrapExpr(holder.initializer) as ts.Identifier).text)
    }
    return isConst(binding.decl) && !!binding.init && isTrial(binding.init, seen)
  }

  /** Whether an expression is true only while the flag is. */
  const isGuard = (expr: ts.Node, seen = new Set<ts.Node>()): boolean => {
    const e = ts.isExpression(expr) ? unwrapExpr(expr) : expr
    if (ts.isBinaryExpression(e) && e.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken) return isGuard(e.left, seen) || isGuard(e.right, seen)
    if (ts.isExpression(e) && memberOf(e, flagNamespaces, 'ENABLE_PRO_TRIAL')) return true
    if (!ts.isIdentifier(e)) return false
    const binding = resolve(e)
    if (!binding) return flagImports.has(e.text) || e.text === 'ENABLE_PRO_TRIAL'
    if (seen.has(binding.decl) || !isConst(binding.decl) || !binding.init) return false
    seen.add(binding.decl)
    return isGuard(binding.init, seen)
  }
  /** Whether a node renders only when a guard holds: inside `guard && …`, `guard ? … :`, or `if (guard) …`. */
  const guarded = (node: ts.Node): boolean => {
    for (let child = node, parent = node.parent; parent; child = parent, parent = parent.parent) {
      if (ts.isBinaryExpression(parent) && parent.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken && parent.right === child && isGuard(parent.left)) return true
      if (ts.isConditionalExpression(parent) && parent.whenTrue === child && isGuard(parent.condition)) return true
      if (ts.isIfStatement(parent) && parent.thenStatement === child && isGuard(parent.expression)) return true
    }
    return false
  }

  /** The number an expression holds, when the file says so (literals, arithmetic, consts, String/Number). */
  const numberOf = (expr: ts.Expression, seen = new Set<ts.Node>()): number | null => {
    const e = unwrapExpr(expr)
    if (ts.isNumericLiteral(e)) return Number(e.text)
    if (ts.isPrefixUnaryExpression(e) && (e.operator === ts.SyntaxKind.MinusToken || e.operator === ts.SyntaxKind.PlusToken)) {
      const n = numberOf(e.operand, seen)
      return n === null ? null : e.operator === ts.SyntaxKind.MinusToken ? -n : n
    }
    if (ts.isBinaryExpression(e)) {
      const [a, b] = [numberOf(e.left, seen), numberOf(e.right, seen)]
      if (a === null || b === null) return null
      switch (e.operatorToken.kind) {
        case ts.SyntaxKind.PlusToken: return a + b
        case ts.SyntaxKind.MinusToken: return a - b
        case ts.SyntaxKind.AsteriskToken: return a * b
        case ts.SyntaxKind.SlashToken: return a / b
        default: return null
      }
    }
    if (ts.isCallExpression(e) && ts.isIdentifier(e.expression) && /^(?:Number|parseInt|parseFloat)$/.test(e.expression.text) && e.arguments[0]) {
      const arg = unwrapExpr(e.arguments[0])
      return ts.isStringLiteralLike(arg) && arg.text.trim() !== '' && !Number.isNaN(Number(arg.text)) ? Number(arg.text) : numberOf(arg, seen)
    }
    if (ts.isIdentifier(e) && !isTrial(e)) {
      const binding = resolve(e)
      if (binding && isConst(binding.decl) && binding.init && !seen.has(binding.decl)) return numberOf(binding.init, new Set([...seen, binding.decl]))
    }
    return null
  }

  const MAX_READINGS = 16
  const product = (parts: string[][]): string[] => {
    let out = ['']
    for (const options of parts) {
      out = out.flatMap((head) => options.map((option) => head + option))
      if (out.length > MAX_READINGS) out = out.slice(0, MAX_READINGS)
    }
    return out
  }
  /** What a spliced expression renders as, one string per reading (a ternary has two). */
  const valuesOf = (expr: ts.Expression, seen = new Set<ts.Node>()): string[] => {
    const e = unwrapExpr(expr)
    if (isTrial(e)) return [TRIAL]
    const n = numberOf(e)
    if (n !== null) return [String(n)]
    if (ts.isStringLiteralLike(e)) return [e.text]
    if (e.kind === ts.SyntaxKind.NullKeyword || e.kind === ts.SyntaxKind.TrueKeyword || e.kind === ts.SyntaxKind.FalseKeyword) return ['']
    if (ts.isTemplateExpression(e)) return product([[e.head.text], ...e.templateSpans.flatMap((span) => [valuesOf(span.expression, seen), [span.literal.text]])])
    if (ts.isConditionalExpression(e)) return [...valuesOf(e.whenTrue, seen), ...valuesOf(e.whenFalse, seen)]
    if (ts.isBinaryExpression(e)) {
      const op = e.operatorToken.kind
      if (op === ts.SyntaxKind.AmpersandAmpersandToken) return [...valuesOf(e.right, seen), '']
      if (op === ts.SyntaxKind.BarBarToken || op === ts.SyntaxKind.QuestionQuestionToken) return [...valuesOf(e.left, seen), ...valuesOf(e.right, seen)]
      if (op === ts.SyntaxKind.PlusToken) return product([valuesOf(e.left, seen), valuesOf(e.right, seen)])
      return [GAP]
    }
    if (ts.isJsxElement(e) || ts.isJsxFragment(e) || ts.isJsxSelfClosingElement(e)) return jsxText(e, seen)
    if (ts.isCallExpression(e)) {
      const callee = unwrapExpr(e.expression)
      if (ts.isIdentifier(callee) && callee.text === 'String' && e.arguments[0]) return valuesOf(e.arguments[0], seen)
      if (ts.isPropertyAccessExpression(callee) && /^(?:toString|toLocaleString|trim)$/.test(callee.name.text)) return valuesOf(callee.expression, seen)
      return [GAP]
    }
    if (ts.isIdentifier(e)) {
      if (e.text === 'undefined') return ['']
      const binding = resolve(e)
      if (binding && isConst(binding.decl) && binding.init && !seen.has(binding.decl)) return valuesOf(binding.init, new Set([...seen, binding.decl]))
    }
    return [GAP]
  }
  /** A JSX element's whole text as it renders, its children in order, one string per reading. */
  const jsxText = (node: ts.JsxElement | ts.JsxFragment | ts.JsxSelfClosingElement, seen: Set<ts.Node>): string[] => {
    if (ts.isJsxSelfClosingElement(node)) return ['']
    return product(node.children.map((child) => {
      if (ts.isJsxText(child)) return [child.text]
      if (ts.isJsxExpression(child)) return child.expression ? valuesOf(child.expression, seen) : ['']
      return jsxText(child, seen)
    }))
  }
  /** A JSX element or fragment that is not inside another one's children: its text is read whole. */
  const isJsxRoot = (node: ts.Node): boolean => {
    for (let p = node.parent; p; p = p.parent) {
      if (ts.isJsxElement(p) || ts.isJsxFragment(p)) return false
      if (ts.isJsxAttribute(p) || ts.isFunctionLike(p) || ts.isStatement(p)) return true
    }
    return true
  }

  const reads: TrialReader['reads'] = []
  const copy: Array<{ node: ts.Node; text: string }> = []
  const visit = (node: ts.Node) => {
    if (ts.isIdentifier(node) && isReference(node) && isTrial(node)) {
      // A const that only renames TRIAL_DAYS is not a render of it: its own reads are checked instead.
      const holder = node.parent
      const alias = ts.isVariableDeclaration(holder) && holder.initializer === node && isConst(holder)
      if (!alias) reads.push({ line: line(node), guarded: guarded(node) })
    }
    if ((ts.isPropertyAccessExpression(node) || ts.isElementAccessExpression(node)) && memberOf(node, planNamespaces, 'TRIAL_DAYS')) {
      reads.push({ line: line(node), guarded: guarded(node) })
    }
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) copy.push({ node, text: node.text })
    if (ts.isTemplateExpression(node)) for (const text of valuesOf(node)) copy.push({ node, text })
    if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken &&
      !(ts.isBinaryExpression(node.parent) && node.parent.operatorToken.kind === ts.SyntaxKind.PlusToken)) {
      for (const text of valuesOf(node)) copy.push({ node, text })
    }
    if ((ts.isJsxElement(node) || ts.isJsxFragment(node)) && isJsxRoot(node)) for (const text of jsxText(node, new Set())) copy.push({ node, text })
    ts.forEachChild(node, visit)
  }
  visit(sf)
  const typed = copy
    .filter(({ text }) => typesTrialLength(text))
    .map(({ node, text }) => ({ line: line(node), text: aroundLength(text).replace(new RegExp(GAP, 'g'), '{…}').replace(new RegExp(TRIAL, 'g'), '{TRIAL_DAYS}') }))
  // One entry per line and length: a root, its readings and a literal inside it can type the same one.
  const unique = new Map(typed.map((t) => [`${t.line} ${t.text}`, t]))
  return { reads, typed: [...unique.values()] }
}

const parsed = new Map<string, ts.SourceFile>()
/** Each source file is parsed once for the clauses that walk the whole tree. */
const parse = (file: string) => {
  let sf = parsed.get(file)
  if (!sf) {
    const kind = /\.tsx$/.test(file) ? ts.ScriptKind.TSX : /\.jsx$/.test(file) ? ts.ScriptKind.JSX : /\.m?js$/.test(file) ? ts.ScriptKind.JS : ts.ScriptKind.TS
    sf = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, kind)
    parsed.set(file, sf)
  }
  return sf
}
const readers = new Map<string, TrialReader>()
const readerOf = (file: string) => {
  let reader = readers.get(file)
  if (!reader) readers.set(file, (reader = trialReader(parse(file))))
  return reader
}
/** The code the trial clauses read: the cap walk's files, its .ts/.tsx/.js/.jsx ones parsed; .md and .mdx are read as copy. */
const sourceFiles = () =>
  SOURCE_ROOTS.flatMap((root) => walk(path.join(frontendDir, root))).filter((file) => !/\.(spec|test)\.[jt]sx?$|\.d\.ts$/.test(file))
const isCode = (file: string) => /\.[jt]sx?$/.test(file)

/** "7 days" that is not the trial: each with the file and the copy it reads. */
const NOT_THE_TRIAL: Record<string, string> = {
  'app/admin/invites/page.tsx 7 days': "an invite link's lifetime option",
}

const probe = (code: string) => trialReader(ts.createSourceFile('probe.tsx', code, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX))

describe('the Pro trial length is stated only through TRIAL_DAYS, and only while the trial ships', () => {
  it('no copy types the trial length', () => {
    const offenders: string[] = []
    const allowed = new Set<string>()
    for (const file of sourceFiles()) {
      const rel = path.relative(frontendDir, file)
      if (rel === path.join('lib', 'planLimits.ts')) continue
      const typed = isCode(file)
        ? readerOf(file).typed
        : readFileSync(file, 'utf8').split('\n').flatMap((text, i) => (typesTrialLength(text) ? [{ line: i + 1, text: aroundLength(text) }] : []))
      for (const { line, text } of typed) {
        const key = `${rel} ${text}`
        if (key in NOT_THE_TRIAL) {
          allowed.add(key)
          continue
        }
        offenders.push(`${rel}:${line} ${text}`)
      }
    }
    expect(offenders, 'write the trial length as {TRIAL_DAYS} from lib/planLimits').toEqual([])
    expect(Object.keys(NOT_THE_TRIAL).filter((key) => !allowed.has(key)), 'no longer in the code: delete it from NOT_THE_TRIAL').toEqual([])
    // Parses every source file (about 2s idle): the default 5s is too tight on a loaded runner.
  }, 30_000)

  it('every read of TRIAL_DAYS renders only under ENABLE_PRO_TRIAL', () => {
    const reads: string[] = []
    const unguarded: string[] = []
    for (const file of sourceFiles().filter(isCode)) {
      const rel = path.relative(frontendDir, file)
      if (rel === path.join('lib', 'planLimits.ts')) continue
      for (const read of readerOf(file).reads) {
        reads.push(`${rel}:${read.line}`)
        if (!read.guarded) unguarded.push(`${rel}:${read.line}`)
      }
    }
    // Anti-vacuity: the signup gate, the paywall card and both pricing surfaces state the length.
    expect(reads.length, 'TRIAL_DAYS reads found').toBeGreaterThanOrEqual(4)
    expect(unguarded, 'state the trial only inside ENABLE_PRO_TRIAL (or a const derived from it)').toEqual([])
  }, 30_000)

  it('the two clauses follow bindings, read copy whole, and refuse a guard that can hold with the flag off', () => {
    const imports = "import { TRIAL_DAYS } from '@/lib/planLimits'\nimport { ENABLE_PRO_TRIAL } from '@/lib/featureFlags'\n"
    const typed = (code: string) => probe(imports + code).typed.length > 0
    // Copy that types a length: each is flagged.
    const lengths: Record<string, string> = {
      'a literal': "const a = 'Start a 7-day free trial'",
      'JSX text': 'const a = <p>First 7 days free</p>',
      'a number in JSX': 'const a = <p>Start a {7}-day free trial</p>',
      'a number in a template': 'const a = `Start ${7}-day free trial`',
      'a local number const': 'const LEN = 7\nconst a = <p>First {LEN} days free</p>',
      'a const of a const': 'const N = 7\nconst LEN = N\nconst a = <p>First {LEN} days free</p>',
      'a + chain': "const a = 'Start ' + 7 + '-day free trial'",
      'a length in its own element': 'const a = <p>Start a <span className="font-data">7</span>-day free trial</p>',
      'a length in a nested element': 'const a = <p>get <strong><em>7</em></strong> days free, cancel anytime.</p>',
      'a length behind &&': 'const a = <p>Start a {ready && 7}-day free trial</p>',
      'a length in a ternary': 'const a = <p>Start a {monthly ? 7 : 14}-day free trial</p>',
      'arithmetic': 'const a = <p>Start a {3 + 4}-day free trial</p>',
      'String() of a number': 'const a = `Start a ${String(7)}-day free trial`',
      'toString() of a number': 'const LEN = 7\nconst a = `Start a ${LEN.toString()}-day free trial`',
      'a no-break space entity': 'const a = <p>First 7&nbsp;days free</p>',
      'a numeric space entity': 'const a = <p>First 7&#160;days free</p>',
      'a no-break space': 'const a = <p>First 7\u00a0days free</p>',
      'a non-breaking hyphen': 'const a = <p>Start a 7\u2011day free trial</p>',
      'a number word': 'const a = <p>Start a seven-day free trial</p>',
      'weeks': 'const a = <p>Start a 1-week free trial</p>',
      'a value the reader cannot resolve': 'const a = <p>Start a {PLAN.trialDays}-day free trial</p>',
      'a length imported from another module': "import { TRIAL_LEN } from '@/lib/other'\nconst a = <p>Start a {TRIAL_LEN}-day free trial</p>",
      'a call the reader cannot read': 'const a = `Start a ${trialLength()}-day free trial`',
    }
    // Copy that states the length through TRIAL_DAYS, or another fact: each passes.
    const lookAlikes: Record<string, string> = {
      'TRIAL_DAYS itself': 'const a = <p>Start a {TRIAL_DAYS}-day free trial</p>',
      'TRIAL_DAYS in a template': 'const a = `First ${TRIAL_DAYS} days free`',
      'TRIAL_DAYS renamed': "import { TRIAL_DAYS as LEN } from '@/lib/planLimits'\nconst a = <p>First {LEN} days free</p>",
      'TRIAL_DAYS through a namespace': "import * as plan from '@/lib/planLimits'\nconst a = <p>First {plan.TRIAL_DAYS} days free</p>",
      'TRIAL_DAYS held in a const': 'const LEN = TRIAL_DAYS\nconst a = <p>First {LEN} days free</p>',
      'another limit': 'const a = <p>Free accounts get {FREE_SUMMARY_LIMIT} summaries</p>',
      'a history length': 'const a = <p>Free keeps 90-day history</p>',
      'a countdown of what is left': 'const a = <p><strong>{trialDays} {trialDays === 1 ? \'day\' : \'days\'} left</strong> in your Pro trial</p>',
    }
    expect(Object.entries(lengths).filter(([, code]) => !typed(code)).map(([name]) => name), 'a typed length the clause missed').toEqual([])
    expect(Object.entries(lookAlikes).filter(([, code]) => typed(code)).map(([name]) => name), 'a look-alike the clause flagged').toEqual([])

    const loose = (code: string) => probe(imports + code).reads.filter((r) => !r.guarded).length
    // Each read is guarded: 0 loose.
    const guardedForms: Record<string, string> = {
      'the flag': 'const a = ENABLE_PRO_TRIAL && <p>{TRIAL_DAYS}</p>',
      'a derived && const': 'const show = ENABLE_PRO_TRIAL && monthly && !beta\nconst a = show && <p>{TRIAL_DAYS}</p>',
      'an && condition': 'const a = (ready && ENABLE_PRO_TRIAL) ? <p>{TRIAL_DAYS}</p> : null',
      'an if': 'function f() { if (ENABLE_PRO_TRIAL) return <p>{TRIAL_DAYS}</p>; return null }',
      'a renamed flag import': "import { ENABLE_PRO_TRIAL as TRIAL_ON } from '@/lib/featureFlags'\nconst a = TRIAL_ON && <p>{TRIAL_DAYS}</p>",
      'a namespace flag': "import * as flags from '@/lib/featureFlags'\nconst a = flags.ENABLE_PRO_TRIAL && <p>{TRIAL_DAYS}</p>",
      'a renamed TRIAL_DAYS under the flag': "import { TRIAL_DAYS as LEN } from '@/lib/planLimits'\nconst a = ENABLE_PRO_TRIAL && <p>{LEN}</p>",
      'a guard in each of two functions': 'function A({ m }) { const show = ENABLE_PRO_TRIAL && m; return show && <p>{TRIAL_DAYS}</p> }\nfunction B({ m }) { const show = ENABLE_PRO_TRIAL && !m; return show && <p>{TRIAL_DAYS}</p> }',
      'a shadowing local, not TRIAL_DAYS': 'function F({ TRIAL_DAYS }) { return <p>{TRIAL_DAYS}</p> }',
    }
    // Each read is loose: 1 or more.
    const looseForms: Record<string, string> = {
      'no guard': 'const a = <p>{TRIAL_DAYS}</p>',
      'a derived ||': 'const show = ENABLE_PRO_TRIAL || beta\nconst a = show && <p>{TRIAL_DAYS}</p>',
      'an inline ||': 'const a = (ENABLE_PRO_TRIAL || beta) && <p>{TRIAL_DAYS}</p>',
      'a parenthesised negation': 'const a = !(ENABLE_PRO_TRIAL) && <p>{TRIAL_DAYS}</p>',
      'a comparison': 'const a = ENABLE_PRO_TRIAL === false && <p>{TRIAL_DAYS}</p>',
      'an inverted ternary': 'const show = ENABLE_PRO_TRIAL ? false : true\nconst a = show && <p>{TRIAL_DAYS}</p>',
      'a ??': 'const a = (ENABLE_PRO_TRIAL ?? beta) && <p>{TRIAL_DAYS}</p>',
      'the else branch': 'const a = ENABLE_PRO_TRIAL ? null : <p>{TRIAL_DAYS}</p>',
      'a renamed TRIAL_DAYS import': "import { TRIAL_DAYS as TRIAL_LENGTH } from '@/lib/planLimits'\nconst a = <p>Pro starts with a {TRIAL_LENGTH}-day free trial.</p>",
      'a namespace member': "import * as plan from '@/lib/planLimits'\nconst a = <p>{plan.TRIAL_DAYS}</p>",
      'a namespace element access': "import * as plan from '@/lib/planLimits'\nconst a = <p>{plan['TRIAL_DAYS']}</p>",
      'destructured from the namespace': "import * as plan from '@/lib/planLimits'\nconst { TRIAL_DAYS: n } = plan\nconst a = <p>{n}</p>",
      'TRIAL_DAYS held in a const': 'const LEN = TRIAL_DAYS\nconst a = <p>{LEN}</p>',
      'a same-named const in another function': 'function A({ m }) { const showTrial = ENABLE_PRO_TRIAL && m; return showTrial && <p>{TRIAL_DAYS}</p> }\nfunction B({ m }) { const showTrial = m; return showTrial ? <p>Start with a {TRIAL_DAYS}-day free trial.</p> : null }',
      'a reassigned let': 'let show = ENABLE_PRO_TRIAL && monthly\nshow = true\nconst a = show && <p>{TRIAL_DAYS}</p>',
      'a parameter named like a guard': 'function F({ showTrial }) { return showTrial && <p>{TRIAL_DAYS}</p> }',
    }
    expect(Object.entries(guardedForms).filter(([, code]) => loose(code) !== 0).map(([name]) => name), 'a guarded read the clause called loose').toEqual([])
    expect(Object.entries(looseForms).filter(([, code]) => loose(code) === 0).map(([name]) => name), 'a loose read the clause called guarded').toEqual([])
  })

  it('TRIAL_DAYS is the length the trial flips to, in the flag and in the backend', () => {
    const flags = readFileSync(path.join(frontendDir, 'lib/featureFlags.ts'), 'utf8')
    const config = readFileSync(path.resolve(frontendDir, '../backend/app/config.py'), 'utf8')
    expect(flags).toContain(`PRO_TRIAL_DAYS=${TRIAL_DAYS}`)
    expect(config).toContain(`PRO_TRIAL_DAYS=${TRIAL_DAYS}`)
    const bound = config.match(/PRO_TRIAL_DAYS: int = Field\(default=(\d+), ge=0, le=(\d+)\)/)
    expect(bound, 'PRO_TRIAL_DAYS field in backend/app/config.py').not.toBeNull()
    // The backend ships the trial off, which is why every read above is flag-guarded.
    expect(Number(bound![1])).toBe(0)
    expect(TRIAL_DAYS).toBeLessThanOrEqual(Number(bound![2]))
  })
})
