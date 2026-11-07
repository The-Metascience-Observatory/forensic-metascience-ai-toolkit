/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
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
