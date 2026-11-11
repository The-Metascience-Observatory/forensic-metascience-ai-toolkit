// Defence in depth for the hosted site. Paper content (publisher HTML, JATS,
// spreadsheets) is rendered in these pages, so a page may load and talk to
// this origin only: a script that got in could not fetch one from elsewhere
// or send anything out. Next's own inline bootstrap needs 'unsafe-inline';
// pdf.js needs its worker and wasm. `next dev` needs eval, so the policy is
// the production build's. /api/media sets its own (a sandbox for HTML files).
const CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "media-src 'self' blob:",
  "font-src 'self' data:",
  "worker-src 'self' blob:",
  "connect-src 'self'",
  "frame-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'self'",
].join("; ");
const SECURITY_HEADERS = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "no-referrer" },
  { key: "X-Frame-Options", value: "SAMEORIGIN" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async headers() {
    const rules = [{ source: "/:path*", headers: SECURITY_HEADERS }];
    if (process.env.NODE_ENV === "production") {
      rules.push({ source: "/((?!api/media).*)", headers: [{ key: "Content-Security-Policy", value: CSP }] });
    }
    return rules;
  },
  async redirects() {
    return [
      {
        source: "/images/:project",
        destination: "/project/:project/images",
        permanent: true,
      },
      {
        source: "/images/:project/:item",
        destination: "/project/:project/images/:item",
        permanent: true,
      },
      {
        // The seeded-RNG queue is the first detector queue; the generic route
        // is keyed by the stored producer value.
        source: "/project/:project/rng",
        destination: "/project/:project/detector/rng_track",
        permanent: false,
      },
    ];
  },
  // scripts/serve.mjs points both at this machine's cache, outside Dropbox,
  // through a `.next-cache-<hash>` link in the webapp: Next 16 refuses a
  // distDir or tsconfig outside the project folder.
  distDir: process.env.METASCIENCE_NEXT_DIST || ".next-review",
  typescript: { tsconfigPath: process.env.METASCIENCE_NEXT_TSCONFIG || "tsconfig.json" },
  experimental: { cpus: 2 },
  // Next 16.4 `next dev` writes an AGENTS.md into the project; this repository
  // keeps its agent guidance in its own CLAUDE.md/AGENTS.md.
  agentRules: false,
};

export default nextConfig;
