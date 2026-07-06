import { describe, it, expect } from 'vitest'

import {
  DEFAULT_INVITE_MESSAGE,
  INVITE_SHARE_SUBJECT,
  buildInviteMessage,
  buildShareDeepLinks,
  isUnboundInvite,
  messageWithoutLink,
} from '@/features/admin/lib/shareLinks'

const LINK = 'https://earningsnerd.io/register?invite=abc123&t=1'

describe('buildInviteMessage', () => {
  it('substitutes {invite_link} with the raw link', () => {
    const msg = buildInviteMessage({ template: DEFAULT_INVITE_MESSAGE, link: LINK })
    expect(msg).toContain(LINK)
    expect(msg).not.toContain('{invite_link}')
  })

  it('substitutes {name} when a name is provided', () => {
    const msg = buildInviteMessage({ template: 'Hi {name}, here: {invite_link}', link: LINK, name: 'Dana' })
    expect(msg).toBe(`Hi Dana, here: ${LINK}`)
  })

  it('cleanly removes {name} (and a stray space) when no name is given', () => {
    expect(buildInviteMessage({ template: 'Hi {name}, here: {invite_link}', link: LINK })).toBe(
      `Hi, here: ${LINK}`,
    )
    expect(buildInviteMessage({ template: 'Hi {name}, here: {invite_link}', link: LINK, name: '   ' })).toBe(
      `Hi, here: ${LINK}`,
    )
  })

  it('replaces every occurrence of {invite_link}', () => {
    const msg = buildInviteMessage({ template: '{invite_link} ... {invite_link}', link: LINK })
    expect(msg).toBe(`${LINK} ... ${LINK}`)
  })
})

describe('messageWithoutLink', () => {
  it('strips the raw link and collapses the resulting whitespace', () => {
    const full = buildInviteMessage({ template: DEFAULT_INVITE_MESSAGE, link: LINK })
    const stripped = messageWithoutLink(full, LINK)
    expect(stripped).not.toContain(LINK)
    expect(stripped).not.toMatch(/\s{2,}/)
  })
})

describe('buildShareDeepLinks', () => {
  const message = buildInviteMessage({ template: DEFAULT_INVITE_MESSAGE, link: LINK })
  const links = buildShareDeepLinks(message)
  const encoded = encodeURIComponent(message)

  it('builds a wa.me link with the URL-encoded message', () => {
    expect(links.whatsapp).toBe(`https://wa.me/?text=${encoded}`)
  })

  it('builds an sms link with the URL-encoded message body', () => {
    expect(links.sms).toBe(`sms:?&body=${encoded}`)
  })

  it('builds a mailto link with an encoded subject and body', () => {
    expect(links.mailto).toBe(
      `mailto:?subject=${encodeURIComponent(INVITE_SHARE_SUBJECT)}&body=${encoded}`,
    )
  })

  it('URL-encodes special characters (& = ? : space) in free text', () => {
    // The message embeds the link's query string (&, =) plus spaces — none may leak raw.
    expect(links.whatsapp).not.toContain('invite=abc123&t=1')
    expect(links.whatsapp).toContain('%3A') // ':'
    expect(links.whatsapp).toContain('%3D') // '='
    expect(links.whatsapp).toContain('%26') // '&'
    expect(links.whatsapp).not.toContain(' ')
  })

  it('echoes the share subject', () => {
    expect(links.subject).toBe(INVITE_SHARE_SUBJECT)
  })
})

describe('isUnboundInvite', () => {
  it('flags a missing email (warning case)', () => {
    expect(isUnboundInvite(null)).toBe(true)
    expect(isUnboundInvite(undefined)).toBe(true)
    expect(isUnboundInvite('')).toBe(true)
    expect(isUnboundInvite('   ')).toBe(true)
  })

  it('does not flag a real email', () => {
    expect(isUnboundInvite('alice@example.com')).toBe(false)
  })
})
