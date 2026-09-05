import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { GlobalErrorBoundary } from '@/components/GlobalErrorBoundary'

// Happy-path call tracking only (the mock never throws), so vi.fn() is safe here — see
// lessons/test-vitest4-mock-error-tracking.md for why a REJECTING mock must not use vi.fn().
const mockCaptureException = vi.fn()
vi.mock('@sentry/nextjs', () => ({
  captureException: (...args: unknown[]) => mockCaptureException(...args),
}))

function Thrower({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) throw new Error('boom from child')
  return <p>recovered content</p>
}

describe('GlobalErrorBoundary', () => {
  let consoleError: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    mockCaptureException.mockReset()
    // React logs the caught error + component stack; keep the test output quiet.
    consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    consoleError.mockRestore()
  })

  it('reports a caught render error to Sentry with the component stack', () => {
    render(
      <GlobalErrorBoundary>
        <Thrower shouldThrow />
      </GlobalErrorBoundary>,
    )

    expect(mockCaptureException).toHaveBeenCalledTimes(1)
    const [error, hint] = mockCaptureException.mock.calls[0]
    expect(error).toBeInstanceOf(Error)
    expect((error as Error).message).toBe('boom from child')
    expect(hint).toMatchObject({ extra: { componentStack: expect.stringContaining('Thrower') } })
  })

  it('renders the fallback UI and recovers via "Try again"', () => {
    let shouldThrow = true
    function Wrapper() {
      return (
        <GlobalErrorBoundary>
          <Thrower shouldThrow={shouldThrow} />
        </GlobalErrorBoundary>
      )
    }
    const { rerender } = render(<Wrapper />)

    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
    expect(screen.getByText(/reported automatically/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /support@earningsnerd\.io/ })).toHaveAttribute(
      'href',
      'mailto:support@earningsnerd.io',
    )

    // The child stops throwing; "Try again" resets the boundary and the tree re-renders cleanly.
    shouldThrow = false
    rerender(<Wrapper />)
    fireEvent.click(screen.getByRole('button', { name: /try again/i }))
    expect(screen.getByText('recovered content')).toBeInTheDocument()
    expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument()
  })

  it('renders children untouched when nothing throws', () => {
    render(
      <GlobalErrorBoundary>
        <Thrower shouldThrow={false} />
      </GlobalErrorBoundary>,
    )
    expect(screen.getByText('recovered content')).toBeInTheDocument()
    expect(mockCaptureException).not.toHaveBeenCalled()
  })
})
