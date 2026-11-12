import { beforeEach, describe, expect, it } from 'vitest'
import { consumePostAuthRedirect, isSafeInternalPath, stashPostAuthRedirect } from '@/lib/postAuthRedirect'

/**
 * Where a login may send its reader (lib/postAuthRedirect.ts): the login page's `?redirect=`, and the destination the
 * signup gate or an OAuth start stashed, which a password login and the OAuth landing page consume. One rule decides
 * all of them, `isSafeInternalPath`, and it must agree with the browser, not with the string's first characters: a
 * URL parser removes tab, CR and LF wherever they stand and reads a backslash as a slash, so "/\t/evil.example"
 * starts with one slash and still resolves to another site. Until 2026-11-12 the rule checked the first characters
 * only, and a login link carrying such a value sent its reader to the other site after they logged in. The rule also
 * takes a path only in the parser's own form: a dot segment ("/.//evil.example") stays on the origin but parses to
 * the path "//evil.example", another site to anything that later reads that path by itself.
 */
const SITE = 'https://www.earningsnerd.io'
const STASH = 'en_post_auth_redirect'

const INTERNAL = [
  '/',
  '/filing/123',
  '/pricing?billing=monthly',
  '/dashboard/watchlist#alerts',
  '/search?q=apple%20inc',
  '/company/BRK.B',
  '/a//b',
  // An encoded tab or slash is data, not syntax: the parser leaves it in the path.
  '/%09/evil.example',
  '/redirect?to=%2F%2Fevil.example',
]

const REFUSED: [string, string][] = [
  ['an empty value', ''],
  ['a relative path', 'filing/123'],
  ['an absolute address', 'https://evil.example/'],
  ['a script address', 'javascript:alert(1)'],
  ['a protocol-relative address', '//evil.example'],
  ['a backslash after the slash', '/\\evil.example'],
  ['a tab the parser removes', '/\t/evil.example'],
  ['a line feed the parser removes', '/\n/evil.example'],
  ['a carriage return the parser removes', '/\r/evil.example'],
  ['a tab before a backslash', '/\t\\evil.example'],
  ['a backslash further in', '/filing\\..\\evil'],
  ['a NUL', '/\u0000/evil.example'],
  ['a DEL', '/filing/\u007f'],
  ['a leading space', ' /filing/123'],
  // On the origin, but the parser rewrites each to the path "//evil.example".
  ['a dot segment before a double slash', '/.//evil.example'],
  ['a double-dot segment before a double slash', '/..//evil.example'],
  ['an encoded dot segment before a double slash', '/%2e//evil.example'],
  ['a dot segment further in', '/a/..//evil.example'],
  // Harmless, but not in the parser's form: a destination this app builds never looks like this.
  ['a raw space the parser would encode', '/a b'],
]

beforeEach(() => {
  localStorage.clear()
})

describe('isSafeInternalPath', () => {
  it.each(INTERNAL)('accepts %s, which the browser keeps on this site and reads as written', (path) => {
    expect(isSafeInternalPath(path)).toBe(true)
    const parsed = new URL(path, `${SITE}/login`)
    expect(parsed.origin).toBe(SITE)
    expect(parsed.pathname + parsed.search + parsed.hash).toBe(path)
  })

  it.each(REFUSED)('refuses %s', (_name, path) => {
    expect(isSafeInternalPath(path)).toBe(false)
  })

  it('never accepts a path the browser reads as another site, or as a path that opens with two slashes, whatever ASCII character is planted in it', () => {
    const escapes: string[] = []
    for (let code = 0; code <= 0x7f; code += 1) {
      const c = String.fromCharCode(code)
      for (const path of [`/${c}/evil.example`, `/${c}${c}evil.example`, `/${c}\\evil.example`, `/a/..${c}/${c}/evil.example`, `/${c}/${c}/evil.example`, `/${c}${c}//evil.example`, `${c}/evil.example`, `/${c}`]) {
        let leaves: boolean
        try {
          const parsed = new URL(path, `${SITE}/login`)
          leaves = parsed.origin !== SITE || parsed.pathname.startsWith('//')
        } catch {
          leaves = true
        }
        if (leaves && isSafeInternalPath(path)) escapes.push(JSON.stringify(path))
      }
    }
    expect(escapes).toEqual([])
  })
})

describe('the stash takes and gives only an internal path', () => {
  it.each(REFUSED)('stores nothing for %s', (_name, path) => {
    stashPostAuthRedirect(path)
    expect(localStorage.getItem(STASH)).toBeNull()
  })

  it.each(REFUSED.filter(([, path]) => path !== ''))('gives nothing for a stored %s, and clears it', (_name, path) => {
    localStorage.setItem(STASH, JSON.stringify({ path, at: Date.now() }))
    expect(consumePostAuthRedirect()).toBeNull()
    expect(localStorage.getItem(STASH)).toBeNull()
  })

  it('gives an internal path once', () => {
    stashPostAuthRedirect('/filing/123')
    expect(consumePostAuthRedirect()).toBe('/filing/123')
    expect(consumePostAuthRedirect()).toBeNull()
  })
})
