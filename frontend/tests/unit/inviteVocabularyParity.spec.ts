import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { DELIVERY_STATUSES, EMAIL_SUPPRESSIONS, PERMISSION_VIA } from '@/features/admin/api/admin-api'
import { COLLECTION_REASONS, INVITATION_EMAIL_REASONS } from '@/features/admin/lib/inviteReadiness'

/**
 * The admin invites page restates the backend's invitation vocabularies: the delivery states, the suppression reasons
 * and the permission channels (backend/app/models/invite_mail.py), and the readiness reason codes
 * (backend/app/services/legal_readiness_service.py). A code the page does not know falls back to words that claim
 * nothing ("Delivery state not recognized", "Something this page doesn't recognize holds it."), so a backend code added
 * or renamed without the page would pass every other test. These cases read the backend sources, so such a change
 * fails here until the page has words for it (rule 12; review of #1965).
 */
const BACKEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../backend')
const source = (rel: string) => readFileSync(path.join(BACKEND, rel), 'utf8')

/** Each `NAME = "value"` string constant at a module's top level. */
function stringConstants(text: string): Map<string, string> {
  const found = new Map<string, string>()
  for (const match of text.matchAll(/^([A-Z][A-Z0-9_]*) = "([^"]*)"/gm)) found.set(match[1], match[2])
  return found
}

/** The values of a top-level tuple, `NAME = (A, B, ...)`, each a constant's name or a string literal. */
function tupleValues(text: string, name: string): string[] {
  const match = new RegExp(`^${name} = \\(([^)]*)\\)`, 'm').exec(text)
  if (!match) throw new Error(`${name} is not a tuple at the top of the module`)
  const constants = stringConstants(text)
  return match[1].split(',').map((item) => item.trim()).filter(Boolean).map((item) => {
    const literal = /^"([^"]*)"$/.exec(item)
    if (literal) return literal[1]
    const value = constants.get(item)
    if (value === undefined) throw new Error(`${name} names ${item}, which is no string constant in the module`)
    return value
  })
}

/** The string constants between a comment line that starts with `from` and the next comment line or blank line. */
function codesUnder(text: string, from: string): string[] {
  const lines = text.split('\n')
  const start = lines.findIndex((line) => line.startsWith(from))
  if (start < 0) throw new Error(`no comment starting "${from}"`)
  const codes: string[] = []
  for (const line of lines.slice(start + 1)) {
    if (!line.trim() || line.startsWith('#')) break
    const match = /^[A-Z][A-Z0-9_]* = "([^"]*)"/.exec(line)
    if (match) codes.push(match[1])
  }
  if (!codes.length) throw new Error(`no codes under "${from}"`)
  return codes
}

const sorted = (values: Iterable<string>) => [...values].sort()

describe("the admin invites page knows every code the backend sends (backend sources, read here)", () => {
  const models = source('app/models/invite_mail.py')
  const readiness = source('app/services/legal_readiness_service.py')

  it('the delivery states are the ledger\'s (invite_mail.DELIVERY_STATUSES)', () => {
    expect(sorted(DELIVERY_STATUSES)).toEqual(sorted(tupleValues(models, 'DELIVERY_STATUSES')))
  })

  it('the suppression reasons are the list\'s (invite_mail.SUPPRESSION_REASONS)', () => {
    expect(sorted(EMAIL_SUPPRESSIONS)).toEqual(sorted(tupleValues(models, 'SUPPRESSION_REASONS')))
  })

  it('the permission channels are the record\'s (invite_mail.PERMISSION_VIA)', () => {
    expect(sorted(PERMISSION_VIA)).toEqual(sorted(tupleValues(models, 'PERMISSION_VIA')))
  })

  it('the page has words for every reason collection is held, and no others', () => {
    expect(sorted(Object.keys(COLLECTION_REASONS))).toEqual(sorted(codesUnder(readiness, '# Why new collection is held')))
  })

  it('the page has words for every reason invitation email is held, and no others', () => {
    expect(sorted(Object.keys(INVITATION_EMAIL_REASONS))).toEqual(
      sorted(codesUnder(readiness, '# Why requested invitation email is held')),
    )
  })
})
