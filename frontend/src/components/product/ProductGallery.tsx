"use client";

/**
 * Product gallery: main image, thumbnail rail, keyboard-navigable lightbox.
 *
 * Mobile uses a native horizontal scroll-snap track, which gives real swipe
 * physics and momentum for free rather than a JS drag implementation. The
 * thumbnails are hidden on mobile because the swipe track already provides
 * position feedback via the dot indicators.
 */

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { ChevronLeft, ChevronRight, X, ZoomIn } from "lucide-react";
import { useCallback, useState } from "react";

import { ProductImage } from "@/components/catalog/ProductImage";
import type { ProductImage as ProductImageData } from "@/lib/api/types";
import { cn } from "@/lib/cn";

export function ProductGallery({
  images,
  title,
}: {
  images: ProductImageData[];
  title: string;
}) {
  const [index, setIndex] = useState(0);
  const [zoomOpen, setZoomOpen] = useState(false);

  const ordered = [...images].sort(
    (a, b) => Number(b.is_primary) - Number(a.is_primary) || a.position - b.position,
  );
  const active = ordered[index] ?? ordered[0] ?? null;

  const go = useCallback(
    (delta: number) => setIndex((current) => (current + delta + ordered.length) % ordered.length),
    [ordered.length],
  );

  if (ordered.length === 0) {
    return (
      <div className="aspect-square border border-ink-200 bg-white">
        <ProductImage src={null} alt={title} className="size-full" />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* --- mobile: swipe track with dots --- */}
      <div className="lg:hidden">
        <div className="flex snap-x snap-mandatory gap-2 overflow-x-auto no-scrollbar">
          {ordered.map((image, position) => (
            <div key={image.id} className="w-[85%] shrink-0 snap-center">
              <ProductImage
                src={image.url}
                alt={image.alt_text || `${title} - view ${position + 1}`}
                width={image.width ?? 800}
                height={image.height ?? 800}
                sizes="85vw"
                priority={position === 0}
                className="aspect-square border border-ink-200"
              />
            </div>
          ))}
        </div>
        {ordered.length > 1 ? (
          <div className="mt-2 flex justify-center gap-1.5">
            {ordered.map((image, position) => (
              <span
                key={image.id}
                className={cn(
                  "h-1.5 rounded-full transition-colors",
                  position === index ? "w-5 bg-ink-950" : "w-1.5 bg-ink-300",
                )}
              />
            ))}
          </div>
        ) : null}
      </div>

      {/* --- desktop: main image + thumbnail rail --- */}
      <div className="hidden lg:block">
        <div className="group relative border border-ink-200 bg-white">
          <ProductImage
            src={active.url}
            alt={active.alt_text || `${title} - view ${index + 1}`}
            width={active.width ?? 800}
            height={active.height ?? 800}
            sizes="(min-width: 1024px) 50vw, 100vw"
            priority
            className="aspect-square p-6"
            imageClassName="object-contain"
          />
          {ordered.length > 1 ? (
            <>
              <button
                type="button"
                onClick={() => go(-1)}
                aria-label="Previous image"
                className="absolute left-2 top-1/2 flex size-9 -translate-y-1/2 items-center justify-center rounded-xs border border-ink-200 bg-white/95 text-ink-700 opacity-0 shadow-sm transition-opacity hover:border-ink-900 hover:text-ink-950 focus-visible:opacity-100 group-hover:opacity-100"
              >
                <ChevronLeft aria-hidden="true" className="size-4" />
              </button>
              <button
                type="button"
                onClick={() => go(1)}
                aria-label="Next image"
                className="absolute right-2 top-1/2 flex size-9 -translate-y-1/2 items-center justify-center rounded-xs border border-ink-200 bg-white/95 text-ink-700 opacity-0 shadow-sm transition-opacity hover:border-ink-900 hover:text-ink-950 focus-visible:opacity-100 group-hover:opacity-100"
              >
                <ChevronRight aria-hidden="true" className="size-4" />
              </button>
              <DialogPrimitive.Root open={zoomOpen} onOpenChange={setZoomOpen}>
                <DialogPrimitive.Trigger asChild>
                  <button
                    type="button"
                    aria-label={`Enlarge image ${index + 1} of ${ordered.length}`}
                    className="absolute bottom-2 right-2 flex size-9 items-center justify-center rounded-xs border border-ink-200 bg-white/95 text-ink-700 shadow-sm transition-colors hover:border-ink-900 hover:text-ink-950"
                  >
                    <ZoomIn aria-hidden="true" className="size-4" />
                  </button>
                </DialogPrimitive.Trigger>
                <GalleryLightbox
                  images={ordered}
                  index={index}
                  onIndex={setIndex}
                  title={title}
                />
              </DialogPrimitive.Root>
            </>
          ) : null}
        </div>

        {ordered.length > 1 ? (
          <ul
            className="mt-3 grid grid-cols-5 gap-2"
            aria-label="Product images"
          >
            {ordered.map((image, position) => (
              <li key={image.id}>
                <button
                  type="button"
                  onClick={() => setIndex(position)}
                  aria-current={position === index ? "true" : undefined}
                  aria-label={`Show image ${position + 1}`}
                  className={cn(
                    "block w-full border transition-colors",
                    position === index
                      ? "border-ink-950"
                      : "border-ink-200 hover:border-ink-500",
                  )}
                >
                  <ProductImage
                    src={image.url}
                    alt=""
                    width={120}
                    height={120}
                    sizes="120px"
                    className="aspect-square p-1.5"
                  />
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  );
}

function GalleryLightbox({
  images,
  index,
  onIndex,
  title,
}: {
  images: ProductImageData[];
  index: number;
  onIndex: (index: number) => void;
  title: string;
}) {
  const active = images[index];
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-ink-950/90" />
      <DialogPrimitive.Content
        onKeyDown={(event) => {
          if (event.key === "ArrowRight") onIndex((index + 1) % images.length);
          if (event.key === "ArrowLeft") onIndex((index - 1 + images.length) % images.length);
        }}
        className="fixed inset-0 z-50 flex flex-col items-center justify-center p-4 outline-none"
      >
        <DialogPrimitive.Title className="sr-only">
          {title} - enlarged image
        </DialogPrimitive.Title>
        <DialogPrimitive.Description className="sr-only">
          Image {index + 1} of {images.length}. Use the arrow keys to move between images.
        </DialogPrimitive.Description>

        <ProductImage
          key={active.id}
          src={active.url}
          alt={active.alt_text || title}
          width={active.width ?? 1200}
          height={active.height ?? 1200}
          priority
          className="max-h-[82vh] w-auto"
          imageClassName="object-contain"
        />

        <div className="mt-4 flex items-center gap-4">
          {images.length > 1 ? (
            <>
              <button
                type="button"
                onClick={() => onIndex((index - 1 + images.length) % images.length)}
                className="flex size-10 items-center justify-center rounded-xs border border-white/25 text-white hover:bg-white/10"
                aria-label="Previous image"
              >
                <ChevronLeft aria-hidden="true" className="size-5" />
              </button>
              <span className="tabular text-[13px] text-white/70">
                {index + 1} / {images.length}
              </span>
              <button
                type="button"
                onClick={() => onIndex((index + 1) % images.length)}
                className="flex size-10 items-center justify-center rounded-xs border border-white/25 text-white hover:bg-white/10"
                aria-label="Next image"
              >
                <ChevronRight aria-hidden="true" className="size-5" />
              </button>
            </>
          ) : null}
          <DialogPrimitive.Close asChild>
            <button
              type="button"
              aria-label="Close"
              className="ml-4 flex size-10 items-center justify-center rounded-xs border border-white/25 text-white hover:bg-white/10"
            >
              <X aria-hidden="true" className="size-5" />
            </button>
          </DialogPrimitive.Close>
        </div>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}
