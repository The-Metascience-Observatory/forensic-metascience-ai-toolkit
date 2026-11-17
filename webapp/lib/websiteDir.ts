import fs from "node:fs";
import path from "node:path";

import { repoRoot } from "@/lib/python";
import { FINDINGS_JSON } from "@/lib/websiteFinding";

/** The website checkout: METASCIENCE_WEBSITE_DIR, else the nearest
 * `website/metascience-observatory-website` (or `metascience-observatory-website`)
 * holding findings.json beside this repo or beside any folder above it (the
 * toolkit is in AA_forensic_metascience/, the website in website/). Falls back to the sibling path so the
 * error names a concrete location. Server-only (reads the filesystem). */
const WEBSITE_REPO = "metascience-observatory-website";

export function websiteDir(): string {
  const env = (process.env.METASCIENCE_WEBSITE_DIR || "").trim();
  if (env) return path.resolve(env);
  const sibling = path.resolve(repoRoot(), "..", "..", "website", WEBSITE_REPO);
  for (let d = path.resolve(repoRoot(), ".."); ; d = path.dirname(d)) {
    for (const candidate of [path.join(d, "website", WEBSITE_REPO), path.join(d, WEBSITE_REPO)]) {
      if (fs.existsSync(path.join(candidate, FINDINGS_JSON))) return candidate;
    }
    if (path.dirname(d) === d) return sibling;
  }
}
