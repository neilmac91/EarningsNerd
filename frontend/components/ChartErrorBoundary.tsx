'use client'

import React, { Component, ErrorInfo, ReactNode } from 'react'

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
      
      return (
        <div className="bg-panel-light dark:bg-panel-dark border border-border-light dark:border-border-dark rounded-lg p-6 text-center">
          <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
            Unable to display charts. Financial data is still available in the table below.
          </p>
        </div>
      )
    }

    return this.props.children
  }
}

