export interface NormalizedFact {
  metric: string
  currentPeriod?: string | null
  priorPeriod?: string | null
  commentary?: string | null
  currentValue?: number | null
  priorValue?: number | null
  deltaValue?: number | null
  deltaPercent?: number | null
}

export interface SummarySchema {
  metrics: NormalizedFact[]
  notes?: string | null
  hasPriorPeriod: boolean
}

export interface RiskFactor {
  summary: string
  supporting_evidence: string
  title?: string | null
  description?: string | null
}

export interface MetricItem {
  metric: string
  current_period: string
  prior_period: string
  commentary?: string
}

export interface FinancialHighlights {
  title?: string | null
  notes?: string | null
  table?: Array<Record<string, string | number | null>>
  normalized?: SummarySchema | null
}
