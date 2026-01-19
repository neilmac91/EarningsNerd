'use client'

import React, { useMemo, useState } from 'react'
import { FileText, TrendingUp, AlertTriangle, Building2, BarChart3, HelpCircle } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { RiskFactor } from '../types/summary'
import { SummaryBlock } from './SummaryBlock'

interface MetricItem {
  metric: string
  current_period: string
  prior_period: string
  commentary?: string
}

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

  const evidenceKeys = ['excerpt', 'text', 'quote', 'source', 'reference', 'tag', 'xbrl_tag', 'xbrlTag', 'citation']

  const renderMarkdownValue = (value: unknown): string => {
    if (value === null || value === undefined) {
      return ''
    }
    if (typeof value === 'string') {
      return value
    }
    if (Array.isArray(value)) {
      const items = value
        .map((item) => {
          const rendered = renderMarkdownValue(item)
          return rendered ? `- ${rendered}` : ''
        })
        .filter(Boolean)
      return items.join('\n')
    }
    if (typeof value === 'object') {
      return Object.entries(value)
        .map(([key, val]) => {
          const formattedKey = key
            .replace(/_/g, ' ')
            .replace(/\b\w/g, (char) => char.toUpperCase())
          const rendered = renderMarkdownValue(val)
          if (!rendered) {
            return ''
          }
          if (typeof val === 'object' && val !== null) {
            return `${formattedKey}:\n${rendered}`
          }
          return `${formattedKey}: ${rendered}`
        })
        .filter(Boolean)
        .join('\n')
    }
    return String(value)
  }

  const getAccordionContent = (value: unknown): string | null => {
    if (value === null || value === undefined) {
      return null
    }

    const rendered = renderMarkdownValue(value)
    if (!rendered) {
      return null
    }

    return rendered.trim().length > 0 ? rendered : null
  }

  const formatEvidence = (value: unknown): string => {
    if (!value) return ''
    if (Array.isArray(value)) {
      const parts = value.map((item) => formatEvidence(item)).filter(Boolean)
      return parts.join('; ')
    }
    if (typeof value === 'object') {
      const parts: string[] = []
      evidenceKeys.forEach((key) => {
        if (value && typeof value === 'object' && key in value) {
          const part = formatEvidence((value as Record<string, unknown>)[key])
          if (part) {
            parts.push(part)
          }
        }
      })
      if (parts.length === 0 && 'value' in (value as Record<string, unknown>)) {
        const fallback = formatEvidence((value as Record<string, unknown>).value)
        if (fallback) {
          parts.push(fallback)
        }
      }
      return parts.join(' | ')
    }
    if (typeof value === 'string') {
      return value.trim()
    }
    return String(value).trim()
  }

  const normalizeRisk = (risk: unknown): RiskFactor | null => {
    if (!risk || typeof risk !== 'object') {
      return null
    }

    const riskObj = risk as Record<string, unknown>
    const title = typeof riskObj.title === 'string' ? riskObj.title.trim() : null
    const description = typeof riskObj.description === 'string' ? riskObj.description.trim() : null
    const summaryCandidate =
      (typeof riskObj.summary === 'string' && riskObj.summary.trim()) ||
      (description && description) ||
      (title && title) ||
      ''

    if (!summaryCandidate) {
      return null
    }

    const supportingEvidence = formatEvidence(
      riskObj.supporting_evidence ?? riskObj.supportingEvidence ?? riskObj.evidence ?? riskObj.source
    )

    if (!supportingEvidence) {
      return null
    }

    return {
      summary: summaryCandidate,
      supporting_evidence: supportingEvidence,
      title: title || null,
      description: description || null,
    }
  }

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
        if (!hasOverview) return <EmptyState label="Executive Summary" />
        return (
          <div className="prose max-w-none prose-slate">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {overviewContent}
            </ReactMarkdown>
          </div>
        )

      case 'financials':
        if (!hasFinancials) return <EmptyState label="Financial Highlights" />
        return (
          <div className="space-y-4">
            {sections.financial_highlights?.notes && (
              <SummaryBlock type="neutral" title="Analyst Notes">
                 {sections.financial_highlights.notes}
              </SummaryBlock>
            )}
            {metrics && metrics.length > 0 && (
              <div className="text-sm text-slate-600">
                <p>Key highlights from the reporting period:</p>
                <ul className="list-disc list-inside mt-2 space-y-1">
                  {metrics.slice(0, 5).map((m: MetricItem, i: number) => (
                    <li key={i}>
                      <span className="font-medium">{m.metric}:</span> {m.current_period} 
                      <span className="text-slate-400 mx-1">vs</span> 
                      {m.prior_period}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )

      case 'risks':
        if (!hasRisks) return <EmptyState label="Risk Factors" />
        return (
          <div className="space-y-4">
            {normalizedRisks.map((risk, index) => (
              <SummaryBlock 
                key={`${risk.summary}-${index}`} 
                type="bearish" 
                title={risk.title || 'Risk Factor'}
              >
                <div className="space-y-2">
                  <p>{risk.description || risk.summary}</p>
                  <div className="mt-2 text-xs bg-rose-50 text-rose-800 p-2 rounded border border-rose-100">
                    <span className="font-semibold uppercase tracking-wider text-[10px] mr-2">Evidence</span>
                    {risk.supporting_evidence}
                  </div>
                </div>
              </SummaryBlock>
            ))}
          </div>
        )

      case 'management':
        if (!hasManagement) return <EmptyState label="Management Discussion" />
        return (
          <div className="prose max-w-none prose-slate">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {renderMarkdownValue(sections.management_discussion_insights)}
            </ReactMarkdown>
          </div>
        )

      case 'guidance':
        if (!hasGuidance) return <EmptyState label="Guidance & Outlook" />
        return (
          <SummaryBlock type="neutral" title="Forward-Looking Statements">
            <div className="prose max-w-none prose-sm">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {guidanceContent}
              </ReactMarkdown>
            </div>
          </SummaryBlock>
        )

      case 'liquidity':
        if (!hasLiquidity) return <EmptyState label="Liquidity & Capital" />
        return (
          <div className="space-y-6">
            {liquidityContent && (
               <SummaryBlock type="neutral" title="Liquidity Position">
                <div className="prose max-w-none prose-sm">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {liquidityContent}
                  </ReactMarkdown>
                </div>
              </SummaryBlock>
            )}
            {footnotesContent && (
               <div className="mt-4 border-t border-slate-200 pt-4">
                <h3 className="text-sm font-semibold text-slate-900 mb-2 uppercase tracking-wide">Notable Footnotes</h3>
                <div className="prose max-w-none prose-sm text-slate-600">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {footnotesContent}
                  </ReactMarkdown>
                </div>
              </div>
            )}
          </div>
        )

      case 'trends':
        if (!hasTrends) return <EmptyState label="Trends & Segments" />
        return (
          <div className="space-y-6">
            {Boolean(sections.three_year_trend) && (
              <SummaryBlock type="bullish" title="Three-Year Trend Analysis">
                 <div className="prose max-w-none prose-sm">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {renderMarkdownValue(sections.three_year_trend)}
                  </ReactMarkdown>
                </div>
              </SummaryBlock>
            )}
            {Boolean(sections.segment_performance) && (
              <div className="mt-6">
                <h3 className="text-lg font-semibold text-slate-900 mb-3">Segment Performance</h3>
                <div className="prose max-w-none prose-slate">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {renderMarkdownValue(sections.segment_performance)}
                  </ReactMarkdown>
                </div>
              </div>
            )}
          </div>
        )

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

function EmptyState({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="bg-slate-100 p-4 rounded-full mb-4">
        <HelpCircle className="h-8 w-8 text-slate-400" />
      </div>
      <h3 className="text-lg font-medium text-slate-900">No {label} Found</h3>
      <p className="text-slate-500 max-w-sm mt-2">
        The AI couldn't extract this specific section from the filing. This usually means the company didn't report it in standard format.
      </p>
    </div>
  )
}
