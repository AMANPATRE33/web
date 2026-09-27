import type { NextConfig } from "next";

/**
 * Image configuration.
 *
 * The seeded catalogue serves vector placeholders from this app's own `public/`
 * directory, so nothing remote is needed to run locally. Once the real
 * photography is migrated to Supabase Storage, URLs will be absolute and the
 * remote patterns below cover that.
 *
 * `dangerouslyAllowSVG` is deliberately **not** enabled. It would permit
 * optimising arbitrary SVG from any allowed host, which is a script-injection
 * vector unless paired with a strict CSP and `contentDispositionType: attach`.
 * The seed's SVGs are static and same-origin, and `ProductImage` passes
 * `unoptimized` for vector files rather than opening that door.
 */
const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  images: {
    formats: ["image/avif", "image/webp"],
    // Local SVGs are served from /public, which never needs a remote pattern.
    remotePatterns: [
      { protocol: "https", hostname: "**.supabase.co", pathname: "/storage/v1/object/public/**" },
      { protocol: "https", hostname: "**.supabase.in", pathname: "/storage/v1/object/public/**" },
    ],
  },
  // Explicitly ignore build-time Vercel telemetry prompt config in CI.
  experimental: {
    optimizePackageImports: ["lucide-react", "framer-motion"],
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
