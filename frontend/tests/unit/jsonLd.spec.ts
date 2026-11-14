import { describe, expect, it } from 'vitest'
import { jsonLdHtml } from '@/lib/jsonLd'

describe('jsonLdHtml', () => {
  it('never lets a value close the script element, and still parses back to the same object', () => {
    const data = { name: 'Acme </script><script>alert(1)</script> Corp', nested: { form: '<10-K>' } }
    const html = jsonLdHtml(data)
    expect(html).not.toContain('<')
    expect(JSON.parse(html)).toEqual(data)
  })

  it('leaves a payload without `<` exactly as JSON.stringify writes it', () => {
    const data = { '@type': 'Corporation', name: 'Acme & Sons' }
    expect(jsonLdHtml(data)).toBe(JSON.stringify(data))
  })
})
