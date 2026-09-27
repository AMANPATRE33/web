import { ProductGridSkeleton } from "@/components/catalog/ProductGrid";

/**
 * Shop loading skeleton.
 *
 * Matches the real layout - sidebar width, 4 columns, 1:1 image blocks - so the
 * grid does not jump when the data lands. A spinner on a listing page is worse
 * than useless here: it hides the page structure the customer is about to scan.
 */
export default function Loading() {
  return (
    <div className="container-page py-10 sm:py-14">
      <div className="mb-6 h-8 w-64 animate-pulse rounded-xs bg-ink-200" />
      <div className="mb-8 h-4 w-full max-w-2xl animate-pulse rounded-xs bg-ink-100" />
      <div className="flex flex-col gap-6 lg:flex-row">
        <div className="hidden w-60 shrink-0 space-y-4 lg:block" aria-hidden="true">
          {Array.from({ length: 5 }, (_, index) => (
            <div key={index} className="space-y-2">
              <div className="h-3 w-20 animate-pulse rounded-xs bg-ink-200" />
              <div className="h-9 animate-pulse rounded-xs bg-ink-100" />
            </div>
          ))}
        </div>
        <div className="min-w-0 flex-1">
          <div className="mb-4 flex items-center justify-between">
            <div className="h-3 w-24 animate-pulse rounded-xs bg-ink-200" />
            <div className="h-9 w-40 animate-pulse rounded-xs bg-ink-100" />
          </div>
          <ProductGridSkeleton count={8} />
        </div>
      </div>
      <p className="sr-only" role="status">
        Loading products
      </p>
    </div>
  );
}
