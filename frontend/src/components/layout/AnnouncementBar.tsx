import Link from "next/link";

import { business } from "@/lib/env";

/**
 * The announcement bar.
 *
 * One line, no dismiss button, no carousel. A rotating bar is the most common
 * source of layout shift in an ecommerce header and a distraction on a page
 * whose job is to sell safety signage.
 */
export function AnnouncementBar() {
  return (
    <div className="dark-surface bg-ink-950 text-white">
      <div className="container-page flex h-9 items-center justify-center gap-2">
        <p className="truncate text-center text-[12px] font-medium tracking-wide sm:text-[13px]">
          {business.tagline}
        </p>
        <span aria-hidden="true" className="hidden h-3 w-px bg-white/25 sm:block" />
        <Link
          href="/bulk-order"
          className="hidden shrink-0 text-[12px] font-semibold text-signal-400 underline-offset-4 hover:underline sm:block"
        >
          Bulk quotes
        </Link>
      </div>
    </div>
  );
}
