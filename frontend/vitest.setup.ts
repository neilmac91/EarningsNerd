import '@testing-library/jest-dom/vitest'

// Enable feature flags for tests to ensure tabbed UI is available
// Tests were written expecting the tabbed interface
process.env.NEXT_PUBLIC_ENABLE_SECTION_TABS = 'true'
process.env.NEXT_PUBLIC_ENABLE_FINANCIAL_CHARTS = 'true'

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (!('ResizeObserver' in globalThis)) {
  // @ts-ignore - assigning to global scope for test environment
  globalThis.ResizeObserver = ResizeObserverMock
}

if (typeof window !== 'undefined' && !window.matchMedia) {
  // @ts-ignore - provide minimal mock for tests
  window.matchMedia = () => ({
    matches: false,
    media: '',
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })
}



