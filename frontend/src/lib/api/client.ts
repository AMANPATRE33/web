/**
 * The single place the frontend talks to the backend.
 *
 * No component calls `fetch` directly. That is not ceremony: it is what makes
 * three things possible at all -
 *
 *   1. one place to normalise the `{ error: { code, message } }` envelope into
 *      a real Error the UI can branch on;
 *   2. one place to attach the Supabase access token, so no screen can
 *      accidentally make an unauthenticated call it thought was authorised;
 *   3. one place to attach a request id, so a customer-reported bug maps to
 *      server logs.
 *
 * `ApiError` deliberately keeps the backend's machine-readable `code`. The UI
 * branches on that rather than on message text, which the backend is free to
 * reword.
 */

import { env } from "@/lib/env";
import type { ApiErrorBody } from "./types";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fieldErrors?: Record<string, string[]>;
  readonly details?: Record<string, unknown>;
  readonly requestId?: string;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message || "Something went wrong.");
    this.name = "ApiError";
    this.status = status;
    this.code = body.code || "unknown_error";
    this.fieldErrors = body.field_errors;
    this.details = body.details;
    this.requestId = body.request_id;
  }

  /** True when the request never reached the application (network, DNS, CORS). */
  get isNetworkError(): boolean {
    return this.status === 0;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }

  get isUnauthorized(): boolean {
    return this.status === 401;
  }

  get isRateLimited(): boolean {
    return this.status === 429;
  }
}

export interface RequestOptions {
  /** Supabase access token, when the caller is authenticated. */
  token?: string | null;
  /** Forwarded to the backend so its logs and emails match the server's. */
  requestId?: string;
  /** Seconds. Server components should use a short one to stay dynamic. */
  revalidate?: number | false;
  tags?: string[];
  signal?: AbortSignal;
  method?: string;
  body?: unknown;
}

/**
 * Reads the Supabase session token without a hard import.
 *
 * Passed in rather than resolved here: this module is used from server
 * components, where there is no browser session to read.
 */
let tokenProvider: (() => Promise<string | null>) | null = null;
export function setTokenProvider(provider: () => Promise<string | null>): void {
  tokenProvider = provider;
}

const DEFAULT_TIMEOUT_MS = 12_000;

function buildUrl(path: string, params?: URLSearchParams): string {
  const url = `${env.apiUrl}${path.startsWith("/") ? path : `/${path}`}`;
  if (!params) return url;
  const query = params.toString();
  return query ? `${url}?${query}` : url;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers({ Accept: "application/json" });

  if (options.token !== undefined && options.token !== null) {
    headers.set("Authorization", `Bearer ${options.token}`);
  } else if (!options.token && tokenProvider) {
    const ambient = await tokenProvider();
    if (ambient) headers.set("Authorization", `Bearer ${ambient}`);
  }
  if (options.requestId) headers.set("X-Request-ID", options.requestId);
  if (options.method && options.method !== "GET") headers.set("Content-Type", "application/json");

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);
  if (options.signal) {
    options.signal.addEventListener("abort", () => controller.abort(), { once: true });
  }

  let response: Response;
  try {
    response = await fetch(buildUrl(path), {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: controller.signal,
      // Server components: opt into ISR/caching explicitly per call. Client
      // components pass nothing, which keeps them uncached and always fresh.
      ...(typeof window === "undefined" && options.revalidate !== undefined
        ? { next: { revalidate: options.revalidate, tags: options.tags } }
        : {}),
      cache: typeof window === "undefined" ? undefined : "no-store",
    });
  } catch {
    // A timeout, an offline device, a DNS failure or a blocked CORS preflight
    // all land here. Status 0 marks them as "never reached the server".
    throw new ApiError(0, {
      code: "network_error",
      message:
        "We couldn't reach the store. Check your connection and try again.",
    });
  } finally {
    clearTimeout(timeout);
  }

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  let parsed: unknown = null;
  if (text.length > 0) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = null;
    }
  }

  if (!response.ok) {
    const body =
      parsed && typeof parsed === "object" && "error" in parsed
        ? ((parsed as { error: ApiErrorBody }).error ?? null)
        : null;
    throw new ApiError(
      response.status,
      body ?? {
        code: "http_error",
        message: `Request failed with status ${response.status}.`,
      },
    );
  }

  return parsed as T;
}

/** Build a `URLSearchParams` from a record, dropping empty values. */
export function toParams(
  source: Record<string, string | number | boolean | string[] | undefined | null>,
): URLSearchParams {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(source)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item) params.append(key, item);
      }
    } else if (typeof value === "boolean") {
      if (value) params.set(key, "true");
    } else {
      params.set(key, String(value));
    }
  }
  return params;
}
