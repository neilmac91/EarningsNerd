import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
import { middleware } from '@/middleware'
import { CONTACT_ADDRESSES, contactMailto } from '@/lib/contactAddresses'
import { GET } from '@/app/.well-known/security.txt/route'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const FIRST_PARTY_EMAIL = /[a-z0-9._%+-]+@earningsnerd\.io\b/i

function filesIn(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const file = path.join(directory, entry.name)
    return entry.isDirectory() ? filesIn(file) : /\.(tsx?|js)$/.test(file) ? [file] : []
  })
}

describe('public email configuration', () => {
  it('keeps first-party address literals out of shipped frontend code', () => {
    const files = ['app', 'components', 'features', 'hooks', 'lib'].flatMap((directory) =>
      filesIn(path.join(frontendRoot, directory)),
    )
    expect(files.length).toBeGreaterThan(100)
    const hardcoded: string[] = []
    for (const file of files) {
      const source = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true)
      const visit = (node: ts.Node) => {
        if ((ts.isStringLiteralLike(node) || ts.isTemplateHead(node) || ts.isTemplateMiddle(node) ||
          ts.isTemplateTail(node) || ts.isJsxText(node)) && FIRST_PARTY_EMAIL.test(node.text)) {
          hardcoded.push(`${path.relative(frontendRoot, file)}:${source.getLineAndCharacterOfPosition(node.getStart()).line + 1}`)
        }
        ts.forEachChild(node, visit)
      }
      visit(source)
    }
    expect(hardcoded, 'Import addresses from lib/contactAddresses.ts, which reads the shared backend JSON.').toEqual([])
  })

  it('keeps security.txt discoverable while the waitlist gate is enabled', () => {
    vi.stubEnv('WAITLIST_MODE', 'true')
    try {
      const response = middleware(new NextRequest('https://www.earningsnerd.io/.well-known/security.txt'))
      expect(response.status).toBe(200)
      expect(response.headers.get('location')).toBeNull()
    } finally {
      vi.unstubAllEnvs()
    }
  })

  it('publishes a reply-able RFC 9116 contact with a valid expiry and plain-text response', async () => {
    const response = GET()
    expect(response.status).toBe(200)
    expect(response.headers.get('Content-Type')).toBe('text/plain; charset=utf-8')
    const content = await response.text()
    expect(content).toContain(`Contact: ${contactMailto('security')}\n`)
    expect(content).toContain('Canonical: https://www.earningsnerd.io/.well-known/security.txt\n')
    expect(content).toContain('Preferred-Languages: en\n')
    expect(content).toContain('Policy: https://www.earningsnerd.io/security\n')
    expect(CONTACT_ADDRESSES.security).toMatch(FIRST_PARTY_EMAIL)
    const expiry = Date.parse(content.match(/^Expires: (.+)$/m)?.[1] ?? '')
    expect(expiry).toBeGreaterThan(Date.now())
    expect(expiry - Date.now()).toBeLessThan(366 * 24 * 60 * 60 * 1000)
  })
})
