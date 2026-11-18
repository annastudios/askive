import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// Unmount whatever a test rendered, and reset mocks and storage between tests.
afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  localStorage.clear()
})

// jsdom doesn't implement scrolling; the app scrolls new messages and
// highlighted passages into view.
Element.prototype.scrollIntoView = () => {}
