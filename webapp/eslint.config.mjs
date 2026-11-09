import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

export default defineConfig([
  globalIgnores([".next*/**", "node_modules/**", "public/**", "next-env.d.ts", "tsconfig.tsbuildinfo"]),
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // Media (panel crops, PDFs, thumbnails) is streamed by /api/media with
      // byte ranges, ETags and hash checks; next/image cannot optimise it and
      // would add a second cache. Plain <img> is the design.
      "@next/next/no-img-element": "off",
      // Burn-down list (2026-11-09, first lint run: 192 refs, 38
      // set-state-in-effect, 62 any, 18 exhaustive-deps). These are
      // warnings until the component splits in the restructure resolve
      // them file by file; new code must not add to the count.
      "react-hooks/refs": "warn",
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/immutability": "warn",
      "react-hooks/exhaustive-deps": "warn",
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/no-unused-vars": ["error", {
        argsIgnorePattern: "^_", varsIgnorePattern: "^_", caughtErrors: "none",
      }],
    },
  },
  {
    // lib/ is the layer app/ builds on; it must not reach back up (the
    // image types used to live in app/images/lib.ts and were imported by
    // five lib modules). Enforced here, not by convention.
    files: ["lib/**/*.ts", "lib/**/*.tsx"],
    rules: {
      "no-restricted-imports": ["error", {
        patterns: [{ group: ["@/app/*", "**/app/*", "../app/*"],
                     message: "lib/ must not import from app/; move the shared piece into lib/." }],
      }],
    },
  },
  {
    // Test scripts: the Playwright harness renders through a deliberate
    // `ReactDOM.render` shim (test/reactGlobals.mjs), and fixtures name
    // fields they do not read.
    files: ["test/**"],
    rules: {
      "react/no-deprecated": "off",
      "react/no-render-return-value": "off",
      "@typescript-eslint/no-unused-vars": "warn",
      "@typescript-eslint/no-explicit-any": "off",
    },
  },
]);
