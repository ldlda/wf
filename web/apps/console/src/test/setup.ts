import "@testing-library/jest-dom/vitest";

class TestResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// React Flow measures nodes through browser layout APIs. JSDOM does not provide
// these APIs, so tests install stable no-op versions and assert our projected
// graph state rather than actual browser layout.
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = TestResizeObserver as unknown as typeof ResizeObserver;
}

if (!globalThis.DOMRect) {
  globalThis.DOMRect = {
    fromRect: () => ({
      x: 0,
      y: 0,
      width: 0,
      height: 0,
      top: 0,
      right: 0,
      bottom: 0,
      left: 0,
      toJSON() {},
    }),
  } as unknown as typeof DOMRect;
}
