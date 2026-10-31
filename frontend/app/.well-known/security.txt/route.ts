import { contactMailto } from '@/lib/contactAddresses'

export function GET(): Response {
  const content = [
    `Contact: ${contactMailto('security')}`,
    'Expires: 2027-09-30T00:00:00Z',
    'Canonical: https://www.earningsnerd.io/.well-known/security.txt',
    'Preferred-Languages: en',
    'Policy: https://www.earningsnerd.io/security',
    '',
  ].join('\n')

  return new Response(content, {
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  })
}
