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
 *    PASSWORD_MIN_LENGTH, read by password_utils.validate_password_strength). Every statement of that
 *    validator's body is pinned (a helper call is a statement too), and every password field of the auth
 *    schemas (backend/app/routers/auth.py) is a bare `str` whose validator only calls it, so PASSWORD_RULE
 *    states the whole rule. A check written into a route handler's own body is not read here.
 *  - PASSWORD_RULE's "Breached passwords are rejected" stands only while the HaveIBeenPwned check defaults
 *    on (backend/app/config.py PWNED_PASSWORD_CHECK_ENABLED, backend/app/services/pwned_passwords.py) and
 *    the two routes behind the pages that state it (register and reset_password) call it.
 *  - A file that handles a password (renders a password field or reads lib/passwordRules) never writes a
 *    length by hand: no length in copy ("12 characters", "12-character", "12+", "12 or more", "twelve"), no
 *    `minLength` or `min_length` number, no local constant whose name says min and len, no `.length`
 *    compared against a number, and no number equal to the floor anywhere in its code. Any other file that
 *    mentions a password never types the floor itself: in copy, as a minimum, in a constant named for a
 *    minimum, a length, a floor or a password, or against a `.length`. The two pages that state PASSWORD_RULE render it word for word, whatever their
 *    source looks like (authPagesCopy.spec.tsx for /reset-password, RegisterForm.spec.tsx for /register).
 *  - Every new-password field carries `minLength={PASSWORD_MIN_LENGTH}`, or its form checks
 *    `.length < PASSWORD_MIN_LENGTH` in code (CODE_CHECKED). A field is a new-password field when its
 *    `autoComplete` names new-password: a literal, braced or not, or inside an expression. A value passed
 *    in from elsewhere (PasswordField forwards its prop) is read at the caller that writes it.
 *  - The strength meter says "Too short" under the minimum and scores length past it.
 */
const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const backend = (rel: string) => readFileSync(path.resolve(frontendDir, '../backend', rel), 'utf8')

const SOURCE_ROOTS = ['app', 'features', 'components', 'lib', 'hooks']
/** Renders a password field or reads the rule. */
const HANDLES_PASSWORD = /type=\{?\s*["'`]password["'`]|<PasswordField\b|["'`](?:new|current)-password["'`]|@\/lib\/passwordRules/

/** The counts copy spells out, to twenty. */
const NUMBER_WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen', 'twenty']
/** A length in copy: "12 characters", "12-character", "12+ characters", "12 or more characters", "twelve chars". */
const lengthInCopy = (count: string) =>
  new RegExp(String.raw`\b${count}\+?(?:\s+or\s+(?:more|longer))?[\s‐-―-]+(?:characters?|chars?)\b`, 'i')
const ANY_COUNT = String.raw`(?:\d+|${NUMBER_WORDS.join('|')})`
const FLOOR_COUNT = String.raw`(?:${PASSWORD_MIN_LENGTH}|${NUMBER_WORDS[PASSWORD_MIN_LENGTH] ?? PASSWORD_MIN_LENGTH})`
/** `minLength={12}`, `minLength: 12`, `minlength="12"`, `min_length=12`. */
const MIN_LENGTH_NUMBER = /\bmin_?length\b\s*(?:=\s*\{?\s*|:\s*)["'`]?\d+/i
/** A constant whose name says min and len, in either order and any case, set to a number. */
const MIN_CONSTANT = /\b\w*(?:min\w*len|len\w*min)\w*\s*(?::\s*[\w.]+\s*)?=\s*\d+/i

type Pattern = { label: string; pattern: RegExp }
/** Written by hand in a file that handles a password. */
const HAND_TYPED: Pattern[] = [
  { label: 'a minLength literal', pattern: MIN_LENGTH_NUMBER },
  { label: 'a length in copy', pattern: lengthInCopy(ANY_COUNT) },
  { label: 'a local minimum constant', pattern: MIN_CONSTANT },
  { label: 'a length compared against a number', pattern: /\.length\s*[<>]=?\s*[1-9]\d*|\b[1-9]\d*\s*[<>]=?\s*[\w.]*\.length\b/ },
]
/** In any other file that mentions a password: the floor itself, typed. */
const FLOOR_TYPED: Pattern[] = [
  { label: 'a minLength literal', pattern: MIN_LENGTH_NUMBER },
  { label: 'the floor in copy', pattern: lengthInCopy(FLOOR_COUNT) },
  {
    label: 'the floor in a constant',
    pattern: new RegExp(String.raw`\b\w*(?:min|len|floor|password)\w*\s*(?::\s*[\w.]+\s*)?=\s*${PASSWORD_MIN_LENGTH}\b`, 'i'),
  },
  {
    label: 'the floor compared against a length',
    pattern: new RegExp(String.raw`\.length\s*[<>]=?\s*${PASSWORD_MIN_LENGTH}\b|\b${PASSWORD_MIN_LENGTH}\s*[<>]=?\s*[\w.]*\.length\b`),
  },
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

/** In a file that handles a password, the floor typed as a number anywhere in its code, whatever it is named. */
function floorNumbers(source: string, rel: string): string[] {
  if (!/\.tsx?$/.test(rel) || !HANDLES_PASSWORD.test(source)) return []
  const sf = ts.createSourceFile(rel, source, ts.ScriptTarget.Latest, true, rel.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const out: string[] = []
  const visit = (node: ts.Node): void => {
    if (ts.isNumericLiteral(node) && Number(node.text.replace(/_/g, '')) === PASSWORD_MIN_LENGTH) {
      out.push(`${rel}:${sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1} (the floor as a number): ${node.parent.getText(sf).trim()}`)
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out
}

/** Whether an `autoComplete` value names new-password: a literal, braced or not, or one inside an expression. */
function namesNewPassword(value: ts.Node | undefined): boolean {
  if (!value) return false
  const text =
    ts.isStringLiteral(value) || ts.isNoSubstitutionTemplateLiteral(value) || ts.isTemplateHead(value) || ts.isTemplateMiddle(value) || ts.isTemplateTail(value)
      ? value.text
      : undefined
  if (text !== undefined && /\bnew-password\b/i.test(text)) return true
  return ts.forEachChild(value, (child) => namesNewPassword(child) || undefined) ?? false
}

/** New-password JSX fields whose `minLength` is not the shared constant. */
function fieldsWithoutFloor(source: string, rel: string): string[] {
  const sf = ts.createSourceFile(rel, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const out: string[] = []
  const visit = (node: ts.Node): void => {
    if (ts.isJsxSelfClosingElement(node) || ts.isJsxOpeningElement(node)) {
      const attrs = new Map<string, ts.JsxAttribute>()
      for (const prop of node.attributes.properties) if (ts.isJsxAttribute(prop)) attrs.set(prop.name.getText(sf), prop)
      if (namesNewPassword(attrs.get('autoComplete')?.initializer)) {
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

/** The statements a Python `def` at `start` runs: its body without the docstring, comments or blank lines. */
function pythonBlock(lines: string[], start: number): string[] {
  const indent = (line: string) => line.length - line.trimStart().length
  // The signature may span lines; the body starts after the line that closes it.
  let open = start
  while (open < lines.length && !/\)\s*(?:->\s*[^:]+)?:\s*(?:#.*)?$/.test(lines[open])) open++
  const code: string[] = []
  for (let i = open + 1; i < lines.length && (!lines[i].trim() || indent(lines[i]) > indent(lines[start])); i++) {
    const line = lines[i].trim()
    if (line && !line.startsWith('#')) code.push(line)
  }
  const quote = code[0]?.match(/^(?:"""|''')/)?.[0]
  if (quote) {
    const closes = code.findIndex((line, k) => (k === 0 ? line.length > 3 && line.endsWith(quote) : line.endsWith(quote)))
    code.splice(0, closes + 1)
  }
  return code
}
const pythonBody = (source: string, def: RegExp): string[] | undefined => {
  const lines = source.split('\n')
  const start = lines.findIndex((line) => def.test(line))
  return start < 0 ? undefined : pythonBlock(lines, start)
}

/** Every validator in a schema module that names a password field or reads one, as `(args) statement / …`. */
function passwordValidators(source: string): string[] {
  const lines = source.split('\n')
  return lines.flatMap((line, index) => {
    const decorator = line.match(/^\s*@(?:field_validator|model_validator|validator|root_validator)\b(.*)$/)
    if (!decorator) return []
    const def = lines.findIndex((l, k) => k > index && /^\s*(?:async\s+)?def\s/.test(l))
    const body = def < 0 ? [] : pythonBlock(lines, def)
    return /password/.test(decorator[1]) || body.some((statement) => /password/.test(statement)) ? [`${decorator[1].trim()} ${body.join(' / ')}`] : []
  })
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
    const body = pythonBody(backend('app/services/password_utils.py'), /^def validate_password_strength\b/)
    if (!body) throw new Error('validate_password_strength not found in backend/app/services/password_utils.py')
    expect(body, 'a new password rule on the server: state it in PASSWORD_RULE, then update this list').toEqual([
      'if len(value) < settings.PASSWORD_MIN_LENGTH:',
      'raise ValueError(f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters.")',
      'if len(value) > PASSWORD_MAX_LENGTH:',
      'raise ValueError(f"Password must be at most {PASSWORD_MAX_LENGTH} characters.")',
      'return value',
    ])
  })

  it('every password field of the auth schemas is a bare str whose validator only calls validate_password_strength', () => {
    const router = backend('app/routers/auth.py')
    // A constraint on the field itself (Field(min_length=…), a pattern) would be a rule too.
    const fields = router.split('\n').flatMap((line) => line.match(/^ {4}(\w*password\w*)\s*:\s*(.+?)\s*$/)?.slice(1, 3).join(': ') ?? [])
    expect(fields, 'a password field changed in backend/app/routers/auth.py: state any new rule in PASSWORD_RULE, then update this list').toEqual([
      'password: str',
      'password: str',
      'new_password: str',
      'current_password: Optional[str] = None',
      'new_password: str',
    ])
    expect(passwordValidators(router), 'a new password rule in a schema: state it in PASSWORD_RULE, then update this list').toEqual([
      '("password") return validate_password_strength(value)',
      '("new_password") return validate_password_strength(value)',
      '("new_password") return validate_password_strength(value)',
    ])
  })

  it('says breached passwords are rejected only while the breach check defaults on and the routes behind the sentence call it', () => {
    expect(PASSWORD_RULE).toContain('Breached passwords are rejected.')
    expect(backend('app/config.py')).toMatch(/^\s*PWNED_PASSWORD_CHECK_ENABLED:\s*bool\s*=\s*True\b/m)
    // /register and /reset-password state PASSWORD_RULE; these are the routes their forms post to.
    const router = backend('app/routers/auth.py')
    for (const [route, password] of [['register', 'user_data.password'], ['reset_password', 'payload.new_password']]) {
      const body = pythonBody(router, new RegExp(String.raw`^async def ${route}\(`))
      expect(body, `${route} must refuse a breached password with is_password_pwned`).toContain(`if await is_password_pwned(${password}):`)
    }
  })

  it('reads every file that handles a password (a scan that finds none must not pass)', () => {
    const handling = FILES.filter((file) => HANDLES_PASSWORD.test(readFileSync(file, 'utf8'))).map(rel)
    expect(handling).toEqual(expect.arrayContaining([...RULE_SITES, 'app/login/page.tsx']))
  })

  it('no file that handles a password writes a length by hand', () => {
    const offenders = FILES.filter((file) => rel(file) !== RULE_FILE).flatMap((file) => {
      const source = readFileSync(file, 'utf8')
      return [...handTyped(source, rel(file)), ...floorNumbers(source, rel(file))]
    })
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
    // The rest of the copy family: hyphenated, a plus, spelled out, and the short form.
    for (const copy of ['Use a 12-character passphrase.', 'Use 12+ characters.', 'Use twelve characters or more.', 'At least 8 chars.']) {
      expect(handTyped(`${form}const hint = '${copy}'`, 'probe.tsx'), copy).toHaveLength(1)
    }
    // A renamed constant is read by its name and by its value; the value alone, under any name.
    expect(handTyped(`${form}const MIN_PASSWORD_LENGTH = 12`, 'probe.tsx')).toEqual([
      'probe.tsx:2 (a local minimum constant): const MIN_PASSWORD_LENGTH = 12',
    ])
    expect(floorNumbers(`${form}const MIN_PASSWORD_LENGTH = 12\nconst FLOOR = 12\nconst gap = 4`, 'probe.tsx')).toEqual([
      'probe.tsx:2 (the floor as a number): MIN_PASSWORD_LENGTH = 12',
      'probe.tsx:3 (the floor as a number): FLOOR = 12',
    ])
    expect(handTyped(`${form}const field = { minLength: 12 }`, 'probe.tsx')).toEqual(['probe.tsx:2 (a minLength literal): const field = { minLength: 12 }'])
    expect(handTyped(`${form}if (value.length > 0 && next.length < PASSWORD_MIN_LENGTH) {}`, 'probe.tsx')).toEqual([])
    expect(floorNumbers(`${form}if (value.length > 0 && next.length < PASSWORD_MIN_LENGTH + 4) {}`, 'probe.tsx')).toEqual([])
    // A file that only mentions a password is held to the floor, not to every number.
    expect(handTyped(`// password note\nconst cap = 'at most 400 characters'\nif (s.length > 120) {}`, 'note.ts')).toEqual([])
    for (const floor of [
      `const copy = 'at least ${PASSWORD_MIN_LENGTH} characters'`,
      `const copy = 'a ${PASSWORD_MIN_LENGTH}-character passphrase'`,
      `const copy = '${NUMBER_WORDS[PASSWORD_MIN_LENGTH]} characters'`,
      `export const PASSWORD_FLOOR = ${PASSWORD_MIN_LENGTH}`,
      `if (value.length < ${PASSWORD_MIN_LENGTH}) {}`,
      `const rule = { minLength: ${PASSWORD_MIN_LENGTH} }`,
    ]) {
      expect(handTyped(`// password note\n${floor}`, 'note.ts'), floor).toHaveLength(1)
    }
    expect(
      fieldsWithoutFloor(
        [
          '<PasswordField id="a" autoComplete="new-password" minLength={PASSWORD_MIN_LENGTH} />',
          '<PasswordField id="b" autoComplete="new-password" showStrength />',
          '<Input id="c" type="password" autoComplete="new-password" minLength={12} />',
          '<PasswordField id="d" autoComplete="current-password" />',
          // Braced, a template, or one branch of an expression: still a new-password field.
          "<Input id=\"e\" type=\"password\" autoComplete={'new-password'} />",
          '<Input id="f" type="password" autoComplete={`new-password`} minLength={PASSWORD_MIN_LENGTH} />',
          "<Input id=\"g\" type=\"password\" autoComplete={setting ? 'new-password' : 'current-password'} />",
          // A forwarded prop is read where its caller writes the literal.
          '<input id="h" autoComplete={autoComplete} minLength={minLength} />',
        ].join('\n'),
        'probe.tsx',
      ),
    ).toEqual(['probe.tsx:2 <PasswordField>', 'probe.tsx:3 <Input>', 'probe.tsx:5 <Input>', 'probe.tsx:7 <Input>'])
    const python = [
      'def validate(value: str) -> str:',
      '    """Doc.',
      '',
      '    More doc."""',
      '    # a note',
      '    _reject_letters_only(value)',
      '    return value',
      '',
      'class UserCreate(BaseModel):',
      '    @field_validator("password")',
      '    @classmethod',
      '    def check(cls, value: str) -> str:',
      '        if value.isalpha():',
      '            raise ValueError("Add a digit.")',
      '        return validate_password_strength(value)',
      '',
      '    @field_validator("email")',
      '    @classmethod',
      '    def normalize(cls, value: str) -> str:',
      '        return value.strip()',
    ].join('\n')
    // A helper call is a statement of the body; the docstring and the comment are not.
    expect(pythonBody(python, /^def validate\b/)).toEqual(['_reject_letters_only(value)', 'return value'])
    expect(passwordValidators(python)).toEqual(['("password") if value.isalpha(): / raise ValueError("Add a digit.") / return validate_password_strength(value)'])
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
