"use client";

/**
 * Filter UI driven entirely by the URL.
 *
 * `router.push` with `scroll: false` on every change means the server component
 * re-renders with the new result set, so the grid, the count and the pagination
 * are always server-rendered truth. There is no client-side copy of the result
 * set that can drift from the database.
 *
 * `useTransition` keeps the previous results visible while the new page loads,
 * which is what stops the grid flashing to skeletons on every checkbox.
 */

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { ChevronDown, SlidersHorizontal, X } from "lucide-react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { useCallback, useMemo, useState, useTransition } from "react";

import { Button, Checkbox, Label } from "@/components/ui";
import type { Category, Facets } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import {
  activeChips,
  readFilters,
  removeChip,
  SORTS,
  toggleValue,
  writeFilters,
  type ActiveChip,
  type FilterState,
} from "@/lib/filters";
import { formatMinor } from "@/lib/money";

export function FilterControls({
  facets,
  categories,
  /** Locks the category facet off, e.g. on a category page. */
  hideCategory = false,
  lockedCategorySlug,
}: {
  facets: Facets;
  categories: Category[];
  hideCategory?: boolean;
  lockedCategorySlug?: string;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [pending, startTransition] = useTransition();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const urlState = useMemo(
    () => readFilters(new URLSearchParams(searchParams.toString())),
    [searchParams],
  );

  /**
   * Optimistic filter state.
   *
   * The URL is the source of truth, but it can only become truth after the
   * server has re-rendered the route. Reading the checkbox straight from
   * `searchParams` therefore leaves the box visually unticked for the length of
   * a network round trip, which reads as a broken control - and Playwright
   * caught exactly that: the URL updated, the checkbox did not tick.
   *
   * So the last requested state is held locally and used until the URL catches
   * up. `optimistic` is keyed by the exact query string that produced it, so
   * the moment the URL matches, the override is dropped and the UI is back to
   * pure server truth with no effect to unwind.
   */
  const [optimistic, setOptimistic] = useState<{ query: string; state: FilterState } | null>(
    null,
  );
  const urlQuery = searchParams.toString();

  // Drop the override once the URL catches up. Done as a render-phase update
  // on this component's own state, which React explicitly supports and which
  // avoids both a stale override and a setState-in-effect.
  if (optimistic !== null && optimistic.query === urlQuery) setOptimistic(null);

  // While the navigation is in flight the URL still holds the *old* query, so
  // the override is the only way to reflect the click immediately.
  const state = optimistic !== null ? optimistic.state : urlState;

  const chips = useMemo(() => activeChips(state), [state]);

  const navigate = useCallback(
    (next: FilterState) => {
      const query = writeFilters(next);
      setOptimistic({ query, state: next });
      startTransition(() => {
        // Push the bare pathname when the query is empty, not "?". A trailing
        // "?" produces two distinct URLs for the same page, which splits
        // analytics and looks sloppy when shared.
        router.push(query ? `${pathname}?${query}` : pathname, { scroll: false });
      });
    },
    [pathname, router],
  );

  const onToggle = useCallback(
    (key: "category" | "brand" | "material" | "size" | "tag", value: string) => {
      navigate(toggleValue(state, key, value));
    },
    [navigate, state],
  );

  const body = (
    <div className={cn("space-y-1", pending && "opacity-60")}>
      {!hideCategory && categories.length > 0 ? (
        <FilterGroup title="Category" defaultOpen>
          {categories.map((category) => (
            <Checkbox
              key={category.id}
              label={category.name}
              description={undefined}
              checked={state.category.includes(category.slug)}
              onChange={() => onToggle("category", category.slug)}
            />
          ))}
        </FilterGroup>
      ) : null}

      {lockedCategorySlug ? (
        <input type="hidden" name="category" value={lockedCategorySlug} />
      ) : null}

      <FilterGroup
        title="Material"
        defaultOpen
        hint="The substrate the sign is printed and mounted on."
      >
        {facets.materials.map((material) => (
          <FacetRow
            key={material.value}
            label={material.value}
            count={material.count}
            checked={state.material.includes(material.value)}
            onChange={() => onToggle("material", material.value)}
          />
        ))}
      </FilterGroup>

      <FilterGroup title="Size" defaultOpen hint="Dimensions in inches.">
        {facets.sizes.map((size) => (
          <FacetRow
            key={size.value}
            label={size.value}
            count={size.count}
            checked={state.size.includes(size.value)}
            onChange={() => onToggle("size", size.value)}
          />
        ))}
      </FilterGroup>

      <FilterGroup
        title="Price"
        defaultOpen
        hint={`Catalogue range ${formatMinor(facets.price_range.min)} to ${formatMinor(facets.price_range.max)}`}
      >
        <PriceRange
          min={state.minPrice}
          max={state.maxPrice}
          bounds={facets.price_range}
          onCommit={(min, max) => navigate({ ...state, minPrice: min, maxPrice: max, page: 1 })}
        />
      </FilterGroup>

      <FilterGroup title="Availability" defaultOpen>
        <Checkbox
          label="In stock only"
          checked={state.inStock}
          onChange={() => navigate({ ...state, inStock: !state.inStock, page: 1 })}
        />
        <Checkbox
          label="On sale"
          checked={state.onSale}
          onChange={() => navigate({ ...state, onSale: !state.onSale, page: 1 })}
        />
      </FilterGroup>

      {facets.brands.length > 1 ? (
        <FilterGroup title="Brand">
          {facets.brands.map((brand) => (
            <FacetRow
              key={brand.value}
              label={brand.value}
              count={brand.count}
              checked={state.brand.includes(brand.value)}
              onChange={() => onToggle("brand", brand.value)}
            />
          ))}
        </FilterGroup>
      ) : null}
    </div>
  );

  return (
    <>
      {/* --- desktop sidebar --- */}
      <aside className="hidden w-60 shrink-0 lg:block" aria-label="Filters">
        <div className="sticky top-32 max-h-[calc(100vh-9rem)] overflow-y-auto pr-1">
          {chips.length > 0 ? (
            <div className="mb-4 flex items-center justify-between border-b border-ink-200 pb-3">
              <span className="text-[13px] font-semibold text-ink-900">
                {chips.length} filter{chips.length === 1 ? "" : "s"}
              </span>
              <button
                type="button"
                onClick={() => navigate({ ...state, page: 1, category: [], brand: [], material: [], size: [], tag: [], minPrice: undefined, maxPrice: undefined, inStock: false, onSale: false })}
                className="text-[12px] font-semibold text-ink-600 underline underline-offset-4 hover:text-ink-950"
              >
                Clear all
              </button>
            </div>
          ) : null}
          {body}
        </div>
      </aside>

      {/* --- mobile trigger + drawer --- */}
      <div className="lg:hidden">
        <DialogPrimitive.Root open={drawerOpen} onOpenChange={setDrawerOpen}>
          <DialogPrimitive.Trigger asChild>
            <Button variant="outline" size="md" className="w-full justify-between">
              <span className="flex items-center gap-2">
                <SlidersHorizontal aria-hidden="true" className="size-4" />
                Filters
                {chips.length > 0 ? (
                  <span className="tabular rounded-xs bg-ink-950 px-1.5 py-0.5 text-[10px] font-bold text-white">
                    {chips.length}
                  </span>
                ) : null}
              </span>
              <span className="text-[12px] font-medium text-ink-500">Show results</span>
            </Button>
          </DialogPrimitive.Trigger>

          <DialogPrimitive.Portal>
            <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-ink-950/50" />
            <DialogPrimitive.Content
              className={cn(
                "fixed inset-x-0 bottom-0 z-50 flex max-h-[88vh] flex-col rounded-t-lg bg-white shadow-2xl outline-none",
                "data-[state=open]:animate-in data-[state=open]:slide-in-from-bottom",
              )}
            >
              <DialogPrimitive.Title className="sr-only">Filter products</DialogPrimitive.Title>
              <DialogPrimitive.Description className="sr-only">
                Narrow the product list by category, material, size, price and availability.
              </DialogPrimitive.Description>

              <div className="flex shrink-0 items-center justify-between border-b border-ink-200 px-4 py-3">
                <p className="text-[15px] font-bold text-ink-950">Filters</p>
                <DialogPrimitive.Close asChild>
                  <Button variant="quiet" size="icon" aria-label="Close filters">
                    <X aria-hidden="true" />
                  </Button>
                </DialogPrimitive.Close>
              </div>

              <div className="flex-1 overflow-y-auto overscroll-contain px-4 py-2">{body}</div>

              <div className="shrink-0 border-t border-ink-200 p-4">
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={() =>
                      navigate({
                        ...state,
                        page: 1,
                        category: [],
                        brand: [],
                        material: [],
                        size: [],
                        tag: [],
                        minPrice: undefined,
                        maxPrice: undefined,
                        inStock: false,
                        onSale: false,
                      })
                    }
                    className="flex-1"
                  >
                    Clear all
                  </Button>
                  <DialogPrimitive.Close asChild>
                    <Button variant="primary" className="flex-[2]">
                      Show results
                    </Button>
                  </DialogPrimitive.Close>
                </div>
              </div>
            </DialogPrimitive.Content>
          </DialogPrimitive.Portal>
        </DialogPrimitive.Root>
      </div>
    </>
  );
}

function FilterGroup({
  title,
  children,
  hint,
  defaultOpen = false,
}: {
  title: string;
  children: React.ReactNode;
  hint?: string;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-b border-ink-200 py-3 last:border-0">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full items-center justify-between text-left"
      >
        <span className="text-[13px] font-bold uppercase tracking-[0.06em] text-ink-900">
          {title}
        </span>
        <ChevronDown
          aria-hidden="true"
          className={cn("size-4 text-ink-400 transition-transform", open && "rotate-180")}
        />
      </button>
      {open ? (
        <div className="mt-3 space-y-2.5">
          {hint ? <p className="text-[12px] leading-relaxed text-ink-500">{hint}</p> : null}
          {children}
        </div>
      ) : null}
    </div>
  );
}

function FacetRow({
  label,
  count,
  checked,
  onChange,
}: {
  label: string;
  count: number;
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <div className="flex items-start justify-between gap-2">
      <Checkbox
        label={<span className="font-mono text-[12px] uppercase tracking-wide">{label}</span>}
        checked={checked}
        onChange={onChange}
        className="min-w-0 flex-1"
      />
      <span className="tabular mt-0.5 shrink-0 text-[11px] text-ink-400">{count}</span>
    </div>
  );
}

/**
 * Price range.
 *
 * Two number inputs rather than a dual-thumb slider. A custom range slider
 * needs two overlapping inputs and a z-index dance to be keyboard-operable,
 * and the value the buyer cares about - a rupee figure - is easier to type than
 * to hunt for by dragging. The inputs are `type="number"`, clamped to the
 * catalogue bounds, and commit on blur or Enter.
 */
function PriceRange({
  min,
  max,
  bounds,
  onCommit,
}: {
  min: number | undefined;
  max: number | undefined;
  bounds: { min: number; max: number };
  onCommit: (min: number | undefined, max: number | undefined) => void;
}) {
  const floor = Math.max(0, bounds.min);
  const ceiling = Math.max(bounds.max, bounds.min + 100);

  const commit = (rawMin: string, rawMax: string) => {
    const parse = (value: string): number | undefined => {
      if (!value.trim()) return undefined;
      const parsed = Number.parseFloat(value) * 100; // rupees -> paise
      if (!Number.isFinite(parsed) || parsed < 0) return undefined;
      return Math.min(Math.round(parsed), ceiling);
    };
    const nextMin = parse(rawMin);
    const nextMax = parse(rawMax);
    // An inverted range is a data-entry slip, not an empty result set.
    if (nextMin !== undefined && nextMax !== undefined && nextMin > nextMax) {
      onCommit(nextMax, nextMin);
      return;
    }
    onCommit(nextMin, nextMax);
  };

  return (
    <div>
      <div className="flex items-end gap-2">
        <div className="min-w-0 flex-1">
          <Label htmlFor="price-min" className="mb-1 text-[11px] text-ink-500">
            Min (Rs.)
          </Label>
          <input
            id="price-min"
            type="number"
            inputMode="numeric"
            min={0}
            defaultValue={min === undefined ? "" : Math.round(min / 100)}
            placeholder={String(Math.round(floor / 100))}
            onBlur={(event) => {
              const target = event.currentTarget.form?.elements.namedItem("price-max") as
                | HTMLInputElement
                | null;
              commit(event.target.value, target?.value ?? "");
            }}
            className="tabular h-10 w-full rounded-xs border border-ink-300 px-2.5 text-[13px]"
          />
        </div>
        <span aria-hidden="true" className="pb-2.5 text-ink-400">
          &ndash;
        </span>
        <div className="min-w-0 flex-1">
          <Label htmlFor="price-max" className="mb-1 text-[11px] text-ink-500">
            Max (Rs.)
          </Label>
          <input
            id="price-max"
            name="price-max"
            type="number"
            inputMode="numeric"
            min={0}
            defaultValue={max === undefined ? "" : Math.round(max / 100)}
            placeholder={String(Math.round(ceiling / 100))}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                const target = event.currentTarget.form?.elements.namedItem("price-min") as
                  | HTMLInputElement
                  | null;
                commit(target?.value ?? "", event.currentTarget.value);
              }
            }}
            onBlur={(event) => {
              const target = event.currentTarget.form?.elements.namedItem("price-min") as
                | HTMLInputElement
                | null;
              commit(target?.value ?? "", event.target.value);
            }}
            className="tabular h-10 w-full rounded-xs border border-ink-300 px-2.5 text-[13px]"
          />
        </div>
      </div>
      <p className="mt-2 text-[11px] text-ink-400">
        Prices vary by material and size. Enter whole rupees.
      </p>
    </div>
  );
}

/** Removable chip row above the grid. */
export function ActiveFilterChips({
  chips,
  className,
}: {
  chips: ActiveChip[];
  className?: string;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [pending, startTransition] = useTransition();
  const state = useMemo(
    () => readFilters(new URLSearchParams(searchParams.toString())),
    [searchParams],
  );

  if (chips.length === 0) return null;

  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      {chips.map((chip) => (
        <button
          key={`${chip.key}:${chip.value}`}
          type="button"
          disabled={pending}
          onClick={() => {
            const next = removeChip(state, chip);
            const query = writeFilters(next);
            startTransition(() => {
              router.push(query ? `${pathname}?${query}` : pathname, { scroll: false });
            });
          }}
          className="inline-flex items-center gap-1.5 rounded-xs border border-ink-300 bg-white px-2 py-1 text-[12px] font-medium text-ink-800 transition-colors hover:border-ink-900 hover:bg-ink-50"
        >
          {chip.label}
          <X aria-hidden="true" className="size-3.5 text-ink-400" />
          <span className="sr-only">Remove filter</span>
        </button>
      ))}
      <button
        type="button"
        disabled={pending}
        onClick={() =>
          startTransition(() => {
            router.push(pathname, { scroll: false });
          })
        }
        className="text-[12px] font-semibold text-ink-600 underline underline-offset-4 hover:text-ink-950"
      >
        Clear all
      </button>
    </div>
  );
}

/** Sort dropdown, also URL-driven. */
export function SortSelect({ className }: { className?: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [pending, startTransition] = useTransition();
  const state = useMemo(
    () => readFilters(new URLSearchParams(searchParams.toString())),
    [searchParams],
  );

  /**
   * A `<select>` is not a controlled-input problem: the browser keeps the
   * chosen option visible on its own, so this needs no optimistic override the
   * way a checkbox does. Only the URL and the re-sorted grid lag by a round
   * trip, and the grid dimming during the transition covers that.
   */
  function applySort(value: FilterState["sort"]) {
    const next = { ...state, sort: value, page: 1 };
    const query = writeFilters(next);
    startTransition(() => {
      router.push(query ? `${pathname}?${query}` : pathname, { scroll: false });
    });
  }

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <label htmlFor="sort" className="shrink-0 text-[13px] text-ink-600">
        Sort
      </label>
      <select
        id="sort"
        value={state.sort}
        disabled={pending}
        onChange={(event) => applySort(event.target.value as FilterState["sort"])}
        className="h-9 rounded-xs border border-ink-300 bg-white pl-2.5 pr-8 text-[13px] font-semibold text-ink-900"
      >
        {SORTS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
