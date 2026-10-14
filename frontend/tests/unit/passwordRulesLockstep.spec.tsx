import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import PasswordField from '@/features/auth/components/PasswordField'
import { PASSWORD_MIN_LENGTH, PASSWORD_RULE } from '@/lib/passwordRules'

/**
 * The password rule the UI states moves in lockstep with the server (CLAUDE.md rule 12; the
 * planLimitsLockstep pattern). The reset page once told users "with upper- and lowercase letters and a
 * number", a rule the server never had (2026-10 audit, UA-35), and the strength meter called an
 * 11-character password "Good" though the server rejects it (UA-43).
 *
 *  - lib/passwordRules.ts mirrors the minimum the server enforces (backend/app/config.py
 *    PASSWORD_MIN_LENGTH, read by password_utils.validate_password_strength), and that validator checks
 *    length only, so PASSWORD_RULE states the whole rule.
 *  - PASSWORD_RULE's "Breached passwords are rejected" stands only while the HaveIBeenPwned check
 *    defaults on (backend/app/config.py PWNED_PASSWORD_CHECK_ENABLED, backend/app/services/pwned_passwords.py).
 *  - A file that handles a password (renders a password field or reads lib/passwordRules) never writes a
 *    length by hand: no length in copy, no `minLength={N}`, no local minimum constant, no `.length`
 *    compared against a number. Any other file that mentions a password never types the floor itself.
 *  - Every new-password field carries `minLength={PASSWORD_MIN_LENGTH}`, or its form checks
 *    `.length < PASSWORD_MIN_LENGTH` in code (CODE_CHECKED).
 *  - The strength meter says "Too short" under the minimum and scores length past it.
 */
const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const backend = (rel: string) => readFileSync(path.resolve(frontendDir, '../backend', rel), 'utf8')

const SOURCE_ROOTS = ['app', 'features', 'components', 'lib', 'hooks']
/** Renders a password field or reads the rule. */
const HANDLES_PASSWORD = /type=["']password["']|<PasswordField\b|["'](?:new|current)-password["']|@\/lib\/passwordRules/

type Pattern = { label: string; pattern: RegExp }
/** Written by hand in a file that handles a password. */
const HAND_TYPED: Pattern[] = [
  { label: 'a minLength literal', pattern: /minLength=\{\s*\d+\s*\}/ },
  { label: 'a length in copy', pattern: /\b\d+\b(?:\s+or\s+more)?\s+(?:characters?|chars)\b/i },
  { label: 'a local minimum constant', pattern: /\b[A-Z_]*MIN_LENGTH\s*=\s*\d+/ },
  { label: 'a length compared against a number', pattern: /\.length\s*[<>]=?\s*[1-9]\d*|\b[1-9]\d*\s*[<>]=?\s*[\w.]*\.length\b/ },
]
/** In any other file that mentions a password: the floor itself, typed. */
const FLOOR_TYPED: Pattern[] = [
  { label: 'a minLength literal', pattern: /minLength=\{\s*\d+\s*\}/ },
  { label: 'the floor in copy', pattern: new RegExp(`\\b${PASSWORD_MIN_LENGTH}\\b(?:\\s+or\\s+more)?\\s+(?:characters?|chars)\\b`, 'i') },
  { label: 'a local minimum constant', pattern: /\b[A-Z_]*MIN_LENGTH\s*=\s*\d+/ },
]
/** The pages that state or enforce the rule, and the meter that scores against it. */
const RULE_SITES = [
  'app/reset-password/page.tsx',
  'features/auth/components/RegisterForm.tsx',
  'features/auth/components/PasswordField.tsx',
  'features/settings/components/ChangePasswordForm.tsx',
]
/** Forms whose new-password inputs check the floor in code instead of through `minLength`. */
const CODE_CHECKED: Record<string, string> = {
  'features/settings/components/ChangePasswordForm.tsx': 'shows its own sentence for a short password before the request',
}

function walk(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) return entry.name === 'node_modules' ? [] : walk(full)
    return /\.(tsx?|mdx?)$/.test(entry.name) ? [full] : []
  })
}

function handTyped(source: string, rel: string): string[] {
  const patterns = HANDLES_PASSWORD.test(source) ? HAND_TYPED : /password/i.test(source) ? FLOOR_TYPED : []
  const offenders: string[] = []
  source.split('\n').forEach((line, index) => {
    for (const { label, pattern } of patterns) {
      if (pattern.test(line)) offenders.push(`${rel}:${index + 1} (${label}): ${line.trim()}`)
    }
  })
  return offenders
}

/** New-password JSX fields whose `minLength` is not the shared constant. */
function fieldsWithoutFloor(source: string, rel: string): string[] {
  const sf = ts.createSourceFile(rel, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const out: string[] = []
  const visit = (node: ts.Node): void => {
    if (ts.isJsxSelfClosingElement(node) || ts.isJsxOpeningElement(node)) {
      const attrs = new Map<string, ts.JsxAttribute>()
      for (const prop of node.attributes.properties) if (ts.isJsxAttribute(prop)) attrs.set(prop.name.getText(sf), prop)
      const auto = attrs.get('autoComplete')?.initializer
      if (auto && ts.isStringLiteral(auto) && auto.text === 'new-password') {
        const min = attrs.get('minLength')?.initializer
        const reads = !!min && ts.isJsxExpression(min) && !!min.expression && min.expression.getText(sf) === 'PASSWORD_MIN_LENGTH'
        if (!reads) out.push(`${rel}:${sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1} <${node.tagName.getText(sf)}>`)
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out
}

const FILES = SOURCE_ROOTS.flatMap((root) => walk(path.join(frontendDir, root)))
const rel = (file: string) => path.relative(frontendDir, file).split(path.sep).join('/')
const RULE_FILE = 'lib/passwordRules.ts'

describe('the password rule moves in lockstep with the backend', () => {
  it('mirrors PASSWORD_MIN_LENGTH, the minimum validate_password_strength enforces', () => {
    const match = backend('app/config.py').match(/^\s*PASSWORD_MIN_LENGTH:\s*int\s*=\s*(\d+)/m)
    if (!match) throw new Error('PASSWORD_MIN_LENGTH not found in backend/app/config.py')
    expect(PASSWORD_MIN_LENGTH).toBe(Number(match[1]))
  })

  it('the validator checks length only, so PASSWORD_RULE states the whole rule', () => {
    const body = backend('app/services/password_utils.py').match(/^def validate_password_strength\b[\s\S]*?(?=^\S)/m)?.[0]
    if (!body) throw new Error('validate_password_strength not found in backend/app/services/password_utils.py')
    const checks = body.split('\n').map((line) => line.trim()).filter((line) => /^(if|elif|raise)\b/.test(line) || /\braise\b/.test(line))
    expect(checks, 'a new password rule on the server: state it in PASSWORD_RULE, then update this list').toEqual([
      'if len(value) < settings.PASSWORD_MIN_LENGTH:',
      'raise ValueError(f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters.")',
      'if len(value) > PASSWORD_MAX_LENGTH:',
      'raise ValueError(f"Password must be at most {PASSWORD_MAX_LENGTH} characters.")',
    ])
  })

  it('says breached passwords are rejected only while the breach check defaults on', () => {
    expect(PASSWORD_RULE).toContain('Breached passwords are rejected.')
    expect(backend('app/config.py')).toMatch(/^\s*PWNED_PASSWORD_CHECK_ENABLED:\s*bool\s*=\s*True\b/m)
  })

  it('reads every file that handles a password (a scan that finds none must not pass)', () => {
    const handling = FILES.filter((file) => HANDLES_PASSWORD.test(readFileSync(file, 'utf8'))).map(rel)
    expect(handling).toEqual(expect.arrayContaining([...RULE_SITES, 'app/login/page.tsx']))
  })

  it('no file that handles a password writes a length by hand', () => {
    const offenders = FILES.filter((file) => rel(file) !== RULE_FILE).flatMap((file) => handTyped(readFileSync(file, 'utf8'), rel(file)))
    expect(offenders, "use PASSWORD_MIN_LENGTH / PASSWORD_RULE from '@/lib/passwordRules'").toEqual([])
  })

  it('every new-password field carries minLength={PASSWORD_MIN_LENGTH}, or its form checks the floor in code', () => {
    const missing = FILES.filter((file) => /\.tsx$/.test(file) && !(rel(file) in CODE_CHECKED)).flatMap((file) =>
      fieldsWithoutFloor(readFileSync(file, 'utf8'), rel(file)),
    )
    expect(missing, 'give the field minLength={PASSWORD_MIN_LENGTH}').toEqual([])
    for (const file of Object.keys(CODE_CHECKED)) {
      expect(readFileSync(path.join(frontendDir, file), 'utf8'), `${file} must check .length < PASSWORD_MIN_LENGTH`).toMatch(
        /\.length\s*<\s*PASSWORD_MIN_LENGTH\b/,
      )
    }
  })

  it('the pages that state or enforce the rule read it from lib/passwordRules', () => {
    for (const site of RULE_SITES) {
      expect(readFileSync(path.join(frontendDir, site), 'utf8'), `${site} must import from '@/lib/passwordRules'`).toMatch(
        /from '@\/lib\/passwordRules'/,
      )
    }
  })

  it('the scans catch what they are for (a self-check on fixed sources)', () => {
    const form = "import { PASSWORD_MIN_LENGTH } from '@/lib/passwordRules'\n"
    expect(handTyped(`${form}if (next.length < 12) {`, 'probe.tsx')).toEqual(['probe.tsx:2 (a length compared against a number): if (next.length < 12) {'])
    expect(handTyped(`${form}const hint = 'Use 12 or more characters.'`, 'probe.tsx')).toEqual([
      "probe.tsx:2 (a length in copy): const hint = 'Use 12 or more characters.'",
    ])
    expect(handTyped(`${form}if (value.length > 0 && next.length < PASSWORD_MIN_LENGTH) {}`, 'probe.tsx')).toEqual([])
    // A file that only mentions a password is held to the floor, not to every number.
    expect(handTyped(`// password note\nconst cap = 'at most 400 characters'`, 'note.ts')).toEqual([])
    expect(handTyped(`// password note\nconst copy = 'at least ${PASSWORD_MIN_LENGTH} characters'`, 'note.ts')).toHaveLength(1)
    expect(
      fieldsWithoutFloor(
        [
          '<PasswordField id="a" autoComplete="new-password" minLength={PASSWORD_MIN_LENGTH} />',
          '<PasswordField id="b" autoComplete="new-password" showStrength />',
          '<Input id="c" type="password" autoComplete="new-password" minLength={12} />',
          '<PasswordField id="d" autoComplete="current-password" />',
        ].join('\n'),
        'probe.tsx',
      ),
    ).toEqual(['probe.tsx:2 <PasswordField>', 'probe.tsx:3 <Input>'])
  })

  it('the strength meter says "Too short" under the minimum and scores length past it', () => {
    const field = (value: string, minLength?: number) => (
      <PasswordField id="pw" label="Password" value={value} onChange={() => {}} minLength={minLength} showStrength />
    )
    const almost = 'Ab1!'.padEnd(PASSWORD_MIN_LENGTH - 1, 'x')
    const { rerender } = render(field(almost, PASSWORD_MIN_LENGTH))
    expect(screen.getByText('Too short')).toBeInTheDocument()
    // Clearing the floor alone is one bar.
    rerender(field('a'.repeat(PASSWORD_MIN_LENGTH), PASSWORD_MIN_LENGTH))
    expect(screen.getByText('Weak')).toBeInTheDocument()
    rerender(field(`${almost}x`, PASSWORD_MIN_LENGTH))
    expect(screen.getByText('Good')).toBeInTheDocument()
    rerender(field(`${almost}xxxxx`, PASSWORD_MIN_LENGTH))
    expect(screen.getByText('Strong')).toBeInTheDocument()
    // Without the prop the meter still scores against the server's floor.
    rerender(field(almost))
    expect(screen.getByText('Too short')).toBeInTheDocument()
  })
})
