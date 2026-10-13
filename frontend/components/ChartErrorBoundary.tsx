'use client'

import React, { Component, ErrorInfo, ReactNode } from 'react'
import { Card } from '@/components/ui'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error?: Error
}

export class ChartErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
  }

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Chart rendering error:', error, errorInfo)
  }

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }
      
      // Says only what failed: the boundary wraps a chart on the filing page and on Multi-Period
      // Analysis, and neither promises a table beneath it.
      return (
        <Card className="p-6 text-center">
          <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
            This chart could not be drawn.
          </p>
        </Card>
      )
    }

    return this.props.children
  }
}

