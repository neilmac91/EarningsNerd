import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
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
 *    PASSWORD_MIN_LENGTH, read by password_utils.validate_password_strength).
 *  - PASSWORD_RULE's "Breached passwords are rejected" stands only while the HaveIBeenPwned check
 *    defaults on (backend/app/config.py PWNED_PASSWORD_CHECK_ENABLED, backend/app/services/pwned_passwords.py).
 *  - No file that handles a password spells the length out; the pages that state or enforce it import it.
 *  - The strength meter says "Too short" for anything under the field's minimum.
 */
const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const backend = (rel: string) => readFileSync(path.resolve(frontendDir, '../backend', rel), 'utf8')

const SOURCE_ROOTS = ['app', 'features', 'components', 'lib', 'hooks']
/** The length written by hand, in a file that handles a password. */
const HAND_TYPED: Array<{ label: string; pattern: RegExp }> = [
  { label: 'a minLength literal', pattern: /minLength=\{\s*\d+\s*\}/ },
  { label: 'a length in copy', pattern: /\b\d+\s+characters\b/i },
  { label: 'a local minimum constant', pattern: /\b[A-Z_]*MIN_LENGTH\s*=\s*\d+/ },
]
/** The sites that state or enforce the rule (PasswordField takes it through its minLength prop). */
const RULE_SITES = [
  'app/reset-password/page.tsx',
  'features/auth/components/RegisterForm.tsx',
  'features/settings/components/ChangePasswordForm.tsx',
]

function walk(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) return entry.name === 'node_modules' ? [] : walk(full)
    return /\.(tsx?|mdx?)$/.test(entry.name) ? [full] : []
  })
}

describe('the password rule moves in lockstep with the backend', () => {
  it('mirrors PASSWORD_MIN_LENGTH, the minimum validate_password_strength enforces', () => {
    const match = backend('app/config.py').match(/^\s*PASSWORD_MIN_LENGTH:\s*int\s*=\s*(\d+)/m)
    if (!match) throw new Error('PASSWORD_MIN_LENGTH not found in backend/app/config.py')
    expect(PASSWORD_MIN_LENGTH).toBe(Number(match[1]))
    expect(backend('app/services/password_utils.py')).toMatch(/len\(value\) < settings\.PASSWORD_MIN_LENGTH/)
  })

  it('says breached passwords are rejected only while the breach check defaults on', () => {
    expect(PASSWORD_RULE).toContain('Breached passwords are rejected.')
    expect(backend('app/config.py')).toMatch(/^\s*PWNED_PASSWORD_CHECK_ENABLED:\s*bool\s*=\s*True\b/m)
  })

  it('no file that handles a password types the length by hand', () => {
    const offenders: string[] = []
    for (const root of SOURCE_ROOTS) {
      for (const file of walk(path.join(frontendDir, root))) {
        if (file.endsWith(path.join('lib', 'passwordRules.ts'))) continue
        const source = readFileSync(file, 'utf8')
        if (!/password/i.test(source)) continue
        source.split('\n').forEach((line, index) => {
          for (const { label, pattern } of HAND_TYPED) {
            if (pattern.test(line)) offenders.push(`${path.relative(frontendDir, file)}:${index + 1} (${label}): ${line.trim()}`)
          }
        })
      }
    }
    expect(offenders, "use PASSWORD_MIN_LENGTH / PASSWORD_RULE from '@/lib/passwordRules'").toEqual([])
  })

  it('the pages that state or enforce the rule read it from lib/passwordRules', () => {
    for (const rel of RULE_SITES) {
      expect(readFileSync(path.join(frontendDir, rel), 'utf8'), `${rel} must import from '@/lib/passwordRules'`).toMatch(
        /from '@\/lib\/passwordRules'/,
      )
    }
  })

  it('the strength meter says "Too short" under the minimum, whatever else the password holds', () => {
    const almost = 'Ab1!'.padEnd(PASSWORD_MIN_LENGTH - 1, 'x')
    const { rerender } = render(
      <PasswordField id="pw" label="Password" value={almost} onChange={() => {}} minLength={PASSWORD_MIN_LENGTH} showStrength />,
    )
    expect(screen.getByText('Too short')).toBeInTheDocument()
    rerender(
      <PasswordField id="pw" label="Password" value={`${almost}x`} onChange={() => {}} minLength={PASSWORD_MIN_LENGTH} showStrength />,
    )
    expect(screen.queryByText('Too short')).toBeNull()
    expect(screen.getByText('Strong')).toBeInTheDocument()
  })
})
