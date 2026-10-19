/** An image finding reported on PubPeer, as one entry of the Observatory
 * website's `app/forensic-metascience-ai-toolkit/findings/image-findings/findings.json`.
 * The shape matches the entries already there; the page renders it as is. */
export type WebsiteCitation = {
  authors: string; title: string; journal: string;
  volume: string | null; issue: string | null; pages: string | null;
  year: number | string | null; url: string;
};
export type WebsiteFinding = {
  id: string; doi: string; citation: WebsiteCitation;
  pubpeerUrl: string; submitted: string; summary: string;
  image: { src: string; width: number; height: number; alt: string };
};

export const FINDINGS_JSON = "app/forensic-metascience-ai-toolkit/findings/image-findings/findings.json";
export const IMAGE_DIR = "public/assets/forensic-metascience-ai-toolkit/image-findings";
export const IMAGE_URL = "/assets/forensic-metascience-ai-toolkit/image-findings";

/** A PubPeer publication link, optionally to one comment (`#12`). Word's
 * meaningless `#null` fragment is dropped, as the page's README records.
 * Returns null for anything that is not a pubpeer.com publication page. */
export function normalisePubpeerUrl(raw: string): string | null {
  let url: URL;
  try { url = new URL(raw.trim()); } catch { return null; }
  if (url.protocol !== "https:" && url.protocol !== "http:") return null;
  if (!/^(www\.)?pubpeer\.com$/i.test(url.hostname)) return null;
  const m = url.pathname.match(/^\/publications\/([0-9A-Fa-f]{10,})\/?$/);
  if (!m) return null;
  const hash = url.hash && url.hash !== "#null" ? url.hash : "";
  return `https://pubpeer.com/publications/${m[1].toUpperCase()}${hash}`;
}

const slug = (s: string) => s.normalize("NFKD").replace(/[̀-ͯ]/g, "")
  .toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");

/** `family-year` of the first author, like the existing ids (`fu-2012`);
 * `-b`, `-c`, ... when that id is taken. */
export function findingId(citation: Pick<WebsiteCitation, "authors" | "year">, taken: Iterable<string>): string {
  const first = (citation.authors || "").split(";")[0].trim();
  const family = first.split(/\s+/).filter(Boolean).pop() || "finding";
  const base = [slug(family) || "finding", citation.year ? String(citation.year) : ""].filter(Boolean).join("-");
  const used = new Set(taken);
  if (!used.has(base)) return base;
  for (let i = 1; i < 26; i++) {
    const id = `${base}-${String.fromCharCode(97 + i)}`;
    if (!used.has(id)) return id;
  }
  return `${base}-${Date.now()}`;
}

/** Width and height from a PNG's IHDR chunk; null when it is not a PNG. */
export function pngSize(bytes: Uint8Array): { width: number; height: number } | null {
  const sig = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
  if (bytes.length < 24 || sig.some((b, i) => bytes[i] !== b)) return null;
  if (String.fromCharCode(...bytes.slice(12, 16)) !== "IHDR") return null;
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const width = view.getUint32(16), height = view.getUint32(20);
  return width && height ? { width, height } : null;
}

const text = (v: unknown) => v == null || v === "" ? null : String(v).trim() || null;

/** The citation block from `fetch_metadata_from_doi` output -- the same call
 * the website's README names -- or null when it lacks a title or authors. */
export function citationFrom(meta: Record<string, unknown> | null | undefined, doi: string): WebsiteCitation | null {
  if (!meta) return null;
  const title = text(meta.title), authors = text(meta.authors);
  if (!title || !authors) return null;
  const year = meta.year == null || meta.year === "" ? null : Number.isFinite(Number(meta.year)) ? Number(meta.year) : String(meta.year);
  return { authors, title, journal: text(meta.journal) || "", volume: text(meta.volume), issue: text(meta.issue),
    pages: text(meta.pages), year, url: text(meta.url) || `https://doi.org/${doi}` };
}

/** Today in the reviewer's calendar, as the ISO date the page expects. */
export const isoDate = (d = new Date()) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
