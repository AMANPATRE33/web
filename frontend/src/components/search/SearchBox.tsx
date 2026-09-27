"use client";

/**
 * Search box with debounced suggestions.
 *
 * Suggestions are fetched from this app's own `/api/search-suggestions` route
 * rather than from the FastAPI backend directly, because a client component
 * calling a different origin needs CORS to be right and fails silently when it
 * is not. See the route handler for the full reasoning.
 *
 * The form still navigates to `/search?q=...` on submit, so search works with
 * JavaScript disabled and results are shareable URLs.
 */

import { Search, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import type { SearchSuggestion } from "@/lib/api/types";
import { cn } from "@/lib/cn";

const MIN_QUERY = 2;
const DEBOUNCE_MS = 220;
const EMPTY: SearchSuggestion[] = [];

export function SearchBox({
  initialQuery = "",
  autoFocus = false,
  size = "lg",
  className,
}: {
  initialQuery?: string;
  autoFocus?: boolean;
  size?: "md" | "lg";
  className?: string;
}) {
  const router = useRouter();
  const [query, setQuery] = useState(initialQuery);
  const [results, setResults] = useState<{ for: string; items: SearchSuggestion[] } | null>(
    null,
  );
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const blurTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const trimmed = query.trim();
  // Derived, not stored: a short query simply has no suggestions to show, so
  // there is nothing to clear in an effect.
  const eligible = trimmed.length >= MIN_QUERY;
  const suggestions = results !== null && results.for === trimmed ? results.items : EMPTY;

  useEffect(() => {
    if (trimmed.length < MIN_QUERY) return;

    // Every state transition happens inside the timer, i.e. asynchronously.
    // Setting it synchronously in the effect body would be a synchronous
    // setState in an effect, which cascades a render on every keystroke.
    const timer = setTimeout(async () => {
      setBusy(true);
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const response = await fetch(
          `/api/search-suggestions?q=${encodeURIComponent(trimmed)}`,
          { signal: controller.signal },
        );
        if (!response.ok) throw new Error(`suggestions failed: ${response.status}`);
        const payload = (await response.json()) as { suggestions: SearchSuggestion[] };
        if (!controller.signal.aborted) setResults({ for: trimmed, items: payload.suggestions });
      } catch {
        // A failed suggestion lookup must not break typing or submission.
        if (!controller.signal.aborted) setResults({ for: trimmed, items: EMPTY });
      } finally {
        if (!controller.signal.aborted) setBusy(false);
      }
    }, DEBOUNCE_MS);

    return () => {
      clearTimeout(timer);
      abortRef.current?.abort();
    };
  }, [trimmed]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      if (blurTimer.current) clearTimeout(blurTimer.current);
    };
  }, []);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = query.trim();
    setOpen(false);
    router.push(trimmed ? `/search?q=${encodeURIComponent(trimmed)}` : "/search");
  }

  return (
    <form
      role="search"
      onSubmit={submit}
      className={cn("relative", className)}
      onFocus={() => setOpen(true)}
      onBlur={() => {
        // Deferred so a click on a suggestion still registers.
        blurTimer.current = setTimeout(() => setOpen(false), 140);
      }}
    >
      <label htmlFor="site-search" className="sr-only">
        Search products, categories and SKUs
      </label>
      <div
        className={cn(
          "flex items-center border border-ink-300 bg-white focus-within:border-ink-900",
          size === "lg" ? "h-12" : "h-10",
        )}
      >
        <Search aria-hidden="true" className="ml-3 size-4 shrink-0 text-ink-400" />
        <input
          id="site-search"
          type="search"
          value={query}
          autoFocus={autoFocus}
          autoComplete="off"
          placeholder="Search posters, boards, SKUs..."
          aria-expanded={open && suggestions.length > 0}
          aria-controls="search-suggestions"
          aria-autocomplete="list"
          role="combobox"
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          className={cn(
            "min-w-0 flex-1 bg-transparent px-2.5 text-sm text-ink-900 outline-none placeholder:text-ink-400",
            "[&::-webkit-search-cancel-button]:appearance-none",
          )}
        />
        {query ? (
          <button
            type="button"
            onClick={() => {
              setQuery("");
              setResults(null);
            }}
            aria-label="Clear search"
            className="shrink-0 px-2.5 text-ink-400 hover:text-ink-900"
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        ) : null}
      </div>

      {open && eligible && (suggestions.length > 0 || busy) ? (
        <ul
          id="search-suggestions"
          role="listbox"
          className="absolute inset-x-0 top-full z-40 mt-1 max-h-80 overflow-y-auto border border-ink-200 bg-white shadow-lg"
        >
          {busy && suggestions.length === 0 ? (
            <li className="px-3 py-2.5 text-[13px] text-ink-500">Searching...</li>
          ) : null}
          {suggestions.map((suggestion) => (
            <li key={`${suggestion.type}-${suggestion.text}`}>
              <Link
                href={
                  suggestion.type === "product" && suggestion.slug
                    ? `/products/${suggestion.slug}`
                    : suggestion.type === "category" && suggestion.slug
                      ? `/category/${suggestion.slug}`
                      : `/search?q=${encodeURIComponent(suggestion.text)}`
                }
                role="option"
                aria-selected="false"
                className="flex items-center justify-between gap-3 px-3 py-2.5 text-[13px] text-ink-800 hover:bg-ink-50"
              >
                <span className="min-w-0 truncate">{suggestion.text}</span>
                <span className="shrink-0 text-[11px] uppercase tracking-wider text-ink-400">
                  {suggestion.type}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </form>
  );
}
