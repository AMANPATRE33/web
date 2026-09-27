import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

/**
 * Test environment setup.
 *
 * `localStorage` is cleared between tests. That matters for this suite: the cart
 * and wishlist are real `localStorage` stores via `useSyncExternalStore`, and a
 * line leaking from one test into the next would produce a cart with a
 * completely unrelated product in it.
 */
beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.useRealTimers();
});

// jsdom does not implement matchMedia, and `prefers-reduced-motion` is read by
// framer-motion. Without this, any component using `useReducedMotion` throws.
if (!window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}

// Radix Dialog uses these during layout measurement.
if (!window.ResizeObserver) {
  window.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}

if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
