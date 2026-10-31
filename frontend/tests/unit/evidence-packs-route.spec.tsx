import React from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('next/navigation', () => ({ notFound: () => { throw new Error('NOT_FOUND') } }))
afterEach(() => { vi.unstubAllEnvs(); vi.resetModules() })

describe('research evidence route flag', () => {
  it.each([undefined, 'false', 'TRUE', '1'])('returns notFound when flag is %j', async (value) => {
    vi.stubEnv('NEXT_PUBLIC_ENABLE_RESEARCH_EVIDENCE_PACKS', value)
    vi.resetModules()
    const { default: Layout } = await import('@/app/labs/research-evidence-packs/layout')
    expect(() => Layout({ children: <p>Hidden</p> })).toThrow('NOT_FOUND')
  })
  it('mounts only with the explicit true flag', async () => {
    vi.stubEnv('NEXT_PUBLIC_ENABLE_RESEARCH_EVIDENCE_PACKS', 'true')
    vi.resetModules()
    const { default: Layout } = await import('@/app/labs/research-evidence-packs/layout')
    expect(Layout({ children: <p>Prototype</p> }).props.children.props.children).toBe('Prototype')
  })
})
