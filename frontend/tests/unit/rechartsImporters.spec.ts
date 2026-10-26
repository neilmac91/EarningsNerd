import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

/** Recharts reaches only the two charts not yet on the engine; the analysis route loads none of it (E195).
 *  Shrink-only: moving either onto the engine deletes its line. */
const IMPORTERS = [
  'features/fundamentals/components/FundamentalsTrendChart.tsx',
  'features/peers/components/PeerComparisonPanel.tsx',
]

describe('recharts importers', () => {
  it('only the charts not yet on the engine import recharts', () => {
    const files = execFileSync('git', ['ls-files', 'app', 'components', 'features', 'hooks', 'lib'], { encoding: 'utf8' })
      .split('\n').filter((file) => /\.(ts|tsx)$/.test(file))
    const importers = files.filter((file) => /(from\s+|import\s*\(\s*|import\s+)['"]recharts(\/[^'"]*)?['"]/.test(readFileSync(file, 'utf8')))
    expect(importers.sort()).toEqual(IMPORTERS)
  })
})
