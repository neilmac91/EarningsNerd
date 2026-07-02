'use client'

import { useState, useEffect } from 'react'
import { ChartBarIcon, CheckCircleIcon, FileTextIcon, SparkleIcon, TrendUpIcon } from '@/lib/icons'

interface SummaryProgressProps {
  isGenerating?: boolean
  backendStage?: 'pending' | 'fetching' | 'parsing' | 'analyzing' | 'summarizing' | 'completed' | 'error'
  elapsedSeconds?: number
}

const stages = [
  { 
    id: 'fetching', 
    label: 'Fetching filing document', 
    description: 'Downloading the SEC filing from EDGAR',
    icon: FileTextIcon,
    duration: 2000
  },
  { 
    id: 'parsing', 
    label: 'Parsing document structure', 
    description: 'Extracting tables, financial data, and sections',
    icon: ChartBarIcon,
    duration: 3000
  },
  { 
    id: 'analyzing', 
    label: 'Analyzing content', 
    description: 'Processing with AI to identify key metrics and trends',
    icon: SparkleIcon,
    duration: 4000
  },
  { 
    id: 'summarizing', 
    label: 'Generating insights', 
    description: 'Creating executive summary and financial highlights',
    icon: TrendUpIcon,
    duration: 5000
  },
]

export default function SummaryProgress({ isGenerating = true, backendStage, elapsedSeconds }: SummaryProgressProps) {
  const [currentStage, setCurrentStage] = useState(0)
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    if (!isGenerating) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- resets timer-driven progress state when generation stops; effect also drives interval/timeout updates below
      setCurrentStage(0)
      setProgress(0)
      return
    }

    // If we have backend stage, use it to drive the UI
    if (backendStage && backendStage !== 'pending' && backendStage !== 'completed' && backendStage !== 'error') {
      const backendStageIndex = stages.findIndex(s => s.id === backendStage)
      if (backendStageIndex >= 0) {
        setCurrentStage(backendStageIndex)
        // Calculate progress based on stage and elapsed time
        // Each stage gets roughly equal weight (25% each)
        const baseProgress = (backendStageIndex / stages.length) * 100
        // Add some progress within the current stage (up to 20% of stage progress)
        const stageProgress = Math.min(20, (elapsedSeconds || 0) / 5) // Rough estimate: 5s per stage
        setProgress(Math.min(95, baseProgress + stageProgress))
        return
      }
    }

    // Fallback to time-based progress if no backend stage
    const startTime = Date.now()
    const totalDuration = stages.reduce((sum, s) => sum + s.duration, 0)

    const updateProgress = () => {
      const elapsed = Date.now() - startTime
      
      // Calculate which stage we should be in based on elapsed time
      let cumulativeTime = 0
      let newStageIndex = 0
      for (let i = 0; i < stages.length; i++) {
        cumulativeTime += stages[i].duration
        if (elapsed >= cumulativeTime) {
          newStageIndex = i + 1
        } else {
          break
        }
      }
      
      // Don't go beyond the last stage
      newStageIndex = Math.min(newStageIndex, stages.length - 1)
      setCurrentStage(newStageIndex)
      
      // Calculate overall progress (cap at 95% to show we're still working, but allow it to reach 100% if it takes longer)
      // For longer operations, allow progress to continue past the initial estimate
      const estimatedTotal = totalDuration * 1.5 // Extend estimate by 50%
      const overallProgress = Math.min(95, (elapsed / estimatedTotal) * 100)
      setProgress(overallProgress)
    }

    // Update every 200ms for smooth animation
    const interval = setInterval(updateProgress, 200)
    updateProgress() // Initial call
    
    return () => clearInterval(interval)
  }, [isGenerating, backendStage, elapsedSeconds])

  return (
    <div className="bg-panel-light dark:bg-panel-dark border border-border-light dark:border-white/10 rounded-lg shadow-e2 dark:shadow-none p-8">
      <div className="max-w-2xl mx-auto">
        {/* Progress Bar */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-text-primary-light dark:text-text-primary-dark">
              {stages[currentStage]?.label || 'Preparing...'}
            </span>
            <span className="text-sm text-text-secondary-light dark:text-text-secondary-dark">{Math.round(progress)}%</span>
          </div>
          <div className="w-full bg-border-light dark:bg-white/10 rounded-full h-2.5">
            <div
              className="bg-gradient-to-r from-brand-strong to-brand-light dark:from-brand-dark dark:to-brand-strong-dark h-2.5 rounded-full transition-all duration-base ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* Stage List */}
        <div className="space-y-4">
          {stages.map((stage, index) => {
            const Icon = stage.icon
            const isActive = index === currentStage
            const isComplete = index < currentStage
            
            return (
              <div
                key={stage.id}
                className={`flex items-start space-x-4 p-4 rounded-lg transition-all duration-base ${
                  isActive
                    ? 'bg-brand-strong/10 dark:bg-brand-dark/15 border-2 border-brand-light/30 dark:border-brand-dark/30'
                    : isComplete
                    ? 'bg-brand-weak dark:bg-brand-dark/10 border-2 border-brand-light/30 dark:border-brand-dark/30'
                    : 'bg-background-light dark:bg-white/5 border-2 border-border-light dark:border-white/10'
                }`}
              >
                <div className={`flex-shrink-0 mt-0.5 ${
                  isComplete
                    ? 'text-brand-strong dark:text-brand-strong-dark'
                    : isActive
                    ? 'text-brand-strong dark:text-brand-strong-dark'
                    : 'text-text-tertiary-light dark:text-text-secondary-dark'
                }`}>
                  {isComplete ? (
                    <CheckCircleIcon className="h-6 w-6" />
                  ) : (
                    <Icon className={`h-6 w-6 ${isActive ? 'animate-pulse' : ''}`} />
                  )}
                </div>
                <div className="flex-1">
                  <div className={`font-medium ${
                    isActive
                      ? 'text-brand-strong dark:text-brand-strong-dark'
                      : isComplete
                      ? 'text-brand-strong dark:text-brand-strong-dark'
                      : 'text-text-secondary-light dark:text-text-secondary-dark'
                  }`}>
                    {stage.label}
                  </div>
                  <div className={`text-sm mt-1 ${
                    isActive
                      ? 'text-brand-strong dark:text-brand-strong-dark'
                      : isComplete
                      ? 'text-brand-strong dark:text-brand-strong-dark'
                      : 'text-text-tertiary-light dark:text-text-secondary-dark'
                  }`}>
                    {stage.description}
                  </div>
                  {isActive && (
                    <div className="mt-2 flex space-x-1">
                      <div className="w-2 h-2 bg-brand-strong dark:bg-brand-strong-dark rounded-full animate-bounce" />
                      <div className="w-2 h-2 bg-brand-strong dark:bg-brand-strong-dark rounded-full animate-bounce" style={{ animationDelay: 'calc(var(--duration-fast) * 1)' }} />
                      <div className="w-2 h-2 bg-brand-strong dark:bg-brand-strong-dark rounded-full animate-bounce" style={{ animationDelay: 'calc(var(--duration-fast) * 2)' }} />
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>

        {/* Estimated Time */}
        <div className="mt-6 text-center">
          <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark font-medium">
            Generating your summary...
          </p>
          <p className="text-xs text-text-tertiary-light dark:text-text-secondary-dark mt-1">
            This typically takes 30-60 seconds for large filings. Please don&apos;t close this page.
          </p>
          <div className="mt-3 flex items-center justify-center space-x-2 text-xs text-text-tertiary-light dark:text-text-secondary-dark">
            <div className="w-2 h-2 bg-brand-strong dark:bg-brand-strong-dark rounded-full animate-pulse" />
            <span>Processing securely</span>
          </div>
        </div>
      </div>
    </div>
  )
}

