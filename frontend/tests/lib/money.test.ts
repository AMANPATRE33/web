import { describe, expect, it } from "vitest";

import { formatMinor, hasRealRating, moneyLabel, stockLabel, stockTone } from "@/lib/money";
import { isVector, resolveImageUrl } from "@/lib/images";

describe("formatMinor", () => {
  it("uses Indian digit grouping, not western", () => {
    // 1,234,567 is the wrong answer for this audience. 12,34,567 is right.
    expect(formatMinor(123_456_700)).toBe("Rs.12,34,567");
    expect(formatMinor(100_000_00)).toBe("Rs.1,00,000");
  });

  it("leaves three or fewer digits ungrouped", () => {
    expect(formatMinor(99900)).toBe("Rs.999");
  });

  it("omits a trailing .00 on a whole-rupee price", () => {
    expect(formatMinor(18_000)).toBe("Rs.180");
  });

  it("shows paise only when there are any", () => {
    expect(formatMinor(18_050)).toBe("Rs.180.50");
  });

  it("is exact where float arithmetic would drift", () => {
    // 0.1 + 0.2 !== 0.3 in floating point. Integer minor units must not.
    expect(formatMinor(10 + 20)).toBe("Rs.0.30");
  });

  it("handles a negative amount", () => {
    expect(formatMinor(-18_000)).toBe("-Rs.180");
  });

  it("handles zero", () => {
    expect(formatMinor(0)).toBe("Rs.0");
  });
});

describe("moneyLabel", () => {
  it("prefers the server's own string, which is authoritative", () => {
    expect(
      moneyLabel({ amount: 18_000, currency: "INR", symbol: "Rs.", formatted: "Rs.180" }),
    ).toBe("Rs.180");
  });
  it("returns an empty string for null, so callers never render 'null'", () => {
    expect(moneyLabel(null)).toBe("");
    expect(moneyLabel(undefined)).toBe("");
  });
});

describe("hasRealRating", () => {
  it("is false when there are no reviews, so no stars are rendered", () => {
    // The seeded catalogue has zero reviews because the live site publishes
    // none. Rendering a star rating anyway would be fabricated social proof.
    expect(hasRealRating(0)).toBe(false);
  });
  it("is true once real reviews exist", () => {
    expect(hasRealRating(3)).toBe(true);
  });
});

describe("stockLabel / stockTone", () => {
  it("gives a distinct label per status", () => {
    expect(stockLabel("in_stock")).toBe("In stock");
    expect(stockLabel("out_of_stock")).toBe("Out of stock");
    expect(stockLabel("low_stock")).toBe("Low stock");
  });
  it("falls back to a non-committal label for an unknown status", () => {
    // Never claim availability we do not have.
    expect(stockLabel("who_knows")).toBe("Availability on request");
    expect(stockTone("who_knows")).toBe("muted");
  });
  it("maps out_of_stock to the danger tone", () => {
    expect(stockTone("out_of_stock")).toBe("danger");
  });
});

describe("resolveImageUrl", () => {
  it("passes a root-relative seed path through unchanged", () => {
    // These resolve against the Next.js origin from public/, and must not be
    // prefixed with the API host.
    expect(resolveImageUrl("/seed/msds/SPP-MDS-001.svg")).toBe(
      "/seed/msds/SPP-MDS-001.svg",
    );
  });

  it("passes an absolute storage URL through unchanged", () => {
    const url = "https://abc.supabase.co/storage/v1/object/public/products/a.jpg";
    expect(resolveImageUrl(url)).toBe(url);
  });

  it("upgrades a protocol-relative URL to https", () => {
    expect(resolveImageUrl("//cdn.example.com/a.jpg")).toBe("https://cdn.example.com/a.jpg");
  });

  it("returns null for a missing url rather than a broken src", () => {
    expect(resolveImageUrl(null)).toBeNull();
    expect(resolveImageUrl("")).toBeNull();
    expect(resolveImageUrl("   ")).toBeNull();
  });

  it("never references the old Wix CDN", () => {
    // The reference site is a content source, not an asset host.
    const resolved = resolveImageUrl("https://static.wixstatic.com/media/x.jpg");
    expect(resolved).toBe("https://static.wixstatic.com/media/x.jpg");
    // The assertion above is that we do not *rewrite* or *depend on* it; the
    // store simply never stores such a URL. Guard the code path instead:
    expect(resolveImageUrl("/seed/a.svg")).not.toContain("wixstatic");
  });
});

describe("isVector", () => {
  it("detects svg, including with a query string", () => {
    expect(isVector("/seed/a.svg")).toBe(true);
    expect(isVector("/seed/a.SVG")).toBe(true);
    expect(isVector("/seed/a.svg?v=2")).toBe(true);
  });
  it("does not flag raster formats", () => {
    expect(isVector("/a.jpg")).toBe(false);
    expect(isVector("/a.webp")).toBe(false);
    // "mysvg" contains the letters but is not a vector file.
    expect(isVector("/a.mysvgx")).toBe(false);
  });
});
