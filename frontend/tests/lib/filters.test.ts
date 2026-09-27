import { describe, expect, it } from "vitest";

import {
  activeChips,
  readFilters,
  removeChip,
  toQuery,
  toggleValue,
  writeFilters,
  type FilterState,
} from "@/lib/filters";

const blank: FilterState = {
  page: 1,
  perPage: 24,
  category: [],
  brand: [],
  material: [],
  size: [],
  tag: [],
  inStock: false,
  onSale: false,
  sort: "newest",
  q: "",
};

describe("readFilters", () => {
  it("returns defaults for an empty query string", () => {
    expect(readFilters(new URLSearchParams())).toEqual(blank);
  });

  it("splits comma-joined multi-value filters", () => {
    const state = readFilters(
      new URLSearchParams("material=3MM+ACP,5MM+FOAMSHEET&size=18x24"),
    );
    expect(state.material).toEqual(["3MM ACP", "5MM FOAMSHEET"]);
    expect(state.size).toEqual(["18x24"]);
  });

  it("preserves the space in a material name rather than encoding it", () => {
    // "3MM ACP" is a display value, not a slug. Losing the space would make the
    // filter silently match nothing.
    const state = readFilters(new URLSearchParams("material=3MM ACP"));
    expect(state.material).toEqual(["3MM ACP"]);
  });

  it("clamps page to a positive integer", () => {
    expect(readFilters(new URLSearchParams("page=0")).page).toBe(1);
    expect(readFilters(new URLSearchParams("page=-5")).page).toBe(1);
    expect(readFilters(new URLSearchParams("page=abc")).page).toBe(1);
  });

  it("clamps per_page into a sane range", () => {
    expect(readFilters(new URLSearchParams("per_page=0")).perPage).toBe(1);
    expect(readFilters(new URLSearchParams("per_page=9999")).perPage).toBe(100);
  });

  it("falls back to newest for an unknown sort", () => {
    expect(readFilters(new URLSearchParams("sort=chaos")).sort).toBe("newest");
  });

  it("accepts a known sort", () => {
    expect(readFilters(new URLSearchParams("sort=price_asc")).sort).toBe("price_asc");
  });

  it("ignores a negative price bound rather than passing it to the API", () => {
    const state = readFilters(new URLSearchParams("min_price=-500"));
    expect(state.minPrice).toBeUndefined();
  });
});

describe("writeFilters", () => {
  it("omits everything at its default, so a clean shop URL stays clean", () => {
    expect(writeFilters(blank)).toBe("");
  });

  it("round-trips a non-default state", () => {
    const state: FilterState = {
      ...blank,
      page: 3,
      category: ["msds"],
      material: ["3MM ACP"],
      size: ["18x24"],
      inStock: true,
      sort: "price_asc",
    };
    expect(readFilters(new URLSearchParams(writeFilters(state)))).toEqual(state);
  });

  it("serialises a price of zero rather than dropping it", () => {
    // min_price=0 is a real bound meaning "free and up". Omitting it would turn
    // a deliberate filter into an absent one.
    const query = writeFilters({ ...blank, minPrice: 0 });
    expect(query).toContain("min_price=0");
  });
});

describe("toQuery", () => {
  it("sends only the filters that are actually set", () => {
    const query = toQuery({ ...blank, material: ["3MM ACP"] });
    expect(query.material).toEqual(["3MM ACP"]);
    expect(query.category).toBeUndefined();
    expect(query.size).toBeUndefined();
  });

  it("omits false booleans so the backend default applies", () => {
    const query = toQuery(blank);
    expect(query.in_stock).toBeUndefined();
    expect(query.on_sale).toBeUndefined();
  });
});

describe("activeChips", () => {
  it("produces one chip per selected value", () => {
    const chips = activeChips({
      ...blank,
      material: ["3MM ACP"],
      size: ["18x24"],
      category: ["msds"],
    });
    expect(chips.map((c) => c.key).sort()).toEqual(["category", "material", "size"]);
  });

  it("labels sizes with the unit so the chip is readable", () => {
    const chip = activeChips({ ...blank, size: ["18x24"] })[0];
    expect(chip.label).toBe("18x24 in.");
  });

  it("returns nothing when no filter is set", () => {
    expect(activeChips(blank)).toEqual([]);
  });

  it("adds a single price chip for a two-sided range", () => {
    const chips = activeChips({ ...blank, minPrice: 10_000, maxPrice: 50_000 });
    expect(chips).toHaveLength(1);
    expect(chips[0].key).toBe("price");
  });
});

describe("removeChip", () => {
  it("removes only the clicked value and resets to page 1", () => {
    const state: FilterState = { ...blank, page: 4, material: ["3MM ACP", "5MM FOAMSHEET"] };
    const next = removeChip(state, { key: "material", value: "3MM ACP", label: "3MM ACP" });
    expect(next.material).toEqual(["5MM FOAMSHEET"]);
    expect(next.page).toBe(1);
  });

  it("clears both bounds for the price chip", () => {
    const state: FilterState = { ...blank, minPrice: 1, maxPrice: 2 };
    const next = removeChip(state, { key: "price", value: "price", label: "x" });
    expect(next.minPrice).toBeUndefined();
    expect(next.maxPrice).toBeUndefined();
  });
});

describe("toggleValue", () => {
  it("adds a value", () => {
    expect(toggleValue(blank, "material", "3MM ACP").material).toEqual(["3MM ACP"]);
  });

  it("removes a value that is already selected", () => {
    const state = { ...blank, material: ["3MM ACP"] };
    expect(toggleValue(state, "material", "3MM ACP").material).toEqual([]);
  });

  it("resets to page 1 so a new filter is not applied to page 7", () => {
    const state = { ...blank, page: 7 };
    expect(toggleValue(state, "material", "3MM ACP").page).toBe(1);
  });

  it("leaves other axes untouched", () => {
    const state = { ...blank, size: ["18x24"] };
    const next = toggleValue(state, "material", "3MM ACP");
    expect(next.size).toEqual(["18x24"]);
  });
});
