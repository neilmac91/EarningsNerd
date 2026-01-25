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

// Placeholder patterns that indicate missing or unavailable data
const PLACEHOLDER_PATTERNS = [
  'not available',
  'unavailable',
  'n/a',
  'retry',
  'requires full',
  'data pending',
  'being processed',
  'taking longer',
  'preliminary',
  'placeholder',
  'available in the full',
]

// Check if a string contains placeholder content
function isPlaceholderText(text: string | undefined | null): boolean {
  if (!text || typeof text !== 'string') return true
  const lowerText = text.toLowerCase().trim()
  if (lowerText.length === 0) return true
  return PLACEHOLDER_PATTERNS.some(pattern => lowerText.includes(pattern))
}

// Check if a metric has real data (not placeholder)
function hasRealMetricData(metric: MetricItem): boolean {
  const currentValid = metric.current_period && !isPlaceholderText(metric.current_period)
  const priorValid = metric.prior_period && !isPlaceholderText(metric.prior_period)
  return Boolean(currentValid || priorValid)
}

// Check if content has real substantive data
function hasRealContent(content: unknown): boolean {
  if (!content) return false

  if (typeof content === 'string') {
    return !isPlaceholderText(content) && content.trim().length > 20
  }

  if (Array.isArray(content)) {
    return content.some(item => hasRealContent(item))
  }

  if (typeof content === 'object') {
    const values = Object.values(content as Record<string, unknown>)
    return values.some(val => hasRealContent(val))
  }

  return Boolean(content)
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
      .filter((risk): risk is RiskFactor => {
        if (!risk || !risk.supporting_evidence) return false
        // Filter out placeholder risks
        if (isPlaceholderText(risk.supporting_evidence)) return false
        if (risk.description && isPlaceholderText(risk.description)) return false
        return true
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sections.risk_factors])

  // Content Checkers - Enhanced to detect placeholder content
  const overviewContent = sections.executive_snapshot
    ? renderMarkdownValue(sections.executive_snapshot)
    : (summary.business_overview || '')

  // Overview is valid if it has content and isn't just placeholder text
  const hasOverview = Boolean(overviewContent) && !isPlaceholderText(overviewContent)

  // Financials: check for real metric data, not just array presence
  const validMetrics = metrics?.filter(hasRealMetricData) ?? []
  const hasFinancials = Boolean(
    (sections.financial_highlights?.notes && !isPlaceholderText(sections.financial_highlights.notes)) ||
    validMetrics.length > 0
  )

  // Risks: already filtered for placeholder content above
  const hasRisks = normalizedRisks.length > 0

  // MD&A: check for real content
  const hasManagement = hasRealContent(sections.management_discussion_insights)

  // Guidance: check accordion content isn't placeholder
  const guidanceContent = getAccordionContent(sections.guidance_outlook)
  const hasGuidance = Boolean(guidanceContent) && !isPlaceholderText(guidanceContent)

  // Liquidity: check both liquidity and footnotes content
  const liquidityContent = getAccordionContent(sections.liquidity_capital_structure)
  const footnotesContent = getAccordionContent(sections.notable_footnotes)
  const hasLiquidity = (Boolean(liquidityContent) && !isPlaceholderText(liquidityContent)) ||
                       (Boolean(footnotesContent) && !isPlaceholderText(footnotesContent))

  // Trends: check for real content, not just object presence
  const hasTrends = hasRealContent(sections.three_year_trend) || hasRealContent(sections.segment_performance)

  // Tab Configuration - Per execution plan: hide sections where data cannot be found
  // Only show tabs that have content (dynamic section hiding)
  // Note: Executive Summary is ALWAYS shown to display unavailable sections disclosure
  const allTabs = [
    { id: 'overview', label: 'Executive Summary', icon: FileText, hasContent: true },  // Always show
    { id: 'financials', label: 'Financials', icon: BarChart3, hasContent: hasFinancials },
    { id: 'risks', label: 'Risks', icon: AlertTriangle, hasContent: hasRisks },
    { id: 'management', label: 'MD&A', icon: Building2, hasContent: hasManagement },
    { id: 'guidance', label: 'Guidance', icon: TrendingUp, hasContent: hasGuidance },
    { id: 'liquidity', label: 'Liquidity', icon: Building2, hasContent: hasLiquidity },
    { id: 'trends', label: 'Trends', icon: TrendingUp, hasContent: hasTrends },
  ]

  // Filter to only show tabs with content (hide empty sections per execution plan)
  const tabs = allTabs.filter(tab => tab.hasContent)

  // Track unavailable sections for Executive Summary disclosure
  const unavailableSections = allTabs
    .filter(tab => !tab.hasContent && tab.id !== 'overview')
    .map(tab => tab.label)

  // Ensure active tab is valid (if current tab became hidden, switch to first available)
  React.useEffect(() => {
    const currentTabExists = tabs.some(tab => tab.id === activeTab)
    if (!currentTabExists && tabs.length > 0) {
      setActiveTab(tabs[0].id)
    }
  }, [tabs, activeTab])

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return (
          <div>
            {hasOverview ? (
              <SummaryExecutiveSnapshot content={overviewContent} />
            ) : (
              <div className="text-center py-8">
                <p className="text-slate-500">
                  Executive summary is being processed. Please retry for full analysis.
                </p>
              </div>
            )}
            {/* Per execution plan: Executive Summary must note unavailable sections */}
            {unavailableSections.length > 0 && (
              <div className="mt-6 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-200 dark:border-slate-700">
                <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-2">
                  Not included in this filing:
                </p>
                <ul className="text-sm text-slate-500 dark:text-slate-500 space-y-1">
                  {unavailableSections.map((section) => (
                    <li key={section} className="flex items-center space-x-2">
                      <span className="w-1.5 h-1.5 bg-slate-400 rounded-full"></span>
                      <span>{section} data was not available</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )

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

            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`
                  group flex items-center space-x-2 px-4 py-4 text-sm font-medium border-b-2 transition-all duration-200 outline-none
                  ${isActive
                    ? 'border-emerald-500 text-emerald-700 bg-emerald-50/50'
                    : 'border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-50'
                  }
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
