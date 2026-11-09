import path from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Offline unit and component tests. Pure modules run under Node; a component
// test opts into jsdom with `// @vitest-environment jsdom` at its top. The
// Playwright scripts (canvas, image loading, pdf.js, GIF encoding, the
// security audit) and the live-server checks stay as plain scripts under
// `npm run test:components` / `test:*`; see README "Checks".
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname),
      // Server modules carry `import "server-only"`, which throws outside a
      // server bundle; tests get an empty module instead.
      "server-only": path.resolve(import.meta.dirname, "test/stubs/server-only.js"),
    },
  },
  test: {
    include: ["test/**/*.test.{ts,tsx,mjs}"],
    setupFiles: ["test/setup.ts"],
    environment: "node",
    testTimeout: 30_000,
    hookTimeout: 30_000,
  },
});
