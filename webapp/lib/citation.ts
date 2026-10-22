/** Keep in lockstep with `paper_metadata.first_author` (pinned there). */
export function displayFirstAuthor(name: string | null | undefined): string {
  if (!name) return "";
  const s = name.trim();
  if (!s) return "";
  if (s.includes(";")) return s.split(";")[0].trim();
  const parts = s.split(",").map((p) => p.trim()).filter(Boolean);
  if (parts.length >= 3) return parts[0];
  if (parts.length === 2 && parts[1].split(/\s+/).length >= 2) return parts[0];
  return s;
}

/** Keep in lockstep with `paper_metadata.citation_bits` (pinned there). */
export function citationParts(p: {
  journal?: string | null;
  volume?: string | null;
  issue?: string | null;
  year?: string | number | null;
}): { journal: string; loc: string; year: string } {
  const journal = (p.journal || "").trim();
  const volume = String(p.volume ?? "").trim();
  const issue = String(p.issue ?? "").trim();
  const year = p.year == null || p.year === "" ? "" : String(p.year);
  const loc = volume && issue ? `${volume}(${issue})`
    : volume || (issue ? `(${issue})` : "");
  return { journal, loc, year };
}

export function citationLine(p: {
  journal?: string | null;
  volume?: string | null;
  issue?: string | null;
  year?: string | number | null;
}): string {
  const { journal, loc, year } = citationParts(p);
  return [journal, loc, year ? `(${year})` : ""].filter(Boolean).join(" ");
}

/** A bare `10.x/y`, or null when the input is not a DOI we can use.
 *  Accepts a full doi.org URL and strips it. Shared so every surface that
 *  builds a link from a DOI agrees on what counts as one. */
export function normalizeDoi(doi: string | null | undefined): string | null {
  let d = (doi || "").trim();
  if (!d) return null;
  d = d.replace(/^https?:\/\/(dx\.)?doi\.org\//i, "");
  return d.toLowerCase().startsWith("10.") ? d : null;
}

/** `doi.org/10.x/y` → https://doi.org/10.x/y. Null when we have no DOI. */
export function doiLink(doi: string | null | undefined): { href: string; label: string } | null {
  const d = normalizeDoi(doi);
  if (!d) return null;
  return { href: `https://doi.org/${d}`, label: `doi.org/${d}` };
}

/** PubPeer's DOI SEARCH for this paper. Null when we have no DOI.
 *
 *  A SEARCH, not a thread link, and the distinction is the point. A thread
 *  URL on a paper record is a fact -- somebody posted about this paper. This
 *  is a lookup: it answers "has anyone posted?", and an empty result page is
 *  not evidence the paper is clean, only that this search found nothing. The
 *  label says "search" so the link cannot be read as the former.
 *
 *  `encodeURIComponent` is what turns the DOI's slash into `%2F`; PubPeer's
 *  search does not match a raw slash reliably. */
export function pubpeerSearchLink(
  doi: string | null | undefined,
): { href: string; label: string } | null {
  const d = normalizeDoi(doi);
  if (!d) return null;
  return {
    href: `https://pubpeer.com/search?q=${encodeURIComponent(d)}`,
    label: "PubPeer search",
  };
}

/** A recorded publication URL takes precedence over the DOI search fallback. */
export function pubpeerLink(
  doi: string | null | undefined,
  publicationUrl?: string | null,
  title?: string | null,
) {
  if (publicationUrl && /^https:\/\/pubpeer\.com\/publications\/[a-z0-9]+\/?$/i.test(publicationUrl)) {
    return { href: publicationUrl, label: "PubPeer page" };
  }
  const bySearch = pubpeerSearchLink(doi);
  if (bySearch) return bySearch;
  // A paper with no DOI (some journals issue none) can still be looked up by
  // its title. Weaker than a DOI match, so the label says so.
  const t = (title || "").trim();
  if (!t) return null;
  return { href: `https://pubpeer.com/search?q=${encodeURIComponent(t)}`, label: "PubPeer title search" };
}
