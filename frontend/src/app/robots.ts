import type { MetadataRoute } from "next";

import { env } from "@/lib/env";

/**
 * robots.txt
 *
 * Account, cart and checkout paths are disallowed because they are per-user
 * pages with no indexable content. They also carry `noindex` in their own
 * metadata; this is belt and braces, since a crawler that ignores meta tags
 * still respects robots.txt.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: [
          "/api/",
          "/account/",
          "/cart",
          "/checkout",
          "/search",
          "/*?*",
        ],
      },
    ],
    sitemap: `${env.siteUrl}/sitemap.xml`,
    host: env.siteUrl,
  };
}
