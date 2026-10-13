import { readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

// Mutable holders the hoisted mocks can read (vi.mock factories are hoisted above imports).
const h = vi.hoisted(() => ({
  enableAnalysis: false,
  notFound: vi.fn(() => {
    throw new Error('NEXT_NOT_FOUND')
  }),
}))

vi.mock('next/navigation', () => ({ notFound: h.notFound, useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/lib/featureFlags', () => ({
  get ENABLE_ANALYSIS() {
    return h.enableAnalysis
  },
}))

import AnalysisLayout from '@/app/analysis/layout'
import UpgradeModal from '@/features/subscriptions/components/UpgradeModal'

describe('Analysis route gating (NEXT_PUBLIC_ENABLE_ANALYSIS)', () => {
  beforeEach(() => {
    h.notFound.mockClear()
  })

  it('404s /analysis when the flag is off', () => {
    h.enableAnalysis = false
    expect(() => AnalysisLayout({ children: 'gated' })).toThrow('NEXT_NOT_FOUND')
    expect(h.notFound).toHaveBeenCalledTimes(1)
  })

  it('renders the route when the flag is on', () => {
    h.enableAnalysis = true
    const out = AnalysisLayout({ children: 'visible' })
    expect(h.notFound).not.toHaveBeenCalled()
    expect(out).toBeTruthy()
  })
})

/**
 * Shipped-flag truth for the Pro feature list (DSW-05, D-033): the upgrade dialog names Multi-Period
 * Analysis only while the flag ships it, and the list is typed once, in lib/planLimits.ts
 * (proIncludes), so no second copy can keep advertising a feature that ships off.
 */
describe('The Pro feature list follows NEXT_PUBLIC_ENABLE_ANALYSIS', () => {
  it('leaves Multi-Period Analysis out while the flag is off', () => {
    h.enableAnalysis = false
    render(<UpgradeModal open onClose={() => {}} feature="PDF export" />)
    expect(
      screen.getByText('PDF export is a Pro feature. Pro includes unlimited summaries, hourly filing alerts, 8-K alerts and exports.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('dialog')).not.toHaveTextContent(/Multi-Period Analysis/i)
  })

  it('names Multi-Period Analysis while the flag is on', () => {
    h.enableAnalysis = true
    render(<UpgradeModal open onClose={() => {}} />)
    expect(
      screen.getByText('Pro includes unlimited summaries, hourly filing alerts, 8-K alerts, exports and Multi-Period Analysis.'),
    ).toBeInTheDocument()
  })

  it('no other source file types a Pro feature list of its own', () => {
    const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
    const roots = ['app', 'features', 'components', 'lib', 'hooks']
    const walk = (dir: string): string[] =>
      readdirSync(dir).flatMap((name) => {
        const full = path.join(dir, name)
        if (statSync(full).isDirectory()) return walk(full)
        return /\.(ts|tsx)$/.test(name) ? [full] : []
      })
    const offenders: string[] = []
    for (const root of roots) {
      for (const file of walk(path.join(frontendDir, root))) {
        const rel = path.relative(frontendDir, file).split(path.sep).join('/')
        if (rel === 'lib/planLimits.ts') continue
        readFileSync(file, 'utf8').split('\n').forEach((line, i) => {
          if (/\bPro includes\b/i.test(line)) offenders.push(`${rel}:${i + 1} ${line.trim()}`)
        })
      }
    }
    expect(offenders).toEqual([])
  })
})
