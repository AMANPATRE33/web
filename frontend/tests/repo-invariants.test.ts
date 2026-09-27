import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * Repository-level invariants.
 *
 * These are the rules that are easy to break with a well-meaning edit and hard
 * to notice: a "tidy up" that corrects a misspelled SEO slug, or a page that
 * quietly starts rendering invented business data. Both have already been real
 * decisions in this project, so both are pinned by a test.
 */

const ROOT = process.cwd();

function read(relativePath: string): string {
  return readFileSync(join(ROOT, relativePath), "utf8");
}

/**
 * Every source file, walked from disk.
 *
 * Deliberately not `git ls-files`: these rules must hold for the working tree,
 * including files that have not been committed yet. A test that only inspects
 * committed files silently stops protecting anything the moment a new file is
 * written - which is exactly when a rule matters most.
 */
function sourceFiles(subdir: string): string[] {
  const found: string[] = [];
  const walk = (dir: string) => {
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry);
      if (statSync(full).isDirectory()) {
        if (entry === "node_modules" || entry === ".next") continue;
        walk(full);
      } else if (/\.(ts|tsx)$/.test(entry)) {
        found.push(relative(ROOT, full).replace(/\\/g, "/"));
      }
    }
  };
  walk(join(ROOT, subdir));
  return found;
}

const ALL_SOURCE = sourceFiles("src");
const IS_TEST = (path: string) => path.includes(".test.");

describe("no fabricated business data", () => {
  it("no source file invents a customer count or testimonial", () => {
    // The live site publishes neither, so neither may appear here.
    const banned = [
      /\b\d{1,3},\d{3}\+?\s*(happy\s+)?(customers?|clients?|businesses)\b/i,
      /\btrusted by\b/i,
      /\b\d[\d,]*\s*\+?\s*customers\b/i,
      /testimonial/i,
      /\b\d{1,3},\d{3}\+?\s*(orders?|products)\s*(sold|delivered)\b/i,
    ];

    const files = ALL_SOURCE.filter((file) => !IS_TEST(file));
    expect(files.length).toBeGreaterThan(20);

    const offenders: string[] = [];
    for (const file of files) {
      const source = read(file);
      const lines = source.split("\n");
      for (const pattern of banned) {
        const match = pattern.exec(source);
        if (!match) continue;
        const lineIndex = source.slice(0, match.index).split("\n").length - 1;
        // A comment that explicitly rules the pattern out is the rule being
        // visible where it applies, so allow it.
        if (/\/\/|\*/.test(lines[lineIndex] ?? "")) continue;
        offenders.push(`${file}:${lineIndex + 1} ${match[0]}`);
      }
    }
    expect(offenders).toEqual([]);
  });

  it("does not hard-code a GSTIN", () => {
    // A GSTIN is 15 characters in a fixed format. A plausible-looking one in
    // source would be indexed by search engines and quoted back to us.
    for (const file of ALL_SOURCE) {
      const match = /\b\d{2}[A-Z]{5}\d{4}[A-Z]\d{4}Z[A-Z\d]\b/.exec(read(file));
      expect(match, `${file} contains something shaped like a GSTIN`).toBeNull();
    }
  });

  it("keeps unpublished business facts null in the env module", () => {
    const env = read("src/lib/env.ts");
    expect(env).toMatch(/gstin:\s*null/);
    expect(env).toMatch(/businessHours:\s*null/);
    expect(env).toMatch(/mapsUrl:\s*null/);
    // Customer counts and review counts are also unverified.
    expect(env).toMatch(/customerCount:\s*null/);
    expect(env).toMatch(/reviewCount:\s*null/);
  });

  it("renders a rating only when review data exists", () => {
    // One place decides, so no screen can be talked into faking social proof.
    const money = read("src/lib/money.ts");
    expect(money).toContain("hasRealRating");
    expect(money).toMatch(/count > 0/);
  });
});

describe("the catalogue is the source of truth", () => {
  it("no page hard-codes a product array", () => {
    // The brief was explicit: no `const products = [...]` for production data.
    const banned =
      /const\s+(products|categories|industries|posts|variants)\s*(?::[^=]+)?=\s*\[/;

    const files = ALL_SOURCE.filter((file) => !IS_TEST(file));
    for (const file of files) {
      expect(banned.exec(read(file)), `${file} declares an inline data array`).toBeNull();
    }
  });

  it("no component calls fetch() directly", () => {
    // All API access goes through lib/api/client.ts, so error normalisation and
    // auth cannot be bypassed by one screen.
    const files = sourceFiles("src/components").filter(
      (file) => !IS_TEST(file) && !file.includes("api/client"),
    );
    expect(files.length).toBeGreaterThan(10);

    // One documented exception: SearchBox calls this app's own
    // /api/search-suggestions route rather than the backend, because a client
    // component calling a different origin needs CORS to be right. Anything
    // else reaching for fetch() is bypassing the API client.
    const allowed = new Set(["src/components/search/SearchBox.tsx"]);

    for (const file of files) {
      if (allowed.has(file)) continue;
      const match = /(?<![.\w])fetch\s*\(/.exec(read(file));
      expect(match, `${file} calls fetch() directly`).toBeNull();
    }
  });

  it("never references the old site's asset host", () => {
    for (const file of ALL_SOURCE) {
      const source = read(file);
      expect(source, `${file} references the Wix CDN`).not.toContain("static.wixstatic.com");
      expect(source, `${file} iframes the reference site`).not.toMatch(
        /<iframe[^>]+safetyposterprint/,
      );
    }
  });
});

describe("SEO slugs are preserved verbatim", () => {
  it("does not 'correct' the misspelled Environmental Signages slug", () => {
    // The stored slug is `envirnomental-signages`. Changing it would 404 every
    // existing link and drop the ranking. The display name is corrected instead.
    for (const file of ALL_SOURCE) {
      const asUrl = /["'`]\/category\/environmental-signages/.exec(read(file));
      expect(asUrl, `${file} builds a URL from the corrected slug`).toBeNull();
    }
  });
});

describe("prices are never computed in the browser", () => {
  it("the cart labels its total as an estimate", () => {
    const cart = read("src/components/cart/CartProvider.tsx");
    expect(cart).toContain("isEstimate: true");
    expect(cart).toMatch(/never decides a price/);
  });

  it("never renders a bare zero price as purchasable", () => {
    expect(read("src/components/catalog/primitives.tsx")).toMatch(/Price on request/);
  });
});

describe("dynamic routes are not baked into a build", () => {
  it("every page that reads live catalogue data renders per request", () => {
    // A statically prerendered listing would serve a stale price or a sold-out
    // variant straight out of the build output.
    const dynamicRoutes = [
      "src/app/shop/page.tsx",
      "src/app/category/page.tsx",
      "src/app/category/[slug]/page.tsx",
      "src/app/products/[slug]/page.tsx",
      "src/app/search/page.tsx",
      "src/app/industries/page.tsx",
      "src/app/industries/[slug]/page.tsx",
      "src/app/blog/page.tsx",
      "src/app/blog/[slug]/page.tsx",
      "src/app/msds/page.tsx",
      "src/app/5s/page.tsx",
    ];
    for (const route of dynamicRoutes) {
      expect(read(route), `${route} is not forced dynamic`).toContain(
        'export const dynamic = "force-dynamic"',
      );
    }
  });
});
