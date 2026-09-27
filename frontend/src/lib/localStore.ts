"use client";

/**
 * A typed `localStorage` store wired through `useSyncExternalStore`.
 *
 * ## Why not `useState` + `useEffect`
 *
 * The obvious implementation of a persisted cart is:
 *
 * ```ts
 * const [lines, setLines] = useState([]);
 * useEffect(() => setLines(readFromStorage()), []);
 * ```
 *
 * That is an effect calling setState synchronously, which React flags for good
 * reason: it guarantees a second render pass on every mount, and it renders the
 * server HTML before the real state is known. `useSyncExternalStore` is the API
 * built for exactly this situation - `localStorage` *is* an external mutable
 * store - and it gives correct hydration for free: React uses
 * `getServerSnapshot` for the hydration render and `getSnapshot` immediately
 * after, with no mismatched markup and no extra pass.
 *
 * ## Snapshot identity
 *
 * `useSyncExternalStore` compares snapshots with `Object.is` and re-renders on
 * any change, so a getter that returned a fresh array on every call would spin
 * forever. `getSnapshot` therefore caches the parsed value and only re-parses
 * when the underlying raw string actually changes.
 */

import { useSyncExternalStore } from "react";

export interface LocalStore<T> {
  subscribe: (listener: () => void) => () => void;
  getSnapshot: () => T;
  getServerSnapshot: () => T;
  write: (value: T) => void;
  read: () => T;
}

export function createLocalStore<T>({
  key,
  parse,
  empty,
  eventName,
}: {
  key: string;
  parse: (raw: unknown) => T;
  /** Must be a stable reference; it is returned verbatim on the server. */
  empty: T;
  /** Custom event so same-tab writes are observed, not just cross-tab ones. */
  eventName: string;
}): LocalStore<T> {
  const listeners = new Set<() => void>();

  let cachedRaw: string | null | undefined;
  let cachedValue: T = empty;

  function read(): T {
    if (typeof window === "undefined") return empty;
    const raw = window.localStorage.getItem(key);
    if (raw === cachedRaw) return cachedValue;

    cachedRaw = raw;
    if (raw === null) {
      cachedValue = empty;
    } else {
      try {
        cachedValue = parse(JSON.parse(raw));
      } catch {
        // Corrupt or tampered storage must never break the storefront. Treat it
        // as empty rather than throwing during render.
        cachedValue = empty;
      }
    }
    return cachedValue;
  }

  function notify(): void {
    for (const listener of listeners) listener();
  }

  function write(value: T): void {
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // Private mode, disabled storage, or a full quota. The in-memory snapshot
      // still updates because we invalidate the cache below and notify.
    }
    // Invalidate unconditionally: if the write threw, the next read must
    // re-derive from whatever storage actually holds.
    cachedRaw = undefined;
    notify();
  }

  function subscribe(listener: () => void): () => void {
    listeners.add(listener);

    const onStorage = (event: StorageEvent) => {
      if (event.key === key) listener();
    };
    const onInternal = () => listener();

    window.addEventListener("storage", onStorage);
    window.addEventListener(eventName, onInternal);

    return () => {
      listeners.delete(listener);
      window.removeEventListener("storage", onStorage);
      window.removeEventListener(eventName, onInternal);
    };
  }

  // Not a hook: `empty` is a caller-supplied constant, so returning it directly
  // is already referentially stable across calls and renders.
  const getServerSnapshot = () => empty;

  return { subscribe, getSnapshot: read, getServerSnapshot, write, read };
}

/** Subscribe to a store. */
export function useLocalStore<T>(store: LocalStore<T>): T {
  return useSyncExternalStore(store.subscribe, store.getSnapshot, store.getServerSnapshot);
}
