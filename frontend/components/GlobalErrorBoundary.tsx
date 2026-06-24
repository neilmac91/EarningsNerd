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
        <div className="min-h-screen bg-slate-50 dark:bg-slate-900 flex items-center justify-center p-4">
          <div className="max-w-md w-full bg-white dark:bg-slate-800 rounded-xl shadow-lg p-8 text-center">
            <div className="mx-auto w-16 h-16 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center mb-6">
              <WarningIcon className="w-8 h-8 text-red-600 dark:text-red-400" />
            </div>

            <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">
              Something went wrong
            </h1>

            <p className="text-slate-600 dark:text-slate-400 mb-6">
              We encountered an unexpected error. Our team has been notified and is working to fix it.
            </p>

            {process.env.NODE_ENV === 'development' && this.state.error && (
              <div className="mb-6 p-4 bg-slate-100 dark:bg-slate-700 rounded-lg text-left overflow-auto max-h-40">
                <p className="text-xs font-mono text-red-600 dark:text-red-400 break-all">
                  {this.state.error.message}
                </p>
              </div>
            )}

            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <button
                onClick={this.handleRetry}
                className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-brand-strong text-white hover:bg-brand-light dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark focus-visible:outline-brand-light font-medium rounded-lg transition-colors"
              >
                <ArrowsClockwiseIcon className="w-4 h-4" />
                Try Again
              </button>

              <button
                onClick={this.handleGoHome}
                className="inline-flex items-center justify-center gap-2 px-4 py-2 border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 font-medium rounded-lg transition-colors"
              >
                <HouseIcon className="w-4 h-4" />
                Go Home
              </button>
            </div>

            <p className="mt-6 text-xs text-slate-500 dark:text-slate-400">
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
