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
  // Trace-to-Source provenance (added by the backend at serialization time).
  source_url?: string | null
  source_verified?: boolean | null
  source_section_ref?: string | null
}

export interface MetricItem {
  metric: string
  current_period: string
  prior_period: string
  commentary?: string
  // Trace-to-Source provenance (added by the backend at serialization time).
  source_url?: string | null
  source_verified?: boolean | null
  source_section_ref?: string | null
  xbrl_concept?: string | null
}

export interface FinancialHighlights {
  title?: string | null
  notes?: string | null
  table?: Array<Record<string, string | number | null>>
  normalized?: SummarySchema | null
}
