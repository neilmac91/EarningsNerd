'use client'

import React, { Component, ErrorInfo, ReactNode } from 'react'
import { ArrowsClockwiseIcon, HouseIcon, WarningIcon } from '@/lib/icons'
import { Button, GuidanceCard } from '@/components/ui'

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
          <div className="w-full max-w-md space-y-4">
            <GuidanceCard
              variant="error"
              icon={<WarningIcon className="h-5 w-5" />}
              title="Something went wrong"
              description="We encountered an unexpected error. Our team has been notified and is working to fix it."
              action={
                <>
                  <Button onClick={this.handleRetry} leftIcon={<ArrowsClockwiseIcon className="h-4 w-4" />}>
                    Try again
                  </Button>
                  <Button variant="secondary" onClick={this.handleGoHome} leftIcon={<HouseIcon className="h-4 w-4" />}>
                    Go home
                  </Button>
                </>
              }
            />

            {process.env.NODE_ENV === 'development' && this.state.error && (
              <div className="max-h-40 overflow-auto rounded-lg border border-border-light bg-background-light p-4 text-left dark:border-border-dark dark:bg-white/5">
                <p className="break-all font-mono text-xs text-error-light dark:text-error-dark">
                  {this.state.error.message}
                </p>
              </div>
            )}

            <p className="text-center text-xs text-text-secondary-light dark:text-text-secondary-dark">
              If this problem persists, please contact{' '}
              <a href="mailto:support@earningsnerd.io" className="text-brand-strong hover:underline dark:text-brand-strong-dark">
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
