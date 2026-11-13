// Filesystem and AST policy tests use Node and do not need browser matchers.
if (typeof window !== 'undefined') {
  await import('@testing-library/jest-dom/vitest')
}

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

export {}
