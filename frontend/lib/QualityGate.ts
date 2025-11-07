'use client'

import type { ComparisonData } from './api'
import { parseNumeric } from './format'

const FORBIDDEN_DISPLAY_VALUES = new Set(['n/a', 'na', 'nan', 'undefined'])

export interface QualityGateResult {
  ok: boolean
  message?: string
}

export const evaluateComparisonQuality = (data: ComparisonData): QualityGateResult => {
  if (!data?.comparison?.financial_metrics?.length) {
    return { ok: true }
  }

  const metricsByFiling = data.comparison.financial_metrics

  const targetLength = metricsByFiling[0]?.metrics?.length ?? 0
  for (const entry of metricsByFiling) {
    if (!Array.isArray(entry.metrics) || entry.metrics.length !== targetLength) {
      return {
        ok: false,
        message: 'Inconsistent metric rows detected across filings.',
      }
    }
  }

  for (const rowIndex of Array.from({ length: targetLength }, (_, idx) => idx)) {
    for (const column of metricsByFiling) {
      const metric = column.metrics[rowIndex]
      if (!metric) {
        return {
          ok: false,
          message: `Missing metric data in comparison row ${rowIndex + 1}.`,
        }
      }
      const candidate = metric.current_period ?? metric.currentPeriod ?? ''
      const raw = String(candidate ?? '').trim()
      if (!raw) {
        return {
          ok: false,
          message: `Empty comparison cell detected for metric "${metric.metric ?? 'unknown'}".`,
        }
      }
      const lowered = raw.toLowerCase()
      if (FORBIDDEN_DISPLAY_VALUES.has(lowered)) {
        return {
          ok: false,
          message: `Forbidden value "${raw}" detected for metric "${metric.metric ?? 'unknown'}".`,
        }
      }

      const numeric = parseNumeric(raw)
      if (numeric !== null && !Number.isFinite(numeric)) {
        return {
          ok: false,
          message: `Non-finite numeric value detected for metric "${metric.metric ?? 'unknown'}".`,
        }
      }
    }
  }

  return { ok: true }
}


