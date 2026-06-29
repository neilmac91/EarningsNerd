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

// Per-ADS EPS (ADS-ratio correctness layer). For foreign issuers (ADRs) XBRL reports earnings
// per *ordinary share*; ADR investors hold ADSs, so the figure they care about is per-ADS
// (= per-ordinary-share × ordinary-shares-per-ADS). The ratio is sourced + dated (deposit
// agreement / 20-F cover) and the `arithmetic` string shows the full derivation, so the
// correction is auditable rather than an unexplained number. Present only on the EPS row of
// ratio != 1 ADRs.
export interface PerAdsValue {
  value: number
  ordinary_per_ads: number
  currency?: string | null
  as_of?: string | null
  source?: string | null
  arithmetic?: string | null
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
  // Per-ADS EPS, added by the backend for ratio != 1 ADRs (see PerAdsValue).
  per_ads?: PerAdsValue | null
}

export interface FinancialHighlights {
  title?: string | null
  notes?: string | null
  table?: Array<Record<string, string | number | null>>
  normalized?: SummarySchema | null
}
