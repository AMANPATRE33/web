"use client";

import Link from "next/link";
import { useEffect } from "react";

import { Button } from "@/components/ui";

/**
 * Route-level error boundary.
 *
 * Next.js requires this to be a client component. It catches render errors in
 * the segment it wraps - a failed data fetch that throws, a bug in a component.
 * The digest is shown so a customer-reported failure maps to a server log line.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Surfaced in the browser console. In production the request id and digest
    // are what make this diagnosable.
    console.error("Route error:", error);
  }, [error]);

  return (
    <div className="container-page flex min-h-[60vh] flex-col items-center justify-center py-20 text-center">
      <p className="eyebrow">Something went wrong</p>
      <h1 className="mt-3 text-2xl sm:text-3xl">We couldn&apos;t load this page</h1>
      <p className="mt-3 max-w-lg text-[15px] leading-relaxed text-ink-600">
        The page failed to render. Trying again often fixes it. If it keeps happening, contact
        us and we will take your order directly.
      </p>
      {error.digest ? (
        <p className="mt-3 font-mono text-[11px] text-ink-400">Reference: {error.digest}</p>
      ) : null}
      <div className="mt-7 flex flex-wrap justify-center gap-3">
        <Button variant="primary" size="lg" onClick={reset}>
          Try again
        </Button>
        <Button variant="outline" size="lg" asChild>
          <Link href="/">Back to home</Link>
        </Button>
        <Button variant="outline" size="lg" asChild>
          <Link href="/shop">Browse products</Link>
        </Button>
      </div>
    </div>
  );
}
