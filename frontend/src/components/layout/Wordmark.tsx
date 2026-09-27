"use client";

/**
 * Wordmark.
 *
 * Rendered as text rather than an image: it stays crisp at any DPR, inherits
 * the current colour, and it is the one piece of brand furniture that must
 * never be missing because an asset 404'd. The amber rule underneath is the
 * only decorative element in the header.
 */
/**
 * Wordmark.
 *
 * Rendered as text rather than an image: it stays crisp at any DPR, inherits
 * the current colour, and it is the one piece of brand furniture that must
 * never be missing because an asset 404'd. The amber rule underneath is the
 * only decorative element in the header.
 *
 * The two-line stacking is `lg:hidden`, not `sm:hidden`. The desktop navigation
 * appears at `lg`, and the wordmark has to collapse to one line by then: with
 * the full primary nav plus the promoted category links, a two-line wordmark at
 * the 1024px breakpoint pushed the search, account and cart icons 159px off
 * the right edge of the screen.
 */
export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={className}>
      <span className="block text-[15px] font-extrabold leading-none tracking-[-0.02em] text-ink-950 uppercase lg:text-base">
        Safety Poster
        <br className="lg:hidden" /> Prints
      </span>
      <span aria-hidden="true" className="mt-1 block h-[3px] w-7 bg-signal-400" />
      <span className="sr-only">Safety Poster Prints - home</span>
    </span>
  );
}
