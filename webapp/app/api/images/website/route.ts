import fs from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";

import { errMsg } from "@/lib/err";
import { rejectCrossOrigin } from "@/lib/mutation";
import { pyJson, pyModuleJson, repoRoot } from "@/lib/python";
import { workbench } from "@/lib/workbench";
import { OVERRIDE_LOG, overrideConfirmed, overrideLine } from "@/lib/embargoOverride";
import { FINDINGS_JSON, IMAGE_DIR, IMAGE_URL, citationFrom, findingId, normalisePubpeerUrl, pngSize,
  type WebsiteFinding } from "@/lib/websiteFinding";

export const dynamic = "force-dynamic";

const MAX_PNG_BYTES = 25 * 1024 * 1024;
const EMBARGO_MARKER = "EMBARGO.json";

/** The website checkout: METASCIENCE_WEBSITE_DIR, else the sibling of this repo. */
function websiteDir(): string {
  const env = (process.env.METASCIENCE_WEBSITE_DIR || "").trim();
  return path.resolve(env || path.join(repoRoot(), "..", "metascience_observatory_website"));
}

/** The first EMBARGO.json at or above the paper folder. A corpus under a
 * selection embargo carries one at its root, and nothing from it may be
 * published (history_publication.assert_not_embargoed). */
function embargoMarker(dir: string): string | null {
  for (let d = path.resolve(dir); ; d = path.dirname(d)) {
    const marker = path.join(d, EMBARGO_MARKER);
    if (fs.existsSync(marker)) return marker;
    if (path.dirname(d) === d) return null;
  }
}

const fail = (error: string, status = 400) => NextResponse.json({ error }, { status });

/** Add a PubPeer-reported image finding to the website's image-findings page:
 *  the summary figure PNG into public/assets, one entry appended to
 *  findings.json. Writes the local website checkout only -- committing and
 *  deploying stay with the person, so nothing here reaches the public site. */
export async function POST(req: Request) {
  const rejected = rejectCrossOrigin(req); if (rejected) return rejected;
  let form: FormData;
  try { form = await req.formData(); } catch { return fail("expected multipart form data"); }
  const field = (k: string) => { const v = form.get(k); return typeof v === "string" ? v.trim() : ""; };
  const project = field("project"), dir = field("dir");
  const summary = field("summary").replace(/\s+/g, " ");
  const alt = field("alt") || "Annotated comparison with the matching regions outlined.";
  const submitted = field("submitted");
  const pubpeerUrl = normalisePubpeerUrl(field("pubpeerUrl"));
  const image = form.get("image");
  if (!project || !dir) return fail("project and dir required");
  if (!pubpeerUrl) return fail("That is not a PubPeer publication link (https://pubpeer.com/publications/…).");
  if (!summary) return fail("The comment text is empty.");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(submitted)) return fail("The submission date must be YYYY-MM-DD.");
  if (!(image instanceof Blob) || image.size > MAX_PNG_BYTES) return fail("A summary-figure PNG (at most 25 MB) is required.");
  const bytes = new Uint8Array(await image.arrayBuffer());
  const size = pngSize(bytes);
  if (!size) return fail("The image is not a PNG.");

  const site = websiteDir();
  const findingsPath = path.join(site, FINDINGS_JSON);
  if (!fs.existsSync(findingsPath)) return fail(`No website checkout at ${site} (set METASCIENCE_WEBSITE_DIR).`, 500);

  let paperDir: string;
  try {
    const target = await workbench("reveal_target", { project, dir, component: "image_forensics" });
    paperDir = String(target.directory);
  } catch (e) { return fail(`Could not find the paper folder: ${errMsg(e)}`, 404); }
  const marker = embargoMarker(paperDir);
  // Lifted only by a typed confirmation, checked HERE; one finding per request.
  if (marker && !overrideConfirmed(field("embargoOverride"))) {
    return NextResponse.json({ error: `Refused: ${marker} marks this corpus as under a selection embargo, so nothing from it may be published.`,
      code: "embargo", marker }, { status: 403 });
  }

  let doi: string, citation: WebsiteFinding["citation"] | null;
  try {
    const local = await pyJson(["fetch-metadata", "--offline", paperDir], { timeoutMs: 60_000 }) as Record<string, unknown>;
    doi = String(local?.doi || "").trim();
    if (!doi) return fail("This paper has no DOI on record, so it cannot be cited on the website.", 422);
    const meta = await pyModuleJson("forensic_metascience_ai_toolkit.fetch_metadata_from_doi", [doi], { timeoutMs: 90_000 }) as Record<string, unknown>;
    citation = citationFrom(meta, doi);
  } catch (e) { return fail(`Citation lookup failed: ${errMsg(e)}`, 502); }
  if (!citation) return fail(`The DOI APIs returned no title or authors for ${doi}.`, 502);

  // Read-modify-write with synchronous calls only, so two requests cannot interleave.
  let findings: WebsiteFinding[];
  try { findings = JSON.parse(fs.readFileSync(findingsPath, "utf8")); }
  catch (e) { return fail(`Could not read ${findingsPath}: ${errMsg(e)}`, 500); }
  if (!Array.isArray(findings)) return fail(`${findingsPath} is not a list.`, 500);
  const existing = findings.find(f => String(f.doi).toLowerCase() === doi.toLowerCase());
  if (existing) return fail(`This paper is already on the website as "${existing.id}". Edit findings.json to change that entry.`, 409);
  const taken = new Set(findings.map(f => f.id));
  const imageDir = path.join(site, IMAGE_DIR);
  let id = findingId(citation, taken);
  while (fs.existsSync(path.join(imageDir, `${id}.png`))) { taken.add(id); id = findingId(citation, taken); }

  // The override is recorded before anything is written to the website: if the
  // record cannot be kept, nothing is published.
  if (marker) {
    try {
      fs.appendFileSync(path.join(path.dirname(marker), OVERRIDE_LOG),
        overrideLine({ project, dir, doi, website_id: id, marker }));
    } catch (e) { return fail(`Could not record the embargo override, so nothing was published: ${errMsg(e)}`, 500); }
  }
  const entry: WebsiteFinding = {
    id, doi, citation, pubpeerUrl, submitted, summary,
    image: { src: `${IMAGE_URL}/${id}.png`, width: size.width, height: size.height, alt },
  };
  const pngPath = path.join(imageDir, `${id}.png`);
  try {
    fs.mkdirSync(imageDir, { recursive: true });
    fs.writeFileSync(pngPath, bytes, { flag: "wx" });
    const tmp = `${findingsPath}.${process.pid}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify([...findings, entry], null, 2) + "\n");
    fs.renameSync(tmp, findingsPath);
  } catch (e) {
    try { fs.rmSync(pngPath, { force: true }); } catch { /* best effort */ }
    return fail(`Writing the website files failed: ${errMsg(e)}`, 500);
  }
  return NextResponse.json({
    id, doi, website: site, ...(marker ? { embargoOverridden: marker } : {}),
    files: [path.relative(site, findingsPath), path.relative(site, pngPath)],
    page: `/forensic-metascience-ai-toolkit/findings/image-findings#${id}`,
    entry,
  });
}
