'use client'

import { useState, useEffect } from 'react'
import { FileText, Sparkles, BarChart3, TrendingUp, CheckCircle2 } from 'lucide-react'

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
    icon: FileText,
    duration: 2000
  },
  { 
    id: 'parsing', 
    label: 'Parsing document structure', 
    description: 'Extracting tables, financial data, and sections',
    icon: BarChart3,
    duration: 3000
  },
  { 
    id: 'analyzing', 
    label: 'Analyzing content', 
    description: 'Processing with AI to identify key metrics and trends',
    icon: Sparkles,
    duration: 4000
  },
  { 
    id: 'summarizing', 
    label: 'Generating insights', 
    description: 'Creating executive summary and financial highlights',
    icon: TrendingUp,
    duration: 5000
  },
]

export default function SummaryProgress({ isGenerating = true, backendStage, elapsedSeconds }: SummaryProgressProps) {
  const [currentStage, setCurrentStage] = useState(0)
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    if (!isGenerating) {
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
    <div className="bg-white rounded-lg shadow-md p-8">
      <div className="max-w-2xl mx-auto">
        {/* Progress Bar */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-700">
              {stages[currentStage]?.label || 'Preparing...'}
            </span>
            <span className="text-sm text-gray-500">{Math.round(progress)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2.5">
            <div
              className="bg-gradient-to-r from-primary-500 to-primary-600 h-2.5 rounded-full transition-all duration-300 ease-out"
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
                className={`flex items-start space-x-4 p-4 rounded-lg transition-all duration-300 ${
                  isActive
                    ? 'bg-primary-50 border-2 border-primary-200'
                    : isComplete
                    ? 'bg-green-50 border-2 border-green-200'
                    : 'bg-gray-50 border-2 border-gray-200'
                }`}
              >
                <div className={`flex-shrink-0 mt-0.5 ${
                  isComplete
                    ? 'text-green-600'
                    : isActive
                    ? 'text-primary-600'
                    : 'text-gray-400'
                }`}>
                  {isComplete ? (
                    <CheckCircle2 className="h-6 w-6" />
                  ) : (
                    <Icon className={`h-6 w-6 ${isActive ? 'animate-pulse' : ''}`} />
                  )}
                </div>
                <div className="flex-1">
                  <div className={`font-medium ${
                    isActive
                      ? 'text-primary-900'
                      : isComplete
                      ? 'text-green-900'
                      : 'text-gray-500'
                  }`}>
                    {stage.label}
                  </div>
                  <div className={`text-sm mt-1 ${
                    isActive
                      ? 'text-primary-700'
                      : isComplete
                      ? 'text-green-700'
                      : 'text-gray-400'
                  }`}>
                    {stage.description}
                  </div>
                  {isActive && (
                    <div className="mt-2 flex space-x-1">
                      <div className="w-2 h-2 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <div className="w-2 h-2 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <div className="w-2 h-2 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>

        {/* Estimated Time */}
        <div className="mt-6 text-center">
          <p className="text-sm text-gray-600 font-medium">
            Generating your summary...
          </p>
          <p className="text-xs text-gray-500 mt-1">
            This typically takes 30-60 seconds for large filings. Please don&apos;t close this page.
          </p>
          <div className="mt-3 flex items-center justify-center space-x-2 text-xs text-gray-400">
            <div className="w-2 h-2 bg-primary-400 rounded-full animate-pulse" />
            <span>Processing securely</span>
          </div>
        </div>
      </div>
    </div>
  )
}

