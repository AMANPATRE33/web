/**
 * Visual QA sweep.
 *
 * Not a unit test. This drives a real Chromium at the five viewports the brief
 * names, on the five routes it names, and checks the things a build cannot:
 * horizontal overflow, console errors, broken images, and whether the Material
 * x Size selector and the cart actually work in a real browser.
 *
 *   npx playwright test qa/visual.spec.ts --reporter=list
 *
 * Screenshots land in `qa/screenshots/`. Requires the API on :8000 and the
 * storefront on :3100 (`npm run build && npm run start -- -p 3100`).
 */

import { expect, test, type ConsoleMessage, type Page } from "@playwright/test";

const BASE = process.env.QA_BASE_URL ?? "http://127.0.0.1:3100";

const VIEWPORTS = [
  { name: "mobile-390", width: 390, height: 844 },
  { name: "mobile-430", width: 430, height: 932 },
  { name: "tablet-768", width: 768, height: 1024 },
  { name: "laptop-1024", width: 1024, height: 800 },
  { name: "desktop-1440", width: 1440, height: 900 },
] as const;

const ROUTES = [
  { name: "home", path: "/" },
  { name: "shop", path: "/shop" },
  { name: "category", path: "/category/electrical-safety" },
  { name: "product", path: "/products/danger-high-voltage" },
  { name: "cart", path: "/cart" },
] as const;

/**
 * Fail fast if the server is serving a stale build.
 *
 * `next start` keeps serving after `next build` rewrites `.next`, and the HTML
 * it emits can reference chunk hashes that no longer exist. The result is a run
 * of misleading failures - missing CSS utilities, 500s on chunks, "images are
 * broken" - that look like product bugs and are not. This was observed
 * directly: a green suite went to 12/39 purely from a stale server.
 *
 * So the first thing the suite does is prove the server is actually serving the
 * build on disk, and say so explicitly if not.
 */
test("the server is serving the current build", async ({ page, request }) => {
  const stale: string[] = [];

  page.on("response", (response) => {
    if (response.url().includes("/_next/static/") && response.status() >= 400) {
      stale.push(`${response.status()} ${response.url()}`);
    }
  });

  await page.goto(BASE, { waitUntil: "networkidle" });

  // If Tailwind's utilities are not applied, the design system is not loaded.
  const styling = await page.evaluate(() => {
    const first = document.querySelector("main");
    return {
      sheets: document.styleSheets.length,
      rules: document.styleSheets[0]?.cssRules.length ?? 0,
      // A card image with `w-full` must not render at its intrinsic width.
      imageOverflows: Array.from(document.querySelectorAll("img")).some(
        (image) => image.getBoundingClientRect().width > window.innerWidth,
      ),
      hasMain: first !== null,
    };
  });

  expect(
    stale,
    "The server returned errors for build assets. It is almost certainly " +
      "serving a stale build: run `npm run build` and restart the server.",
  ).toEqual([]);

  expect(styling.hasMain, "the page rendered no <main>").toBe(true);
  expect(styling.sheets, "no stylesheet loaded - the CSS build is missing").toBeGreaterThan(0);
  expect(styling.rules, "the stylesheet has almost no rules").toBeGreaterThan(50);
  expect(
    styling.imageOverflows,
    "an image is wider than the viewport, so Tailwind's sizing utilities are " +
      "not being applied - a stale or partial CSS build",
  ).toBe(false);

  // Prove the API is up too, so a later failure is unambiguous.
  const health = await request.get("http://127.0.0.1:8000/health");
  expect(health.ok(), "the backend is not answering on :8000").toBe(true);
});

test.describe("visual QA", () => {
  for (const viewport of VIEWPORTS) {
    test.describe(viewport.name, () => {
      test.use({ viewport: { width: viewport.width, height: viewport.height } });

      for (const route of ROUTES) {
        test(`${route.name} has no horizontal overflow`, async ({ page }) => {
          const errors = collectConsoleErrors(page);
          await page.goto(`${BASE}${route.path}`, { waitUntil: "networkidle" });

          const overflow = await measureOverflow(page);
          expect(
            overflow.overflow,
            `${route.path} at ${viewport.width}px overflows by ${overflow.overflow}px. ` +
              `Element: ${overflow.widest}`,
          ).toBe(0);

          expect(errors, `console errors on ${route.path}`).toEqual([]);
        });
      }    });
  }

  test.describe("desktop-1440 content", () => {
    test.use({ viewport: { width: 1440, height: 900 } });

    test("homepage shows real catalogue data, not placeholders", async ({ page }) => {
      await page.goto(BASE, { waitUntil: "networkidle" });

      // Hero copy, verbatim from the brief.
      await expect(
        page.getByRole("heading", { level: 1, name: "Safety Signage That Speaks Before You Do." }),
      ).toBeVisible();
      await expect(page.getByRole("link", { name: "Shop Safety Products" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Request Bulk Quote" }).first()).toBeVisible();

      // Category grid from the database: 18 of them.
      const categoryLinks = page.locator('a[href^="/category/"]');
      expect(await categoryLinks.count()).toBeGreaterThan(15);

      // A real product from the seed, with a real price.
      await expect(page.getByText("Danger High Voltage").first()).toBeVisible();
      await expect(page.locator("text=Rs.").first()).toBeVisible();

      // No zero price anywhere.
      expect(await page.getByText("Rs.0").count()).toBe(0);
    });

    test("every image on the homepage and shop actually loaded", async ({ page }) => {
      const httpFailures: string[] = [];
      page.on("response", (response) => {
        if (response.url().includes("/seed/") && response.status() >= 400) {
          httpFailures.push(`${response.status()} ${response.url()}`);
        }
      });

      for (const path of ["/", "/shop", "/category/electrical-safety"]) {
        await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });

        // Scroll the full page first. Below-the-fold images are `loading="lazy"`,
        // so they are legitimately unrequested until they approach the
        // viewport - checking `naturalWidth` without scrolling reports them as
        // broken, which is a false positive about correct behaviour.
        await page.evaluate(async () => {
          for (let y = 0; y < document.body.scrollHeight; y += 600) {
            window.scrollTo(0, y);
            await new Promise((resolve) => setTimeout(resolve, 50));
          }
          window.scrollTo(0, 0);
        });
        await page.waitForLoadState("networkidle");

        const broken = await page.evaluate(() =>
          Array.from(document.images)
            .filter((image) => image.complete && image.naturalWidth === 0)
            .map((image) => image.currentSrc || image.src),
        );
        // `complete && naturalWidth === 0` is a genuine decode failure. A
        // not-yet-complete image is just lazy loading, and is excluded.
        expect(broken, `broken images on ${path}`).toEqual([]);
      }

      expect(httpFailures, "an image request returned an error status").toEqual([]);
    });

    test("no text is clipped or overlapping at 1440px", async ({ page }) => {
      await page.goto(`${BASE}/products/danger-high-voltage`, { waitUntil: "networkidle" });

      const clipped = await page.evaluate(() => {
        const problems: string[] = [];
        for (const element of Array.from(document.querySelectorAll("h1, h2, h3, p, a, button, span"))) {
          const style = getComputedStyle(element);
          if (style.overflow === "hidden" && style.textOverflow !== "ellipsis") {
            // Intentional single-line truncation is fine.
            if (style.whiteSpace === "nowrap") continue;
          }
          if (element.scrollHeight > element.clientHeight + 2 && style.overflowY === "hidden") {
            problems.push(`${element.tagName}.${element.className}`.slice(0, 120));
          }
        }
        return problems.slice(0, 10);
      });
      expect(clipped).toEqual([]);
    });
  });

  test.describe("mobile-390 interaction", () => {
    test.use({ viewport: { width: 390, height: 844 } });

    // No manual storage clearing. Playwright gives every test its own browser
    // context, so `localStorage` is already isolated. An earlier version added
    // an `addInitScript` to clear it, which was both unnecessary and actively
    // harmful: init scripts re-run on *every* navigation, so the cart was wiped
    // by the time the cart page loaded.

    test("the header drawer opens, navigates and closes", async ({ page }) => {
      const errors = collectConsoleErrors(page);
      await page.goto(`${BASE}/shop`, { waitUntil: "networkidle" });

      const menu = page.getByRole("button", { name: "Open menu" });
      await expect(menu).toBeVisible();
      await menu.click();

      const dialog = page.getByRole("dialog");
      await expect(dialog).toBeVisible();
      await expect(dialog.getByRole("link", { name: "Industries" })).toBeVisible();
      await expect(dialog.getByRole("link", { name: "All products" })).toBeVisible();

      // Escape closes it, and the drawer must not trap the page.
      await page.keyboard.press("Escape");
      await expect(dialog).toBeHidden();

      await menu.click();
      await dialog.getByRole("link", { name: "Industries" }).click();
      await expect(page).toHaveURL(/\/industries$/);
      await expect(page.getByRole("dialog")).toBeHidden();
      expect(errors).toEqual([]);
    });

    test("the mobile filter drawer applies a material filter", async ({ page }) => {
      await page.goto(`${BASE}/shop`, { waitUntil: "networkidle" });

      const trigger = page.getByRole("button", { name: /Filters/ });
      await expect(trigger).toBeVisible();
      await trigger.click();

      const sheet = page.getByRole("dialog");
      await sheet.getByRole("checkbox", { name: /3MM ACP/ }).check();
      await sheet.getByRole("button", { name: "Show results" }).click();

      await expect(page).toHaveURL(/material=/);
      await expect(sheet).toBeHidden();
      // The grid reflects the filter.
      await expect(page.getByRole("button", { name: /Filters/ })).toContainText("1");
    });

    test("the Material x Size selector works on a 390px screen", async ({ page, request }) => {
      const errors = collectConsoleErrors(page);
      await page.goto(`${BASE}/products/danger-high-voltage`, { waitUntil: "networkidle" });

      const materialGroup = page.getByRole("radiogroup", { name: "Material" });
      const sizeGroup = page.getByRole("radiogroup", { name: "Size" });
      await expect(materialGroup).toBeVisible();
      await expect(sizeGroup).toBeVisible();

      // The expected SKU is read from the API rather than hard-coded, so this
      // test breaks if the seed changes the matrix, and passes only if the
      // frontend is faithfully showing what the database says.
      //
      // Fetched through Playwright's `request` fixture, not `page.evaluate`:
      // an in-page fetch to :8000 is a cross-origin request and fails CORS,
      // which has nothing to do with what is being tested.
      const apiResponse = await request.get(
        "http://127.0.0.1:8000/api/v1/products/danger-high-voltage",
      );
      const product = (await apiResponse.json()) as {
        variants: Array<{ sku: string; attributes: Record<string, string> }>;
      };
      const expectedSku = product.variants.find(
        (variant) =>
          variant.attributes.Material === "ECO VINYL STICKER" &&
          variant.attributes.Size === "18x24",
      )?.sku;
      expect(expectedSku, "seeded catalogue has no vinyl 18x24 variant").toBeTruthy();

      // Price before.
      const priceBefore = await page.locator("text=/^Rs\\.[\\d,]+$/").first().innerText();

      // Choose 18x24, which every material is made in.
      await sizeGroup.getByRole("radio", { name: /18x24/ }).click();
      await page.getByRole("radio", { name: /ECO VINYL STICKER/ }).click();

      // Price and SKU both changed, and the SKU is the one the database holds.
      await expect(page.getByText(`SKU ${expectedSku}`, { exact: false })).toBeVisible();
      const priceAfter = await page.locator("text=/^Rs\\.[\\d,]+$/").first().innerText();
      expect(priceAfter).not.toBe(priceBefore);

      // Every seeded product carries a *complete* material x size matrix, so no
      // size is disabled by the choice of material here. Verified against the
      // API rather than assumed, so that when the import pipeline starts
      // producing sparse matrices this fails loudly and the disabled-combination
      // assertions below can be switched on deliberately.
      const sizes = product.variants.map((variant) => variant.attributes.Size);
      const materials = product.variants.map((variant) => variant.attributes.Material);
      const uniqueSizes = [...new Set(sizes)];
      const uniqueMaterials = [...new Set(materials)];
      const isComplete = product.variants.length === uniqueSizes.length * uniqueMaterials.length;

      if (isComplete) {
        await expect(sizeGroup.getByRole("radio", { name: /24x36/ })).toBeEnabled();
      } else {
        // Sparse matrix: the combination the data says does not exist must be
        // disabled rather than selectable-then-failing.
        await expect(sizeGroup.getByRole("radio", { name: /48x96/ })).toBeDisabled();
      }

      await page.screenshot({ path: "qa/screenshots/product-mobile-390.png" });

      // Add to cart is enabled and produces a line with the right identity.
      await page.getByRole("button", { name: "Add to cart" }).click();
      await expect(page.getByRole("status")).toContainText("ECO VINYL STICKER / 18x24");

      await page.getByRole("link", { name: "Cart" }).click();
      await expect(page).toHaveURL(/\/cart$/);
      await expect(page.getByText("ECO VINYL STICKER")).toBeVisible();
      await expect(page.getByText("18x24 in.")).toBeVisible();
      await page.screenshot({ path: "qa/screenshots/cart-mobile-390.png" });
      expect(errors).toEqual([]);
    });

    test("the cart badge reflects an add", async ({ page }) => {
      await page.goto(`${BASE}/products/danger-high-voltage`, { waitUntil: "networkidle" });
      await page.getByRole("button", { name: "Add to cart" }).click();

      // The badge lives inside the cart link, but the link's own aria-label is
      // "Cart" (a fixed, predictable accessible name), so the count is asserted
      // as text within that link rather than as part of its name.
      const cartLink = page.getByRole("link", { name: "Cart" });
      await expect(cartLink).toBeVisible();
      await expect(cartLink.getByText("1 item in cart")).toBeAttached();
    });

    test("the cart opens with the right line and quantity controls", async ({ page }) => {
      await page.goto(`${BASE}/products/danger-high-voltage`, { waitUntil: "networkidle" });
      await page.getByRole("button", { name: "Add to cart" }).click();

      await page.goto(`${BASE}/cart`, { waitUntil: "networkidle" });
      const line = page.locator("li").filter({ hasText: "Danger High Voltage" }).first();
      await expect(line).toBeVisible();
      await expect(line.getByText(/SPP-ELS/)).toBeVisible();

      // The quantity block renders "Rs.180 x 1" then the line total. The *total*
      // is the figure under test, and reading only it avoids having to parse the
      // "x N" form whose digits would otherwise run together.
      const total = line.locator("p").filter({ hasText: /^Rs\./ }).nth(1);
      const rupees = (text: string) => Number.parseFloat(text.replace(/[^\d.]/g, ""));

      const before = rupees(await total.innerText());
      expect(before).toBeGreaterThan(0);

      await page.getByRole("button", { name: /Increase quantity/ }).first().click();

      // Doubling the quantity doubles the line total. Compared numerically so
      // the test does not reimplement Indian digit grouping in order to check it.
      await expect.poll(async () => rupees(await total.innerText())).toBe(before * 2);
      await expect(line).toContainText("× 2");

      await page.getByRole("button", { name: /Remove .* from cart/ }).first().click();
      await expect(page.getByText("Your cart is empty")).toBeVisible();
    });
  });

  test.describe("accessibility", () => {
    test.use({ viewport: { width: 1440, height: 900 } });

    test("every page has exactly one h1 and a skip link", async ({ page }) => {
      for (const path of ["/", "/shop", "/products/danger-high-voltage", "/industries", "/blog"]) {
        await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
        expect(await page.locator("h1").count(), `h1 count on ${path}`).toBe(1);
        await expect(page.getByRole("link", { name: "Skip to main content" })).toHaveCount(1);
      }
    });

    test("the cart icon is labelled and the variant groups are radiogroups", async ({
      page,
    }) => {
      await page.goto(`${BASE}/products/danger-high-voltage`, { waitUntil: "networkidle" });
      await expect(page.getByRole("radiogroup", { name: "Material" })).toBeVisible();
      await expect(page.getByRole("radiogroup", { name: "Size" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Cart" })).toHaveCount(1);
    });

    test("keyboard focus is visible on the primary navigation", async ({ page }) => {
      await page.goto(BASE, { waitUntil: "networkidle" });
      await page.keyboard.press("Tab");
      const focused = await page.evaluate(() => document.activeElement?.textContent?.trim());
      // The first tab stop is the skip link.
      expect(focused).toBe("Skip to main content");
    });
  });

  test.describe("SEO output", () => {
    test.use({ viewport: { width: 1440, height: 900 } });

    test("the product page emits Product and BreadcrumbList schema", async ({ page }) => {
      await page.goto(`${BASE}/products/danger-high-voltage`, { waitUntil: "networkidle" });
      const blocks = await readJsonLd(page);
      expect(blocks.some((block) => block["@type"] === "Product")).toBe(true);
      expect(blocks.some((block) => block["@type"] === "BreadcrumbList")).toBe(true);

      const product = blocks.find((block) => block["@type"] === "Product");
      expect(product, "no Product block was emitted").toBeDefined();

      const offers = product!.offers as {
        priceCurrency: string;
        offers: unknown[];
      };
      // One offer per variant, because a board with a size and material matrix
      // is not a single-price product.
      expect(offers.offers.length).toBeGreaterThan(1);
      expect(offers.priceCurrency).toBe("INR");
    });

    test("the sitemap lists products, categories and industries", async ({ request }) => {
      const response = await request.get(`${BASE}/sitemap.xml`);
      expect(response.status()).toBe(200);
      const xml = await response.text();
      expect(xml).toContain("/products/danger-high-voltage");
      expect(xml).toContain("/category/electrical-safety");
      expect(xml).toContain("/industries/manufacturing");
      // > 100 products means it paged past the first API page.
      expect((xml.match(/<loc>[^<]*\/products\//g) ?? []).length).toBeGreaterThan(100);
    });

    test("robots.txt disallows account and cart", async ({ request }) => {
      const xml = await (await request.get(`${BASE}/robots.txt`)).text();
      expect(xml).toContain("Disallow: /account/");
      expect(xml).toContain("Disallow: /cart");
      expect(xml).toContain("Sitemap:");
    });
  });
});

// ---------------------------------------------------------------------------

/**
 * Real horizontal overflow.
 *
 * The naive check - "does any element's right edge exceed the viewport?" - is
 * wrong, and it reports a false failure on every page. The header's category
 * rail is an `overflow-x: auto` strip holding all 18 categories, so its links
 * *deliberately* extend past the viewport and are clipped by the scroller. Those
 * are not layout bugs; they are the feature.
 *
 * So this measures the two things that actually mean "the page is broken":
 *
 *   1. the document itself can be scrolled horizontally, and
 *   2. an element overflows *without* an ancestor that clips or scrolls it.
 *
 * The second catches a real bug the first misses: a wide unbreakable child
 * inside a `hidden`-overflow parent looks fine but clips its content, so
 * `hidden` is deliberately not treated as a valid excuse.
 */
async function measureOverflow(page: Page): Promise<{ overflow: number; widest: string }> {
  return page.evaluate(() => {
    const viewWidth = document.documentElement.clientWidth;

    // 1. Can the page actually be panned sideways?
    const before = window.scrollX;
    window.scrollTo(10_000, window.scrollY);
    const documentPans = window.scrollX > before + 1;
    window.scrollTo(before, window.scrollY);

    // 2. Anything that overflows with no ancestor clipping it.
    //
    //    An ancestor with `overflow: auto|scroll` is a deliberate rail and is
    //    always accepted. An ancestor with `overflow: hidden` is accepted *only*
    //    when it is deliberately truncating - it declares `text-overflow:
    //    ellipsis` or a `-webkit-line-clamp`. That distinction matters:
    //    `truncate` on a long product name is correct design, whereas a
    //    `hidden` ancestor that silently cuts text off is a bug. `hidden` on its
    //    own is therefore treated as a failure.
    const escapes: Array<{ excess: number; label: string }> = [];

    for (const element of Array.from(document.querySelectorAll<HTMLElement>("body *"))) {
      const rect = element.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) continue;
      if (rect.right <= viewWidth + 1) continue;

      let ancestor = element.parentElement;
      let clipped = false;
      while (ancestor) {
        const style = getComputedStyle(ancestor);
        if (style.overflowX === "auto" || style.overflowX === "scroll") {
          clipped = true;
          break;
        }
        if (style.overflowX === "hidden" || style.overflowY === "hidden") {
          // `className` is an `SVGAnimatedString`, not a string, on SVG
          // elements, so it has to be coerced before any string method is used.
          const className =
            typeof ancestor.className === "string" ? ancestor.className : "";
          const truncates =
            style.textOverflow === "ellipsis" ||
            style.webkitLineClamp !== "none" ||
            className.includes("line-clamp");
          if (truncates) {
            clipped = true;
            break;
          }
        }
        ancestor = ancestor.parentElement;
      }
      if (clipped) continue;

      escapes.push({
        excess: rect.right - viewWidth,
        label: `${element.tagName.toLowerCase()}.${String(element.className).slice(0, 90)}`,
      });
    }

    escapes.sort((a, b) => b.excess - a.excess);
    const worst = escapes[0];

    return {
      overflow: documentPans ? Math.max(worst?.excess ?? 1, 1) : Math.round(worst?.excess ?? 0),
      widest: worst?.label ?? "",
    };
  });
}

function collectConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (message: ConsoleMessage) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error: Error) => errors.push(`pageerror: ${error.message}`));
  return errors;
}

async function readJsonLd(page: Page): Promise<Array<Record<string, unknown>>> {
  return page.evaluate(() =>
    Array.from(document.querySelectorAll('script[type="application/ld+json"]')).map(
      (node) => JSON.parse(node.textContent ?? "{}") as Record<string, unknown>,
    ),
  );
}
