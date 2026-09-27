/**
 * Global loading skeleton.
 *
 * Deliberately sparse. This is what a customer sees for a few hundred
 * milliseconds during a hard navigation, so it shows the page frame and nothing
 * that would be wrong on the page that is actually coming.
 */
export default function Loading() {
  return (
    <div className="container-page py-14" aria-busy="true">
      <div className="h-3 w-32 animate-pulse rounded-xs bg-ink-200" />
      <div className="mt-4 h-9 w-full max-w-lg animate-pulse rounded-xs bg-ink-200" />
      <div className="mt-3 h-4 w-full max-w-2xl animate-pulse rounded-xs bg-ink-100" />
      <div className="mt-10 grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-4">
        {Array.from({ length: 8 }, (_, index) => (
          <div key={index}>
            <div className="aspect-square animate-pulse bg-ink-100" />
            <div className="mt-3 h-4 w-full animate-pulse rounded-xs bg-ink-200" />
            <div className="mt-2 h-3 w-2/3 animate-pulse rounded-xs bg-ink-100" />
          </div>
        ))}
      </div>
      <p className="sr-only" role="status">
        Loading
      </p>
    </div>
  );
}
