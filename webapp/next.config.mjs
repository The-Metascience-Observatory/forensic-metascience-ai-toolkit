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
  // scripts/serve.mjs points both at this machine's cache, outside Dropbox.
  distDir: process.env.METASCIENCE_NEXT_DIST || ".next-review",
  typescript: { tsconfigPath: process.env.METASCIENCE_NEXT_TSCONFIG || "tsconfig.json" },
  experimental: { cpus: 2 },
};

export default nextConfig;
