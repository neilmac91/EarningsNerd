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
 *    length by hand: no length in copy ("12 characters", "12-character", "12+", "12 or more", "twelve"),
 *    on one line or composed across JSX text and its expressions (`At least {12}` then `characters` on the
 *    next line), no `minLength` or `min_length` number, no local constant whose name says min and len, no
 *    `.length` compared against a number or a numeric constant of any name, no `.min(n)` call or `.{n,}`
 *    pattern, and no number equal to the floor anywhere in its code. Any other file that mentions a password
 *    never types the floor itself, in any of those forms or in a constant named for a minimum, a length, a
 *    floor or a password. A count computed at runtime is not read. The two pages that state PASSWORD_RULE
 *    render it word for word, whatever their source looks like (authPagesCopy.spec.tsx for
 *    /reset-password, RegisterForm.spec.tsx for /register).
 *  - Every new-password field carries `minLength={PASSWORD_MIN_LENGTH}`, or its form checks
 *    `.length < PASSWORD_MIN_LENGTH` in its code (CODE_CHECKED, read on the syntax tree, so a comment or a
 *    string does not count). A field is a new-password field when its `autoComplete` names new-password: a
 *    literal, braced or not, inside an expression, or in a spread object. Every password field (`<PasswordField>`
 *    or a `type` that names password) names its `autoComplete` or forwards one passed in (PasswordField
 *    forwards its prop; a spread of props), which is read at the caller that writes it, and the scan must
 *    find the app's new-password fields, so a field it cannot read fails instead of passing unseen.
 *  - Every file under SOURCE_ROOTS is read (scripts, Markdown, MDX) or listed in NOT_READ with why it can
 *    hold no password rule.
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

/** Scripts (TS or JS, JSX or not) and prose (Markdown, MDX) are read. */
const READ = /\.(?:[cm]?[jt]sx?|mdx?)$/
/** Every other extension under SOURCE_ROOTS, with why it can hold no password rule. */
const NOT_READ: Record<string, string> = {
  '.json': 'data (the analysis demo), never copy, a field or a check',
  '.css': 'styles, never copy, a field or a check',
}
const isScript = (rel: string) => /\.[cm]?[jt]sx?$/.test(rel)
const scriptKind = (rel: string) =>
  rel.endsWith('.tsx') ? ts.ScriptKind.TSX : rel.endsWith('.jsx') ? ts.ScriptKind.JSX : /\.[cm]?js$/.test(rel) ? ts.ScriptKind.JS : ts.ScriptKind.TS
const parse = (source: string, rel: string) => ts.createSourceFile(rel, source, ts.ScriptTarget.Latest, true, scriptKind(rel))
const lineOf = (sf: ts.SourceFile, node: ts.Node) => sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
const squash = (text: string) => text.replace(/\s+/g, ' ').trim()

function walk(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) return entry.name === 'node_modules' ? [] : walk(full)
    return [full]
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
  if (!isScript(rel) || !HANDLES_PASSWORD.test(source)) return []
  const sf = parse(source, rel)
  const out: string[] = []
  const visit = (node: ts.Node): void => {
    if (ts.isNumericLiteral(node) && Number(node.text.replace(/_/g, '')) === PASSWORD_MIN_LENGTH) {
      out.push(`${rel}:${lineOf(sf, node)} (the floor as a number): ${node.parent.getText(sf).trim()}`)
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out
}

const unwrap = (node: ts.Expression): ts.Expression =>
  ts.isParenthesizedExpression(node) || ts.isAsExpression(node) || ts.isSatisfiesExpression(node) || ts.isTypeAssertionExpression(node)
    ? unwrap(node.expression)
    : node
const COMPARISONS = new Set([ts.SyntaxKind.LessThanToken, ts.SyntaxKind.LessThanEqualsToken, ts.SyntaxKind.GreaterThanToken, ts.SyntaxKind.GreaterThanEqualsToken])

/**
 * In a script, the lengths a line scan cannot see: copy composed across JSX text and its expressions (a
 * number in braces, a sentence split over lines), a `.length` compared against a numeric constant of any
 * name, a `.min(n)` call and a `.{n,}` pattern. Where the file handles a password, any count; where it only
 * mentions one, the floor.
 */
function codeForms(source: string, rel: string): string[] {
  const handles = HANDLES_PASSWORD.test(source)
  if (!isScript(rel) || (!handles && !/password/i.test(source))) return []
  const counts = (n: number | undefined) => n !== undefined && (handles ? n >= 1 : n === PASSWORD_MIN_LENGTH)
  const copy = lengthInCopy(handles ? ANY_COUNT : FLOOR_COUNT)
  const sf = parse(source, rel)
  const out: string[] = []
  // The file's numeric constants, whatever their names: `const FLOOR = 12`, `const n = 12 as const`.
  const constants = new Map<string, number>()
  const collect = (node: ts.Node): void => {
    if (ts.isVariableDeclarationList(node) && node.flags & ts.NodeFlags.Const) {
      for (const decl of node.declarations) {
        const init = decl.initializer && unwrap(decl.initializer)
        if (ts.isIdentifier(decl.name) && init && ts.isNumericLiteral(init)) constants.set(decl.name.text, Number(init.text.replace(/_/g, '')))
      }
    }
    ts.forEachChild(node, collect)
  }
  collect(sf)
  const valueOf = (node: ts.Expression): number | undefined => {
    const inner = unwrap(node)
    if (ts.isNumericLiteral(inner)) return Number(inner.text.replace(/_/g, ''))
    return ts.isIdentifier(inner) ? constants.get(inner.text) : undefined
  }
  const isLength = (node: ts.Expression) => {
    const inner = unwrap(node)
    return ts.isPropertyAccessExpression(inner) && inner.name.text === 'length'
  }
  // What an element renders as text: its text, its literal or constant expressions, its children's text.
  const rendered = (node: ts.Node): string => {
    if (ts.isJsxText(node)) return node.text
    if (ts.isJsxExpression(node)) {
      const inner = node.expression && unwrap(node.expression)
      if (!inner) return ''
      if (ts.isStringLiteral(inner) || ts.isNoSubstitutionTemplateLiteral(inner)) return inner.text
      return String(valueOf(inner) ?? ' … ')
    }
    return ts.isJsxElement(node) || ts.isJsxFragment(node) ? node.children.map(rendered).join('') : ' '
  }
  const statesCount = (node: ts.Node) => (ts.isJsxElement(node) || ts.isJsxFragment(node)) && copy.test(squash(rendered(node)))
  const visit = (node: ts.Node): void => {
    // The innermost element whose text states a count, so one sentence is one finding.
    if (statesCount(node) && !(node as ts.JsxElement | ts.JsxFragment).children.some(statesCount)) {
      out.push(`${rel}:${lineOf(sf, node)} (copy composed across JSX): ${squash(rendered(node))}`)
    }
    if (ts.isBinaryExpression(node) && COMPARISONS.has(node.operatorToken.kind)) {
      const other = isLength(node.left) ? node.right : isLength(node.right) ? node.left : undefined
      if (other && counts(valueOf(other))) out.push(`${rel}:${lineOf(sf, node)} (a length compared against a number): ${squash(node.getText(sf))}`)
    }
    if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression) && node.expression.name.text === 'min') {
      const receiver = node.expression.expression
      const math = ts.isIdentifier(receiver) && receiver.text === 'Math'
      if (!math && node.arguments.length > 0 && counts(valueOf(node.arguments[0]))) {
        out.push(`${rel}:${lineOf(sf, node)} (a minimum call): ${squash(node.getText(sf))}`)
      }
    }
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isRegularExpressionLiteral(node)) {
      const min = node.text.match(/(?<!\\)\.\{(\d+),\d*\}/)
      if (min && counts(Number(min[1]))) out.push(`${rel}:${lineOf(sf, node)} (a pattern minimum): ${node.getText(sf)}`)
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out
}

type Field = { line: number; tag: string; id: string; kind: 'new' | 'current' | 'forwarded' | 'unnamed'; floor: boolean }

/** Whether a value carries a string that passes `test`: a literal, braced or not, or one inside an expression. */
function carries(value: ts.Node | undefined, test: (text: string) => boolean): boolean {
  if (!value) return false
  const text =
    ts.isStringLiteral(value) || ts.isNoSubstitutionTemplateLiteral(value) || ts.isTemplateHead(value) || ts.isTemplateMiddle(value) || ts.isTemplateTail(value)
      ? value.text
      : undefined
  if (text !== undefined && test(text)) return true
  return ts.forEachChild(value, (child) => carries(child, test) || undefined) ?? false
}
const namesNew = (text: string) => /\bnew-password\b/i.test(text)
const namesCurrent = (text: string) => /\bcurrent-password\b/i.test(text)

/** The password fields (`<PasswordField>`, a `type` that names password) and new-password fields a file renders. */
function passwordFields(source: string, rel: string): Field[] {
  if (!isScript(rel)) return []
  const sf = parse(source, rel)
  const out: Field[] = []
  const visit = (node: ts.Node): void => {
    if (ts.isJsxSelfClosingElement(node) || ts.isJsxOpeningElement(node)) {
      // Attributes written on the element, and those of a spread object (`{...{ autoComplete: '…' }}`).
      const attrs = new Map<string, ts.Node | undefined>()
      let spreadsProps = false
      for (const prop of node.attributes.properties) {
        if (ts.isJsxAttribute(prop)) attrs.set(prop.name.getText(sf), prop.initializer)
        else if (ts.isObjectLiteralExpression(unwrap(prop.expression))) {
          for (const entry of (unwrap(prop.expression) as ts.ObjectLiteralExpression).properties) {
            if (ts.isPropertyAssignment(entry)) attrs.set(entry.name.getText(sf).replace(/^["'`]|["'`]$/g, ''), entry.initializer)
          }
        } else spreadsProps = true
      }
      const tag = node.tagName.getText(sf)
      const autoComplete = attrs.get('autoComplete')
      const isNew = carries(autoComplete, namesNew)
      if (isNew || tag === 'PasswordField' || carries(attrs.get('type'), (text) => text === 'password')) {
        const min = attrs.get('minLength')
        const minExpression = min && ts.isJsxExpression(min) ? min.expression : (min as ts.Expression | undefined)
        out.push({
          line: lineOf(sf, node),
          tag,
          id: (attrs.get('id') as ts.StringLiteral | undefined)?.text ?? '',
          kind: isNew ? 'new' : carries(autoComplete, namesCurrent) ? 'current' : attrs.has('autoComplete') || spreadsProps ? 'forwarded' : 'unnamed',
          floor: !!minExpression && minExpression.getText(sf) === 'PASSWORD_MIN_LENGTH',
        })
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out
}
const describeField = (rel: string, field: Field) => `${rel}:${field.line} <${field.tag}>`

/** New-password JSX fields whose `minLength` is not the shared constant. */
const fieldsWithoutFloor = (source: string, rel: string) =>
  passwordFields(source, rel)
    .filter((field) => field.kind === 'new' && !field.floor)
    .map((field) => describeField(rel, field))
/** Password fields with no `autoComplete` this scan can read or follow. */
const unnamedFields = (source: string, rel: string) =>
  passwordFields(source, rel)
    .filter((field) => field.kind === 'unnamed')
    .map((field) => describeField(rel, field))

/** Whether a form checks `….length < PASSWORD_MIN_LENGTH` in its code; a comment or a string does not count. */
function checksFloorInCode(source: string, rel: string): boolean {
  const visit = (node: ts.Node): boolean =>
    (ts.isBinaryExpression(node) &&
      node.operatorToken.kind === ts.SyntaxKind.LessThanToken &&
      ts.isPropertyAccessExpression(node.left) &&
      node.left.name.text === 'length' &&
      ts.isIdentifier(node.right) &&
      node.right.text === 'PASSWORD_MIN_LENGTH') ||
    (ts.forEachChild(node, (child) => visit(child) || undefined) ?? false)
  return visit(parse(source, rel))
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

const ALL_FILES = SOURCE_ROOTS.flatMap((root) => walk(path.join(frontendDir, root)))
const FILES = ALL_FILES.filter((file) => READ.test(file))
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
    expect(
      ALL_FILES.filter((file) => !READ.test(file) && !(path.extname(file) in NOT_READ)).map(rel),
      'a file the scan does not read: read its extension (READ), or list it in NOT_READ with why it holds no password rule',
    ).toEqual([])
    const handling = FILES.filter((file) => HANDLES_PASSWORD.test(readFileSync(file, 'utf8'))).map(rel)
    expect(handling).toEqual(expect.arrayContaining([...RULE_SITES, 'app/login/page.tsx']))
  })

  it('no file that handles a password writes a length by hand', () => {
    const offenders = FILES.filter((file) => rel(file) !== RULE_FILE).flatMap((file) => {
      const source = readFileSync(file, 'utf8')
      return [...handTyped(source, rel(file)), ...floorNumbers(source, rel(file)), ...codeForms(source, rel(file))]
    })
    expect(offenders, "use PASSWORD_MIN_LENGTH / PASSWORD_RULE from '@/lib/passwordRules'").toEqual([])
  })

  it('every new-password field carries minLength={PASSWORD_MIN_LENGTH}, or its form checks the floor in code', () => {
    const sources = FILES.map((file) => ({ rel: rel(file), source: readFileSync(file, 'utf8') }))
    // The scan finds the app's new-password fields: a check that reads none must not pass.
    const found = sources.flatMap(({ rel, source }) => passwordFields(source, rel).filter((f) => f.kind === 'new').map((f) => `${rel} <${f.tag} id="${f.id}">`))
    expect(found).toEqual(
      expect.arrayContaining([
        'app/reset-password/page.tsx <PasswordField id="password">',
        'app/reset-password/page.tsx <PasswordField id="confirm">',
        'features/auth/components/RegisterForm.tsx <PasswordField id="password">',
        'features/settings/components/ChangePasswordForm.tsx <Input id="new_pw">',
        'features/settings/components/ChangePasswordForm.tsx <Input id="confirm_pw">',
      ]),
    )
    expect(
      sources.flatMap(({ rel, source }) => unnamedFields(source, rel)),
      "name the field's autoComplete (new-password or current-password), so this check can tell which it is",
    ).toEqual([])
    const missing = sources.filter(({ rel }) => !(rel in CODE_CHECKED)).flatMap(({ rel, source }) => fieldsWithoutFloor(source, rel))
    expect(missing, 'give the field minLength={PASSWORD_MIN_LENGTH}').toEqual([])
    for (const file of Object.keys(CODE_CHECKED)) {
      expect(checksFloorInCode(readFileSync(path.join(frontendDir, file), 'utf8'), file), `${file} must check .length < PASSWORD_MIN_LENGTH in its code`).toBe(true)
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
    // What a line scan cannot see (the principal review's forms), at any count where a file handles a
    // password: copy composed across JSX, a comparison through a constant of any name, a minimum call, a pattern.
    expect(
      codeForms(
        [
          form.trimEnd(),
          'const a = <p>At least {8} characters.</p>',
          'const b = (',
          '  <p>',
          '    At least 8',
          '    characters.',
          '  </p>',
          ')',
          'const GAP = 8',
          'if (pw.length < GAP) {}',
          'const schema = z.string().min(8)',
          'const c = <input type="password" pattern=".{8,}" />',
          // The shared constant, a count computed at runtime and Math.min are not a hand-typed length.
          'const d = <p>At least {PASSWORD_MIN_LENGTH} characters, {Math.min(a, 8)} left.</p>',
          'if (items.length > 0 && pw.length < PASSWORD_MIN_LENGTH) {}',
        ].join('\n'),
        'probe.tsx',
      ),
    ).toEqual([
      'probe.tsx:2 (copy composed across JSX): At least 8 characters.',
      'probe.tsx:4 (copy composed across JSX): At least 8 characters.',
      'probe.tsx:10 (a length compared against a number): pw.length < GAP',
      'probe.tsx:11 (a minimum call): z.string().min(8)',
      'probe.tsx:12 (a pattern minimum): ".{8,}"',
    ])
    // Where a file only mentions a password: the floor in those forms, and no other count.
    expect(
      codeForms(
        [
          '// password note',
          `const a = <p>At least {${PASSWORD_MIN_LENGTH}} characters.</p>`,
          `const n = ${PASSWORD_MIN_LENGTH}`,
          'if (pw.length < n) {}',
          `const schema = z.string().min(${PASSWORD_MIN_LENGTH})`,
          `const re = /^.{${PASSWORD_MIN_LENGTH},}$/`,
          'const b = <p>At most {400} characters.</p>',
          'const LIMIT = 400',
          'if (note.length > LIMIT) {}',
        ].join('\n'),
        'note.tsx',
      ),
    ).toEqual([
      `note.tsx:2 (copy composed across JSX): At least ${PASSWORD_MIN_LENGTH} characters.`,
      'note.tsx:4 (a length compared against a number): pw.length < n',
      `note.tsx:5 (a minimum call): z.string().min(${PASSWORD_MIN_LENGTH})`,
      `note.tsx:6 (a pattern minimum): /^.{${PASSWORD_MIN_LENGTH},}$/`,
    ])
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
    const spreads = [
      // A spread object is read like attributes written out.
      "<PasswordField id=\"i\" {...{ autoComplete: 'new-password' }} />",
      "<PasswordField id=\"j\" {...{ autoComplete: 'new-password', minLength: PASSWORD_MIN_LENGTH }} />",
      // A password field names its autoComplete or forwards one (a spread of props); a field it cannot read fails.
      '<Input id="k" type="password" name="new_password" />',
      '<Input id="l" type="password" {...rest} />',
      "<input id=\"m\" type={show ? 'text' : 'password'} autoComplete={autoComplete} />",
    ].join('\n')
    expect(fieldsWithoutFloor(spreads, 'probe.tsx')).toEqual(['probe.tsx:1 <PasswordField>'])
    expect(unnamedFields(spreads, 'probe.tsx')).toEqual(['probe.tsx:3 <Input>'])
    // CODE_CHECKED's check is read on the syntax tree: a comment or a string does not count.
    expect(checksFloorInCode('// if (next.length < PASSWORD_MIN_LENGTH) {}\nconst s = "next.length < PASSWORD_MIN_LENGTH"', 'probe.tsx')).toBe(false)
    expect(checksFloorInCode('if (next.length < PASSWORD_MIN_LENGTH) {}', 'probe.tsx')).toBe(true)
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
