'use client'

import React, { useMemo, useState } from 'react'
import { FileText, TrendingUp, AlertTriangle, Building2, BarChart3 } from 'lucide-react'
import type { RiskFactor, MetricItem } from '../types/summary'
import { renderMarkdownValue, getAccordionContent, normalizeRisk } from '../lib/formatters'
import { SummaryExecutiveSnapshot } from '@/features/filings/components/SummaryExecutiveSnapshot'
import { SummaryFinancials } from '@/features/filings/components/SummaryFinancials'
import { SummaryRisks } from '@/features/filings/components/SummaryRisks'
import { SummaryMDA } from '@/features/filings/components/SummaryMDA'
import { SummaryGuidance } from '@/features/filings/components/SummaryGuidance'
import { SummaryLiquidity } from '@/features/filings/components/SummaryLiquidity'
import { SummaryTrends } from '@/features/filings/components/SummaryTrends'

interface RawSummaryData {
  sections?: Record<string, unknown>
  section_coverage?: {
    covered_count?: number
    total_count?: number
    coverage_ratio?: number
  }
  writer_error?: string
  writer?: {
    fallback_used?: boolean
    fallback_reason?: string
  }
}

interface SectionsData {
  executive_snapshot?: unknown
  financial_highlights?: {
    table?: MetricItem[]
    notes?: string
  }
  risk_factors?: unknown[]
  management_discussion_insights?: unknown
  guidance_outlook?: unknown
  liquidity_capital_structure?: unknown
  notable_footnotes?: unknown
  three_year_trend?: unknown
  segment_performance?: unknown
  [key: string]: unknown
}

interface SummarySectionsProps {
  summary: {
    business_overview?: string
    raw_summary?: RawSummaryData | null
  }
  metrics?: MetricItem[]
}

export default function SummarySections({ summary, metrics }: SummarySectionsProps) {
  const [activeTab, setActiveTab] = useState<string>('overview')

  const raw_summary = summary.raw_summary || {}
  const sections: SectionsData = (raw_summary.sections as SectionsData) || {}

  const normalizedRisks = useMemo(() => {
    const rawRisks = sections.risk_factors
    if (!Array.isArray(rawRisks)) {
      return [] as RiskFactor[]
    }
    return rawRisks
      .map((risk: unknown) => normalizeRisk(risk))
      .filter((risk): risk is RiskFactor => Boolean(risk && risk.supporting_evidence))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sections.risk_factors])

  // Content Checkers
  const overviewContent = sections.executive_snapshot 
    ? renderMarkdownValue(sections.executive_snapshot) 
    : (summary.business_overview || '')
  
  const hasOverview = Boolean(overviewContent)
  const hasFinancials = Boolean(sections.financial_highlights?.notes || (metrics && metrics.length > 0))
  const hasRisks = normalizedRisks.length > 0
  const hasManagement = Boolean(sections.management_discussion_insights)
  
  const guidanceContent = getAccordionContent(sections.guidance_outlook)
  const hasGuidance = Boolean(guidanceContent)

  const liquidityContent = getAccordionContent(sections.liquidity_capital_structure)
  const footnotesContent = getAccordionContent(sections.notable_footnotes)
  const hasLiquidity = Boolean(liquidityContent || footnotesContent)
  
  const hasTrends = Boolean(sections.three_year_trend || sections.segment_performance)

  // Ghost Tabs Configuration
  const tabs = [
    { id: 'overview', label: 'Executive Summary', icon: FileText, hasContent: hasOverview },
    { id: 'financials', label: 'Financials', icon: BarChart3, hasContent: hasFinancials },
    { id: 'risks', label: 'Risks', icon: AlertTriangle, hasContent: hasRisks },
    { id: 'management', label: 'MD&A', icon: Building2, hasContent: hasManagement },
    { id: 'guidance', label: 'Guidance', icon: TrendingUp, hasContent: hasGuidance },
    { id: 'liquidity', label: 'Liquidity', icon: Building2, hasContent: hasLiquidity },
    { id: 'trends', label: 'Trends', icon: TrendingUp, hasContent: hasTrends },
  ]

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return <SummaryExecutiveSnapshot content={overviewContent} />

      case 'financials':
        return <SummaryFinancials notes={sections.financial_highlights?.notes} metrics={metrics} />

      case 'risks':
        return <SummaryRisks risks={normalizedRisks} />

      case 'management':
        return <SummaryMDA content={sections.management_discussion_insights} />

      case 'guidance':
        return <SummaryGuidance content={guidanceContent} />

      case 'liquidity':
        return <SummaryLiquidity liquidityContent={liquidityContent} footnotesContent={footnotesContent} />

      case 'trends':
        return <SummaryTrends threeYearTrend={sections.three_year_trend} segmentPerformance={sections.segment_performance} />

      default:
        return null
    }
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      {/* Scrollable Tabs Container */}
      <div className="border-b border-slate-200 overflow-x-auto">
        <nav className="flex min-w-max px-2" aria-label="Tabs">
          {tabs.map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            const isDisabled = !tab.hasContent

            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                title={isDisabled ? "No data available in this filing" : ""}
                className={`
                  group flex items-center space-x-2 px-4 py-4 text-sm font-medium border-b-2 transition-all duration-200 outline-none
                  ${isActive
                    ? 'border-emerald-500 text-emerald-700 bg-emerald-50/50'
                    : 'border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-50'
                  }
                  ${isDisabled ? 'text-slate-400 opacity-60 hover:text-slate-500 hover:bg-slate-50 cursor-not-allowed' : ''}
                `}
              >
                <Icon className={`h-4 w-4 ${isActive ? 'text-emerald-600' : 'text-slate-400'}`} />
                <span>{tab.label}</span>
              </button>
            )
          })}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="p-6 min-h-[300px]">
        {renderTabContent()}
      </div>
    </div>
  )
}
