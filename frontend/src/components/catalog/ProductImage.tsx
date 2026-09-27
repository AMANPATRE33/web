import Image from "next/image";

import { isVector, resolveImageUrl } from "@/lib/images";
import { cn } from "@/lib/cn";

/**
 * Product artwork.
 *
 * Deliberately renders a legible placeholder *block* rather than nothing when
 * the URL is missing: a card with a hole where the product should be reads as a
 * broken page, and a safety poster is the entire reason the customer is here.
 * Placeholder artwork is generated in ISO signal colours by
 * `backend/app/scripts/placeholders.py`, so the fallback uses the same language.
 */
export function ProductImage({
  src,
  alt,
  width,
  height,
  sizes = "(min-width: 1280px) 280px, (min-width: 768px) 33vw, 50vw",
  priority = false,
  className,
  imageClassName,
}: {
  src: string | null | undefined;
  alt: string;
  width?: number;
  height?: number;
  sizes?: string;
  priority?: boolean;
  className?: string;
  imageClassName?: string;
}) {
  const url = resolveImageUrl(src);

  if (!url) {
    return (
      <div
        className={cn(
          "flex items-center justify-center bg-ink-100 text-center",
          className,
        )}
        role="img"
        aria-label={`${alt} - image unavailable`}
      >
        <span className="px-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-ink-400">
          No image
        </span>
      </div>
    );
  }

  return (
    <div className={cn("relative overflow-hidden bg-white", className)}>
      <Image
        src={url}
        alt={alt}
        width={width ?? 800}
        height={height ?? 800}
        sizes={sizes}
        priority={priority}
        unoptimized={isVector(url)}
        className={cn("h-full w-full object-contain", imageClassName)}
      />
    </div>
  );
}
