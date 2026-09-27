/**
 * Search suggestions, proxied to the API server-side.
 *
 * ## Why this route exists
 *
 * The suggestion box is a client component, so its first implementation called
 * the FastAPI backend straight from the browser. That is a cross-origin
 * request, and it fails in exactly the deployment shape this project uses:
 * the storefront on Vercel and the API on Railway are different origins, so
 * the request needs CORS to be configured correctly, and any misconfiguration
 * silently breaks typing in the search box with nothing more informative than
 * a console error.
 *
 * It failed in local development for the same reason - `localhost:3100` and
 * `127.0.0.1:8000` are different origins, and the browser blocked it. The audit
 * caught it as a console error on `/search`:
 *
 *   Access to fetch at 'http://localhost:8000/api/v1/search/suggestions'
 *   from origin 'http://127.0.0.1:3100' has been blocked by CORS policy
 *
 * Proxied through the Next.js server instead. The browser only ever talks to
 * its own origin, so:
 *
 *   - there is no CORS dependency for this call in any environment;
 *   - the API base URL is no longer needed in the client bundle for it;
 *   - the backend's error envelope is normalised in one place.
 *
 * Cost is one extra same-origin hop, which is immeasurable next to the
 * correctness win. The `sizes` list is deliberately capped, because this
 * returns on every keystroke past a debounce.
 */

import { NextResponse } from "next/server";

import { getSearchSuggestions } from "@/lib/api/catalog";
import type { SearchSuggestion } from "@/lib/api/types";

/** Never cache: suggestions track catalogue changes and are per-keystroke. */
export const dynamic = "force-dynamic";

const MIN_QUERY = 2;
const MAX_QUERY = 100;
const MAX_SUGGESTIONS = 7;

export async function GET(request: Request): Promise<NextResponse> {
  const { searchParams } = new URL(request.url);
  const raw = searchParams.get("q") ?? "";
  const query = raw.trim().slice(0, MAX_QUERY);

  if (query.length < MIN_QUERY) {
    return NextResponse.json({ suggestions: [] });
  }

  try {
    const suggestions: SearchSuggestion[] = await getSearchSuggestions(
      query,
      MAX_SUGGESTIONS,
    );
    return NextResponse.json(
      { suggestions },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch {
    // A failed suggestion lookup must never break typing. The search results
    // page still works; only the dropdown is absent.
    return NextResponse.json({ suggestions: [] }, { status: 200 });
  }
}
