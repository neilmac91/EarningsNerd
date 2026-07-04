'use client'

import React, { Component, ErrorInfo, ReactNode } from 'react'
import { ArrowsClockwiseIcon, HouseIcon, WarningIcon } from '@/lib/icons'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error?: Error
  errorInfo?: ErrorInfo
}

/**
 * Global error boundary to catch unhandled errors in the React tree.
 * Provides a user-friendly fallback UI and error reporting.
 */
export class GlobalErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
  }

  public static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Log error to console in development
    console.error('Uncaught error:', error)
    console.error('Component stack:', errorInfo.componentStack)

    // Store error info for display
    this.setState({ errorInfo })

    // Report to Sentry if available (guard window first — this can run during SSR)
    if (typeof window !== 'undefined') {
      const sentry = (window as unknown as {
        Sentry?: { captureException?: (error: unknown) => void }
      }).Sentry
      sentry?.captureException?.(error)
    }
  }

  private handleRefresh = () => {
    window.location.reload()
  }

  private handleGoHome = () => {
    window.location.href = '/'
  }

  private handleRetry = () => {
    this.setState({ hasError: false, error: undefined, errorInfo: undefined })
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-background-light dark:bg-background-dark flex items-center justify-center p-4">
          <div className="max-w-md w-full bg-panel-light dark:bg-panel-dark rounded-xl shadow-e2 dark:shadow-none p-8 text-center">
            <div className="mx-auto w-16 h-16 bg-error-light/10 dark:bg-error-dark/10 rounded-full flex items-center justify-center mb-6">
              <WarningIcon className="w-8 h-8 text-error-light dark:text-error-dark" />
            </div>

            <h1 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark mb-2">
              Something went wrong
            </h1>

            <p className="text-text-secondary-light dark:text-text-secondary-dark mb-6">
              We encountered an unexpected error. Our team has been notified and is working to fix it.
            </p>

            {process.env.NODE_ENV === 'development' && this.state.error && (
              <div className="mb-6 p-4 bg-background-light dark:bg-background-dark rounded-lg text-left overflow-auto max-h-40">
                <p className="text-xs font-mono text-error-light dark:text-error-dark break-all">
                  {this.state.error.message}
                </p>
              </div>
            )}

            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <button
                onClick={this.handleRetry}
                className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-brand text-white hover:bg-brand-strong active:bg-brand-emphasis dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark font-medium rounded-lg transition-colors"
              >
                <ArrowsClockwiseIcon className="w-4 h-4" />
                Try Again
              </button>

              <button
                onClick={this.handleGoHome}
                className="inline-flex items-center justify-center gap-2 px-4 py-2 border border-border-light dark:border-border-dark text-text-secondary-light dark:text-text-secondary-dark hover:bg-background-light dark:hover:bg-background-dark font-medium rounded-lg transition-colors"
              >
                <HouseIcon className="w-4 h-4" />
                Go Home
              </button>
            </div>

            <p className="mt-6 text-xs text-text-secondary-light dark:text-text-secondary-dark">
              If this problem persists, please contact{' '}
              <a href="mailto:support@earningsnerd.io" className="text-brand-strong dark:text-brand-strong-dark hover:underline">
                support@earningsnerd.io
              </a>
            </p>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

export default GlobalErrorBoundary
