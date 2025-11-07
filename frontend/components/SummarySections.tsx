'use client'

import { useMemo, useState } from 'react'
import { ChevronDown, ChevronUp, FileText, TrendingUp, AlertTriangle, Building2, BarChart3 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { RiskFactor } from '../types/summary'

interface SummarySectionsProps {
  summary: {
    business_overview?: string
    raw_summary?: any
  }
  metrics?: any[]
}

export default function SummarySections({ summary, metrics }: SummarySectionsProps) {
  const [activeTab, setActiveTab] = useState<string>('overview')
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['overview']))

  const raw_summary = summary.raw_summary || {}
  const sections = raw_summary.sections || {}

  const toggleSection = (section: string) => {
    const newExpanded = new Set(expandedSections)
    if (newExpanded.has(section)) {
      newExpanded.delete(section)
    } else {
      newExpanded.add(section)
    }
    setExpandedSections(newExpanded)
  }

  const evidenceKeys = ['excerpt', 'text', 'quote', 'source', 'reference', 'tag', 'xbrl_tag', 'xbrlTag', 'citation']

  const renderMarkdownValue = (value: any): string => {
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

  const formatEvidence = (value: any): string => {
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

  const normalizeRisk = (risk: any): RiskFactor | null => {
    if (!risk || typeof risk !== 'object') {
      return null
    }

    const title = typeof risk.title === 'string' ? risk.title.trim() : null
    const description = typeof risk.description === 'string' ? risk.description.trim() : null
    const summaryCandidate =
      (typeof risk.summary === 'string' && risk.summary.trim()) ||
      (description && description) ||
      (title && title) ||
      ''

    if (!summaryCandidate) {
      return null
    }

    const supportingEvidence = formatEvidence(
      (risk.supporting_evidence ?? risk.supportingEvidence ?? risk.evidence ?? risk.source) as unknown
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
      .map((risk) => normalizeRisk(risk))
      .filter((risk): risk is RiskFactor => Boolean(risk && risk.supporting_evidence))
  }, [sections.risk_factors])

  const hasTrendContent = Boolean(sections.three_year_trend || sections.segment_performance)

  const tabs = [
    { id: 'overview', label: 'Executive Summary', icon: FileText },
    { id: 'financials', label: 'Financials', icon: BarChart3 },
    { id: 'risks', label: 'Risks', icon: AlertTriangle },
    { id: 'management', label: 'Management', icon: Building2 },
  ] as Array<{ id: string; label: string; icon: typeof FileText }>

  if (hasTrendContent) {
    tabs.push({ id: 'trends', label: 'Trends', icon: TrendingUp })
  }

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        if (!sections.executive_snapshot && !summary.business_overview) {
          return null
        }
        const overviewMarkdown = sections.executive_snapshot
          ? renderMarkdownValue(sections.executive_snapshot)
          : (summary.business_overview || '')
        return (
          <div className="prose max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {overviewMarkdown}
            </ReactMarkdown>
          </div>
        )

      case 'financials':
        if (
          !sections.financial_highlights?.notes &&
          (!metrics || metrics.length === 0)
        ) {
          return null
        }
        return (
          <div className="space-y-4">
            {sections.financial_highlights?.notes && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p className="text-sm text-blue-800">{sections.financial_highlights.notes}</p>
              </div>
            )}
            {metrics && metrics.length > 0 && (
              <div className="text-sm text-gray-600">
                <p>Financial metrics are displayed in the table above. Key highlights include:</p>
                <ul className="list-disc list-inside mt-2 space-y-1">
                  {metrics.slice(0, 5).map((m: any, i: number) => (
                    <li key={i}>{m.metric}: {m.current_period} vs {m.prior_period}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )

      case 'risks':
        if (normalizedRisks.length === 0) {
          return null
        }
        return (
          <div className="space-y-3">
            {normalizedRisks.map((risk, index) => (
              <div key={`${risk.summary}-${index}`} className="border border-red-100 bg-red-50 rounded-lg p-4 space-y-2">
                {(risk.title || risk.description) && (
                  <>
                    {risk.title && <h4 className="font-semibold text-red-900">{risk.title}</h4>}
                    {risk.description && (
                      <p className="text-sm text-red-800">{risk.description}</p>
                    )}
                  </>
                )}
                {!risk.title && !risk.description && (
                  <p className="text-sm text-red-900">{risk.summary}</p>
                )}
                <div className="text-xs text-red-700 bg-red-100/60 border border-red-200 rounded-md px-3 py-2">
                  <span className="font-semibold">Supporting evidence:</span>{' '}
                  <span>{risk.supporting_evidence}</span>
                </div>
              </div>
            ))}
          </div>
        )

      case 'management':
        if (!sections.management_discussion_insights) {
          return null
        }
        return (
          <div className="prose max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {renderMarkdownValue(sections.management_discussion_insights)}
            </ReactMarkdown>
          </div>
        )

      case 'trends':
        if (!hasTrendContent) {
          return null
        }
        return (
          <div className="space-y-4">
            {sections.three_year_trend && (
              <div className="prose max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {renderMarkdownValue(sections.three_year_trend)}
                </ReactMarkdown>
              </div>
            )}
            {sections.segment_performance && (
              <div className="mt-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-3">Segment Performance</h3>
                <div className="prose max-w-none">
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
    <div className="bg-white rounded-lg shadow-md border border-gray-200">
      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-1 px-6" aria-label="Tabs">
          {tabs.map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`
                  flex items-center space-x-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors
                  ${isActive
                    ? 'border-primary-500 text-primary-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }
                `}
              >
                <Icon className="h-4 w-4" />
                <span>{tab.label}</span>
              </button>
            )
          })}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="p-6">
        {renderTabContent()}
      </div>

      {/* Additional Sections (Collapsible) */}
      {(sections.guidance_outlook || sections.liquidity_capital_structure || sections.notable_footnotes) && (
        <div className="border-t border-gray-200 p-6 space-y-4">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Additional Information</h3>
          
          {sections.guidance_outlook && (
            <div className="border border-gray-200 rounded-lg">
              <button
                onClick={() => toggleSection('guidance')}
                className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50 transition-colors"
              >
                <span className="font-medium text-gray-900">Forward Outlook & Guidance</span>
                {expandedSections.has('guidance') ? (
                  <ChevronUp className="h-5 w-5 text-gray-500" />
                ) : (
                  <ChevronDown className="h-5 w-5 text-gray-500" />
                )}
              </button>
              {expandedSections.has('guidance') && (
                <div className="px-4 pb-4">
                  <div className="prose max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {renderMarkdownValue(sections.guidance_outlook)}
                    </ReactMarkdown>
                  </div>
                </div>
              )}
            </div>
          )}

          {sections.liquidity_capital_structure && (
            <div className="border border-gray-200 rounded-lg">
              <button
                onClick={() => toggleSection('liquidity')}
                className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50 transition-colors"
              >
                <span className="font-medium text-gray-900">Liquidity & Capital Structure</span>
                {expandedSections.has('liquidity') ? (
                  <ChevronUp className="h-5 w-5 text-gray-500" />
                ) : (
                  <ChevronDown className="h-5 w-5 text-gray-500" />
                )}
              </button>
              {expandedSections.has('liquidity') && (
                <div className="px-4 pb-4">
                  <div className="prose max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {renderMarkdownValue(sections.liquidity_capital_structure)}
                    </ReactMarkdown>
                  </div>
                </div>
              )}
            </div>
          )}

          {sections.notable_footnotes && (
            <div className="border border-gray-200 rounded-lg">
              <button
                onClick={() => toggleSection('footnotes')}
                className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50 transition-colors"
              >
                <span className="font-medium text-gray-900">Notable Footnotes</span>
                {expandedSections.has('footnotes') ? (
                  <ChevronUp className="h-5 w-5 text-gray-500" />
                ) : (
                  <ChevronDown className="h-5 w-5 text-gray-500" />
                )}
              </button>
              {expandedSections.has('footnotes') && (
                <div className="px-4 pb-4">
                  <div className="prose max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {renderMarkdownValue(sections.notable_footnotes)}
                    </ReactMarkdown>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

